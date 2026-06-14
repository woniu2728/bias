from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable

from django.utils import timezone

from apps.core.extensions.runtime import create_runtime_post_event
from apps.core.extensions.runtime import get_runtime_user_by_id
from extensions.discussions.backend.models import Discussion


TimelineContentBuilder = Callable[[object], tuple[str, str] | None]


@dataclass(frozen=True)
class TimelineEventDefinition:
    event_type: type
    post_type: str
    build_content: TimelineContentBuilder


def make_timeline_context(event, **extra):
    payload = dict(getattr(event, "__dict__", {}))
    payload.update(extra)
    return SimpleNamespace(**payload)


def create_timeline_from_builder(event, builder, *, update_discussion_last_post: bool = True) -> None:
    built = builder(event)
    if not built:
        return

    post_type, content = built
    create_timeline_event_post(
        discussion_id=event.discussion_id,
        actor_user_id=event.actor_user_id,
        post_type=post_type,
        content=content,
        update_discussion_last_post=update_discussion_last_post,
    )


def create_timeline_event_post(
    *,
    discussion_id: int,
    actor_user_id: int,
    post_type: str,
    content: str,
    update_discussion_last_post: bool = True,
) -> object | None:
    try:
        actor = get_runtime_user_by_id(actor_user_id)
        discussion = Discussion.objects.get(id=discussion_id)
    except Discussion.DoesNotExist:
        return None
    except Exception:
        return None

    event_post = create_runtime_post_event(
        discussion=discussion,
        actor=actor,
        post_type=post_type,
        content=content,
        content_html="",
        approved_at=timezone.now(),
    )

    if update_discussion_last_post:
        locked_discussion = event_post.discussion
        locked_discussion.last_post_id = event_post.id
        locked_discussion.last_post_number = event_post.number
        locked_discussion.last_posted_at = event_post.created_at
        locked_discussion.last_posted_user = actor
        locked_discussion.save(update_fields=[
            "last_post_id",
            "last_post_number",
            "last_posted_at",
            "last_posted_user",
        ])
    return event_post


def build_discussion_renamed_content(event) -> tuple[str, str] | None:
    return event.post_type, f"from: {event.old_title}\nto: {event.new_title}"


def build_discussion_tagged_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"added:{'|'.join(event.added_tags)}\n"
        f"removed:{'|'.join(event.removed_tags)}"
    )


def build_discussion_locked_content(event) -> tuple[str, str] | None:
    return event.post_type, ("locked" if event.is_locked else "unlocked")


def build_discussion_sticky_content(event) -> tuple[str, str] | None:
    return event.post_type, ("sticky" if event.is_sticky else "unsticky")


def build_discussion_hidden_content(event) -> tuple[str, str] | None:
    return event.post_type, ("hidden" if event.is_hidden else "restored")


def build_discussion_review_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"previous_status: {event.previous_status}\n"
        f"note: {event.note}"
    )


def build_discussion_resubmitted_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"previous_status: {event.previous_status}\n"
        "note:"
    )


def build_post_review_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"target_post_id: {event.post_id}\n"
        f"target_post_number: {event.post_number}\n"
        f"previous_status: {event.previous_status}\n"
        f"note: {event.note}"
    )


def build_post_resubmitted_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"target_post_id: {event.post_id}\n"
        f"target_post_number: {event.post_number}\n"
        f"previous_status: {event.previous_status}\n"
        "note:"
    )


def build_post_hidden_content(event) -> tuple[str, str] | None:
    return event.post_type, (
        f"state: {'hidden' if event.is_hidden else 'restored'}\n"
        f"target_post_id: {event.post_id}\n"
        f"target_post_number: {event.post_number}"
    )


