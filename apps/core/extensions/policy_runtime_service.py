from __future__ import annotations

from apps.core.extensions.bootstrap import get_extension_application


def get_extension_policy_handlers() -> dict[str, list[callable]]:
    handlers: dict[str, list[callable]] = {}
    application = get_extension_application()
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
    decisions: list[bool] = []
    for handler in handlers:
        result = handler(**context)
        if result is None:
            continue
        decisions.append(bool(result))

    if any(decision is False for decision in decisions):
        return False
    if any(decision is True for decision in decisions):
        return True
    return default


def evaluate_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    normalized_ability = str(ability or "").strip()
    if not normalized_ability:
        return default

    decisions: list[bool] = []
    for mount in get_extension_policy_mounts():
        handler = getattr(mount, "handler", None)
        if not callable(handler):
            continue
        mount_model = getattr(mount, "model", None)
        is_global = bool(getattr(mount, "global_policy", False))
        if mount_model is None and not is_global:
            continue
        if mount_model is not None and not _model_matches(mount_model, model):
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
        decisions.append(bool(result))

    keyed = evaluate_extension_policy(
        f"model.{normalized_ability}",
        default=None,
        user=user,
        ability=normalized_ability,
        model=model,
        **context,
    )
    if keyed is not None:
        decisions.append(bool(keyed))

    if any(decision is False for decision in decisions):
        return False
    if any(decision is True for decision in decisions):
        return True
    return default


def assert_model_policy(ability: str, *, user=None, model=None, **context) -> None:
    if evaluate_model_policy(ability, user=user, model=model, default=True, **context) is False:
        raise PermissionError("无权限")


def _model_matches(expected, model) -> bool:
    if model is None:
        return False
    if isinstance(expected, str):
        model_class = model if isinstance(model, type) else model.__class__
        return expected in {model_class.__name__, f"{model_class.__module__}.{model_class.__name__}"}
    if isinstance(model, type):
        try:
            return issubclass(model, expected)
        except TypeError:
            return model == expected
    try:
        return isinstance(model, expected)
    except TypeError:
        return model == expected


def _invoke_policy_handler(handler, **context):
    try:
        return handler(**context)
    except TypeError:
        return handler(context.get("user"), context.get("ability"), context.get("model"))
