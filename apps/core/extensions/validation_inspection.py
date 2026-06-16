from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.core.extensions.backend import inspect_extension_backend_entry
from apps.core.extensions.types import ExtensionManifest
from apps.core.extensions.validation_rules import EXPORT_DECLARATION_PATTERN, EXPORT_FUNCTION_PATTERN


def _path_for_payload(path: Path | str | None) -> str:
    if not path:
        return ""
    return Path(path).as_posix()


def resolve_frontend_admin_entry(target: ExtensionManifest) -> str:
    return str(getattr(target, "frontend_admin_entry", "") or "").strip()


def resolve_frontend_forum_entry(target: ExtensionManifest) -> str:
    return str(getattr(target, "frontend_forum_entry", "") or "").strip()


def expected_frontend_entry(manifest: ExtensionManifest, base_path: Path, frontend: str) -> str:
    manifest_path = str(getattr(manifest, "path", "") or "").strip()
    if manifest_path:
        try:
            relative_path = (Path(manifest_path) / "frontend" / frontend / "index.js").relative_to(Path(base_path).parent)
            return relative_path.as_posix()
        except ValueError:
            pass
    return f"extensions/{manifest.id}/frontend/{frontend}/index.js"


def inspect_frontend_admin_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = resolve_frontend_admin_entry(manifest)
    required_exports = build_required_frontend_admin_exports(manifest)
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "required_exports": tuple(required_exports),
        "optional_exports": ("resolveDetailPage",),
        "available_exports": (),
        "exists": False,
        "resolved_path": "",
    }

    if not entry:
        return payload

    if not entry.startswith("extensions/"):
        payload.update({
            "entry_type": "external",
            "exists": False,
        })
        return payload

    if extensions_base_path is None:
        payload.update({
            "entry_type": "filesystem",
            "exists": False,
        })
        return payload

    absolute_path = Path(extensions_base_path).parent / entry
    payload.update({
        "entry_type": "filesystem",
        "exists": absolute_path.exists(),
        "resolved_path": _path_for_payload(absolute_path),
    })

    if not absolute_path.exists():
        return payload

    source = absolute_path.read_text(encoding="utf-8")
    payload["available_exports"] = inspect_available_frontend_exports(source)
    return payload


def resolve_admin_surface_implementation(
    manifest: ExtensionManifest,
    surface: str,
    available_exports: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, str | bool]:
    normalized_surface = str(surface or "").strip()
    export_names = {
        "detail": "resolveDetailPage",
        "settings": "resolveSettingsPage",
        "permissions": "resolvePermissionsPage",
        "operations": "resolveOperationsPage",
    }
    export_name = export_names.get(normalized_surface, "")
    export_set = set(available_exports or [])

    if export_name and export_name in export_set:
        return {
            "surface": normalized_surface,
            "mode": "custom",
            "mode_label": "自定义组件",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "settings" and getattr(manifest, "settings_schema", ()):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "自动生成表单",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "permissions" and getattr(manifest, "permissions_pages", ()):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "统一权限宿主",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "operations" and getattr(manifest, "operations_pages", ()) and (
        getattr(manifest, "admin_actions", ()) or getattr(manifest, "runtime_actions", ())
    ):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "统一操作宿主",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "detail":
        return {
            "surface": normalized_surface,
            "mode": "default",
            "mode_label": "平台默认详情",
            "export_name": export_name,
            "available": True,
        }

    return {
        "surface": normalized_surface,
        "mode": "missing",
        "mode_label": "未提供",
        "export_name": export_name,
        "available": False,
    }


def inspect_frontend_forum_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = resolve_frontend_forum_entry(manifest)
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "required_exports": ("extend",),
        "optional_exports": (),
        "available_exports": (),
        "exists": False,
        "resolved_path": "",
    }

    if not entry:
        return payload

    if not entry.startswith("extensions/"):
        payload.update({
            "entry_type": "external",
            "exists": False,
        })
        return payload

    if extensions_base_path is None:
        payload.update({
            "entry_type": "filesystem",
            "exists": False,
        })
        return payload

    absolute_path = Path(extensions_base_path).parent / entry
    payload.update({
        "entry_type": "filesystem",
        "exists": absolute_path.exists(),
        "resolved_path": _path_for_payload(absolute_path),
    })

    if not absolute_path.exists():
        return payload

    source = absolute_path.read_text(encoding="utf-8")
    payload["available_exports"] = inspect_available_frontend_exports(source)
    return payload


def inspect_backend_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = str(manifest.backend_entry or "").strip()
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "exists": False,
        "resolved_path": "",
        "available_hooks": (),
    }

    if not entry:
        return payload

    if not entry.startswith("extensions."):
        payload.update({
            "entry_type": "external",
            "exists": False,
        })
        return payload

    if extensions_base_path is None:
        payload["entry_type"] = "filesystem"
        return payload

    manifest_path = str(getattr(manifest, "path", "") or "").strip()
    extension_dir = Path(manifest_path) if manifest_path else Path(extensions_base_path) / manifest.id
    debug_definition = type("_DebugExtensionDefinition", (), {
        "manifest": type("_DebugManifest", (), {
            "id": manifest.id,
            "backend_entry": entry,
            "path": str(extension_dir),
        })(),
        "source": "filesystem",
    })()
    inspection = inspect_extension_backend_entry(debug_definition)
    payload.update(inspection)
    payload["resolved_path"] = _path_for_payload(payload.get("resolved_path"))
    return payload


def inspect_available_frontend_exports(source: str) -> tuple[str, ...]:
    return tuple(sorted(set(
        EXPORT_FUNCTION_PATTERN.findall(source)
        + EXPORT_DECLARATION_PATTERN.findall(source)
    )))


def build_required_frontend_admin_exports(manifest: ExtensionManifest) -> list[str]:
    required_exports = []
    if manifest.settings_pages:
        required_exports.append("resolveSettingsPage")
    if manifest.permissions_pages:
        required_exports.append("resolvePermissionsPage")
    if manifest.operations_pages:
        required_exports.append("resolveOperationsPage")
    return required_exports


def resolve_surface_from_export_name(export_name: str) -> str:
    return {
        "resolveSettingsPage": "settings",
        "resolvePermissionsPage": "permissions",
        "resolveOperationsPage": "operations",
        "resolveDetailPage": "detail",
    }.get(str(export_name or "").strip(), "")
