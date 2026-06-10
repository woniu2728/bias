from ninja import Body, Router
from pathlib import Path

from apps.core.api_errors import api_error
from apps.core.models import AuditLog
from apps.core.services import PaginationService
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
from apps.core.extension_django_apps import normalize_extension_django_app_label
from apps.core.extensions.product import get_extension_protected_reason, is_extension_protected, is_product_visible_extension
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.frontend_runtime_service import build_frontend_document_payload
from apps.core.extensions.recovery import (
    advance_extension_bisect,
    get_extension_bisect_state,
    get_extension_safe_mode_extension_ids,
    is_extension_safe_mode_enabled,
    serialize_extension_recovery_state,
    start_extension_bisect,
    stop_extension_bisect,
)
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.markdown_service import MarkdownService
from apps.core.forum_registry import get_core_module_ids, get_forum_registry
from apps.core.extensions.runtime_access import get_runtime_resource_registry


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None


def _serialize_audit_log(log: AuditLog):
    return {
        "id": log.id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "data": log.data,
        "created_at": log.created_at,
        "user": {
            "id": log.user.id,
            "username": log.user.username,
            "display_name": log.user.display_name,
        } if log.user else None,
    }


@router.get("/extensions", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_extensions(request):
    denied = _require_staff(request)
    if denied:
        return denied

    summary = str(request.GET.get("summary") or "").strip().lower() in {"1", "true", "yes", "on"}
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions(), summary=summary)


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


@router.post("/extensions/sync", auth=AccessTokenAuth(), tags=["Admin"])
def sync_admin_extensions(request, payload: dict = Body(default={})):
    denied = _require_staff(request)
    if denied:
        return denied

    prune_missing = bool(dict(payload or {}).get("prune_missing", True))
    ExtensionService.sync_extension_packages(
        prune_missing=prune_missing,
        actor=request.auth,
        request=request,
    )
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/sync-order", auth=AccessTokenAuth(), tags=["Admin"])
def sync_admin_extension_order(request):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        ExtensionService.sync_enabled_extension_order(
            actor=request.auth,
            request=request,
        )
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


@router.post("/extensions/rebuild-frontend", auth=AccessTokenAuth(), tags=["Admin"])
def rebuild_admin_extension_frontend(request, payload: dict = Body(default={})):
    denied = _require_staff(request)
    if denied:
        return denied

    options = dict(payload or {})
    result = ExtensionService.rebuild_extension_frontend_assets(
        run_build=bool(options.get("run_build", True)),
        include_disabled=bool(options.get("include_disabled", False)),
        publish=bool(options.get("publish", False)),
        actor=request.auth,
        request=request,
    )
    status = str(result.get("status") or "")
    if status and status != "ok":
        return api_error(
            str(result.get("message") or "扩展前端资产重建失败"),
            status=409,
            code="extension_frontend_rebuild_failed",
            field_errors=result,
        )
    return {
        **_serialize_admin_extensions_payload(get_extension_registry().get_extensions()),
        "frontend_rebuild": result,
    }


@router.get("/extensions/{extension_id}", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension(request, extension_id: str):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
    except ExtensionNotFoundError:
        return api_error("扩展不存在", status=404, code="extension_not_found")
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
        return api_error("扩展不存在", status=404, code="extension_not_found")


@router.post("/extensions/{extension_id}/settings", auth=AccessTokenAuth(), tags=["Admin"])
def save_admin_extension_settings(request, extension_id: str, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        extension = get_extension_registry().get_extension(extension_id)
        settings_data = save_extension_settings(extension.id, payload)
        log_admin_action(
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
        return api_error("扩展不存在", status=404, code="extension_not_found")
    except ExtensionStateError as exc:
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)


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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
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
        return api_error(str(exc), status=409, code=exc.code, field_errors=exc.details)
    return _serialize_admin_extensions_payload(get_extension_registry().get_extensions())


def _serialize_admin_extensions_payload(extensions, *, summary: bool = False):
    payload = [
        _serialize_admin_extension_summary(extension) if summary else _serialize_admin_extension(extension)
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


def _serialize_admin_extension_summary(extension):
    runtime_view = _resolve_extension_runtime_record(extension)
    settings_pages = _resolve_extension_settings_pages(extension, runtime_view)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_view)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_view)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_view)
    frontend_outputs = _resolve_extension_frontend_outputs(extension.id)
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


def _serialize_admin_extension(extension, include_permission_details: bool = False):
    runtime_view = _resolve_extension_runtime_record(extension)
    detail_page = f"/admin/extensions/{extension.id}"
    settings_pages = _resolve_extension_settings_pages(extension, runtime_view)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_view)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_view)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_view)
    frontend_forum_entry = _resolve_extension_frontend_forum_entry(extension, runtime_view)
    frontend_outputs = _resolve_extension_frontend_outputs(extension.id)
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
        "settings_schema": serialize_extension_settings_schema(extension.id),
        "settings_values": get_extension_settings(extension.id) if serialize_extension_settings_schema(extension.id) else {},
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


def _build_extension_links(extension) -> dict:
    links: dict[str, object] = {}
    documentation_url = _manifest_attr(extension, "documentation_url")
    homepage = _manifest_attr(extension, "homepage")
    support_email = _manifest_nested_attr(extension, "security", "support_email")
    if documentation_url:
        links["documentation"] = documentation_url
    if homepage:
        links["website"] = homepage
    if support_email:
        links["support"] = f"mailto:{support_email}"

    extra_links = dict((_manifest_value(extension, "extra", {}) or {}).get("links") or {})
    for key, value in extra_links.items():
        normalized_key = str(key or "").strip()
        if normalized_key and value:
            links[normalized_key] = value

    links["authors"] = _build_extension_author_links(extension)
    return links


def _build_extension_author_names(extension) -> list[str]:
    return [
        str(getattr(author, "name", "") or "").strip()
        for author in _manifest_sequence(extension, "authors")
        if str(getattr(author, "name", "") or "").strip()
    ]


def _build_extension_author_links(extension) -> list[dict[str, str]]:
    author_links = []
    for author in _manifest_sequence(extension, "authors"):
        name = str(getattr(author, "name", "") or "").strip()
        if not name:
            continue
        homepage = str(getattr(author, "homepage", "") or "").strip()
        email = str(getattr(author, "email", "") or "").strip()
        link = homepage or (f"mailto:{email}" if email else "")
        author_links.append({"name": name, "link": link})
    return author_links


def _build_extension_readme(extension) -> dict:
    if extension.source != "filesystem":
        return {
            "available": False,
            "path": "",
            "html": "",
            "source": "",
        }

    manifest_path = _manifest_attr(extension, "path")
    root_path = Path(manifest_path) if manifest_path else None
    if root_path is None:
        return {
            "available": False,
            "path": "",
            "html": "",
            "source": "",
        }

    for candidate in (
        root_path / "README.md",
        root_path / "README",
        root_path / "docs" / "README.md",
    ):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            source = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source = candidate.read_text(encoding="utf-8", errors="replace")
        return {
            "available": bool(source.strip()),
            "path": str(candidate),
            "html": MarkdownService.render(source, sanitize=True),
            "source": source,
        }

    return {
        "available": False,
        "path": "",
        "html": "",
        "source": "",
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


def _resolve_extension_frontend_outputs(extension_id: str) -> dict:
    from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest

    output_manifest = inspect_extension_frontend_output_manifest()
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


def _manifest_attr(extension, name: str, default: str = "") -> str:
    return str(_manifest_value(extension, name, default) or default).strip()


def _manifest_value(extension, name: str, default=None):
    manifest = getattr(extension, "manifest", None)
    if isinstance(manifest, dict):
        return manifest.get(name, default)
    return getattr(manifest, name, default)


def _manifest_nested_value(extension, group: str, name: str, default=None):
    parent = _manifest_value(extension, group, None)
    if isinstance(parent, dict):
        return parent.get(name, default)
    return getattr(parent, name, default)


def _manifest_nested_attr(extension, group: str, name: str, default: str = "") -> str:
    return str(_manifest_nested_value(extension, group, name, default) or default).strip()


def _manifest_sequence(extension, name: str) -> list:
    value = _manifest_value(extension, name, ()) or ()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


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
    documentation_url = _manifest_attr(extension, "documentation_url")
    if documentation_url:
        generated.append({
            "key": "documentation",
            "label": "文档",
            "kind": "link",
            "target": documentation_url,
            "icon": "fas fa-book",
            "tone": "subtle",
            "opens_in_new_tab": False,
            "requires_enabled": False,
            "description": "",
            "order": 50,
        })

    return tuple(type("_GeneratedAdminAction", (), item)() for item in generated if item.get("target"))


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
            available_extension_ids=_resolve_available_extension_ids_for_validation(),
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
        "version": runtime_version or str(payload.get("version") or ""),
        "stamp": f"{raw_order}:{runtime_version or setting.value or ''}",
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

    page, limit = PaginationService.normalize(page, limit)
    queryset = (
        AuditLog.objects.select_related("user")
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
        "data": [_serialize_audit_log(log) for log in logs],
    }
