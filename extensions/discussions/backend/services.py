"""讨论系统业务逻辑层。"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone

from apps.core.extensions.forum import sqlite_write_retry
from apps.core.extensions.platform import get_forum_event_bus
from apps.core.extensions.platform import evaluate_extension_policy
from apps.core.extensions.runtime import (
    apply_runtime_discussion_search,
    evaluate_runtime_model_policy,
    get_runtime_resource_registry,
)
from apps.core.extensions.forum import get_forum_registry
from extensions.discussions.backend import discussion_tracking, service_lifecycle
from extensions.discussions.backend.models import Discussion, DiscussionUser
from apps.core.extensions.platform import PaginationService
from apps.core.extensions.runtime import (
    has_runtime_forum_permission,
)


def _get_forum_registry():
    return get_forum_registry()


def _get_default_post_type() -> str:
    return _get_forum_registry().get_default_post_type_code()


def _get_discussion_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_discussion_counted_post_type_codes()


def _get_user_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_user_counted_post_type_codes()


class DiscussionService:
    """讨论服务"""

    VIEW_COUNT_THROTTLE_SECONDS = 60 * 15
    VIEW_COUNT_FLUSH_DELAY_SECONDS = 60
    VIEW_COUNT_CACHE_TIMEOUT = 60 * 60 * 24
    VIEW_COUNT_PENDING_IDS_CACHE_KEY = "discussion.view_count.pending.ids"

    @staticmethod
    def normalize_discussion_sort(sort: str | None) -> str:
        return _get_forum_registry().get_discussion_sort(sort or "").code

    @staticmethod
    def get_discussion_sort_catalog():
        return get_runtime_resource_registry().apply_sort_definitions(
            "discussion",
            _get_forum_registry().get_discussion_sorts(),
        )

    @staticmethod
    def normalize_discussion_list_filter(filter_code: str | None) -> str:
        return _get_forum_registry().get_discussion_list_filter(filter_code or "").code

    @staticmethod
    def get_discussion_list_filter_catalog():
        return _get_forum_registry().get_discussion_list_filters()

    @staticmethod
    def _viewer_cache_identity(user: Optional[User]) -> str:
        return discussion_tracking.viewer_cache_identity(user)

    @staticmethod
    def _view_count_cache_key(discussion_id: int, user: Optional[User]) -> str:
        return discussion_tracking.view_count_cache_key(discussion_id, user)

    @staticmethod
    def _view_count_pending_cache_key(discussion_id: int) -> str:
        return discussion_tracking.view_count_pending_cache_key(discussion_id)

    @staticmethod
    def _view_count_flush_lock_cache_key(discussion_id: int) -> str:
        return discussion_tracking.view_count_flush_lock_cache_key(discussion_id)

    @staticmethod
    def record_view(discussion: Discussion, user: Optional[User] = None) -> bool:
        return discussion_tracking.record_view(
            discussion,
            user=user,
            throttle_seconds=DiscussionService.VIEW_COUNT_THROTTLE_SECONDS,
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            pending_ids_cache_key=DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
            flush_delay_seconds=DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS,
        )

    @staticmethod
    def _increment_pending_view_count(discussion_id: int) -> int:
        return discussion_tracking.increment_pending_view_count(
            discussion_id,
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            pending_ids_cache_key=DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
        )

    @staticmethod
    def _remember_pending_view_discussion(discussion_id: int) -> None:
        discussion_tracking.remember_pending_view_discussion(
            discussion_id,
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            pending_ids_cache_key=DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
        )

    @staticmethod
    def dispatch_view_count_flush(discussion_id: int, pending_count: int = 0):
        return discussion_tracking.dispatch_view_count_flush(
            discussion_id,
            pending_count=pending_count,
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            flush_delay_seconds=DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS,
        )

    @staticmethod
    def flush_pending_view_count(discussion_id: int) -> int:
        return discussion_tracking.flush_pending_view_count(
            discussion_id,
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            flush_delay_seconds=DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS,
        )

    @staticmethod
    def flush_all_pending_view_counts() -> int:
        return discussion_tracking.flush_all_pending_view_counts(
            cache_timeout=DiscussionService.VIEW_COUNT_CACHE_TIMEOUT,
            pending_ids_cache_key=DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY,
            flush_delay_seconds=DiscussionService.VIEW_COUNT_FLUSH_DELAY_SECONDS,
        )

    @staticmethod
    def _can_view_discussion(discussion: Discussion, user: Optional[User]) -> bool:
        return discussion_tracking.can_view_discussion(discussion, user)

    @staticmethod
    def apply_visibility_filters(queryset, user: Optional[User] = None):
        return discussion_tracking.apply_visibility_filters(queryset, user)

    @staticmethod
    @sqlite_write_retry()
    def create_discussion(
        title: str,
        content: str,
        user: User,
        extension_payload: Optional[dict[str, Any]] = None,
    ) -> Discussion:
        """
        创建讨论

        Args:
            title: 讨论标题
            content: 第一条帖子内容
            user: 创建者

        Returns:
            Discussion: 创建的讨论对象
        """
        return service_lifecycle.create_discussion(
            title,
            content,
            user,
            extension_payload=extension_payload,
            default_post_type=_get_default_post_type(),
            render_markdown_cb=DiscussionService._render_markdown,
        )

    @staticmethod
    def get_discussion_list(
        q: Optional[str] = None,
        author: Optional[str] = None,
        list_filter: str = 'all',
        sort: str = 'latest',
        page: int = 1,
        limit: int = 20,
        user: Optional[User] = None,
        preload=None,
        query_params: Optional[dict] = None,
    ) -> Tuple[List[Discussion], int]:
        """
        获取讨论列表

        Args:
            q: 搜索关键词
            author: 作者用户名
            sort: 排序方式
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Discussion], int]: (讨论列表, 总数)
        """
        page, limit = PaginationService.normalize(page, limit)
        queryset = Discussion.objects.all()
        if preload is not None:
            queryset = preload(queryset)

        queryset = DiscussionService.apply_visibility_filters(queryset, user)

        # 搜索
        if q:
            queryset = apply_runtime_discussion_search(queryset, q, user=user)

        # 按作者过滤
        if author:
            queryset = queryset.filter(user__username=author)

        normalized_query_params = dict(query_params or {})
        query_context = {
            "user": user,
            "query": q,
            "author": author,
            "params": normalized_query_params,
        }
        for query_definition in _get_forum_registry().get_discussion_list_queries():
            queryset = query_definition.applier(
                queryset,
                {
                    **query_context,
                    "key": query_definition.key,
                },
            )

        filter_definition = _get_forum_registry().get_discussion_list_filter(list_filter)
        queryset = filter_definition.applier(
            queryset,
            {
                "user": user,
                "filter": filter_definition.code,
                "query": q,
                "author": author,
                "params": normalized_query_params,
            },
        )

        # 排序
        sort_definition = _get_forum_registry().get_discussion_sort(sort)
        queryset = sort_definition.applier(
            queryset,
            {
                "user": user,
                "sort": sort_definition.code,
                "query": q,
                "author": author,
                "filter": filter_definition.code,
                "params": normalized_query_params,
            },
        )
        queryset = get_runtime_resource_registry().apply_named_sort(
            "discussion",
            queryset,
            sort_definition.code,
            {
                "user": user,
                "sort": sort_definition.code,
                "query": q,
                "author": author,
                "filter": filter_definition.code,
                "params": normalized_query_params,
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
    def get_discussion_by_id(
        discussion_id: int,
        user: Optional[User] = None,
        preload=None,
    ) -> Optional[Discussion]:
        """
        获取讨论详情

        Args:
            discussion_id: 讨论ID
            user: 当前用户（用于更新阅读状态）

        Returns:
            Optional[Discussion]: 讨论对象
        """
        try:
            queryset = Discussion.objects.all()
            if preload is not None:
                queryset = preload(queryset)
            discussion = queryset.get(id=discussion_id)

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
        discussion_tracking.attach_user_read_state(discussions, user)

    @staticmethod
    def mark_all_as_read(user: User):
        return discussion_tracking.mark_all_as_read(user)

    @staticmethod
    def update_read_state(discussion_id: int, user: User, last_read_post_number: int) -> DiscussionUser:
        return discussion_tracking.update_read_state(discussion_id, user, last_read_post_number)

    @staticmethod
    def update_discussion(
        discussion_id: int,
        user: User,
        title: Optional[str] = None,
        content: Optional[str] = None,
        extension_payload: Optional[dict[str, Any]] = None,
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
        return service_lifecycle.update_discussion(
            discussion_id,
            user,
            title=title,
            content=content,
            extension_payload=extension_payload,
            is_locked=is_locked,
            is_sticky=is_sticky,
            is_hidden=is_hidden,
            can_edit_discussion_cb=DiscussionService.can_edit_discussion,
            render_markdown_cb=DiscussionService._render_markdown,
            set_locked_state_cb=DiscussionService.set_locked_state,
            set_sticky_state_cb=DiscussionService.set_sticky_state,
            set_hidden_state_cb=DiscussionService.set_hidden_state,
        )

    @staticmethod
    def set_hidden_state(discussion: Discussion, user: User, is_hidden: bool) -> Discussion:
        return service_lifecycle.set_hidden_state(
            discussion,
            user,
            is_hidden,
            approved_reply_counts_by_author_cb=DiscussionService._approved_reply_counts_by_author,
        )

    @staticmethod
    def approve_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        return service_lifecycle.approve_discussion(
            discussion,
            admin_user,
            note=note,
            approved_reply_counts_by_author_cb=DiscussionService._approved_reply_counts_by_author,
        )

    @staticmethod
    def reject_discussion(discussion: Discussion, admin_user: User, note: str = "") -> Discussion:
        return service_lifecycle.reject_discussion(
            discussion,
            admin_user,
            note=note,
            approved_reply_counts_by_author_cb=DiscussionService._approved_reply_counts_by_author,
        )

    @staticmethod
    def _approved_reply_counts_by_author(discussion: Discussion) -> dict:
        return service_lifecycle.approved_reply_counts_by_author(
            discussion,
            user_counted_post_types=_get_user_counted_post_types(),
        )

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
        return service_lifecycle.delete_discussion(
            discussion_id,
            user,
            can_delete_discussion_cb=DiscussionService.can_delete_discussion,
            approved_reply_counts_by_author_cb=DiscussionService._approved_reply_counts_by_author,
        )

    @staticmethod
    def set_locked_state(discussion: Discussion, actor: User, is_locked: bool) -> Discussion:
        return service_lifecycle.set_locked_state(discussion, actor, is_locked)

    @staticmethod
    def set_sticky_state(discussion: Discussion, actor: User, is_sticky: bool) -> Discussion:
        return service_lifecycle.set_sticky_state(discussion, actor, is_sticky)

    @staticmethod
    def can_edit_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以编辑讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if has_runtime_forum_permission(user, "discussion.edit"):
            allowed = True
        elif discussion.user_id == user.id:
            allowed = has_runtime_forum_permission(user, "discussion.editOwn")
        return bool(evaluate_extension_policy(
            "discussion.edit",
            default=allowed,
            user=user,
            discussion=discussion,
        ))

    @staticmethod
    def can_delete_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以删除讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if has_runtime_forum_permission(user, "discussion.delete"):
            allowed = True
        elif discussion.user_id == user.id:
            allowed = has_runtime_forum_permission(user, "discussion.deleteOwn")
        return bool(evaluate_extension_policy(
            "discussion.delete",
            default=allowed,
            user=user,
            discussion=discussion,
        ))

    @staticmethod
    def can_reply_discussion(discussion: Discussion, user: User) -> bool:
        """检查用户是否可以回复讨论"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        if not has_runtime_forum_permission(user, "discussion.reply"):
            return False
        if discussion.approval_status != Discussion.APPROVAL_APPROVED and not user.is_staff:
            return False
        if discussion.is_locked and not user.is_staff:
            return False
        if evaluate_runtime_model_policy(
            "reply",
            user=user,
            model=discussion,
            default=True,
            discussion=discussion,
        ) is False:
            return False
        return bool(evaluate_extension_policy(
            "discussion.reply",
            default=True,
            user=user,
            discussion=discussion,
        ))

    @staticmethod
    def _render_markdown(content: str) -> str:
        """
        渲染Markdown为HTML

        Args:
            content: Markdown内容

        Returns:
            str: HTML内容
        """
        from apps.core.extensions.platform import MarkdownService
        return MarkdownService.render(content, sanitize=True)
