from __future__ import annotations

from dataclasses import dataclass

from apps.core.domain_events import DomainEvent


@dataclass(frozen=True)
class DiscussionCreatedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    tag_ids: tuple[int, ...] = ()
    is_approved: bool = True


@dataclass(frozen=True)
class DiscussionApprovedEvent(DomainEvent):
    discussion_id: int
    admin_user_id: int
    note: str = ""


@dataclass(frozen=True)
class PostCreatedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int
    reply_to_post_id: int | None = None
    is_approved: bool = True


@dataclass(frozen=True)
class PostApprovedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int | None
    admin_user_id: int
    note: str = ""
