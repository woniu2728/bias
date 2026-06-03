from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.core.extensions.manager import ExtensionManager, get_extension_manager


class ExtensionRegistry(ExtensionManager):
    pass


def get_extension_registry() -> ExtensionRegistry:
    manager = get_extension_manager()
    default_path = Path(settings.BASE_DIR) / "extensions"
    if isinstance(manager, ExtensionRegistry):
        if manager.extensions_path != default_path:
            registry = ExtensionRegistry(extensions_path=default_path)

            from apps.core.extensions import manager as manager_module

            manager_module._manager = registry
            registry.load(force=True)
            return registry
        return manager

    registry = ExtensionRegistry(extensions_path=manager.extensions_path)
    registry.load(force=True)

    from apps.core.extensions import manager as manager_module

    manager_module._manager = registry
    return registry
