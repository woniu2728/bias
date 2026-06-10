from __future__ import annotations

from apps.core.extensions.bootstrap import bootstrap_extension_application, reset_extension_application_bootstrap_state
from apps.core.extensions.registry import get_extension_registry
from apps.core.extensions.lifecycle import reset_extension_runtime_state
from apps.core.models import ExtensionInstallation


class ExtensionRuntimeTestMixin:
    def _pre_setup(self):
        super()._pre_setup()
        reset_extension_runtime_state()
        reset_extension_application_bootstrap_state()
        bootstrap_extension_application(force=True)

    def _post_teardown(self):
        super()._post_teardown()
        reset_extension_runtime_state()
        reset_extension_application_bootstrap_state()

    def bootstrap_extensions(self, *extension_ids: str):
        return bootstrap_enabled_extension_application(*extension_ids)

    def disable_extension_for_test(self, extension_id: str, *, version: str = "0.1.0") -> None:
        mark_extension_disabled(extension_id, version=version)


def bootstrap_enabled_extension_application(*extension_ids: str):
    reset_extension_runtime_state()
    reset_extension_application_bootstrap_state()
    enabled_ids = _resolve_required_extension_ids(extension_ids)
    for extension_id in enabled_ids:
        ExtensionInstallation.objects.update_or_create(
            extension_id=extension_id,
            defaults={
                "version": "0.1.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
    return bootstrap_extension_application(force=True)


def mark_extension_disabled(extension_id: str, *, version: str = "0.1.0") -> None:
    reset_extension_runtime_state()
    reset_extension_application_bootstrap_state()
    disabled_ids = _resolve_required_dependent_extension_ids(extension_id)
    for disabled_id in disabled_ids:
        ExtensionInstallation.objects.update_or_create(
            extension_id=disabled_id,
            defaults={
                "version": _resolve_extension_version(disabled_id, fallback=version),
                "source": "filesystem",
                "enabled": False,
                "installed": True,
                "booted": False,
            },
        )
    reset_extension_runtime_state()
    reset_extension_application_bootstrap_state()
    bootstrap_extension_application(force=True)


def _resolve_required_extension_ids(extension_ids: tuple[str, ...]) -> tuple[str, ...]:
    registry = get_extension_registry()
    registry.load(force=True)
    by_id = {
        extension.id: extension
        for extension in registry.get_extensions()
    }
    resolved: list[str] = []

    def visit(extension_id: str) -> None:
        if extension_id == "core" or extension_id in resolved:
            return
        extension = by_id.get(extension_id)
        if extension is None:
            return
        for dependency_id in extension.manifest.dependencies:
            visit(dependency_id)
        resolved.append(extension_id)

    for extension_id in extension_ids:
        visit(extension_id)
    return tuple(resolved)


def _resolve_required_dependent_extension_ids(extension_id: str) -> tuple[str, ...]:
    normalized = str(extension_id or "").strip()
    if not normalized:
        return ()
    registry = get_extension_registry()
    registry.load(force=True)
    extensions = registry.get_extensions()
    by_id = {extension.id: extension for extension in extensions}
    disabled: list[str] = []

    def visit(target_id: str) -> None:
        if target_id in disabled:
            return
        disabled.append(target_id)
        for extension in extensions:
            if target_id in tuple(extension.manifest.dependencies or ()):
                visit(extension.id)

    if normalized in by_id:
        visit(normalized)
    else:
        disabled.append(normalized)
    return tuple(disabled)


def _resolve_extension_version(extension_id: str, *, fallback: str) -> str:
    registry = get_extension_registry()
    registry.load(force=True)
    try:
        return registry.get_extension(extension_id).version or fallback
    except Exception:
        return fallback
