from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Tuple


@dataclass(frozen=True)
class ExtensionLifecyclePhaseDefinition:
    key: str
    label: str
    description: str = ""
    optional: bool = False


DEFAULT_EXTENSION_LIFECYCLE_PHASES: Tuple[ExtensionLifecyclePhaseDefinition, ...] = (
    ExtensionLifecyclePhaseDefinition(
        key="discover",
        label="discover",
        description="发现扩展清单并解析扩展元数据。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="register",
        label="register",
        description="注册扩展元数据与能力声明。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="boot",
        label="boot",
        description="接入运行时依赖、监听器、前端资源和后台入口。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="ready",
        label="ready",
        description="依赖与健康检查通过后，对外提供稳定能力。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="disable",
        label="disable",
        description="停用扩展并撤销可撤销能力。",
        optional=True,
    ),
    ExtensionLifecyclePhaseDefinition(
        key="teardown",
        label="teardown",
        description="卸载、迁移或重建时回收扩展运行时资源。",
        optional=True,
    ),
)


@dataclass(frozen=True)
class ExtensionLifecycleDefinition:
    registration_mode: str = "static"
    registration_mode_label: str = "启动时静态注册"
    readiness_probe: str = "扩展依赖校验与运行时健康摘要"
    supports_disable: bool = False
    supports_teardown: bool = False
    phases: Tuple[ExtensionLifecyclePhaseDefinition, ...] = DEFAULT_EXTENSION_LIFECYCLE_PHASES


@dataclass(frozen=True)
class ExtensionManifest:
    id: str
    name: str
    version: str
    description: str = ""
    icon: str = "fas fa-puzzle-piece"
    category: str = "feature"
    authors: Tuple[str, ...] = ()
    homepage: str = ""
    documentation_url: str = ""
    dependencies: Tuple[str, ...] = ()
    optional_dependencies: Tuple[str, ...] = ()
    conflicts: Tuple[str, ...] = ()
    provides: Tuple[str, ...] = ()
    backend_entry: str = ""
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    settings_pages: Tuple[str, ...] = ()
    permissions_pages: Tuple[str, ...] = ()
    operations_pages: Tuple[str, ...] = ()
    migration_namespace: str = ""
    source: str = "filesystem"
    path: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtensionRuntimeState:
    installed: bool = True
    enabled: bool = True
    booted: bool = True
    healthy: bool = True
    migration_state: str = "builtin"
    migration_label: str = "内置扩展"
    dependency_state: str = "healthy"
    dependency_state_label: str = "依赖正常"
    runtime_issues: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionDefinition:
    manifest: ExtensionManifest
    runtime: ExtensionRuntimeState = ExtensionRuntimeState()
    lifecycle: ExtensionLifecycleDefinition = ExtensionLifecycleDefinition()
    capabilities: Tuple[str, ...] = ()
    module_ids: Tuple[str, ...] = ()
    source: str = "filesystem"
    admin_pages: Tuple[str, ...] = ()
    settings_groups: Tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def description(self) -> str:
        return self.manifest.description


@dataclass(frozen=True)
class ExtensionDiscoveryResult:
    manifest: ExtensionManifest
    path: Path
