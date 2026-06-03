from __future__ import annotations

from apps.core.extensions.event_bus import get_extension_event_bus
from apps.core.extensions.events import (
    ExtensionDisabledEvent,
    ExtensionEnabledEvent,
    ExtensionInstalledEvent,
    ExtensionPackagesSyncedEvent,
    ExtensionUninstalledEvent,
    RuntimeCacheClearedEvent,
)
from apps.core.extensions.lifecycle import invalidate_extension_frontend_assets


_bootstrapped_bus_ids: set[int] = set()


def reset_extension_runtime_event_listener_bootstrap() -> None:
    _bootstrapped_bus_ids.clear()


def bootstrap_extension_runtime_event_listeners() -> None:
    bus = get_extension_event_bus()
    bus_id = id(bus)
    if bus_id in _bootstrapped_bus_ids:
        return

    for event_type in (
        ExtensionInstalledEvent,
        ExtensionEnabledEvent,
        ExtensionDisabledEvent,
        ExtensionUninstalledEvent,
        ExtensionPackagesSyncedEvent,
        RuntimeCacheClearedEvent,
    ):
        bus.register(event_type, handle_extension_runtime_invalidation)
    _bootstrapped_bus_ids.add(bus_id)


def handle_extension_runtime_invalidation(event) -> None:
    from apps.core.extensions.formatter_service import clear_extension_formatter_cache
    from apps.core.extensions.frontend_runtime_service import clear_extension_frontend_runtime_cache
    from apps.core.extensions.locale_service import clear_extension_locale_cache
    from apps.core.extensions.lifecycle import reset_extension_runtime_state
    from django.urls import clear_url_caches

    clear_extension_frontend_runtime_cache()
    clear_extension_locale_cache()
    clear_extension_formatter_cache()
    invalidate_extension_frontend_assets(
        str(getattr(event, "reason", "") or "extension_runtime_invalidated"),
        extension_id=str(getattr(event, "extension_id", "") or ""),
    )
    reset_extension_runtime_state()
    clear_url_caches()
