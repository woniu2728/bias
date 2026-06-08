from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.runtime_access import get_runtime_post_lifecycle_service, refresh_runtime_model_private
from apps.core.forum_events import (
    PostApprovedEvent,
    PostRejectedEvent,
)
from extensions.discussions.backend.models import Discussion, DiscussionUser
from extensions.posts.backend.models import Post
from extensions.users.backend.models import User


def refresh_discussion_approved_stats(discussion: Discussion, *, discussion_counted_post_types, user_counted_post_types):
    approved_posts = Post.objects.filter(
        discussion=discussion,
        type__in=discussion_counted_post_types,
        approval_status=Post.APPROVAL_APPROVED,
        hidden_at__isnull=True,
    ).order_by("number")

    approved_count = approved_posts.count()
    last_post = approved_posts.order_by("-number").select_related("user").first()

    discussion.comment_count = approved_count
    if last_post:
        discussion.last_post_id = last_post.id
        discussion.last_post_number = last_post.number
        discussion.last_posted_at = last_post.created_at
        discussion.last_posted_user = last_post.user
    else:
        discussion.last_post_id = None
        discussion.last_post_number = None
        discussion.last_posted_at = None
        discussion.last_posted_user = None

    discussion.save(update_fields=[
        "comment_count",
        "last_post_id",
        "last_post_number",
        "last_posted_at",
        "last_posted_user",
    ])
    return discussion


def approve_post(
    post: Post,
    admin_user: User,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        now = timezone.now()
        post.approval_status = Post.APPROVAL_APPROVED
        post.approved_at = now
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = None
        post.hidden_user = None
        refresh_runtime_model_private(post)
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user", "is_private"
        ])

        discussion = post.discussion
        if not was_counted:
            discussion.comment_count = F("comment_count") + 1
            if not discussion.last_post_number or post.number >= discussion.last_post_number:
                discussion.last_posted_at = now
                discussion.last_posted_user = post.user
                discussion.last_post_id = post.id
                discussion.last_post_number = post.number
            discussion.save()

            if post.user and post.type in user_counted_post_types:
                post.user.comment_count = F("comment_count") + 1
                post.user.save(update_fields=["comment_count"])
                approval_defaults = {
                    "last_read_at": now,
                    "last_read_post_number": post.number,
                }
                DiscussionUser.objects.update_or_create(
                    discussion=discussion,
                    user=post.user,
                    defaults=approval_defaults,
                )

            _apply_post_approved_extensions(
                post,
                context={
                    "content": post.content,
                    "actor": admin_user,
                    "previous_status": previous_status,
                },
            )

            dispatch_forum_event_after_commit(
                PostApprovedEvent(
                    post_id=post.id,
                    discussion_id=discussion.id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                )
            )
    post.refresh_from_db()
    return post


def _apply_post_approved_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_approved(post=post, context=context)


def reject_post(
    post: Post,
    admin_user: User,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    rejected_at = timezone.now()
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        post.approval_status = Post.APPROVAL_REJECTED
        post.approved_at = rejected_at
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = rejected_at
        post.hidden_user = admin_user
        refresh_runtime_model_private(post)
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user", "is_private"
        ])

        if was_counted:
            refresh_discussion_approved_stats_cb(post.discussion)
            if post.user and post.type in user_counted_post_types:
                post.user.comment_count = F("comment_count") - 1
                post.user.save(update_fields=["comment_count"])

        if previous_status != Post.APPROVAL_REJECTED:
            dispatch_forum_event_after_commit(
                PostRejectedEvent(
                    post_id=post.id,
                    discussion_id=post.discussion_id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                )
            )
    return post
