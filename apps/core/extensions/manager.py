from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.core.extensions.backend import run_extension_backend_hook
from apps.core.extensions.assets import publish_extension_assets, unpublish_extension_assets
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.event_bus import get_extension_event_bus
from apps.core.extensions.events import (
    ExtensionDisabledEvent,
    ExtensionDisablingEvent,
    ExtensionEnabledEvent,
    ExtensionEnablingEvent,
    ExtensionInstalledEvent,
    ExtensionPackagesSyncedEvent,
    ExtensionUninstalledEvent,
)
from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners
from apps.core.extensions.lifecycle import reset_extension_runtime_state
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.migration_repository import ExtensionMigrationRepository
from apps.core.extensions.migrations import (
    has_django_extension_migrations,
    run_extension_migrations as sync_django_extension_migrations,
)
from apps.core.extensions.product import (
    get_extension_protected_reason,
    is_extension_auto_enabled,
    is_extension_auto_installed,
    is_extension_protected,
    is_product_visible_extension,
)
from apps.core.extensions.recovery import is_extension_allowed_in_safe_mode
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.validation import resolve_bias_version_compatibility
from apps.core.extensions.types import (
    ExtensionAssembly,
    ExtensionBootPlan,
    ExtensionRuntimeActionDefinition,
    ExtensionRuntimeState,
)
from apps.core.models import ExtensionInstallation, Setting


EXTENSION_PACKAGE_LOCK_SETTING = "extensions.package_lock"
EXTENSION_ENABLED_ORDER_SETTING = "extensions_enabled_order"


class ExtensionManager:
    def __init__(self, *, extensions_path: Path | None = None):
        self._uses_default_extensions_path = extensions_path is None
        self.extensions_path = Path(extensions_path or Path(settings.BASE_DIR) / "extensions")
        self._extensions: dict[str, Extension] = {}
        self._loaded = False
        self._loading = False

    def invalidate(self) -> None:
        if self._uses_default_extensions_path:
            self.extensions_path = Path(settings.BASE_DIR) / "extensions"
        self._extensions = {}
        self._loaded = False

    def load(self, *, force: bool = False) -> None:
        if self._loaded and not force:
            return
        if self._loading:
            return

        self._loading = True
        loader = ExtensionManifestLoader(self.extensions_path)
        extensions: dict[str, Extension] = {}

        try:
            for manifest in loader.discover_manifests():
                extension = Extension.from_manifest(manifest)
                extensions[extension.id] = self._apply_installation_state(extension)

            self._extensions = extensions
            self._loaded = True
        finally:
            self._loading = False

    def get_extensions(self) -> list[Extension]:
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

    def get_extension(self, extension_id: str) -> Extension:
        self.load()
        normalized = str(extension_id or "").strip()
        if normalized in self._extensions:
            return self._extensions[normalized]
        raise ExtensionNotFoundError(f"扩展不存在: {normalized}")

    def get_loaded_extension(self, extension_id: str) -> Extension:
        extension = self.get_extension(extension_id)
        if extension.source != "filesystem":
            raise ExtensionNotFoundError(f"扩展不存在: {extension_id}")
        return extension

    @transaction.atomic
    def install_extension(self, extension_id: str) -> Extension:
        self.load(force=True)
        extension = self.get_extension(extension_id)

        if extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 已安装",
                code="extension_install_already_installed",
                details={"extension_id": extension.id},
        )

        self._validate_bias_compatibility(extension, action="install")
        self._dispatch_extension_lifecycle_event(ExtensionEnablingEvent(extension_id=extension.id))
        migration_result = self._run_install_migrations_if_declared(extension)
        migration_meta = self._build_migration_meta_updates(extension.id, migration_result)
        self._write_installation_state(
            extension,
            installed=True,
            enabled=False,
            booted=False,
            meta_updates={
                **migration_meta,
            },
        )
        install_result = self._run_lifecycle_extenders(
            extension,
            "install",
            meta={"action": "install"},
            target_runtime={"installed": True, "enabled": False, "booted": False},
        )
        self._write_installation_state(
            extension,
            installed=True,
            enabled=True,
            booted=True,
            meta_updates={
                **migration_meta,
            },
        )
        enable_result = self._run_lifecycle_extenders(
            extension,
            "enable",
            meta={"action": "install_enable"},
            target_runtime={"installed": True, "enabled": True, "booted": True},
        )
        asset_result = publish_extension_assets(extension)

        backend_hooks = {
            "run_install": install_result,
            "run_enable": enable_result,
            "publish_assets": asset_result,
        }
        if migration_result is not None:
            backend_hooks["run_migrations"] = migration_result
        return self._persist_installation_state(
            extension,
            installed=True,
            enabled=True,
            booted=True,
            lifecycle_events=(
                ExtensionInstalledEvent(extension_id=extension.id),
                ExtensionEnabledEvent(extension_id=extension.id),
            ),
            meta_updates={
                "backend_hooks": backend_hooks,
                **migration_meta,
            },
        )

    @transaction.atomic
    def uninstall_extension(self, extension_id: str) -> Extension:
        self.load(force=True)
        extension = self.get_extension(extension_id)
        extensions = self.get_extensions()

        if not extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装",
                code="extension_uninstall_not_installed",
                details={"extension_id": extension.id},
            )

        self._validate_disable(extension, extensions, uninstalling=True)
        disable_result = None
        disable_asset_result = None
        if extension.runtime.enabled:
            disabled_extension = self._disable_extension(extension, extensions)
            extension = disabled_extension
            disable_result = dict(extension.runtime.backend_hooks.get("run_disable") or {})
            disable_asset_result = dict(extension.runtime.backend_hooks.get("unpublish_assets") or {})

        migration_result = self._run_uninstall_migrations_if_declared(extension)
        migration_meta = self._build_migration_meta_updates(extension.id, migration_result, direction="down")
        self._write_installation_state(
            extension,
            installed=False,
            enabled=False,
            booted=False,
            meta_updates={
                **migration_meta,
            },
        )
        uninstall_result = self._run_lifecycle_extenders(
            extension,
            "uninstall",
            meta={"action": "uninstall"},
            target_runtime={"installed": False, "enabled": False, "booted": False},
        )
        asset_result = unpublish_extension_assets(extension)
        backend_hooks = {"run_uninstall": uninstall_result, "unpublish_assets": asset_result}
        if disable_result is not None:
            backend_hooks["run_disable"] = disable_result
        if disable_asset_result:
            backend_hooks["disable_unpublish_assets"] = disable_asset_result
        if migration_result is not None:
            backend_hooks["rollback_migrations"] = migration_result
        return self._persist_installation_state(
            extension,
            installed=False,
            enabled=False,
            booted=False,
            lifecycle_event=ExtensionUninstalledEvent(extension_id=extension.id),
            meta_updates={
                "backend_hooks": backend_hooks,
                **migration_meta,
            },
        )

    @transaction.atomic
    def set_extension_enabled(self, extension_id: str, enabled: bool) -> Extension:
        self.load(force=True)
        extension = self.get_extension(extension_id)
        extensions = self.get_extensions()

        if enabled:
            self._validate_enable(extension, extensions)
            self._dispatch_extension_lifecycle_event(ExtensionEnablingEvent(extension_id=extension.id))
            migration_result = self._run_install_migrations_if_declared(extension)
            self._write_installation_state(
                extension,
                installed=True,
                enabled=True,
                booted=True,
            )
            hook_result = self._run_lifecycle_extenders(
                extension,
                "enable",
                meta={"action": "enable"},
                target_runtime={"installed": True, "enabled": True, "booted": True},
            )
            asset_result = publish_extension_assets(extension)
            backend_hooks = {
                "run_enable": hook_result,
                "publish_assets": asset_result,
            }
            meta_updates = {"backend_hooks": backend_hooks}
            if migration_result is not None:
                backend_hooks["run_migrations"] = migration_result
                meta_updates.update({
                    **self._build_migration_meta_updates(extension.id, migration_result),
                })
            return self._persist_installation_state(
                extension,
                installed=True,
                enabled=True,
                booted=True,
                lifecycle_event=ExtensionEnabledEvent(extension_id=extension.id),
                meta_updates=meta_updates,
            )

        return self._disable_extension(extension, extensions)

    def _disable_extension(self, extension, extensions) -> Extension:
        self._validate_disable(extension, extensions)
        self._dispatch_extension_lifecycle_event(ExtensionDisablingEvent(extension_id=extension.id))
        self._write_installation_state(
            extension,
            installed=True,
            enabled=False,
            booted=False,
        )
        hook_result = self._run_lifecycle_extenders(
            extension,
            "disable",
            meta={"action": "disable"},
            target_runtime={"installed": True, "enabled": False, "booted": False},
        )
        asset_result = unpublish_extension_assets(extension)
        return self._persist_installation_state(
            extension,
            installed=True,
            enabled=False,
            booted=False,
            lifecycle_event=ExtensionDisabledEvent(extension_id=extension.id),
            meta_updates={
                "backend_hooks": {
                    "run_disable": hook_result,
                    "unpublish_assets": asset_result,
                }
            },
        )

    @transaction.atomic
    def run_extension_runtime_hook(self, extension_id: str, hook_name: str) -> Extension:
        self.load(force=True)
        extension = self.get_extension(extension_id)

        runtime_action = next(
            (
                action for action in extension.manifest_runtime_actions
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

        hook_result = self._run_backend_hook(
            extension,
            hook_name,
            meta={"action": "runtime_hook", "hook": hook_name},
        )
        return self._persist_installation_state(
            extension,
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            meta_updates={"backend_hooks": {hook_name: hook_result}},
            invalidate_frontend_assets=False,
        )

    @transaction.atomic
    def run_extension_migrations(self, extension_id: str) -> Extension:
        self.load(force=True)
        extension = self.get_extension(extension_id)

        if not extension.runtime.installed:
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装，无法执行迁移",
                code="extension_migrations_not_installed",
                details={"extension_id": extension.id},
            )
        if not has_django_extension_migrations(extension):
            raise ExtensionStateError(
                f"扩展 {extension.id} 未声明 Django 迁移资源",
                code="extension_migrations_not_declared",
                details={"extension_id": extension.id},
            )

        hook_result = self._run_declared_extension_migrations(
            extension,
            action="migrate",
        )
        return self._persist_installation_state(
            extension,
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            meta_updates={
                "backend_hooks": {"run_migrations": hook_result},
                **self._build_migration_meta_updates(extension.id, hook_result),
            },
            invalidate_frontend_assets=False,
        )

    def get_extension_assembly_catalog(self, *, force: bool = False) -> dict[str, ExtensionAssembly]:
        self.load(force=force)
        return {
            extension.id: self._build_extension_assembly(extension)
            for extension in self.get_extensions()
        }

    def get_enabled_extension_assemblies(
        self,
        *,
        force: bool = False,
    ) -> list[ExtensionAssembly]:
        self.load(force=force)
        extensions = [
            extension
            for extension in self.get_extensions()
            if extension.runtime.installed and extension.runtime.enabled
            and is_extension_allowed_in_safe_mode(extension)
        ]
        return [
            self._build_extension_assembly(extension)
            for extension in self.sort_extensions_for_boot(extensions)
        ]

    def get_enabled_extensions(
        self,
        *,
        force: bool = False,
    ) -> list[Extension]:
        self.load(force=force)
        extensions = [
            extension
            for extension in self.get_extensions()
            if extension.runtime.installed and extension.runtime.enabled
            and is_extension_allowed_in_safe_mode(extension)
        ]
        return self.sort_extensions_for_boot(extensions)

    def get_extension_boot_plan(self, *, force: bool = False) -> ExtensionBootPlan:
        forum_extensions = tuple(self.get_enabled_extension_assemblies(force=force))
        return ExtensionBootPlan(
            forum_extensions=forum_extensions,
            event_extensions=forum_extensions,
            resource_extensions=forum_extensions,
            frontend_extensions=forum_extensions,
            locale_extensions=forum_extensions,
            formatter_extensions=forum_extensions,
        )

    @transaction.atomic
    def sync_extension_packages(self, *, prune_missing: bool = True) -> dict:
        self.load(force=True)
        discovered = {
            extension.id: extension
            for extension in self.get_extensions()
        }
        installations = {
            installation.extension_id: installation
            for installation in ExtensionInstallation.objects.all()
        }
        created = []
        updated = []
        pruned = []

        for extension_id, extension in discovered.items():
            installation = installations.get(extension_id)
            if installation is None:
                installation = self._write_installation_state(
                    extension,
                    installed=extension.runtime.installed,
                    enabled=extension.runtime.enabled,
                    booted=extension.runtime.booted,
                    meta_updates={"sync": {"created": True, "reason": "extension_package_discovered"}},
                )
                installations[extension_id] = installation
                created.append(extension_id)
                continue
            changed_fields = []
            installed, enabled, booted = _coerce_installation_runtime_state(
                extension,
                installed=installation.installed,
                enabled=installation.enabled,
                booted=installation.booted,
            )
            if (
                installation.installed != installed
                or installation.enabled != enabled
                or installation.booted != booted
            ):
                installation.installed = installed
                installation.enabled = enabled
                installation.booted = booted
                installation.meta = self._merge_installation_meta(
                    installation.meta,
                    {
                        "sync": {
                            "protected_auto_enabled": True,
                            "reason": "protected_extension_auto_enabled",
                        },
                    },
                )
                changed_fields.extend(["installed", "enabled", "booted", "meta"])
            if installation.version != extension.version:
                installation.version = extension.version
                changed_fields.append("version")
            if installation.source != extension.source:
                installation.source = extension.source
                changed_fields.append("source")
            if changed_fields:
                installation.save(update_fields=[*dict.fromkeys(changed_fields), "updated_at"])
                updated.append(extension_id)

        if prune_missing:
            missing_ids = sorted(set(installations.keys()) - set(discovered.keys()))
            for extension_id in missing_ids:
                installation = installations[extension_id]
                installation.enabled = False
                installation.booted = False
                installation.meta = self._merge_installation_meta(
                    installation.meta,
                    {"sync": {"missing": True, "reason": "extension_package_missing"}},
                )
                installation.save(update_fields=["enabled", "booted", "meta", "updated_at"])
                pruned.append(extension_id)

        self._persist_package_lock(discovered=discovered, installations=installations)
        self._persist_enabled_order()
        self.load(force=True)

        def after_commit() -> None:
            reset_extension_runtime_state()
            if created or updated or pruned:
                self._dispatch_extension_lifecycle_event(ExtensionPackagesSyncedEvent(
                    created=tuple(created),
                    updated=tuple(updated),
                    pruned=tuple(pruned),
                ))

        self._run_after_commit(after_commit)
        return {
            "discovered": sorted(discovered.keys()),
            "created": created,
            "updated": updated,
            "pruned": pruned,
            "locked": len(self._build_package_lock(discovered=discovered, installations=installations)["packages"]),
            "package_inspection": self.inspect_extension_packages(force=True),
        }

    @transaction.atomic
    def sync_enabled_extension_order(self) -> dict:
        before = self.inspect_enabled_extension_order(force=True)
        self._persist_enabled_order()
        self.load(force=True)
        after = self.inspect_enabled_extension_order(force=True)

        def after_commit() -> None:
            reset_extension_runtime_state()

        self._run_after_commit(after_commit)
        return {
            "changed": bool(before.get("drift")),
            "before": before,
            "after": after,
        }

    def get_extension_package_lock(self) -> dict:
        setting = Setting.objects.filter(key=EXTENSION_PACKAGE_LOCK_SETTING).only("value").first()
        if setting is None:
            return {"schema": 1, "packages": []}
        try:
            payload = json.loads(str(setting.value or "{}"))
        except json.JSONDecodeError:
            return {"schema": 1, "packages": [], "invalid": True}
        if not isinstance(payload, dict):
            return {"schema": 1, "packages": [], "invalid": True}
        return {
            "schema": int(payload.get("schema") or 1),
            "packages": list(payload.get("packages") or []),
        }

    def inspect_extension_packages(self, *, force: bool = False) -> dict:
        self.load(force=force)
        discovered = {
            extension.id: extension
            for extension in self.get_extensions()
        }
        installations = {
            installation.extension_id: installation
            for installation in ExtensionInstallation.objects.all()
        }
        packages = self._build_package_lock(discovered=discovered, installations=installations)["packages"]
        missing = [item["id"] for item in packages if item["missing"]]
        version_drift = [item["id"] for item in packages if item.get("version_mismatch")]
        source_drift = [item["id"] for item in packages if item.get("source_mismatch")]
        unmanaged = [
            item["id"]
            for item in packages
            if item.get("discovered") and not item.get("installed")
        ]
        lock = self.get_extension_package_lock()
        locked_ids = {
            str(item.get("id") or "").strip()
            for item in lock.get("packages", [])
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        discovered_ids = set(discovered.keys())
        installed_ids = set(installations.keys())
        dependency_resolution = _build_dependency_resolution_payload(list(discovered.values()))
        enabled_order = self.inspect_enabled_extension_order(force=False)
        return {
            "schema": 1,
            "packages": packages,
            "lock": {
                "schema": lock.get("schema", 1),
                "count": len(lock.get("packages") or []),
                "stale_ids": sorted(locked_ids - (discovered_ids | installed_ids)),
                "invalid": bool(lock.get("invalid")),
            },
            "summary": {
                "discovered_count": len(discovered_ids),
                "installed_count": sum(1 for item in packages if item.get("installed")),
                "installation_record_count": len(installed_ids),
                "locked_count": len(packages),
                "missing_count": len(missing),
                "version_drift_count": len(version_drift),
                "source_drift_count": len(source_drift),
                "unmanaged_discovered_count": len(unmanaged),
            },
            "dependency_resolution": dependency_resolution,
            "enabled_order": enabled_order,
            "missing": missing,
            "version_drift": version_drift,
            "source_drift": source_drift,
            "unmanaged_discovered": unmanaged,
        }

    def inspect_enabled_extension_order(self, *, force: bool = False) -> dict:
        self.load(force=force)
        enabled_extensions = [
            extension
            for extension in self.get_extensions()
            if extension.runtime.installed and extension.runtime.enabled
        ]
        resolved = resolve_extension_order(
            enabled_extensions,
            satisfied_dependency_ids=_get_core_satisfied_dependency_ids(),
        )
        resolved_ids = list(resolved.get("order") or [])
        persisted_ids = self._read_persisted_enabled_order()
        known_enabled_ids = {extension.id for extension in enabled_extensions}
        stale_ids = [
            extension_id
            for extension_id in persisted_ids
            if extension_id not in known_enabled_ids
        ]
        drift = persisted_ids != resolved_ids
        return {
            "schema": 1,
            "persisted": persisted_ids,
            "resolved": resolved_ids,
            "stale": stale_ids,
            "drift": drift,
            "changed": drift,
            "enabled_count": len(resolved_ids),
            "missing_dependencies": dict(resolved.get("missing_dependencies") or {}),
            "circular_dependencies": list(resolved.get("circular_dependencies") or []),
        }

    def _persist_package_lock(
        self,
        *,
        discovered: dict[str, Extension],
        installations: dict[str, ExtensionInstallation],
    ) -> None:
        payload = self._build_package_lock(discovered=discovered, installations=installations)
        Setting.objects.update_or_create(
            key=EXTENSION_PACKAGE_LOCK_SETTING,
            defaults={"value": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        )

    def _build_package_lock(
        self,
        *,
        discovered: dict[str, Extension],
        installations: dict[str, ExtensionInstallation],
    ) -> dict:
        packages = []
        for extension_id in sorted(set(discovered.keys()) | set(installations.keys())):
            extension = discovered.get(extension_id)
            installation = installations.get(extension_id)
            distribution = {}
            if extension is not None:
                distribution = dict((extension.manifest.extra or {}).get("python_distribution") or {})
            runtime = extension.runtime if extension is not None else None
            installed_version = installation.version if installation is not None else ""
            installed_source = installation.source if installation is not None else ""
            discovered_version = extension.version if extension is not None else ""
            discovered_source = extension.source if extension is not None else ""
            packages.append({
                "id": extension_id,
                "version": installed_version or discovered_version,
                "source": installed_source or discovered_source,
                "discovered_version": discovered_version,
                "discovered_source": discovered_source,
                "path": str(extension.manifest.path or "") if extension is not None else "",
                "distribution": {
                    "name": str(distribution.get("name") or ""),
                    "version": str(distribution.get("version") or ""),
                } if distribution else {},
                "installed": bool(installation.installed) if installation is not None else bool(runtime and runtime.installed),
                "enabled": bool(installation.enabled) if installation is not None else bool(runtime and runtime.enabled),
                "booted": bool(installation.booted) if installation is not None else bool(runtime and runtime.booted),
                "discovered": extension is not None,
                "missing": extension is None,
                "version_mismatch": bool(installation is not None and extension is not None and installed_version != discovered_version),
                "source_mismatch": bool(installation is not None and extension is not None and installed_source != discovered_source),
                "abandoned": bool(extension.manifest.distribution.abandoned) if extension is not None else False,
                "replacement": str(extension.manifest.distribution.replacement or "") if extension is not None else "",
            })
        return {
            "schema": 1,
            "packages": packages,
        }

    def sort_extensions_for_boot(self, extensions: list[Extension]) -> list[Extension]:
        resolved = resolve_extension_order(
            extensions,
            satisfied_dependency_ids=_get_core_satisfied_dependency_ids(),
        )
        if resolved["circular_dependencies"]:
            circular = ", ".join(resolved["circular_dependencies"])
            raise ExtensionStateError(
                f"扩展依赖存在循环: {circular}",
                code="extension_dependency_cycle",
                details={"circular_dependencies": resolved["circular_dependencies"]},
            )
        if resolved["missing_dependencies"]:
            missing = {
                extension_id: dependencies
                for extension_id, dependencies in resolved["missing_dependencies"].items()
                if dependencies
            }
            if missing:
                raise ExtensionStateError(
                    "扩展依赖缺失，无法确定启动顺序。",
                    code="extension_dependency_missing",
                    details={"missing_dependencies": missing},
                )
        return list(resolved["valid"])

    def _apply_installation_state(self, extension: Extension) -> Extension:
        extension.invalidate_discovery()
        installation = ExtensionInstallation.objects.filter(extension_id=extension.id).first()
        if installation is None:
            extension = self._build_uninstalled_extension(extension)
        else:
            installed, enabled, booted = _coerce_installation_runtime_state(
                extension,
                installed=installation.installed,
                enabled=installation.enabled,
                booted=installation.booted,
            )
            extension.runtime = ExtensionRuntimeState(
                installed=installed,
                enabled=enabled,
                booted=booted,
                healthy=extension.runtime.healthy,
                status_key=_build_extension_status_key(installed, enabled),
                status_label=_build_extension_status_label(installed, enabled),
                migration_state=extension.runtime.migration_state,
                migration_label=extension.runtime.migration_label,
                dependency_state=extension.runtime.dependency_state,
                dependency_state_label=extension.runtime.dependency_state_label,
                runtime_issues=extension.runtime.runtime_issues,
                runtime_actions=(),
                backend_hooks=dict((installation.meta or {}).get("backend_hooks") or {}),
                migration_execution=dict((installation.meta or {}).get("migration_execution") or {}),
                applied_migration_files=tuple((installation.meta or {}).get("applied_migration_files") or ()),
            )
        return self._with_runtime_actions(extension)

    def _build_uninstalled_extension(self, extension: Extension) -> Extension:
        auto_installed = is_extension_auto_installed(extension)
        auto_enabled = is_extension_auto_enabled(extension)
        if auto_installed:
            extension.runtime = ExtensionRuntimeState(
                installed=True,
                enabled=auto_enabled,
                booted=auto_enabled,
                healthy=extension.runtime.healthy,
                status_key=_build_extension_status_key(True, auto_enabled),
                status_label=_build_extension_status_label(True, auto_enabled),
                migration_state=extension.runtime.migration_state,
                migration_label=extension.runtime.migration_label,
                dependency_state=extension.runtime.dependency_state,
                dependency_state_label=extension.runtime.dependency_state_label,
                runtime_issues=extension.runtime.runtime_issues,
                runtime_actions=(),
                backend_hooks=dict(extension.runtime.backend_hooks or {}),
                migration_execution=dict(extension.runtime.migration_execution or {}),
                applied_migration_files=tuple(extension.runtime.applied_migration_files or ()),
            )
            return extension

        extension.runtime = ExtensionRuntimeState(
            installed=False,
            enabled=False,
            booted=False,
            healthy=extension.runtime.healthy,
            status_key="pending_install",
            status_label="待安装",
            migration_state="pending",
            migration_label="待安装",
            dependency_state=extension.runtime.dependency_state,
            dependency_state_label=extension.runtime.dependency_state_label,
            runtime_issues=extension.runtime.runtime_issues,
            runtime_actions=(),
            backend_hooks=dict(extension.runtime.backend_hooks or {}),
            migration_execution=dict(extension.runtime.migration_execution or {}),
            applied_migration_files=tuple(extension.runtime.applied_migration_files or ()),
        )
        return extension

    def _with_runtime_actions(self, extension: Extension) -> Extension:
        runtime_probe = inspect_extension_runtime(extension)
        extension.runtime = ExtensionRuntimeState(
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            healthy=bool(runtime_probe["healthy"]),
            status_key=extension.runtime.status_key,
            status_label=extension.runtime.status_label,
            migration_state=str(runtime_probe["migration_state"]),
            migration_label=str(runtime_probe["migration_label"]),
            dependency_state=extension.runtime.dependency_state,
            dependency_state_label=extension.runtime.dependency_state_label,
            runtime_issues=tuple(runtime_probe["runtime_issues"]),
            runtime_actions=(),
            delivery_checks=tuple(runtime_probe["delivery_checks"]),
            uninstall_warnings=tuple(runtime_probe["uninstall_warnings"]),
            backend_hooks=dict(extension.runtime.backend_hooks or {}),
            migration_execution=dict(runtime_probe.get("migration_execution") or extension.runtime.migration_execution or {}),
            applied_migration_files=tuple(extension.runtime.applied_migration_files or ()),
        )
        extension.runtime = ExtensionRuntimeState(
            installed=extension.runtime.installed,
            enabled=extension.runtime.enabled,
            booted=extension.runtime.booted,
            healthy=extension.runtime.healthy,
            status_key=extension.runtime.status_key,
            status_label=extension.runtime.status_label,
            migration_state=extension.runtime.migration_state,
            migration_label=extension.runtime.migration_label,
            dependency_state=extension.runtime.dependency_state,
            dependency_state_label=extension.runtime.dependency_state_label,
            runtime_issues=extension.runtime.runtime_issues,
            runtime_actions=_build_runtime_actions(extension),
            delivery_checks=extension.runtime.delivery_checks,
            uninstall_warnings=extension.runtime.uninstall_warnings,
            backend_hooks=dict(extension.runtime.backend_hooks or {}),
            migration_execution=dict(extension.runtime.migration_execution or {}),
            applied_migration_files=tuple(extension.runtime.applied_migration_files or ()),
        )
        return extension

    def _build_extension_assembly(self, extension: Extension) -> ExtensionAssembly:
        return ExtensionAssembly(
            extension_id=extension.id,
            name=extension.name,
            source=extension.source,
            module_ids=tuple(extension.module_ids),
            product_visible=is_product_visible_extension(extension),
            frontend_admin_entry=extension.frontend_admin_entry,
            frontend_forum_entry=extension.frontend_forum_entry,
            frontend_common_entry="",
            frontend_routes=tuple(extension.discover().frontend_routes),
            settings_schema=tuple(extension.settings_schema),
            settings_defaults=tuple(extension.settings_defaults),
            settings_reset_rules=tuple(extension.settings_reset_rules),
            settings_frontend_cache_keys=tuple(extension.settings_frontend_cache_keys),
            settings_theme_variables=tuple(extension.settings_theme_variables),
            settings_forum_serializations=tuple(extension.settings_forum_serializations),
            forum_settings_keys=tuple(
                key for key in extension.forum_settings_keys
                if str(key or "").strip()
            ),
            permissions=tuple(extension.permissions),
            admin_pages=tuple(extension.admin_page_definitions),
            notification_types=tuple(extension.notification_types),
            user_preferences=tuple(extension.user_preferences),
            language_packs=tuple(extension.language_packs),
            post_types=tuple(extension.post_types),
            search_filters=tuple(extension.search_filters),
            discussion_list_queries=tuple(extension.discussion_list_queries),
            discussion_sorts=tuple(extension.discussion_sorts),
            discussion_list_filters=tuple(extension.discussion_list_filters),
            locale_paths=tuple(
                path for path in extension.locale_paths
                if str(path or "").strip()
            ),
            view_namespaces=tuple(extension.view_namespaces),
            formatter_pipeline=tuple(extension.formatter_pipeline),
            formatter_callbacks=tuple(extension.formatter_callbacks),
            resource_definitions=tuple(extension.resource_definitions),
            resource_fields=tuple(extension.resource_fields),
            resource_field_mutators=tuple(extension.resource_field_mutators),
            resource_relationships=tuple(extension.resource_relationships),
            resource_endpoints=tuple(extension.resource_endpoints),
            resource_sorts=tuple(extension.resource_sorts),
            resource_filters=tuple(extension.resource_filters),
            model_definitions=tuple(extension.model_definitions),
            model_visibility=tuple(extension.model_visibility),
            model_relations=tuple(extension.model_relations),
            model_casts=tuple(extension.model_casts),
            model_defaults=tuple(extension.model_defaults),
            model_slug_drivers=tuple(extension.model_slug_drivers),
            search_drivers=tuple(extension.search_drivers),
            search_indexes=tuple(extension.search_indexes),
            event_listeners=tuple(extension.event_listeners),
            realtime_included=tuple(extension.realtime_included),
            realtime_discussion_visibility=tuple(extension.discover().realtime_discussion_visibility),
            realtime_discussion_transports=tuple(extension.discover().realtime_discussion_transports),
            realtime_discussion_broadcasts=tuple(extension.discover().realtime_discussion_broadcasts),
            discussion_lifecycle=tuple(extension.discussion_lifecycle),
            post_lifecycle=tuple(extension.post_lifecycle),
            runtime_actions=tuple(extension.manifest_runtime_actions),
            admin_actions=tuple(extension.admin_actions),
            settings_pages=tuple(extension.settings_pages),
            permissions_pages=tuple(extension.permissions_pages),
            operations_pages=tuple(extension.operations_pages),
        )

    def _validate_enable(self, extension, extensions) -> None:
        if not extension.runtime.installed and extension.source == "filesystem":
            raise ExtensionStateError(
                f"扩展 {extension.id} 尚未安装",
                code="extension_enable_not_installed",
                details={"extension_id": extension.id},
            )

        self._validate_bias_compatibility(extension, action="enable")

        extension_map = {item.id: item for item in extensions}
        satisfied_dependency_ids = _get_core_satisfied_dependency_ids()
        missing_dependencies = []
        disabled_dependencies = []
        active_conflicts = []

        for dependency_id in extension.manifest.dependencies:
            if dependency_id in satisfied_dependency_ids:
                continue
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

    def _validate_disable(self, extension, extensions, *, uninstalling: bool = False) -> None:
        if is_extension_protected(extension):
            raise ExtensionStateError(
                f"无法{'卸载' if uninstalling else '停用'}受保护扩展 {extension.id}",
                code="extension_uninstall_protected_blocked" if uninstalling else "extension_disable_protected_blocked",
                details={
                    "extension_id": extension.id,
                    "protected_reason": get_extension_protected_reason(extension),
                },
            )

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

    def _validate_bias_compatibility(self, extension, *, action: str) -> None:
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

    def _run_install_migrations_if_declared(self, extension) -> dict | None:
        if not has_django_extension_migrations(extension):
            return None
        return self._run_declared_extension_migrations(
            extension,
            action="install_migrations",
        )

    def _run_uninstall_migrations_if_declared(self, extension) -> dict | None:
        if not has_django_extension_migrations(extension):
            return None
        return self._run_declared_extension_migrations(
            extension,
            action="uninstall_migrations",
            direction="down",
        )

    def _run_declared_extension_migrations(self, extension, *, action: str, direction: str = "up") -> dict:
        migration_record = ExtensionMigrationRepository().get_record(extension.id)
        base_result = sync_django_extension_migrations(
            extension,
            applied_steps=list(migration_record.applied_steps),
            applied_migration_files=list(migration_record.applied_files),
            direction=direction,
        )
        hook_name = "rollback_migrations" if direction == "down" else "run_migrations"
        hook_result = self._run_backend_hook(extension, hook_name, meta={"action": action, "direction": direction})
        merged_details = {
            **dict(base_result.get("details") or {}),
            **dict(hook_result.get("details") or {}),
        }
        hook_status = str(hook_result.get("status") or "").strip()
        base_status = str(base_result.get("status") or "").strip()
        use_hook_result = bool(hook_status and hook_status != "skipped")
        return {
            "hook": hook_name,
            "status": (hook_result.get("status") if use_hook_result else base_status) or "ok",
            "status_label": (hook_result.get("status_label") if use_hook_result else base_result.get("status_label")) or "已执行",
            "message": (hook_result.get("message") if use_hook_result else base_result.get("message")) or "扩展迁移已执行。",
            "executed_at": (hook_result.get("executed_at") if use_hook_result else base_result.get("executed_at")),
            "details": merged_details,
        }

    def _build_migration_meta_updates(
        self,
        extension_id: str,
        migration_result: dict | None,
        *,
        direction: str = "up",
    ) -> dict:
        if migration_result is None:
            return {}
        return ExtensionMigrationRepository().build_execution_meta(
            extension_id,
            migration_result,
            direction=direction,
        )

    def _persist_installation_state(
        self,
        extension,
        *,
        installed: bool,
        enabled: bool,
        booted: bool,
        meta_updates: dict | None = None,
        invalidate_frontend_assets: bool = True,
        lifecycle_event=None,
        lifecycle_events: tuple | list | None = None,
    ):
        self._write_installation_state(
            extension,
            installed=installed,
            enabled=enabled,
            booted=booted,
            meta_updates=meta_updates,
        )

        self.load(force=True)
        self._persist_enabled_order()
        events_to_dispatch = tuple(lifecycle_events or (() if lifecycle_event is None else (lifecycle_event,)))

        def after_commit() -> None:
            reset_extension_runtime_state()
            if invalidate_frontend_assets:
                for event in events_to_dispatch:
                    self._dispatch_extension_lifecycle_event(event)

        self._run_after_commit(after_commit)
        return self.get_extension(extension.id)

    def _write_installation_state(
        self,
        extension,
        *,
        installed: bool,
        enabled: bool,
        booted: bool,
        meta_updates: dict | None = None,
    ) -> ExtensionInstallation:
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

        installed, enabled, booted = _coerce_installation_runtime_state(
            extension,
            installed=installed,
            enabled=enabled,
            booted=booted,
        )
        installation.version = extension.version
        installation.source = extension.source
        installation.enabled = bool(enabled)
        installation.installed = bool(installed)
        installation.booted = bool(booted)
        installation.meta = self._merge_installation_meta(
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
        return installation

    def _dispatch_extension_lifecycle_event(self, event) -> None:
        bootstrap_extension_runtime_event_listeners()
        get_extension_event_bus().dispatch(event)

    @staticmethod
    def _run_after_commit(callback) -> None:
        connection = transaction.get_connection()
        if connection.in_atomic_block:
            transaction.on_commit(callback)
            return
        callback()

    def _persist_enabled_order(self) -> None:
        extensions = [
            extension
            for extension in self.get_extensions()
            if extension.runtime.installed and extension.runtime.enabled
        ]
        ordered_ids = [extension.id for extension in self.sort_extensions_for_boot(extensions)]
        Setting.objects.update_or_create(
            key=EXTENSION_ENABLED_ORDER_SETTING,
            defaults={"value": json_dumps(ordered_ids)},
        )

    def _read_persisted_enabled_order(self) -> list[str]:
        setting = Setting.objects.filter(key=EXTENSION_ENABLED_ORDER_SETTING).only("value").first()
        raw_value = str(getattr(setting, "value", "") or "")
        if not raw_value:
            return []
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [
            str(item).strip()
            for item in payload
            if str(item).strip()
        ]

    def _run_backend_hook(self, extension, hook_name: str, *, meta: dict | None = None) -> dict:
        return run_extension_backend_hook(
            extension,
            hook_name,
            meta=meta,
        )

    def _run_lifecycle_extenders(
        self,
        extension,
        action: str,
        *,
        meta: dict | None = None,
        target_runtime: dict | None = None,
    ) -> dict:
        from apps.core.extensions.backend import build_backend_context

        method_name = {
            "install": "on_install",
            "enable": "on_enable",
            "disable": "on_disable",
            "uninstall": "on_uninstall",
        }.get(action, "")
        hook_name = {
            "install": "run_install",
            "enable": "run_enable",
            "disable": "run_disable",
            "uninstall": "run_uninstall",
        }.get(action, action)

        context_extension = extension
        if target_runtime:
            context_extension = replace(
                extension,
                runtime=replace(extension.runtime, **dict(target_runtime)),
            )
        context = build_backend_context(context_extension, meta=meta)
        results = []
        for extender in extension.get_extenders():
            callback = getattr(extender, method_name, None)
            if not callable(callback):
                continue
            try:
                result = callback(context)
            except Exception as exc:
                raise ExtensionStateError(
                    f"扩展 {extension.id} 的 {method_name} 生命周期处理器执行失败: {exc}",
                    code="extension_lifecycle_failed",
                    details={
                        "extension_id": extension.id,
                        "action": action,
                        "hook": hook_name,
                        "handler": callback.__name__ if hasattr(callback, "__name__") else callback.__class__.__name__,
                    },
                ) from exc
            normalized_result = _normalize_lifecycle_result(result, hook_name)
            if normalized_result.get("status") not in ("ok", "skipped"):
                raise ExtensionStateError(
                    normalized_result.get("message") or f"扩展 {extension.id} 的 {method_name} 生命周期处理器执行失败。",
                    code="extension_lifecycle_failed",
                    details={
                        "extension_id": extension.id,
                        "action": action,
                        "hook": hook_name,
                        "result": normalized_result,
                    },
                )
            results.append(normalized_result)

        if not results:
            return {
                "hook": hook_name,
                "status": "skipped",
                "status_label": "已跳过",
                "message": f"扩展未声明 {method_name} 生命周期处理器。",
            }

        effective = next((item for item in results if item.get("status") != "skipped"), results[-1])
        return {
            **effective,
            "hook": hook_name,
            "details": {
                **dict(effective.get("details") or {}),
                "lifecycle_results": results,
            },
        }

    def _merge_installation_meta(self, current_meta: dict | None, updates: dict | None) -> dict:
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


def _normalize_lifecycle_result(result, hook_name: str) -> dict:
    from django.utils import timezone

    timestamp = timezone.now().isoformat()
    if result is None:
        return {
            "hook": hook_name,
            "status": "ok",
            "status_label": "已完成",
            "message": f"{hook_name} 已执行。",
            "executed_at": timestamp,
        }
    if isinstance(result, dict):
        payload = dict(result)
        payload.setdefault("hook", hook_name)
        payload.setdefault("status", "ok")
        payload.setdefault("status_label", "已完成")
        payload.setdefault("executed_at", timestamp)
        return payload
    return {
        "hook": hook_name,
        "status": "ok",
        "status_label": "已完成",
        "message": str(result),
        "executed_at": timestamp,
    }


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _get_core_satisfied_dependency_ids() -> set[str]:
    try:
        from apps.core.forum_registry import get_core_module_ids

        return set(get_core_module_ids())
    except Exception:
        return {"core"}


def resolve_extension_order(extensions: list[Extension], *, satisfied_dependency_ids: set[str] | None = None) -> dict:
    satisfied_dependency_ids = set(satisfied_dependency_ids or set())
    extension_map = {extension.id: extension for extension in extensions}
    sorted_extensions = sorted(extensions, key=lambda item: item.id)
    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {extension.id: 0 for extension in sorted_extensions}
    missing_dependencies: dict[str, list[str]] = {}

    for extension in sorted_extensions:
        dependencies = list(extension.manifest.dependencies)
        optional_dependencies = [
            dependency_id
            for dependency_id in extension.manifest.optional_dependencies
            if dependency_id in extension_map
        ]
        graph.setdefault(extension.id, [])
        for dependency_id in [*dependencies, *optional_dependencies]:
            if dependency_id in satisfied_dependency_ids:
                continue
            if dependency_id not in extension_map:
                if dependency_id in dependencies:
                    missing_dependencies.setdefault(extension.id, []).append(dependency_id)
                continue
            graph.setdefault(dependency_id, [])
            graph[dependency_id].append(extension.id)
            in_degree[extension.id] = in_degree.get(extension.id, 0) + 1

    pending = sorted([extension_id for extension_id, count in in_degree.items() if count == 0])
    output: list[str] = []
    while pending:
        active = pending.pop(0)
        output.append(active)
        for dependent_id in sorted(graph.get(active, [])):
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                pending.append(dependent_id)

    circular_dependencies = sorted([
        extension_id
        for extension_id, count in in_degree.items()
        if count > 0
    ])
    valid_ids = [
        extension_id
        for extension_id in output
        if extension_id not in missing_dependencies
    ]

    return {
        "valid": [extension_map[extension_id] for extension_id in valid_ids],
        "order": valid_ids,
        "graph": graph,
        "missing_dependencies": missing_dependencies,
        "circular_dependencies": circular_dependencies,
    }


def _build_dependency_resolution_payload(extensions: list[Extension]) -> dict:
    resolved = resolve_extension_order(
        extensions,
        satisfied_dependency_ids=_get_core_satisfied_dependency_ids(),
    )
    dependents: dict[str, list[str]] = {extension.id: [] for extension in extensions}
    for dependency_id, dependent_ids in dict(resolved.get("graph") or {}).items():
        for dependent_id in dependent_ids:
            dependents.setdefault(dependency_id, [])
            if dependent_id not in dependents[dependency_id]:
                dependents[dependency_id].append(dependent_id)
    extension_map = {extension.id: extension for extension in extensions}
    graph = {}
    for extension in sorted(extensions, key=lambda item: item.id):
        optional_dependencies = [
            dependency_id
            for dependency_id in extension.manifest.optional_dependencies
            if dependency_id in extension_map
        ]
        graph[extension.id] = {
            "dependencies": list(extension.manifest.dependencies),
            "optional_dependencies": optional_dependencies,
            "dependents": sorted(dependents.get(extension.id, [])),
        }
    return {
        "boot_order": list(resolved.get("order") or []),
        "graph": graph,
        "missing_dependencies": dict(resolved.get("missing_dependencies") or {}),
        "circular_dependencies": list(resolved.get("circular_dependencies") or []),
    }


_manager: ExtensionManager | None = None


def get_extension_manager() -> ExtensionManager:
    global _manager
    default_path = Path(settings.BASE_DIR) / "extensions"
    if _manager is None:
        _manager = ExtensionManager()
    elif _manager.extensions_path != default_path:
        _manager = ExtensionManager(extensions_path=default_path)
    return _manager


def _build_extension_status_key(installed: bool, enabled: bool) -> str:
    if not installed:
        return "pending_install"
    if enabled:
        return "active"
    return "disabled"


def _coerce_installation_runtime_state(
    extension: Extension,
    *,
    installed: bool,
    enabled: bool,
    booted: bool,
) -> tuple[bool, bool, bool]:
    installed = bool(installed)
    enabled = bool(enabled)
    booted = bool(booted)
    if is_extension_protected(extension) and is_extension_auto_enabled(extension):
        return True, True, True
    return installed, enabled, booted


def _build_extension_status_label(installed: bool, enabled: bool) -> str:
    if not installed:
        return "待安装"
    if enabled:
        return "已启用"
    return "已停用"


def _build_runtime_actions(extension: Extension) -> tuple[ExtensionRuntimeActionDefinition, ...]:
    manifest_actions = _build_manifest_runtime_actions(extension)
    migration_action = _build_migration_runtime_action(extension)
    protected = is_extension_protected(extension)
    action_prefix = []
    if migration_action is not None:
        action_prefix.append(migration_action)
    action_prefix.extend(list(manifest_actions))

    if not extension.runtime.installed:
        return tuple([
            ExtensionRuntimeActionDefinition(
                key="install",
                label="安装扩展",
                action="install",
                tone="primary",
                confirm_title="安装扩展",
                confirm_message=f"确定安装 {extension.name} 吗？当前版本会登记为已安装并默认启用。",
                confirm_text="安装",
                success_message="扩展已安装并启用。",
                order=10,
            ),
            *action_prefix,
        ])

    actions = list(action_prefix)
    if extension.runtime.enabled:
        if not protected:
            actions.append(ExtensionRuntimeActionDefinition(
                key="disable",
                label="停用扩展",
                action="disable",
                tone="danger",
                confirm_title="停用扩展",
                confirm_message=f"确定停用 {extension.name} 吗？相关后台入口和运行能力会立即隐藏。",
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
            confirm_message=f"确定启用 {extension.name} 吗？依赖校验通过后会立即恢复能力。",
            confirm_text="启用",
            success_message="扩展已启用。",
            requires_installed=True,
            order=10,
        ))
        if not protected:
            actions.append(ExtensionRuntimeActionDefinition(
                key="uninstall",
                label="卸载扩展",
                action="uninstall",
                tone="danger",
                confirm_title="卸载扩展",
                confirm_message=_build_uninstall_confirm_message(extension),
                confirm_text="卸载",
                success_message="扩展已卸载。",
                requires_installed=True,
                order=30,
            ))

    return tuple(actions)


def _build_manifest_runtime_actions(extension: Extension) -> tuple[ExtensionRuntimeActionDefinition, ...]:
    actions = []
    for action in sorted(extension.manifest_runtime_actions, key=lambda item: (item.order, item.key)):
        actions.append(ExtensionRuntimeActionDefinition(
            key=action.key,
            label=action.label,
            action=f"hook:{action.hook}",
            tone=action.tone,
            confirm_title=action.confirm_title,
            confirm_message=action.confirm_message,
            confirm_text=action.confirm_text,
            success_message=action.success_message,
            requires_enabled=action.requires_enabled,
            requires_installed=action.requires_installed,
            order=action.order,
        ))
    return tuple(actions)


def _build_migration_runtime_action(extension: Extension) -> ExtensionRuntimeActionDefinition | None:
    if not extension.runtime.installed:
        return None
    if not has_django_extension_migrations(extension):
        return None
    return ExtensionRuntimeActionDefinition(
        key="migrations",
        label="执行迁移",
        action="migrations",
        tone="default",
        confirm_title="执行扩展迁移",
        confirm_message=f"确定执行 {extension.name} 的扩展迁移吗？该操作通常用于安装后补跑或同步迁移摘要。",
        confirm_text="执行",
        success_message="扩展迁移已执行。",
        requires_installed=True,
        order=15,
    )


def _build_uninstall_confirm_message(extension: Extension) -> str:
    warnings = list(extension.runtime.uninstall_warnings or ())
    if not warnings:
        return f"确定卸载 {extension.name} 吗？"

    body = "；".join(warnings[:2])
    return f"确定卸载 {extension.name} 吗？{body}"
