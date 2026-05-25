from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError

from apps.core.extensions.builtin_adapter import adapt_builtin_module_to_extension
from apps.core.extensions.exceptions import ExtensionNotFoundError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.types import (
    ExtensionDefinition,
    ExtensionRuntimeActionDefinition,
    ExtensionRuntimeState,
)
from apps.core.forum_registry import get_forum_registry
from apps.core.models import ExtensionInstallation


class ExtensionRegistry:
    def __init__(self, *, extensions_path: Path | None = None):
        self.extensions_path = Path(extensions_path or Path(settings.BASE_DIR) / "extensions")
        self._extensions: dict[str, ExtensionDefinition] = {}
        self._loaded = False

    def load(self, *, force: bool = False) -> None:
        if self._loaded and not force:
            return

        self._extensions = {}

        loader = ExtensionManifestLoader(self.extensions_path)
        for result in loader.discover():
            self._extensions[result.manifest.id] = self._apply_installation_state(ExtensionDefinition(
                manifest=result.manifest,
                source="filesystem",
            ))

        for module in get_forum_registry().get_modules():
            self._extensions.setdefault(
                module.module_id,
                self._apply_installation_state(adapt_builtin_module_to_extension(module)),
            )

        self._loaded = True

    def get_extensions(self) -> list[ExtensionDefinition]:
        self.load()
        return sorted(
            self._extensions.values(),
            key=lambda item: (
                int(item.manifest.category != "core"),
                item.manifest.category,
                item.name.lower(),
                item.id,
            ),
        )

    def get_extension(self, extension_id: str) -> ExtensionDefinition:
        self.load()
        normalized = str(extension_id or "").strip()
        if normalized in self._extensions:
            return self._extensions[normalized]
        raise ExtensionNotFoundError(f"扩展不存在: {normalized}")

    def _apply_installation_state(self, definition: ExtensionDefinition) -> ExtensionDefinition:
        try:
            installation = ExtensionInstallation.objects.filter(extension_id=definition.id).first()
        except (OperationalError, ProgrammingError):
            return self._with_runtime_actions(definition)
        if installation is None:
            return self._with_runtime_actions(self._build_uninstalled_definition(definition))

        runtime = ExtensionRuntimeState(
            installed=installation.installed,
            enabled=installation.enabled,
            booted=installation.booted,
            healthy=definition.runtime.healthy,
            status_key=_build_extension_status_key(installation.installed, installation.enabled),
            status_label=_build_extension_status_label(installation.installed, installation.enabled),
            migration_state=definition.runtime.migration_state,
            migration_label=definition.runtime.migration_label,
            dependency_state=definition.runtime.dependency_state,
            dependency_state_label=definition.runtime.dependency_state_label,
            runtime_issues=definition.runtime.runtime_issues,
            runtime_actions=(),
        )

        return self._with_runtime_actions(ExtensionDefinition(
            manifest=definition.manifest,
            runtime=runtime,
            lifecycle=definition.lifecycle,
            capabilities=definition.capabilities,
            module_ids=definition.module_ids,
            source=definition.source,
            admin_pages=definition.admin_pages,
            settings_groups=definition.settings_groups,
        ))

    def _build_uninstalled_definition(self, definition: ExtensionDefinition) -> ExtensionDefinition:
        if definition.source == "builtin-module":
            return definition

        return ExtensionDefinition(
            manifest=definition.manifest,
            runtime=ExtensionRuntimeState(
                installed=False,
                enabled=False,
                booted=False,
                healthy=definition.runtime.healthy,
                status_key="pending_install",
                status_label="待安装",
                migration_state="pending",
                migration_label="待安装",
                dependency_state=definition.runtime.dependency_state,
                dependency_state_label=definition.runtime.dependency_state_label,
                runtime_issues=definition.runtime.runtime_issues,
                runtime_actions=(),
            ),
            lifecycle=definition.lifecycle,
            capabilities=definition.capabilities,
            module_ids=definition.module_ids,
            source=definition.source,
            admin_pages=definition.admin_pages,
            settings_groups=definition.settings_groups,
        )

    def _with_runtime_actions(self, definition: ExtensionDefinition) -> ExtensionDefinition:
        return ExtensionDefinition(
            manifest=definition.manifest,
            runtime=ExtensionRuntimeState(
                installed=definition.runtime.installed,
                enabled=definition.runtime.enabled,
                booted=definition.runtime.booted,
                healthy=definition.runtime.healthy,
                status_key=definition.runtime.status_key,
                status_label=definition.runtime.status_label,
                migration_state=definition.runtime.migration_state,
                migration_label=definition.runtime.migration_label,
                dependency_state=definition.runtime.dependency_state,
                dependency_state_label=definition.runtime.dependency_state_label,
                runtime_issues=definition.runtime.runtime_issues,
                runtime_actions=_build_runtime_actions(definition),
            ),
            lifecycle=definition.lifecycle,
            capabilities=definition.capabilities,
            module_ids=definition.module_ids,
            source=definition.source,
            admin_pages=definition.admin_pages,
            settings_groups=definition.settings_groups,
        )


_registry: ExtensionRegistry | None = None


def get_extension_registry() -> ExtensionRegistry:
    global _registry
    if _registry is None:
        _registry = ExtensionRegistry()
    return _registry


def _build_extension_status_key(installed: bool, enabled: bool) -> str:
    if not installed:
        return "pending_install"
    if enabled:
        return "active"
    return "disabled"


def _build_extension_status_label(installed: bool, enabled: bool) -> str:
    if not installed:
        return "待安装"
    if enabled:
        return "已启用"
    return "已停用"


def _build_runtime_actions(definition: ExtensionDefinition) -> tuple[ExtensionRuntimeActionDefinition, ...]:
    if definition.source == "builtin-module":
        if definition.runtime.enabled:
            return (
                ExtensionRuntimeActionDefinition(
                    key="disable",
                    label="停用扩展",
                    action="disable",
                    tone="danger",
                    confirm_title="停用扩展",
                    confirm_message=f"确定停用 {definition.name} 吗？相关后台入口和运行能力会立即隐藏。",
                    confirm_text="停用",
                    success_message="扩展已停用。",
                    requires_installed=True,
                    order=20,
                ),
            )
        return (
            ExtensionRuntimeActionDefinition(
                key="enable",
                label="启用扩展",
                action="enable",
                tone="primary",
                confirm_title="启用扩展",
                confirm_message=f"确定启用 {definition.name} 吗？依赖校验通过后会立即恢复能力。",
                confirm_text="启用",
                success_message="扩展已启用。",
                requires_installed=True,
                order=10,
            ),
        )

    if not definition.runtime.installed:
        return (
            ExtensionRuntimeActionDefinition(
                key="install",
                label="安装扩展",
                action="install",
                tone="primary",
                confirm_title="安装扩展",
                confirm_message=f"确定安装 {definition.name} 吗？当前版本会登记为已安装并默认启用。",
                confirm_text="安装",
                success_message="扩展已安装并启用。",
                order=10,
            ),
        )

    actions = []
    if definition.runtime.enabled:
        actions.append(ExtensionRuntimeActionDefinition(
            key="disable",
            label="停用扩展",
            action="disable",
            tone="danger",
            confirm_title="停用扩展",
            confirm_message=f"确定停用 {definition.name} 吗？相关后台入口和运行能力会立即隐藏。",
            confirm_text="停用",
            success_message="扩展已停用。",
            requires_installed=True,
            order=20,
        ))
    else:
        actions.append(ExtensionRuntimeActionDefinition(
            key="enable",
            label="启用扩展",
            action="enable",
            tone="primary",
            confirm_title="启用扩展",
            confirm_message=f"确定启用 {definition.name} 吗？依赖校验通过后会立即恢复能力。",
            confirm_text="启用",
            success_message="扩展已启用。",
            requires_installed=True,
            order=10,
        ))
        actions.append(ExtensionRuntimeActionDefinition(
            key="uninstall",
            label="卸载扩展",
            action="uninstall",
            tone="danger",
            confirm_title="卸载扩展",
            confirm_message=f"确定卸载 {definition.name} 吗？当前只会移除安装登记，不会自动回滚数据库迁移。",
            confirm_text="卸载",
            success_message="扩展已卸载。",
            requires_installed=True,
            order=30,
        ))

    return tuple(actions)
