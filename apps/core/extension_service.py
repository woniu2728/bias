from __future__ import annotations

from apps.core.audit import log_admin_action
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.lifecycle import reset_extension_runtime_state
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
