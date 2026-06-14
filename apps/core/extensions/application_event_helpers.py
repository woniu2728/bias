from __future__ import annotations

from typing import Any

from apps.core.extensions.container import import_string
from apps.core.forum_registry_types import EventListenerDefinition


def resolve_event_type(event_type: Any):
    if isinstance(event_type, str):
        try:
            resolved = import_string(event_type)
        except Exception:
            return None
        return resolved if isinstance(resolved, type) else None
    return event_type if isinstance(event_type, type) else None


def build_forum_event_listener_definition(extension_id: str, definition) -> EventListenerDefinition:
    event_type = getattr(definition, "event_type", None)
    handler = getattr(definition, "handler", None)
    event_name = str(getattr(event_type, "__name__", "") or event_type or "").strip()
    handler_name = str(getattr(handler, "__name__", "") or handler or "").strip()
    return EventListenerDefinition(
        event=event_name,
        listener=handler_name,
        module_id=extension_id,
        description=str(getattr(definition, "description", "") or "").strip(),
    )


def build_event_bus_listener_key(extension_id: str, definition) -> tuple[str, str, str]:
    event_type = getattr(definition, "event_type", None)
    handler = getattr(definition, "handler", None)
    event_key = ":".join(
        item
        for item in (
            str(getattr(event_type, "__module__", "") or "").strip(),
            str(getattr(event_type, "__qualname__", "") or "").strip(),
        )
        if item
    ) or str(event_type)
    handler_key = ":".join(
        item
        for item in (
            str(getattr(handler, "__module__", "") or "").strip(),
            str(getattr(handler, "__qualname__", "") or "").strip(),
        )
        if item
    ) or str(handler)
    return extension_id, event_key, handler_key


def event_type_key(event_type: Any) -> str:
    return ":".join(
        item
        for item in (
            str(getattr(event_type, "__module__", "") or "").strip(),
            str(getattr(event_type, "__qualname__", "") or "").strip(),
        )
        if item
    ) or str(event_type)


def event_value_key(value: Any) -> str:
    if callable(value):
        return ":".join(
            item
            for item in (
                str(getattr(value, "__module__", "") or "").strip(),
                str(getattr(value, "__qualname__", "") or "").strip(),
            )
            if item
        ) or str(value)
    return str(value or "").strip()


def resolve_event_value(source: Any, event: Any, *, default: Any = None) -> Any:
    if source is None:
        return default
    if callable(source):
        try:
            return source(event)
        except TypeError:
            return source()
    if isinstance(source, str):
        return getattr(event, source, default)
    return source


def resolve_event_name(source: Any, event: Any) -> Any:
    if callable(source):
        try:
            return source(event)
        except TypeError:
            return source()
    return source
