from __future__ import annotations

from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.types import ExtensionAssembly


def get_extension_assembly_catalog(
    *,
    force: bool = False,
    registry=None,
) -> dict[str, ExtensionAssembly]:
    manager = registry if registry is not None else get_extension_manager()
    return manager.get_extension_assembly_catalog(force=force)


def get_enabled_extension_assemblies(
    *,
    force: bool = False,
    registry=None,
) -> list[ExtensionAssembly]:
    manager = registry if registry is not None else get_extension_manager()
    return manager.get_enabled_extension_assemblies(
        force=force,
    )
