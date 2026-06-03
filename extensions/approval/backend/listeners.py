from apps.core.forum_runtime import (
    broadcast_discussion_event,
    create_timeline_from_builder,
    make_timeline_context,
)
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    DiscussionRejectedEvent,
    DiscussionResubmittedEvent,
    PostApprovedEvent,
    PostRejectedEvent,
    PostResubmittedEvent,
)
from apps.core.forum_timeline import (
    build_discussion_resubmitted_content,
    build_discussion_review_content,
    build_post_resubmitted_content,
    build_post_review_content,
)


def handle_discussion_approved(event: DiscussionApprovedEvent) -> None:
    from apps.discussions.models import Discussion
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    try:
        discussion = Discussion.objects.select_related("user").get(id=event.discussion_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Discussion.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_discussion_approved(discussion, admin_user, note=event.note)
    broadcast_discussion_event(
        event.discussion_id,
        "discussion.approved",
        include_discussion=True,
        include_post=True,
        post_id_getter=lambda current_discussion: current_discussion.first_post_id,
    )
    create_timeline_from_builder(
        make_timeline_context(
            event,
            actor_user_id=event.admin_user_id,
            post_type="discussionApproved",
            previous_status="pending",
        ),
        build_discussion_review_content,
        update_discussion_last_post=False,
    )


def handle_discussion_rejected(event: DiscussionRejectedEvent) -> None:
    from apps.discussions.models import Discussion
    from apps.notifications.services import NotificationService
    from apps.users.models import User

    try:
        discussion = Discussion.objects.select_related("user").get(id=event.discussion_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Discussion.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_discussion_rejected(discussion, admin_user, note=event.note)
    broadcast_discussion_event(event.discussion_id, "discussion.rejected")
    create_timeline_from_builder(
        make_timeline_context(
            event,
            actor_user_id=event.admin_user_id,
            post_type="discussionRejected",
        ),
        build_discussion_review_content,
        update_discussion_last_post=False,
    )


def handle_discussion_resubmitted(event: DiscussionResubmittedEvent) -> None:
    broadcast_discussion_event(event.discussion_id, "discussion.resubmitted")
    create_timeline_from_builder(
        make_timeline_context(
            event,
            post_type="discussionResubmitted",
        ),
        build_discussion_resubmitted_content,
        update_discussion_last_post=False,
    )


def handle_post_approved(event: PostApprovedEvent) -> None:
    from apps.notifications.services import NotificationService
    from apps.posts.models import Post
    from apps.users.models import User

    try:
        post = Post.objects.select_related("user", "discussion").get(id=event.post_id)
        admin_user = User.objects.get(id=event.admin_user_id)
    except (Post.DoesNotExist, User.DoesNotExist):
        return

    NotificationService.notify_post_approved(post, admin_user, note=event.note)
    broadcast_discussion_event(event.discussion_id, "post.approved", include_discussion=True, post_id=event.post_id)
    enriched_event = make_timeline_context(
        event,
        actor_user_id=event.admin_user_id,
        post_type="postApproved",
        post_number=getattr(post, "number", None),
    )
    create_timeline_from_builder(enriched_event, build_post_review_content, update_discussion_last_post=False)


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
    broadcast_discussion_event(event.discussion_id, "post.rejected")
    enriched_event = make_timeline_context(
        event,
        actor_user_id=event.admin_user_id,
        post_type="postRejected",
        post_number=getattr(post, "number", None),
    )
    create_timeline_from_builder(enriched_event, build_post_review_content, update_discussion_last_post=False)


def handle_post_resubmitted(event: PostResubmittedEvent) -> None:
    from apps.posts.models import Post

    try:
        post = Post.objects.get(id=event.post_id)
    except Post.DoesNotExist:
        return

    enriched_event = make_timeline_context(
        event,
        post_type="postResubmitted",
        post_number=getattr(post, "number", None),
    )
    broadcast_discussion_event(event.discussion_id, "post.resubmitted")
    create_timeline_from_builder(enriched_event, build_post_resubmitted_content, update_discussion_last_post=False)
