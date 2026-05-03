from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, Generic, List, TypeVar


class DomainEvent:
    """Base type for in-process domain events."""


EventT = TypeVar("EventT", bound=DomainEvent)
DomainEventHandler = Callable[[EventT], None]


class DomainEventBus:
    def __init__(self):
        self._listeners: DefaultDict[type[DomainEvent], List[DomainEventHandler]] = defaultdict(list)

    def register(self, event_type: type[EventT], handler: DomainEventHandler[EventT]) -> None:
        listeners = self._listeners[event_type]
        if handler not in listeners:
            listeners.append(handler)

    def dispatch(self, event: DomainEvent) -> None:
        for event_type, handlers in self._listeners.items():
            if isinstance(event, event_type):
                for handler in list(handlers):
                    handler(event)


_forum_event_bus: DomainEventBus | None = None


def get_forum_event_bus() -> DomainEventBus:
    global _forum_event_bus
    if _forum_event_bus is None:
        _forum_event_bus = DomainEventBus()
    return _forum_event_bus
