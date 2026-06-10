from __future__ import annotations

from dataclasses import dataclass

from apps.core.domain_events import DomainEvent


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
    previous_status: str = ""


@dataclass(frozen=True)
class PostRejectedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int | None
    admin_user_id: int
    note: str = ""
    previous_status: str = ""


@dataclass(frozen=True)
class PostResubmittedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int
    previous_status: str = ""


@dataclass(frozen=True)
class PostHiddenEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int
    post_number: int | None
    is_hidden: bool


@dataclass(frozen=True)
class PostDeletedEvent(DomainEvent):
    post_id: int
    discussion_id: int
    actor_user_id: int
    post_number: int | None
