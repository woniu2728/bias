import logging

from ninja import Body, Router
from pathlib import Path

from apps.core.api_errors import api_error
from apps.core.admin_auth import require_staff
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.registry import get_extension_registry
from apps.core.extensions.validation import (
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    resolve_admin_surface_implementation,
    validate_extension_manifests_with_available_ids,
)
from apps.core.extension_diagnostics import (
    classify_extension_diagnostics,
    summarize_extension_delivery,
    summarize_extension_diagnostics,
)
from apps.core.extension_service import ExtensionService
from apps.core.extension_settings_service import get_extension_settings, serialize_extension_settings_schema, save_extension_settings
from apps.core.extension_django_apps import normalize_extension_django_app_label
from apps.core.extensions.product import get_extension_protected_reason, is_extension_protected, is_product_visible_extension
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.frontend_runtime_service import build_frontend_document_payload
from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest
from apps.core.extensions.admin_assets import (
    serialize_extension_frontend_asset_state,
    serialize_extension_frontend_asset_state_for_extension,
)
from apps.core.extensions.admin_actions import (
    build_default_extension_admin_actions,
    serialize_extension_admin_actions,
)
from apps.core.extension_validation_context import resolve_available_extension_ids_for_validation
from apps.core.extensions.admin_manifest import (
    build_extension_author_names as _build_extension_author_names,
    build_extension_links as _build_extension_links,
    build_extension_readme as _build_extension_readme,
    manifest_attr as _manifest_attr,
    manifest_nested_attr as _manifest_nested_attr,
    manifest_nested_value as _manifest_nested_value,
    manifest_sequence as _manifest_sequence,
)
from apps.core.extensions.recovery import (
    get_extension_bisect_state,
    get_extension_safe_mode_extension_ids,
    is_extension_safe_mode_enabled,
    serialize_extension_recovery_state,
)
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.forum_registry import get_forum_registry
from apps.core.extensions.runtime import get_runtime_resource_registry


logger = logging.getLogger(__name__)


def _serialize_admin_extensions_payload(extensions, *, summary: bool = False):
    frontend_output_manifest = inspect_extension_frontend_output_manifest()
    payload = [
        _serialize_admin_extension_summary(
            extension,
            frontend_output_manifest=frontend_output_manifest,
        ) if summary else _serialize_admin_extension(
            extension,
            frontend_output_manifest=frontend_output_manifest,
        )
        for extension in extensions
    ]
    diagnostics_summary = summarize_extension_diagnostics(payload)
    delivery_summary = summarize_extension_delivery(payload)

    return {
        "summary": {
            "extension_count": len(payload),
            "enabled_count": sum(1 for item in payload if item["enabled"]),
            "healthy_count": sum(1 for item in payload if item["healthy"]),
            "filesystem_count": sum(1 for item in payload if item["source"] == "filesystem"),
            "blocking_count": diagnostics_summary["blocking_count"],
            "warning_count": diagnostics_summary["warning_count"],
            "attention_count": diagnostics_summary["attention_count"],
            "asset_count": delivery_summary["asset_count"],
            "frontend_bundle_count": delivery_summary["frontend_bundle_count"],
            "migration_bundle_count": delivery_summary["migration_bundle_count"],
            "locale_bundle_count": delivery_summary["locale_bundle_count"],
            "signed_extension_count": delivery_summary["signed_extension_count"],
            "product_visible_count": sum(1 for item in payload if item["product_visible"]),
        },
        "runtime": {
            **_serialize_extension_runtime_rebuild_state(),
            "recovery": serialize_extension_recovery_state(),
            "package_lock": ExtensionService.inspect_extension_packages(),
        },
        "extensions": payload,
    }


def serialize_admin_extensions_payload(extensions, *, summary: bool = False):
    return _serialize_admin_extensions_payload(extensions, summary=summary)


def _serialize_admin_extension_action_payload(extension):
    frontend_output_manifest = inspect_extension_frontend_output_manifest()
    return {
        "runtime": {
            **_serialize_extension_runtime_rebuild_state(),
            "recovery": serialize_extension_recovery_state(),
        },
        "extension": _serialize_admin_extension(extension, frontend_output_manifest=frontend_output_manifest),
    }


def _serialize_admin_extension_summary(extension, *, frontend_output_manifest: dict | None = None):
    runtime_view = _resolve_extension_runtime_record(extension)
    settings_pages = _resolve_extension_settings_pages(extension, runtime_view)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_view)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_view)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_view)
    frontend_outputs = _resolve_extension_frontend_outputs(extension.id, frontend_output_manifest=frontend_output_manifest)
    frontend_routes = _build_extension_frontend_routes(runtime_view)

    return {
        "id": extension.id,
        "name": extension.name,
        "version": extension.version,
        "description": extension.description,
        "icon": _manifest_attr(extension, "icon", "fas fa-puzzle-piece"),
        "category": _manifest_attr(extension, "category", "feature"),
        "frontend_admin_entry": frontend_admin_entry,
        "frontend_outputs": frontend_outputs,
        "frontend_routes": frontend_routes,
        "installed": extension.runtime.installed,
        "enabled": extension.runtime.enabled,
        "booted": extension.runtime.booted,
        "healthy": extension.runtime.healthy,
        "runtime_status": {
            "key": extension.runtime.status_key,
            "label": extension.runtime.status_label,
        },
        "source": extension.source,
        "product_visible": is_product_visible_extension(extension),
        "protected": is_extension_protected(extension),
        "module_ids": list(extension.module_ids),
        "admin_pages": list(extension.admin_pages),
        "settings_pages": list(settings_pages),
        "permissions_pages": list(permissions_pages),
        "operations_pages": list(operations_pages),
        "action_links": {
            "detail_page": f"/admin/extensions/{extension.id}",
            "settings_page": next(iter(settings_pages), ""),
            "permissions_page": next(iter(permissions_pages), ""),
            "operations_page": next(iter(operations_pages), ""),
            "documentation_url": _manifest_attr(extension, "documentation_url"),
        },
        "diagnostics": [],
        "delivery_checks": [],
        "delivery_assets": [],
        "runtime_issues": list(extension.runtime.runtime_issues),
    }


def _serialize_admin_extension(
    extension,
    include_permission_details: bool = False,
    *,
    frontend_output_manifest: dict | None = None,
):
    runtime_view = _resolve_extension_runtime_record(extension)
    detail_page = f"/admin/extensions/{extension.id}"
    settings_pages = _resolve_extension_settings_pages(extension, runtime_view)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_view)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_view)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_view)
    frontend_forum_entry = _resolve_extension_frontend_forum_entry(extension, runtime_view)
    frontend_outputs = _resolve_extension_frontend_outputs(extension.id, frontend_output_manifest=frontend_output_manifest)
    frontend_routes = _build_extension_frontend_routes(runtime_view)
    settings_page = next(iter(settings_pages), "")
    permissions_page = next(iter(permissions_pages), "")
    operations_page = next(iter(operations_pages), "")
    admin_actions = _serialize_extension_admin_actions(extension, runtime_record=runtime_view)
    permission_sections = _build_extension_permission_sections(extension) if include_permission_details else []
    permissions = _flatten_extension_permissions(permission_sections)
    permission_summary = _build_extension_permission_summary(permission_sections)
    permission_modules = _build_extension_permission_modules(permission_sections)
    admin_page_details = _build_extension_admin_page_details(extension)
    notification_types = _build_extension_notification_types(extension)
    user_preferences = _build_extension_user_preferences(extension)
    event_listeners = _build_extension_event_listeners(extension, runtime_view)
    realtime_broadcasts = _build_extension_realtime_broadcasts(runtime_view)
    post_lifecycle = _build_extension_post_lifecycle(extension, runtime_view)
    post_types = _build_extension_post_types(extension)
    search_filters = _build_extension_search_filters(extension)
    discussion_sorts = _build_extension_discussion_sorts(extension)
    discussion_list_filters = _build_extension_discussion_list_filters(extension)
    resource_definitions = _build_extension_resource_definitions(extension)
    resource_relationships = _build_extension_resource_relationships(extension)
    resource_fields = _build_extension_resource_fields(extension)
    resource_endpoints = _build_extension_resource_endpoints(extension)
    resource_sorts = _build_extension_resource_sorts(extension)
    resource_filters = _build_extension_resource_filters(extension)
    model_definitions = _build_extension_model_definitions(runtime_view)
    owned_models = _build_extension_owned_models(runtime_view, extension=extension)
    model_ownership_audit = _build_extension_model_ownership_audit(runtime_view, extension=extension)
    model_relations = _build_extension_model_relations(runtime_view)
    model_visibility = _build_extension_model_visibility(runtime_view)
    search_drivers = _build_extension_search_drivers(runtime_view)
    language_packs = _build_extension_language_packs(extension)
    delivery_assets = _build_extension_delivery_assets(extension)
    capability_summary = _build_extension_capability_summary(
        notification_types=notification_types,
        user_preferences=user_preferences,
        event_listeners=event_listeners,
        realtime_broadcasts=realtime_broadcasts,
        post_lifecycle=post_lifecycle,
        post_types=post_types,
        search_filters=search_filters,
        discussion_sorts=discussion_sorts,
        discussion_list_filters=discussion_list_filters,
        resource_definitions=resource_definitions,
        resource_relationships=resource_relationships,
        resource_fields=resource_fields,
        resource_endpoints=resource_endpoints,
        resource_sorts=resource_sorts,
        resource_filters=resource_filters,
        owned_models=owned_models,
        model_ownership_audit=model_ownership_audit,
        model_relations=model_relations,
        language_packs=language_packs,
    )

    settings_schema = serialize_extension_settings_schema(extension.id)

    payload = {
        "id": extension.id,
        "name": extension.name,
        "version": extension.version,
        "description": extension.description,
        "icon": _manifest_attr(extension, "icon", "fas fa-puzzle-piece"),
        "category": _manifest_attr(extension, "category", "feature"),
        "authors": _build_extension_author_names(extension),
        "homepage": _manifest_attr(extension, "homepage"),
        "documentation_url": _manifest_attr(extension, "documentation_url"),
        "links": _build_extension_links(extension),
        "readme": _build_extension_readme(extension),
        "dependencies": _manifest_sequence(extension, "dependencies"),
        "optional_dependencies": _manifest_sequence(extension, "optional_dependencies"),
        "conflicts": _manifest_sequence(extension, "conflicts"),
        "provides": _manifest_sequence(extension, "provides"),
        "backend_entry": _manifest_attr(extension, "backend_entry"),
        "django_app_config": _manifest_attr(extension, "django_app_config"),
        "django_app_label": _manifest_attr(extension, "django_app_label") or normalize_extension_django_app_label(extension.id),
        "frontend_admin_entry": frontend_admin_entry,
        "frontend_forum_entry": frontend_forum_entry,
        "frontend_outputs": frontend_outputs,
        "frontend_routes": frontend_routes,
        "settings_pages": list(settings_pages),
        "permissions_pages": list(permissions_pages),
        "operations_pages": list(operations_pages),
        "operations_profile": dict(getattr(extension.manifest, "operations_profile", {}) or {}),
        "settings_schema": settings_schema,
        "settings_values": get_extension_settings(extension.id) if settings_schema else {},
        "compatibility": {
            "bias_version": _manifest_nested_attr(extension, "compatibility", "bias_version"),
            "api_version": _manifest_nested_attr(extension, "compatibility", "api_version", "1.0"),
            "api_stability": _manifest_nested_attr(extension, "compatibility", "api_stability", "experimental"),
            "api_stability_label": _resolve_api_stability_label(extension),
            "breaking_change_policy": _manifest_nested_attr(extension, "compatibility", "breaking_change_policy"),
        },
        "security": {
            "policy_url": _manifest_nested_attr(extension, "security", "policy_url"),
            "support_email": _manifest_nested_attr(extension, "security", "support_email"),
            "capabilities_notice": _manifest_nested_attr(extension, "security", "capabilities_notice"),
        },
        "distribution": {
            "channel": _manifest_nested_attr(extension, "distribution", "channel", "private"),
            "channel_label": _resolve_distribution_channel_label(extension),
            "signing_key_id": _manifest_nested_attr(extension, "distribution", "signing_key_id"),
            "signature_url": _manifest_nested_attr(extension, "distribution", "signature_url"),
            "abandoned": bool(_manifest_nested_value(extension, "distribution", "abandoned", False)),
            "replacement": _manifest_nested_attr(extension, "distribution", "replacement"),
        },
        "installed": extension.runtime.installed,
        "enabled": extension.runtime.enabled,
        "booted": extension.runtime.booted,
        "healthy": extension.runtime.healthy,
        "runtime_status": {
            "key": extension.runtime.status_key,
            "label": extension.runtime.status_label,
        },
        "recovery_status": _serialize_extension_recovery_status(extension),
        "migration_state": extension.runtime.migration_state,
        "migration_label": extension.runtime.migration_label,
        "migration_execution": _serialize_extension_migration_execution(extension),
        "migration_plan": _serialize_extension_migration_plan(extension),
        "dependency_state": extension.runtime.dependency_state,
        "dependency_state_label": extension.runtime.dependency_state_label,
        "runtime_issues": list(extension.runtime.runtime_issues),
        "delivery_checks": [
            {
                "key": check.key,
                "label": check.label,
                "status": check.status,
                "status_label": check.status_label,
                "message": check.message,
                "path": check.path,
                "optional": check.optional,
            }
            for check in extension.runtime.delivery_checks
        ],
        "uninstall_warnings": list(extension.runtime.uninstall_warnings),
        "runtime_actions": [
            {
                "key": action.key,
                "label": action.label,
                "action": action.action,
                "tone": action.tone,
                "confirm_title": action.confirm_title,
                "confirm_message": action.confirm_message,
                "confirm_text": action.confirm_text,
                "success_message": action.success_message,
                "requires_enabled": action.requires_enabled,
                "requires_installed": action.requires_installed,
                "order": action.order,
            }
            for action in extension.runtime.runtime_actions
        ],
        "backend_hooks": _serialize_extension_backend_hooks(extension),
        "source": extension.source,
        "product_visible": is_product_visible_extension(extension),
        "protected": is_extension_protected(extension),
        "protected_reason": get_extension_protected_reason(extension),
        "module_ids": list(extension.module_ids),
        "admin_pages": list(extension.admin_pages),
        "admin_page_details": admin_page_details,
        "settings_groups": list(extension.settings_groups),
        "admin_actions": admin_actions,
        "permission_summary": permission_summary,
        "permission_modules": permission_modules,
        "permissions": permissions,
        "permission_sections": permission_sections,
        "notification_types": notification_types,
        "user_preferences": user_preferences,
        "event_listeners": event_listeners,
        "realtime_broadcasts": realtime_broadcasts,
        "post_lifecycle": post_lifecycle,
        "post_types": post_types,
        "search_filters": search_filters,
        "discussion_sorts": discussion_sorts,
        "discussion_list_filters": discussion_list_filters,
        "resource_definitions": resource_definitions,
        "resource_relationships": resource_relationships,
        "resource_fields": resource_fields,
        "resource_endpoints": resource_endpoints,
        "resource_sorts": resource_sorts,
        "resource_filters": resource_filters,
        "model_definitions": model_definitions,
        "owned_models": owned_models,
        "model_ownership_audit": model_ownership_audit,
        "model_relations": model_relations,
        "model_visibility": model_visibility,
        "search_drivers": search_drivers,
        "language_packs": language_packs,
        "delivery_assets": delivery_assets,
        "frontend_asset_state": _serialize_extension_frontend_asset_state_for_extension(extension),
        "capability_summary": capability_summary,
        "action_links": {
            "detail_page": detail_page,
            "settings_page": settings_page,
            "permissions_page": permissions_page,
            "operations_page": operations_page,
            "documentation_url": _manifest_attr(extension, "documentation_url"),
        },
        "lifecycle": {
            "registration_mode": extension.lifecycle.registration_mode,
            "registration_mode_label": extension.lifecycle.registration_mode_label,
            "readiness_probe": extension.lifecycle.readiness_probe,
            "supports_disable": extension.lifecycle.supports_disable,
            "supports_teardown": extension.lifecycle.supports_teardown,
            "runtime_phases": list(getattr(runtime_view, "lifecycle_phase_keys", ()) or ()),
            "runtime_extenders": list(getattr(runtime_view, "extender_keys", ()) or ()),
            "runtime_lifecycle_extenders": list(getattr(runtime_view, "lifecycle_extender_keys", ()) or ()),
            "runtime_rebuild": _serialize_extension_runtime_rebuild_state(),
            "phases": [
                {
                    "key": phase.key,
                    "label": phase.label,
                    "description": phase.description,
                    "optional": phase.optional,
                }
                for phase in extension.lifecycle.phases
            ],
        },
        "debug_info": _build_extension_debug_info(extension),
    }
    payload["diagnostics"] = classify_extension_diagnostics(payload)
    return payload


def serialize_admin_extension(extension, *, include_permission_details: bool = False):
    return _serialize_admin_extension(
        extension,
        include_permission_details=include_permission_details,
    )


def _resolve_extension_runtime_record(extension):
    host = get_extension_host()
    if host is None:
        return None
    return host.get_runtime_view(extension.id)


def _serialize_extension_recovery_status(extension):
    safe_mode = is_extension_safe_mode_enabled()
    safe_mode_extensions = get_extension_safe_mode_extension_ids()
    bisect = get_extension_bisect_state()
    extension_id = str(extension.id or "").strip()
    return {
        "safe_mode": safe_mode,
        "safe_mode_allowed": (not safe_mode)
        or extension_id in safe_mode_extensions,
        "bisect_active": bool(bisect.get("active")),
        "bisect_current": extension_id in set(bisect.get("current") or []),
        "bisect_candidate": extension_id in set(bisect.get("ids") or []),
        "bisect_culprit": extension_id == str(bisect.get("culprit") or "").strip(),
    }


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


def _build_extension_admin_page_details(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    pages = []
    seen_paths = set()
    for page in get_forum_registry().get_admin_pages():
        if page.module_id not in module_ids:
            continue
        if page.path in seen_paths:
            continue
        seen_paths.add(page.path)
        pages.append({
            "path": page.path,
            "label": page.label,
            "icon": page.icon,
            "module_id": page.module_id,
            "nav_section": page.nav_section,
            "description": page.description,
            "settings_group": page.settings_group,
        })
    return pages


def _build_extension_permission_sections(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    sections = []
    for section in get_forum_registry().get_permission_sections():
        permissions = [
            permission
            for permission in section.get("permissions", [])
            if permission.get("module_id") in module_ids
        ]
        if not permissions:
            continue
        sections.append({
            "name": section.get("name", ""),
            "label": section.get("label", ""),
            "permission_count": len(permissions),
            "permissions": permissions,
        })
    return sections


def _build_extension_permission_summary(sections):
    permission_count = sum(len(section["permissions"]) for section in sections)
    module_ids = {
        permission["module_id"]
        for section in sections
        for permission in section["permissions"]
    }
    return {
        "section_count": len(sections),
        "permission_count": permission_count,
        "module_count": len(module_ids),
    }


def _flatten_extension_permissions(sections):
    return [
        permission
        for section in sections
        for permission in section.get("permissions", [])
    ]


def _build_extension_permission_modules(sections):
    counts = {}
    for section in sections:
        for permission in section["permissions"]:
            module_id = permission["module_id"]
            counts[module_id] = counts.get(module_id, 0) + 1
    return [
        {
            "module_id": module_id,
            "permission_count": counts[module_id],
        }
        for module_id in sorted(counts.keys())
    ]


def _build_extension_notification_types(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "navigation_scope": item.navigation_scope,
            "preference_key": item.preference_key,
            "preference_label": item.preference_label,
        }
        for item in get_forum_registry().get_notification_types()
        if item.module_id in module_ids
    ]


def _build_extension_user_preferences(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "key": item.key,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "category": item.category,
            "default_value": item.default_value,
        }
        for item in get_forum_registry().get_user_preferences()
        if item.module_id in module_ids
    ]


def _build_extension_event_listeners(extension, runtime_record=None):
    module_ids = set(extension.module_ids or ())
    listeners = []
    seen = set()

    if runtime_record is not None:
        for item in getattr(runtime_record, "event_listeners", ()) or ():
            event_type = getattr(item, "event_type", None)
            handler = getattr(item, "handler", None)
            payload = {
                "event": getattr(event_type, "__name__", str(event_type or "")),
                "listener": getattr(handler, "__qualname__", getattr(handler, "__name__", str(handler or ""))),
                "module_id": extension.id,
                "description": getattr(item, "description", ""),
                "source": "runtime",
            }
            key = (payload["event"], payload["listener"], payload["module_id"])
            if key not in seen:
                seen.add(key)
                listeners.append(payload)

    if not module_ids:
        return listeners

    for item in get_forum_registry().get_event_listeners():
        if item.module_id not in module_ids:
            continue
        payload = {
            "event": item.event,
            "listener": item.listener,
            "module_id": item.module_id,
            "description": item.description,
            "source": "registry",
        }
        key = (payload["event"], payload["listener"], payload["module_id"])
        if key not in seen:
            seen.add(key)
            listeners.append(payload)
    return listeners


def _build_extension_realtime_broadcasts(runtime_record=None):
    if runtime_record is None:
        return []

    broadcasts = []
    for item in getattr(runtime_record, "realtime_discussion_broadcasts", ()) or ():
        event_type = getattr(item, "event_type", None)
        broadcasts.append({
            "event": getattr(event_type, "__name__", str(event_type or "")),
            "event_name": _serialize_callable_or_value(getattr(item, "event_name", "")),
            "channel": "discussion",
            "module_id": getattr(runtime_record, "extension_id", ""),
            "include_discussion": bool(getattr(item, "include_discussion", False)),
            "include_post": bool(getattr(item, "include_post", False)),
            "description": getattr(item, "description", ""),
            "source": "runtime",
        })
    return broadcasts


def _serialize_callable_or_value(value):
    if callable(value):
        return getattr(value, "__qualname__", getattr(value, "__name__", str(value or "")))
    return str(value or "")


def _build_extension_post_lifecycle(extension, runtime_record=None):
    if runtime_record is None:
        return []

    handlers = []
    for item in getattr(runtime_record, "post_lifecycle", ()) or ():
        phases = [
            phase
            for phase in ("apply_created", "apply_updated", "apply_approved", "apply_hidden", "prepare_delete", "apply_deleted")
            if callable(getattr(item, phase, None))
        ]
        handlers.append({
            "key": getattr(item, "key", ""),
            "module_id": extension.id,
            "phases": phases,
            "description": getattr(item, "description", ""),
            "source": "runtime",
        })
    return handlers


def _build_extension_post_types(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "is_stream_visible": item.is_stream_visible,
            "counts_toward_discussion": item.counts_toward_discussion,
            "counts_toward_user": item.counts_toward_user,
            "searchable": item.searchable,
        }
        for item in get_forum_registry().get_post_types()
        if item.module_id in module_ids
    ]


def _build_extension_search_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "target": item.target,
            "syntax": item.syntax,
            "description": item.description,
        }
        for item in get_forum_registry().get_search_filters()
        if item.module_id in module_ids
    ]


def _build_extension_discussion_sorts(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "toolbar_visible": item.toolbar_visible,
        }
        for item in get_forum_registry().get_discussion_sorts()
        if item.module_id in module_ids
    ]


def _build_extension_discussion_list_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "requires_authenticated_user": item.requires_authenticated_user,
            "sidebar_visible": item.sidebar_visible,
            "route_path": item.route_path,
        }
        for item in get_forum_registry().get_discussion_list_filters()
        if item.module_id in module_ids
    ]


def _build_extension_resource_definitions(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "module_id": item.module_id,
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_resources()
        if item.module_id in module_ids
    ]


def _build_extension_resource_relationships(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "relationship": item.relationship,
            "module_id": item.module_id,
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_relationships()
        if item.module_id in module_ids
    ]


def _build_extension_resource_endpoints(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "endpoint": item.endpoint,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "mutate"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_endpoints()
        if item.module_id in module_ids
    ]


def _build_extension_resource_sorts(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "sort": item.sort,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "add"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_sorts()
        if item.module_id in module_ids
    ]


def _build_extension_resource_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "filter": item.filter,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "add"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_filters()
        if item.module_id in module_ids
    ]


def _build_extension_resource_fields(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    fields = [
        {
            "resource": item.resource,
            "field": item.field,
            "module_id": item.module_id,
            "operation": "add",
            "anchor": "",
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_fields()
        if item.module_id in module_ids
    ]
    fields.extend([
        {
            "resource": item.resource,
            "field": item.field,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "mutate"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_field_mutators()
        if item.module_id in module_ids
    ])
    return fields


def _build_extension_language_packs(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "native_label": item.native_label,
            "module_id": item.module_id,
            "description": item.description,
            "is_default": item.is_default,
        }
        for item in get_forum_registry().get_language_packs()
        if item.module_id in module_ids
    ]


def _build_extension_model_definitions(runtime_view):
    if runtime_view is None:
        return []
    definitions = [
        {
            "model": _model_name(item.model),
            "key": item.key,
            "kind": item.kind,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_definitions", ()) or ()
    ]
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.name,
            "kind": f"relation:{item.relation_type}",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_relations", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.attribute,
            "kind": "cast",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_casts", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.attribute,
            "kind": "default",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_defaults", ()) or ()
    ])
    definitions.extend([
        {
            "model": _model_name(item.model),
            "key": item.identifier,
            "kind": "model-url:slug",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_slug_drivers", ()) or ()
    ])
    return definitions


def _build_extension_owned_models(runtime_view, *, extension=None):
    if runtime_view is None:
        return []
    items = []
    target_app_label = _extension_app_label(runtime_view.extension_id, extension=extension)
    target_app_label_source = _extension_app_label_source(extension)
    for item in getattr(runtime_view, "model_definitions", ()) or ():
        if item.kind != "owner":
            continue
        model = item.model
        current_app_label = _model_app_label(model)
        package_migration_required = _model_package_migration_required(model, runtime_view.extension_id)
        app_label_migration_required = _model_app_label_migration_required(
            model,
            runtime_view.extension_id,
            extension=extension,
        )
        items.append({
            "module_id": runtime_view.extension_id,
            "model": _model_name(model),
            "model_label": _model_label(model),
            "model_module": _model_module(model),
            "app_label": current_app_label,
            "current_app_label": current_app_label,
            "target_app_label": target_app_label,
            "target_app_label_source": target_app_label_source,
            "db_table": _model_db_table(model),
            "storage_origin": _model_storage_origin(model, runtime_view.extension_id),
            "package_migration_required": package_migration_required,
            "app_label_migration_required": app_label_migration_required,
            "migration_risk": _model_migration_risk(
                package_migration_required=package_migration_required,
                app_label_migration_required=app_label_migration_required,
            ),
            "recommended_steps": _model_migration_recommended_steps(
                package_migration_required=package_migration_required,
                app_label_migration_required=app_label_migration_required,
            ),
            "key": item.key,
            "description": item.description,
        })
    return items


def _build_extension_model_ownership_audit(runtime_view, *, extension=None):
    if runtime_view is None:
        return {
            "owned_model_count": 0,
            "extension_native_count": 0,
            "django_app_count": 0,
            "package_migration_required_count": 0,
            "app_label_migration_required_count": 0,
            "target_app_label": "",
            "target_app_label_source": "",
            "items": [],
        }

    items = _build_extension_owned_models(runtime_view, extension=extension)
    return {
        "owned_model_count": len(items),
        "extension_native_count": sum(1 for item in items if item["storage_origin"] == "extension"),
        "django_app_count": sum(1 for item in items if item["storage_origin"] == "django_app"),
        "package_migration_required_count": sum(1 for item in items if item["package_migration_required"]),
        "app_label_migration_required_count": sum(1 for item in items if item["app_label_migration_required"]),
        "target_app_label": _extension_app_label(runtime_view.extension_id, extension=extension),
        "target_app_label_source": _extension_app_label_source(extension),
        "app_label_migration_plan_required_count": sum(
            1
            for item in items
            if item["app_label_migration_required"] and item["target_app_label"]
        ),
        "app_label_migration_items": [
            _build_model_app_label_migration_item(item)
            for item in items
            if item["app_label_migration_required"]
        ],
        "items": items,
    }


def _build_extension_model_relations(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "module_id": runtime_view.extension_id,
            "model": _model_name(item.model),
            "name": item.name,
            "relation_type": item.relation_type,
            "related_model": _model_name(item.related_model),
            "foreign_key": item.foreign_key,
            "owner_key": item.owner_key,
            "inject_attribute": bool(getattr(item, "inject_attribute", True)),
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_relations", ()) or ()
    ]


def _build_extension_model_visibility(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "model": _model_name(item.model),
            "ability": item.ability,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_visibility", ()) or ()
    ]


def _resolve_display_model(model):
    from apps.core.extensions.model_references import resolve_model_reference

    return resolve_model_reference(model) or model


def _model_name(model) -> str:
    resolved_model = _resolve_display_model(model)
    return str(getattr(resolved_model, "__name__", "") or str(resolved_model))


def _model_label(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    label = str(getattr(meta, "label", "") or getattr(meta, "label_lower", "") or "").strip()
    if label:
        return label
    module = str(getattr(model, "__module__", "") or "").strip()
    name = str(getattr(model, "__name__", "") or getattr(model, "__qualname__", "") or "").strip()
    return ".".join(item for item in (module, name) if item) or str(model)


def _model_module(model) -> str:
    model = _resolve_display_model(model)
    return str(getattr(model, "__module__", "") or "").strip()


def _model_app_label(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    return str(getattr(meta, "app_label", "") or "").strip()


def _extension_app_label(extension_id: str, *, extension=None) -> str:
    manifest_label = str(getattr(getattr(extension, "manifest", None), "django_app_label", "") or "").strip()
    return normalize_extension_django_app_label(extension_id, manifest_label)


def _extension_app_label_source(extension=None) -> str:
    manifest_label = str(getattr(getattr(extension, "manifest", None), "django_app_label", "") or "").strip()
    return "manifest" if manifest_label else "extension_id"


def _model_db_table(model) -> str:
    model = _resolve_display_model(model)
    meta = getattr(model, "_meta", None)
    return str(getattr(meta, "db_table", "") or "").strip()


def _model_storage_origin(model, extension_id: str) -> str:
    module = _model_module(model)
    extension_module = f"extensions.{str(extension_id or '').replace('-', '_')}."
    if module.startswith(extension_module):
        return "extension"
    if module.startswith("extensions."):
        return "extension-other"
    if module.startswith("apps."):
        return "django_app"
    return "external"


def _model_package_migration_required(model, extension_id: str) -> bool:
    return _model_storage_origin(model, extension_id) == "django_app"


def _model_app_label_migration_required(model, extension_id: str, *, extension=None) -> bool:
    app_label = _model_app_label(model)
    expected = _extension_app_label(extension_id, extension=extension)
    return bool(app_label and expected and app_label != expected)


def _model_migration_risk(*, package_migration_required: bool, app_label_migration_required: bool) -> str:
    if app_label_migration_required:
        return "high"
    if package_migration_required:
        return "medium"
    return "none"


def _model_migration_recommended_steps(
    *,
    package_migration_required: bool,
    app_label_migration_required: bool,
) -> list[str]:
    steps = []
    if package_migration_required:
        steps.append("将模型定义迁入扩展 backend/models.py，并从核心 Django app model 文件移除实体定义。")
    if app_label_migration_required:
        steps.extend([
            "新增目标扩展 app label 的状态迁移，使用 SeparateDatabaseAndState 保留现有数据表。",
            "将模型 Meta.app_label 切换为目标扩展 app label，并明确 ContentType/Permission 迁移策略。",
            "运行 makemigrations --check、扩展安装迁移和卸载回滚测试，确认不会生成删表建表操作。",
        ])
    return steps


def _build_model_app_label_migration_item(item: dict) -> dict:
    return {
        "module_id": item.get("module_id") or "",
        "model": item.get("model") or "",
        "model_label": item.get("model_label") or "",
        "current_app_label": item.get("current_app_label") or item.get("app_label") or "",
        "target_app_label": item.get("target_app_label") or "",
        "db_table": item.get("db_table") or "",
        "migration_risk": item.get("migration_risk") or "high",
        "recommended_steps": list(item.get("recommended_steps") or ()),
    }


def _build_extension_search_drivers(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "target": item.target,
            "driver": getattr(item.driver, "__name__", str(item.driver)),
            "filter_count": len(item.filters),
            "description": item.description,
        }
        for item in getattr(runtime_view, "search_drivers", ()) or ()
    ]


def _build_extension_delivery_assets(extension):
    from apps.core.extensions.assets import inspect_published_extension_assets

    if extension.source != "filesystem":
        return {
            "root_path": "",
            "root_exists": False,
            "asset_count": 0,
            "assets": [],
        }

    manifest_path = _manifest_attr(extension, "path")
    root_path = Path(manifest_path) if manifest_path else None
    asset_specs = [
        {
            "key": "backend_entry",
            "label": "后端入口",
            "path": root_path / "backend" / "ext.py" if root_path else None,
            "kind": "backend",
        },
        {
            "key": "migrations",
            "label": "迁移目录",
            "path": root_path / "backend" / "migrations" if root_path else None,
            "kind": "migration",
        },
        {
            "key": "frontend_admin_entry",
            "label": "后台入口",
            "path": root_path / "frontend" / "admin" / "index.js" if root_path else None,
            "kind": "frontend-admin",
        },
        {
            "key": "frontend_forum_entry",
            "label": "前台入口",
            "path": root_path / "frontend" / "forum" / "index.js" if root_path else None,
            "kind": "frontend-forum",
        },
        {
            "key": "locale",
            "label": "语言目录",
            "path": root_path / "locale" if root_path else None,
            "kind": "locale",
        },
        {
            "key": "docs",
            "label": "文档资源",
            "path": root_path / "docs" / "README.md" if root_path else None,
            "kind": "docs",
        },
    ]
    signature_url = _manifest_nested_attr(extension, "distribution", "signature_url")
    if signature_url:
        signature_path = signature_url
        if not signature_path.startswith(("http://", "https://")):
            root = root_path if root_path else None
            if signature_path.startswith("file://"):
                signature_path = signature_path[7:]
            candidate = Path(signature_path)
            if not candidate.is_absolute() and root is not None:
                candidate = root / candidate
            signature_path = candidate
        asset_specs.append({
            "key": "signature",
            "label": "签名文件",
            "path": signature_path,
            "kind": "signature",
        })

    assets = []
    for item in asset_specs:
        asset_path = item["path"]
        exists = False
        normalized_path = ""
        if isinstance(asset_path, Path):
            exists = asset_path.exists()
            normalized_path = str(asset_path)
        elif asset_path:
            normalized_path = str(asset_path)
            exists = True

        assets.append({
            "key": item["key"],
            "label": item["label"],
            "status": "ready" if exists else "pending",
            "status_label": "已就绪" if exists else "未提供",
            "path": normalized_path,
            "kind": item["kind"],
            "exists": exists,
        })

    published_assets = inspect_published_extension_assets(extension)
    assets.append({
        "key": "published_assets",
        "label": "已发布资产",
        "status": "ready" if published_assets["published"] and published_assets["target_exists"] else "pending",
        "status_label": "已发布" if published_assets["published"] and published_assets["target_exists"] else "未发布",
        "path": published_assets["target"],
        "kind": "published-assets",
        "exists": bool(published_assets["published"] and published_assets["target_exists"]),
        "files": published_assets["files"],
        "cache_key": published_assets.get("cache_key", ""),
        "frontend": published_assets.get("frontend", {}),
        "published_at": published_assets["published_at"],
    })

    return {
        "root_path": str(root_path or ""),
        "root_exists": bool(root_path and root_path.exists()),
        "asset_count": sum(1 for item in assets if item["exists"]),
        "assets": assets,
    }


def _build_extension_capability_summary(
    *,
    notification_types,
    user_preferences,
    event_listeners,
    realtime_broadcasts,
    post_lifecycle,
    post_types,
    search_filters,
    discussion_sorts,
    discussion_list_filters,
    resource_definitions,
    resource_relationships,
    resource_fields,
    resource_endpoints,
    resource_sorts,
    resource_filters,
    owned_models,
    model_ownership_audit,
    model_relations,
    language_packs,
):
    return {
        "notification_type_count": len(notification_types),
        "user_preference_count": len(user_preferences),
        "event_listener_count": len(event_listeners),
        "realtime_broadcast_count": len(realtime_broadcasts),
        "post_lifecycle_count": len(post_lifecycle),
        "post_type_count": len(post_types),
        "search_filter_count": len(search_filters),
        "discussion_sort_count": len(discussion_sorts),
        "discussion_list_filter_count": len(discussion_list_filters),
        "resource_definition_count": len(resource_definitions),
        "resource_relationship_count": len(resource_relationships),
        "resource_field_count": len(resource_fields),
        "resource_endpoint_count": len(resource_endpoints),
        "resource_sort_count": len(resource_sorts),
        "resource_filter_count": len(resource_filters),
        "owned_model_count": len(owned_models),
        "model_package_migration_required_count": int(
            (model_ownership_audit or {}).get("package_migration_required_count") or 0
        ),
        "model_app_label_migration_required_count": int(
            (model_ownership_audit or {}).get("app_label_migration_required_count") or 0
        ),
        "model_relation_count": len(model_relations),
        "language_pack_count": len(language_packs),
    }


def _serialize_extension_admin_actions(extension, *, runtime_record=None):
    return serialize_extension_admin_actions(
        extension,
        runtime_record=runtime_record,
        resolve_settings_pages=_resolve_extension_settings_pages,
        resolve_permissions_pages=_resolve_extension_permissions_pages,
        resolve_operations_pages=_resolve_extension_operations_pages,
        resolve_documentation_url=lambda item: _manifest_attr(item, "documentation_url"),
    )


def _build_default_extension_admin_actions(extension, *, runtime_record=None):
    return build_default_extension_admin_actions(
        extension,
        runtime_record=runtime_record,
        resolve_settings_pages=_resolve_extension_settings_pages,
        resolve_permissions_pages=_resolve_extension_permissions_pages,
        resolve_operations_pages=_resolve_extension_operations_pages,
        resolve_documentation_url=lambda item: _manifest_attr(item, "documentation_url"),
    )


def _resolve_api_stability_label(extension):
    label = _manifest_nested_attr(extension, "compatibility", "api_stability_label")
    if label:
        return label
    api_stability = _manifest_nested_attr(extension, "compatibility", "api_stability", "experimental")
    return {
        "experimental": "实验性",
        "beta": "测试中",
        "stable": "稳定",
        "deprecated": "废弃中",
        "internal": "内部",
    }.get(api_stability, api_stability or "未知")


def _resolve_distribution_channel_label(extension):
    label = _manifest_nested_attr(extension, "distribution", "channel_label")
    if label:
        return label
    channel = _manifest_nested_attr(extension, "distribution", "channel", "private")
    return {
        "private": "私有分发",
        "bundled": "随平台内置",
        "partner": "合作方分发",
        "public": "公开分发",
    }.get(channel, channel or "未知")


def _build_extension_debug_info(extension):
    runtime_record = _resolve_extension_runtime_record(extension)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_record)
    frontend_forum_entry = _resolve_extension_frontend_forum_entry(extension, runtime_record)
    settings_pages = _resolve_extension_settings_pages(extension, runtime_record)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_record)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_record)
    runtime_surface_view = _build_runtime_surface_view(
        extension,
        runtime_record,
        frontend_admin_entry=frontend_admin_entry,
        frontend_forum_entry=frontend_forum_entry,
        settings_pages=settings_pages,
        permissions_pages=permissions_pages,
        operations_pages=operations_pages,
    )
    manifest_path = _manifest_attr(extension, "path")
    extension_root_path = Path(manifest_path) if manifest_path else None
    extensions_base_path = extension_root_path.parent if extension_root_path is not None else None
    inspection = inspect_frontend_admin_entry(
        runtime_surface_view,
        extensions_base_path=extensions_base_path,
    )
    forum_inspection = inspect_frontend_forum_entry(
        runtime_surface_view,
        extensions_base_path=extensions_base_path,
    )
    backend_inspection = inspect_backend_entry(
        extension.manifest,
        extensions_base_path=extensions_base_path,
    )
    validation_issues = []
    if extension.source == "filesystem":
        validation_result = validate_extension_manifests_with_available_ids(
            [extension.manifest],
            available_extension_ids=resolve_available_extension_ids_for_validation(),
            extensions_base_path=extensions_base_path,
            strict_runtime_hooks=True,
        )
        validation_issues = [
            {
                "level": issue.level,
                "code": issue.code,
                "field": issue.field,
                "message": issue.message,
            }
            for issue in validation_result.issues
        ]

    expected_settings_path = f"/admin/extensions/{extension.id}/settings"
    expected_permissions_path = f"/admin/extensions/{extension.id}/permissions"
    expected_operations_path = f"/admin/extensions/{extension.id}/operations"
    expected_forum_entry = f"extensions/{extension.id}/frontend/forum/index.js"
    admin_surface_statuses = [
        {
            "key": "detail",
            "label": "详情页",
            **resolve_admin_surface_implementation(runtime_surface_view, "detail", inspection["available_exports"]),
        },
        {
            "key": "settings",
            "label": "设置页",
            **resolve_admin_surface_implementation(runtime_surface_view, "settings", inspection["available_exports"]),
        },
        {
            "key": "permissions",
            "label": "权限页",
            **resolve_admin_surface_implementation(runtime_surface_view, "permissions", inspection["available_exports"]),
        },
        {
            "key": "operations",
            "label": "操作页",
            **resolve_admin_surface_implementation(runtime_surface_view, "operations", inspection["available_exports"]),
        },
    ]

    return {
        "manifest_path": manifest_path,
        "frontend_admin_entry": {
            "entry": inspection["entry"],
            "entry_type": inspection["entry_type"],
            "exists": inspection["exists"],
            "resolved_path": inspection["resolved_path"],
            "required_exports": list(inspection["required_exports"]),
            "optional_exports": list(inspection["optional_exports"]),
            "available_exports": list(inspection["available_exports"]),
        },
        "frontend_forum_entry": {
            "entry": forum_inspection["entry"],
            "entry_type": forum_inspection["entry_type"],
            "exists": forum_inspection["exists"],
            "resolved_path": forum_inspection["resolved_path"],
            "required_exports": list(forum_inspection["required_exports"]),
            "optional_exports": list(forum_inspection["optional_exports"]),
            "available_exports": list(forum_inspection["available_exports"]),
        },
        "backend_entry": {
            "entry": backend_inspection["entry"],
            "entry_type": backend_inspection["entry_type"],
            "exists": backend_inspection["exists"],
            "resolved_path": backend_inspection["resolved_path"],
            "available_hooks": list(backend_inspection["available_hooks"]),
        },
        "system_hooks": _build_extension_system_hooks(runtime_record),
        "settings_runtime": _build_extension_settings_runtime(runtime_record),
        "frontend_document": _build_extension_frontend_document(runtime_record),
        "theme_runtime": _build_extension_theme_runtime(runtime_record),
        "migration_execution": _serialize_extension_migration_execution(extension),
        "migration_plan": _serialize_extension_migration_plan(extension),
        "admin_surface_statuses": admin_surface_statuses,
        "route_bindings": [
            {
                "key": "settings",
                "label": "设置页",
                "declared": next(iter(settings_pages), ""),
                "expected": expected_settings_path,
                "matches_expected": next(iter(settings_pages), "") == expected_settings_path if settings_pages else False,
            },
            {
                "key": "permissions",
                "label": "权限页",
                "declared": next(iter(permissions_pages), ""),
                "expected": expected_permissions_path,
                "matches_expected": next(iter(permissions_pages), "") == expected_permissions_path if permissions_pages else False,
            },
            {
                "key": "operations",
                "label": "操作页",
                "declared": next(iter(operations_pages), ""),
                "expected": expected_operations_path,
                "matches_expected": next(iter(operations_pages), "") == expected_operations_path if operations_pages else False,
            },
            {
                "key": "frontend_forum_entry",
                "label": "前台入口",
                "declared": frontend_forum_entry,
                "expected": expected_forum_entry,
                "matches_expected": str(frontend_forum_entry or "").strip() == expected_forum_entry,
            },
        ],
        "validation_issues": validation_issues,
    }


def _build_extension_settings_runtime(runtime_record=None) -> dict:
    if runtime_record is None:
        return {
            "defaults": [],
            "reset_rules": [],
            "frontend_cache_keys": [],
            "theme_variables": [],
            "forum_serializations": [],
            "forum_settings_keys": [],
        }

    return {
        "defaults": [
            {
                "key": str(getattr(definition, "key", "") or ""),
                "value": _serialize_debug_value(getattr(definition, "value", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_defaults", ()) or ()
        ],
        "reset_rules": [
            {
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_reset_rules", ()) or ()
        ],
        "frontend_cache_keys": [
            str(key)
            for key in getattr(runtime_record, "settings_frontend_cache_keys", ()) or ()
            if str(key or "").strip()
        ],
        "theme_variables": [
            {
                "name": str(getattr(definition, "name", "") or ""),
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_theme_variables", ()) or ()
        ],
        "forum_serializations": [
            {
                "attribute": str(getattr(definition, "attribute", "") or ""),
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_forum_serializations", ()) or ()
        ],
        "forum_settings_keys": [
            str(key)
            for key in getattr(runtime_record, "forum_settings_keys", ()) or ()
            if str(key or "").strip()
        ],
    }


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


def _build_extension_theme_runtime(runtime_record=None) -> dict:
    if runtime_record is None:
        return {
            "handlers": [],
            "variables": [],
            "document_attributes": [],
            "head_tags": [],
        }

    handlers = []
    variables = []
    document_attributes = []
    head_tags = []
    for definition in getattr(runtime_record, "theme_handlers", ()) or ():
        payload = getattr(definition, "callback", None)
        payload_value = _serialize_debug_value(payload)
        item = {
            "key": str(getattr(definition, "key", "") or ""),
            "payload": payload_value,
            "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            "description": str(getattr(definition, "description", "") or ""),
            "order": int(getattr(definition, "order", 100) or 100),
        }
        handlers.append(item)
        if item["key"] == "variables":
            variables.append(payload_value)
        elif item["key"] == "document_attributes":
            document_attributes.append(payload_value)
        elif item["key"] == "head_tag":
            head_tags.append(payload_value)

    return {
        "handlers": sorted(handlers, key=lambda item: (item["order"], item["key"])),
        "variables": variables,
        "document_attributes": document_attributes,
        "head_tags": head_tags,
    }


def _build_extension_system_hooks(runtime_record=None) -> list[dict]:
    if runtime_record is None:
        return []

    groups = (
        ("error.handling", "错误处理", "error_handlers"),
        ("auth", "认证", "auth_handlers"),
        ("csrf", "CSRF", "csrf_handlers"),
        ("filesystem", "文件系统", "filesystem_drivers"),
        ("console", "控制台", "console_commands"),
        ("session", "会话", "session_handlers"),
        ("theme", "主题", "theme_handlers"),
        ("throttle.api", "API 限流", "throttle_api_handlers"),
        ("user", "用户", "user_handlers"),
    )
    hooks = []
    for service, service_label, attribute in groups:
        for definition in getattr(runtime_record, attribute, ()) or ():
            payload = getattr(definition, "callback", None)
            payload_dict = payload if isinstance(payload, dict) else {}
            hooks.append({
                "service": service,
                "service_label": service_label,
                "key": str(getattr(definition, "key", "") or ""),
                "name": str(payload_dict.get("name") or payload_dict.get("route_name") or payload_dict.get("identifier") or ""),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
                "description": str(getattr(definition, "description", "") or payload_dict.get("description") or ""),
                "order": int(getattr(definition, "order", 100) or 100),
            })
    return sorted(hooks, key=lambda item: (item["service"], item["order"], item["key"]))


def _serialize_debug_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _serialize_debug_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_serialize_debug_value(item) for item in value]
    return getattr(value, "__name__", str(value))


def _serialize_extension_backend_hooks(extension):
    hooks = []
    raw_hooks = dict(extension.runtime.backend_hooks or {})
    for hook_name in sorted(raw_hooks.keys()):
        payload = raw_hooks.get(hook_name)
        if not isinstance(payload, dict):
            continue
        hooks.append({
            "hook": str(payload.get("hook") or hook_name),
            "status": str(payload.get("status") or "ok"),
            "status_label": str(payload.get("status_label") or "已完成"),
            "message": str(payload.get("message") or ""),
            "executed_at": str(payload.get("executed_at") or ""),
            "details": dict(payload.get("details") or {}),
        })
    return hooks


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


def _serialize_extension_migration_execution(extension):
    payload = dict(extension.runtime.migration_execution or {})
    if not payload:
        return None
    return {
        "state": str(payload.get("state") or ""),
        "label": str(payload.get("label") or ""),
        "status": str(payload.get("status") or ""),
        "status_label": str(payload.get("status_label") or ""),
        "message": str(payload.get("message") or ""),
        "executed_at": str(payload.get("executed_at") or ""),
        "details": dict(payload.get("details") or {}),
    }


def _serialize_extension_migration_plan(extension):
    payload = dict(inspect_extension_runtime(extension).get("migration_plan") or {})
    return {
        "declared_files": list(payload.get("declared_files") or []),
        "applied_files": list(payload.get("applied_files") or []),
        "pending_files": list(payload.get("pending_files") or []),
    }
