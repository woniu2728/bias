from __future__ import annotations

from extensions.subscriptions.backend.services import get_subscription_state


def resolve_discussion_subscription_state(discussion, context: dict) -> bool:
    user = context.get("user")
    return get_subscription_state(discussion, user)
