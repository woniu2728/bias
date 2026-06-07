from __future__ import annotations

from django.db.models import Subquery
from django.db.models import Prefetch

from apps.core.visibility import apply_related_model_visibility_subquery
from apps.posts.models import Post
from apps.users.services import UserService
from extensions.flags.backend.models import PostFlag


def post_flag_preload_resolver(context: dict):
    user = context.get("user")
    prefetches = []
    if user and user.is_authenticated:
        prefetches.append(
            Prefetch(
                "flags",
                queryset=PostFlag.objects.filter(
                    user=user,
                    status=PostFlag.STATUS_OPEN,
                ).select_related("post", "post__discussion", "post__user", "user", "resolved_by"),
                to_attr="viewer_open_flags_cache",
            )
        )
    if resolve_forum_can_view_flags(None, context):
        prefetches.append(
            Prefetch(
                "flags",
                queryset=PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).select_related(
                    "post",
                    "post__discussion",
                    "post__user",
                    "user",
                    "resolved_by",
                ),
                to_attr="open_flags_cache",
            )
        )
    return (), tuple(prefetches)


def resolve_forum_can_view_flags(forum, context: dict) -> bool:
    user = context.get("user")
    return bool(
        user
        and user.is_authenticated
        and UserService.has_forum_permission(user, "admin.flag.view")
    )


def resolve_forum_flag_count(forum, context: dict) -> int:
    user = context.get("user")
    queryset = scope_flag_visibility(PostFlag.objects.filter(status=PostFlag.STATUS_OPEN), {"user": user})
    return queryset.values("post_id").distinct().count()


def resolve_admin_open_flags(stats, context: dict) -> int:
    return PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).count()


def resolve_post_viewer_has_open_flag(post, context: dict) -> bool:
    cached = getattr(post, "viewer_open_flags_cache", None)
    if cached is not None:
        return bool(cached)
    user = context.get("user")
    if not user or not user.is_authenticated:
        return False
    return PostFlag.objects.filter(
        post_id=post.id,
        user=user,
        status=PostFlag.STATUS_OPEN,
    ).exists()


def resolve_post_can_flag(post, context: dict) -> bool:
    user = context.get("user")
    if not user or not user.is_authenticated:
        return False
    if getattr(post, "hidden_at", None) is not None:
        return False
    if post.user_id != user.id:
        return True

    from apps.core.extension_settings_service import get_extension_settings

    settings = get_extension_settings("flags")
    return bool(settings.get("can_flag_own", False))


def resolve_post_open_flag_count(post, context: dict) -> int:
    cached = getattr(post, "open_flags_cache", None)
    if cached is not None:
        return len(cached)
    if not resolve_forum_can_view_flags(None, context):
        return 0
    return PostFlag.objects.filter(post_id=post.id, status=PostFlag.STATUS_OPEN).count()


def resolve_post_flag_objects(post, context: dict):
    cached = getattr(post, "open_flags_cache", None)
    if cached is not None:
        return cached
    return PostFlag.objects.filter(
        post_id=post.id,
        status=PostFlag.STATUS_OPEN,
    ).select_related("post", "post__discussion", "post__user", "user", "resolved_by")


def resolve_post_open_flags(post, context: dict) -> list[dict]:
    open_flags = resolve_post_flag_objects(post, context)
    return [
        {
            "id": flag.id,
            "reason": flag.reason,
            "message": flag.message,
            "created_at": flag.created_at,
            "user": {
                "id": flag.user.id,
                "username": flag.user.username,
                "display_name": flag.user.display_name,
            } if flag.user else None,
        }
        for flag in open_flags
    ]


def resolve_post_flags(post, context: dict) -> list[dict]:
    from extensions.flags.backend.handlers import serialize_flag

    return [
        serialize_flag(flag)
        for flag in resolve_post_flag_objects(post, context)
    ]


def resolve_post_flag_identifiers(post, context: dict) -> list[dict]:
    return [
        {
            "type": "flag",
            "id": str(flag.id),
        }
        for flag in resolve_post_flag_objects(post, context)
    ]


def resolve_post_can_moderate_flags(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and UserService.has_forum_permission(user, "admin.flag.view"))


def resolve_user_new_flag_count(user, context: dict) -> int:
    actor = context.get("user")
    if (
        not actor
        or not actor.is_authenticated
        or actor.id != user.id
        or not UserService.has_forum_permission(actor, "admin.flag.view")
    ):
        return 0
    queryset = scope_flag_visibility(PostFlag.objects.filter(status=PostFlag.STATUS_OPEN), {"user": actor})
    return queryset.values("post_id").distinct().count()


def scope_flag_visibility(queryset, context: dict):
    user = context.get("user")
    if (
        not user
        or not user.is_authenticated
        or not UserService.has_forum_permission(user, "admin.flag.view")
    ):
        return queryset.none()
    visible_post_ids = apply_related_model_visibility_subquery(
        Post,
        user=user,
        ability="view",
        context={"skip_view_forum_gate": True},
    )
    return queryset.filter(post_id__in=Subquery(visible_post_ids))
