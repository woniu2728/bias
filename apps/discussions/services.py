"""
讨论系统业务逻辑层
"""
from typing import Optional, List, Tuple
from django.db import transaction
from django.db.models import Q, F, Count
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.core.db import sqlite_write_retry
from apps.discussions.models import Discussion, DiscussionUser
from apps.posts.models import Post
from apps.users.models import User
from apps.users.services import UserService
from apps.tags.models import Tag, DiscussionTag
from apps.tags.services import TagService
from apps.core.services import SearchService
from apps.core.visibility import build_discussion_visibility_q


class DiscussionService:
    """讨论服务"""

    VIEW_COUNT_THROTTLE_SECONDS = 60 * 15

    @staticmethod
    def _viewer_cache_identity(user: Optional[User]) -> str:
        if user and user.is_authenticated:
            return f"user:{user.id}"
        return "guest"

    @staticmethod
    def _view_count_cache_key(discussion_id: int, user: Optional[User]) -> str:
        return f"discussion.viewed.{discussion_id}.{DiscussionService._viewer_cache_identity(user)}"

    @staticmethod
    def record_view(discussion: Discussion, user: Optional[User] = None) -> bool:
        cache_key = DiscussionService._view_count_cache_key(discussion.id, user)
        try:
            if cache.get(cache_key):
                return False
            cache.set(cache_key, True, DiscussionService.VIEW_COUNT_THROTTLE_SECONDS)
        except Exception:
            pass

        Discussion.objects.filter(id=discussion.id).update(view_count=F('view_count') + 1)
        discussion.view_count = (discussion.view_count or 0) + 1
        return True

    @staticmethod
    def _can_view_discussion(discussion: Discussion, user: Optional[User]) -> bool:
        if discussion.hidden_at and not (user and user.is_staff):
            can_view_rejected_own_discussion = bool(
                user
                and user.is_authenticated
                and discussion.approval_status == Discussion.APPROVAL_REJECTED
                and discussion.user_id == user.id
            )
            if not can_view_rejected_own_discussion:
                return False
        if not TagService.can_view_discussion_tags(discussion, user):
            return False
        if discussion.approval_status == Discussion.APPROVAL_APPROVED:
            return True
        if user and user.is_staff:
            return True
        return bool(
            user
            and user.is_authenticated
            and discussion.approval_status in {Discussion.APPROVAL_PENDING, Discussion.APPROVAL_REJECTED}
            and discussion.user_id == user.id
        )

    @staticmethod
    def apply_visibility_filters(queryset, user: Optional[User] = None):
        return queryset.filter(build_discussion_visibility_q(user))

    @staticmethod
    @sqlite_write_retry()
    def create_discussion(
        title: str,
        content: str,
        user: User,
        tag_ids: Optional[List[int]] = None
    ) -> Discussion:
        """
        创建讨论

        Args:
            title: 讨论标题
            content: 第一条帖子内容
            user: 创建者
            tag_ids: 标签ID列表

        Returns:
            Discussion: 创建的讨论对象
        """
        UserService.ensure_not_suspended(user, "发布讨论")
        UserService.ensure_email_confirmed(user, "发布讨论")
        UserService.ensure_forum_permission(user, "startDiscussion", "没有权限发起讨论")
        requires_approval = UserService.requires_content_approval(user, "startDiscussionWithoutApproval")
        approval_status = Discussion.APPROVAL_PENDING if requires_approval else Discussion.APPROVAL_APPROVED
        approved_at = None if requires_approval else timezone.now()
        approved_by = None if requires_approval else user
        tags = TagService.ensure_can_start_discussion(user, tag_ids)

        with transaction.atomic():
            # 创建讨论
            discussion = Discussion.objects.create(
                title=title,
                user=user,
                last_posted_at=timezone.now(),
                last_posted_user=user,
                approval_status=approval_status,
                approved_at=approved_at,
                approved_by=approved_by,
            )

            # 创建第一条帖子
            first_post = Post.objects.create(
                discussion=discussion,
                number=1,
                user=user,
                content=content,
                content_html=DiscussionService._render_markdown(content),
                type='comment',
                approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
                approved_at=approved_at,
                approved_by=approved_by,
            )

            # 更新讨论的第一条帖子ID
            discussion.first_post_id = first_post.id
            discussion.last_post_id = first_post.id
            discussion.last_post_number = 1
            discussion.comment_count = 1
            discussion.participant_count = 1
            discussion.save()

            # 添加标签
            if tags:
                for tag in tags:
                    DiscussionTag.objects.create(discussion=discussion, tag=tag)
                TagService.refresh_tag_stats([tag.id for tag in tags])

            # 更新用户统计
            if not requires_approval:
                user.discussion_count = F('discussion_count') + 1
                user.save(update_fields=['discussion_count'])

            # 创建用户阅读状态
            DiscussionUser.objects.create(
                discussion=discussion,
                user=user,
                last_read_at=timezone.now(),
                last_read_post_number=1,
                is_subscribed=user.preferences.get('follow_after_create', False),
            )

            return discussion

    @staticmethod
    def get_discussion_list(
        q: Optional[str] = None,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        subscription: Optional[str] = None,
        sort: str = 'latest',
        page: int = 1,
        limit: int = 20,
        user: Optional[User] = None,
    ) -> Tuple[List[Discussion], int]:
        """
        获取讨论列表

        Args:
            q: 搜索关键词
            tag: 标签slug
            author: 作者用户名
            sort: 排序方式
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Discussion], int]: (讨论列表, 总数)
        """
        queryset = Discussion.objects.select_related(
            'user', 'last_posted_user'
        ).prefetch_related('discussion_tags__tag', 'user__user_groups', 'last_posted_user__user_groups')

        queryset = DiscussionService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_discussions_for_user(queryset, user)

        # 搜索
        if q:
            queryset = queryset.filter(SearchService.build_discussion_search_query(q))
            queryset = queryset.filter(
                Q(posts__isnull=True) |
                Q(posts__type='comment', posts__hidden_at__isnull=True)
            )

        # 按标签过滤
        if tag:
            queryset = queryset.filter(discussion_tags__tag__slug=tag)

        # 按作者过滤
        if author:
            queryset = queryset.filter(user__username=author)

        # 订阅过滤
        if subscription == 'following':
            if not user or not user.is_authenticated:
                return [], 0

            queryset = queryset.filter(
                user_states__user=user,
                user_states__is_subscribed=True,
            )

        # 排序
        if sort == 'latest':
            queryset = queryset.order_by('-is_sticky', '-last_posted_at')
        elif sort == 'top':
            queryset = queryset.order_by('-is_sticky', '-comment_count', '-view_count')
        elif sort == 'oldest':
            queryset = queryset.order_by('-is_sticky', 'created_at')
        elif sort == 'newest':
            queryset = queryset.order_by('-is_sticky', '-created_at')
        else:
            queryset = queryset.order_by('-is_sticky', '-last_posted_at')

        # 分页
        queryset = queryset.distinct()
        total = queryset.count()
        offset = (page - 1) * limit
        discussions = list(queryset[offset:offset + limit])

        DiscussionService._attach_user_read_state(discussions, user)

        return discussions, total

    @staticmethod
    def get_discussion_by_id(discussion_id: int, user: Optional[User] = None) -> Optional[Discussion]:
        """
        获取讨论详情

        Args:
            discussion_id: 讨论ID
            user: 当前用户（用于更新阅读状态）

        Returns:
            Optional[Discussion]: 讨论对象
        """
        try:
            discussion = Discussion.objects.select_related(
                'user', 'last_posted_user'
            ).prefetch_related('discussion_tags__tag', 'user__user_groups', 'last_posted_user__user_groups').get(id=discussion_id)

            if not DiscussionService._can_view_discussion(discussion, user):
                return None

            # 增加浏览次数，同一访问者短时间内只计一次，减少热门讨论写压力。
            DiscussionService.record_view(discussion, user)

            # 仅附加当前阅读状态，不在进入讨论页时直接清空未读
            if user and user.is_authenticated:
                DiscussionUser.objects.get_or_create(
                    discussion=discussion,
                    user=user,
                    defaults={
                        'last_read_at': timezone.now(),
                        'last_read_post_number': 1 if discussion.last_post_number else 0,
                    }
                )
                DiscussionService._attach_user_read_state([discussion], user)
            else:
                discussion.is_subscribed = False
                discussion.last_read_at = None
                discussion.last_read_post_number = 0
                discussion.unread_count = discussion.last_post_number or 0
                discussion.is_unread = discussion.unread_count > 0

            return discussion
        except Discussion.DoesNotExist:
            return None

    @staticmethod
    def _attach_user_read_state(discussions: List[Discussion], user: Optional[User]) -> None:
        if not discussions:
            return

        if not user or not user.is_authenticated:
            for discussion in discussions:
                discussion.is_subscribed = False
                discussion.last_read_at = None
                discussion.last_read_post_number = 0
                discussion.unread_count = 0
                discussion.is_unread = False
            return

        states = {
            state.discussion_id: state
            for state in DiscussionUser.objects.filter(
                user=user,
                discussion_id__in=[discussion.id for discussion in discussions],
            )
        }
        marked_all_as_read_at = getattr(user, 'marked_all_as_read_at', None)

        for discussion in discussions:
            state = states.get(discussion.id)
            last_read_at = state.last_read_at if state else None
            last_read_post_number = state.last_read_post_number if state else 0

            if (
                marked_all_as_read_at
                and discussion.last_posted_at
                and discussion.last_posted_at <= marked_all_as_read_at
            ):
                last_read_at = marked_all_as_read_at
                last_read_post_number = max(last_read_post_number, discussion.last_post_number or 0)

            discussion.is_subscribed = bool(state and state.is_subscribed)
            discussion.last_read_at = last_read_at
            discussion.last_read_post_number = last_read_post_number
            discussion.unread_count = max((discussion.last_post_number or 0) - last_read_post_number, 0)
            discussion.is_unread = discussion.unread_count > 0

    @staticmethod
    def mark_all_as_read(user: User):
        now = timezone.now()
        user.marked_all_as_read_at = now
        user.save(update_fields=['marked_all_as_read_at'])
        return now

    @staticmethod
    def update_read_state(discussion_id: int, user: User, last_read_post_number: int) -> DiscussionUser:
        discussion = Discussion.objects.get(id=discussion_id)
        if not DiscussionService._can_view_discussion(discussion, user):
            raise PermissionDenied("没有权限查看此讨论")

        clamped_number = max(1, min(last_read_post_number, discussion.last_post_number or 1))
        state, _ = DiscussionUser.objects.get_or_create(
            discussion=discussion,
            user=user,
            defaults={
                'last_read_at': timezone.now(),
                'last_read_post_number': clamped_number,
            }
        )

        next_number = max(state.last_read_post_number, clamped_number)
        update_fields = []
        if next_number != state.last_read_post_number:
            state.last_read_post_number = next_number
            update_fields.append('last_read_post_number')

        now = timezone.now()
        if not state.last_read_at or next_number >= state.last_read_post_number:
            state.last_read_at = now
            update_fields.append('last_read_at')

        if update_fields:
            state.save(update_fields=update_fields)

        return state

    @staticmethod
    def get_subscription_state(discussion: Discussion, user: Optional[User]) -> bool:
        if not user or not user.is_authenticated:
            return False

        state = DiscussionUser.objects.filter(
            discussion=discussion,
            user=user,
            is_subscribed=True,
        ).exists()
        return state

    @staticmethod
    def subscribe_discussion(discussion_id: int, user: User) -> bool:
        UserService.ensure_not_suspended(user, "关注讨论")
        discussion = Discussion.objects.get(id=discussion_id)
        state, _ = DiscussionUser.objects.get_or_create(
            discussion=discussion,
            user=user,
            defaults={
                'last_read_at': timezone.now(),
                'last_read_post_number': discussion.last_post_number or 0,
            }
        )
        if state.is_subscribed:
            return False
        state.is_subscribed = True
        state.save(update_fields=['is_subscribed'])
        return True

    @staticmethod
    def unsubscribe_discussion(discussion_id: int, user: User) -> bool:
        UserService.ensure_not_suspended(user, "关注讨论")
        discussion = Discussion.objects.get(id=discussion_id)
        state, _ = DiscussionUser.objects.get_or_create(
            discussion=discussion,
            user=user,
            defaults={
                'last_read_at': timezone.now(),
                'last_read_post_number': discussion.last_post_number or 0,
            }
        )
        if not state.is_subscribed:
            return False
        state.is_subscribed = False
        state.save(update_fields=['is_subscribed'])
        return True

    @staticmethod
    def update_discussion(
        discussion_id: int,
        user: User,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
        is_locked: Optional[bool] = None,
        is_sticky: Optional[bool] = None,
        is_hidden: Optional[bool] = None,
    ) -> Discussion:
        """
        更新讨论

        Args:
            discussion_id: 讨论ID
            user: 操作用户
            title: 新标题
            is_locked: 是否锁定
            is_sticky: 是否置顶
            is_hidden: 是否隐藏

        Returns:
            Discussion: 更新后的讨论对象

        Raises:
            PermissionDenied: 权限不足
        """
        UserService.ensure_not_suspended(user, "编辑讨论")
        discussion = Discussion.objects.get(id=discussion_id)

        # 权限检查
        if not DiscussionService.can_edit_discussion(discussion, user):
            raise PermissionDenied("没有权限编辑此讨论")

        with transaction.atomic():
            previous_tag_ids = list(discussion.discussion_tags.values_list('tag_id', flat=True))
            first_post = None
            if content is not None:
                first_post = Post.objects.get(id=discussion.first_post_id)

            if title is not None:
                discussion.title = title
            if content is not None and first_post is not None:
                first_post.content = content
                first_post.content_html = DiscussionService._render_markdown(content)
                first_post.edited_at = timezone.now()
                first_post.edited_user = user
                first_post.save(update_fields=['content', 'content_html', 'edited_at', 'edited_user'])

            if tag_ids is not None:
                tags = TagService.ensure_can_start_discussion(user, tag_ids)
                DiscussionTag.objects.filter(discussion=discussion).delete()
                DiscussionTag.objects.bulk_create([
                    DiscussionTag(discussion=discussion, tag=tag)
                    for tag in tags
                ])

            if is_locked is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限锁定/解锁讨论")
                discussion.is_locked = is_locked

            if is_sticky is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限置顶/取消置顶讨论")
                discussion.is_sticky = is_sticky

            if is_hidden is not None:
                DiscussionService.set_hidden_state(discussion, user, is_hidden)

            if (
                discussion.approval_status == Discussion.APPROVAL_REJECTED
                and not user.is_staff
                and discussion.user_id == user.id
            ):
                discussion.approval_status = Discussion.APPROVAL_PENDING
                discussion.approved_at = None
                discussion.approved_by = None
                discussion.approval_note = ""
                discussion.hidden_at = None
                discussion.hidden_user = None

                if first_post is None:
                    first_post = Post.objects.get(id=discussion.first_post_id)
                first_post.approval_status = Post.APPROVAL_PENDING
                first_post.approved_at = None
                first_post.approved_by = None
                first_post.approval_note = ""
                first_post.hidden_at = None
                first_post.hidden_user = None
                first_post.save(update_fields=[
                    'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
                ])

            discussion.save()
            if is_hidden is not None or tag_ids is not None:
                refreshed_tag_ids = set(previous_tag_ids) | set(discussion.discussion_tags.values_list('tag_id', flat=True))
                if refreshed_tag_ids:
                    TagService.refresh_tag_stats(list(refreshed_tag_ids))
            return discussion

    @staticmethod
    def set_hidden_state(discussion: Discussion, user: User, is_hidden: bool) -> Discussion:
        if not user.is_staff:
            raise PermissionDenied("没有权限隐藏/显示讨论")

        discussion.hidden_at = timezone.now() if is_hidden else None
        discussion.hidden_user = user if is_hidden else None
        discussion.save(update_fields=["hidden_at", "hidden_user"])
        TagService.refresh_discussion_tag_stats(discussion.id)
        return discussion

    @staticmethod
    def approve_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        with transaction.atomic():
            discussion.approval_status = Discussion.APPROVAL_APPROVED
            discussion.approved_at = timezone.now()
            discussion.approved_by = admin_user
            discussion.approval_note = note
            discussion.hidden_at = None
            discussion.hidden_user = None
            discussion.save(update_fields=[
                'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
            ])

            Post.objects.filter(id=discussion.first_post_id).update(
                approval_status=Post.APPROVAL_APPROVED,
                approved_at=discussion.approved_at,
                approved_by=admin_user,
                approval_note=note,
                hidden_at=None,
                hidden_user=None,
            )

            if discussion.user:
                discussion.user.discussion_count = F('discussion_count') + 1
                discussion.user.save(update_fields=['discussion_count'])

            from apps.notifications.services import NotificationService
            NotificationService.notify_discussion_approved(discussion, admin_user, note=note)
            TagService.refresh_discussion_tag_stats(discussion.id)

        discussion.refresh_from_db()
        return discussion

    @staticmethod
    def reject_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        rejected_at = timezone.now()
        with transaction.atomic():
            discussion.approval_status = Discussion.APPROVAL_REJECTED
            discussion.approved_at = rejected_at
            discussion.approved_by = admin_user
            discussion.approval_note = note
            discussion.hidden_at = rejected_at
            discussion.hidden_user = admin_user
            discussion.save(update_fields=[
                'approval_status', 'approved_at', 'approved_by', 'approval_note', 'hidden_at', 'hidden_user'
            ])

            Post.objects.filter(id=discussion.first_post_id).update(
                approval_status=Post.APPROVAL_REJECTED,
                approved_at=rejected_at,
                approved_by=admin_user,
                approval_note=note,
                hidden_at=rejected_at,
                hidden_user=admin_user,
            )

            from apps.notifications.services import NotificationService
            NotificationService.notify_discussion_rejected(discussion, admin_user, note=note)
            TagService.refresh_discussion_tag_stats(discussion.id)

        discussion.refresh_from_db()
        return discussion

    @staticmethod
    def delete_discussion(discussion_id: int, user: User) -> bool:
        """
        删除讨论

        Args:
            discussion_id: 讨论ID
            user: 操作用户

        Returns:
            bool: 是否删除成功

        Raises:
            PermissionDenied: 权限不足
        """
        UserService.ensure_not_suspended(user, "删除讨论")
        discussion = Discussion.objects.get(id=discussion_id)

        # 权限检查
        if not DiscussionService.can_delete_discussion(discussion, user):
            raise PermissionDenied("没有权限删除此讨论")

        with transaction.atomic():
            approved_discussion = discussion.approval_status == Discussion.APPROVAL_APPROVED
            approved_reply_counts = {}
            approved_replies = (
                Post.objects.filter(
                    discussion=discussion,
                    type="comment",
                    approval_status=Post.APPROVAL_APPROVED,
                    number__gt=1,
                )
                .exclude(user_id__isnull=True)
                .values("user_id")
                .annotate(total=Count("id"))
            )
            for row in approved_replies:
                approved_reply_counts[row["user_id"]] = row["total"]

            # 删除相关帖子
            Post.objects.filter(discussion=discussion).delete()
            tag_ids = list(discussion.discussion_tags.values_list('tag_id', flat=True))

            # 删除讨论
            discussion.delete()

            if tag_ids:
                from apps.tags.services import TagService
                TagService.refresh_tag_stats(tag_ids)

            # 更新作者讨论数
            if approved_discussion and discussion.user:
                discussion.user.discussion_count = F('discussion_count') - 1
                discussion.user.save(update_fields=['discussion_count'])

            # 更新回复作者评论数
            for user_id, total in approved_reply_counts.items():
                User.objects.filter(id=user_id).update(comment_count=F("comment_count") - total)

        return True

    @staticmethod
    def can_edit_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以编辑讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if UserService.has_forum_permission(user, "discussion.edit"):
            return True
        if discussion.user_id == user.id:
            return UserService.has_forum_permission(user, "discussion.editOwn")
        return False

    @staticmethod
    def can_delete_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以删除讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if UserService.has_forum_permission(user, "discussion.delete"):
            return True
        if discussion.user_id == user.id:
            return UserService.has_forum_permission(user, "discussion.deleteOwn")
        return False

    @staticmethod
    def can_reply_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以回复讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if not UserService.has_forum_permission(user, "discussion.reply"):
            return False
        if discussion.approval_status != Discussion.APPROVAL_APPROVED and not user.is_staff:
            return False
        if discussion.is_locked and not user.is_staff:
            return False
        if not TagService.can_reply_in_discussion(discussion, user):
            return False
        return True

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
