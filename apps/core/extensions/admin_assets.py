from __future__ import annotations

from typing import Callable

from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest


def serialize_extension_frontend_asset_state() -> dict:
    return inspect_extension_frontend_output_manifest()


def serialize_extension_frontend_asset_state_for_extension(
    extension,
    *,
    runtime_rebuild_state: dict,
    resolve_admin_entry: Callable[[object], str],
    resolve_forum_entry: Callable[[object], str],
) -> dict:
    state = serialize_extension_frontend_asset_state()
    extensions = dict(state.get("extensions") or {})
    entry = dict(extensions.get(extension.id) or {})
    has_frontend = bool(resolve_admin_entry(extension) or resolve_forum_entry(extension))
    return {
        "manifest_exists": bool(state.get("exists")),
        "has_frontend": has_frontend,
        "compiled": bool(entry.get("outputs")) if has_frontend else True,
        "requires_rebuild": bool(runtime_rebuild_state.get("required")),
        "outputs": dict(entry.get("outputs") or {}),
        "generated_at": str(state.get("generated_at") or ""),
    }
