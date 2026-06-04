from __future__ import annotations


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
    return [
        {
            "id": dt.tag.id,
            "name": dt.tag.name,
            "slug": dt.tag.slug,
            "color": dt.tag.color,
            "icon": dt.tag.icon,
        }
        for dt in discussion.discussion_tags.all()
    ]


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


def resolve_tag_can_start_discussion(tag, context: dict) -> bool:
    from extensions.tags.backend.services import TagService

    user = context.get("user")
    return TagService.can_start_discussion_in_tag(tag, user)


def resolve_tag_can_reply(tag, context: dict) -> bool:
    from extensions.tags.backend.services import TagService

    user = context.get("user")
    return TagService.can_reply_in_tag(tag, user)


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
