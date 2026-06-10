from __future__ import annotations

from dataclasses import dataclass

from apps.core.domain_events import DomainEvent


@dataclass(frozen=True)
class UserSuspendedEvent(DomainEvent):
    user_id: int
    actor_user_id: int | None


@dataclass(frozen=True)
class UserUnsuspendedEvent(DomainEvent):
    user_id: int
    actor_user_id: int | None
