from __future__ import annotations


def _serialize_callable_or_value(value):
    if callable(value):
        return getattr(value, "__qualname__", getattr(value, "__name__", str(value or "")))
    return str(value or "")
