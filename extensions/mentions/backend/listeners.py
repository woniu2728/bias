from extensions.mentions.backend.events import UserMentionedEvent
from apps.core.extensions import runtime_access
from apps.core.extensions.runtime_access import get_runtime_user_by_id


def handle_user_mentioned_notification(event: UserMentionedEvent) -> None:
    mentioned_user = _resolve_user_or_none(event.mentioned_user_id)
    if mentioned_user is None:
        return

    from_user = _resolve_user_or_none(event.actor_user_id)
    if from_user is None:
        return

    runtime_access.notify_runtime_notification(
        "notify_user_mentioned",
        post_id=event.post_id,
        mentioned_user=mentioned_user,
        from_user=from_user,
    )


def _resolve_user_or_none(user_id: int):
    if not user_id:
        return None
    try:
        return get_runtime_user_by_id(user_id)
    except Exception:
        return None
