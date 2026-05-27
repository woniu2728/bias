from ninja import Body, Router
from django.shortcuts import get_object_or_404

from apps.core.extensions import get_extension_registry
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.validation import (
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    validate_extension_manifests_with_available_ids,
)
from apps.core.extension_service import ExtensionService
from apps.core.extension_settings_service import get_extension_settings, serialize_extension_settings_schema, save_extension_settings
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.forum_registry import get_builtin_module_ids


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
        "extension": _serialize_admin_extension(extension),
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

    return {
        "summary": {
            "extension_count": len(payload),
            "enabled_count": sum(1 for item in payload if item["enabled"]),
            "healthy_count": sum(1 for item in payload if item["healthy"]),
            "builtin_count": sum(1 for item in payload if item["source"] == "builtin-module"),
            "filesystem_count": sum(1 for item in payload if item["source"] == "filesystem"),
        },
        "extensions": payload,
    }


def _serialize_admin_extension(extension):
    detail_page = f"/admin/extensions/{extension.id}"
    settings_page = next(iter(extension.manifest.settings_pages), "")
    permissions_page = next(iter(extension.manifest.permissions_pages), "")
    operations_page = next(iter(extension.manifest.operations_pages), "")
    admin_actions = _serialize_extension_admin_actions(extension)

    return {
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
        "frontend_admin_entry": extension.manifest.frontend_admin_entry,
        "frontend_forum_entry": extension.manifest.frontend_forum_entry,
        "settings_pages": list(extension.manifest.settings_pages),
        "permissions_pages": list(extension.manifest.permissions_pages),
        "operations_pages": list(extension.manifest.operations_pages),
        "settings_schema": serialize_extension_settings_schema(extension.id),
        "settings_values": get_extension_settings(extension.id) if extension.manifest.settings_schema else {},
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
        "migration_state": extension.runtime.migration_state,
        "migration_label": extension.runtime.migration_label,
        "migration_execution": _serialize_extension_migration_execution(extension),
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
        "module_ids": list(extension.module_ids),
        "admin_pages": list(extension.admin_pages),
        "settings_groups": list(extension.settings_groups),
        "admin_actions": admin_actions,
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


def _serialize_extension_admin_actions(extension):
    actions = []
    for action in sorted(extension.manifest.admin_actions, key=lambda item: (item.order, item.key)):
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
    registry = get_extension_registry()
    inspection = inspect_frontend_admin_entry(
        extension.manifest,
        extensions_base_path=registry.extensions_path,
    )
    forum_inspection = inspect_frontend_forum_entry(
        extension.manifest,
        extensions_base_path=registry.extensions_path,
    )
    backend_inspection = inspect_backend_entry(
        extension.manifest,
        extensions_base_path=registry.extensions_path,
    )
    validation_result = validate_extension_manifests_with_available_ids(
        [extension.manifest],
        available_extension_ids=set(get_builtin_module_ids()),
        extensions_base_path=registry.extensions_path,
        strict_runtime_hooks=True,
    )

    expected_settings_path = f"/admin/extensions/{extension.id}/settings"
    expected_permissions_path = f"/admin/extensions/{extension.id}/permissions"
    expected_operations_path = f"/admin/extensions/{extension.id}/operations"
    expected_forum_entry = f"extensions/{extension.id}/frontend/forum/index.js"

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
        "route_bindings": [
            {
                "key": "settings",
                "label": "设置页",
                "declared": next(iter(extension.manifest.settings_pages), ""),
                "expected": expected_settings_path,
                "matches_expected": next(iter(extension.manifest.settings_pages), "") == expected_settings_path if extension.manifest.settings_pages else False,
            },
            {
                "key": "permissions",
                "label": "权限页",
                "declared": next(iter(extension.manifest.permissions_pages), ""),
                "expected": expected_permissions_path,
                "matches_expected": next(iter(extension.manifest.permissions_pages), "") == expected_permissions_path if extension.manifest.permissions_pages else False,
            },
            {
                "key": "operations",
                "label": "操作页",
                "declared": next(iter(extension.manifest.operations_pages), ""),
                "expected": expected_operations_path,
                "matches_expected": next(iter(extension.manifest.operations_pages), "") == expected_operations_path if extension.manifest.operations_pages else False,
            },
            {
                "key": "frontend_forum_entry",
                "label": "前台入口",
                "declared": extension.manifest.frontend_forum_entry,
                "expected": expected_forum_entry,
                "matches_expected": str(extension.manifest.frontend_forum_entry or "").strip() == expected_forum_entry,
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


@router.get("/tags", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_tags(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    tags = legacy.Tag.objects.select_related("parent").all().order_by("position", "name")
    return [legacy.serialize_admin_tag(tag) for tag in tags]


@router.post("/tags", auth=AccessTokenAuth(), tags=["Admin"])
def create_admin_tag(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        normalized = legacy.normalize_optional_tag_parent(payload)
        name = (normalized.get("name") or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")
        parent_id = normalized.get("parent_id")
        tag = legacy.TagService.create_tag(
            name=name,
            slug=(normalized.get("slug") or "").strip() or None,
            description=normalized.get("description", ""),
            color=normalized.get("color") or "#888",
            icon=(normalized.get("icon") or "").strip(),
            position=legacy.normalize_tag_position(normalized, parent_id=parent_id),
            parent_id=parent_id,
            is_hidden=bool(normalized.get("is_hidden", False)),
            is_restricted=bool(normalized.get("is_restricted", False)),
            view_scope=normalized.get("view_scope") or legacy.Tag.ACCESS_PUBLIC,
            start_discussion_scope=normalized.get("start_discussion_scope") or legacy.Tag.ACCESS_MEMBERS,
            reply_scope=normalized.get("reply_scope") or legacy.Tag.ACCESS_MEMBERS,
            user=request.auth,
        )
        tag = legacy.Tag.objects.select_related("parent").get(id=tag.id)
        legacy.log_admin_action(
            request,
            "admin.tag.create",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "slug": tag.slug, "parent_id": tag.parent_id},
        )
        return legacy.serialize_admin_tag(tag)
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)
    except Exception as exc:
        return legacy.admin_error(str(exc), status=400)


@router.put("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_admin_tag(request, tag_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        tag = get_object_or_404(legacy.Tag, id=tag_id)
        normalized = legacy.normalize_optional_tag_parent(payload)
        next_view_scope = tag.view_scope
        next_start_scope = tag.start_discussion_scope
        next_reply_scope = tag.reply_scope

        if "name" in normalized:
            name = (normalized.get("name") or "").strip()
            if not name:
                raise ValueError("标签名称不能为空")
            tag.name = name
        if "slug" in normalized:
            tag.slug = (normalized.get("slug") or "").strip()
        if "description" in normalized:
            tag.description = normalized.get("description") or ""
        if "color" in normalized:
            tag.color = normalized.get("color") or "#888"
        if "icon" in normalized:
            tag.icon = (normalized.get("icon") or "").strip()
        if "position" in normalized and normalized.get("position") is not None:
            tag.position = int(normalized["position"])
        if "parent_id" in normalized:
            parent_id = normalized.get("parent_id")
            if parent_id is None:
                tag.parent = None
            else:
                parent = get_object_or_404(legacy.Tag, id=parent_id)
                legacy.TagService.validate_parent_assignment(tag, parent)
                tag.parent = parent
        if "is_hidden" in normalized:
            tag.is_hidden = bool(normalized["is_hidden"])
        if "is_restricted" in normalized:
            tag.is_restricted = bool(normalized["is_restricted"])
        if "view_scope" in normalized:
            next_view_scope = normalized.get("view_scope")
        if "start_discussion_scope" in normalized:
            next_start_scope = normalized.get("start_discussion_scope")
        if "reply_scope" in normalized:
            next_reply_scope = normalized.get("reply_scope")
        (
            tag.view_scope,
            tag.start_discussion_scope,
            tag.reply_scope,
        ) = legacy.TagService.validate_scope_configuration(
            next_view_scope,
            next_start_scope,
            next_reply_scope,
        )
        tag.save()
        tag.refresh_from_db()
        legacy.log_admin_action(
            request,
            "admin.tag.update",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "slug": tag.slug, "changed_fields": sorted(normalized.keys())},
        )
        return legacy.serialize_admin_tag(tag)
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)
    except Exception as exc:
        return legacy.admin_error(str(exc), status=400)


@router.post("/tags/{tag_id}/move", auth=AccessTokenAuth(), tags=["Admin"])
def move_admin_tag(request, tag_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        tag = get_object_or_404(legacy.Tag, id=tag_id)
        moved = legacy.TagService.move_tag(
            tag_id=tag_id,
            direction=(payload.get("direction") or "").strip(),
            user=request.auth,
        )
        tags = legacy.Tag.objects.select_related("parent").all().order_by("position", "name")
        legacy.log_admin_action(
            request,
            "admin.tag.move",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "direction": (payload.get("direction") or "").strip(), "moved": bool(moved)},
        )
        return {
            "moved": moved,
            "data": [legacy.serialize_admin_tag(item) for item in tags],
        }
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)
    except legacy.Tag.DoesNotExist:
        return legacy.admin_error("标签不存在", status=404)


@router.delete("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_admin_tag(request, tag_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        tag = get_object_or_404(legacy.Tag, id=tag_id)
        tag_snapshot = {"name": tag.name, "slug": tag.slug, "parent_id": tag.parent_id}
        legacy.TagService.delete_tag(tag_id, request.auth)
        legacy.log_admin_action(
            request,
            "admin.tag.delete",
            target_type="tag",
            target_id=tag_id,
            data=tag_snapshot,
        )
        return {"message": "标签删除成功"}
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)


@router.post("/tags/stats/refresh", auth=AccessTokenAuth(), tags=["Admin"])
def refresh_admin_tag_stats(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    result = legacy.TagService.dispatch_refresh_tag_stats()
    legacy.log_admin_action(
        request,
        "admin.tag.refresh_stats",
        target_type="tag",
        data={
            "mode": result.get("mode"),
            "tag_ids": result.get("tag_ids"),
        },
    )
    return result


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
