from __future__ import annotations

from django.db.models import Subquery

from apps.core.visibility import apply_related_model_visibility_subquery
from apps.posts.models import Post, PostFlag
from apps.users.services import UserService


def _serialize_flag_base(flag, context: dict) -> dict:
    from extensions.flags.backend.handlers import serialize_flag

    return serialize_flag(flag)


def _resolve_forum_can_view_flags(forum, context: dict) -> bool:
    user = context.get("user")
    return bool(
        user
        and user.is_authenticated
        and UserService.has_forum_permission(user, "admin.flag.view")
    )


def _resolve_forum_flag_count(forum, context: dict) -> int:
    user = context.get("user")
    queryset = scope_flag_visibility(PostFlag.objects.filter(status=PostFlag.STATUS_OPEN), {"user": user})
    return queryset.values("post_id").distinct().count()


def _resolve_post_viewer_has_open_flag(post, context: dict) -> bool:
    return bool(getattr(post, "viewer_has_open_flag", False))


def _resolve_post_can_flag(post, context: dict) -> bool:
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


def _resolve_post_open_flag_count(post, context: dict) -> int:
    return int(getattr(post, "open_flag_count", 0) or 0)


def _resolve_post_flag_objects(post, context: dict):
    cached = getattr(post, "open_flags_cache", None)
    if cached is not None:
        return cached
    return PostFlag.objects.filter(
        post_id=post.id,
        status=PostFlag.STATUS_OPEN,
    ).select_related("post", "post__discussion", "post__user", "user", "resolved_by")


def _resolve_post_open_flags(post, context: dict) -> list[dict]:
    open_flags = _resolve_post_flag_objects(post, context)
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


def _resolve_post_flags(post, context: dict) -> list[dict]:
    from extensions.flags.backend.handlers import serialize_flag

    return [
        serialize_flag(flag)
        for flag in _resolve_post_flag_objects(post, context)
    ]


def _resolve_post_flag_identifiers(post, context: dict) -> list[dict]:
    return [
        {
            "type": "flag",
            "id": str(flag.id),
        }
        for flag in _resolve_post_flag_objects(post, context)
    ]


def _resolve_post_can_moderate_flags(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and UserService.has_forum_permission(user, "admin.flag.view"))


def _resolve_user_new_flag_count(user, context: dict) -> int:
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
