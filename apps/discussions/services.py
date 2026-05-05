"""
讨论系统业务逻辑层
"""
from typing import Optional, List, Tuple
from django.db import transaction
from django.db.models import F, Count
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.core.db import sqlite_write_retry
from apps.core.domain_events import get_forum_event_bus
from apps.core.forum_events import DiscussionApprovedEvent, DiscussionCreatedEvent
from apps.core.forum_registry import get_forum_registry
from apps.discussions.models import Discussion, DiscussionUser
from apps.posts.models import Post
from apps.users.models import User
from apps.users.preferences import get_user_preference_value
from apps.users.services import UserService
from apps.tags.models import Tag, DiscussionTag
from apps.tags.services import TagService
from apps.core.services import PaginationService, SearchService
from apps.core.visibility import build_discussion_visibility_q


FORUM_REGISTRY = get_forum_registry()
DEFAULT_POST_TYPE = FORUM_REGISTRY.get_default_post_type_code()
DISCUSSION_COUNTED_POST_TYPES = FORUM_REGISTRY.get_discussion_counted_post_type_codes()
USER_COUNTED_POST_TYPES = FORUM_REGISTRY.get_user_counted_post_type_codes()
DISCUSSION_RENAMED_POST_TYPE = "discussionRenamed"
DISCUSSION_LOCKED_POST_TYPE = "discussionLocked"
DISCUSSION_STICKY_POST_TYPE = "discussionSticky"
DISCUSSION_TAGGED_POST_TYPE = "discussionTagged"
DISCUSSION_HIDDEN_POST_TYPE = "discussionHidden"
DISCUSSION_APPROVED_POST_TYPE = "discussionApproved"
DISCUSSION_REJECTED_POST_TYPE = "discussionRejected"
DISCUSSION_RESUBMITTED_POST_TYPE = "discussionResubmitted"


class DiscussionService:
    """讨论服务"""

    VIEW_COUNT_THROTTLE_SECONDS = 60 * 15
    VIEW_COUNT_FLUSH_DELAY_SECONDS = 60
    VIEW_COUNT_CACHE_TIMEOUT = 60 * 60 * 24
    VIEW_COUNT_PENDING_IDS_CACHE_KEY = "discussion.view_count.pending.ids"

    @staticmethod
    def normalize_discussion_sort(sort: str | None) -> str:
        return FORUM_REGISTRY.get_discussion_sort(sort or "").code

    @staticmethod
    def get_discussion_sort_catalog():
        return FORUM_REGISTRY.get_discussion_sorts()

    @staticmethod
    def normalize_discussion_list_filter(filter_code: str | None) -> str:
        return FORUM_REGISTRY.get_discussion_list_filter(filter_code or "").code

    @staticmethod
    def get_discussion_list_filter_catalog():
        return FORUM_REGISTRY.get_discussion_list_filters()

    @staticmethod
    def _viewer_cache_identity(user: Optional[User]) -> str:
        if user and user.is_authenticated:
            return f"user:{user.id}"
        return "guest"

    @staticmethod
    def _view_count_cache_key(discussion_id: int, user: Optional[User]) -> str:
        return f"discussion.viewed.{discussion_id}.{DiscussionService._viewer_cache_identity(user)}"

    @staticmethod
    def _view_count_pending_cache_key(discussion_id: int) -> str:
        return f"discussion.view_count.pending.{discussion_id}"

    @staticmethod
    def _view_count_flush_lock_cache_key(discussion_id: int) -> str:
        return f"discussion.view_count.flush_lock.{discussion_id}"

    @staticmethod
    def record_view(discussion: Discussion, user: Optional[User] = None) -> bool:
        cache_key = DiscussionService._view_count_cache_key(discussion.id, user)
        try:
            if cache.get(cache_key):
                return False
            cache.set(cache_key, True, DiscussionService.VIEW_COUNT_THROTTLE_SECONDS)
        except Exception:
            pass

        try:
            pending_count = DiscussionService._increment_pending_view_count(discussion.id)
            DiscussionService.dispatch_view_count_flush(discussion.id, pending_count=pending_count)
        except Exception:
            Discussion.objects.filter(id=discussion.id).update(view_count=F('view_count') + 1)

        discussion.view_count = (discussion.view_count or 0) + 1
        return True

    @staticmethod
    def _increment_pending_view_count(discussion_id: int) -> int:
        pending_key = DiscussionService._view_count_pending_cache_key(discussion_id)
        cache.add(pending_key, 0, DiscussionService.VIEW_COUNT_CACHE_TIMEOUT)
        pending_count = cache.incr(pending_key)
        DiscussionService._remember_pending_view_discussion(discussion_id)
        return int(pending_count or 0)

    @staticmethod
    def _remember_pending_view_discussion(discussion_id: int) -> None:
        pending_ids = cache.get(DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY) or []
        if discussion_id not in pending_ids:
            pending_ids.append(discussion_id)
            cache.set(
                DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
                pending_ids,
                DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            )

    @staticmethod
    def dispatch_view_count_flush(discussion_id: int, pending_count: int = 0):
        from apps.core.queue_service import QueueService
        from apps.discussions.tasks import flush_discussion_view_count_task

        def fallback():
            return DiscussionService.flush_pending_view_count(discussion_id)

        if QueueService.should_enqueue():
            lock_key = DiscussionService._view_count_flush_lock_cache_key(discussion_id)
            lock_timeout = DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS + 30
            if cache.add(lock_key, True, lock_timeout):
                return QueueService.dispatch_celery_task(
                    flush_discussion_view_count_task,
                    discussion_id,
                    countdown=DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS,
                    fallback=fallback,
                )
            return None

        return QueueService.dispatch_celery_task(
            flush_discussion_view_count_task,
            discussion_id,
            fallback=fallback,
        )

    @staticmethod
    def flush_pending_view_count(discussion_id: int) -> int:
        pending_key = DiscussionService._view_count_pending_cache_key(discussion_id)
        lock_key = DiscussionService._view_count_flush_lock_cache_key(discussion_id)
        cache.delete(lock_key)

        try:
            pending_count = int(cache.get(pending_key) or 0)
        except (TypeError, ValueError):
            pending_count = 0
        if pending_count <= 0:
            return 0

        try:
            remaining = cache.decr(pending_key, pending_count)
            if remaining <= 0:
                cache.delete(pending_key)
        except Exception:
            cache.delete(pending_key)
            remaining = 0

        Discussion.objects.filter(id=discussion_id).update(view_count=F('view_count') + pending_count)
        if remaining > 0:
            DiscussionService.dispatch_view_count_flush(discussion_id, pending_count=remaining)
        return pending_count

    @staticmethod
    def flush_all_pending_view_counts() -> int:
        pending_ids = cache.get(DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY) or []
        flushed_count = 0
        active_ids = []
        for discussion_id in pending_ids:
            flushed_count += DiscussionService.flush_pending_view_count(int(discussion_id))
            if cache.get(DiscussionService._view_count_pending_cache_key(int(discussion_id))):
                active_ids.append(int(discussion_id))

        if active_ids:
            cache.set(
                DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
                active_ids,
                DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            )
        else:
            cache.delete(DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY)
        return flushed_count

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
                type=DEFAULT_POST_TYPE,
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
                is_subscribed=get_user_preference_value(user, 'follow_after_create', fallback=False),
            )

            get_forum_event_bus().dispatch(
                DiscussionCreatedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=user.id,
                    tag_ids=tuple(tag.id for tag in tags),
                    is_approved=not requires_approval,
                )
            )
            return discussion

    @staticmethod
    def get_discussion_list(
        q: Optional[str] = None,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        list_filter: str = 'all',
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
        page, limit = PaginationService.normalize(page, limit)
        queryset = Discussion.objects.select_related(
            'user', 'last_posted_user'
        ).prefetch_related('discussion_tags__tag', 'user__user_groups', 'last_posted_user__user_groups')

        queryset = DiscussionService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_discussions_for_user(queryset, user)

        # 搜索
        if q:
            queryset = SearchService.apply_discussion_search(queryset, q, user=user)

        # 按标签过滤
        if tag:
            queryset = queryset.filter(discussion_tags__tag__slug=tag)

        # 按作者过滤
        if author:
            queryset = queryset.filter(user__username=author)

        filter_definition = FORUM_REGISTRY.get_discussion_list_filter(list_filter)
        queryset = filter_definition.applier(
            queryset,
            {
                "user": user,
                "filter": filter_definition.code,
                "query": q,
                "tag": tag,
                "author": author,
            },
        )

        # 排序
        sort_definition = FORUM_REGISTRY.get_discussion_sort(sort)
        queryset = sort_definition.applier(
            queryset,
            {
                "user": user,
                "sort": sort_definition.code,
                "query": q,
                "tag": tag,
                "author": author,
                "filter": filter_definition.code,
            },
        )

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
            previous_tag_names = list(
                discussion.discussion_tags.select_related("tag")
                .order_by("tag__name")
                .values_list("tag__name", flat=True)
            )
            first_post = None
            previous_title = discussion.title
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

            should_persist_discussion = True

            if is_locked is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限锁定/解锁讨论")
                DiscussionService.set_locked_state(discussion, user, is_locked)
                should_persist_discussion = False

            if is_sticky is not None:
                if not user.is_staff:
                    raise PermissionDenied("没有权限置顶/取消置顶讨论")
                DiscussionService.set_sticky_state(discussion, user, is_sticky)

            if is_hidden is not None:
                DiscussionService.set_hidden_state(discussion, user, is_hidden)

            if (
                discussion.approval_status == Discussion.APPROVAL_REJECTED
                and not user.is_staff
                and discussion.user_id == user.id
            ):
                previous_approval_status = discussion.approval_status
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
                DiscussionService._create_system_event_post(
                    discussion=discussion,
                    actor=user,
                    post_type=DISCUSSION_RESUBMITTED_POST_TYPE,
                    content=(
                        f"previous_status: {previous_approval_status}\n"
                        "note:"
                    ),
                )

            if should_persist_discussion:
                discussion.save()
            if title is not None and title != previous_title:
                DiscussionService._create_system_event_post(
                    discussion=discussion,
                    actor=user,
                    post_type=DISCUSSION_RENAMED_POST_TYPE,
                    content=f"from: {previous_title}\nto: {title}",
                )
            if tag_ids is not None:
                current_tag_names = list(
                    discussion.discussion_tags.select_related("tag")
                    .order_by("tag__name")
                    .values_list("tag__name", flat=True)
                )
                added_tags = [name for name in current_tag_names if name not in previous_tag_names]
                removed_tags = [name for name in previous_tag_names if name not in current_tag_names]
                if added_tags or removed_tags:
                    DiscussionService._create_system_event_post(
                        discussion=discussion,
                        actor=user,
                        post_type=DISCUSSION_TAGGED_POST_TYPE,
                        content=(
                            f"added:{'|'.join(added_tags)}\n"
                            f"removed:{'|'.join(removed_tags)}"
                        ),
                    )
            if is_hidden is not None or tag_ids is not None:
                refreshed_tag_ids = set(previous_tag_ids) | set(discussion.discussion_tags.values_list('tag_id', flat=True))
                if refreshed_tag_ids:
                    TagService.dispatch_refresh_tag_stats(list(refreshed_tag_ids))
            return discussion

    @staticmethod
    def set_hidden_state(discussion: Discussion, user: User, is_hidden: bool) -> Discussion:
        if not user.is_staff:
            raise PermissionDenied("没有权限隐藏/显示讨论")

        was_hidden = discussion.hidden_at is not None
        if was_hidden == is_hidden:
            return discussion

        should_adjust_counts = discussion.approval_status == Discussion.APPROVAL_APPROVED
        approved_reply_counts = {}
        if should_adjust_counts:
            approved_reply_counts = DiscussionService._approved_reply_counts_by_author(discussion)

        discussion.hidden_at = timezone.now() if is_hidden else None
        discussion.hidden_user = user if is_hidden else None

        with transaction.atomic():
            discussion.save(update_fields=["hidden_at", "hidden_user"])
            if should_adjust_counts:
                discussion_delta = -1 if is_hidden else 1
                reply_delta = -1 if is_hidden else 1
                if discussion.user:
                    User.objects.filter(id=discussion.user_id).update(
                        discussion_count=F('discussion_count') + discussion_delta
                    )
                for user_id, total in approved_reply_counts.items():
                    User.objects.filter(id=user_id).update(comment_count=F("comment_count") + (reply_delta * total))

            DiscussionService._create_system_event_post(
                discussion=discussion,
                actor=user,
                post_type=DISCUSSION_HIDDEN_POST_TYPE,
                content="hidden" if is_hidden else "restored",
            )
            TagService.refresh_discussion_tag_stats(discussion.id)
        return discussion

    @staticmethod
    def approve_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        previous_status = discussion.approval_status
        was_counted = discussion.approval_status == Discussion.APPROVAL_APPROVED
        approved_reply_counts = {}
        if not was_counted:
            approved_reply_counts = DiscussionService._approved_reply_counts_by_author(discussion)

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

            if not was_counted:
                if discussion.user:
                    User.objects.filter(id=discussion.user_id).update(discussion_count=F('discussion_count') + 1)
                for user_id, total in approved_reply_counts.items():
                    User.objects.filter(id=user_id).update(comment_count=F("comment_count") + total)

            if not was_counted:
                get_forum_event_bus().dispatch(
                    DiscussionApprovedEvent(
                        discussion_id=discussion.id,
                        admin_user_id=admin_user.id,
                        note=note,
                    )
                )
            else:
                TagService.refresh_discussion_tag_stats(discussion.id)

            DiscussionService._create_system_event_post(
                discussion=discussion,
                actor=admin_user,
                post_type=DISCUSSION_APPROVED_POST_TYPE,
                content=(
                    f"previous_status: {previous_status}\n"
                    f"note: {note}"
                ),
            )

        discussion.refresh_from_db()
        return discussion

    @staticmethod
    def reject_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        rejected_at = timezone.now()
        previous_status = discussion.approval_status
        was_counted = discussion.approval_status == Discussion.APPROVAL_APPROVED
        approved_reply_counts = {}
        if was_counted:
            approved_reply_counts = DiscussionService._approved_reply_counts_by_author(discussion)

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

            if was_counted:
                if discussion.user:
                    User.objects.filter(id=discussion.user_id).update(discussion_count=F('discussion_count') - 1)
                for user_id, total in approved_reply_counts.items():
                    User.objects.filter(id=user_id).update(comment_count=F("comment_count") - total)

            if previous_status != Discussion.APPROVAL_REJECTED:
                from apps.notifications.services import NotificationService
                NotificationService.notify_discussion_rejected(discussion, admin_user, note=note)
            TagService.refresh_discussion_tag_stats(discussion.id)
            DiscussionService._create_system_event_post(
                discussion=discussion,
                actor=admin_user,
                post_type=DISCUSSION_REJECTED_POST_TYPE,
                content=(
                    f"previous_status: {previous_status}\n"
                    f"note: {note}"
                ),
            )

        discussion.refresh_from_db()
        return discussion

    @staticmethod
    def _approved_reply_counts_by_author(discussion: Discussion) -> dict:
        approved_replies = (
            Post.objects.filter(
                discussion=discussion,
                type__in=USER_COUNTED_POST_TYPES,
                approval_status=Post.APPROVAL_APPROVED,
                hidden_at__isnull=True,
                number__gt=1,
            )
            .exclude(user_id__isnull=True)
            .values("user_id")
            .annotate(total=Count("id"))
        )
        return {row["user_id"]: row["total"] for row in approved_replies}

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
            counted_discussion = (
                discussion.approval_status == Discussion.APPROVAL_APPROVED
                and discussion.hidden_at is None
            )
            approved_reply_counts = {}
            if counted_discussion:
                approved_replies = (
                    Post.objects.filter(
                        discussion=discussion,
                        type__in=USER_COUNTED_POST_TYPES,
                        approval_status=Post.APPROVAL_APPROVED,
                        hidden_at__isnull=True,
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
                TagService.dispatch_refresh_tag_stats(tag_ids)

            # 更新作者讨论数
            if counted_discussion and discussion.user:
                discussion.user.discussion_count = F('discussion_count') - 1
                discussion.user.save(update_fields=['discussion_count'])

            # 更新回复作者评论数
            for user_id, total in approved_reply_counts.items():
                User.objects.filter(id=user_id).update(comment_count=F("comment_count") - total)

        return True

    @staticmethod
    def set_locked_state(discussion: Discussion, actor: User, is_locked: bool) -> Discussion:
        if not actor.is_staff:
            raise PermissionDenied("没有权限锁定/解锁讨论")

        if discussion.is_locked == is_locked:
            return discussion

        discussion.is_locked = is_locked
        discussion.save(update_fields=["is_locked"])
        DiscussionService._create_system_event_post(
            discussion=discussion,
            actor=actor,
            post_type=DISCUSSION_LOCKED_POST_TYPE,
            content="locked" if is_locked else "unlocked",
        )
        return discussion

    @staticmethod
    def set_sticky_state(discussion: Discussion, actor: User, is_sticky: bool) -> Discussion:
        if not actor.is_staff:
            raise PermissionDenied("没有权限置顶/取消置顶讨论")

        if discussion.is_sticky == is_sticky:
            return discussion

        discussion.is_sticky = is_sticky
        discussion.save(update_fields=["is_sticky"])
        DiscussionService._create_system_event_post(
            discussion=discussion,
            actor=actor,
            post_type=DISCUSSION_STICKY_POST_TYPE,
            content="sticky" if is_sticky else "unsticky",
        )
        return discussion

    @staticmethod
    def _create_system_event_post(
        discussion: Discussion,
        actor: User,
        post_type: str,
        content: str,
    ) -> Post:
        from apps.posts.services import PostService

        locked_discussion = PostService._lock_discussion_for_post_number(discussion.id)
        event_post = PostService._create_post_with_sequential_number(
            discussion=locked_discussion,
            user=actor,
            type=post_type,
            content=content,
            content_html="",
            approval_status=Post.APPROVAL_APPROVED,
            approved_at=timezone.now(),
            approved_by=actor,
        )
        locked_discussion.last_post_id = event_post.id
        locked_discussion.last_post_number = event_post.number
        locked_discussion.last_posted_at = event_post.created_at
        locked_discussion.last_posted_user = actor
        locked_discussion.save(update_fields=[
            "last_post_id",
            "last_post_number",
            "last_posted_at",
            "last_posted_user",
        ])
        return event_post

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
