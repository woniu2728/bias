from __future__ import annotations


def parse_tag_search_filter(token: str) -> str | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "tag":
        return None

    normalized = value.strip().lower()
    return normalized or None


def apply_discussion_tag_search_filter(queryset, tag_slug: str, context: dict):
    return queryset.filter(discussion_tags__tag__slug=tag_slug)
