"""
帖子系统业务逻辑层
"""
from math import ceil
from typing import Optional, List, Tuple
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Q, F, Count, Exists, OuterRef
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.posts.models import Post, PostLike, PostMentionsUser, PostFlag
from apps.discussions.models import Discussion
from apps.discussions.models import DiscussionUser
from apps.users.models import User
from apps.users.services import UserService
import re


class PostService:
    """帖子服务"""

    @staticmethod
    def _can_view_post(post: Post, user: Optional[User]) -> bool:
        if post.hidden_at and not (user and user.is_staff):
            return False
        if post.approval_status == Post.APPROVAL_APPROVED:
            return True
        if user and user.is_staff:
            return True
        return bool(user and user.is_authenticated and post.approval_status == Post.APPROVAL_PENDING and post.user_id == user.id)

    @staticmethod
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
        requires_approval = UserService.requires_content_approval(user, "replyWithoutApproval")

        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            raise ValueError("讨论不存在")

        if discussion.approval_status != Discussion.APPROVAL_APPROVED and not user.is_staff:
            raise ValueError("讨论正在审核中，暂时无法回复")

        if discussion.is_locked and not user.is_staff:
            raise ValueError("讨论已锁定，无法回复")

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

                if user.preferences.get('follow_after_reply', False):
                    DiscussionUser.objects.update_or_create(
                        discussion=discussion,
                        user=user,
                        defaults={
                            'is_subscribed': True,
                            'last_read_at': timezone.now(),
                            'last_read_post_number': post.number,
                        }
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
        ).annotate(
            like_count=Count('likes')
        )

        # 过滤隐藏的帖子
        if not user or not user.is_staff:
            queryset = queryset.filter(hidden_at__isnull=True)

        if user and user.is_authenticated and not user.is_staff:
            queryset = queryset.filter(
                Q(approval_status=Post.APPROVAL_APPROVED)
                | Q(approval_status=Post.APPROVAL_PENDING, user=user)
            )
        elif not user or not user.is_authenticated:
            queryset = queryset.filter(approval_status=Post.APPROVAL_APPROVED)

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

        if not user or not user.is_staff:
            queryset = queryset.filter(hidden_at__isnull=True)

        if user and user.is_authenticated and not user.is_staff:
            queryset = queryset.filter(
                Q(approval_status=Post.APPROVAL_APPROVED)
                | Q(approval_status=Post.APPROVAL_PENDING, user=user)
            )
        elif not user or not user.is_authenticated:
            queryset = queryset.filter(approval_status=Post.APPROVAL_APPROVED)

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
            ).annotate(
                like_count=Count('likes')
            ).get(id=post_id)

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
            post.save()

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

            # 删除帖子
            post.delete()

            # 更新讨论统计
            discussion.comment_count = F('comment_count') - 1
            discussion.save()

            # 更新用户统计
            if post.user:
                post.user.comment_count = F('comment_count') - 1
                post.user.save(update_fields=['comment_count'])

        return True

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

            PostService._process_mentions(post, post.content)

            from apps.notifications.services import NotificationService
            NotificationService.notify_discussion_reply(
                discussion_id=discussion.id,
                post_id=post.id,
                from_user=post.user
            )

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
        if user.is_staff or user.is_superuser:
            return True
        if post.user_id == user.id:
            return True
        return False

    @staticmethod
    def can_delete_post(post: Post, user: User) -> bool:
        """检查用户是否可以删除帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if user.is_staff or user.is_superuser:
            return True
        # 普通用户只能删除自己的帖子
        if post.user_id == user.id:
            return True
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
