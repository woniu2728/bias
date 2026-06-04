from __future__ import annotations


def parse_following_search_filter(token: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "is":
        return None

    return True if value.strip().lower() == "following" else None


def apply_discussion_following_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)


def apply_following_discussion_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)
