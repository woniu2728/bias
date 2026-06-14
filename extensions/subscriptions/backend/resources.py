from __future__ import annotations

from apps.core.extensions.runtime import get_runtime_discussion_subscription_state


def resolve_discussion_subscription_state(discussion, context: dict) -> bool:
    user = context.get("user")
    return get_runtime_discussion_subscription_state(discussion, user)

