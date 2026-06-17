from __future__ import annotations

from apps.core.extension_detail._shared import _serialize_callable_or_value
from apps.core.extensions.admin_manifest import (
    manifest_attr as _manifest_attr,
    manifest_nested_attr as _manifest_nested_attr,
)
from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest
from apps.core.forum_registry import get_forum_registry
from pathlib import Path

def _build_extension_discussion_list_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "requires_authenticated_user": item.requires_authenticated_user,
            "sidebar_visible": item.sidebar_visible,
            "route_path": item.route_path,
        }
        for item in get_forum_registry().get_discussion_list_filters()
        if item.module_id in module_ids
    ]

def _build_extension_discussion_sorts(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "toolbar_visible": item.toolbar_visible,
        }
        for item in get_forum_registry().get_discussion_sorts()
        if item.module_id in module_ids
    ]

def _build_extension_post_types(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "is_default": item.is_default,
            "is_stream_visible": item.is_stream_visible,
            "counts_toward_discussion": item.counts_toward_discussion,
            "counts_toward_user": item.counts_toward_user,
            "searchable": item.searchable,
        }
        for item in get_forum_registry().get_post_types()
        if item.module_id in module_ids
    ]

def _build_extension_post_lifecycle(extension, runtime_record=None):
    if runtime_record is None:
        return []

    handlers = []
    for item in getattr(runtime_record, "post_lifecycle", ()) or ():
        phases = [
            phase
            for phase in ("apply_created", "apply_updated", "apply_approved", "apply_hidden", "prepare_delete", "apply_deleted")
            if callable(getattr(item, phase, None))
        ]
        handlers.append({
            "key": getattr(item, "key", ""),
            "module_id": extension.id,
            "phases": phases,
            "description": getattr(item, "description", ""),
            "source": "runtime",
        })
    return handlers

def _build_extension_notification_types(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "icon": item.icon,
            "navigation_scope": item.navigation_scope,
            "preference_key": item.preference_key,
            "preference_label": item.preference_label,
        }
        for item in get_forum_registry().get_notification_types()
        if item.module_id in module_ids
    ]

def _build_extension_user_preferences(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "key": item.key,
            "label": item.label,
            "module_id": item.module_id,
            "description": item.description,
            "category": item.category,
            "default_value": item.default_value,
        }
        for item in get_forum_registry().get_user_preferences()
        if item.module_id in module_ids
    ]

def _build_extension_event_listeners(extension, runtime_record=None):
    module_ids = set(extension.module_ids or ())
    listeners = []
    seen = set()

    if runtime_record is not None:
        for item in getattr(runtime_record, "event_listeners", ()) or ():
            event_type = getattr(item, "event_type", None)
            handler = getattr(item, "handler", None)
            payload = {
                "event": getattr(event_type, "__name__", str(event_type or "")),
                "listener": getattr(handler, "__qualname__", getattr(handler, "__name__", str(handler or ""))),
                "module_id": extension.id,
                "description": getattr(item, "description", ""),
                "source": "runtime",
            }
            key = (payload["event"], payload["listener"], payload["module_id"])
            if key not in seen:
                seen.add(key)
                listeners.append(payload)

    if not module_ids:
        return listeners

    for item in get_forum_registry().get_event_listeners():
        if item.module_id not in module_ids:
            continue
        payload = {
            "event": item.event,
            "listener": item.listener,
            "module_id": item.module_id,
            "description": item.description,
            "source": "registry",
        }
        key = (payload["event"], payload["listener"], payload["module_id"])
        if key not in seen:
            seen.add(key)
            listeners.append(payload)
    return listeners

def _build_extension_realtime_broadcasts(runtime_record=None):
    if runtime_record is None:
        return []

    broadcasts = []
    for item in getattr(runtime_record, "realtime_discussion_broadcasts", ()) or ():
        event_type = getattr(item, "event_type", None)
        broadcasts.append({
            "event": getattr(event_type, "__name__", str(event_type or "")),
            "event_name": _serialize_callable_or_value(getattr(item, "event_name", "")),
            "channel": "discussion",
            "module_id": getattr(runtime_record, "extension_id", ""),
            "include_discussion": bool(getattr(item, "include_discussion", False)),
            "include_post": bool(getattr(item, "include_post", False)),
            "description": getattr(item, "description", ""),
            "source": "runtime",
        })
    return broadcasts

def _build_extension_language_packs(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "native_label": item.native_label,
            "module_id": item.module_id,
            "description": item.description,
            "is_default": item.is_default,
        }
        for item in get_forum_registry().get_language_packs()
        if item.module_id in module_ids
    ]

def _build_extension_delivery_assets(extension):
    from apps.core.extensions.assets import inspect_published_extension_assets

    if extension.source != "filesystem":
        return {
            "root_path": "",
            "root_exists": False,
            "asset_count": 0,
            "assets": [],
        }

    manifest_path = _manifest_attr(extension, "path")
    root_path = Path(manifest_path) if manifest_path else None
    asset_specs = [
        {
            "key": "backend_entry",
            "label": "后端入口",
            "path": root_path / "backend" / "ext.py" if root_path else None,
            "kind": "backend",
        },
        {
            "key": "migrations",
            "label": "迁移目录",
            "path": root_path / "backend" / "migrations" if root_path else None,
            "kind": "migration",
        },
        {
            "key": "frontend_admin_entry",
            "label": "后台入口",
            "path": root_path / "frontend" / "admin" / "index.js" if root_path else None,
            "kind": "frontend-admin",
        },
        {
            "key": "frontend_forum_entry",
            "label": "前台入口",
            "path": root_path / "frontend" / "forum" / "index.js" if root_path else None,
            "kind": "frontend-forum",
        },
        {
            "key": "locale",
            "label": "语言目录",
            "path": root_path / "locale" if root_path else None,
            "kind": "locale",
        },
        {
            "key": "docs",
            "label": "文档资源",
            "path": root_path / "docs" / "README.md" if root_path else None,
            "kind": "docs",
        },
    ]
    signature_url = _manifest_nested_attr(extension, "distribution", "signature_url")
    if signature_url:
        signature_path = signature_url
        if not signature_path.startswith(("http://", "https://")):
            root = root_path if root_path else None
            if signature_path.startswith("file://"):
                signature_path = signature_path[7:]
            candidate = Path(signature_path)
            if not candidate.is_absolute() and root is not None:
                candidate = root / candidate
            signature_path = candidate
        asset_specs.append({
            "key": "signature",
            "label": "签名文件",
            "path": signature_path,
            "kind": "signature",
        })

    assets = []
    for item in asset_specs:
        asset_path = item["path"]
        exists = False
        normalized_path = ""
        if isinstance(asset_path, Path):
            exists = asset_path.exists()
            normalized_path = str(asset_path)
        elif asset_path:
            normalized_path = str(asset_path)
            exists = True

        assets.append({
            "key": item["key"],
            "label": item["label"],
            "status": "ready" if exists else "pending",
            "status_label": "已就绪" if exists else "未提供",
            "path": normalized_path,
            "kind": item["kind"],
            "exists": exists,
        })

    published_assets = inspect_published_extension_assets(extension)
    assets.append({
        "key": "published_assets",
        "label": "已发布资产",
        "status": "ready" if published_assets["published"] and published_assets["target_exists"] else "pending",
        "status_label": "已发布" if published_assets["published"] and published_assets["target_exists"] else "未发布",
        "path": published_assets["target"],
        "kind": "published-assets",
        "exists": bool(published_assets["published"] and published_assets["target_exists"]),
        "files": published_assets["files"],
        "cache_key": published_assets.get("cache_key", ""),
        "frontend": published_assets.get("frontend", {}),
        "published_at": published_assets["published_at"],
    })

    return {
        "root_path": str(root_path or ""),
        "root_exists": bool(root_path and root_path.exists()),
        "asset_count": sum(1 for item in assets if item["exists"]),
        "assets": assets,
    }
