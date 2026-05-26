from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from django.utils import timezone

from apps.core.extensions.types import ExtensionDefinition

BACKEND_FUNCTION_PATTERN = re.compile(r"^(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE)


@dataclass(frozen=True)
class ExtensionBackendContext:
    extension_id: str
    extension_name: str
    version: str
    source: str
    extension_path: str
    manifest_path: str
    backend_entry: str
    migration_namespace: str
    installed: bool
    enabled: bool
    booted: bool
    meta: dict[str, Any]


def build_backend_context(
    definition: ExtensionDefinition,
    *,
    meta: dict[str, Any] | None = None,
    ) -> ExtensionBackendContext:
    extension_path = str(definition.manifest.path or "").strip()
    manifest_path = str(Path(extension_path) / "extension.json") if extension_path else ""
    return ExtensionBackendContext(
        extension_id=definition.id,
        extension_name=definition.name,
        version=definition.version,
        source=definition.source,
        extension_path=extension_path,
        manifest_path=manifest_path,
        backend_entry=str(definition.manifest.backend_entry or "").strip(),
        migration_namespace=str(definition.manifest.migration_namespace or "").strip(),
        installed=bool(definition.runtime.installed),
        enabled=bool(definition.runtime.enabled),
        booted=bool(definition.runtime.booted),
        meta=dict(meta or {}),
    )


def inspect_extension_backend_entry(definition: ExtensionDefinition) -> dict[str, Any]:
    entry = str(definition.manifest.backend_entry or "").strip()
    root_path = str(definition.manifest.path or "").strip()
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "exists": False,
        "resolved_path": "",
        "available_hooks": (),
    }

    if definition.source == "builtin-module":
        payload.update({
            "entry_type": "builtin",
            "exists": True,
        })
        return payload

    if not entry:
        return payload

    if not root_path:
        payload["entry_type"] = "filesystem"
        return payload

    backend_file = Path(root_path) / "backend" / "ext.py"
    payload.update({
        "entry_type": "filesystem",
        "exists": backend_file.exists(),
        "resolved_path": str(backend_file),
    })
    if not backend_file.exists():
        return payload

    source = backend_file.read_text(encoding="utf-8")
    payload["available_hooks"] = tuple(sorted(set(BACKEND_FUNCTION_PATTERN.findall(source))))
    return payload


def load_extension_backend_module(definition: ExtensionDefinition) -> ModuleType | None:
    if definition.source == "builtin-module":
        return None

    backend_entry = str(definition.manifest.backend_entry or "").strip()
    root_path = str(definition.manifest.path or "").strip()
    if not backend_entry or not root_path:
        return None

    backend_file = Path(root_path) / "backend" / "ext.py"
    if not backend_file.exists():
        return None

    module_name = f"bias_extension_backend_{definition.id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, backend_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载扩展后端入口: {backend_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_extension_backend_hook(
    definition: ExtensionDefinition,
    hook_name: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    module = load_extension_backend_module(definition)
    if module is None:
        return {
            "hook": hook_name,
            "status": "skipped",
            "status_label": "已跳过",
            "message": "当前扩展没有可执行的后端入口。",
        }

    hook = getattr(module, hook_name, None)
    if not callable(hook):
        return {
            "hook": hook_name,
            "status": "skipped",
            "status_label": "已跳过",
            "message": f"后端入口未声明 {hook_name}。",
        }

    context = build_backend_context(definition, meta=meta)
    result = hook(context)
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
