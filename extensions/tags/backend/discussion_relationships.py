from __future__ import annotations

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.runtime_access import ensure_can_start_discussion_in_runtime_tags
from extensions.tags.backend.events import DiscussionTaggedEvent, TagStatsRefreshRequestedEvent
from extensions.tags.backend.tag_relationships import replace_discussion_tags


def set_discussion_tags_relationship(discussion, value, context: dict | None = None) -> None:
    context = context or {}
    user = context.get("user")
    tag_ids = _relationship_tag_ids(value)
    tags = tuple(ensure_can_start_discussion_in_runtime_tags(user, tag_ids))

    result = replace_discussion_tags(discussion, tags)
    affected_tag_ids = tuple(result["affected_tag_ids"])

    if not context.get("creating"):
        added_tags = tuple(result["added_tags"])
        removed_tags = tuple(result["removed_tags"])
        if added_tags or removed_tags:
            dispatch_forum_event_after_commit(
                DiscussionTaggedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=context.get("actor_user_id"),
                    added_tags=added_tags,
                    removed_tags=removed_tags,
                    tag_ids=affected_tag_ids,
                )
            )

    if affected_tag_ids:
        dispatch_forum_event_after_commit(
            TagStatsRefreshRequestedEvent(tag_ids=affected_tag_ids)
        )


def _relationship_tag_ids(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, dict) and "data" in value:
        value = value["data"]
    if not isinstance(value, (list, tuple)):
        value = [value]

    tag_ids: list[int] = []
    for item in value:
        raw_id = item.get("id") if isinstance(item, dict) else item
        try:
            tag_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        tag_ids.append(tag_id)
    return tag_ids
