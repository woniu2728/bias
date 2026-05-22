from typing import Any, Dict, List


def resolve_module_category_label(category: str) -> str:
    if category == "core":
        return "核心"
    if category == "infrastructure":
        return "基础设施"
    return "功能模块"


def build_module_dependency_state(module, module_map: Dict[str, Any]) -> Dict[str, Any]:
    missing_dependencies = []
    disabled_dependencies = []

    for dependency in module.dependencies:
        dependency_module = module_map.get(dependency)
        if dependency_module is None:
            missing_dependencies.append(dependency)
        elif not dependency_module.enabled:
            disabled_dependencies.append(dependency)

    if missing_dependencies:
        status = "missing"
        label = "缺少依赖"
    elif disabled_dependencies:
        status = "disabled"
        label = "依赖未启用"
    else:
        status = "healthy"
        label = "依赖正常"

    return {
        "status": status,
        "label": label,
        "missing": missing_dependencies,
        "disabled": disabled_dependencies,
    }


def build_module_health_state(module, dependency_state: Dict[str, Any]) -> Dict[str, Any]:
    issues = []

    if dependency_state["status"] != "healthy":
        issues.append(dependency_state["label"])

    if module.enabled and not module.capabilities:
        issues.append("未声明能力项")

    status = "healthy"
    label = "健康"
    if issues:
        status = "attention"
        label = "需关注"

    return {
        "status": status,
        "label": label,
        "issues": issues,
    }


def build_module_settings_overview(
    module,
    *,
    setting_model,
    basic_settings_defaults: Dict[str, Any],
    appearance_settings_defaults: Dict[str, Any],
    advanced_settings_defaults: Dict[str, Any],
    mail_settings_defaults: Dict[str, Any],
) -> Dict[str, Any]:
    setting_keys = []
    for group_name in module.settings_groups:
        if group_name == "basic":
            setting_keys.extend([f"basic.{key}" for key in basic_settings_defaults.keys()])
        elif group_name == "appearance":
            setting_keys.extend([f"appearance.{key}" for key in appearance_settings_defaults.keys()])
        elif group_name == "advanced":
            setting_keys.extend([f"advanced.{key}" for key in advanced_settings_defaults.keys()])
        elif group_name == "mail":
            setting_keys.extend([f"mail.{key}" for key in mail_settings_defaults.keys()])

    configured_count = 0
    if setting_keys:
        configured_count = setting_model.objects.filter(key__in=setting_keys).count()

    return {
        "groups": list(module.settings_groups),
        "group_count": len(module.settings_groups),
        "configured_key_count": configured_count,
        "has_settings": bool(module.settings_groups),
    }


def resolve_module_documentation_url(module) -> str:
    if module.documentation_url:
        return module.documentation_url
    return f"/admin.html#/admin/docs?guide=module-development&module={module.module_id}"


def build_module_runtime_state(module) -> Dict[str, Any]:
    migration_state = "built-in"
    migration_label = "内置模块"
    if module.module_id == "core":
        migration_label = "核心底座"

    settings_entry_path = None
    if len(module.settings_groups) == 1:
        group_name = next(iter(module.settings_groups), "")
        settings_entry_path = {
            "basic": "/admin/basics",
            "appearance": "/admin/appearance",
            "mail": "/admin/mail",
            "advanced": "/admin/advanced",
        }.get(group_name)

    return {
        "migration_state": migration_state,
        "migration_label": migration_label,
        "boot_mode": "static",
        "boot_mode_label": "启动时静态注册",
        "settings_entry_path": settings_entry_path,
        "permissions_entry_path": "/admin/permissions" if module.permissions else "",
        "module_center_path": f"/admin/modules?module={module.module_id}",
        "debug_items": [
            {"key": "module_id", "label": "模块 ID", "value": module.module_id},
            {"key": "category", "label": "模块分类", "value": resolve_module_category_label(module.category)},
            {"key": "boot_mode", "label": "启动方式", "value": "启动时静态注册"},
            {"key": "migration", "label": "迁移状态", "value": migration_label},
        ],
    }


def serialize_module_definition(
    module,
    module_map: Dict[str, Any],
    *,
    resource_registry,
    runtime_dependency_summary_builder,
    setting_model,
    basic_settings_defaults: Dict[str, Any],
    appearance_settings_defaults: Dict[str, Any],
    advanced_settings_defaults: Dict[str, Any],
    mail_settings_defaults: Dict[str, Any],
) -> Dict[str, Any]:
    dependency_state = build_module_dependency_state(module, module_map)
    health_state = build_module_health_state(module, dependency_state)
    settings_overview = build_module_settings_overview(
        module,
        setting_model=setting_model,
        basic_settings_defaults=basic_settings_defaults,
        appearance_settings_defaults=appearance_settings_defaults,
        advanced_settings_defaults=advanced_settings_defaults,
        mail_settings_defaults=mail_settings_defaults,
    )
    runtime_state = build_module_runtime_state(module)
    resource_fields = [
        {
            "resource": definition.resource,
            "field": definition.field,
            "description": definition.description,
        }
        for definition in resource_registry.get_all_fields()
        if definition.module_id == module.module_id
    ]
    resource_definitions = [
        {
            "resource": definition.resource,
            "description": definition.description,
        }
        for definition in resource_registry.get_resources()
        if definition.module_id == module.module_id
    ]
    resource_relationships = [
        {
            "resource": definition.resource,
            "relationship": definition.relationship,
            "description": definition.description,
        }
        for definition in resource_registry.get_all_relationships()
        if definition.module_id == module.module_id
    ]
    runtime_dependency_summary = None
    if module.module_id == "core":
        runtime_dependency_summary = runtime_dependency_summary_builder()
        if runtime_dependency_summary["status"] != "healthy":
            health_state = {
                "status": "attention",
                "label": "需关注",
                "issues": [
                    *health_state["issues"],
                    *runtime_dependency_summary["issues"],
                ],
            }
    return {
        "id": module.module_id,
        "name": module.name,
        "description": module.description,
        "version": module.version,
        "category": module.category,
        "category_label": resolve_module_category_label(module.category),
        "is_core": module.is_core,
        "enabled": module.enabled,
        "dependencies": list(module.dependencies),
        "dependency_status": dependency_state["status"],
        "dependency_status_label": dependency_state["label"],
        "missing_dependencies": dependency_state["missing"],
        "disabled_dependencies": dependency_state["disabled"],
        "health_status": health_state["status"],
        "health_status_label": health_state["label"],
        "health_issues": health_state["issues"],
        "capabilities": list(module.capabilities),
        "settings": settings_overview,
        "documentation_url": resolve_module_documentation_url(module),
        "runtime": runtime_state,
        "notification_types": [
            {
                "code": notification_type.code,
                "label": notification_type.label,
                "description": notification_type.description,
                "icon": notification_type.icon,
                "navigation_scope": notification_type.navigation_scope,
                "preference_key": notification_type.preference_key,
                "preference_label": notification_type.preference_label,
                "preference_description": notification_type.preference_description,
                "preference_default_enabled": notification_type.preference_default_enabled,
            }
            for notification_type in module.notification_types
        ],
        "user_preferences": [
            {
                "key": preference.key,
                "label": preference.label,
                "description": preference.description,
                "category": preference.category,
                "default_value": preference.default_value,
            }
            for preference in module.user_preferences
        ],
        "language_packs": [
            {
                "code": language_pack.code,
                "label": language_pack.label,
                "native_label": language_pack.native_label,
                "description": language_pack.description,
                "is_default": language_pack.is_default,
            }
            for language_pack in module.language_packs
        ],
        "event_listeners": [
            {
                "event": listener.event,
                "listener": listener.listener,
                "description": listener.description,
            }
            for listener in module.event_listeners
        ],
        "post_types": [
            {
                "code": post_type.code,
                "label": post_type.label,
                "description": post_type.description,
                "icon": post_type.icon,
                "is_default": post_type.is_default,
                "is_stream_visible": post_type.is_stream_visible,
                "counts_toward_discussion": post_type.counts_toward_discussion,
                "counts_toward_user": post_type.counts_toward_user,
                "searchable": post_type.searchable,
            }
            for post_type in module.post_types
        ],
        "search_filters": [
            {
                "code": search_filter.code,
                "label": search_filter.label,
                "target": search_filter.target,
                "syntax": search_filter.syntax,
                "description": search_filter.description,
            }
            for search_filter in module.search_filters
        ],
        "discussion_sorts": [
            {
                "code": discussion_sort.code,
                "label": discussion_sort.label,
                "description": discussion_sort.description,
                "icon": discussion_sort.icon,
                "is_default": discussion_sort.is_default,
                "toolbar_visible": discussion_sort.toolbar_visible,
            }
            for discussion_sort in module.discussion_sorts
        ],
        "discussion_list_filters": [
            {
                "code": discussion_list_filter.code,
                "label": discussion_list_filter.label,
                "description": discussion_list_filter.description,
                "icon": discussion_list_filter.icon,
                "is_default": discussion_list_filter.is_default,
                "requires_authenticated_user": discussion_list_filter.requires_authenticated_user,
                "sidebar_visible": discussion_list_filter.sidebar_visible,
                "route_path": discussion_list_filter.route_path,
            }
            for discussion_list_filter in module.discussion_list_filters
        ],
        "resource_definitions": resource_definitions,
        "resource_relationships": resource_relationships,
        "resource_fields": resource_fields,
        "runtime_dependency_summary": runtime_dependency_summary,
        "permissions": [
            {
                "code": permission.code,
                "label": permission.label,
                "section": permission.section,
                "section_label": permission.section_label,
                "icon": permission.icon,
                "description": permission.description,
                "required_permissions": list(permission.required_permissions),
                "aliases": list(permission.aliases),
            }
            for permission in module.permissions
        ],
        "admin_pages": [
            {
                "path": page.path,
                "label": page.label,
                "icon": page.icon,
                "nav_section": page.nav_section,
                "description": page.description,
                "settings_group": page.settings_group,
            }
            for page in module.admin_pages
        ],
        "registration_counts": {
            "permissions": len(module.permissions),
            "admin_pages": len(module.admin_pages),
            "notification_types": len(module.notification_types),
            "user_preferences": len(module.user_preferences),
            "language_packs": len(module.language_packs),
            "event_listeners": len(module.event_listeners),
            "post_types": len(module.post_types),
            "search_filters": len(module.search_filters),
            "discussion_sorts": len(module.discussion_sorts),
            "discussion_list_filters": len(module.discussion_list_filters),
            "resource_definitions": len(resource_definitions),
            "resource_relationships": len(resource_relationships),
            "resource_fields": len(resource_fields),
            "settings_groups": len(module.settings_groups),
        },
    }


def build_module_category_summaries(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for module in modules:
        category_id = module["category"]
        group = grouped.setdefault(
            category_id,
            {
                "id": category_id,
                "label": module["category_label"],
                "module_count": 0,
                "enabled_count": 0,
                "attention_count": 0,
            },
        )
        group["module_count"] += 1
        if module["enabled"]:
            group["enabled_count"] += 1
        if module["health_status"] != "healthy":
            group["attention_count"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (
            0 if item["id"] == "core" else 1,
            item["label"],
        ),
    )
