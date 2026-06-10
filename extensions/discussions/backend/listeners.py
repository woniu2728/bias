from __future__ import annotations

from extensions.discussions.backend.events import (
    DiscussionHiddenEvent,
    DiscussionLockedEvent,
    DiscussionRenamedEvent,
    DiscussionStickyChangedEvent,
)
from extensions.discussions.backend.timeline import (
    build_discussion_hidden_content,
    build_discussion_locked_content,
    build_discussion_renamed_content,
    build_discussion_sticky_content,
    build_post_hidden_content,
    create_timeline_from_builder,
    make_timeline_context,
)


def handle_discussion_renamed(event: DiscussionRenamedEvent) -> None:
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionRenamed"),
        build_discussion_renamed_content,
    )


def handle_discussion_locked(event: DiscussionLockedEvent) -> None:
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionLocked"),
        build_discussion_locked_content,
    )


def handle_discussion_sticky_changed(event: DiscussionStickyChangedEvent) -> None:
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionSticky"),
        build_discussion_sticky_content,
    )


def handle_discussion_hidden(event: DiscussionHiddenEvent) -> None:
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionHidden"),
        build_discussion_hidden_content,
    )


def handle_post_hidden(event) -> None:
    create_timeline_from_builder(
        make_timeline_context(
            event,
            post_type="postHidden",
        ),
        build_post_hidden_content,
    )
