from __future__ import annotations

from apps.core.extensions.types import (
    ExtensionDefinition,
    ExtensionLifecycleDefinition,
    ExtensionLifecyclePhaseDefinition,
    ExtensionManifest,
    ExtensionRuntimeState,
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
        permissions_pages=("/admin/permissions",) if module.permissions else (),
        operations_pages=_resolve_builtin_operations_pages(module),
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
        "tags": "builtin:tags",
    }
    return builtin_entries.get(module.module_id, "")


def _resolve_builtin_settings_pages(module: ForumModuleDefinition) -> tuple[str, ...]:
    if module.module_id == "tags":
        return (f"/admin/extensions/{module.module_id}/settings",)
    return tuple(page.path for page in module.admin_pages if page.settings_group)


def _resolve_builtin_operations_pages(module: ForumModuleDefinition) -> tuple[str, ...]:
    if module.module_id == "tags":
        return ()
    return tuple(page.path for page in module.admin_pages if not page.settings_group)
