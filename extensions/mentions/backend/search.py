def parse_mentioned_me_search_filter(token: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "mentioned":
        return None

    return True if value.strip().lower() == "me" else None


def apply_post_mentioned_me_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(mentions__mentions_user=user)
