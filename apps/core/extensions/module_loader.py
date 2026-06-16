from __future__ import annotations

import importlib.util
import importlib
import re
from pathlib import Path
from types import ModuleType


BACKEND_FUNCTION_PATTERN = re.compile(r"^(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE)


def _path_for_payload(path: Path | str | None) -> str:
    if not path:
        return ""
    return Path(path).as_posix()


def resolve_extension_backend_file(definition) -> Path | None:
    if definition.source == "python-package":
        return None

    backend_entry = str(definition.manifest.backend_entry or "").strip()
    root_path = str(definition.manifest.path or "").strip()
    if not backend_entry or not root_path:
        return None

    extension_root = Path(root_path)
    extension_id = str(getattr(definition, "id", "") or getattr(definition.manifest, "id", "") or "").strip()
    extension_package = extension_id.replace("-", "_")
    expected_prefix = f"extensions.{extension_package}."
    if not backend_entry.startswith(expected_prefix):
        return None

    relative_module = backend_entry[len(expected_prefix):]
    relative_parts = [
        part
        for part in relative_module.split(".")
        if part
    ]
    if not relative_parts:
        return None

    return extension_root.joinpath(*relative_parts).with_suffix(".py")


def inspect_extension_backend_module(definition) -> dict:
    entry = str(definition.manifest.backend_entry or "").strip()
    root_path = str(definition.manifest.path or "").strip()
    payload: dict = {
        "entry": entry,
        "entry_type": "missing",
        "exists": False,
        "resolved_path": "",
        "available_hooks": (),
    }

    if definition.source == "python-package":
        payload.update({
            "entry_type": "python-package",
            "exists": _can_import_module(entry),
            "resolved_path": entry,
        })
        if payload["exists"]:
            module = importlib.import_module(entry)
            payload["available_hooks"] = tuple(sorted(
                name for name in dir(module)
                if callable(getattr(module, name, None)) and (name.startswith("run_") or name == "extend")
            ))
        return payload

    if not entry:
        return payload

    if not root_path:
        payload["entry_type"] = "filesystem"
        return payload

    backend_file = resolve_extension_backend_file(definition)
    payload.update({
        "entry_type": "filesystem",
        "exists": bool(backend_file and backend_file.exists()),
        "resolved_path": _path_for_payload(backend_file),
    })
    if backend_file is None or not backend_file.exists():
        return payload

    source = backend_file.read_text(encoding="utf-8")
    payload["available_hooks"] = tuple(sorted(set(BACKEND_FUNCTION_PATTERN.findall(source))))
    return payload


def load_extension_backend_module(definition) -> ModuleType | None:
    backend_entry = str(definition.manifest.backend_entry or "").strip()
    if definition.source == "python-package":
        if not backend_entry:
            return None
        try:
            return importlib.import_module(backend_entry)
        except Exception:
            return None

    root_path = str(definition.manifest.path or "").strip()
    if not backend_entry or not root_path:
        return None

    backend_file = resolve_extension_backend_file(definition)
    if backend_file is None:
        return None
    if not backend_file.exists():
        return None

    module_name = f"bias_extension_backend_{definition.id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, backend_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载扩展后端入口: {backend_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _can_import_module(module_name: str) -> bool:
    if not module_name:
        return False
    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True
