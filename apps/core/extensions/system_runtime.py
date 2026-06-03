from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_runtime_system_service(key: str):
    from apps.core.extensions.runtime_access import get_extension_host_service

    return get_extension_host_service(key)


def run_runtime_system_hooks(key: str, hook: str, payload: dict | None = None, context: dict | None = None) -> list[Any]:
    service = get_runtime_system_service(key)
    if service is None or not hasattr(service, "run"):
        return []
    try:
        return list(service.run(hook, payload or {}, context or {}))
    except Exception:
        logger.exception("运行扩展系统 hook 失败: %s.%s", key, hook)
        return []


def report_runtime_error(error: BaseException, *, request=None, operation: str = "request", context: dict | None = None) -> list[Any]:
    payload = {
        "error": error,
        "error_type": error.__class__.__name__,
        "message": str(error),
        "operation": operation,
    }
    if request is not None:
        payload.update({
            "method": getattr(request, "method", ""),
            "path": getattr(request, "path", ""),
        })
    results = run_runtime_system_hooks("error.handling", "report", payload, context or {})
    for reporter in get_runtime_error_reporters():
        try:
            if callable(reporter):
                results.append(reporter(payload, dict(context or {})))
        except TypeError:
            try:
                results.append(reporter(error))
            except Exception:
                logger.exception("扩展错误 reporter 执行失败: %s", reporter)
        except Exception:
            logger.exception("扩展错误 reporter 执行失败: %s", reporter)
    return results


def handle_runtime_error(error: BaseException, *, request=None, operation: str = "request", context: dict | None = None):
    payload = {
        "error": error,
        "error_type": resolve_runtime_error_type(error),
        "message": str(error),
        "operation": operation,
        "http_status": resolve_runtime_error_status(error),
    }
    if request is not None:
        payload.update({
            "method": getattr(request, "method", ""),
            "path": getattr(request, "path", ""),
        })
    for exception_class, handler in get_runtime_error_handlers().items():
        try:
            if not isinstance(error, exception_class):
                continue
        except TypeError:
            if error.__class__ != exception_class:
                continue
        if not callable(handler):
            return handler
        try:
            return handler(payload, dict(context or {}))
        except TypeError:
            return handler(error)
    return None


def resolve_runtime_error_type(error: BaseException) -> str:
    for exception_class, error_type in get_runtime_error_types().items():
        try:
            if isinstance(error, exception_class):
                return error_type
        except TypeError:
            if error.__class__ == exception_class:
                return error_type
    return error.__class__.__name__


def resolve_runtime_error_status(error: BaseException, default: int = 500) -> int:
    return int(get_runtime_error_statuses().get(resolve_runtime_error_type(error), default))


def resolve_runtime_filesystem_driver(driver: str, config: dict | None = None):
    normalized = str(driver or "").strip().lower()
    if not normalized:
        return None
    payload = {
        "driver": normalized,
        "config": dict(config or {}),
    }
    service = get_runtime_system_service("filesystem")
    if service is None:
        return None
    for definition in getattr(service, "get_definitions", lambda: [])():
        if definition.key != "driver":
            continue
        callback = definition.callback
        if isinstance(callback, dict):
            if str(callback.get("name") or "").strip().lower() != normalized:
                continue
            driver_factory = callback.get("driver")
            return driver_factory(dict(config or {})) if callable(driver_factory) else driver_factory
        if callable(callback):
            result = callback(payload, {})
            if result is not None:
                return result
    return None


def verify_runtime_user_password(user: Any, password: str, *, default_checker: Any = None) -> bool:
    for identifier, checker in get_runtime_password_checkers(default_checker=default_checker).items():
        if not callable(checker):
            continue
        try:
            result = checker(user, password)
        except TypeError:
            result = checker({
                "user": user,
                "password": password,
                "identifier": identifier,
            }, {})
        if result is True:
            return True
        if result is False:
            return False
    return False


def get_runtime_password_checkers(*, default_checker: Any = None) -> dict[str, Any]:
    checkers: dict[str, Any] = {}
    if default_checker is not None:
        checkers["django"] = default_checker

    for definition in _get_system_definitions("auth"):
        payload = _resolve_system_payload(definition)
        if definition.key == "remove_password_checker" and isinstance(payload, dict):
            identifier = str(payload.get("identifier") or "").strip()
            if identifier:
                checkers.pop(identifier, None)
            continue
        if definition.key != "password_checker" or not isinstance(payload, dict):
            continue
        identifier = str(payload.get("identifier") or "").strip()
        checker = payload.get("checker")
        if identifier and checker is not None:
            checkers[identifier] = checker
    return checkers


def resolve_runtime_session_driver(driver: str, config: dict | None = None):
    normalized = str(driver or "").strip().lower()
    if not normalized:
        return None
    for item in list_runtime_session_drivers():
        if item["name"] != normalized:
            continue
        driver_factory = item.get("driver")
        return driver_factory(dict(config or {})) if callable(driver_factory) else driver_factory
    return None


def list_runtime_session_drivers() -> list[dict[str, Any]]:
    service = get_runtime_system_service("session")
    if service is None:
        return []
    drivers = []
    for definition in getattr(service, "get_definitions", lambda: [])():
        if definition.key != "driver":
            continue
        payload = _resolve_system_payload(definition)
        if isinstance(payload, dict) and str(payload.get("name") or "").strip():
            drivers.append({
                "name": str(payload.get("name") or "").strip().lower(),
                "driver": payload.get("driver"),
                "description": str(payload.get("description") or ""),
                "extension_id": definition.module_id,
            })
    return sorted(drivers, key=lambda item: item["name"])


def get_runtime_csrf_exempt_routes() -> set[str]:
    routes: set[str] = set()
    for definition in _get_system_definitions("csrf", "exempt_route"):
        payload = _resolve_system_payload(definition)
        if isinstance(payload, dict):
            route_name = str(payload.get("route_name") or "").strip()
            if route_name:
                routes.add(route_name)
        elif isinstance(payload, str) and payload.strip():
            routes.add(payload.strip())
    return routes


def is_runtime_csrf_exempt_route(route_name: str) -> bool:
    normalized = str(route_name or "").strip()
    return bool(normalized and normalized in get_runtime_csrf_exempt_routes())


def should_throttle_runtime_api_request(request) -> bool:
    for name, throttler in get_runtime_api_throttlers().items():
        if not callable(throttler):
            continue
        try:
            result = throttler(request)
        except TypeError:
            result = throttler(_build_request_payload(request, throttler=name), {})
        if result is False:
            return False
        if result is True:
            return True
    return False


def get_runtime_api_throttlers() -> dict[str, Any]:
    throttlers: dict[str, Any] = {}
    for definition in _get_system_definitions("throttle.api"):
        payload = _resolve_system_payload(definition)
        if definition.key == "remove_throttler" and isinstance(payload, dict):
            name = str(payload.get("name") or "").strip()
            if name:
                throttlers.pop(name, None)
            continue
        if definition.key != "throttler" or not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or "").strip()
        throttler = payload.get("throttler")
        if name and throttler is not None:
            throttlers[name] = throttler
    return throttlers


def get_runtime_user_display_name_drivers() -> dict[str, Any]:
    return _get_runtime_user_drivers("display_name_driver")


def get_runtime_user_avatar_drivers() -> dict[str, Any]:
    return _get_runtime_user_drivers("avatar_driver")


def apply_runtime_user_group_processors(user: Any, group_ids: list[Any] | tuple[Any, ...]) -> list[Any]:
    output = list(group_ids or [])
    for processor in get_runtime_user_group_processors():
        callback = processor.get("callback")
        if not callable(callback):
            continue
        try:
            result = callback(user, list(output))
        except TypeError:
            result = callback({
                "user": user,
                "group_ids": list(output),
            }, {})
        if result is not None:
            output = list(result)
    return output


def get_runtime_user_group_processors() -> list[dict[str, Any]]:
    processors = []
    for definition in _get_system_definitions("user", "permission_groups"):
        payload = _resolve_system_payload(definition)
        if isinstance(payload, dict):
            processors.append({
                "callback": payload.get("callback"),
                "description": str(payload.get("description") or ""),
                "extension_id": definition.module_id,
            })
    return processors


def get_runtime_user_preference_transformers() -> dict[str, dict[str, Any]]:
    transformers: dict[str, dict[str, Any]] = {}
    for definition in _get_system_definitions("user", "preference_transformer"):
        payload = _resolve_system_payload(definition)
        if not isinstance(payload, dict):
            continue
        key = str(payload.get("key") or "").strip()
        if key:
            transformers[key] = {
                "transformer": payload.get("transformer"),
                "default": payload.get("default"),
                "extension_id": definition.module_id,
            }
    return transformers


def list_runtime_filesystem_disks() -> list[dict[str, Any]]:
    service = get_runtime_system_service("filesystem")
    if service is None:
        return []
    disks = []
    for definition in getattr(service, "get_definitions", lambda: [])():
        if definition.key != "disk":
            continue
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict) and str(payload.get("name") or "").strip():
            disks.append({
                "name": str(payload.get("name") or "").strip().lower(),
                "driver": str(payload.get("driver") or "local").strip().lower() or "local",
                "config": payload.get("config"),
                "description": str(payload.get("description") or ""),
                "extension_id": definition.module_id,
            })
    return sorted(disks, key=lambda item: item["name"])


def list_runtime_console_commands() -> list[dict[str, Any]]:
    commands = _list_console_payloads("command")
    return sorted(
        [command for command in commands if str(command.get("name") or "").strip()],
        key=lambda command: str(command.get("name") or ""),
    )


def list_runtime_console_schedules() -> list[dict[str, Any]]:
    return sorted(
        [schedule for schedule in _list_console_payloads("schedule") if str(schedule.get("name") or "").strip()],
        key=lambda schedule: str(schedule.get("name") or ""),
    )


def run_runtime_console_command(name: str, *, options: dict | None = None):
    normalized = str(name or "").strip()
    if not normalized:
        return None
    for command in list_runtime_console_commands():
        if str(command.get("name") or "").strip() != normalized:
            continue
        handler = command.get("handler")
        if callable(handler):
            return handler(dict(options or {}))
        return command
    return None


def _list_console_payloads(key: str) -> list[dict[str, Any]]:
    service = get_runtime_system_service("console")
    if service is None:
        return []
    payloads: list[dict[str, Any]] = []
    for definition in getattr(service, "get_definitions", lambda: [])():
        if definition.key != key:
            continue
        callback = definition.callback
        if callable(callback):
            result = callback({}, {})
        else:
            result = callback
        if isinstance(result, dict):
            payloads.append({**result, "extension_id": definition.module_id})
        elif isinstance(result, (list, tuple)):
            payloads.extend({**item, "extension_id": definition.module_id} for item in result if isinstance(item, dict))
    return payloads


def get_runtime_error_statuses() -> dict[str, int]:
    statuses: dict[str, int] = {}
    for definition in _get_system_definitions("error.handling", "status"):
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict) and payload.get("error_type"):
            statuses[str(payload["error_type"])] = int(payload.get("http_status") or 500)
    return statuses


def get_runtime_error_types() -> dict[Any, str]:
    types: dict[Any, str] = {}
    for definition in _get_system_definitions("error.handling", "type"):
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict) and payload.get("exception_class") and payload.get("error_type"):
            types[payload["exception_class"]] = str(payload["error_type"])
    return types


def get_runtime_error_handlers() -> dict[Any, Any]:
    handlers: dict[Any, Any] = {}
    for definition in _get_system_definitions("error.handling", "handler"):
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict) and payload.get("exception_class") and payload.get("handler"):
            handlers[payload["exception_class"]] = payload["handler"]
    return handlers


def get_runtime_error_reporters() -> list[Any]:
    reporters = []
    for definition in _get_system_definitions("error.handling", "reporter"):
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if isinstance(payload, dict) and payload.get("reporter"):
            reporters.append(payload["reporter"])
    return reporters


def _get_runtime_user_drivers(key: str) -> dict[str, Any]:
    drivers: dict[str, Any] = {}
    for definition in _get_system_definitions("user", key):
        payload = _resolve_system_payload(definition)
        if not isinstance(payload, dict):
            continue
        identifier = str(payload.get("identifier") or "").strip()
        driver = payload.get("driver")
        if identifier and driver is not None:
            drivers[identifier] = driver
    return drivers


def _get_system_definitions(service_key: str, hook: str = ""):
    service = get_runtime_system_service(service_key)
    if service is None:
        return []
    return [
        definition
        for definition in getattr(service, "get_definitions", lambda: [])()
        if not hook or definition.key == hook
    ]


def _resolve_system_payload(definition):
    payload = definition.callback
    if callable(payload):
        return payload({}, {})
    return payload


def _build_request_payload(request, **extra):
    return {
        "request": request,
        "method": getattr(request, "method", ""),
        "path": getattr(request, "path", ""),
        "route_name": getattr(getattr(request, "resolver_match", None), "url_name", ""),
        **extra,
    }
