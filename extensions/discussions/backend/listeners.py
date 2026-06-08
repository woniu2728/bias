from __future__ import annotations

from apps.core.forum_events import (
    DiscussionCreatedEvent,
    DiscussionHiddenEvent,
    DiscussionLockedEvent,
    DiscussionRenamedEvent,
    DiscussionStickyChangedEvent,
    PostCreatedEvent,
    PostHiddenEvent,
)
from extensions.discussions.backend.realtime import broadcast_discussion_event
from extensions.discussions.backend.timeline import (
    build_discussion_hidden_content,
    build_discussion_locked_content,
    build_discussion_renamed_content,
    build_discussion_sticky_content,
    build_post_hidden_content,
    create_timeline_from_builder,
    make_timeline_context,
)


def handle_discussion_created(event: DiscussionCreatedEvent) -> None:
    if event.is_approved:
        broadcast_discussion_event(
            event.discussion_id,
            "discussion.created",
            include_discussion=True,
            include_post=True,
            post_id_getter=lambda discussion: discussion.first_post_id,
        )


def handle_discussion_renamed(event: DiscussionRenamedEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "discussion.renamed", include_discussion=True)
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionRenamed"),
        build_discussion_renamed_content,
    )


def handle_discussion_locked(event: DiscussionLockedEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "discussion.locked", include_discussion=True)
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionLocked"),
        build_discussion_locked_content,
    )


def handle_discussion_sticky_changed(event: DiscussionStickyChangedEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "discussion.sticky_changed", include_discussion=True)
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionSticky"),
        build_discussion_sticky_content,
    )


def handle_discussion_hidden(event: DiscussionHiddenEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "discussion.hidden")
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionHidden"),
        build_discussion_hidden_content,
    )


def handle_post_created(event: PostCreatedEvent) -> None:
    if event.is_approved:
        broadcast_discussion_event(
            event.discussion_id,
            "post.created",
            include_discussion=True,
            include_post=True,
            post_id=event.post_id,
        )


def handle_post_hidden(event: PostHiddenEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "post.hidden")
    create_timeline_from_builder(
        make_timeline_context(
            event,
            post_type="postHidden",
        ),
        build_post_hidden_content,
    )
