from __future__ import annotations

from apps.core.extensions.runtime_access import get_runtime_post_by_id, get_runtime_user_by_id
from extensions.points.backend.settings import get_points_settings
from extensions.points.backend.services import award_points


def handle_discussion_created(event) -> None:
    settings = get_points_settings()
    if not settings.enabled or not getattr(event, "is_approved", True):
        return
    user = _resolve_user_or_none(getattr(event, "actor_user_id", 0))
    if user is None:
        return
    award_points(
        user,
        settings.discussion_create_reward,
        reason="discussion_created",
        idempotency_key=f"discussion:create:{event.discussion_id}",
        source_type="discussion",
        source_id=event.discussion_id,
        meta={"event": "DiscussionCreatedEvent"},
    )


def handle_post_created(event) -> None:
    settings = get_points_settings()
    if not settings.enabled or not getattr(event, "is_approved", True):
        return
    user = _resolve_user_or_none(getattr(event, "actor_user_id", 0))
    if user is None:
        return
    award_points(
        user,
        settings.reply_create_reward,
        reason="reply_created",
        idempotency_key=f"post:create:{event.post_id}",
        source_type="post",
        source_id=event.post_id,
        meta={"event": "PostCreatedEvent", "discussion_id": getattr(event, "discussion_id", None)},
    )


def handle_post_liked(event) -> None:
    settings = get_points_settings()
    if not settings.enabled or settings.like_received_reward <= 0:
        return
    try:
        post = get_runtime_post_by_id(
            int(getattr(event, "post_id", 0)),
            select_related=("user",),
        )
    except Exception:
        return
    if post is None or not getattr(post, "user", None):
        return
    if int(getattr(post, "user_id", 0) or 0) == int(getattr(event, "actor_user_id", 0) or 0):
        return
    award_points(
        post.user,
        settings.like_received_reward,
        reason="like_received",
        idempotency_key=f"post:like-received:{event.post_id}:{event.actor_user_id}",
        source_type="post",
        source_id=getattr(event, "post_id", ""),
        meta={"event": "PostLikedEvent", "from_user_id": getattr(event, "actor_user_id", None)},
    )


def _resolve_user_or_none(user_id: int):
    try:
        return get_runtime_user_by_id(int(user_id or 0))
    except Exception:
        return None
