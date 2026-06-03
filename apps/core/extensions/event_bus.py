from __future__ import annotations

from apps.core.domain_events import DomainEventBus, get_forum_event_bus


_extension_event_bus: DomainEventBus | None = None


def get_extension_event_bus() -> DomainEventBus:
    global _extension_event_bus
    if _extension_event_bus is None:
        _extension_event_bus = get_forum_event_bus()
    return _extension_event_bus
