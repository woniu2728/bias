from __future__ import annotations

from typing import Any


def resolve_runtime_user_by_id(user_id: Any):
    provider = get_runtime_user_model_provider()
    if provider is None:
        return None
    resolver = provider.get("get_by_id")
    if not callable(resolver):
        return None
    return resolver(user_id)


def serialize_runtime_users_by_ids(user_ids, *, limit: int = 50) -> list[dict]:
    provider = get_runtime_user_model_provider()
    if provider is None:
        return []
    serializer = provider.get("serialize_many_by_ids")
    if not callable(serializer):
        return []
    return list(serializer(list(user_ids or []), limit=int(limit or 50)) or [])


def ensure_runtime_admin_user(*, username: str, email: str, password: str) -> dict:
    provider = get_runtime_user_model_provider()
    if provider is None:
        raise RuntimeError("用户扩展尚未提供管理员账号管理能力")
    handler = provider.get("ensure_admin")
    if not callable(handler):
        raise RuntimeError("用户扩展尚未提供管理员账号管理能力")
    return dict(handler(username=username, email=email, password=password) or {})


def get_runtime_user_model_provider() -> dict[str, Any] | None:
    provider = _resolve_user_model_provider()
    if provider is not None:
        return provider
    try:
        from apps.core.extensions.bootstrap import get_extension_application

        get_extension_application(force=True)
    except Exception:
        return None
    return _resolve_user_model_provider()


def _resolve_user_model_provider() -> dict[str, Any] | None:
    from apps.core.extensions.system_runtime import get_runtime_system_service

    service = get_runtime_system_service("user")
    if service is None:
        return None
    for definition in getattr(service, "get_definitions", lambda: [])():
        if definition.key != "model_provider":
            continue
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict):
            provider = payload.get("provider", payload)
            if callable(provider):
                provider = provider()
            if isinstance(provider, dict):
                return provider
    return None
