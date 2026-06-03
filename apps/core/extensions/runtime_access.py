from __future__ import annotations

from typing import Any


def get_extension_host_service(key: str, default: Any = None) -> Any:
    from apps.core.extensions.bootstrap import get_extension_host

    host = get_extension_host()
    if host is None:
        return default
    return host.make(key, default)


def get_runtime_resource_registry():
    from apps.core.resource_registry import get_resource_registry

    return get_extension_host_service("resource.registry", get_resource_registry())


def get_runtime_model_service():
    return get_extension_host_service("models")


def get_runtime_model_url_service():
    return get_extension_host_service("model.urls")


def generate_runtime_model_slug(model: Any, source: Any, **kwargs) -> str | None:
    service = get_runtime_model_url_service()
    if service is None:
        return None
    try:
        return service.generate_slug(model, source, **kwargs)
    except KeyError:
        return None


def apply_runtime_model_visibility(model: Any, queryset, context: dict | None = None):
    model_service = get_runtime_model_service()
    if model_service is None:
        return queryset
    return model_service.apply_visibility(model, queryset, context or {})


def evaluate_runtime_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_model_policy

    return evaluate_model_policy(
        ability,
        user=user,
        model=model,
        default=default,
        **context,
    )


def get_runtime_search_service():
    return get_extension_host_service("search")


def get_runtime_locale_service():
    return get_extension_host_service("locales")


def get_runtime_formatter_service():
    return get_extension_host_service("formatters")


def get_runtime_discussion_lifecycle_service():
    return get_extension_host_service("discussion.lifecycle")
