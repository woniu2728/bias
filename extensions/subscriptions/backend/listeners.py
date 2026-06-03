from django.utils import timezone

from apps.core.forum_events import (
    DiscussionCreatedEvent,
    PostApprovedEvent,
    PostCreatedEvent,
    PostDeletedEvent,
    PostHiddenEvent,
)


def handle_post_created_discussion_reply_notification(event: PostCreatedEvent) -> None:
    if not event.is_approved:
        return

    _notify_discussion_reply(
        discussion_id=event.discussion_id,
        post_id=event.post_id,
        actor_user_id=event.actor_user_id,
    )


def handle_post_approved_discussion_reply_notification(event: PostApprovedEvent) -> None:
    if not event.actor_user_id:
        return

    _notify_discussion_reply(
        discussion_id=event.discussion_id,
        post_id=event.post_id,
        actor_user_id=event.actor_user_id,
    )


def handle_discussion_created_follow_after_create(event: DiscussionCreatedEvent) -> None:
    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_create",
        last_read_post_number=1,
    )


def handle_post_created_follow_after_reply(event: PostCreatedEvent) -> None:
    if not event.is_approved:
        return

    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_reply",
        post_id=event.post_id,
    )


def handle_post_approved_follow_after_reply(event: PostApprovedEvent) -> None:
    if not event.actor_user_id:
        return

    _follow_discussion_if_enabled(
        discussion_id=event.discussion_id,
        user_id=event.actor_user_id,
        preference_key="follow_after_reply",
        post_id=event.post_id,
    )


def handle_post_hidden_discussion_reply_notifications(event: PostHiddenEvent) -> None:
    if event.is_hidden:
        _delete_discussion_reply_notifications_for_post(event.post_id)


def handle_post_deleted_discussion_reply_notifications(event: PostDeletedEvent) -> None:
    _delete_discussion_reply_notifications_for_post(event.post_id)


def _notify_discussion_reply(*, discussion_id: int, post_id: int, actor_user_id: int) -> None:
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    try:
        from_user = User.objects.get(id=actor_user_id)
    except User.DoesNotExist:
        return

    NotificationService.notify_discussion_reply(
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
    from apps.discussions.models import DiscussionUser
    from apps.posts.models import Post
    from apps.users.models import User
    from apps.users.preferences import get_user_preference_value

    user = User.objects.filter(id=user_id).first()
    if user is None or not get_user_preference_value(user, preference_key, fallback=False):
        return

    if last_read_post_number is None and post_id is not None:
        last_read_post_number = Post.objects.filter(id=post_id).values_list("number", flat=True).first()

    defaults = {"is_subscribed": True}
    if last_read_post_number:
        defaults["last_read_at"] = timezone.now()
        defaults["last_read_post_number"] = last_read_post_number

    DiscussionUser.objects.update_or_create(
        discussion_id=discussion_id,
        user_id=user_id,
        defaults=defaults,
    )


def _delete_discussion_reply_notifications_for_post(post_id: int) -> None:
    from apps.notifications.models import Notification
    from apps.notifications.services import NotificationService

    Notification.objects.filter(
        type=NotificationService.TYPE_DISCUSSION_REPLY,
        data__post_id=post_id,
    ).delete()
