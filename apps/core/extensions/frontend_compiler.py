from __future__ import annotations

import json
import shutil
import subprocess
from hashlib import sha256
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
    input_revision: str = ""
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
            "input_revision": self.input_revision,
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
    input_revision = _build_extension_input_revision(manifest)

    command: tuple[str, ...] = ()
    completed = None
    if run_build:
        command = tuple(npm_command)
        try:
            completed = subprocess.run(
                list(command),
                cwd=str(get_frontend_root()),
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            result = ExtensionFrontendCompileResult(
                status="error",
                status_label="编译环境缺失",
                message=f"扩展前端资产编译命令不可用: {command[0]}",
                manifest_path=get_extension_frontend_build_manifest_path(),
                import_map_path=import_map_path,
                output_manifest_path=output_manifest_path,
                extension_count=len(manifest["extensions"]),
                input_revision=input_revision,
                command=command,
                returncode=None,
                stdout="",
                stderr=str(exc),
            )
            write_extension_frontend_output_manifest(result.to_dict())
            return result
        if completed.returncode != 0:
            result = ExtensionFrontendCompileResult(
                status="error",
                status_label="编译失败",
                message="扩展前端资产编译失败。",
                manifest_path=get_extension_frontend_build_manifest_path(),
                import_map_path=import_map_path,
                output_manifest_path=output_manifest_path,
                extension_count=len(manifest["extensions"]),
                input_revision=input_revision,
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
        input_revision=input_revision,
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
        inputs = dict(payload.get("inputs") or {})
        admin_entry = str(payload.get("admin_entry") or inputs.get("admin") or "").strip()
        forum_entry = str(payload.get("forum_entry") or inputs.get("forum") or "").strip()
        if admin_entry:
            admin_entries[extension_id] = admin_entry
        if forum_entry:
            forum_entries[extension_id] = forum_entry

    path.write_text(_build_import_map_source_from_manifest(manifest), encoding="utf-8")
    return path


def build_extension_frontend_output_manifest(manifest: dict) -> dict:
    vite_manifest = _read_json(get_frontend_vite_manifest_path())
    revision = _build_frontend_revision(vite_manifest)
    input_revision = _build_extension_input_revision(manifest)
    output = {
        "generated_at": timezone.now().isoformat(),
        "revision": revision,
        "input_revision": input_revision,
        "extensions": {},
        "vite_manifest_path": str(get_frontend_vite_manifest_path()),
        "vite_manifest_exists": bool(vite_manifest),
    }
    for extension_id, payload in sorted((manifest.get("extensions") or {}).items()):
        admin_entry = str(payload.get("admin_entry") or "").strip()
        forum_entry = str(payload.get("forum_entry") or "").strip()
        admin_routes = _frontend_route_component_chunk_keys(payload, extension_id, "admin", admin_entry)
        forum_routes = _frontend_route_component_chunk_keys(payload, extension_id, "forum", forum_entry)
        output["extensions"][extension_id] = {
            **dict(payload),
            "revision": revision,
            "outputs": {
                "admin": _resolve_vite_entry(vite_manifest, admin_entry, extra_chunks=admin_routes, revision=revision),
                "forum": _resolve_vite_entry(vite_manifest, forum_entry, extra_chunks=forum_routes, revision=revision),
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
    build_manifest = _read_json(get_extension_frontend_build_manifest_path())
    current_input_revision = _build_extension_input_revision(build_manifest) if build_manifest else ""
    input_revision = str(payload.get("input_revision") or "")
    return {
        "path": str(path),
        "exists": bool(payload),
        "generated_at": str(payload.get("generated_at") or ""),
        "input_revision": input_revision,
        "current_input_revision": current_input_revision,
        "input_stale": bool(payload and current_input_revision and input_revision != current_input_revision),
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
    extensions = {}
    for extension_id, entry in admin_entries.items():
        payload = extensions.setdefault(extension_id, {"inputs": {}})
        payload["admin_entry"] = entry
        payload["inputs"]["admin"] = entry
    for extension_id, entry in forum_entries.items():
        payload = extensions.setdefault(extension_id, {"inputs": {}})
        payload["forum_entry"] = entry
        payload["inputs"]["forum"] = entry
    return _build_import_map_source_from_manifest({
        "extensions": extensions,
    })


def _build_import_map_source_from_manifest(manifest: dict) -> str:
    def append_module(lines: list[str], seen_keys: set[str], key: str, importer: str) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key or normalized_key in seen_keys:
            return
        seen_keys.add(normalized_key)
        lines.append(f"  {json.dumps(normalized_key)}: {importer},")

    lines = [
        "// This file is generated by python manage.py build_extension_frontend.",
        "// Do not edit it by hand.",
        "",
        "function loadExtensionModule(moduleImporter, cssImporters = []) {",
        "  return Promise.all([...cssImporters.map(importer => importer()), moduleImporter()])",
        "    .then(results => results[results.length - 1])",
        "}",
        "",
        "export const generatedAdminExtensionModules = {",
    ]
    seen_admin_keys: set[str] = set()
    for extension_id, payload in sorted((manifest.get("extensions") or {}).items()):
        entry = str(payload.get("admin_entry") or payload.get("inputs", {}).get("admin") or "").strip()
        if entry:
            import_path = _frontend_import_path(entry)
            loader_key = _admin_loader_key(entry)
            css_importers = _frontend_css_importers(payload, extension_id)
            importer = _frontend_loader_source(import_path, css_importers)
            for key in _frontend_loader_keys(loader_key, import_path):
                append_module(lines, seen_admin_keys, key, importer)
            append_module(lines, seen_admin_keys, extension_id, importer)
        for key, component_path in _frontend_route_component_imports(payload, extension_id, "admin", entry):
            append_module(lines, seen_admin_keys, key, f"() => import({json.dumps(component_path)})")
    lines.extend([
        "}",
        "",
        "export const generatedForumExtensionModules = {",
    ])
    seen_forum_keys: set[str] = set()
    for extension_id, payload in sorted((manifest.get("extensions") or {}).items()):
        entry = str(payload.get("forum_entry") or payload.get("inputs", {}).get("forum") or "").strip()
        if entry:
            import_path = _frontend_import_path(entry)
            loader_key = _forum_loader_key(entry)
            css_importers = _frontend_css_importers(payload, extension_id)
            importer = _frontend_loader_source(import_path, css_importers)
            for key in _frontend_loader_keys(loader_key, import_path):
                append_module(lines, seen_forum_keys, key, importer)
            append_module(lines, seen_forum_keys, extension_id, importer)
        for key, component_path in _frontend_route_component_imports(payload, extension_id, "forum", entry):
            append_module(lines, seen_forum_keys, key, f"() => import({json.dumps(component_path)})")
    lines.extend([
        "}",
        "",
    ])
    return "\n".join(lines)


def _frontend_loader_source(import_path: str, css_importers: list[str]) -> str:
    if not css_importers:
        return f"() => import({json.dumps(import_path)})"
    css_source = ", ".join(f"() => import({json.dumps(path)})" for path in css_importers)
    return f"() => loadExtensionModule(() => import({json.dumps(import_path)}), [{css_source}])"


def _frontend_css_importers(payload: dict, extension_id: str) -> list[str]:
    paths = []
    for css_path in payload.get("css") or []:
        import_path = _frontend_extension_asset_import_path(str(css_path or ""), extension_id)
        if import_path and _is_vite_style_import(import_path):
            paths.append(import_path)
    return _dedupe(paths)


def _frontend_route_component_imports(payload: dict, extension_id: str, frontend: str, entry: str) -> list[tuple[str, str]]:
    output = []
    for route in payload.get("routes") or []:
        if str(route.get("frontend") or "forum").strip() != frontend:
            continue
        if bool(route.get("removed")):
            continue
        component = str(route.get("component") or "").strip()
        if not component or _is_core_route_component(component, frontend):
            continue
        import_path = _frontend_route_component_import_path(component, extension_id, frontend, entry)
        if not import_path:
            continue
        for key in _frontend_route_component_keys(component, extension_id, frontend, entry, import_path):
            output.append((key, import_path))
    seen = set()
    deduped = []
    for key, import_path in output:
        signature = (key, import_path)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(signature)
    return deduped


def _frontend_route_component_chunk_keys(payload: dict, extension_id: str, frontend: str, entry: str) -> list[str]:
    return _dedupe([
        import_path
        for _, import_path in _frontend_route_component_imports(payload, extension_id, frontend, entry)
    ])


def _frontend_route_component_import_path(component: str, extension_id: str, frontend: str, entry: str) -> str:
    normalized = str(component or "").strip().replace("\\", "/")
    if not normalized:
        return ""
    if normalized.startswith("extensions/"):
        return _frontend_import_path(normalized)
    if normalized.startswith("./") or normalized.startswith("../"):
        entry_dir = "/".join(str(entry or "").strip().replace("\\", "/").split("/")[:-1])
        if entry_dir:
            return _frontend_import_path(_normalize_frontend_path(f"{entry_dir}/{normalized}"))
        return _frontend_import_path(_normalize_frontend_path(f"extensions/{extension_id}/frontend/{frontend}/{normalized}"))
    if "/" in normalized:
        return _frontend_import_path(_normalize_frontend_path(f"extensions/{extension_id}/{normalized}"))
    return _frontend_import_path(_normalize_frontend_path(f"extensions/{extension_id}/frontend/{frontend}/{normalized}"))


def _frontend_route_component_keys(component: str, extension_id: str, frontend: str, entry: str, import_path: str) -> list[str]:
    normalized = str(component or "").strip().replace("\\", "/")
    entry_dir = "/".join(str(entry or "").strip().replace("\\", "/").split("/")[:-1])
    canonical = ""
    if normalized.startswith(("./", "../")):
        canonical = _normalize_frontend_path(
            f"{entry_dir}/{normalized}" if entry_dir else f"extensions/{extension_id}/frontend/{frontend}/{normalized}"
        )
    elif normalized.startswith("extensions/"):
        canonical = _normalize_frontend_path(normalized)
    elif "/" in normalized:
        canonical = _normalize_frontend_path(f"extensions/{extension_id}/{normalized}")
    else:
        canonical = _normalize_frontend_path(f"extensions/{extension_id}/frontend/{frontend}/{normalized}")
    keys = [
        canonical,
        _frontend_import_path(canonical),
        import_path,
        f"{extension_id}:{normalized}",
        f"{extension_id}:{canonical}",
    ]
    if normalized.startswith("extensions/"):
        keys.insert(0, normalized)
    return _frontend_loader_keys(*keys)


def _frontend_extension_asset_import_path(path: str, extension_id: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized or normalized.startswith(("http://", "https://", "/")):
        return ""
    if normalized.startswith("extensions/") or normalized.startswith("../"):
        return _frontend_import_path(normalized)
    return _frontend_import_path(f"extensions/{extension_id}/{normalized}")


def _is_vite_style_import(path: str) -> bool:
    return str(path or "").lower().split("?", 1)[0].endswith((".css", ".scss", ".sass", ".less"))


def _is_core_route_component(component: str, frontend: str) -> bool:
    normalized = str(component or "").strip()
    if str(frontend or "").strip() == "admin":
        return normalized in {
            "AdvancedPage",
            "AppearancePage",
            "AuditLogsPage",
            "BasicsPage",
            "DashboardPage",
            "DeveloperDocsPage",
            "ExtensionDetailPage",
            "ExtensionHostPage",
            "MailPage",
            "PermissionsPage",
            "UsersPage",
        }
    return normalized in {
    }


def _dedupe(values: list[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _normalize_frontend_path(path: str) -> str:
    parts = []
    for part in str(path or "").replace("\\", "/").split("/"):
        if not part or part == ".":
            continue
        if part == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


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


def _resolve_vite_entry(vite_manifest: dict, entry: str, *, extra_chunks: list[str] | None = None, revision: str = "") -> dict:
    normalized = str(entry or "").strip().replace("\\", "/")
    extra_dynamic_imports = _dedupe([str(item or "").strip().replace("\\", "/") for item in extra_chunks or []])
    if not normalized:
        return {
            "revision": revision,
            "chunks": _resolve_vite_chunks(vite_manifest, extra_dynamic_imports, revision=revision),
        } if extra_dynamic_imports else {}
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
            dynamic_imports = list(payload.get("dynamicImports") or [])
            return {
                "file": payload.get("file", ""),
                "css": list(payload.get("css") or []),
                "imports": list(payload.get("imports") or []),
                "dynamic_imports": dynamic_imports,
                "revision": revision,
                "chunks": _resolve_vite_chunks(vite_manifest, _dedupe([*dynamic_imports, *extra_dynamic_imports]), revision=revision),
            }
    return {
        "revision": revision,
        "chunks": _resolve_vite_chunks(vite_manifest, extra_dynamic_imports, revision=revision),
    } if extra_dynamic_imports else {}


def _resolve_vite_chunks(vite_manifest: dict, dynamic_imports: list[str], *, revision: str = "") -> list[dict]:
    chunks = []
    for key in dynamic_imports:
        normalized_key = str(key or "").strip().replace("\\", "/")
        if not normalized_key:
            continue
        payload = vite_manifest.get(normalized_key)
        if not isinstance(payload, dict):
            chunks.append({
                "key": normalized_key,
                "module_id": _resolve_vite_module_id(normalized_key),
                "file": normalized_key,
                "css": [],
                "imports": [],
                "dynamic_imports": [],
                "revision": revision,
            })
            continue
        nested_dynamic_imports = list(payload.get("dynamicImports") or [])
        chunks.append({
            "key": normalized_key,
            "module_id": _resolve_vite_module_id(normalized_key),
            "file": str(payload.get("file") or "").strip(),
            "css": list(payload.get("css") or []),
            "imports": list(payload.get("imports") or []),
            "dynamic_imports": nested_dynamic_imports,
            "revision": revision,
        })
    return chunks


def _build_frontend_revision(vite_manifest: dict) -> str:
    if not vite_manifest:
        return ""
    payload = json.dumps(vite_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_extension_input_revision(manifest: dict) -> str:
    payload = json.dumps(manifest.get("extensions") or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _resolve_vite_module_id(key: str) -> str:
    normalized = str(key or "").strip().replace("\\", "/").lstrip("./")
    marker = "extensions/"
    if marker in normalized:
        suffix = normalized.split(marker, 1)[1]
        parts = suffix.split("/", 1)
        if len(parts) == 2:
            return parts[1]
    return normalized


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
