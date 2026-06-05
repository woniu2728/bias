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


def get_runtime_model_relation(model: Any, name: str):
    service = get_runtime_model_service()
    if service is None or not hasattr(service, "get_relation"):
        return None
    return service.get_relation(model, name)


def resolve_runtime_model_relation(instance: Any, name: str, *, model: Any | None = None, default: Any = None):
    service = get_runtime_model_service()
    if service is None or instance is None:
        return default
    if hasattr(service, "resolve_relation"):
        resolved = service.resolve_relation(model or instance.__class__, name, instance)
        return default if resolved is None else resolved
    return default


def apply_runtime_model_visibility(model: Any, queryset, context: dict | None = None):
    model_service = get_runtime_model_service()
    if model_service is None:
        return queryset
    return model_service.apply_visibility(model, queryset, context or {})


def has_runtime_model_visibility(model: Any, *, ability: str | None = None) -> bool:
    model_service = get_runtime_model_service()
    if model_service is None:
        return False
    if hasattr(model_service, "has_visibility"):
        return bool(model_service.has_visibility(model, ability=ability))
    try:
        definitions = model_service.get_visibility()
    except Exception:
        return False
    requested_ability = str(ability or "view")
    return any(
        _model_matches(definition.model, model)
        and str(definition.ability or "*") in {"*", requested_ability}
        for definition in definitions
    )


def is_runtime_model_private(instance: Any, *, model: Any | None = None, default: bool | None = None) -> bool:
    model_service = get_runtime_model_service()
    fallback = bool(False if default is None else default)
    if model_service is None:
        return fallback
    model_class = model or instance.__class__
    return bool(model_service.is_private(model_class, instance, default=fallback))


def refresh_runtime_model_private(instance: Any, *, model: Any | None = None, save: bool = False) -> bool:
    if instance is None or not hasattr(instance, "is_private"):
        return bool(getattr(instance, "is_private", False))
    resolved = is_runtime_model_private(instance, model=model)
    if bool(getattr(instance, "is_private", False)) == resolved:
        return resolved
    instance.is_private = resolved
    if save and getattr(instance, "pk", None):
        instance.save(update_fields=["is_private"])
    return resolved


def can_view_runtime_model_private(model: Any, *, user=None, default: bool = False, **context) -> bool:
    return bool(evaluate_runtime_model_policy(
        "viewPrivate",
        user=user,
        model=model,
        default=default,
        **context,
    ))


def can_view_runtime_private_instance(instance: Any, *, user=None, model: Any | None = None, **context) -> bool:
    if not getattr(instance, "is_private", False):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return can_view_runtime_model_private(
        model or instance,
        user=user,
        instance=instance,
        **context,
    )


def evaluate_runtime_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_model_policy

    return evaluate_model_policy(
        ability,
        user=user,
        model=model,
        default=default,
        **context,
    )


def evaluate_runtime_query_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_query_model_policy

    return evaluate_query_model_policy(
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


def get_runtime_view_service():
    return get_extension_host_service("views")


def render_runtime_template(template_name: str, context: dict | None = None, *, request: Any = None) -> str:
    service = get_runtime_view_service()
    if service is None:
        raise RuntimeError("扩展视图服务尚未启动")
    return service.render(template_name, context or {}, request=request)


def get_runtime_discussion_lifecycle_service():
    return get_extension_host_service("discussion.lifecycle")


def get_runtime_post_lifecycle_service():
    return get_extension_host_service("post.lifecycle")


def get_runtime_post_event_data_service():
    return get_extension_host_service("post.events")


def _model_matches(registered_model: Any, model: Any) -> bool:
    registered_class = registered_model if isinstance(registered_model, type) else getattr(registered_model, "__class__", None)
    model_class = model if isinstance(model, type) else getattr(model, "__class__", None)
    if registered_class is None or model_class is None:
        return registered_model == model
    return issubclass(model_class, registered_class)
