from __future__ import annotations

import logging

from apps.core.extension_settings_service import get_extension_settings, serialize_extension_settings_schema, save_extension_settings

logger = logging.getLogger(__name__)
from apps.core.extensions.admin_assets import (
    serialize_extension_frontend_asset_state,
    serialize_extension_frontend_asset_state_for_extension,
)
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest
from apps.core.extensions.frontend_runtime_service import build_frontend_document_payload

def _build_extension_frontend_routes(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "path": route.path,
            "name": route.name,
            "component": route.component,
            "frontend": route.frontend,
            "title": route.title,
            "description": route.description,
            "requires_auth": route.requires_auth,
            "order": route.order,
            "removed": route.removed,
            "module_id": route.module_id,
        }
        for route in getattr(runtime_view, "frontend_routes", ()) or ()
    ]

def _build_extension_frontend_document(runtime_record=None) -> dict:
    if runtime_record is None:
        return {
            "preloads": [],
            "document_attributes": [],
            "head_tags": [],
            "theme_variables": [],
            "title_driver": "",
            "content_callbacks": [],
        }

    try:
        settings_values = get_extension_settings(runtime_record.extension_id)
    except Exception:
        logger.warning(
            "Failed to load extension settings for frontend document: %s",
            runtime_record.extension_id,
            exc_info=True,
        )
        settings_values = {}
    return build_frontend_document_payload(runtime_record, settings_values=settings_values)

def _resolve_extension_frontend_admin_entry(extension, runtime_record=None) -> str:
    host = get_extension_host()
    if host is not None:
        frontend = host.get_frontend_extension(extension.id)
        if frontend is not None and str(frontend.admin_entry or "").strip():
            return str(frontend.admin_entry or "").strip()
    if runtime_record is not None and str(runtime_record.frontend_admin_entry or "").strip():
        return str(runtime_record.frontend_admin_entry or "").strip()
    return extension.frontend_admin_entry

def _resolve_extension_frontend_forum_entry(extension, runtime_record=None) -> str:
    host = get_extension_host()
    if host is not None:
        frontend = host.get_frontend_extension(extension.id)
        if frontend is not None and str(frontend.forum_entry or "").strip():
            return str(frontend.forum_entry or "").strip()
    if runtime_record is not None and str(runtime_record.frontend_forum_entry or "").strip():
        return str(runtime_record.frontend_forum_entry or "").strip()
    return extension.frontend_forum_entry

def _resolve_extension_frontend_outputs(extension_id: str, *, frontend_output_manifest: dict | None = None) -> dict:
    output_manifest = frontend_output_manifest or inspect_extension_frontend_output_manifest()
    payload = dict(dict(output_manifest.get("extensions") or {}).get(str(extension_id or "").strip()) or {})
    return dict(payload.get("outputs") or {})

def _resolve_extension_settings_pages(extension, runtime_record=None) -> tuple[str, ...]:
    host = get_extension_host()
    if host is not None:
        frontend = host.get_frontend_extension(extension.id)
        if frontend is not None and frontend.settings_pages:
            return tuple(frontend.settings_pages)
    if runtime_record is not None and runtime_record.settings_pages:
        return tuple(runtime_record.settings_pages)
    return tuple(extension.settings_pages)

def _resolve_extension_permissions_pages(extension, runtime_record=None) -> tuple[str, ...]:
    host = get_extension_host()
    if host is not None:
        frontend = host.get_frontend_extension(extension.id)
        if frontend is not None and frontend.permissions_pages:
            return tuple(frontend.permissions_pages)
    if runtime_record is not None and runtime_record.permissions_pages:
        return tuple(runtime_record.permissions_pages)
    return tuple(extension.permissions_pages)

def _resolve_extension_operations_pages(extension, runtime_record=None) -> tuple[str, ...]:
    host = get_extension_host()
    if host is not None:
        frontend = host.get_frontend_extension(extension.id)
        if frontend is not None and frontend.operations_pages:
            return tuple(frontend.operations_pages)
    if runtime_record is not None and runtime_record.operations_pages:
        return tuple(runtime_record.operations_pages)
    return tuple(extension.operations_pages)

def _build_runtime_surface_view(
    extension,
    runtime_record,
    *,
    frontend_admin_entry: str,
    frontend_forum_entry: str,
    settings_pages: tuple[str, ...],
    permissions_pages: tuple[str, ...],
    operations_pages: tuple[str, ...],
):
    return type("_RuntimeSurfaceView", (), {
        "frontend_admin_entry": frontend_admin_entry,
        "frontend_forum_entry": frontend_forum_entry,
        "settings_pages": settings_pages,
        "permissions_pages": permissions_pages,
        "operations_pages": operations_pages,
        "settings_schema": tuple(getattr(runtime_record, "settings_schema", ()) or extension.settings_schema),
        "admin_actions": tuple(getattr(runtime_record, "admin_actions", ()) or extension.admin_actions),
        "runtime_actions": tuple(getattr(runtime_record, "runtime_actions", ()) or extension.manifest_runtime_actions),
    })()

def _serialize_extension_runtime_rebuild_state():
    import json

    from apps.core.models import Setting
    from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY, RUNTIME_VERSION_KEY

    setting = Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).first()
    version_setting = Setting.objects.filter(key=RUNTIME_VERSION_KEY).first()
    enabled_order = Setting.objects.filter(key="extensions_enabled_order").first()
    raw_order = str(getattr(enabled_order, "value", "") or "")
    runtime_version = str(getattr(version_setting, "value", "") or "")
    if setting is None:
        return {
            "required": False,
            "reason": "",
            "extension_id": "",
            "urlconf": "",
            "version": runtime_version,
            "stamp": f"{raw_order}:{runtime_version}",
            "frontend_assets": serialize_extension_frontend_asset_state(),
        }
    try:
        payload = json.loads(setting.value or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "required": True,
        "reason": str(payload.get("reason") or ""),
        "extension_id": str(payload.get("extension_id") or ""),
        "urlconf": str(payload.get("urlconf") or ""),
        "version": runtime_version or str(payload.get("version") or ""),
        "stamp": f"{raw_order}:{runtime_version or setting.value or ''}",
        "frontend_assets": serialize_extension_frontend_asset_state(),
    }

def _serialize_extension_frontend_asset_state_for_extension(extension):
    return serialize_extension_frontend_asset_state_for_extension(
        extension,
        runtime_rebuild_state=_serialize_extension_runtime_rebuild_state(),
        resolve_admin_entry=_resolve_extension_frontend_admin_entry,
        resolve_forum_entry=_resolve_extension_frontend_forum_entry,
    )
