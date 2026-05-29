from __future__ import annotations

from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionCompatibilityDefinition,
    ExtensionDefinition,
    ExtensionDistributionDefinition,
    ExtensionLifecycleDefinition,
    ExtensionLifecyclePhaseDefinition,
    ExtensionManifest,
    ExtensionRuntimeState,
    ExtensionSecurityDefinition,
)
from apps.core.forum_registry_types import ForumModuleDefinition


def adapt_builtin_module_to_extension(module: ForumModuleDefinition) -> ExtensionDefinition:
    lifecycle = module.lifecycle
    phases = tuple(
        ExtensionLifecyclePhaseDefinition(
            key=item.key,
            label=item.label,
            description=item.description,
            optional=item.optional,
        )
        for item in lifecycle.phases
    )

    category = "core" if module.is_core else module.category
    module_id = module.module_id

    manifest = ExtensionManifest(
        id=module_id,
        name=module.name,
        version=module.version,
        description=module.description,
        icon=_resolve_builtin_module_icon(module),
        category=category,
        documentation_url=module.documentation_url,
        dependencies=tuple(module.dependencies),
        provides=tuple(module.capabilities),
        frontend_admin_entry=_resolve_builtin_frontend_admin_entry(module),
        settings_pages=_resolve_builtin_settings_pages(module),
        permissions_pages=_resolve_builtin_permissions_pages(module),
        operations_pages=_resolve_builtin_operations_pages(module),
        admin_actions=_build_builtin_admin_actions(module),
        compatibility=ExtensionCompatibilityDefinition(
            bias_version="^1.0.0",
            api_version="1.0",
            api_stability="stable" if module.is_core else "internal",
            api_stability_label="稳定" if module.is_core else "内部",
            breaking_change_policy="跟随 Bias 主版本升级节奏评估兼容性。",
        ),
        security=ExtensionSecurityDefinition(
            policy_url="",
            support_email="",
            capabilities_notice="内置扩展随平台发布，不单独提供第三方安全边界。",
        ),
        distribution=ExtensionDistributionDefinition(
            channel="bundled",
            channel_label="随平台内置",
        ),
        source="builtin-module",
        path="apps/core/forum_registry_builtin.py",
    )

    runtime = ExtensionRuntimeState(
        installed=True,
        enabled=bool(module.enabled),
        booted=bool(module.enabled),
        healthy=True,
        migration_state="builtin",
        migration_label="核心底座" if module.is_core else "内置模块",
        dependency_state="healthy",
        dependency_state_label="依赖正常",
        runtime_issues=(),
    )

    return ExtensionDefinition(
        manifest=manifest,
        runtime=runtime,
        lifecycle=ExtensionLifecycleDefinition(
            registration_mode=lifecycle.registration_mode,
            registration_mode_label=lifecycle.registration_mode_label,
            readiness_probe=lifecycle.readiness_probe,
            supports_disable=lifecycle.supports_disable,
            supports_teardown=lifecycle.supports_teardown,
            phases=phases,
        ),
        capabilities=tuple(module.capabilities),
        module_ids=(module_id,),
        source="builtin-module",
        admin_pages=tuple(page.path for page in module.admin_pages),
        settings_groups=tuple(module.settings_groups),
    )


def _resolve_builtin_module_icon(module: ForumModuleDefinition) -> str:
    if module.is_core:
        return "fas fa-shield-alt"
    if module.category == "infrastructure":
        return "fas fa-server"
    if module.category == "moderation":
        return "fas fa-gavel"
    if module.category == "communication":
        return "fas fa-bell"
    return "fas fa-puzzle-piece"


def _resolve_builtin_frontend_admin_entry(module: ForumModuleDefinition) -> str:
    builtin_entries = {
        "core": "builtin:core",
        "discussions": "builtin:discussions",
        "posts": "builtin:posts",
        "approval": "builtin:approval",
        "tags": "builtin:tags",
        "flags": "builtin:flags",
        "users": "builtin:users",
        "notifications": "builtin:notifications",
        "mentions": "builtin:mentions",
        "subscriptions": "builtin:subscriptions",
        "realtime": "builtin:realtime",
        "likes": "builtin:likes",
        "tag-stats": "builtin:tag-stats",
    }
    return builtin_entries.get(module.module_id, "")


def _resolve_builtin_settings_pages(module: ForumModuleDefinition) -> tuple[str, ...]:
    if module.module_id == "tags":
        return (f"/admin/extensions/{module.module_id}/settings",)
    if module.module_id == "core":
        return (f"/admin/extensions/{module.module_id}/settings",)
    return tuple(page.path for page in module.admin_pages if page.settings_group)


def _resolve_builtin_permissions_pages(module: ForumModuleDefinition) -> tuple[str, ...]:
    if module.module_id == "core":
        return (f"/admin/extensions/{module.module_id}/permissions",)
    if not module.permissions:
        return ()
    return (f"/admin/extensions/{module.module_id}/permissions",)


def _resolve_builtin_operations_pages(module: ForumModuleDefinition) -> tuple[str, ...]:
    hosted_operations_modules = {
        "discussions",
        "posts",
        "approval",
        "flags",
        "users",
        "notifications",
        "mentions",
        "subscriptions",
        "realtime",
        "likes",
        "tag-stats",
    }
    if module.module_id == "core":
        return (f"/admin/extensions/{module.module_id}/operations",)
    if module.module_id == "tags":
        return ()
    if module.module_id in hosted_operations_modules:
        return (f"/admin/extensions/{module.module_id}/operations",)
    return tuple(page.path for page in module.admin_pages if not page.settings_group)


def _build_builtin_admin_actions(module: ForumModuleDefinition) -> tuple[ExtensionAdminActionDefinition, ...]:
    settings_page = next(iter(_resolve_builtin_settings_pages(module)), "")
    permissions_page = next(iter(_resolve_builtin_permissions_pages(module)), "")
    operations_page = next(iter(_resolve_builtin_operations_pages(module)), "")

    actions: list[ExtensionAdminActionDefinition] = [
        ExtensionAdminActionDefinition(
            key="details",
            label="查看详情",
            kind="route",
            target=f"/admin/extensions/{module.module_id}",
            icon="fas fa-arrow-right",
            tone="primary",
            order=10,
        )
    ]

    if settings_page:
        actions.append(ExtensionAdminActionDefinition(
            key="settings",
            label="设置",
            kind="route",
            target=settings_page,
            icon="fas fa-sliders-h",
            tone="default",
            requires_enabled=True,
            order=20,
        ))

    if permissions_page and permissions_page != settings_page:
        actions.append(ExtensionAdminActionDefinition(
            key="permissions",
            label="权限",
            kind="route",
            target=permissions_page,
            icon="fas fa-user-shield",
            tone="default",
            requires_enabled=True,
            order=30,
        ))

    if operations_page and operations_page not in {settings_page, permissions_page}:
        actions.append(ExtensionAdminActionDefinition(
            key="operations",
            label="操作",
            kind="route",
            target=operations_page,
            icon="fas fa-screwdriver-wrench",
            tone="default",
            requires_enabled=True,
            order=40,
        ))

    if module.documentation_url:
        actions.append(ExtensionAdminActionDefinition(
            key="documentation",
            label="文档",
            kind="link",
            target=module.documentation_url,
            icon="fas fa-book",
            tone="subtle",
            order=50,
        ))

    return tuple(actions)
