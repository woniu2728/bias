from __future__ import annotations

from typing import Iterable

from extensions.tags.backend.models import DiscussionTag


def get_discussion_tag_links(discussion):
    links = getattr(discussion, "discussion_tags", None)
    if links is None:
        return []
    queryset = links.select_related("tag") if hasattr(links, "select_related") else links
    return list(queryset.all() if hasattr(queryset, "all") else queryset)


def get_discussion_tags(discussion) -> list:
    return [
        link.tag
        for link in get_discussion_tag_links(discussion)
        if getattr(link, "tag", None) is not None
    ]


def get_discussion_tag_ids(discussion) -> tuple[int, ...]:
    links = getattr(discussion, "discussion_tags", None)
    if links is not None and hasattr(links, "order_by"):
        return tuple(links.order_by("tag_id").values_list("tag_id", flat=True))

    discussion_id = getattr(discussion, "id", discussion)
    if not discussion_id:
        return ()
    return tuple(
        DiscussionTag.objects.filter(discussion_id=discussion_id)
        .order_by("tag_id")
        .values_list("tag_id", flat=True)
    )


def get_discussion_tag_names(discussion) -> tuple[str, ...]:
    return tuple(
        link.tag.name
        for link in sorted(
            get_discussion_tag_links(discussion),
            key=lambda item: getattr(getattr(item, "tag", None), "name", ""),
        )
        if getattr(link, "tag", None) is not None
    )


def serialize_discussion_tag_summaries(discussion) -> list[dict]:
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "color": tag.color,
            "icon": tag.icon,
        }
        for tag in get_discussion_tags(discussion)
    ]


def replace_discussion_tags(discussion, tags: Iterable) -> dict:
    previous_tag_ids = get_discussion_tag_ids(discussion)
    previous_tag_names = get_discussion_tag_names(discussion)
    normalized_tags = tuple(tags or ())

    DiscussionTag.objects.filter(discussion=discussion).delete()
    DiscussionTag.objects.bulk_create([
        DiscussionTag(discussion=discussion, tag=tag)
        for tag in normalized_tags
    ])

    current_tag_ids = tuple(tag.id for tag in normalized_tags)
    current_tag_names = tuple(tag.name for tag in sorted(normalized_tags, key=lambda item: item.name))
    return {
        "previous_tag_ids": previous_tag_ids,
        "previous_tag_names": previous_tag_names,
        "current_tag_ids": current_tag_ids,
        "current_tag_names": current_tag_names,
        "affected_tag_ids": tuple(sorted(set(previous_tag_ids) | set(current_tag_ids))),
        "added_tags": tuple(name for name in current_tag_names if name not in previous_tag_names),
        "removed_tags": tuple(name for name in previous_tag_names if name not in current_tag_names),
    }


def tag_has_discussions(tag) -> bool:
    return DiscussionTag.objects.filter(tag=tag).exists()


def get_discussion_tag_ids_for_stats(discussion) -> list[int]:
    discussion_id = getattr(discussion, "id", discussion)
    if not discussion_id:
        return []
    return list(
        DiscussionTag.objects.filter(discussion_id=discussion_id)
        .values_list("tag_id", flat=True)
    )
