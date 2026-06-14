from __future__ import annotations

from extensions.tags.backend.models import Tag
from apps.core.extensions.runtime import (
    can_runtime_reply_in_tag,
    can_runtime_start_discussion_in_tag,
    filter_runtime_tags_for_user,
)


def serialize_tag_base(tag, context: dict) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "description": tag.description,
        "color": tag.color,
        "icon": tag.icon,
        "background_url": tag.background_url,
        "position": tag.position,
        "parent_id": tag.parent_id,
        "is_hidden": tag.is_hidden,
        "is_restricted": tag.is_restricted,
        "view_scope": tag.view_scope,
        "start_discussion_scope": tag.start_discussion_scope,
        "reply_scope": tag.reply_scope,
        "discussion_count": tag.discussion_count,
        "last_posted_at": tag.last_posted_at,
        "created_at": tag.created_at,
        "updated_at": tag.updated_at,
    }


def resolve_discussion_tags(discussion, context: dict) -> list[dict]:
    from extensions.tags.backend.tag_relationships import serialize_discussion_tag_summaries

    return serialize_discussion_tag_summaries(discussion)


def resolve_forum_tags(forum, context: dict) -> list[dict]:
    from django.db.models import Prefetch

    user = context.get("user")
    child_queryset = filter_runtime_tags_for_user(
        Tag.objects.filter(is_hidden=False).order_by("position", "name"),
        user,
        action="view",
    )
    queryset = filter_runtime_tags_for_user(
        Tag.objects.filter(parent__isnull=True, is_hidden=False)
        .select_related("last_posted_discussion")
        .prefetch_related(Prefetch("children", queryset=child_queryset, to_attr="visible_children"))
        .order_by("position", "name"),
        user,
        action="view",
    )
    return [_serialize_forum_tag(tag, context) for tag in queryset]


def resolve_forum_can_bypass_tag_counts(forum, context: dict) -> bool:
    user = context.get("user")
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def resolve_discussion_tagged_event_data(post, context: dict) -> dict | None:
    added = []
    removed = []
    for line in _normalized_lines(getattr(post, "content", "")):
        if line.startswith("added:"):
            added = [item for item in line.removeprefix("added:").split("|") if item]
        elif line.startswith("removed:"):
            removed = [item for item in line.removeprefix("removed:").split("|") if item]

    return {
        "kind": "discussionTagged",
        "added_tags": added,
        "removed_tags": removed,
    }


def resolve_post_event_mentions_tags(post, context: dict | None = None) -> list[Tag]:
    if getattr(post, "type", "") != "discussionTagged":
        return []
    event_data = resolve_discussion_tagged_event_data(post, context or {}) or {}
    slugs = []
    for slug in [*event_data.get("added_tags", []), *event_data.get("removed_tags", [])]:
        if slug and slug not in slugs:
            slugs.append(slug)
    if not slugs:
        return []

    tags_by_slug = {
        tag.slug: tag
        for tag in Tag.objects.filter(slug__in=slugs).select_related("last_posted_discussion")
    }
    return [tags_by_slug[slug] for slug in slugs if slug in tags_by_slug]


def resolve_tag_can_start_discussion(tag, context: dict) -> bool:
    user = context.get("user")
    return can_runtime_start_discussion_in_tag(tag, user)


def resolve_tag_can_reply(tag, context: dict) -> bool:
    user = context.get("user")
    return can_runtime_reply_in_tag(tag, user)


def resolve_tag_last_posted_discussion(tag, context: dict) -> dict | None:
    discussion = getattr(tag, "last_posted_discussion", None)
    if not discussion:
        return None

    return {
        "id": discussion.id,
        "title": discussion.title,
        "slug": discussion.slug,
        "last_post_number": discussion.last_post_number,
        "last_posted_at": discussion.last_posted_at,
    }


def _normalized_lines(content: str | None) -> list[str]:
    return [
        line.strip()
        for line in (content or "").splitlines()
        if line.strip()
    ]


def _serialize_forum_tag(tag, context: dict) -> dict:
    payload = serialize_tag_base(tag, context)
    payload["can_start_discussion"] = resolve_tag_can_start_discussion(tag, context)
    payload["can_reply"] = resolve_tag_can_reply(tag, context)
    payload["last_posted_discussion"] = resolve_tag_last_posted_discussion(tag, context)
    payload["children"] = [
        _serialize_forum_tag(child, context)
        for child in getattr(tag, "visible_children", [])
    ]
    return payload
