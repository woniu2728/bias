from __future__ import annotations

from dataclasses import dataclass

from apps.core.extensions.platform import DomainEvent


@dataclass(frozen=True)
class PostFlagCreatedEvent(DomainEvent):
    flag_id: int
    post_id: int
    discussion_id: int
    actor_user_id: int


@dataclass(frozen=True)
class PostFlagsResolvedEvent(DomainEvent):
    flag_ids: tuple[int, ...]
    post_id: int
    discussion_id: int
    actor_user_id: int
    status: str


@dataclass(frozen=True)
class PostFlagsDeletedEvent(DomainEvent):
    flag_ids: tuple[int, ...]
    post_id: int
    discussion_id: int
    actor_user_id: int
