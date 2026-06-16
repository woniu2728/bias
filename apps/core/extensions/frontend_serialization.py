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
