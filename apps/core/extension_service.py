from __future__ import annotations

from apps.core.audit import log_admin_action
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.frontend_compiler import recompile_extension_frontend_assets
from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.lifecycle import (
    clear_extension_runtime_rebuild_marker,
    mark_extension_runtime_requires_rebuild,
    mark_extension_runtime_version_changed,
    reset_extension_runtime_state,
)
from apps.core.extensions.validation import resolve_bias_version_compatibility


class ExtensionService:
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
    def _refresh_runtime(updated):
        reset_extension_runtime_state()
        return get_extension_manager().get_extension(updated.id)

    @staticmethod
    def list_extensions():
        return get_extension_manager().get_extensions()

    @staticmethod
    def inspect_extension_packages():
        return get_extension_manager().inspect_extension_packages(force=True)

    @staticmethod
    def sync_extension_packages(*, prune_missing: bool = True, actor=None, request=None):
        result = get_extension_manager().sync_extension_packages(prune_missing=prune_missing)
        reset_extension_runtime_state()

        if request is not None:
            summary = dict((result.get("package_inspection") or {}).get("summary") or {})
            log_admin_action(
                request,
                "admin.extension.sync_packages",
                target_type="extension",
                target_id=None,
                data={
                    "prune_missing": bool(prune_missing),
                    "discovered_count": len(result.get("discovered") or []),
                    "updated": list(result.get("updated") or []),
                    "pruned": list(result.get("pruned") or []),
                    "missing_count": int(summary.get("missing_count") or 0),
                    "version_drift_count": int(summary.get("version_drift_count") or 0),
                    "source_drift_count": int(summary.get("source_drift_count") or 0),
                },
            )

        return result

    @staticmethod
    def sync_enabled_extension_order(*, actor=None, request=None):
        result = get_extension_manager().sync_enabled_extension_order()
        reset_extension_runtime_state()

        if request is not None:
            after = dict(result.get("after") or {})
            log_admin_action(
                request,
                "admin.extension.sync_enabled_order",
                target_type="extension",
                target_id=None,
                data={
                    "changed": bool(result.get("changed")),
                    "persisted": list(after.get("persisted") or []),
                    "resolved": list(after.get("resolved") or []),
                    "stale": list(after.get("stale") or []),
                },
            )

        return result

    @staticmethod
    def rebuild_extension_frontend_assets(
        *,
        run_build: bool = True,
        include_disabled: bool = False,
        publish: bool = False,
        actor=None,
        request=None,
    ):
        manager = get_extension_manager()
        manager.load(force=True)
        extensions = [
            extension
            for extension in manager.get_extensions()
            if extension.runtime.installed
            and (include_disabled or extension.runtime.enabled)
        ]
        result = recompile_extension_frontend_assets(
            extensions,
            run_build=run_build,
            clear_marker=run_build,
            publish_dist=publish,
        ).to_dict()

        if result.get("status") == "ok" and run_build:
            clear_extension_runtime_rebuild_marker()
            mark_extension_runtime_version_changed("extension_frontend_rebuilt")
            reset_extension_runtime_state()
        elif result.get("status") == "ok":
            mark_extension_runtime_requires_rebuild("extension_frontend_manifest_built")
        else:
            mark_extension_runtime_requires_rebuild("extension_frontend_rebuild_failed")

        if request is not None:
            log_admin_action(
                request,
                "admin.extension.rebuild_frontend_assets",
                target_type="extension",
                target_id=None,
                data={
                    "run_build": bool(run_build),
                    "include_disabled": bool(include_disabled),
                    "publish": bool(publish),
                    "status": str(result.get("status") or ""),
                    "extension_count": int(result.get("extension_count") or 0),
                    "returncode": result.get("returncode"),
                },
            )

        return result

    @staticmethod
    def get_extension(extension_id: str):
        return get_extension_manager().get_extension(extension_id)

    @staticmethod
    def install_extension(extension_id: str, *, actor=None, request=None):
        extension = get_extension_manager().get_extension(extension_id)
        ExtensionService._validate_bias_compatibility(extension, action="install")
        updated = get_extension_manager().install_extension(extension_id)
        updated = ExtensionService._refresh_runtime(updated)

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
    def uninstall_extension(extension_id: str, *, actor=None, request=None):
        updated = get_extension_manager().uninstall_extension(extension_id)
        updated = ExtensionService._refresh_runtime(updated)

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
    def set_extension_enabled(extension_id: str, enabled: bool, *, actor=None, request=None):
        normalized_extension_id = str(extension_id or "").strip()
        if not enabled and normalized_extension_id == "core":
            raise ExtensionStateError(
                "无法停用核心扩展 core",
                code="extension_disable_core_blocked",
                details={"extension_id": normalized_extension_id},
            )
        if enabled:
            extension = get_extension_manager().get_extension(extension_id)
            ExtensionService._validate_bias_compatibility(extension, action="enable")
        updated = get_extension_manager().set_extension_enabled(extension_id, enabled)
        updated = ExtensionService._refresh_runtime(updated)

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
    def run_extension_runtime_hook(extension_id: str, hook_name: str, *, actor=None, request=None):
        updated = get_extension_manager().run_extension_runtime_hook(extension_id, hook_name)
        updated = ExtensionService._refresh_runtime(updated)

        if request is not None:
            backend_hook = dict(updated.runtime.backend_hooks or {}).get(hook_name) or {}
            log_admin_action(
                request,
                "admin.extension.runtime_hook",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "hook": hook_name,
                    "status": backend_hook.get("status"),
                },
            )

        return updated

    @staticmethod
    def run_extension_migrations(extension_id: str, *, actor=None, request=None):
        updated = get_extension_manager().run_extension_migrations(extension_id)
        updated = ExtensionService._refresh_runtime(updated)

        if request is not None:
            migration_hook = dict(updated.runtime.backend_hooks or {}).get("run_migrations") or {}
            log_admin_action(
                request,
                "admin.extension.migrations",
                target_type="extension",
                target_id=None,
                data={
                    "extension_id": updated.id,
                    "status": migration_hook.get("status"),
                },
            )

        return updated
