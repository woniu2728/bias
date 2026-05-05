from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.utils import timezone

from apps.discussions.models import Discussion
from apps.posts.models import Post
from apps.users.models import User


TimelineContentBuilder = Callable[[object], tuple[str, str] | None]


@dataclass(frozen=True)
class TimelineEventDefinition:
    event_type: type
    post_type: str
    build_content: TimelineContentBuilder


def create_timeline_event_post(
    *,
    discussion_id: int,
    actor_user_id: int,
    post_type: str,
    content: str,
) -> Post | None:
    from apps.posts.services import PostService

    try:
        actor = User.objects.get(id=actor_user_id)
        discussion = Discussion.objects.get(id=discussion_id)
    except (User.DoesNotExist, Discussion.DoesNotExist):
        return None

    locked_discussion = PostService._lock_discussion_for_post_number(discussion.id)
    event_post = PostService._create_post_with_sequential_number(
        discussion=locked_discussion,
        user=actor,
        type=post_type,
        content=content,
        content_html="",
        approval_status=Post.APPROVAL_APPROVED,
        approved_at=timezone.now(),
        approved_by=actor,
    )

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
