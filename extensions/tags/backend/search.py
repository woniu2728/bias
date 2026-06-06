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


def apply_discussion_tag_list_query(queryset, context: dict):
    tag_slug = _query_param_value((context or {}).get("params"), "tag")
    if not tag_slug:
        return queryset
    return apply_discussion_tag_search_filter(queryset, tag_slug, context)


def _query_param_value(params, key: str) -> str:
    if not isinstance(params, dict):
        return ""
    value = params.get(key)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip().lower()
