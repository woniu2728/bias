from apps.core.extensions import runtime_access
from apps.core.extensions.runtime_access import get_runtime_user_by_id
from extensions.likes.backend.events import PostLikedEvent


def handle_post_liked_notification(event: PostLikedEvent) -> None:
    from_user = _resolve_user_or_none(event.actor_user_id)
    if from_user is None:
        return

    runtime_access.notify_runtime_notification("notify_post_liked", post_id=event.post_id, from_user=from_user)


def _resolve_user_or_none(user_id: int):
    try:
        return get_runtime_user_by_id(user_id)
    except Exception:
        return None
