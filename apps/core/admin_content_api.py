from ninja import Body, Router
from pathlib import Path

from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions import get_extension_registry
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
from apps.core.extensions.product import is_product_visible_extension
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.recovery import (
    advance_extension_bisect,
    get_extension_bisect_state,
    get_extension_safe_mode_extension_ids,
    is_extension_safe_mode_enabled,
    serialize_extension_recovery_state,
    start_extension_bisect,
    stop_extension_bisect,
)
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.forum_registry import get_core_module_ids, get_forum_registry
from apps.core.resource_registry import get_resource_registry


router = Router()


def _legacy():
    from apps.core import admin_api as legacy

    return legacy


def _require_staff(request):
    legacy = _legacy()
    if not request.auth or not request.auth.is_staff:
        return legacy.admin_error("需要管理员权限", status=403)
    return None


@router.get("/extensions", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_extensions(request):
    denied = _require_staff(request)
    if denied:
        return denied

    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.get("/extensions/bisect", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension_bisect(request):
    denied = _require_staff(request)
    if denied:
        return denied
    return {"bisect": get_extension_bisect_state()}


@router.post("/extensions/bisect/start", auth=AccessTokenAuth(), tags=["Admin"])
def start_admin_extension_bisect(request, payload: dict = Body(default={})):
    denied = _require_staff(request)
    if denied:
        return denied
    requested_ids = payload.get("extension_ids")
    if requested_ids is None:
        requested_ids = [
            extension.id
            for extension in get_extension_registry().get_enabled_extensions()
        ]
    return {"bisect": start_extension_bisect(requested_ids)}


@router.post("/extensions/bisect/step", auth=AccessTokenAuth(), tags=["Admin"])
def step_admin_extension_bisect(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied
    return {"bisect": advance_extension_bisect(bool(payload.get("issue_present")))}


@router.post("/extensions/bisect/stop", auth=AccessTokenAuth(), tags=["Admin"])
def stop_admin_extension_bisect(request):
    denied = _require_staff(request)
    if denied:
        return denied
    return {"bisect": stop_extension_bisect()}


@router.get("/extensions/{extension_id}", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
    except ExtensionNotFoundError:
        return _legacy().admin_error("扩展不存在", status=404, code="extension_not_found")
    return {
        "extension": _serialize_admin_extension(extension, include_permission_details=True),
    }


@router.get("/extensions/{extension_id}/settings", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension_settings(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
        return {
            "extension_id": extension.id,
            "schema": serialize_extension_settings_schema(extension.id),
            "settings": get_extension_settings(extension.id),
        }
    except ExtensionNotFoundError:
        return _legacy().admin_error("扩展不存在", status=404, code="extension_not_found")


@router.post("/extensions/{extension_id}/settings", auth=AccessTokenAuth(), tags=["Admin"])
def save_admin_extension_settings(request, extension_id: str, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
        settings_data = save_extension_settings(extension.id, payload)
        _legacy().log_admin_action(
            request,
            "admin.extension.settings.update",
            target_type="extension",
            data={
                "extension_id": extension.id,
                "keys": sorted(payload.keys()),
            },
        )
        return {
            "message": "扩展设置保存成功",
            "extension_id": extension.id,
            "settings": settings_data,
        }
    except ExtensionNotFoundError:
        return _legacy().admin_error("扩展不存在", status=404, code="extension_not_found")
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)


@router.post("/extensions/{extension_id}/enable", auth=AccessTokenAuth(), tags=["Admin"])
def enable_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.set_extension_enabled(
            extension_id,
            True,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/{extension_id}/install", auth=AccessTokenAuth(), tags=["Admin"])
def install_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.install_extension(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/{extension_id}/runtime-hooks/{hook_name}", auth=AccessTokenAuth(), tags=["Admin"])
def run_admin_extension_runtime_hook(request, extension_id: str, hook_name: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.run_extension_runtime_hook(
            extension_id,
            hook_name,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/{extension_id}/migrations", auth=AccessTokenAuth(), tags=["Admin"])
def run_admin_extension_migrations(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.run_extension_migrations(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/{extension_id}/disable", auth=AccessTokenAuth(), tags=["Admin"])
def disable_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.set_extension_enabled(
            extension_id,
            False,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/{extension_id}/uninstall", auth=AccessTokenAuth(), tags=["Admin"])
def uninstall_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.uninstall_extension(
            extension_id,
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return _legacy().admin_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


def _serialize_admin_extensions_payload(extensions):
    payload = [_serialize_admin_extension(extension) for extension in extensions]
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
        },
        "extensions": payload,
    }


def _serialize_admin_extension(extension, include_permission_details: bool = False):
    runtime_view = _resolve_extension_runtime_record(extension)
    detail_page = f"/admin/extensions/{extension.id}"
    settings_pages = _resolve_extension_settings_pages(extension, runtime_view)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_view)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_view)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_view)
    frontend_forum_entry = _resolve_extension_frontend_forum_entry(extension, runtime_view)
    settings_page = next(iter(settings_pages), "")
    permissions_page = next(iter(permissions_pages), "")
    operations_page = next(iter(operations_pages), "")
    admin_actions = _serialize_extension_admin_actions(extension, runtime_record=runtime_view)
    permission_sections = _build_extension_permission_sections(extension) if include_permission_details else []
    permission_summary = _build_extension_permission_summary(permission_sections)
    permission_modules = _build_extension_permission_modules(permission_sections)
    admin_page_details = _build_extension_admin_page_details(extension)
    notification_types = _build_extension_notification_types(extension)
    user_preferences = _build_extension_user_preferences(extension)
    event_listeners = _build_extension_event_listeners(extension, runtime_view)
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
    model_definitions = _build_extension_model_definitions(runtime_view)
    model_visibility = _build_extension_model_visibility(runtime_view)
    search_drivers = _build_extension_search_drivers(runtime_view)
    language_packs = _build_extension_language_packs(extension)
    delivery_assets = _build_extension_delivery_assets(extension)
    capability_summary = _build_extension_capability_summary(
        notification_types=notification_types,
        user_preferences=user_preferences,
        event_listeners=event_listeners,
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
        language_packs=language_packs,
    )

    payload = {
        "id": extension.id,
        "name": extension.name,
        "version": extension.version,
        "description": extension.description,
        "icon": extension.manifest.icon,
        "category": extension.manifest.category,
        "documentation_url": extension.manifest.documentation_url,
        "dependencies": list(extension.manifest.dependencies),
        "optional_dependencies": list(extension.manifest.optional_dependencies),
        "conflicts": list(extension.manifest.conflicts),
        "provides": list(extension.manifest.provides),
        "backend_entry": extension.manifest.backend_entry,
        "frontend_admin_entry": frontend_admin_entry,
        "frontend_forum_entry": frontend_forum_entry,
        "settings_pages": list(settings_pages),
        "permissions_pages": list(permissions_pages),
        "operations_pages": list(operations_pages),
        "settings_schema": serialize_extension_settings_schema(extension.id),
        "settings_values": get_extension_settings(extension.id) if serialize_extension_settings_schema(extension.id) else {},
        "compatibility": {
            "bias_version": extension.manifest.compatibility.bias_version,
            "api_version": extension.manifest.compatibility.api_version,
            "api_stability": extension.manifest.compatibility.api_stability,
            "api_stability_label": _resolve_api_stability_label(extension),
            "breaking_change_policy": extension.manifest.compatibility.breaking_change_policy,
        },
        "security": {
            "policy_url": extension.manifest.security.policy_url,
            "support_email": extension.manifest.security.support_email,
            "capabilities_notice": extension.manifest.security.capabilities_notice,
        },
        "distribution": {
            "channel": extension.manifest.distribution.channel,
            "channel_label": _resolve_distribution_channel_label(extension),
            "signing_key_id": extension.manifest.distribution.signing_key_id,
            "signature_url": extension.manifest.distribution.signature_url,
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
        "module_ids": list(extension.module_ids),
        "admin_pages": list(extension.admin_pages),
        "admin_page_details": admin_page_details,
        "settings_groups": list(extension.settings_groups),
        "admin_actions": admin_actions,
        "permission_summary": permission_summary,
        "permission_modules": permission_modules,
        "permission_sections": permission_sections,
        "notification_types": notification_types,
        "user_preferences": user_preferences,
        "event_listeners": event_listeners,
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
        "model_definitions": model_definitions,
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
            "documentation_url": extension.manifest.documentation_url,
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


def _build_extension_post_lifecycle(extension, runtime_record=None):
    if runtime_record is None:
        return []

    handlers = []
    for item in getattr(runtime_record, "post_lifecycle", ()) or ():
        phases = [
            phase
            for phase in ("apply_created", "apply_updated", "apply_approved", "prepare_delete", "apply_deleted")
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
        for item in get_resource_registry().get_resources()
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
        for item in get_resource_registry().get_all_relationships()
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
        for item in get_resource_registry().get_all_endpoints()
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
        for item in get_resource_registry().get_all_sorts()
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
        for item in get_resource_registry().get_all_fields()
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
        for item in get_resource_registry().get_all_field_mutators()
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
            "model": getattr(item.model, "__name__", str(item.model)),
            "key": item.key,
            "kind": item.kind,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_definitions", ()) or ()
    ]
    definitions.extend([
        {
            "model": getattr(item.model, "__name__", str(item.model)),
            "key": item.name,
            "kind": f"relation:{item.relation_type}",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_relations", ()) or ()
    ])
    definitions.extend([
        {
            "model": getattr(item.model, "__name__", str(item.model)),
            "key": item.attribute,
            "kind": "cast",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_casts", ()) or ()
    ])
    definitions.extend([
        {
            "model": getattr(item.model, "__name__", str(item.model)),
            "key": item.attribute,
            "kind": "default",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_defaults", ()) or ()
    ])
    definitions.extend([
        {
            "model": getattr(item.model, "__name__", str(item.model)),
            "key": item.identifier,
            "kind": "model-url:slug",
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_slug_drivers", ()) or ()
    ])
    return definitions


def _build_extension_model_visibility(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "model": getattr(item.model, "__name__", str(item.model)),
            "ability": item.ability,
            "description": item.description,
        }
        for item in getattr(runtime_view, "model_visibility", ()) or ()
    ]


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

    root_path = Path(extension.manifest.path) if extension.manifest.path else None
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
    if str(extension.manifest.distribution.signature_url or "").strip():
        asset_specs.append({
            "key": "signature",
            "label": "签名文件",
            "path": extension.manifest.distribution.signature_url,
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
    language_packs,
):
    return {
        "notification_type_count": len(notification_types),
        "user_preference_count": len(user_preferences),
        "event_listener_count": len(event_listeners),
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
        "language_pack_count": len(language_packs),
    }


def _serialize_extension_admin_actions(extension, *, runtime_record=None):
    declared_actions = tuple(getattr(runtime_record, "admin_actions", ()) or ()) or extension.admin_actions or tuple(_build_default_extension_admin_actions(extension, runtime_record=runtime_record))
    actions = []
    for action in sorted(declared_actions, key=lambda item: (item.order, item.key)):
        if action.requires_enabled and not extension.runtime.enabled:
            continue
        actions.append({
            "key": action.key,
            "label": action.label,
            "kind": action.kind,
            "target": action.target,
            "icon": action.icon,
            "tone": action.tone,
            "opens_in_new_tab": action.opens_in_new_tab,
            "requires_enabled": action.requires_enabled,
            "description": action.description,
            "order": action.order,
        })
    return actions


def _build_default_extension_admin_actions(extension, *, runtime_record=None):
    settings_pages = _resolve_extension_settings_pages(extension, runtime_record)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_record)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_record)
    generated = [
        {
            "key": "details",
            "label": "查看详情",
            "kind": "route",
            "target": f"/admin/extensions/{extension.id}",
            "icon": "fas fa-arrow-right",
            "tone": "primary",
            "opens_in_new_tab": False,
            "requires_enabled": False,
            "description": "",
            "order": 10,
        },
    ]

    if settings_pages:
        generated.append({
            "key": "settings",
            "label": "设置",
            "kind": "route",
            "target": next(iter(settings_pages), ""),
            "icon": "fas fa-sliders-h",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 20,
        })
    if permissions_pages:
        generated.append({
            "key": "permissions",
            "label": "权限",
            "kind": "route",
            "target": next(iter(permissions_pages), ""),
            "icon": "fas fa-user-shield",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 30,
        })
    if operations_pages:
        generated.append({
            "key": "operations",
            "label": "操作",
            "kind": "route",
            "target": next(iter(operations_pages), ""),
            "icon": "fas fa-screwdriver-wrench",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 40,
        })
    if extension.manifest.documentation_url:
        generated.append({
            "key": "documentation",
            "label": "文档",
            "kind": "link",
            "target": extension.manifest.documentation_url,
            "icon": "fas fa-book",
            "tone": "subtle",
            "opens_in_new_tab": False,
            "requires_enabled": False,
            "description": "",
            "order": 50,
        })

    return tuple(type("_GeneratedAdminAction", (), item)() for item in generated if item.get("target"))


def _resolve_api_stability_label(extension):
    label = str(extension.manifest.compatibility.api_stability_label or "").strip()
    if label:
        return label
    return {
        "experimental": "实验性",
        "beta": "测试中",
        "stable": "稳定",
        "deprecated": "废弃中",
        "internal": "内部",
    }.get(extension.manifest.compatibility.api_stability, extension.manifest.compatibility.api_stability or "未知")


def _resolve_distribution_channel_label(extension):
    label = str(extension.manifest.distribution.channel_label or "").strip()
    if label:
        return label
    return {
        "private": "私有分发",
        "bundled": "随平台内置",
        "partner": "合作方分发",
        "public": "公开分发",
    }.get(extension.manifest.distribution.channel, extension.manifest.distribution.channel or "未知")


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
    extension_root_path = Path(extension.manifest.path) if str(extension.manifest.path or "").strip() else None
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
    validation_result = validate_extension_manifests_with_available_ids(
        [extension.manifest],
        available_extension_ids=_resolve_available_extension_ids_for_validation(),
        extensions_base_path=extensions_base_path,
        strict_runtime_hooks=True,
    )

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
        "manifest_path": extension.manifest.path,
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
        "validation_issues": [
            {
                "level": issue.level,
                "code": issue.code,
                "field": issue.field,
                "message": issue.message,
            }
            for issue in validation_result.issues
        ],
    }


def _resolve_available_extension_ids_for_validation() -> set[str]:
    extension_ids = set(get_core_module_ids())
    try:
        extension_ids.update(item.id for item in get_extension_registry().get_extensions())
    except Exception:
        pass
    return extension_ids


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

    setting = Setting.objects.filter(key="extensions_runtime_rebuild_required").first()
    enabled_order = Setting.objects.filter(key="extensions_enabled_order").first()
    raw_order = str(getattr(enabled_order, "value", "") or "")
    if setting is None:
        return {
            "required": False,
            "reason": "",
            "extension_id": "",
            "urlconf": "",
            "stamp": f"{raw_order}:",
            "frontend_assets": _serialize_extension_frontend_asset_state(),
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
        "stamp": f"{raw_order}:{setting.value or ''}",
        "frontend_assets": _serialize_extension_frontend_asset_state(),
    }


def _serialize_extension_frontend_asset_state():
    from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest

    return inspect_extension_frontend_output_manifest()


def _serialize_extension_frontend_asset_state_for_extension(extension):
    state = _serialize_extension_frontend_asset_state()
    extensions = dict(state.get("extensions") or {})
    entry = dict(extensions.get(extension.id) or {})
    runtime = _serialize_extension_runtime_rebuild_state()
    has_frontend = bool(
        _resolve_extension_frontend_admin_entry(extension)
        or _resolve_extension_frontend_forum_entry(extension)
    )
    return {
        "manifest_exists": bool(state.get("exists")),
        "has_frontend": has_frontend,
        "compiled": bool(entry.get("outputs")) if has_frontend else True,
        "requires_rebuild": bool(runtime.get("required")),
        "outputs": dict(entry.get("outputs") or {}),
        "generated_at": str(state.get("generated_at") or ""),
    }


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


@router.get("/modules", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_modules(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    registry_modules = legacy.REGISTRY.get_modules()
    module_map = {module.module_id: module for module in registry_modules}
    modules = [legacy.serialize_module_definition(module, module_map) for module in registry_modules]
    pages = [
        {
            "path": page.path,
            "label": page.label,
            "icon": page.icon,
            "module_id": page.module_id,
            "nav_section": page.nav_section,
            "description": page.description,
            "settings_group": page.settings_group,
        }
        for page in legacy.REGISTRY.get_admin_pages()
    ]
    notification_types = [
        {
            "code": notification_type.code,
            "label": notification_type.label,
            "module_id": notification_type.module_id,
            "description": notification_type.description,
            "icon": notification_type.icon,
            "navigation_scope": notification_type.navigation_scope,
            "preference_key": notification_type.preference_key,
            "preference_label": notification_type.preference_label,
            "preference_description": notification_type.preference_description,
            "preference_default_enabled": notification_type.preference_default_enabled,
        }
        for notification_type in legacy.REGISTRY.get_notification_types()
    ]
    event_listeners = [
        {
            "event": listener.event,
            "listener": listener.listener,
            "module_id": listener.module_id,
            "description": listener.description,
        }
        for listener in legacy.REGISTRY.get_event_listeners()
    ]
    post_types = [
        {
            "code": post_type.code,
            "label": post_type.label,
            "module_id": post_type.module_id,
            "description": post_type.description,
            "icon": post_type.icon,
            "is_default": post_type.is_default,
            "is_stream_visible": post_type.is_stream_visible,
            "counts_toward_discussion": post_type.counts_toward_discussion,
            "counts_toward_user": post_type.counts_toward_user,
            "searchable": post_type.searchable,
        }
        for post_type in legacy.REGISTRY.get_post_types()
    ]
    search_filters = [
        {
            "code": search_filter.code,
            "label": search_filter.label,
            "module_id": search_filter.module_id,
            "target": search_filter.target,
            "syntax": search_filter.syntax,
            "description": search_filter.description,
        }
        for search_filter in legacy.REGISTRY.get_search_filters()
    ]
    discussion_sorts = [
        {
            "code": discussion_sort.code,
            "label": discussion_sort.label,
            "module_id": discussion_sort.module_id,
            "description": discussion_sort.description,
            "icon": discussion_sort.icon,
            "is_default": discussion_sort.is_default,
            "toolbar_visible": discussion_sort.toolbar_visible,
        }
        for discussion_sort in legacy.REGISTRY.get_discussion_sorts()
    ]
    discussion_list_filters = [
        {
            "code": discussion_list_filter.code,
            "label": discussion_list_filter.label,
            "module_id": discussion_list_filter.module_id,
            "description": discussion_list_filter.description,
            "icon": discussion_list_filter.icon,
            "is_default": discussion_list_filter.is_default,
            "requires_authenticated_user": discussion_list_filter.requires_authenticated_user,
            "sidebar_visible": discussion_list_filter.sidebar_visible,
            "route_path": discussion_list_filter.route_path,
        }
        for discussion_list_filter in legacy.REGISTRY.get_discussion_list_filters()
    ]
    resource_fields = [
        {
            "resource": definition.resource,
            "field": definition.field,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in legacy.RESOURCE_REGISTRY.get_all_fields()
    ]
    resource_definitions = [
        {
            "resource": definition.resource,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in legacy.RESOURCE_REGISTRY.get_resources()
    ]
    resource_relationships = [
        {
            "resource": definition.resource,
            "relationship": definition.relationship,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in legacy.RESOURCE_REGISTRY.get_all_relationships()
    ]
    user_preferences = [
        {
            "key": preference.key,
            "label": preference.label,
            "module_id": preference.module_id,
            "description": preference.description,
            "category": preference.category,
            "default_value": preference.default_value,
        }
        for preference in legacy.REGISTRY.get_user_preferences()
    ]
    language_packs = [
        {
            "code": language_pack.code,
            "label": language_pack.label,
            "native_label": language_pack.native_label,
            "module_id": language_pack.module_id,
            "description": language_pack.description,
            "is_default": language_pack.is_default,
        }
        for language_pack in legacy.REGISTRY.get_language_packs()
    ]
    category_summaries = legacy.build_module_category_summaries(modules)
    dependency_attention = [
        {
            "module_id": module["id"],
            "module_name": module["name"],
            "status": module["dependency_status"],
            "label": module["dependency_status_label"],
            "missing": module["missing_dependencies"],
            "disabled": module["disabled_dependencies"],
        }
        for module in modules
        if module["dependency_status"] != "healthy"
    ]
    runtime_dependency_attention_count = sum(
        1
        for module in modules
        if module.get("runtime_dependency_summary") is not None
        and module["runtime_dependency_summary"]["status"] != "healthy"
    )
    summary = {
        "module_count": len(modules),
        "core_count": sum(1 for module in modules if module["is_core"]),
        "enabled_count": sum(1 for module in modules if module["enabled"]),
        "permission_count": sum(len(module["permissions"]) for module in modules),
        "admin_page_count": len(pages),
        "notification_type_count": len(notification_types),
        "user_preference_count": len(user_preferences),
        "language_pack_count": len(language_packs),
        "event_listener_count": len(event_listeners),
        "post_type_count": len(post_types),
        "resource_definition_count": len(resource_definitions),
        "resource_relationship_count": len(resource_relationships),
        "resource_field_count": len(resource_fields),
        "search_filter_count": len(search_filters),
        "discussion_sort_count": len(discussion_sorts),
        "discussion_list_filter_count": len(discussion_list_filters),
        "settings_group_count": sum(len(module["settings"]["groups"]) for module in modules),
        "dependency_issue_count": len(dependency_attention),
        "health_attention_count": sum(1 for module in modules if module["health_status"] != "healthy"),
        "runtime_dependency_attention_count": runtime_dependency_attention_count,
    }
    return {
        "summary": summary,
        "modules": modules,
        "category_summaries": category_summaries,
        "dependency_attention": dependency_attention,
        "admin_pages": pages,
        "notification_types": notification_types,
        "user_preferences": user_preferences,
        "language_packs": language_packs,
        "event_listeners": event_listeners,
        "post_types": post_types,
        "search_filters": search_filters,
        "discussion_sorts": discussion_sorts,
        "discussion_list_filters": discussion_list_filters,
        "resource_definitions": resource_definitions,
        "resource_relationships": resource_relationships,
        "resource_fields": resource_fields,
        "permission_aliases": legacy.REGISTRY.get_permission_aliases(),
    }


@router.get("/audit-logs", auth=AccessTokenAuth(), tags=["Admin"])
def list_audit_logs(
    request,
    page: int = 1,
    limit: int = 20,
    action: str = "",
    target_type: str = "",
    user_id: int = None,
):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    page, limit = legacy.PaginationService.normalize(page, limit)
    queryset = (
        legacy.AuditLog.objects.select_related("user")
        .filter(action__startswith="admin.")
        .order_by("-created_at", "-id")
    )

    if action:
        queryset = queryset.filter(action=action)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    total = queryset.count()
    offset = (page - 1) * limit
    logs = queryset[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [legacy.serialize_audit_log(log) for log in logs],
    }
