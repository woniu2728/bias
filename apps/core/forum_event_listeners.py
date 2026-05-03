from __future__ import annotations

from apps.core.domain_events import get_forum_event_bus
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    DiscussionCreatedEvent,
    PostApprovedEvent,
    PostCreatedEvent,
)


_listeners_bootstrapped = False


def bootstrap_forum_event_listeners() -> None:
    global _listeners_bootstrapped
    if _listeners_bootstrapped:
        return

    event_bus = get_forum_event_bus()
    event_bus.register(DiscussionCreatedEvent, handle_discussion_created)
    event_bus.register(DiscussionApprovedEvent, handle_discussion_approved)
    event_bus.register(PostCreatedEvent, handle_post_created)
    event_bus.register(PostApprovedEvent, handle_post_approved)
    _listeners_bootstrapped = True


def handle_discussion_created(event: DiscussionCreatedEvent) -> None:
    if not event.tag_ids:
        return

    from apps.tags.services import TagService

    TagService.dispatch_refresh_tag_stats(list(event.tag_ids))


def handle_discussion_approved(event: DiscussionApprovedEvent) -> None:
    from apps.discussions.models import Discussion
    from apps.notifications.services import NotificationService
    from apps.tags.services import TagService
    from apps.users.models import User

    try:
        discussion = Discussion.objects.select_related("user").get(id=event.discussion_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Discussion.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_discussion_approved(discussion, admin_user, note=event.note)
    TagService.refresh_discussion_tag_stats(discussion.id)


def handle_post_created(event: PostCreatedEvent) -> None:
    if not event.is_approved:
        return

    from apps.notifications.services import NotificationService
    from apps.tags.services import TagService
    from apps.users.models import User

    try:
        from_user = User.objects.get(id=event.actor_user_id)
    except User.DoesNotExist:
        return

    NotificationService.notify_discussion_reply(
        discussion_id=event.discussion_id,
        post_id=event.post_id,
        from_user=from_user,
    )
    if event.reply_to_post_id:
        NotificationService.notify_post_reply(
            reply_to_post_id=event.reply_to_post_id,
            post_id=event.post_id,
            from_user=from_user,
        )
    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_post_approved(event: PostApprovedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.posts.models import Post
    from apps.tags.services import TagService
    from apps.users.models import User

    try:
        post = Post.objects.select_related("user", "discussion").get(id=event.post_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Post.DoesNotExist, User.DoesNotExist):
        return

    if event.actor_user_id:
        try:
            from_user = User.objects.get(id=event.actor_user_id)
        except User.DoesNotExist:
            from_user = None
        if from_user:
            NotificationService.notify_discussion_reply(
                discussion_id=event.discussion_id,
                post_id=event.post_id,
                from_user=from_user,
            )

    NotificationService.notify_post_approved(post, admin_user, note=event.note)
    TagService.refresh_discussion_tag_stats(event.discussion_id)
