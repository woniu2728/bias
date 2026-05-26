from __future__ import annotations

from django.db import transaction

from apps.core.audit import log_admin_action
from apps.core.extensions import get_extension_registry
from apps.core.extensions.backend import run_extension_backend_hook
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.validation import resolve_bias_version_compatibility
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

        ExtensionService._validate_bias_compatibility(extension, action="install")
        migration_result = ExtensionService._run_install_migrations_if_declared(extension)
        install_result = ExtensionService._run_backend_hook(
            extension,
            "run_install",
            meta={"action": "install"},
        )

        backend_hooks = {"run_install": install_result}
        if migration_result is not None:
            backend_hooks["run_migrations"] = migration_result
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=True,
            enabled=True,
            booted=True,
            meta_updates={
                "backend_hooks": backend_hooks,
                "migration_execution": dict(migration_result or {}),
            },
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
        uninstall_result = ExtensionService._run_backend_hook(
            extension,
            "run_uninstall",
            meta={"action": "uninstall"},
        )
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=False,
            enabled=False,
            booted=False,
            meta_updates={"backend_hooks": {"run_uninstall": uninstall_result}},
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

        hook_name = "run_enable" if enabled else "run_disable"
        hook_result = ExtensionService._run_backend_hook(
            extension,
            hook_name,
            meta={"action": "enable" if enabled else "disable"},
        )
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=True,
            enabled=bool(enabled),
            booted=bool(enabled),
            meta_updates={"backend_hooks": {hook_name: hook_result}},
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
    @transaction.atomic
    def run_extension_runtime_hook(extension_id: str, hook_name: str, *, actor=None, request=None):
        registry = get_extension_registry()
        registry.load(force=True)
        extension = registry.get_extension(extension_id)

        runtime_action = next(
            (
                action for action in extension.manifest.runtime_actions
                if action.hook == hook_name
            ),
            None,
        )
        if runtime_action is None:
            raise ExtensionStateError(
                f"扩展 {extension.id} 未声明运行操作 {hook_name}",
                code="extension_runtime_hook_not_declared",
                details={"extension_id": extension.id, "hook": hook_name},
            )

        if runtime_action.requires_installed and not extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装，无法执行 {hook_name}",
                code="extension_runtime_hook_requires_install",
                details={"extension_id": extension.id, "hook": hook_name},
            )
        if runtime_action.requires_enabled and not extension.runtime.enabled:
            raise ExtensionStateError(
                f"扩展 {extension.id} 未启用，无法执行 {hook_name}",
                code="extension_runtime_hook_requires_enable",
                details={"extension_id": extension.id, "hook": hook_name},
            )

        hook_result = ExtensionService._run_backend_hook(
            extension,
            hook_name,
            meta={"action": "runtime_hook", "hook": hook_name},
        )
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            meta_updates={"backend_hooks": {hook_name: hook_result}},
        )

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.runtime_hook",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "hook": hook_name,
                    "status": hook_result.get("status"),
                },
            )

        return updated

    @staticmethod
    @transaction.atomic
    def run_extension_migrations(extension_id: str, *, actor=None, request=None):
        registry = get_extension_registry()
        registry.load(force=True)
        extension = registry.get_extension(extension_id)

        if extension.source == "builtin-module":
            raise ExtensionStateError(
                f"内置扩展 {extension.id} 无需执行独立迁移",
                code="extension_migrations_builtin_blocked",
                details={"extension_id": extension.id},
            )
        if not extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装，无法执行迁移",
                code="extension_migrations_not_installed",
                details={"extension_id": extension.id},
            )
        if not str(extension.manifest.migration_namespace or "").strip():
            raise ExtensionStateError(
                f"扩展 {extension.id} 未声明迁移命名空间",
                code="extension_migrations_not_declared",
                details={"extension_id": extension.id},
            )

        hook_result = ExtensionService._run_backend_hook(
            extension,
            "run_migrations",
            meta={"action": "migrate"},
        )
        updated = ExtensionService._persist_installation_state(
            extension,
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            meta_updates={
                "backend_hooks": {"run_migrations": hook_result},
                "migration_execution": dict(hook_result or {}),
            },
        )

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.migrations",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "status": hook_result.get("status"),
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

        ExtensionService._validate_bias_compatibility(extension, action="enable")

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
    def _validate_bias_compatibility(extension, *, action: str) -> None:
        compatibility = resolve_bias_version_compatibility(extension.manifest)
        if compatibility["compatible"]:
            return

        action_label = "安装" if action == "install" else "启用"
        raise ExtensionStateError(
            f"无法{action_label}扩展 {extension.id}。{compatibility['message']}",
            code=f"extension_{action}_incompatible_bias_version",
            details={
                "extension_id": extension.id,
                "current_bias_version": compatibility["current_version"],
                "required_bias_version": compatibility["required_range"],
            },
        )

    @staticmethod
    def _run_install_migrations_if_declared(extension) -> dict | None:
        if not str(extension.manifest.migration_namespace or "").strip():
            return None
        return ExtensionService._run_backend_hook(
            extension,
            "run_migrations",
            meta={"action": "install_migrations"},
        )

    @staticmethod
    def _persist_installation_state(
        extension,
        *,
        installed: bool,
        enabled: bool,
        booted: bool,
        meta_updates: dict | None = None,
    ):
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
        installation.meta = ExtensionService._merge_installation_meta(
            installation.meta,
            {
            "module_ids": list(extension.module_ids),
            "settings_groups": list(extension.settings_groups),
                **dict(meta_updates or {}),
            },
        )
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

    @staticmethod
    def _run_backend_hook(extension, hook_name: str, *, meta: dict | None = None) -> dict:
        return run_extension_backend_hook(
            extension,
            hook_name,
            meta=meta,
        )

    @staticmethod
    def _merge_installation_meta(current_meta: dict | None, updates: dict | None) -> dict:
        merged = dict(current_meta or {})
        for key, value in dict(updates or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {
                    **dict(merged[key]),
                    **value,
                }
            else:
                merged[key] = value
        return merged
