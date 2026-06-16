from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    get_extension_host_service,
    require_extension_host_service,
    runtime_service_method,
    runtime_service_value,
    RuntimeServiceProxy,
)

# 便捷代理
_moderation = RuntimeServiceProxy("moderation.service")


def get_runtime_like_service(default: Any = None):
    return get_extension_host_service("likes.service", default)


def require_runtime_like_service():
    return require_extension_host_service("likes.service")


def like_runtime_post(post_id: int, user: Any) -> bool:
    return bool(runtime_service_method(require_runtime_like_service(), "like_post")(post_id, user))


def unlike_runtime_post(post_id: int, user: Any) -> bool:
    return bool(runtime_service_method(require_runtime_like_service(), "unlike_post")(post_id, user))


def can_runtime_like_post(post: Any, user: Any) -> bool:
    service = get_runtime_like_service()
    if service is None:
        return False
    return bool(runtime_service_method(service, "can_like_post")(post, user))


def get_runtime_post_like_model():
    return runtime_service_value(
        require_runtime_like_service(),
        "model",
        required_message="likes.service 未提供点赞模型",
    )


def get_runtime_flag_service(default: Any = None):
    return get_extension_host_service("flags.service", default)


def require_runtime_flag_service():
    return require_extension_host_service("flags.service")


def report_runtime_post_flag(post_id: int, user: Any, reason: str, message: str = ""):
    return runtime_service_method(require_runtime_flag_service(), "report_post")(
        post_id,
        user,
        reason,
        message,
    )


def list_runtime_post_flags(*, status: str | None = None, page: int = 1, limit: int = 20, user: Any | None = None):
    return runtime_service_method(require_runtime_flag_service(), "get_flag_list")(
        status=status,
        page=page,
        limit=limit,
        user=user,
    )


def resolve_runtime_post_flag(flag_id: int, admin_user: Any, status: str, resolution_note: str = ""):
    return runtime_service_method(require_runtime_flag_service(), "resolve_flag")(
        flag_id,
        admin_user,
        status,
        resolution_note,
    )


def resolve_runtime_post_flags(post_id: int, admin_user: Any, status: str, resolution_note: str = "") -> int:
    return int(runtime_service_method(require_runtime_flag_service(), "resolve_post_flags")(
        post_id,
        admin_user,
        status,
        resolution_note,
    ) or 0)


def delete_runtime_post_flags(post_id: int, user: Any) -> int:
    return int(runtime_service_method(require_runtime_flag_service(), "delete_post_flags")(
        post_id,
        user,
    ) or 0)


def get_runtime_post_flag_model():
    return runtime_service_value(
        require_runtime_flag_service(),
        "model",
        required_message="flags.service 未提供举报模型",
    )


def get_runtime_approval_service(default: Any = None):
    return get_extension_host_service("approval.service", default)


def require_runtime_approval_service():
    return require_extension_host_service("approval.service")


def list_runtime_approval_queue_items(*, content_type: str = "all") -> list[dict]:
    return list(runtime_service_method(require_runtime_approval_service(), "list_queue")(
        content_type=content_type,
    ) or [])


def process_runtime_approval_item(*, content_type: str, content_id: int, action: str, actor, note: str = "") -> dict:
    return dict(runtime_service_method(require_runtime_approval_service(), "process_item")(
        content_type=content_type,
        content_id=content_id,
        action=action,
        actor=actor,
        note=note,
    ) or {})


def bulk_process_runtime_approval_items(*, action: str, items, actor, note: str = "") -> list[dict]:
    return list(runtime_service_method(require_runtime_approval_service(), "bulk_process")(
        action=action,
        items=items,
        actor=actor,
        note=note,
    ) or [])
