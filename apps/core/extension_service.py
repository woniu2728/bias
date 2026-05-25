from __future__ import annotations

from django.db import transaction

from apps.core.audit import log_admin_action
from apps.core.extensions import get_extension_registry
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.models import ExtensionInstallation


class ExtensionService:
    @staticmethod
    def list_extensions():
        return get_extension_registry().get_extensions()

    @staticmethod
    def get_extension(extension_id: str):
        return get_extension_registry().get_extension(extension_id)

    @staticmethod
    @transaction.atomic
    def install_extension(extension_id: str, *, actor=None, request=None):
        registry = get_extension_registry()
        registry.load(force=True)
        extension = registry.get_extension(extension_id)

        if extension.source == "builtin-module":
            raise ExtensionStateError(
                f"内置扩展 {extension.id} 无需安装",
                code="extension_install_builtin_blocked",
                details={"extension_id": extension.id},
            )
        if extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 已安装",
                code="extension_install_already_installed",
                details={"extension_id": extension.id},
            )

        updated = ExtensionService._persist_installation_state(
            extension,
            installed=True,
            enabled=True,
            booted=True,
        )

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.install",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "enabled": updated.runtime.enabled,
                    "installed": updated.runtime.installed,
                    "source": updated.source,
                },
            )

        return updated

    @staticmethod
    @transaction.atomic
    def uninstall_extension(extension_id: str, *, actor=None, request=None):
        registry = get_extension_registry()
        registry.load(force=True)
        extension = registry.get_extension(extension_id)
        extensions = registry.get_extensions()

        if extension.source == "builtin-module":
            raise ExtensionStateError(
                f"内置扩展 {extension.id} 不支持卸载",
                code="extension_uninstall_builtin_blocked",
                details={"extension_id": extension.id},
            )
        if not extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装",
                code="extension_uninstall_not_installed",
                details={"extension_id": extension.id},
            )
        if extension.runtime.enabled:
            raise ExtensionStateError(
                f"请先停用扩展 {extension.id}，再执行卸载",
                code="extension_uninstall_enabled_blocked",
                details={"extension_id": extension.id},
            )

        ExtensionService._validate_disable(extension, extensions, uninstalling=True)
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=False,
            enabled=False,
            booted=False,
        )

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.uninstall",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "enabled": updated.runtime.enabled,
                    "installed": updated.runtime.installed,
                    "source": updated.source,
                },
            )

        return updated

    @staticmethod
    @transaction.atomic
    def set_extension_enabled(extension_id: str, enabled: bool, *, actor=None, request=None):
        registry = get_extension_registry()
        registry.load(force=True)
        extension = registry.get_extension(extension_id)
        extensions = registry.get_extensions()

        if enabled:
            ExtensionService._validate_enable(extension, extensions)
        else:
            ExtensionService._validate_disable(extension, extensions)

        updated = ExtensionService._persist_installation_state(
            extension,
            installed=True,
            enabled=bool(enabled),
            booted=bool(enabled),
        )

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.enable" if enabled else "admin.extension.disable",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "enabled": updated.runtime.enabled,
                    "source": updated.source,
                    "module_ids": list(updated.module_ids),
                },
            )

        return updated

    @staticmethod
    def _validate_enable(extension, extensions) -> None:
        if not extension.runtime.installed and extension.source == "filesystem":
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装",
                code="extension_enable_not_installed",
                details={"extension_id": extension.id},
            )

        extension_map = {item.id: item for item in extensions}
        missing_dependencies = []
        disabled_dependencies = []
        active_conflicts = []

        for dependency_id in extension.manifest.dependencies:
            dependency = extension_map.get(dependency_id)
            if dependency is None:
                missing_dependencies.append(dependency_id)
            elif not dependency.runtime.enabled:
                disabled_dependencies.append(dependency_id)

        for conflict_id in extension.manifest.conflicts:
            conflict = extension_map.get(conflict_id)
            if conflict is not None and conflict.runtime.enabled:
                active_conflicts.append(conflict_id)

        if missing_dependencies or disabled_dependencies or active_conflicts:
            issues = []
            if missing_dependencies:
                issues.append(f"缺少依赖扩展：{', '.join(missing_dependencies)}")
            if disabled_dependencies:
                issues.append(f"依赖扩展未启用：{', '.join(disabled_dependencies)}")
            if active_conflicts:
                issues.append(f"存在冲突扩展：{', '.join(active_conflicts)}")
            raise ExtensionStateError(
                f"无法启用扩展 {extension.id}。{'；'.join(issues)}",
                code="extension_enable_blocked",
                details={
                    "extension_id": extension.id,
                    "missing_dependencies": missing_dependencies,
                    "disabled_dependencies": disabled_dependencies,
                    "active_conflicts": active_conflicts,
                },
            )

    @staticmethod
    def _validate_disable(extension, extensions, *, uninstalling: bool = False) -> None:
        if extension.manifest.category == "core":
            raise ExtensionStateError(
                f"无法{'卸载' if uninstalling else '停用'}核心扩展 {extension.id}",
                code="extension_uninstall_core_blocked" if uninstalling else "extension_disable_core_blocked",
                details={"extension_id": extension.id},
            )

        blocking_dependents = []
        for candidate in extensions:
            if candidate.id == extension.id or not candidate.runtime.enabled:
                continue
            if extension.id in candidate.manifest.dependencies:
                blocking_dependents.append(candidate.id)

        if blocking_dependents:
            raise ExtensionStateError(
                f"无法{'卸载' if uninstalling else '停用'}扩展 {extension.id}。以下扩展仍依赖它：{', '.join(blocking_dependents)}",
                code="extension_uninstall_blocked" if uninstalling else "extension_disable_blocked",
                details={
                    "extension_id": extension.id,
                    "blocking_dependents": blocking_dependents,
                },
            )

    @staticmethod
    def _persist_installation_state(extension, *, installed: bool, enabled: bool, booted: bool):
        installation, _created = ExtensionInstallation.objects.get_or_create(
            extension_id=extension.id,
            defaults={
                "version": extension.version,
                "source": extension.source,
                "enabled": extension.runtime.enabled,
                "installed": extension.runtime.installed,
                "booted": extension.runtime.booted,
                "meta": {
                    "module_ids": list(extension.module_ids),
                    "settings_groups": list(extension.settings_groups),
                },
            },
        )

        installation.version = extension.version
        installation.source = extension.source
        installation.enabled = bool(enabled)
        installation.installed = bool(installed)
        installation.booted = bool(booted)
        installation.meta = {
            **dict(installation.meta or {}),
            "module_ids": list(extension.module_ids),
            "settings_groups": list(extension.settings_groups),
        }
        installation.save(update_fields=[
            "version",
            "source",
            "enabled",
            "installed",
            "booted",
            "meta",
            "updated_at",
        ])

        registry = get_extension_registry()
        registry.load(force=True)
        return registry.get_extension(extension.id)
