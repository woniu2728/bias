from __future__ import annotations

from django.conf import settings
from django.urls import clear_url_caches


def mark_extension_runtime_requires_rebuild(reason: str, *, extension_id: str = "") -> None:
    from apps.core.models import Setting

    payload = {
        "reason": reason,
        "extension_id": extension_id,
        "urlconf": settings.ROOT_URLCONF,
    }
    Setting.objects.update_or_create(
        key="extensions_runtime_rebuild_required",
        defaults={"value": __import__("json").dumps(payload, ensure_ascii=False)},
    )


def invalidate_extension_frontend_assets(
    reason: str,
    *,
    extension_id: str = "",
    include_published: bool = False,
) -> dict:
    from apps.core.extensions.frontend_compiler import flush_extension_frontend_assets

    result = flush_extension_frontend_assets(include_published=include_published)
    mark_extension_runtime_requires_rebuild(reason, extension_id=extension_id)
    return result


def clear_extension_runtime_rebuild_marker() -> None:
    from apps.core.models import Setting

    Setting.objects.filter(key="extensions_runtime_rebuild_required").delete()


def rebuild_extension_runtime_state() -> None:
    reset_extension_runtime_state()
    clear_url_caches()
    clear_extension_runtime_rebuild_marker()


def reset_extension_runtime_state() -> None:
    from apps.core.domain_events import get_forum_event_bus
    from apps.core.extensions.bootstrap import clear_bootstrapped_extension_application
    from apps.core.extensions.bootstrap_state import reset_extension_application_bootstrap_state
    from apps.core.extensions import frontend_runtime_service
    from apps.core.extensions.manager import get_extension_manager
    from apps.core.extensions.runtime_event_listeners import (
        bootstrap_extension_runtime_event_listeners,
        reset_extension_runtime_event_listener_bootstrap,
    )
    from apps.core import forum_event_listeners
    from apps.core.forum_runtime import clear_realtime_included_enrichers
    from apps.core.forum_registry import get_forum_registry
    from apps.core.resource_registry import get_resource_registry
    from apps.core.settings_service import clear_runtime_setting_caches

    frontend_runtime_service._frontend_runtime_catalog = {}
    frontend_runtime_service._frontend_runtime_bootstrapped = False

    clear_bootstrapped_extension_application()
    reset_extension_application_bootstrap_state()
    get_extension_manager().invalidate()

    forum_registry = get_forum_registry()
    forum_registry._external_enabled_module_ids.clear()

    resource_registry = get_resource_registry()

    event_bus = get_forum_event_bus()
    event_bus.clear()
    reset_extension_runtime_event_listener_bootstrap()
    forum_event_listeners._listeners_bootstrapped = False
    clear_realtime_included_enrichers()
    forum_event_listeners.bootstrap_forum_event_listeners()
    bootstrap_extension_runtime_event_listeners()

    clear_runtime_setting_caches()
