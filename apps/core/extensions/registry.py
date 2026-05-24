from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError

from apps.core.extensions.builtin_adapter import adapt_builtin_module_to_extension
from apps.core.extensions.exceptions import ExtensionNotFoundError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.types import ExtensionDefinition, ExtensionRuntimeState
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
            return definition
        if installation is None:
            return definition

        runtime = ExtensionRuntimeState(
            installed=installation.installed,
            enabled=installation.enabled,
            booted=installation.booted,
            healthy=definition.runtime.healthy,
            migration_state=definition.runtime.migration_state,
            migration_label=definition.runtime.migration_label,
            dependency_state=definition.runtime.dependency_state,
            dependency_state_label=definition.runtime.dependency_state_label,
            runtime_issues=definition.runtime.runtime_issues,
        )

        return ExtensionDefinition(
            manifest=definition.manifest,
            runtime=runtime,
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
