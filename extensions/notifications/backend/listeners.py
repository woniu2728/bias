from apps.core.forum_events import (
    PostCreatedEvent,
    PostLikedEvent,
    UserSuspendedEvent,
    UserUnsuspendedEvent,
)


def handle_post_created_direct_reply_notification(event: PostCreatedEvent) -> None:
    if not event.is_approved:
        return

    from extensions.notifications.backend.services import NotificationService
    from apps.users.models import User

    if not event.reply_to_post_id:
        return

    try:
        from_user = User.objects.get(id=event.actor_user_id)
    except User.DoesNotExist:
        return

    NotificationService.notify_post_reply(
        reply_to_post_id=event.reply_to_post_id,
        post_id=event.post_id,
        from_user=from_user,
    )


def handle_post_liked_notification(event: PostLikedEvent) -> None:
    from extensions.notifications.backend.services import NotificationService
    from apps.users.models import User

    try:
        from_user = User.objects.get(id=event.actor_user_id)
    except User.DoesNotExist:
        return

    NotificationService.notify_post_liked(post_id=event.post_id, from_user=from_user)


def handle_user_suspended_notification(event: UserSuspendedEvent) -> None:
    from extensions.notifications.backend.services import NotificationService
    from apps.users.models import User

    user = User.objects.filter(id=event.user_id).first()
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = User.objects.filter(id=event.actor_user_id).first()

    NotificationService.notify_user_suspended(user, admin_user)


def handle_user_unsuspended_notification(event: UserUnsuspendedEvent) -> None:
    from extensions.notifications.backend.services import NotificationService
    from apps.users.models import User

    user = User.objects.filter(id=event.user_id).first()
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = User.objects.filter(id=event.actor_user_id).first()

    NotificationService.notify_user_unsuspended(user, admin_user)
