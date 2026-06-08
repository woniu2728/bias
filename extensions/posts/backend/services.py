"""帖子系统业务逻辑层。"""
from typing import List, Optional, Tuple

from django.db import IntegrityError

from apps.core.db import sqlite_write_retry
from apps.core.domain_events import get_forum_event_bus
from apps.core.extensions.policy_runtime_service import evaluate_extension_policy
from apps.core.forum_registry import get_forum_registry
from extensions.discussions.backend.models import Discussion
from extensions.posts.backend import post_query_service, service_lifecycle, service_moderation
from extensions.posts.backend.models import Post
from extensions.users.backend.models import User
from apps.users.services import UserService


def _get_forum_registry():
    return get_forum_registry()


def _get_default_post_type() -> str:
    return _get_forum_registry().get_default_post_type_code()


def _get_stream_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_stream_post_type_codes()


def _get_discussion_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_discussion_counted_post_type_codes()


def _get_user_counted_post_types() -> tuple[str, ...]:
    return _get_forum_registry().get_user_counted_post_type_codes()


PostStreamWindow = post_query_service.PostStreamWindow


class PostService:
    """帖子服务"""

    POST_NUMBER_CONFLICT_RETRY_ATTEMPTS = 3

    @staticmethod
    def _can_view_post(post: Post, user: Optional[User]) -> bool:
        return post_query_service.can_view_post(post, user)

    @staticmethod
    def apply_visibility_filters(queryset, user: Optional[User] = None):
        return post_query_service.apply_visibility_filters(queryset, user)

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
        return service_lifecycle.create_post(
            discussion_id,
            content,
            user,
            reply_to_post_id=reply_to_post_id,
            default_post_type=_get_default_post_type(),
            can_reply_in_discussion=PostService._validate_replyable_discussion,
            render_markdown_cb=PostService._render_markdown,
            lock_discussion_for_post_number_cb=PostService._lock_discussion_for_post_number,
            create_post_with_sequential_number_cb=PostService._create_post_with_sequential_number,
        )

    @staticmethod
    def get_post_list(
        discussion_id: int,
        page: int = 1,
        limit: int = 20,
        user: Optional[User] = None,
        preload=None,
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
        return service_lifecycle.get_post_list(
            discussion_id,
            page=page,
            limit=limit,
            user=user,
            preload=preload,
            stream_post_types=_get_stream_post_types(),
            apply_visibility_filters_cb=PostService.apply_visibility_filters,
        )

    @staticmethod
    def _build_visible_post_queryset(
        discussion_id: int,
        user: Optional[User] = None,
        preload=None,
    ):
        return post_query_service.build_visible_post_queryset(
            discussion_id,
            stream_post_types=_get_stream_post_types(),
            user=user,
            preload=preload,
        )

    @staticmethod
    def get_post_window(
        discussion_id: int,
        *,
        limit: int = 20,
        page: int = 1,
        near: Optional[int] = None,
        before: Optional[int] = None,
        after: Optional[int] = None,
        user: Optional[User] = None,
        preload=None,
    ) -> PostStreamWindow:
        return post_query_service.get_post_window(
            discussion_id,
            stream_post_types=_get_stream_post_types(),
            limit=limit,
            page=page,
            near=near,
            before=before,
            after=after,
            user=user,
            preload=preload,
        )

    @staticmethod
    def get_page_for_near_post(
        discussion_id: int,
        near: int,
        limit: int = 20,
        user: Optional[User] = None,
    ) -> int:
        return post_query_service.get_page_for_near_post(
            discussion_id,
            near,
            stream_post_types=_get_stream_post_types(),
            limit=limit,
            user=user,
        )

    @staticmethod
    def get_post_by_id(
        post_id: int,
        user: Optional[User] = None,
        preload=None,
    ) -> Optional[Post]:
        """
        获取帖子详情

        Args:
            post_id: 帖子ID
            user: 当前用户

        Returns:
            Optional[Post]: 帖子对象
        """
        return service_lifecycle.get_post_by_id(
            post_id,
            user=user,
            preload=preload,
            can_view_post_cb=PostService._can_view_post,
        )

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
        return service_lifecycle.update_post(
            post_id,
            user,
            content,
            can_edit_post_cb=PostService.can_edit_post,
            render_markdown_cb=PostService._render_markdown,
        )

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
        return service_lifecycle.delete_post(
            post_id,
            user,
            can_delete_post_cb=PostService.can_delete_post,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def set_hidden_state(post: Post, admin_user: User, is_hidden: bool) -> Post:
        return service_lifecycle.set_hidden_state(
            post,
            admin_user,
            is_hidden,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def _validate_replyable_discussion(
        discussion_id: int,
        user: User,
        *,
        discussion: Optional[Discussion] = None,
    ) -> Discussion:
        return service_lifecycle.validate_replyable_discussion(
            discussion_id,
            user,
            discussion=discussion,
        )

    @staticmethod
    def _lock_discussion_for_post_number(discussion_id: int) -> Discussion:
        return Discussion.objects.select_for_update().get(id=discussion_id)

    @staticmethod
    def _allocate_next_post_number(discussion: Discussion) -> int:
        last_post = (
            Post.objects.filter(discussion=discussion)
            .order_by("-number")
            .only("number")
            .first()
        )
        return (last_post.number + 1) if last_post else 1

    @staticmethod
    def _is_post_number_conflict(exc: IntegrityError) -> bool:
        return service_lifecycle.is_post_number_conflict(exc)

    @staticmethod
    def _create_post_with_sequential_number(**post_kwargs) -> Post:
        return service_lifecycle.create_post_with_sequential_number(
            attempts=PostService.POST_NUMBER_CONFLICT_RETRY_ATTEMPTS,
            allocate_next_post_number_cb=PostService._allocate_next_post_number,
            **post_kwargs,
        )

    @staticmethod
    def _refresh_discussion_approved_stats(discussion: Discussion) -> Discussion:
        return service_lifecycle.refresh_discussion_approved_stats(
            discussion,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
        )

    @staticmethod
    def approve_post(post: Post, admin_user: User, note: str = "") -> Post:
        return service_moderation.approve_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def reject_post(post: Post, admin_user: User, note: str = "") -> Post:
        return service_moderation.reject_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=_get_discussion_counted_post_types(),
            user_counted_post_types=_get_user_counted_post_types(),
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def can_edit_post(post: Post, user: User) -> bool:
        """检查用户是否可以编辑帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if UserService.has_forum_permission(user, "discussion.edit"):
            allowed = True
        elif post.user_id == user.id:
            allowed = UserService.has_forum_permission(user, "discussion.editOwn")
        return bool(evaluate_extension_policy(
            "post.edit",
            default=allowed,
            user=user,
            post=post,
        ))

    @staticmethod
    def can_delete_post(post: Post, user: User) -> bool:
        """检查用户是否可以删除帖子"""
        if not user or not user.is_authenticated:
            return False
        if user.is_suspended:
            return False
        allowed = False
        if UserService.has_forum_permission(user, "discussion.delete"):
            allowed = True
        elif post.user_id == user.id:
            allowed = UserService.has_forum_permission(user, "discussion.deleteOwn")
        return bool(evaluate_extension_policy(
            "post.delete",
            default=allowed,
            user=user,
            post=post,
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
        from apps.core.markdown_service import MarkdownService
        return MarkdownService.render(content, sanitize=True)
