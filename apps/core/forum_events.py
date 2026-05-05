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
class DiscussionRenamedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    old_title: str
    new_title: str


@dataclass(frozen=True)
class DiscussionTaggedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    added_tags: tuple[str, ...] = ()
    removed_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscussionLockedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    is_locked: bool


@dataclass(frozen=True)
class DiscussionStickyChangedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    is_sticky: bool


@dataclass(frozen=True)
class DiscussionHiddenEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    is_hidden: bool


@dataclass(frozen=True)
class DiscussionRejectedEvent(DomainEvent):
    discussion_id: int
    admin_user_id: int
    note: str = ""
    previous_status: str = ""


@dataclass(frozen=True)
class DiscussionResubmittedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    previous_status: str = ""


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
