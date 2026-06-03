from __future__ import annotations

from apps.core.extensions.runtime_event_listeners import (
    bootstrap_extension_runtime_event_listeners,
    handle_extension_runtime_invalidation,
)


def bootstrap_extension_frontend_event_listeners() -> None:
    bootstrap_extension_runtime_event_listeners()


def handle_extension_frontend_asset_invalidation(event) -> None:
    handle_extension_runtime_invalidation(event)
