from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from django.conf import settings

from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.extender_values import flatten_extenders
from apps.core.extensions.types import ExtensionManifest, ExtensionRuntimeState


SITE_EXTENSION_ID = "site"
SITE_EXTENDER_FILENAME = "extend.py"


def get_site_extender_path() -> Path:
    return Path(settings.BASE_DIR) / SITE_EXTENDER_FILENAME


def load_site_extenders(*, base_dir: Path | None = None) -> tuple[Any, ...]:
    extender_path = Path(base_dir or settings.BASE_DIR) / SITE_EXTENDER_FILENAME
    if not extender_path.exists() or not extender_path.is_file():
        return ()

    module = _load_site_extender_module(extender_path)
    extenders = _resolve_site_extenders(module)
    return flatten_extenders(extenders)


def build_site_extension(extenders: tuple[Any, ...]) -> Extension | None:
    if not extenders:
        return None

    manifest = ExtensionManifest(
        id=SITE_EXTENSION_ID,
        name="Site",
        version="1.0.0",
        description="站点本地扩展入口。",
        source="site",
        path=str(Path(settings.BASE_DIR)),
    )
    extension = Extension(
        manifest=manifest,
        runtime=ExtensionRuntimeState(
            installed=True,
            enabled=True,
            booted=True,
            status_key="active",
            status_label="已启用",
        ),
        module_ids=(),
        source="site",
        bootstrapper=lambda current, host: host.apply_extension_extenders(current, extenders),
    )
    return extension


def _load_site_extender_module(path: Path) -> ModuleType:
    module_name = "bias_site_extend"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载站点扩展入口: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_site_extenders(module: ModuleType):
    factory = getattr(module, "extend", None)
    if callable(factory):
        return factory() or ()
    return getattr(module, "extenders", ()) or ()


