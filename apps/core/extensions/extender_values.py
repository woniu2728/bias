from __future__ import annotations

from typing import Any


def flatten_extenders(values: Any) -> tuple[Any, ...]:
    flattened: list[Any] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
            return
        flattened.append(value)

    visit(values)
    return tuple(flattened)
