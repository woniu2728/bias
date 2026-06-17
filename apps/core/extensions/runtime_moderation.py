from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    RuntimeServiceProxy,
    get_extension_host_service,
    require_extension_host_service,
)

_like = RuntimeServiceProxy("likes.service")
_flag = RuntimeServiceProxy("flags.service")
_approval = RuntimeServiceProxy("approval.service")


def get_runtime_like_service(default: Any = None):
    return get_extension_host_service("likes.service", default)


def require_runtime_like_service():
    return require_extension_host_service("likes.service")


def like_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_like.like_post(post_id, user))


def unlike_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_like.unlike_post(post_id, user))


def can_runtime_like_post(post: Any, user: Any) -> bool:
    service = get_runtime_like_service()
    if service is None:
        return False
    from apps.core.extensions.runtime_core import runtime_service_method
    return bool(runtime_service_method(service, "can_like_post")(post, user))


def get_runtime_post_like_model():
    return _like.value("model", required_message="likes.service 未提供点赞模型")


def get_runtime_flag_service(default: Any = None):
    return get_extension_host_service("flags.service", default)


def require_runtime_flag_service():
    return require_extension_host_service("flags.service")


def report_runtime_post_flag(post_id: int, user: Any, reason: str, message: str = ""):
    return _flag.report_post(post_id, user, reason, message)


def list_runtime_post_flags(*, status: str | None = None, page: int = 1, limit: int = 20, user: Any | None = None):
    return _flag.get_flag_list(status=status, page=page, limit=limit, user=user)


def resolve_runtime_post_flag(flag_id: int, admin_user: Any, status: str, resolution_note: str = ""):
    return _flag.resolve_flag(flag_id, admin_user, status, resolution_note)


def resolve_runtime_post_flags(post_id: int, admin_user: Any, status: str, resolution_note: str = "") -> int:
    return int(_flag.resolve_post_flags(post_id, admin_user, status, resolution_note) or 0)


def delete_runtime_post_flags(post_id: int, user: Any) -> int:
    return int(_flag.delete_post_flags(post_id, user) or 0)


def get_runtime_post_flag_model():
    return _flag.value("model", required_message="flags.service 未提供举报模型")


def get_runtime_approval_service(default: Any = None):
    return get_extension_host_service("approval.service", default)


def require_runtime_approval_service():
    return require_extension_host_service("approval.service")


def list_runtime_approval_queue_items(*, content_type: str = "all") -> list[dict]:
    return list(_approval.list_queue(content_type=content_type) or [])


def process_runtime_approval_item(*, content_type: str, content_id: int, action: str, actor, note: str = "") -> dict:
    return dict(_approval.process_item(content_type=content_type, content_id=content_id, action=action, actor=actor, note=note) or {})


def bulk_process_runtime_approval_items(*, action: str, items, actor, note: str = "") -> list[dict]:
    return list(_approval.bulk_process(action=action, items=items, actor=actor, note=note) or [])
