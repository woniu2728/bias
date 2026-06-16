from __future__ import annotations

from typing import Any


def get_extension_host_service(key: str, default: Any = None) -> Any:
    from apps.core.extensions.bootstrap import get_extension_host

    host = get_extension_host()
    if host is None:
        return default
    return host.make(key, default)


def require_extension_host_service(key: str) -> Any:
    service = get_extension_host_service(key)
    if service is None:
        raise RuntimeError(f"扩展运行时服务未注册: {key}")
    return service


def runtime_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"扩展运行时服务缺少方法: {name}")
    return method


def runtime_service_value(service: Any, name: str, default: Any = None, *, required_message: str = ""):
    if isinstance(service, dict):
        value = service.get(name, default)
    else:
        value = getattr(service, name, default)
    if value is None and required_message:
        raise RuntimeError(required_message)
    return value


def get_runtime_resource_registry():
    from apps.core.resource_registry import get_resource_registry

    return get_extension_host_service("resource.registry", get_resource_registry())
