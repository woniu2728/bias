from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core.extensions.assets import (
    get_extension_assets_root,
    get_extension_frontend_build_manifest_path,
    write_extension_frontend_manifest,
)
from apps.core.extensions.lifecycle import clear_extension_runtime_rebuild_marker


@dataclass(frozen=True)
class ExtensionFrontendCompileResult:
    status: str
    status_label: str
    message: str
    manifest_path: Path
    import_map_path: Path
    output_manifest_path: Path
    extension_count: int
    command: tuple[str, ...] = ()
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    output_manifest: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "status_label": self.status_label,
            "message": self.message,
            "manifest_path": str(self.manifest_path),
            "import_map_path": str(self.import_map_path),
            "output_manifest_path": str(self.output_manifest_path),
            "extension_count": self.extension_count,
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output_manifest": dict(self.output_manifest or {}),
            "executed_at": timezone.now().isoformat(),
        }


def get_frontend_root() -> Path:
    return Path(settings.BASE_DIR) / "frontend"


def get_frontend_dist_root() -> Path:
    return get_frontend_root() / "dist"


def get_frontend_vite_manifest_path() -> Path:
    return get_frontend_dist_root() / ".vite" / "manifest.json"


def get_extension_frontend_import_map_path() -> Path:
    return get_frontend_root() / "src" / "generated" / "extensionImportMap.js"


def get_extension_frontend_output_manifest_path() -> Path:
    return get_extension_assets_root() / "frontend-output-manifest.json"


def get_published_frontend_root() -> Path:
    return Path(settings.BASE_DIR) / "static" / "frontend"


EMPTY_EXTENSION_FRONTEND_IMPORT_MAP_SOURCE = "\n".join([
    "// This file is overwritten by python manage.py build_extension_frontend.",
    "// Keep the empty defaults so a fresh checkout can build before extension assets are generated.",
    "",
    "export const generatedAdminExtensionModules = {}",
    "export const generatedForumExtensionModules = {}",
    "",
])


def recompile_extension_frontend_assets(
    extensions,
    *,
    run_build: bool = False,
    npm_command: tuple[str, ...] = ("npm", "run", "build"),
    clear_marker: bool = True,
    publish_dist: bool = False,
) -> ExtensionFrontendCompileResult:
    manifest = write_extension_frontend_manifest(extensions)
    import_map_path = write_extension_frontend_import_map(manifest)
    output_manifest_path = get_extension_frontend_output_manifest_path()

    command: tuple[str, ...] = ()
    completed = None
    if run_build:
        command = tuple(npm_command)
        completed = subprocess.run(
            list(command),
            cwd=str(get_frontend_root()),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            result = ExtensionFrontendCompileResult(
                status="error",
                status_label="编译失败",
                message="扩展前端资产编译失败。",
                manifest_path=get_extension_frontend_build_manifest_path(),
                import_map_path=import_map_path,
                output_manifest_path=output_manifest_path,
                extension_count=len(manifest["extensions"]),
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            write_extension_frontend_output_manifest(result.to_dict())
            return result

    output_manifest = build_extension_frontend_output_manifest(manifest)
    publish_result = copy_frontend_dist_to_static() if publish_dist else {
        "status": "skipped",
        "status_label": "已跳过",
        "message": "未请求发布前端 dist。",
        "source": str(get_frontend_dist_root()),
        "target": str(get_published_frontend_root()),
    }
    output_manifest["build"] = {
        "ran": bool(run_build),
        "command": list(command),
        "returncode": completed.returncode if completed is not None else None,
        "stdout": completed.stdout if completed is not None else "",
        "stderr": completed.stderr if completed is not None else "",
        "compiled_at": timezone.now().isoformat(),
        "published": publish_result,
    }
    write_extension_frontend_output_manifest(output_manifest)
    if clear_marker:
        clear_extension_runtime_rebuild_marker()

    return ExtensionFrontendCompileResult(
        status="ok",
        status_label="已编译" if run_build else "已生成",
        message="扩展前端资产已编译。" if run_build else "扩展前端资产清单已生成。",
        manifest_path=get_extension_frontend_build_manifest_path(),
        import_map_path=import_map_path,
        output_manifest_path=output_manifest_path,
        extension_count=len(manifest["extensions"]),
        command=command,
        returncode=completed.returncode if completed is not None else None,
        stdout=completed.stdout if completed is not None else "",
        stderr=completed.stderr if completed is not None else "",
        output_manifest=output_manifest,
    )


def flush_extension_frontend_assets(*, include_published: bool = False, remove_import_map: bool = False) -> dict:
    removed: list[str] = []
    for path in (
        get_extension_frontend_build_manifest_path(),
        get_extension_frontend_output_manifest_path(),
    ):
        if path.exists():
            path.unlink()
            removed.append(str(path))

    import_map_path = get_extension_frontend_import_map_path()
    reset: list[str] = []
    if remove_import_map:
        if import_map_path.exists():
            import_map_path.unlink()
            removed.append(str(import_map_path))
        generated_dir = import_map_path.parent
        if generated_dir.exists() and not any(generated_dir.iterdir()):
            generated_dir.rmdir()
    else:
        reset_extension_frontend_import_map()
        reset.append(str(import_map_path))

    published_root = get_published_frontend_root()
    if include_published and published_root.exists():
        shutil.rmtree(published_root)
        removed.append(str(published_root))

    return {
        "status": "ok",
        "status_label": "已清理",
        "message": "扩展前端资产清单已清理。",
        "removed": removed,
        "reset": reset,
        "executed_at": timezone.now().isoformat(),
    }


def reset_extension_frontend_import_map() -> Path:
    path = get_extension_frontend_import_map_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EMPTY_EXTENSION_FRONTEND_IMPORT_MAP_SOURCE, encoding="utf-8")
    return path


def write_extension_frontend_import_map(manifest: dict) -> Path:
    path = get_extension_frontend_import_map_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    admin_entries: dict[str, str] = {}
    forum_entries: dict[str, str] = {}
    for extension_id, payload in sorted((manifest.get("extensions") or {}).items()):
        admin_entry = str(payload.get("admin_entry") or "").strip()
        forum_entry = str(payload.get("forum_entry") or "").strip()
        if admin_entry:
            admin_entries[extension_id] = admin_entry
        if forum_entry:
            forum_entries[extension_id] = forum_entry

    path.write_text(_build_import_map_source(admin_entries, forum_entries), encoding="utf-8")
    return path


def build_extension_frontend_output_manifest(manifest: dict) -> dict:
    vite_manifest = _read_json(get_frontend_vite_manifest_path())
    output = {
        "generated_at": timezone.now().isoformat(),
        "extensions": {},
        "vite_manifest_path": str(get_frontend_vite_manifest_path()),
        "vite_manifest_exists": bool(vite_manifest),
    }
    for extension_id, payload in sorted((manifest.get("extensions") or {}).items()):
        admin_entry = str(payload.get("admin_entry") or "").strip()
        forum_entry = str(payload.get("forum_entry") or "").strip()
        output["extensions"][extension_id] = {
            **dict(payload),
            "outputs": {
                "admin": _resolve_vite_entry(vite_manifest, admin_entry),
                "forum": _resolve_vite_entry(vite_manifest, forum_entry),
            },
        }
    return output


def write_extension_frontend_output_manifest(payload: dict) -> Path:
    path = get_extension_frontend_output_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def inspect_extension_frontend_output_manifest() -> dict:
    path = get_extension_frontend_output_manifest_path()
    payload = _read_json(path)
    return {
        "path": str(path),
        "exists": bool(payload),
        "generated_at": str(payload.get("generated_at") or ""),
        "vite_manifest_path": str(payload.get("vite_manifest_path") or get_frontend_vite_manifest_path()),
        "vite_manifest_exists": bool(payload.get("vite_manifest_exists")),
        "extension_count": len(payload.get("extensions") or {}),
        "extensions": dict(payload.get("extensions") or {}),
        "build": dict(payload.get("build") or {}),
    }


def copy_frontend_dist_to_static() -> dict:
    source = get_frontend_dist_root()
    target = get_published_frontend_root()
    if not source.exists():
        return {
            "status": "skipped",
            "status_label": "已跳过",
            "message": "前端 dist 目录不存在。",
            "source": str(source),
            "target": str(target),
        }
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return {
        "status": "ok",
        "status_label": "已发布",
        "message": "前端 dist 已发布到 static/frontend。",
        "source": str(source),
        "target": str(target),
    }


def _build_import_map_source(admin_entries: dict[str, str], forum_entries: dict[str, str]) -> str:
    lines = [
        "// This file is generated by python manage.py build_extension_frontend.",
        "// Do not edit it by hand.",
        "",
        "export const generatedAdminExtensionModules = {",
    ]
    for extension_id, entry in admin_entries.items():
        import_path = _frontend_import_path(entry)
        loader_key = _admin_loader_key(entry)
        for key in _frontend_loader_keys(loader_key, import_path):
            lines.append(f"  {json.dumps(key)}: () => import({json.dumps(import_path)}),")
        lines.append(f"  {json.dumps(extension_id)}: () => import({json.dumps(import_path)}),")
    lines.extend([
        "}",
        "",
        "export const generatedForumExtensionModules = {",
    ])
    for extension_id, entry in forum_entries.items():
        import_path = _frontend_import_path(entry)
        loader_key = _forum_loader_key(entry)
        for key in _frontend_loader_keys(loader_key, import_path):
            lines.append(f"  {json.dumps(key)}: () => import({json.dumps(import_path)}),")
        lines.append(f"  {json.dumps(extension_id)}: () => import({json.dumps(import_path)}),")
    lines.extend([
        "}",
        "",
    ])
    return "\n".join(lines)


def _frontend_loader_keys(*keys: str) -> list[str]:
    seen = set()
    normalized_keys = []
    for key in keys:
        normalized = str(key or "").strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_keys.append(normalized)
    return normalized_keys


def _frontend_import_path(entry: str) -> str:
    normalized = str(entry or "").strip().replace("\\", "/")
    if normalized.startswith("extensions/"):
        return f"../../../{normalized}"
    return normalized


def _admin_loader_key(entry: str) -> str:
    normalized = str(entry or "").strip().replace("\\", "/")
    if normalized.startswith("extensions/"):
        return f"../../../{normalized}"
    return normalized


def _forum_loader_key(entry: str) -> str:
    normalized = str(entry or "").strip().replace("\\", "/")
    if normalized.startswith("extensions/"):
        return f"../../../{normalized}"
    return normalized


def _resolve_vite_entry(vite_manifest: dict, entry: str) -> dict:
    normalized = str(entry or "").strip().replace("\\", "/")
    if not normalized:
        return {}
    candidates = [
        normalized,
        f"../{normalized}",
        f"../../{normalized}",
        f"../{_frontend_import_path(normalized)}",
        _frontend_import_path(normalized).lstrip("./"),
    ]
    for key in candidates:
        payload = vite_manifest.get(key)
        if isinstance(payload, dict):
            return {
                "file": payload.get("file", ""),
                "css": list(payload.get("css") or []),
                "imports": list(payload.get("imports") or []),
                "dynamic_imports": list(payload.get("dynamicImports") or []),
            }
    return {}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
