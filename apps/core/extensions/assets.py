from __future__ import annotations

import json
import shutil
import hashlib
from pathlib import Path

from django.conf import settings
from django.utils import timezone


def get_extension_assets_root() -> Path:
    return Path(settings.BASE_DIR) / "static" / "extensions"


def get_extension_asset_manifest_path() -> Path:
    return get_extension_assets_root() / "manifest.json"


def get_extension_frontend_build_manifest_path() -> Path:
    return get_extension_assets_root() / "frontend-build-manifest.json"


def get_extension_asset_url(extension_id: str, file_path: str) -> str:
    base_url = str(settings.STATIC_URL or "/static/").rstrip("/")
    normalized_file_path = str(file_path or "").strip().lstrip("/").replace("\\", "/")
    return f"{base_url}/extensions/{extension_id}/{normalized_file_path}"


def publish_extension_assets(extension) -> dict:
    root_path = Path(extension.manifest.path) if extension.manifest.path else None
    source = root_path / "assets" if root_path else None
    if source is None or not source.exists() or not source.is_dir():
        return _result(extension.id, "skipped", "已跳过", "扩展未提供 assets 目录。")

    target = get_extension_assets_root() / extension.id
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    files = [_build_asset_file_record(extension.id, target, path) for path in sorted(target.rglob("*")) if path.is_file()]
    cache_key = _build_cache_key(files)
    manifest = _read_manifest()
    manifest[extension.id] = {
        "extension_id": extension.id,
        "source": str(source),
        "target": str(target),
        "files": files,
        "cache_key": cache_key,
        "frontend": _build_frontend_asset_manifest(extension),
        "published_at": timezone.now().isoformat(),
    }
    _write_manifest(manifest)
    return _result(
        extension.id,
        "ok",
        "已发布",
        "扩展资产已发布。",
        details={"source": str(source), "target": str(target), "files": files, "cache_key": cache_key},
    )


def unpublish_extension_assets(extension) -> dict:
    target = get_extension_assets_root() / extension.id
    removed = False
    if target.exists():
        shutil.rmtree(target)
        removed = True

    manifest = _read_manifest()
    manifest.pop(extension.id, None)
    _write_manifest(manifest)
    return _result(
        extension.id,
        "ok",
        "已清理" if removed else "无需清理",
        "扩展资产已清理。" if removed else "扩展没有已发布资产。",
        details={"target": str(target), "removed": removed},
    )


def inspect_published_extension_assets(extension) -> dict:
    manifest = _read_manifest()
    payload = dict(manifest.get(extension.id) or {})
    target = get_extension_assets_root() / extension.id
    return {
        "published": bool(payload),
        "target": str(target),
        "target_exists": target.exists(),
        "files": list(payload.get("files") or []),
        "cache_key": str(payload.get("cache_key") or ""),
        "frontend": dict(payload.get("frontend") or {}),
        "published_at": str(payload.get("published_at") or ""),
    }


def build_extension_frontend_manifest(extensions) -> dict:
    manifest = {
        "generated_at": timezone.now().isoformat(),
        "extensions": {},
    }
    for extension in extensions:
        admin_entry = str(extension.frontend_admin_entry or "").strip()
        forum_entry = str(extension.frontend_forum_entry or "").strip()
        if not admin_entry and not forum_entry:
            continue
        extension_payload = {
            "extension_id": extension.id,
            "source": extension.source,
            "admin_entry": admin_entry,
            "forum_entry": forum_entry,
            "css": list(getattr(extension.discover(), "frontend_css", ()) or ()),
            "js_directories": list(getattr(extension.discover(), "frontend_js_directories", ()) or ()),
            "preloads": _serialize_frontend_values(getattr(extension.discover(), "frontend_preloads", ()) or ()),
            "document_attributes": _serialize_frontend_values(getattr(extension.discover(), "frontend_document_attributes", ()) or ()),
            "title_driver": _serialize_frontend_value(getattr(extension.discover(), "frontend_title_driver", None)),
            "inputs": {},
        }
        if admin_entry:
            extension_payload["inputs"]["admin"] = admin_entry
        if forum_entry:
            extension_payload["inputs"]["forum"] = forum_entry
        extension_payload["cache_key"] = _build_frontend_cache_key(extension_payload["inputs"])
        manifest["extensions"][extension.id] = extension_payload
    return manifest


def write_extension_frontend_manifest(extensions) -> dict:
    manifest = build_extension_frontend_manifest(extensions)
    path = get_extension_frontend_build_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _read_manifest() -> dict:
    path = get_extension_asset_manifest_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_manifest(payload: dict) -> None:
    path = get_extension_asset_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _build_asset_file_record(extension_id: str, root: Path, path: Path) -> dict:
    relative_path = str(path.relative_to(root)).replace("\\", "/")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": relative_path,
        "size": path.stat().st_size,
        "sha256": digest,
        "url": get_extension_asset_url(extension_id, relative_path),
    }


def _build_cache_key(files: list[dict]) -> str:
    hasher = hashlib.sha256()
    for item in files:
        hasher.update(str(item.get("path") or "").encode("utf-8"))
        hasher.update(str(item.get("sha256") or "").encode("utf-8"))
    return hasher.hexdigest()[:16]


def _build_frontend_asset_manifest(extension) -> dict:
    runtime_view = extension.discover()
    return {
        "admin_entry": str(extension.frontend_admin_entry or ""),
        "forum_entry": str(extension.frontend_forum_entry or ""),
        "css": list(getattr(runtime_view, "frontend_css", ()) or ()),
        "js_directories": list(getattr(runtime_view, "frontend_js_directories", ()) or ()),
        "preloads": _serialize_frontend_values(getattr(runtime_view, "frontend_preloads", ()) or ()),
        "document_attributes": _serialize_frontend_values(getattr(runtime_view, "frontend_document_attributes", ()) or ()),
        "title_driver": _serialize_frontend_value(getattr(runtime_view, "frontend_title_driver", None)),
        "cache_busting": True,
    }


def _build_frontend_cache_key(inputs: dict) -> str:
    hasher = hashlib.sha256()
    for key in sorted(inputs.keys()):
        hasher.update(str(key).encode("utf-8"))
        hasher.update(str(inputs[key]).encode("utf-8"))
    return hasher.hexdigest()[:16]


def _serialize_frontend_values(values) -> list:
    return [_serialize_frontend_value(value) for value in values]


def _serialize_frontend_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _serialize_frontend_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_serialize_frontend_value(item) for item in value]
    return getattr(value, "__name__", str(value))


def _result(extension_id: str, status: str, status_label: str, message: str, *, details: dict | None = None) -> dict:
    return {
        "extension_id": extension_id,
        "status": status,
        "status_label": status_label,
        "message": message,
        "executed_at": timezone.now().isoformat(),
        "details": dict(details or {}),
    }
