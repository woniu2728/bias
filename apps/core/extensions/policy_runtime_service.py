from __future__ import annotations

from apps.core.authorization import resolve_authorization_decision
from apps.core.extensions.bootstrap import get_extension_application
from apps.core.extensions.model_references import model_matches, resolve_model_reference


def get_extension_policy_handlers(application=None) -> dict[str, list[callable]]:
    handlers: dict[str, list[callable]] = {}
    application = application or get_extension_application()
    if application is None:
        return handlers
    for mount in application.get_policy_mounts():
        handlers.setdefault(mount.key, []).append(mount.handler)
    return handlers


def get_extension_policy_mounts():
    application = get_extension_application()
    if application is None:
        return []
    return application.get_policy_mounts()


def evaluate_extension_policy(key: str, *, default=None, **context):
    normalized = str(key or "").strip()
    if not normalized:
        return default

    handlers = get_extension_policy_handlers().get(normalized, [])
    decisions: list[object] = []
    for handler in handlers:
        handler_context = {"ability": normalized, **context}
        result = handler(**handler_context)
        if result is None:
            continue
        decisions.append(result)

    return resolve_authorization_decision(decisions, default=default)


def evaluate_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    normalized_ability = str(ability or "").strip()
    if not normalized_ability:
        return default

    decisions: list[object] = []
    application = get_extension_application()
    mounts = application.get_policy_mounts() if application is not None else []
    for mount in mounts:
        handler = getattr(mount, "handler", None)
        if not callable(handler):
            continue
        mount_model = getattr(mount, "model", None)
        is_global = bool(getattr(mount, "global_policy", False))
        if mount_model is None and not is_global:
            continue
        if mount_model is not None and not _model_matches(mount_model, model, application):
            continue
        result = _invoke_policy_handler(
            handler,
            user=user,
            ability=normalized_ability,
            model=model,
            **context,
        )
        if result is None:
            continue
        decisions.append(result)

    handlers = get_extension_policy_handlers(application).get(f"model.{normalized_ability}", [])
    keyed_decisions: list[object] = []
    for handler in handlers:
        result = handler(user=user, ability=normalized_ability, model=model, **context)
        if result is not None:
            keyed_decisions.append(result)
    keyed = resolve_authorization_decision(keyed_decisions, default=None) if keyed_decisions else None
    if keyed is not None:
        decisions.append(keyed)

    return resolve_authorization_decision(decisions, default=default)


def evaluate_query_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    normalized_ability = str(ability or "").strip()
    if not normalized_ability:
        return default

    decisions: list[object] = []
    application = get_extension_application()
    mounts = application.get_policy_mounts() if application is not None else []
    for mount in mounts:
        if not bool(getattr(mount, "query_policy", False)):
            continue
        handler = getattr(mount, "handler", None)
        if not callable(handler):
            continue
        mount_model = getattr(mount, "model", None)
        if mount_model is not None and not _model_matches(mount_model, model, application):
            continue
        result = _invoke_policy_handler(
            handler,
            user=user,
            ability=normalized_ability,
            model=model,
            is_query=True,
            **context,
        )
        if result is None:
            continue
        decisions.append(result)

    return resolve_authorization_decision(decisions, default=default)


def assert_model_policy(ability: str, *, user=None, model=None, **context) -> None:
    if evaluate_model_policy(ability, user=user, model=model, default=True, **context) is False:
        raise PermissionError("无权限")


def _model_matches(expected, model, application=None) -> bool:
    if model is None:
        return False
    resolved_expected = resolve_model_reference(expected, application)
    if resolved_expected is None:
        return False
    if isinstance(expected, str):
        model_class = model if isinstance(model, type) else model.__class__
        return expected in {model_class.__name__, f"{model_class.__module__}.{model_class.__name__}"}
    if isinstance(model, type):
        try:
            return issubclass(model, resolved_expected)
        except TypeError:
            return model == resolved_expected
    try:
        return isinstance(model, resolved_expected)
    except TypeError:
        return model_matches(expected, model, application)


def _invoke_policy_handler(handler, **context):
    try:
        return handler(**context)
    except TypeError:
        return handler(context.get("user"), context.get("ability"), context.get("model"))
