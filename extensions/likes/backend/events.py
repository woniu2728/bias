from __future__ import annotations

from dataclasses import dataclass

from apps.core.domain_events import DomainEvent


@dataclass(frozen=True)
class PostLikedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int
    post_number: int | None = None
