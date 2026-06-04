from apps.core.forum_runtime import broadcast_discussion_event
from apps.core.forum_events import PostFlagCreatedEvent, PostFlagsDeletedEvent, PostFlagsResolvedEvent


def handle_post_flag_created(event: PostFlagCreatedEvent) -> None:
    broadcast_discussion_event(
        event.discussion_id,
        "post.flagged",
        include_discussion=True,
        include_post=True,
        post_id=event.post_id,
    )


def handle_post_flags_resolved(event: PostFlagsResolvedEvent) -> None:
    broadcast_discussion_event(
        event.discussion_id,
        "post.flags_resolved",
        include_discussion=True,
        include_post=True,
        post_id=event.post_id,
    )


def handle_post_flags_deleted(event: PostFlagsDeletedEvent) -> None:
    broadcast_discussion_event(
        event.discussion_id,
        "post.flags_deleted",
        include_discussion=True,
        include_post=True,
        post_id=event.post_id,
    )
