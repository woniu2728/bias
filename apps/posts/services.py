"""
帖子系统业务逻辑层
"""
from dataclasses import dataclass
from math import ceil
from typing import Optional, List, Tuple
from django.db import IntegrityError
from django.db.models import Q, Count, Exists, OuterRef, Prefetch
from apps.core.db import sqlite_write_retry
from apps.core.domain_events import get_forum_event_bus
from apps.core.forum_registry import get_forum_registry
from apps.posts.models import Post, PostLike, PostFlag
from apps.discussions.models import Discussion
from apps.tags.services import TagService
from apps.users.models import User
from apps.users.services import UserService
from apps.core.visibility import build_discussion_visibility_q, build_post_visibility_q
from apps.posts import service_lifecycle, service_moderation


FORUM_REGISTRY = get_forum_registry()
DEFAULT_POST_TYPE = FORUM_REGISTRY.get_default_post_type_code()
STREAM_POST_TYPES = FORUM_REGISTRY.get_stream_post_type_codes()
DISCUSSION_COUNTED_POST_TYPES = FORUM_REGISTRY.get_discussion_counted_post_type_codes()
USER_COUNTED_POST_TYPES = FORUM_REGISTRY.get_user_counted_post_type_codes()


@dataclass
class PostStreamWindow:
    posts: List[Post]
    total: int
    page: int
    limit: int
    current_start: int
    current_end: int
    has_previous: bool
    has_more: bool


class PostService:
    """帖子服务"""

    POST_NUMBER_CONFLICT_RETRY_ATTEMPTS = 3

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
        return service_lifecycle.create_post(
            discussion_id,
            content,
            user,
            reply_to_post_id=reply_to_post_id,
            default_post_type=DEFAULT_POST_TYPE,
            can_reply_in_discussion=PostService._validate_replyable_discussion,
            render_markdown_cb=PostService._render_markdown,
            process_mentions_cb=PostService._process_mentions,
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
            stream_post_types=STREAM_POST_TYPES,
            annotate_flag_state_cb=PostService.annotate_flag_state,
            apply_visibility_filters_cb=PostService.apply_visibility_filters,
        )

    @staticmethod
    def _build_visible_post_queryset(
        discussion_id: int,
        user: Optional[User] = None,
        preload=None,
    ):
        queryset = Post.objects.filter(
            discussion_id=discussion_id,
            type__in=STREAM_POST_TYPES,
        ).annotate(
            like_count=Count('likes', distinct=True)
        )
        if preload is not None:
            queryset = preload(queryset)
        queryset = PostService.annotate_flag_state(queryset, user)
        queryset = PostService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_posts_for_user(queryset, user)
        return queryset.order_by('number')

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
        queryset = PostService._build_visible_post_queryset(
            discussion_id=discussion_id,
            user=user,
            preload=preload,
        )
        total = queryset.count()

        if total <= 0:
            return PostStreamWindow(
                posts=[],
                total=0,
                page=1,
                limit=limit,
                current_start=0,
                current_end=0,
                has_previous=False,
                has_more=False,
            )

        mode_count = sum(1 for value in (near, before, after) if value is not None)
        if mode_count > 1:
            raise ValueError("near、before、after 只能传一个")

        if near is not None:
            posts = list(queryset.filter(number__gte=near).order_by('number')[:limit])
            if not posts:
                posts = list(queryset.order_by('-number')[:limit])
                posts.reverse()
            current_start = posts[0].number if posts else 0
            current_end = posts[-1].number if posts else 0
        elif before is not None:
            posts = list(queryset.filter(number__lt=before).order_by('-number')[:limit])
            posts.reverse()
            current_start = posts[0].number if posts else 0
            current_end = posts[-1].number if posts else 0
        elif after is not None:
            posts = list(queryset.filter(number__gt=after).order_by('number')[:limit])
            current_start = posts[0].number if posts else 0
            current_end = posts[-1].number if posts else 0
        else:
            offset = (page - 1) * limit
            posts = list(queryset[offset:offset + limit])
            current_start = posts[0].number if posts else 0
            current_end = posts[-1].number if posts else 0

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

        has_previous = queryset.filter(number__lt=current_start).exists() if current_start else False
        has_more = queryset.filter(number__gt=current_end).exists() if current_end else False
        resolved_page = page
        if current_end:
            resolved_position = queryset.filter(number__lte=current_end).count()
            resolved_page = max(1, ceil(resolved_position / limit))

        return PostStreamWindow(
            posts=posts,
            total=total,
            page=resolved_page,
            limit=limit,
            current_start=current_start,
            current_end=current_end,
            has_previous=has_previous,
            has_more=has_more,
        )

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
            type__in=STREAM_POST_TYPES,
        )

        queryset = PostService.apply_visibility_filters(queryset, user)
        queryset = TagService.filter_posts_for_user(queryset, user)

        position = queryset.count()
        if position <= 0:
            return 1

        return max(1, ceil(position / limit))

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
            annotate_flag_state_cb=PostService.annotate_flag_state,
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
            process_mentions_cb=PostService._process_mentions,
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
            discussion_counted_post_types=DISCUSSION_COUNTED_POST_TYPES,
            user_counted_post_types=USER_COUNTED_POST_TYPES,
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def set_hidden_state(post: Post, admin_user: User, is_hidden: bool) -> Post:
        return service_lifecycle.set_hidden_state(
            post,
            admin_user,
            is_hidden,
            discussion_counted_post_types=DISCUSSION_COUNTED_POST_TYPES,
            user_counted_post_types=USER_COUNTED_POST_TYPES,
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
            discussion_counted_post_types=DISCUSSION_COUNTED_POST_TYPES,
        )

    @staticmethod
    def like_post(post_id: int, user: User) -> bool:
        return service_moderation.like_post(
            post_id,
            user,
            can_view_post=PostService._can_view_post,
        )

    @staticmethod
    def report_post(post_id: int, user: User, reason: str, message: str = "") -> PostFlag:
        return service_moderation.report_post(
            post_id,
            user,
            reason,
            message,
            can_view_post=PostService._can_view_post,
        )

    @staticmethod
    def get_flag_list(status: Optional[str] = None, page: int = 1, limit: int = 20):
        return service_moderation.get_flag_list(status=status, page=page, limit=limit)

    @staticmethod
    def resolve_flag(flag_id: int, admin_user: User, status: str, resolution_note: str = "") -> PostFlag:
        return service_moderation.resolve_flag(
            flag_id,
            admin_user,
            status,
            resolution_note=resolution_note,
        )

    @staticmethod
    def resolve_post_flags(post_id: int, admin_user: User, status: str, resolution_note: str = "") -> int:
        return service_moderation.resolve_post_flags(
            post_id,
            admin_user,
            status,
            resolution_note=resolution_note,
        )

    @staticmethod
    def approve_post(post: Post, admin_user: User, note: str = "") -> Post:
        return service_moderation.approve_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=DISCUSSION_COUNTED_POST_TYPES,
            user_counted_post_types=USER_COUNTED_POST_TYPES,
            process_mentions_cb=PostService._process_mentions,
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def reject_post(post: Post, admin_user: User, note: str = "") -> Post:
        return service_moderation.reject_post(
            post,
            admin_user,
            note=note,
            discussion_counted_post_types=DISCUSSION_COUNTED_POST_TYPES,
            user_counted_post_types=USER_COUNTED_POST_TYPES,
            refresh_discussion_approved_stats_cb=PostService._refresh_discussion_approved_stats,
        )

    @staticmethod
    def unlike_post(post_id: int, user: User) -> bool:
        return service_moderation.unlike_post(
            post_id,
            user,
            can_view_post=PostService._can_view_post,
        )

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
        from apps.core.mentions import extract_mentioned_usernames

        return service_lifecycle.process_mentions(
            post,
            content,
            extract_mentions_cb=extract_mentioned_usernames,
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
