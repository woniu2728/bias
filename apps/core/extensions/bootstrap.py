from __future__ import annotations

from django.db import OperationalError, ProgrammingError

from apps.core.extensions.bootstrap_state import (
    is_extension_host_bootstrapped,
    mark_extension_host_bootstrapped,
    reset_extension_host_bootstrap_state,
)
from apps.core.extensions.manager import get_extension_manager


_extension_application = None


def get_extension_host(*, force: bool = False):
    return bootstrap_extension_host(force=force)


def get_extension_application(*, force: bool = False):
    return get_extension_host(force=force)


def clear_bootstrapped_extension_application() -> None:
    global _extension_application
    _extension_application = None


def clear_bootstrapped_extension_host() -> None:
    clear_bootstrapped_extension_application()


def reset_extension_application_bootstrap() -> None:
    reset_extension_host_bootstrap()


def reset_extension_application_bootstrap_state() -> None:
    reset_extension_host_bootstrap()


def reset_extension_host_bootstrap() -> None:
    clear_bootstrapped_extension_host()
    reset_extension_host_bootstrap_state()


def build_extension_application(
    *,
    manager=None,
    forum_registry=None,
    event_bus=None,
    resource_registry=None,
    force: bool = False,
):
    return build_extension_host(
        manager=manager,
        forum_registry=forum_registry,
        event_bus=event_bus,
        resource_registry=resource_registry,
        force=force,
    )


def build_extension_host(
    *,
    manager=None,
    forum_registry=None,
    event_bus=None,
    resource_registry=None,
    force: bool = False,
):
    from apps.core.domain_events import get_forum_event_bus
    from apps.core.forum_registry import get_forum_registry
    from apps.core.resource_registry import get_resource_registry
    from apps.core.extensions.application import ExtensionApplication

    resolved_manager = manager or get_extension_manager()
    resolved_manager.load(force=force)
    extensions_to_boot = tuple(resolved_manager.get_enabled_extensions())
    return ExtensionApplication(
        extensions_to_boot=extensions_to_boot,
        forum_registry=forum_registry or get_forum_registry(),
        event_bus=event_bus or get_forum_event_bus(),
        resource_registry=resource_registry or get_resource_registry(),
    ).boot()


def bootstrap_extension_application(*, force: bool = False):
    return bootstrap_extension_host(force=force)


def bootstrap_extension_host(*, force: bool = False):
    global _extension_application
    if is_extension_host_bootstrapped() and not force and _extension_application is not None:
        return _extension_application

    try:
        application = build_extension_host(force=force)
        _extension_application = application
    except (OperationalError, ProgrammingError, RuntimeError):
        return None
    mark_extension_host_bootstrapped()
    return application
