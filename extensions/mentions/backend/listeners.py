from apps.core.forum_events import UserMentionedEvent


def handle_user_mentioned_notification(event: UserMentionedEvent) -> None:
    from extensions.notifications.backend.services import NotificationService
    from apps.users.models import User

    try:
        mentioned_user = User.objects.get(id=event.mentioned_user_id)
    except User.DoesNotExist:
        return

    from_user = None
    if event.actor_user_id:
        from_user = User.objects.filter(id=event.actor_user_id).first()
    if from_user is None:
        return

    NotificationService.notify_user_mentioned(
        post_id=event.post_id,
        mentioned_user=mentioned_user,
        from_user=from_user,
    )
