from typing import List, Optional

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    DiscussionCreatedEvent,
    DiscussionHiddenEvent,
    DiscussionLockedEvent,
    DiscussionRejectedEvent,
    DiscussionRenamedEvent,
    DiscussionResubmittedEvent,
    DiscussionStickyChangedEvent,
    DiscussionTagStatsRefreshEvent,
    DiscussionTaggedEvent,
    TagStatsRefreshRequestedEvent,
)
from apps.discussions.models import Discussion, DiscussionUser
from apps.posts.models import Post
from apps.tags.models import DiscussionTag
from apps.tags.services import TagService
from apps.users.models import User
from apps.users.preferences import get_user_preference_value
from apps.users.services import UserService


def create_discussion(
    title: str,
    content: str,
    user: User,
    *,
    tag_ids: Optional[List[int]] = None,
    default_post_type,
    render_markdown_cb,
) -> Discussion:
    UserService.ensure_not_suspended(user, "发布讨论")
    UserService.ensure_email_confirmed(user, "发布讨论")
    UserService.ensure_forum_permission(user, "startDiscussion", "没有权限发起讨论")
    requires_approval = UserService.requires_content_approval(user, "startDiscussionWithoutApproval")
    approval_status = Discussion.APPROVAL_PENDING if requires_approval else Discussion.APPROVAL_APPROVED
    approved_at = None if requires_approval else timezone.now()
    approved_by = None if requires_approval else user
    tags = TagService.ensure_can_start_discussion(user, tag_ids)

    with transaction.atomic():
        discussion = Discussion.objects.create(
            title=title,
            user=user,
            last_posted_at=timezone.now(),
            last_posted_user=user,
            approval_status=approval_status,
            approved_at=approved_at,
            approved_by=approved_by,
        )

        first_post = Post.objects.create(
            discussion=discussion,
            number=1,
            user=user,
            content=content,
            content_html=render_markdown_cb(content),
            type=default_post_type,
            approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
            approved_at=approved_at,
            approved_by=approved_by,
        )

        discussion.first_post_id = first_post.id
        discussion.last_post_id = first_post.id
        discussion.last_post_number = 1
        discussion.comment_count = 1
        discussion.participant_count = 1
        discussion.save()

        if tags:
            for tag in tags:
                DiscussionTag.objects.create(discussion=discussion, tag=tag)

        if not requires_approval:
            user.discussion_count = F("discussion_count") + 1
            user.save(update_fields=["discussion_count"])

        DiscussionUser.objects.create(
            discussion=discussion,
            user=user,
            last_read_at=timezone.now(),
            last_read_post_number=1,
            is_subscribed=get_user_preference_value(user, "follow_after_create", fallback=False),
        )

        dispatch_forum_event_after_commit(
            DiscussionCreatedEvent(
                discussion_id=discussion.id,
                actor_user_id=user.id,
                tag_ids=tuple(tag.id for tag in tags),
                is_approved=not requires_approval,
            )
        )
        return discussion


def update_discussion(
    discussion_id: int,
    user: User,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tag_ids: Optional[List[int]] = None,
    is_locked: Optional[bool] = None,
    is_sticky: Optional[bool] = None,
    is_hidden: Optional[bool] = None,
    can_edit_discussion_cb,
    render_markdown_cb,
    set_locked_state_cb,
    set_sticky_state_cb,
    set_hidden_state_cb,
) -> Discussion:
    UserService.ensure_not_suspended(user, "编辑讨论")
    discussion = Discussion.objects.get(id=discussion_id)

    if not can_edit_discussion_cb(discussion, user):
        raise PermissionDenied("没有权限编辑此讨论")

    with transaction.atomic():
        previous_tag_ids = list(discussion.discussion_tags.values_list("tag_id", flat=True))
        previous_tag_names = list(
            discussion.discussion_tags.select_related("tag")
            .order_by("tag__name")
            .values_list("tag__name", flat=True)
        )
        previous_title = discussion.title
        first_post = None

        if content is not None:
            first_post = Post.objects.get(id=discussion.first_post_id)

        if title is not None:
            discussion.title = title

        if content is not None and first_post is not None:
            first_post.content = content
            first_post.content_html = render_markdown_cb(content)
            first_post.edited_at = timezone.now()
            first_post.edited_user = user
            first_post.save(update_fields=["content", "content_html", "edited_at", "edited_user"])

        if tag_ids is not None:
            tags = TagService.ensure_can_start_discussion(user, tag_ids)
            DiscussionTag.objects.filter(discussion=discussion).delete()
            DiscussionTag.objects.bulk_create([
                DiscussionTag(discussion=discussion, tag=tag)
                for tag in tags
            ])

        should_persist_discussion = True

        if is_locked is not None:
            if not user.is_staff:
                raise PermissionDenied("没有权限锁定/解锁讨论")
            set_locked_state_cb(discussion, user, is_locked)
            should_persist_discussion = False

        if is_sticky is not None:
            if not user.is_staff:
                raise PermissionDenied("没有权限置顶/取消置顶讨论")
            set_sticky_state_cb(discussion, user, is_sticky)

        if is_hidden is not None:
            set_hidden_state_cb(discussion, user, is_hidden)

        if (
            discussion.approval_status == Discussion.APPROVAL_REJECTED
            and not user.is_staff
            and discussion.user_id == user.id
        ):
            previous_approval_status = discussion.approval_status
            discussion.approval_status = Discussion.APPROVAL_PENDING
            discussion.approved_at = None
            discussion.approved_by = None
            discussion.approval_note = ""
            discussion.hidden_at = None
            discussion.hidden_user = None

            if first_post is None:
                first_post = Post.objects.get(id=discussion.first_post_id)
            first_post.approval_status = Post.APPROVAL_PENDING
            first_post.approved_at = None
            first_post.approved_by = None
            first_post.approval_note = ""
            first_post.hidden_at = None
            first_post.hidden_user = None
            first_post.save(update_fields=[
                "approval_status",
                "approved_at",
                "approved_by",
                "approval_note",
                "hidden_at",
                "hidden_user",
            ])
            dispatch_forum_event_after_commit(
                DiscussionResubmittedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=user.id,
                    previous_status=previous_approval_status,
                )
            )

        if should_persist_discussion:
            discussion.save()

        if title is not None and title != previous_title:
            dispatch_forum_event_after_commit(
                DiscussionRenamedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=user.id,
                    old_title=previous_title,
                    new_title=title,
                )
            )

        if tag_ids is not None:
            current_tag_names = list(
                discussion.discussion_tags.select_related("tag")
                .order_by("tag__name")
                .values_list("tag__name", flat=True)
            )
            current_tag_ids = list(
                discussion.discussion_tags.order_by("tag_id").values_list("tag_id", flat=True)
            )
            added_tags = [name for name in current_tag_names if name not in previous_tag_names]
            removed_tags = [name for name in previous_tag_names if name not in current_tag_names]
            if added_tags or removed_tags:
                dispatch_forum_event_after_commit(
                    DiscussionTaggedEvent(
                        discussion_id=discussion.id,
                        actor_user_id=user.id,
                        added_tags=tuple(added_tags),
                        removed_tags=tuple(removed_tags),
                        tag_ids=tuple(sorted(set(previous_tag_ids) | set(current_tag_ids))),
                    )
                )

        if is_hidden is not None or tag_ids is not None:
            refreshed_tag_ids = set(previous_tag_ids) | set(
                discussion.discussion_tags.values_list("tag_id", flat=True)
            )
            if refreshed_tag_ids:
                dispatch_forum_event_after_commit(
                    TagStatsRefreshRequestedEvent(tag_ids=tuple(sorted(refreshed_tag_ids)))
                )

        return discussion


def set_hidden_state(
    discussion: Discussion,
    user: User,
    is_hidden: bool,
    *,
    approved_reply_counts_by_author_cb,
) -> Discussion:
    if not user.is_staff:
        raise PermissionDenied("没有权限隐藏/显示讨论")

    was_hidden = discussion.hidden_at is not None
    if was_hidden == is_hidden:
        return discussion

    should_adjust_counts = discussion.approval_status == Discussion.APPROVAL_APPROVED
    approved_reply_counts = {}
    if should_adjust_counts:
        approved_reply_counts = approved_reply_counts_by_author_cb(discussion)

    discussion.hidden_at = timezone.now() if is_hidden else None
    discussion.hidden_user = user if is_hidden else None

    with transaction.atomic():
        discussion.save(update_fields=["hidden_at", "hidden_user"])
        if should_adjust_counts:
            discussion_delta = -1 if is_hidden else 1
            reply_delta = -1 if is_hidden else 1
            if discussion.user:
                User.objects.filter(id=discussion.user_id).update(
                    discussion_count=F("discussion_count") + discussion_delta
                )
            for user_id, total in approved_reply_counts.items():
                User.objects.filter(id=user_id).update(
                    comment_count=F("comment_count") + (reply_delta * total)
                )

        dispatch_forum_event_after_commit(
            DiscussionHiddenEvent(
                discussion_id=discussion.id,
                actor_user_id=user.id,
                is_hidden=is_hidden,
            )
        )
        dispatch_forum_event_after_commit(
            DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
        )
    return discussion


def approve_discussion(
    discussion: Discussion,
    admin_user: User,
    note: str = "",
    *,
    approved_reply_counts_by_author_cb,
) -> Discussion:
    was_counted = discussion.approval_status == Discussion.APPROVAL_APPROVED
    approved_reply_counts = {}
    if not was_counted:
        approved_reply_counts = approved_reply_counts_by_author_cb(discussion)

    with transaction.atomic():
        discussion.approval_status = Discussion.APPROVAL_APPROVED
        discussion.approved_at = timezone.now()
        discussion.approved_by = admin_user
        discussion.approval_note = note
        discussion.hidden_at = None
        discussion.hidden_user = None
        discussion.save(update_fields=[
            "approval_status",
            "approved_at",
            "approved_by",
            "approval_note",
            "hidden_at",
            "hidden_user",
        ])

        Post.objects.filter(id=discussion.first_post_id).update(
            approval_status=Post.APPROVAL_APPROVED,
            approved_at=discussion.approved_at,
            approved_by=admin_user,
            approval_note=note,
            hidden_at=None,
            hidden_user=None,
        )

        if not was_counted:
            if discussion.user:
                User.objects.filter(id=discussion.user_id).update(discussion_count=F("discussion_count") + 1)
            for user_id, total in approved_reply_counts.items():
                User.objects.filter(id=user_id).update(comment_count=F("comment_count") + total)

        if not was_counted:
            dispatch_forum_event_after_commit(
                DiscussionApprovedEvent(
                    discussion_id=discussion.id,
                    admin_user_id=admin_user.id,
                    note=note,
                )
            )
        else:
            dispatch_forum_event_after_commit(
                DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
            )

    discussion.refresh_from_db()
    return discussion


def reject_discussion(
    discussion: Discussion,
    admin_user: User,
    note: str = "",
    *,
    approved_reply_counts_by_author_cb,
) -> Discussion:
    rejected_at = timezone.now()
    previous_status = discussion.approval_status
    was_counted = discussion.approval_status == Discussion.APPROVAL_APPROVED
    approved_reply_counts = {}
    if was_counted:
        approved_reply_counts = approved_reply_counts_by_author_cb(discussion)

    with transaction.atomic():
        discussion.approval_status = Discussion.APPROVAL_REJECTED
        discussion.approved_at = rejected_at
        discussion.approved_by = admin_user
        discussion.approval_note = note
        discussion.hidden_at = rejected_at
        discussion.hidden_user = admin_user
        discussion.save(update_fields=[
            "approval_status",
            "approved_at",
            "approved_by",
            "approval_note",
            "hidden_at",
            "hidden_user",
        ])

        Post.objects.filter(id=discussion.first_post_id).update(
            approval_status=Post.APPROVAL_REJECTED,
            approved_at=rejected_at,
            approved_by=admin_user,
            approval_note=note,
            hidden_at=rejected_at,
            hidden_user=admin_user,
        )

        if was_counted:
            if discussion.user:
                User.objects.filter(id=discussion.user_id).update(discussion_count=F("discussion_count") - 1)
            for user_id, total in approved_reply_counts.items():
                User.objects.filter(id=user_id).update(comment_count=F("comment_count") - total)

        if previous_status != Discussion.APPROVAL_REJECTED:
            dispatch_forum_event_after_commit(
                DiscussionRejectedEvent(
                    discussion_id=discussion.id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                )
            )
        dispatch_forum_event_after_commit(
            DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
        )

    discussion.refresh_from_db()
    return discussion


def approved_reply_counts_by_author(discussion: Discussion, *, user_counted_post_types) -> dict:
    approved_replies = (
        Post.objects.filter(
            discussion=discussion,
            type__in=user_counted_post_types,
            approval_status=Post.APPROVAL_APPROVED,
            hidden_at__isnull=True,
            number__gt=1,
        )
        .exclude(user_id__isnull=True)
        .values("user_id")
        .annotate(total=Count("id"))
    )
    return {row["user_id"]: row["total"] for row in approved_replies}


def delete_discussion(
    discussion_id: int,
    user: User,
    *,
    can_delete_discussion_cb,
    approved_reply_counts_by_author_cb,
) -> bool:
    UserService.ensure_not_suspended(user, "删除讨论")
    discussion = Discussion.objects.get(id=discussion_id)

    if not can_delete_discussion_cb(discussion, user):
        raise PermissionDenied("没有权限删除此讨论")

    with transaction.atomic():
        counted_discussion = (
            discussion.approval_status == Discussion.APPROVAL_APPROVED
            and discussion.hidden_at is None
        )
        approved_reply_counts = {}
        if counted_discussion:
            approved_reply_counts = approved_reply_counts_by_author_cb(discussion)

        Post.objects.filter(discussion=discussion).delete()
        tag_ids = list(discussion.discussion_tags.values_list("tag_id", flat=True))
        discussion.delete()

        if tag_ids:
            dispatch_forum_event_after_commit(
                TagStatsRefreshRequestedEvent(tag_ids=tuple(sorted(tag_ids)))
            )

        if counted_discussion and discussion.user:
            User.objects.filter(id=discussion.user_id).update(
                discussion_count=F("discussion_count") - 1
            )

        for user_id, total in approved_reply_counts.items():
            User.objects.filter(id=user_id).update(comment_count=F("comment_count") - total)

    return True


def set_locked_state(discussion: Discussion, actor: User, is_locked: bool) -> Discussion:
    if not actor.is_staff:
        raise PermissionDenied("没有权限锁定/解锁讨论")

    if discussion.is_locked == is_locked:
        return discussion

    with transaction.atomic():
        discussion.is_locked = is_locked
        discussion.save(update_fields=["is_locked"])
        dispatch_forum_event_after_commit(
            DiscussionLockedEvent(
                discussion_id=discussion.id,
                actor_user_id=actor.id,
                is_locked=is_locked,
            )
        )
    return discussion


def set_sticky_state(discussion: Discussion, actor: User, is_sticky: bool) -> Discussion:
    if not actor.is_staff:
        raise PermissionDenied("没有权限置顶/取消置顶讨论")

    if discussion.is_sticky == is_sticky:
        return discussion

    with transaction.atomic():
        discussion.is_sticky = is_sticky
        discussion.save(update_fields=["is_sticky"])
        dispatch_forum_event_after_commit(
            DiscussionStickyChangedEvent(
                discussion_id=discussion.id,
                actor_user_id=actor.id,
                is_sticky=is_sticky,
            )
        )
    return discussion
