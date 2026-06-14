from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    get_extension_host_service,
    get_runtime_resource_registry,
    require_extension_host_service,
    runtime_service_method,
)


def get_runtime_user_service(default: Any = None):
    return get_extension_host_service("users.service", default)


def require_runtime_user_service():
    return require_extension_host_service("users.service")


def ensure_runtime_user_not_suspended(user: Any, action_label: str = "") -> None:
    runtime_service_method(require_runtime_user_service(), "ensure_not_suspended")(user, action_label)


def ensure_runtime_user_email_confirmed(user: Any, action_label: str = "") -> None:
    runtime_service_method(require_runtime_user_service(), "ensure_email_confirmed")(user, action_label)


def ensure_runtime_forum_permission(user: Any, permission_names, message: str = "无权限") -> None:
    runtime_service_method(require_runtime_user_service(), "ensure_forum_permission")(
        user,
        permission_names,
        message,
    )


def has_runtime_forum_permission(user: Any, permission_names) -> bool:
    from apps.core.forum_permissions import has_forum_permission

    return has_forum_permission(user, permission_names)


def requires_runtime_content_approval(user: Any, bypass_permission: str) -> bool:
    return bool(
        runtime_service_method(require_runtime_user_service(), "requires_content_approval")(
            user,
            bypass_permission,
        )
    )


def get_runtime_user_preference(user: Any, key: str, fallback: Any = None) -> Any:
    service = require_runtime_user_service()
    try:
        return runtime_service_method(service, "get_preference")(user, key, fallback=fallback)
    except RuntimeError:
        return fallback


def get_runtime_user_preference_transformers() -> dict[str, dict[str, Any]]:
    from apps.core.extensions.system_runtime import get_runtime_user_preference_transformers as get_transformers

    return dict(get_transformers() or {})


def apply_runtime_user_group_processors(user: Any, group_ids: list[Any] | tuple[Any, ...]) -> list[Any]:
    from apps.core.extensions.system_runtime import apply_runtime_user_group_processors as apply_processors

    return list(apply_processors(user, list(group_ids or [])) or [])


def verify_runtime_user_password(user: Any, password: str, *, default_checker: Any = None) -> bool:
    from apps.core.extensions.system_runtime import verify_runtime_user_password as verify_password

    return bool(verify_password(user, password, default_checker=default_checker))


def get_runtime_user_model():
    service = require_runtime_user_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("users.service 未提供用户模型")
    return model


def get_runtime_group_model():
    service = require_runtime_user_service()
    model = service.get("group_model") if isinstance(service, dict) else getattr(service, "group_model", None)
    if model is None:
        raise RuntimeError("users.service 未提供用户组模型")
    return model


def get_runtime_permission_model():
    service = require_runtime_user_service()
    model = service.get("permission_model") if isinstance(service, dict) else getattr(service, "permission_model", None)
    if model is None:
        raise RuntimeError("users.service 未提供权限模型")
    return model


def resolve_runtime_user_by_username(username: str):
    return runtime_service_method(require_runtime_user_service(), "get_by_username")(username)


def get_runtime_user_by_id(user_id: int):
    return runtime_service_method(require_runtime_user_service(), "get_by_id")(user_id)


def list_runtime_users_by_usernames(usernames) -> list[Any]:
    return list(runtime_service_method(require_runtime_user_service(), "list_by_usernames")(usernames) or [])


def get_runtime_username_id_map(usernames) -> dict[str, int]:
    return dict(runtime_service_method(require_runtime_user_service(), "username_id_map")(usernames) or {})


def serialize_runtime_users_by_ids(user_ids, *, limit: int = 50) -> list[dict]:
    service = require_runtime_user_service()
    try:
        serializer = runtime_service_method(service, "serialize_many_by_ids")
    except RuntimeError:
        return []
    return list(serializer(list(user_ids or []), limit=int(limit or 50)) or [])


def serialize_runtime_user(user: Any, *, resource: str = "user_detail", context: dict | None = None) -> dict | None:
    if not user:
        return None
    return get_runtime_resource_registry().serialize(
        str(resource or "user_detail"),
        user,
        context or {},
    )


def increment_runtime_user_discussion_count(user_id: int, delta: int) -> int:
    return int(
        runtime_service_method(require_runtime_user_service(), "increment_discussion_count")(
            user_id,
            delta,
        )
        or 0
    )


def increment_runtime_user_comment_count(user_id: int, delta: int) -> int:
    return int(
        runtime_service_method(require_runtime_user_service(), "increment_comment_count")(
            user_id,
            delta,
        )
        or 0
    )


def apply_runtime_user_comment_count_deltas(deltas: dict | None) -> int:
    return int(
        runtime_service_method(require_runtime_user_service(), "apply_comment_count_deltas")(
            dict(deltas or {}),
        )
        or 0
    )


def ensure_runtime_admin_user(*, username: str, email: str, password: str) -> dict:
    service = require_runtime_user_service()
    try:
        handler = runtime_service_method(service, "ensure_admin")
    except RuntimeError as exc:
        raise RuntimeError("用户扩展尚未提供管理员账号管理能力") from exc
    return dict(handler(username=username, email=email, password=password) or {})
