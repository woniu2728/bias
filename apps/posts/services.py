"""
帖子系统业务逻辑层
"""
from math import ceil
from typing import Optional, List, Tuple
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Q, F, Count, Exists, OuterRef, Prefetch
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.core.db import sqlite_write_retry
from apps.posts.models import Post, PostLike, PostMentionsUser, PostFlag
from apps.discussions.models import Discussion
from apps.discussions.models import DiscussionUser
from apps.tags.services import TagService
from apps.users.models import User
from apps.users.services import UserService
from apps.core.visibility import build_discussion_visibility_q, build_post_visibility_q
import re


class PostService:
    """帖子服务"""

    @staticmethod
    def annotate_flag_state(queryset, user: Optional[User] = None):
        if user and user.is_authenticated:
            queryset = queryset.annotate(
                viewer_has_open_flag=Exists(
                    PostFlag.objects.filter(
                        post=OuterRef("pk"),
                        user=user,
                        status=PostFlag.STATUS_OPEN,
                    )
                )
            )

        if user and user.is_staff:
            queryset = queryset.annotate(
                open_flag_count=Count(
                    "flags",
                    filter=Q(flags__status=PostFlag.STATUS_OPEN),
                    distinct=True,
                )
            ).prefetch_related(
                Prefetch(
                    "flags",
                    queryset=PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).select_related("user"),
                    to_attr="open_flags_cache",
                )
            )

        return queryset

    @staticmethod
    def _can_view_post(post: Post, user: Optional[User]) -> bool:
        discussion = getattr(post, "discussion", None)
        if discussion:
            if discussion.hidden_at and not (user and user.is_staff):
                can_view_rejected_own_discussion = bool(
                    user
                    and user.is_authenticated
                    and discussion.approval_status == Discussion.APPROVAL_REJECTED
                    and discussion.user_id == user.id
                )
                if not can_view_rejected_own_discussion:
                    return False
            if discussion.approval_status != Discussion.APPROVAL_APPROVED and not (user and user.is_staff):
                can_view_unapproved_own_discussion = bool(
                    user
                    and user.is_authenticated
                    and discussion.approval_status in {Discussion.APPROVAL_PENDING, Discussion.APPROVAL_REJECTED}
                    and discussion.user_id == user.id
                )
                if not can_view_unapproved_own_discussion:
                    return False

        if post.hidden_at and not (user and user.is_staff):
            can_view_rejected_own_post = bool(
                user
                and user.is_authenticated
                and post.approval_status == Post.APPROVAL_REJECTED
                and post.user_id == user.id
            )
            if not can_view_rejected_own_post:
                return False
        if not TagService.can_view_discussion_tags(post.discussion, user):
            return False
        if post.approval_status == Post.APPROVAL_APPROVED:
            return True
        if user and user.is_staff:
            return True
        return bool(
            user
            and user.is_authenticated
            and post.approval_status in {Post.APPROVAL_PENDING, Post.APPROVAL_REJECTED}
            and post.user_id == user.id
        )

    @staticmethod
    def apply_visibility_filters(queryset, user: Optional[User] = None):
        return queryset.filter(
            build_post_visibility_q(user),
            build_discussion_visibility_q(user, prefix="discussion__"),
        )

    @staticmethod
    @sqlite_write_retry()
    def create_post(
        discussion_id: int,
        content: str,
        user: User,
        reply_to_post_id: Optional[int] = None,
    ) -> Post:
        """
        创建帖子（回复讨论）

        Args:
            discussion_id: 讨论ID
            content: 帖子内容
            user: 创建者

        Returns:
            Post: 创建的帖子对象

        Raises:
            ValueError: 讨论不存在或已锁定
        """
        UserService.ensure_not_suspended(user, "回复讨论")
        UserService.ensure_email_confirmed(user, "回复讨论")
        UserService.ensure_forum_permission(user, "discussion.reply", "没有权限回复讨论")
        requires_approval = UserService.requires_content_approval(user, "replyWithoutApproval")

        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            raise ValueError("讨论不存在")

        if discussion.approval_status != Discussion.APPROVAL_APPROVED and not user.is_staff:
            raise ValueError("讨论正在审核中，暂时无法回复")

        if discussion.is_locked and not user.is_staff:
            raise ValueError("讨论已锁定，无法回复")

        TagService.ensure_can_reply_in_discussion(user, discussion)

        with transaction.atomic():
            # 获取下一个楼层号
            last_post = Post.objects.filter(discussion=discussion).order_by('-number').first()
            next_number = (last_post.number + 1) if last_post else 1

            reply_target = None
            if reply_to_post_id:
                reply_target = Post.objects.filter(
                    id=reply_to_post_id,
                    discussion=discussion,
                ).select_related('user').first()

            # 创建帖子
            post = Post.objects.create(
                discussion=discussion,
                number=next_number,
                user=user,
                content=content,
                content_html=PostService._render_markdown(content),
                type='comment',
                approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
                approved_at=None if requires_approval else timezone.now(),
                approved_by=None if requires_approval else user,
            )

            if not requires_approval:
                # 更新讨论统计
                discussion.comment_count = F('comment_count') + 1
                discussion.last_posted_at = timezone.now()
                discussion.last_posted_user = user
                discussion.last_post_id = post.id
                discussion.last_post_number = post.number
                discussion.save()

                # 更新用户统计
                user.comment_count = F('comment_count') + 1
                user.save(update_fields=['comment_count'])

                follow_after_reply = user.preferences.get('follow_after_reply', False)
                state_defaults = {
                    'last_read_at': timezone.now(),
                    'last_read_post_number': post.number,
                }
                if follow_after_reply:
                    state_defaults['is_subscribed'] = True
                DiscussionUser.objects.update_or_create(
                    discussion=discussion,
                    user=user,
                    defaults=state_defaults,
                )

                # 处理@提及
                PostService._process_mentions(post, content)

                # 发送通知：讨论有新回复
                from apps.notifications.services import NotificationService
                NotificationService.notify_discussion_reply(
                    discussion_id=discussion.id,
                    post_id=post.id,
                    from_user=user
                )
                if reply_target:
                    NotificationService.notify_post_reply(
                        reply_to_post_id=reply_target.id,
                        post_id=post.id,
                        from_user=user,
                    )
                TagService.refresh_discussion_tag_stats(discussion.id)

            return post

    @staticmethod
    def get_post_list(
        discussion_id: int,
        page: int = 1,
        limit: int = 20,
        user: Optional[User] = None,
    ) -> Tuple[List[Post], int]:
        """
        获取帖子列表

        Args:
            discussion_id: 讨论ID
            page: 页码
            limit: 每页数量
            user: 当前用户（用于判断点赞状态）

        Returns:
            Tuple[List[Post], int]: (帖子列表, 总数)
        """
        queryset = Post.objects.filter(
            discussion_id=discussion_id
        ).select_related(
            'user', 'edited_user'
        ).prefetch_related(
            'user__user_groups', 'edited_user__user_groups'
        ).annotate(
            like_count=Count('likes', distinct=True)
        )
        queryset = PostService.annotate_flag_state(queryset, user)

        queryset = PostService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_posts_for_user(queryset, user)

        # 排序
        queryset = queryset.order_by('number')

        # 分页
        total = queryset.count()
        offset = (page - 1) * limit
        posts = list(queryset[offset:offset + limit])

        # 添加点赞状态
        if user and user.is_authenticated:
            post_ids = [p.id for p in posts]
            liked_post_ids = set(
                PostLike.objects.filter(
                    post_id__in=post_ids,
                    user=user
                ).values_list('post_id', flat=True)
            )
            for post in posts:
                post.is_liked = post.id in liked_post_ids
        else:
            for post in posts:
                post.is_liked = False

        return posts, total

    @staticmethod
    def get_page_for_near_post(
        discussion_id: int,
        near: int,
        limit: int = 20,
        user: Optional[User] = None,
    ) -> int:
        queryset = Post.objects.filter(
            discussion_id=discussion_id,
            number__lte=near,
        )

        queryset = PostService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_posts_for_user(queryset, user)

        position = queryset.count()
        if position <= 0:
            return 1

        return max(1, ceil(position / limit))

    @staticmethod
    def get_post_by_id(post_id: int, user: Optional[User] = None) -> Optional[Post]:
        """
        获取帖子详情

        Args:
            post_id: 帖子ID
            user: 当前用户

        Returns:
            Optional[Post]: 帖子对象
        """
        try:
            post = Post.objects.select_related(
                'user', 'edited_user', 'discussion'
            ).prefetch_related(
                'user__user_groups', 'edited_user__user_groups'
            ).annotate(
                like_count=Count('likes', distinct=True)
            )
            post = PostService.annotate_flag_state(post, user).get(id=post_id)

            if not PostService._can_view_post(post, user):
                return None

            # 检查点赞状态
            if user and user.is_authenticated:
                post.is_liked = PostLike.objects.filter(
                    post=post, user=user
                ).exists()
            else:
                post.is_liked = False

            return post
        except Post.DoesNotExist:
            return None

    @staticmethod
    def update_post(
        post_id: int,
        user: User,
        content: str,
    ) -> Post:
        """
        更新帖子

        Args:
            post_id: 帖子ID
            user: 操作用户
            content: 新内容

        Returns:
            Post: 更新后的帖子对象

        Raises:
            PermissionDenied: 权限不足
        """
        UserService.ensure_not_suspended(user, "编辑帖子")
        post = Post.objects.get(id=post_id)

        # 权限检查
        if not PostService.can_edit_post(post, user):
            raise PermissionDenied("没有权限编辑此帖子")

        with transaction.atomic():
            post.content = content
            post.content_html = PostService._render_markdown(content)
            post.edited_at = timezone.now()
            post.edited_user = user
            update_fields = ['content', 'content_html', 'edited_at', 'edited_user']

            if (
                post.approval_status == Post.APPROVAL_REJECTED
                and not user.is_staff
                and post.user_id == user.id
            ):
                post.approval_status = Post.APPROVAL_PENDING
                post.approved_at = None
                post.approved_by = None
                post.approval_note = ""
                post.hidden_at = None
                post.hidden_user = None
                update_fields.extend([
                    'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
                ])

            post.save(update_fields=update_fields)

            # 重新处理@提及
            PostMentionsUser.objects.filter(post=post).delete()
            PostService._process_mentions(post, content)

            return post

    @staticmethod
    def delete_post(post_id: int, user: User) -> bool:
        """
        删除帖子

        Args:
            post_id: 帖子ID
            user: 操作用户

        Returns:
            bool: 是否删除成功

        Raises:
            PermissionDenied: 权限不足
        """
        UserService.ensure_not_suspended(user, "删除帖子")
        post = Post.objects.select_related('discussion').get(id=post_id)

        # 权限检查
        if not PostService.can_delete_post(post, user):
            raise PermissionDenied("没有权限删除此帖子")

        # 不能删除第一条帖子
        if post.number == 1:
            raise ValueError("不能删除第一条帖子")

        with transaction.atomic():
            discussion = post.discussion
            counted_post = post.approval_status == Post.APPROVAL_APPROVED

            # 删除帖子
            post.delete()

            if counted_post:
                PostService._refresh_discussion_approved_stats(discussion)

                if post.user:
                    post.user.comment_count = F('comment_count') - 1
                    post.user.save(update_fields=['comment_count'])

        return True

    @staticmethod
    def _refresh_discussion_approved_stats(discussion: Discussion) -> Discussion:
        approved_posts = Post.objects.filter(
            discussion=discussion,
            type="comment",
            approval_status=Post.APPROVAL_APPROVED,
            hidden_at__isnull=True,
        ).order_by("number")

        approved_count = approved_posts.count()
        last_post = approved_posts.order_by("-number").select_related("user").first()

        discussion.comment_count = approved_count
        if last_post:
            discussion.last_post_id = last_post.id
            discussion.last_post_number = last_post.number
            discussion.last_posted_at = last_post.created_at
            discussion.last_posted_user = last_post.user
        else:
            discussion.last_post_id = None
            discussion.last_post_number = None
            discussion.last_posted_at = None
            discussion.last_posted_user = None

        discussion.save(update_fields=[
            "comment_count",
            "last_post_id",
            "last_post_number",
            "last_posted_at",
            "last_posted_user",
        ])
        TagService.refresh_discussion_tag_stats(discussion.id)
        return discussion

    @staticmethod
    def like_post(post_id: int, user: User) -> bool:
        """
        点赞帖子

        Args:
            post_id: 帖子ID
            user: 操作用户

        Returns:
            bool: 是否点赞成功
        """
        UserService.ensure_not_suspended(user, "点赞帖子")
        post = Post.objects.get(id=post_id)
        if not PostService._can_view_post(post, user):
            raise PermissionDenied("没有权限查看此帖子")

        # 不能给自己的帖子点赞
        if post.user_id == user.id:
            raise ValueError("不能给自己的帖子点赞")

        # 检查是否已点赞
        if PostLike.objects.filter(post=post, user=user).exists():
            raise ValueError("已经点赞过了")

        try:
            PostLike.objects.create(post=post, user=user)
        except IntegrityError:
            raise ValueError("已经点赞过了")

        # 发送通知：帖子被点赞
        from apps.notifications.services import NotificationService
        NotificationService.notify_post_liked(post_id=post.id, from_user=user)

        return True

    @staticmethod
    def report_post(post_id: int, user: User, reason: str, message: str = "") -> PostFlag:
        """举报帖子"""
        UserService.ensure_not_suspended(user, "举报帖子")
        post = Post.objects.select_related("user", "discussion").get(id=post_id)
        if not PostService._can_view_post(post, user):
            raise PermissionDenied("没有权限查看此帖子")

        if not user or not user.is_authenticated:
            raise PermissionDenied("请先登录")
        if post.user_id == user.id:
            raise ValueError("不能举报自己的帖子")
        if post.hidden_at is not None:
            raise ValueError("该帖子已被隐藏")

        try:
            existing = PostFlag.objects.get(
                post=post,
                user=user,
                status=PostFlag.STATUS_OPEN,
            )
            existing.reason = reason
            existing.message = message
            existing.save(update_fields=["reason", "message"])
            return existing
        except PostFlag.DoesNotExist:
            return PostFlag.objects.create(
                post=post,
                user=user,
                reason=reason,
                message=message,
            )

    @staticmethod
    def get_flag_list(status: Optional[str] = None, page: int = 1, limit: int = 20):
        queryset = PostFlag.objects.select_related(
            "post",
            "post__discussion",
            "post__user",
            "user",
            "resolved_by",
        )

        if status:
            queryset = queryset.filter(status=status)

        total = queryset.count()
        offset = (page - 1) * limit
        return list(queryset[offset:offset + limit]), total

    @staticmethod
    def resolve_flag(flag_id: int, admin_user: User, status: str, resolution_note: str = "") -> PostFlag:
        if status not in {PostFlag.STATUS_RESOLVED, PostFlag.STATUS_IGNORED}:
            raise ValueError("无效的处理状态")

        flag = PostFlag.objects.select_related("post", "post__discussion", "user").get(id=flag_id)
        flag.status = status
        flag.resolution_note = resolution_note
        flag.resolved_by = admin_user
        flag.resolved_at = timezone.now()
        flag.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])
        return flag

    @staticmethod
    def resolve_post_flags(post_id: int, admin_user: User, status: str, resolution_note: str = "") -> int:
        if not admin_user.is_staff:
            raise PermissionDenied("只有管理员可以处理举报")

        if status not in {PostFlag.STATUS_RESOLVED, PostFlag.STATUS_IGNORED}:
            raise ValueError("无效的处理状态")

        open_flags = list(PostFlag.objects.filter(post_id=post_id, status=PostFlag.STATUS_OPEN))
        if not open_flags:
            raise ValueError("当前帖子没有待处理举报")

        resolved_at = timezone.now()
        for flag in open_flags:
            flag.status = status
            flag.resolution_note = resolution_note
            flag.resolved_by = admin_user
            flag.resolved_at = resolved_at

        PostFlag.objects.bulk_update(
            open_flags,
            ["status", "resolution_note", "resolved_by", "resolved_at"],
        )
        return len(open_flags)

    @staticmethod
    def approve_post(post: Post, admin_user: User, note: str = "") -> Post:
        with transaction.atomic():
            now = timezone.now()
            post.approval_status = Post.APPROVAL_APPROVED
            post.approved_at = now
            post.approved_by = admin_user
            post.approval_note = note
            post.hidden_at = None
            post.hidden_user = None
            post.save(update_fields=[
                'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
            ])

            discussion = post.discussion
            discussion.comment_count = F('comment_count') + 1
            if not discussion.last_post_number or post.number >= discussion.last_post_number:
                discussion.last_posted_at = now
                discussion.last_posted_user = post.user
                discussion.last_post_id = post.id
                discussion.last_post_number = post.number
            discussion.save()

            if post.user:
                post.user.comment_count = F('comment_count') + 1
                post.user.save(update_fields=['comment_count'])
                follow_after_reply = post.user.preferences.get('follow_after_reply', False)
                approval_defaults = {
                    'last_read_at': now,
                    'last_read_post_number': post.number,
                }
                if follow_after_reply:
                    approval_defaults['is_subscribed'] = True
                DiscussionUser.objects.update_or_create(
                    discussion=discussion,
                    user=post.user,
                    defaults=approval_defaults,
                )

            PostService._process_mentions(post, post.content)

            from apps.notifications.services import NotificationService
            NotificationService.notify_discussion_reply(
                discussion_id=discussion.id,
                post_id=post.id,
                from_user=post.user
            )
            NotificationService.notify_post_approved(post, admin_user, note=note)
            TagService.refresh_discussion_tag_stats(discussion.id)

        post.refresh_from_db()
        return post

    @staticmethod
    def reject_post(post: Post, admin_user: User, note: str = "") -> Post:
        rejected_at = timezone.now()
        post.approval_status = Post.APPROVAL_REJECTED
        post.approved_at = rejected_at
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = rejected_at
        post.hidden_user = admin_user
        post.save(update_fields=[
            'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
        ])

        from apps.notifications.services import NotificationService
        NotificationService.notify_post_rejected(post, admin_user, note=note)
        return post

    @staticmethod
    def unlike_post(post_id: int, user: User) -> bool:
        """
        取消点赞

        Args:
            post_id: 帖子ID
            user: 操作用户

        Returns:
            bool: 是否取消成功
        """
        UserService.ensure_not_suspended(user, "点赞帖子")
        post = Post.objects.get(id=post_id)
        if not PostService._can_view_post(post, user):
            raise PermissionDenied("没有权限查看此帖子")

        deleted_count, _ = PostLike.objects.filter(post=post, user=user).delete()
        if deleted_count == 0:
            raise ValueError("还没有点赞")

        return True

    @staticmethod
    def can_edit_post(post: Post, user: User) -> bool:
        """检查用户是否可以编辑帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if UserService.has_forum_permission(user, "discussion.edit"):
            return True
        if post.user_id == user.id:
            return UserService.has_forum_permission(user, "discussion.editOwn")
        return False

    @staticmethod
    def can_delete_post(post: Post, user: User) -> bool:
        """检查用户是否可以删除帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if UserService.has_forum_permission(user, "discussion.delete"):
            return True
        if post.user_id == user.id:
            return UserService.has_forum_permission(user, "discussion.deleteOwn")
        return False

    @staticmethod
    def can_like_post(post: Post, user: User) -> bool:
        """检查用户是否可以点赞帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if post.user_id == user.id:
            return False
        return True

    @staticmethod
    def _process_mentions(post: Post, content: str):
        """
        处理@提及

        Args:
            post: 帖子对象
            content: 帖子内容
        """
        # 匹配@username格式
        mentions = re.findall(r'@(\w+)', content)
        if not mentions:
            return

        # 查找被提及的用户
        mentioned_users = User.objects.filter(username__in=mentions)
        for mentioned_user in mentioned_users:
            PostMentionsUser.objects.get_or_create(
                post=post,
                mentions_user=mentioned_user
            )

            # 发送通知：用户被@提及
            from apps.notifications.services import NotificationService
            NotificationService.notify_user_mentioned(
                post_id=post.id,
                mentioned_user=mentioned_user,
                from_user=post.user
            )

    @staticmethod
    def _render_markdown(content: str) -> str:
        """
        渲染Markdown为HTML

        Args:
            content: Markdown内容

        Returns:
            str: HTML内容
        """
        from apps.core.markdown_service import MarkdownService
        return MarkdownService.render(content, sanitize=True)
