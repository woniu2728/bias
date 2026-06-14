from apps.core.extensions.runtime import get_runtime_user_by_id


def handle_post_created_direct_reply_notification(event) -> None:
    if not event.is_approved:
        return

    from extensions.notifications.backend.services import NotificationService

    if not event.reply_to_post_id:
        return

    from_user = _resolve_user_or_none(event.actor_user_id)
    if from_user is None:
        return

    NotificationService.notify_post_reply(
        reply_to_post_id=event.reply_to_post_id,
        post_id=event.post_id,
        from_user=from_user,
    )


def handle_user_suspended_notification(event) -> None:
    from extensions.notifications.backend.services import NotificationService

    user = _resolve_user_or_none(event.user_id)
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = _resolve_user_or_none(event.actor_user_id)

    NotificationService.notify_user_suspended(user, admin_user)


def handle_user_unsuspended_notification(event) -> None:
    from extensions.notifications.backend.services import NotificationService

    user = _resolve_user_or_none(event.user_id)
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = _resolve_user_or_none(event.actor_user_id)

    NotificationService.notify_user_unsuspended(user, admin_user)


def _resolve_user_or_none(user_id: int):
    try:
        return get_runtime_user_by_id(user_id)
    except Exception:
        return None
