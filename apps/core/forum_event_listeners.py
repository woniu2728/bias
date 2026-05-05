from __future__ import annotations

from types import SimpleNamespace

from apps.core.domain_events import get_forum_event_bus
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    DiscussionCreatedEvent,
    DiscussionHiddenEvent,
    DiscussionLockedEvent,
    DiscussionRejectedEvent,
    DiscussionRenamedEvent,
    DiscussionResubmittedEvent,
    DiscussionStickyChangedEvent,
    DiscussionTaggedEvent,
    PostApprovedEvent,
    PostCreatedEvent,
    DiscussionTagStatsRefreshEvent,
    PostHiddenEvent,
    PostLikedEvent,
    PostRejectedEvent,
    PostResubmittedEvent,
    TagStatsRefreshRequestedEvent,
    UserMentionedEvent,
    UserSuspendedEvent,
    UserUnsuspendedEvent,
)
from apps.core.forum_timeline import (
    build_discussion_hidden_content,
    build_discussion_locked_content,
    build_discussion_renamed_content,
    build_discussion_resubmitted_content,
    build_discussion_review_content,
    build_discussion_sticky_content,
    build_discussion_tagged_content,
    build_post_hidden_content,
    build_post_resubmitted_content,
    build_post_review_content,
    create_timeline_event_post,
)


_listeners_bootstrapped = False


def bootstrap_forum_event_listeners() -> None:
    global _listeners_bootstrapped
    if _listeners_bootstrapped:
        return

    event_bus = get_forum_event_bus()
    event_bus.register(DiscussionCreatedEvent, handle_discussion_created)
    event_bus.register(DiscussionApprovedEvent, handle_discussion_approved)
    event_bus.register(DiscussionRenamedEvent, handle_discussion_renamed)
    event_bus.register(DiscussionTaggedEvent, handle_discussion_tagged)
    event_bus.register(DiscussionLockedEvent, handle_discussion_locked)
    event_bus.register(DiscussionStickyChangedEvent, handle_discussion_sticky_changed)
    event_bus.register(DiscussionHiddenEvent, handle_discussion_hidden)
    event_bus.register(DiscussionRejectedEvent, handle_discussion_rejected)
    event_bus.register(DiscussionResubmittedEvent, handle_discussion_resubmitted)
    event_bus.register(PostCreatedEvent, handle_post_created)
    event_bus.register(PostApprovedEvent, handle_post_approved)
    event_bus.register(PostRejectedEvent, handle_post_rejected)
    event_bus.register(PostResubmittedEvent, handle_post_resubmitted)
    event_bus.register(PostHiddenEvent, handle_post_hidden)
    event_bus.register(PostLikedEvent, handle_post_liked)
    event_bus.register(UserMentionedEvent, handle_user_mentioned)
    event_bus.register(UserSuspendedEvent, handle_user_suspended)
    event_bus.register(UserUnsuspendedEvent, handle_user_unsuspended)
    event_bus.register(DiscussionTagStatsRefreshEvent, handle_discussion_tag_stats_refresh)
    event_bus.register(TagStatsRefreshRequestedEvent, handle_tag_stats_refresh_requested)
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
    create_timeline_event_post(
        discussion_id=discussion.id,
        actor_user_id=admin_user.id,
        post_type="discussionApproved",
        update_discussion_last_post=False,
        content=build_discussion_review_content(
            SimpleNamespace(
                post_type="discussionApproved",
                previous_status="pending",
                note=event.note,
            )
        )[1],
    )


def handle_discussion_renamed(event: DiscussionRenamedEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(event, post_type="discussionRenamed"),
        build_discussion_renamed_content,
    )


def handle_discussion_tagged(event: DiscussionTaggedEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(event, post_type="discussionTagged"),
        build_discussion_tagged_content,
    )


def handle_discussion_locked(event: DiscussionLockedEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(event, post_type="discussionLocked"),
        build_discussion_locked_content,
    )


def handle_discussion_sticky_changed(event: DiscussionStickyChangedEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(event, post_type="discussionSticky"),
        build_discussion_sticky_content,
    )


def handle_discussion_hidden(event: DiscussionHiddenEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(event, post_type="discussionHidden"),
        build_discussion_hidden_content,
    )


def handle_discussion_rejected(event: DiscussionRejectedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.discussions.models import Discussion
    from apps.users.models import User

    try:
        discussion = Discussion.objects.select_related("user").get(id=event.discussion_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Discussion.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_discussion_rejected(discussion, admin_user, note=event.note)
    _create_timeline_from_builder(
        _make_timeline_context(
            event,
            actor_user_id=event.admin_user_id,
            post_type="discussionRejected",
        ),
        build_discussion_review_content,
    )


def handle_discussion_resubmitted(event: DiscussionResubmittedEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(
            event,
            post_type="discussionResubmitted",
        ),
        build_discussion_resubmitted_content,
    )


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
    enriched_event = _make_timeline_context(
        event,
        actor_user_id=event.admin_user_id,
        post_type="postApproved",
        post_number=getattr(post, "number", None),
    )
    _create_timeline_from_builder(enriched_event, build_post_review_content)


def handle_post_rejected(event: PostRejectedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.posts.models import Post
    from apps.users.models import User

    try:
        post = Post.objects.select_related("discussion", "user").get(id=event.post_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Post.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_post_rejected(post, admin_user, note=event.note)
    enriched_event = _make_timeline_context(
        event,
        actor_user_id=event.admin_user_id,
        post_type="postRejected",
        post_number=getattr(post, "number", None),
    )
    _create_timeline_from_builder(enriched_event, build_post_review_content)


def handle_post_resubmitted(event: PostResubmittedEvent) -> None:
    from apps.posts.models import Post

    try:
        post = Post.objects.get(id=event.post_id)
    except Post.DoesNotExist:
        return

    enriched_event = _make_timeline_context(
        event,
        post_type="postResubmitted",
        post_number=getattr(post, "number", None),
    )
    _create_timeline_from_builder(enriched_event, build_post_resubmitted_content)


def handle_post_hidden(event: PostHiddenEvent) -> None:
    _create_timeline_from_builder(
        _make_timeline_context(
            event,
            post_type="postHidden",
        ),
        build_post_hidden_content,
    )


def handle_post_liked(event: PostLikedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    try:
        from_user = User.objects.get(id=event.actor_user_id)
    except User.DoesNotExist:
        return

    NotificationService.notify_post_liked(post_id=event.post_id, from_user=from_user)


def handle_user_mentioned(event: UserMentionedEvent) -> None:
    from apps.notifications.services import NotificationService
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


def handle_user_suspended(event: UserSuspendedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    user = User.objects.filter(id=event.user_id).first()
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = User.objects.filter(id=event.actor_user_id).first()

    NotificationService.notify_user_suspended(user, admin_user)


def handle_user_unsuspended(event: UserUnsuspendedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    user = User.objects.filter(id=event.user_id).first()
    if user is None:
        return

    admin_user = None
    if event.actor_user_id:
        admin_user = User.objects.filter(id=event.actor_user_id).first()

    NotificationService.notify_user_unsuspended(user, admin_user)


def handle_discussion_tag_stats_refresh(event: DiscussionTagStatsRefreshEvent) -> None:
    from apps.tags.services import TagService

    TagService.refresh_discussion_tag_stats(event.discussion_id)


def handle_tag_stats_refresh_requested(event: TagStatsRefreshRequestedEvent) -> None:
    if not event.tag_ids:
        return

    from apps.tags.services import TagService

    TagService.dispatch_refresh_tag_stats(list(event.tag_ids))


def _create_timeline_from_builder(event, builder) -> None:
    built = builder(event)
    if not built:
        return

    post_type, content = built
    update_discussion_last_post = post_type not in {
        "discussionApproved",
        "discussionRejected",
        "discussionResubmitted",
        "postApproved",
        "postRejected",
        "postResubmitted",
    }
    create_timeline_event_post(
        discussion_id=event.discussion_id,
        actor_user_id=event.actor_user_id,
        post_type=post_type,
        content=content,
        update_discussion_last_post=update_discussion_last_post,
    )


def _make_timeline_context(event, **extra):
    payload = dict(getattr(event, "__dict__", {}))
    payload.update(extra)
    return SimpleNamespace(**payload)
