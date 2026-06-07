from __future__ import annotations

from apps.core.domain_events import dispatch_forum_event_after_commit
from extensions.tags.backend.models import DiscussionTag
from extensions.tags.backend.events import DiscussionTaggedEvent, TagStatsRefreshRequestedEvent
from extensions.tags.backend.services import TagService


def set_discussion_tags_relationship(discussion, value, context: dict | None = None) -> None:
    context = context or {}
    user = context.get("user")
    tag_ids = _relationship_tag_ids(value)
    tags = tuple(TagService.ensure_can_start_discussion(user, tag_ids))

    previous_tag_ids = list(discussion.discussion_tags.values_list("tag_id", flat=True))
    previous_tag_names = list(
        discussion.discussion_tags.select_related("tag")
        .order_by("tag__name")
        .values_list("tag__name", flat=True)
    )

    DiscussionTag.objects.filter(discussion=discussion).delete()
    DiscussionTag.objects.bulk_create([
        DiscussionTag(discussion=discussion, tag=tag)
        for tag in tags
    ])

    current_tag_ids = [tag.id for tag in tags]
    current_tag_names = [tag.name for tag in sorted(tags, key=lambda item: item.name)]
    affected_tag_ids = tuple(sorted(set(previous_tag_ids) | set(current_tag_ids)))

    if not context.get("creating"):
        added_tags = [name for name in current_tag_names if name not in previous_tag_names]
        removed_tags = [name for name in previous_tag_names if name not in current_tag_names]
        if added_tags or removed_tags:
            dispatch_forum_event_after_commit(
                DiscussionTaggedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=context.get("actor_user_id"),
                    added_tags=tuple(added_tags),
                    removed_tags=tuple(removed_tags),
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
