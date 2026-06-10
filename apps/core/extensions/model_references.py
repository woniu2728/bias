from __future__ import annotations

from typing import Any

from apps.core.extensions.types import ExtensionModelReference


def resolve_model_reference(model: Any, host: Any = None) -> Any:
    if not isinstance(model, ExtensionModelReference):
        return model

    service_key = str(model.service_key or "").strip()
    if not service_key:
        return None

    service = _peek_host_service(host, service_key)
    if service is None and host is None:
        from apps.core.extensions.bootstrap import get_extension_host

        runtime_host = get_extension_host()
        service = _peek_host_service(runtime_host, service_key)

    if service is None:
        return None

    attribute = str(model.attribute or "model").strip() or "model"
    if isinstance(service, dict):
        return service.get(attribute)
    return getattr(service, attribute, None)


def _peek_host_service(host: Any, key: str) -> Any:
    if host is None or not key:
        return None

    normalize_key = getattr(host, "_container_key", None)
    resolve_alias = getattr(host, "_resolve_alias", None)
    normalized = str(key or "").strip()
    if callable(normalize_key):
        normalized = normalize_key(normalized)
    if callable(resolve_alias):
        normalized = resolve_alias(normalized)

    instances = getattr(host, "_instances", {})
    if normalized in instances:
        return instances[normalized]

    make = getattr(host, "make", None)
    if callable(make):
        singletons = getattr(host, "_singletons", {})
        bindings = getattr(host, "_bindings", {})
        if normalized in singletons or normalized in bindings:
            return make(normalized, None)
    return None


def model_class(model: Any, host: Any = None) -> type | None:
    resolved_model = resolve_model_reference(model, host)
    if resolved_model is None:
        return None
    if isinstance(resolved_model, type):
        return resolved_model
    return getattr(resolved_model, "__class__", None)


def model_matches(registered_model: Any, model: Any, host: Any = None) -> bool:
    resolved_registered_model = resolve_model_reference(registered_model, host)
    resolved_model = resolve_model_reference(model, host)
    registered_class = model_class(registered_model, host)
    candidate_class = model_class(model, host)
    if registered_class is None or candidate_class is None:
        return resolved_registered_model == resolved_model
    try:
        return issubclass(candidate_class, registered_class)
    except TypeError:
        return resolved_registered_model == resolved_model
