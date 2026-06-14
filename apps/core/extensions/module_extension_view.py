from __future__ import annotations

from types import SimpleNamespace

from apps.core.extensions.types import (
    ExtensionCompatibilityDefinition,
    ExtensionDistributionDefinition,
    ExtensionLifecycleDefinition,
    ExtensionLifecyclePhaseDefinition,
    ExtensionRuntimeState,
    ExtensionSecurityDefinition,
)


def resolve_module_extension_definition(module):
    try:
        from apps.core.extensions.registry import get_extension_registry

        extension = get_extension_registry().get_extension(module.module_id)
        if extension is not None:
            return extension
    except Exception:
        pass
    return _build_core_module_view(module)


def resolve_module_documentation_url(module) -> str:
    if module.documentation_url:
        return module.documentation_url
    return f"/admin.html#/admin/docs?guide=module-development&module={module.module_id}"


def _build_core_module_view(module):
    settings_pages = tuple(
        item
        for item in (
            _settings_group_entry_path(group_name)
            for group_name in module.settings_groups
        )
        if item
    )
    runtime = ExtensionRuntimeState(
        installed=True,
        enabled=bool(module.enabled),
        booted=bool(module.enabled),
        healthy=True,
        migration_state="core",
        migration_label="核心底座" if module.is_core else "核心模块",
        dependency_state="healthy",
        dependency_state_label="依赖正常",
        runtime_issues=(),
    )
    lifecycle = _build_extension_lifecycle_from_module(module)
    manifest = SimpleNamespace(
        id=module.module_id,
        name=module.name,
        version=module.version,
        description=module.description,
        icon=next((page.icon for page in module.admin_pages if page.icon), "fas fa-cube"),
        category=module.category,
        dependencies=tuple(module.dependencies),
        optional_dependencies=(),
        conflicts=(),
        provides=tuple(module.capabilities),
        backend_entry="",
        frontend_admin_entry="",
        frontend_forum_entry="",
        settings_pages=settings_pages,
        permissions_pages=(),
        operations_pages=(),
        admin_actions=(),
        compatibility=ExtensionCompatibilityDefinition(
            api_stability="stable",
            api_stability_label="稳定",
            breaking_change_policy="核心能力随 Bias 版本发布节奏演进。",
        ),
        security=ExtensionSecurityDefinition(
            capabilities_notice="核心底座提供论坛基础配置、权限、外观、搜索、资源序列化和运行时诊断能力。",
        ),
        distribution=ExtensionDistributionDefinition(
            channel="bundled",
            channel_label="随平台内置",
        ),
        runtime_actions=(),
        settings_schema=(),
        django_app_config="",
        django_app_label="",
        source="core-module",
        path="",
        extra={},
        documentation_url=resolve_module_documentation_url(module),
    )
    return SimpleNamespace(
        id=module.module_id,
        name=module.name,
        version=module.version,
        description=module.description,
        manifest=manifest,
        source="core-module",
        module_ids=(module.module_id,),
        settings_groups=tuple(module.settings_groups),
        admin_pages=tuple(page.path for page in module.admin_pages),
        admin_actions=(),
        settings_pages=settings_pages,
        permissions_pages=(),
        operations_pages=(),
        runtime=runtime,
        lifecycle=lifecycle,
        frontend_admin_entry="",
        frontend_forum_entry="",
        permissions=(),
        settings_schema=(),
        manifest_runtime_actions=(),
    )


def _build_extension_lifecycle_from_module(module):
    lifecycle = getattr(module, "lifecycle", None)
    phases = tuple(
        ExtensionLifecyclePhaseDefinition(
            key=getattr(phase, "key", ""),
            label=getattr(phase, "label", ""),
            description=getattr(phase, "description", ""),
            optional=bool(getattr(phase, "optional", False)),
        )
        for phase in getattr(lifecycle, "phases", ()) or ()
    )
    return ExtensionLifecycleDefinition(
        registration_mode=getattr(lifecycle, "registration_mode", "static"),
        registration_mode_label=getattr(lifecycle, "registration_mode_label", "启动时静态注册"),
        readiness_probe=getattr(lifecycle, "readiness_probe", "依赖校验与健康摘要"),
        supports_disable=bool(getattr(lifecycle, "supports_disable", False)),
        supports_teardown=bool(getattr(lifecycle, "supports_teardown", False)),
        phases=phases or ExtensionLifecycleDefinition().phases,
    )


def _settings_group_entry_path(group_name: str) -> str:
    return {
        "basic": "/admin/basics",
        "appearance": "/admin/appearance",
        "mail": "/admin/mail",
        "advanced": "/admin/advanced",
    }.get(str(group_name or "").strip(), "")
