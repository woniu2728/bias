from __future__ import annotations

from apps.core.domain_events import dispatch_forum_event_after_commit
from extensions.tags.backend.events import (
    DiscussionTagStatsRefreshEvent,
    TagStatsRefreshRequestedEvent,
)
from extensions.tags.backend.tag_relationships import get_discussion_tag_ids


def prepare_discussion_delete(*, discussion, user, context: dict | None = None, **kwargs) -> dict:
    return {
        "tag_ids": get_discussion_tag_ids(discussion),
    }


def apply_discussion_delete(*, state: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    tag_ids = tuple((state or {}).get("tag_ids") or ())
    if tag_ids:
        dispatch_forum_event_after_commit(
            TagStatsRefreshRequestedEvent(tag_ids=tag_ids)
        )
    return {
        "affected_tag_ids": tag_ids,
    }


def apply_discussion_hidden(*, discussion, state: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    dispatch_forum_event_after_commit(
        DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
    )
    return {"discussion_id": discussion.id}


def apply_discussion_approved(*, discussion, state: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    if not (context or {}).get("was_counted"):
        return {}
    dispatch_forum_event_after_commit(
        DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
    )
    return {"discussion_id": discussion.id}


def apply_discussion_rejected(*, discussion, state: dict | None = None, context: dict | None = None, **kwargs) -> dict:
    dispatch_forum_event_after_commit(
        DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
    )
    return {"discussion_id": discussion.id}
