from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def serialize_frontend_values(values: Iterable[Any]) -> list[Any]:
    return [serialize_frontend_value(value) for value in values]


def serialize_frontend_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): serialize_frontend_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [serialize_frontend_value(item) for item in value]
    return getattr(value, "__name__", str(value))


def serialize_frontend_routes(
    routes: Iterable[Any],
    *,
    require_path: bool = True,
    include_document_payload: bool = True,
) -> list[dict[str, Any]]:
    output = []
    for route in routes or ():
        frontend = str(getattr(route, "frontend", "") or "forum").strip() or "forum"
        removed = bool(getattr(route, "removed", False))
        order = getattr(route, "order", 100)
        item = {
            "path": str(getattr(route, "path", "") or "").strip(),
            "name": str(getattr(route, "name", "") or "").strip(),
            "component": str(getattr(route, "component", "") or "").strip(),
            "frontend": frontend,
            "module_id": str(getattr(route, "module_id", "") or "").strip(),
            "title": str(getattr(route, "title", "") or "").strip(),
            "description": str(getattr(route, "description", "") or "").strip(),
            "requires_auth": bool(getattr(route, "requires_auth", False)),
            "order": int(order if order is not None and order != "" else 100),
            "removed": removed,
        }
        if include_document_payload:
            item.update({
                "preloads": serialize_frontend_values(getattr(route, "preloads", ()) or ()),
                "document_attributes": serialize_frontend_values(getattr(route, "document_attributes", ()) or ()),
                "head_tags": serialize_frontend_values(getattr(route, "head_tags", ()) or ()),
            })
        output.append(item)

    return [
        item
        for item in output
        if item["name"]
        and (
            item["removed"]
            or (
                item["component"]
                and (item["path"] or not require_path)
            )
        )
    ]
