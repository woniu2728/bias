from typing import Optional

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.runtime_access import apply_runtime_model_visibility
from apps.core.forum_events import PostFlagCreatedEvent, PostFlagsDeletedEvent, PostFlagsResolvedEvent
from apps.posts import post_query_service
from apps.posts.models import Post
from apps.users.models import User
from apps.users.services import UserService
from extensions.flags.backend.models import PostFlag


def report_post(post_id: int, user: User, reason: str, message: str = "") -> PostFlag:
    UserService.ensure_not_suspended(user, "举报帖子")
    post = Post.objects.select_related("user", "discussion").get(id=post_id)
    if not post_query_service.can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")

    if not user or not user.is_authenticated:
        raise PermissionDenied("请先登录")
    if post.user_id == user.id and not _can_flag_own_post():
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
        flag = PostFlag.objects.create(
            post=post,
            user=user,
            reason=reason,
            message=message,
        )
        dispatch_forum_event_after_commit(
            PostFlagCreatedEvent(
                flag_id=flag.id,
                post_id=post.id,
                discussion_id=post.discussion_id,
                actor_user_id=user.id,
            )
        )
        return flag


def get_flag_list(status: Optional[str] = None, page: int = 1, limit: int = 20, *, user: User | None = None):
    queryset = PostFlag.objects.select_related(
        "post",
        "post__discussion",
        "post__user",
        "user",
        "resolved_by",
    )

    if status:
        queryset = queryset.filter(status=status)

    if user is not None:
        queryset = apply_runtime_model_visibility(
            PostFlag,
            queryset,
            {"user": user, "ability": "view"},
        )

    total = queryset.count()
    offset = (page - 1) * limit
    return list(queryset[offset:offset + limit]), total


def resolve_flag(flag_id: int, admin_user: User, status: str, resolution_note: str = "") -> PostFlag:
    if status not in {PostFlag.STATUS_RESOLVED, PostFlag.STATUS_IGNORED}:
        raise ValueError("无效的处理状态")

    flag = PostFlag.objects.select_related("post", "post__discussion", "user").get(id=flag_id)
    flag.status = status
    flag.resolution_note = resolution_note
    flag.resolved_by = admin_user
    flag.resolved_at = timezone.now()
    flag.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])
    dispatch_forum_event_after_commit(
        PostFlagsResolvedEvent(
            flag_ids=(flag.id,),
            post_id=flag.post_id,
            discussion_id=flag.post.discussion_id,
            actor_user_id=admin_user.id,
            status=status,
        )
    )
    return flag


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
    first_flag = open_flags[0]
    dispatch_forum_event_after_commit(
        PostFlagsResolvedEvent(
            flag_ids=tuple(flag.id for flag in open_flags),
            post_id=post_id,
            discussion_id=first_flag.post.discussion_id,
            actor_user_id=admin_user.id,
            status=status,
        )
    )
    return len(open_flags)


def delete_post_flags(post_id: int, user: User) -> int:
    post = Post.objects.select_related("discussion").get(id=post_id)
    if not post_query_service.can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")
    if not UserService.has_forum_permission(user, "admin.flag.view"):
        raise PermissionDenied("无权查看举报")

    with transaction.atomic():
        flag_ids = tuple(PostFlag.objects.filter(post_id=post.id).values_list("id", flat=True))
        if not flag_ids:
            return 0
        PostFlag.objects.filter(id__in=flag_ids).delete()
        dispatch_forum_event_after_commit(
            PostFlagsDeletedEvent(
                flag_ids=flag_ids,
                post_id=post.id,
                discussion_id=post.discussion_id,
                actor_user_id=user.id,
            )
        )
        return len(flag_ids)


def _can_flag_own_post() -> bool:
    from apps.core.extension_settings_service import get_extension_settings

    settings = get_extension_settings("flags")
    return bool(settings.get("can_flag_own", False))
