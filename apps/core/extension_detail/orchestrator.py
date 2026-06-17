from __future__ import annotations

from apps.core.extension_detail.debug import _build_extension_debug_info
from apps.core.extension_detail.forum_domain import _build_extension_delivery_assets
from apps.core.extension_detail.forum_domain import _build_extension_discussion_list_filters
from apps.core.extension_detail.forum_domain import _build_extension_discussion_sorts
from apps.core.extension_detail.forum_domain import _build_extension_event_listeners
from apps.core.extension_detail.forum_domain import _build_extension_language_packs
from apps.core.extension_detail.forum_domain import _build_extension_notification_types
from apps.core.extension_detail.forum_domain import _build_extension_post_lifecycle
from apps.core.extension_detail.forum_domain import _build_extension_post_types
from apps.core.extension_detail.forum_domain import _build_extension_realtime_broadcasts
from apps.core.extension_detail.forum_domain import _build_extension_user_preferences
from apps.core.extension_detail.frontend import _build_extension_frontend_routes
from apps.core.extension_detail.frontend import _resolve_extension_frontend_admin_entry
from apps.core.extension_detail.frontend import _resolve_extension_frontend_forum_entry
from apps.core.extension_detail.frontend import _resolve_extension_frontend_outputs
from apps.core.extension_detail.frontend import _resolve_extension_operations_pages
from apps.core.extension_detail.frontend import _resolve_extension_permissions_pages
from apps.core.extension_detail.frontend import _resolve_extension_settings_pages
from apps.core.extension_detail.frontend import _serialize_extension_frontend_asset_state_for_extension
from apps.core.extension_detail.frontend import _serialize_extension_runtime_rebuild_state
from apps.core.extension_detail.models import _build_extension_model_definitions
from apps.core.extension_detail.models import _build_extension_model_ownership_audit
from apps.core.extension_detail.models import _build_extension_model_relations
from apps.core.extension_detail.models import _build_extension_model_visibility
from apps.core.extension_detail.models import _build_extension_owned_models
from apps.core.extension_detail.models import _serialize_extension_migration_execution
from apps.core.extension_detail.models import _serialize_extension_migration_plan
from apps.core.extension_detail.permissions import _build_extension_admin_page_details
from apps.core.extension_detail.permissions import _build_extension_permission_modules
from apps.core.extension_detail.permissions import _build_extension_permission_sections
from apps.core.extension_detail.permissions import _build_extension_permission_summary
from apps.core.extension_detail.permissions import _flatten_extension_permissions
from apps.core.extension_detail.resources import _build_extension_resource_definitions
from apps.core.extension_detail.resources import _build_extension_resource_endpoints
from apps.core.extension_detail.resources import _build_extension_resource_fields
from apps.core.extension_detail.resources import _build_extension_resource_filters
from apps.core.extension_detail.resources import _build_extension_resource_relationships
from apps.core.extension_detail.resources import _build_extension_resource_sorts
from apps.core.extension_detail.resources import _build_extension_search_drivers
from apps.core.extension_detail.resources import _build_extension_search_filters
from apps.core.extension_diagnostics import (
    classify_extension_diagnostics,
    summarize_extension_delivery,
    summarize_extension_diagnostics,
)
from apps.core.extension_django_apps import normalize_extension_django_app_label
from apps.core.extension_service import ExtensionService
from apps.core.extension_settings_service import (
    get_extension_settings,
    save_extension_settings,
    serialize_extension_settings_schema,
)
from apps.core.extensions.admin_actions import (
    build_default_extension_admin_actions,
    serialize_extension_admin_actions,
)
from apps.core.extensions.admin_manifest import (
    build_extension_author_names as _build_extension_author_names,
    build_extension_links as _build_extension_links,
    build_extension_readme as _build_extension_readme,
    manifest_attr as _manifest_attr,
    manifest_nested_attr as _manifest_nested_attr,
    manifest_nested_value as _manifest_nested_value,
    manifest_sequence as _manifest_sequence,
)
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest
from apps.core.extensions.product import (
    get_extension_protected_reason,
    is_extension_protected,
    is_product_visible_extension,
)
from apps.core.extensions.recovery import (
    get_extension_bisect_state,
    get_extension_safe_mode_extension_ids,
    is_extension_safe_mode_enabled,
    serialize_extension_recovery_state,
)

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

def _serialize_admin_extension_action_payload(extension):
    frontend_output_manifest = inspect_extension_frontend_output_manifest()
    return {
        "runtime": {
            **_serialize_extension_runtime_rebuild_state(),
            "recovery": serialize_extension_recovery_state(),
        },
        "extension": _serialize_admin_extension(extension, frontend_output_manifest=frontend_output_manifest),
    }

def _build_default_extension_admin_actions(extension, *, runtime_record=None):
    return build_default_extension_admin_actions(
        extension,
        runtime_record=runtime_record,
        resolve_settings_pages=_resolve_extension_settings_pages,
        resolve_permissions_pages=_resolve_extension_permissions_pages,
        resolve_operations_pages=_resolve_extension_operations_pages,
        resolve_documentation_url=lambda item: _manifest_attr(item, "documentation_url"),
    )

def _serialize_extension_admin_actions(extension, *, runtime_record=None):
    return serialize_extension_admin_actions(
        extension,
        runtime_record=runtime_record,
        resolve_settings_pages=_resolve_extension_settings_pages,
        resolve_permissions_pages=_resolve_extension_permissions_pages,
        resolve_operations_pages=_resolve_extension_operations_pages,
        resolve_documentation_url=lambda item: _manifest_attr(item, "documentation_url"),
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

def serialize_admin_extension(extension, *, include_permission_details: bool = False):
    return _serialize_admin_extension(
        extension,
        include_permission_details=include_permission_details,
    )

def serialize_admin_extensions_payload(extensions, *, summary: bool = False):
    return _serialize_admin_extensions_payload(extensions, summary=summary)
