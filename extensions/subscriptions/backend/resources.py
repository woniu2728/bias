from __future__ import annotations

from apps.discussions import discussion_tracking


def resolve_discussion_subscription_state(discussion, context: dict) -> bool:
    user = context.get("user")
    return discussion_tracking.get_subscription_state(discussion, user)
