from __future__ import annotations

import json
import time
import uuid

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.urls import clear_url_caches
from django.utils import timezone


RUNTIME_REBUILD_MARKER_KEY = "extensions_runtime_rebuild_required"
RUNTIME_VERSION_KEY = "extensions_runtime_version"
_runtime_version_seen = ""
_runtime_version_last_checked_at = 0.0
_runtime_version_check_interval_seconds = 1.0


def mark_extension_runtime_requires_rebuild(reason: str, *, extension_id: str = "") -> None:
    from apps.core.models import Setting

    version = f"{timezone.now().isoformat()}:{uuid.uuid4().hex}"
    payload = {
        "reason": reason,
        "extension_id": extension_id,
        "urlconf": settings.ROOT_URLCONF,
        "version": version,
    }
    Setting.objects.update_or_create(
        key=RUNTIME_REBUILD_MARKER_KEY,
        defaults={"value": json.dumps(payload, ensure_ascii=False)},
    )
    Setting.objects.update_or_create(
        key=RUNTIME_VERSION_KEY,
        defaults={"value": json.dumps(payload, ensure_ascii=False)},
    )


def invalidate_extension_frontend_assets(
    reason: str,
    *,
    extension_id: str = "",
    include_published: bool = False,
) -> dict:
    from apps.core.extensions.frontend_compiler import recompile_extension_frontend_assets
    from apps.core.extensions.manager import get_extension_manager

    manager = get_extension_manager()
    manager.load(force=True)
    extensions = [
        extension
        for extension in manager.get_extensions()
        if extension.runtime.installed and extension.runtime.enabled
    ]
    result = recompile_extension_frontend_assets(
        extensions,
        run_build=False,
        clear_marker=False,
        publish_dist=False,
    ).to_dict()
    if include_published:
        import shutil

        from apps.core.extensions.frontend_compiler import get_published_frontend_root

        published_root = get_published_frontend_root()
        removed = False
        if published_root.exists():
            shutil.rmtree(published_root)
            removed = True
        result["published"] = {
            "status": "ok",
            "status_label": "已清理" if removed else "无需清理",
            "removed": removed,
            "target": str(published_root),
        }
    mark_extension_runtime_requires_rebuild(reason, extension_id=extension_id)
    return result


def clear_extension_runtime_rebuild_marker() -> None:
    from apps.core.models import Setting

    Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).delete()


def rebuild_extension_runtime_state() -> None:
    reset_extension_runtime_state()
    rebuild_runtime_urlconf()
    clear_extension_runtime_rebuild_marker()
    mark_extension_runtime_version_seen()


def mark_extension_runtime_version_seen(version: str | None = None) -> None:
    global _runtime_version_seen

    _runtime_version_seen = str(version if version is not None else get_extension_runtime_version())


def reset_extension_runtime_version_seen() -> None:
    global _runtime_version_seen
    global _runtime_version_last_checked_at

    _runtime_version_seen = ""
    _runtime_version_last_checked_at = 0.0


def get_extension_runtime_version() -> str:
    from apps.core.models import Setting

    setting = Setting.objects.filter(key=RUNTIME_VERSION_KEY).only("value").first()
    if setting is None:
        return ""
    return str(setting.value or "")


def sync_extension_runtime_state_if_stale(*, force: bool = False) -> bool:
    global _runtime_version_last_checked_at

    now = time.monotonic()
    if (
        not force
        and _runtime_version_seen
        and now - _runtime_version_last_checked_at < _runtime_version_check_interval_seconds
    ):
        return False

    _runtime_version_last_checked_at = now
    try:
        version = get_extension_runtime_version()
    except (OperationalError, ProgrammingError, RuntimeError):
        return False

    if version == _runtime_version_seen:
        return False

    rebuild_extension_runtime_state()
    mark_extension_runtime_version_seen(version)
    return True


def rebuild_runtime_urlconf() -> None:
    import importlib

    clear_url_caches()
    try:
        urlconf = importlib.import_module(settings.ROOT_URLCONF)
    except Exception:
        return

    rebuild = getattr(urlconf, "rebuild_api_urlpatterns", None)
    if callable(rebuild):
        rebuild()
        clear_url_caches()


def reset_extension_runtime_state() -> None:
    from apps.core.domain_events import get_forum_event_bus
    from apps.core.extensions.bootstrap import clear_bootstrapped_extension_application
    from apps.core.extensions.bootstrap_state import reset_extension_application_bootstrap_state
    from apps.core.extensions.formatter_service import clear_extension_formatter_cache
    from apps.core.extensions import frontend_runtime_service
    from apps.core.extensions.locale_service import clear_extension_locale_cache
    from apps.core.extensions.manager import get_extension_manager
    from apps.core.extensions.template_loader import clear_extension_template_caches
    from apps.core.extensions.runtime_event_listeners import (
        bootstrap_extension_runtime_event_listeners,
        reset_extension_runtime_event_listener_bootstrap,
    )
    from apps.core.extensions.signal_bootstrap import (
        bootstrap_extension_signal_proxies,
        reset_extension_signal_proxy_bootstrap,
    )
    from apps.core.extensions.signal_runtime import disconnect_runtime_signal_receivers
    from apps.core import forum_event_listeners
    from apps.core.forum_runtime import clear_realtime_included_enrichers
    from apps.core.forum_registry import get_forum_registry
    from apps.core.resource_registry import get_resource_registry
    from apps.core.settings_service import clear_runtime_setting_caches

    frontend_runtime_service._frontend_runtime_catalog = {}
    frontend_runtime_service._frontend_runtime_bootstrapped = False
    clear_extension_formatter_cache()
    clear_extension_locale_cache()
    clear_extension_template_caches()
    disconnect_runtime_signal_receivers()
    reset_extension_signal_proxy_bootstrap()
    bootstrap_extension_signal_proxies()

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
