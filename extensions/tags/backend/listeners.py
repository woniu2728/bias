from apps.core.forum_runtime import (
    broadcast_discussion_event,
    create_timeline_from_builder,
    make_timeline_context,
)
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    PostApprovedEvent,
    PostCreatedEvent,
    PostDeletedEvent,
    PostHiddenEvent,
    PostRejectedEvent,
)
from apps.core.forum_timeline import build_discussion_tagged_content
from extensions.tags.backend.events import (
    DiscussionTaggedEvent,
    DiscussionTagStatsRefreshEvent,
    TagStatsRefreshRequestedEvent,
)


def enrich_realtime_tags_included_payload(*, discussion=None, post_payload=None, extension_context=None, payload=None):
    tags = {}
    if discussion is not None:
        for tag in _iter_discussion_tags(discussion):
            _merge_tag_payload(tags, tag, fallback_discussion=discussion)
    else:
        tags_context = dict((extension_context or {}).get("tags") or {})
        tag_ids = tags_context.get("tag_ids") or []
        if not tag_ids:
            return {}
        from apps.tags.models import Tag

        for tag in Tag.objects.select_related("last_posted_discussion").filter(id__in=tag_ids):
            _merge_tag_payload(tags, tag)
    if not tags:
        return {}
    return {"tags": list(tags.values())}


def _iter_discussion_tags(discussion):
    links = getattr(discussion, "discussion_tags", None)
    if links is None:
        return []
    resolved = []
    for link in links.all() if hasattr(links, "all") else links:
        tag = getattr(link, "tag", None)
        if tag is not None:
            resolved.append(tag)
    return resolved


def _merge_tag_payload(target: dict, tag, *, fallback_discussion=None) -> None:
    from extensions.tags.backend.handlers import _serialize_tag

    payload = _serialize_tag(tag, user=None, include_children=False)
    if not payload or payload.get("id") is None:
        return
    if fallback_discussion is not None:
        payload["last_posted_discussion"] = {
            "id": fallback_discussion.id,
            "title": fallback_discussion.title,
            "slug": fallback_discussion.slug,
            "last_post_number": fallback_discussion.last_post_number,
            "last_posted_at": fallback_discussion.last_posted_at,
        }
    target[int(payload["id"])] = payload


def handle_discussion_approved_tag_stats(event: DiscussionApprovedEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_discussion_tagged(event: DiscussionTaggedEvent) -> None:
    from extensions.tags.backend.services import TagService

    if event.tag_ids:
        TagService.refresh_tag_stats(list(event.tag_ids))
    else:
        TagService.refresh_discussion_tag_stats(event.discussion_id)
    broadcast_discussion_event(
        event.discussion_id,
        "discussion.tagged",
        include_discussion=True,
        extension_context={"tags": {"tag_ids": list(event.tag_ids)}} if event.tag_ids else None,
    )
    create_timeline_from_builder(
        make_timeline_context(event, post_type="discussionTagged"),
        build_discussion_tagged_content,
    )


def handle_post_created_tag_stats(event: PostCreatedEvent) -> None:
    if not event.is_approved:
        return

    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_post_approved_tag_stats(event: PostApprovedEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_post_deleted_tag_stats(event: PostDeletedEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_post_hidden_tag_stats(event: PostHiddenEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_post_rejected_tag_stats(event: PostRejectedEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_discussion_tag_stats_refresh(event: DiscussionTagStatsRefreshEvent) -> None:
    from extensions.tags.backend.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_tag_stats_refresh_requested(event: TagStatsRefreshRequestedEvent) -> None:
    if not event.tag_ids:
        return

    from extensions.tags.backend.services import TagService

    TagService.dispatch_refresh_tag_stats(list(event.tag_ids))
