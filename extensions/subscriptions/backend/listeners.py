from apps.core.extensions.runtime_access import (
    follow_runtime_discussion,
)
from apps.core.extensions import runtime_access
from apps.core.extensions.runtime_access import (
    get_runtime_post_number,
)
from apps.core.extensions.runtime_access import (
    get_runtime_user_by_id,
    get_runtime_user_preference,
)


def handle_post_created_discussion_reply_notification(event) -> None:
    if not event.is_approved:
        return

    _notify_discussion_reply(
        discussion_id=event.discussion_id,
        post_id=event.post_id,
        actor_user_id=event.actor_user_id,
    )


def handle_post_approved_discussion_reply_notification(event) -> None:
    if not event.actor_user_id:
        return

    _notify_discussion_reply(
        discussion_id=event.discussion_id,
        post_id=event.post_id,
        actor_user_id=event.actor_user_id,
    )


def handle_discussion_created_follow_after_create(event) -> None:
    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_create",
        last_read_post_number=1,
    )


def handle_post_created_follow_after_reply(event) -> None:
    if not event.is_approved:
        return

    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_reply",
        post_id=event.post_id,
    )


def handle_post_approved_follow_after_reply(event) -> None:
    if not event.actor_user_id:
        return

    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_reply",
        post_id=event.post_id,
    )


def handle_post_hidden_discussion_reply_notifications(event) -> None:
    if event.is_hidden:
        _delete_discussion_reply_notifications_for_post(event.post_id)


def handle_post_deleted_discussion_reply_notifications(event) -> None:
    _delete_discussion_reply_notifications_for_post(event.post_id)


def _notify_discussion_reply(*, discussion_id: int, post_id: int, actor_user_id: int) -> None:
    from_user = _resolve_user_or_none(actor_user_id)
    if from_user is None:
        return

    runtime_access.notify_runtime_notification(
        "notify_discussion_reply",
        discussion_id=discussion_id,
        post_id=post_id,
        from_user=from_user,
    )


def _follow_discussion_if_enabled(
    *,
    discussion_id: int,
    user_id: int,
    preference_key: str,
    post_id: int | None = None,
    last_read_post_number: int | None = None,
) -> None:
    user = _resolve_user_or_none(user_id)
    if user is None or not get_runtime_user_preference(user, preference_key, fallback=False):
        return

    if last_read_post_number is None and post_id is not None:
        last_read_post_number = get_runtime_post_number(post_id)

    follow_runtime_discussion(
        discussion_id=discussion_id,
        user_id=user_id,
        last_read_post_number=last_read_post_number,
    )


def _resolve_user_or_none(user_id: int):
    try:
        return get_runtime_user_by_id(user_id)
    except Exception:
        return None


def _delete_discussion_reply_notifications_for_post(post_id: int) -> None:
    runtime_access.delete_runtime_discussion_reply_notifications_for_post(post_id)



