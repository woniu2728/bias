from __future__ import annotations

from apps.core.resource_registry import ResourceFieldDefinition, get_resource_registry


def register_forum_flag_resource_fields() -> None:
    registry = get_resource_registry()

    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="viewer_has_open_flag",
            module_id="flags",
            resolver=_resolve_post_viewer_has_open_flag,
            description="当前用户是否已对该回复提交待处理举报。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="open_flag_count",
            module_id="flags",
            resolver=_resolve_post_open_flag_count,
            description="当前回复的待处理举报数量。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="open_flags",
            module_id="flags",
            resolver=_resolve_post_open_flags,
            description="当前回复的待处理举报明细。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="can_moderate_flags",
            module_id="flags",
            resolver=_resolve_post_can_moderate_flags,
            description="当前用户是否可在前台处理举报。",
        )
    )


def _resolve_post_viewer_has_open_flag(post, context: dict) -> bool:
    return bool(getattr(post, "viewer_has_open_flag", False))


def _resolve_post_open_flag_count(post, context: dict) -> int:
    return int(getattr(post, "open_flag_count", 0) or 0)


def _resolve_post_open_flags(post, context: dict) -> list[dict]:
    open_flags = getattr(post, "open_flags_cache", [])
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


def _resolve_post_can_moderate_flags(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and user.is_staff)
