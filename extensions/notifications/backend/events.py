from __future__ import annotations

from dataclasses import dataclass

from apps.core.extensions.platform import DomainEvent


@dataclass(frozen=True)
class NotificationCreatedEvent(DomainEvent):
    notification_ids: tuple[int, ...]
