from typing import Optional

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
)
from apps.core.extensions.runtime_access import (
    get_runtime_discussion_lifecycle_service,
    get_runtime_post_lifecycle_service,
    get_runtime_resource_registry,
    refresh_runtime_model_private,
)
from apps.discussions.models import Discussion, DiscussionUser
from extensions.posts.backend.models import Post
from apps.users.models import User
from apps.users.services import UserService


def _prepare_discussion_create_extensions(discussion_lifecycle, *, user, payload: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.prepare_create(user=user, payload=payload)


def _apply_discussion_create_extensions(discussion_lifecycle, *, discussion, states: dict, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_create(discussion=discussion, states=states, context=context)


def _prepare_discussion_update_extensions(discussion_lifecycle, *, discussion, user, payload: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.prepare_update(discussion=discussion, user=user, payload=payload)


def _apply_discussion_update_extensions(discussion_lifecycle, *, discussion, states: dict, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_update(discussion=discussion, states=states, context=context)


def _prepare_discussion_delete_extensions(discussion_lifecycle, *, discussion, user, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.prepare_delete(discussion=discussion, user=user, context=context)


def _apply_discussion_delete_extensions(discussion_lifecycle, *, states: dict, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_delete(states=states, context=context)


def _apply_discussion_hidden_extensions(discussion_lifecycle, *, discussion, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_hidden(discussion=discussion, context=context)


def _apply_discussion_approved_extensions(discussion_lifecycle, *, discussion, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_approved(discussion=discussion, context=context)


def _apply_discussion_rejected_extensions(discussion_lifecycle, *, discussion, context: dict) -> dict:
    if discussion_lifecycle is None:
        return {}
    return discussion_lifecycle.apply_rejected(discussion=discussion, context=context)


def _apply_post_created_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_created(post=post, context=context)


def _apply_post_updated_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_updated(post=post, context=context)


def _apply_post_approved_extensions(post: Post, *, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_approved(post=post, context=context)


def _apply_post_deleted_extensions(*, context: dict) -> dict:
    post_lifecycle = get_runtime_post_lifecycle_service()
    if post_lifecycle is None:
        return {}
    return post_lifecycle.apply_deleted(context=context)


def _apply_discussion_resource_relationships(
    discussion: Discussion,
    *,
    payload: dict,
    user: User,
    creating: bool,
    actor_user_id: int,
) -> None:
    relationship_payload = _discussion_relationship_payload(payload)
    if not relationship_payload:
        return
    registry = get_runtime_resource_registry()
    registry.apply_resource_payload(
        "discussion",
        discussion,
        {},
        {
            "payload": relationship_payload,
            "user": user,
            "actor_user_id": actor_user_id,
        },
        creating=creating,
    )


def _discussion_relationship_payload(payload: dict) -> dict:
    payload = dict(payload or {})
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("relationships"), dict):
        return {"data": {"relationships": dict(data["relationships"])}}
    return {}


def _refresh_discussion_private_state(discussion: Discussion, *, first_post: Post | None = None) -> None:
    refresh_runtime_model_private(discussion)
    if first_post is not None:
        first_post.is_private = discussion.is_private or refresh_runtime_model_private(first_post)


def create_discussion(
    title: str,
    content: str,
    user: User,
    *,
    extension_payload: Optional[dict] = None,
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
    extension_payload = dict(extension_payload or {})
    discussion_lifecycle = get_runtime_discussion_lifecycle_service()
    extension_states = _prepare_discussion_create_extensions(
        discussion_lifecycle,
        user=user,
        payload=extension_payload,
    )

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

        _apply_discussion_create_extensions(
            discussion_lifecycle,
            discussion=discussion,
            states=extension_states,
            context={
                "actor_user_id": user.id,
                "payload": extension_payload,
            },
        )
        _apply_discussion_resource_relationships(
            discussion,
            payload=extension_payload,
            user=user,
            creating=True,
            actor_user_id=user.id,
        )
        _refresh_discussion_private_state(discussion, first_post=first_post)
        discussion.save(update_fields=["is_private"])
        first_post.save(update_fields=["is_private"])

        if not requires_approval:
            _apply_post_created_extensions(
                first_post,
                context={
                    "content": content,
                    "actor": user,
                    "discussion": discussion,
                    "is_first_post": True,
                    "is_approved": True,
                },
            )
            user.discussion_count = F("discussion_count") + 1
            user.save(update_fields=["discussion_count"])

        DiscussionUser.objects.create(
            discussion=discussion,
            user=user,
            last_read_at=timezone.now(),
            last_read_post_number=1,
            is_subscribed=False,
        )

        dispatch_forum_event_after_commit(
            DiscussionCreatedEvent(
                discussion_id=discussion.id,
                actor_user_id=user.id,
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
    extension_payload: Optional[dict] = None,
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

    extension_payload = dict(extension_payload or {})

    with transaction.atomic():
        discussion_lifecycle = get_runtime_discussion_lifecycle_service()
        extension_states = _prepare_discussion_update_extensions(
            discussion_lifecycle,
            discussion=discussion,
            user=user,
            payload=extension_payload,
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

        _apply_discussion_update_extensions(
            discussion_lifecycle,
            discussion=discussion,
            states=extension_states,
            context={
                "actor_user_id": user.id,
                "payload": extension_payload,
            },
        )
        _apply_discussion_resource_relationships(
            discussion,
            payload=extension_payload,
            user=user,
            creating=False,
            actor_user_id=user.id,
        )
        if first_post is None and discussion.first_post_id:
            first_post = Post.objects.get(id=discussion.first_post_id)
        _refresh_discussion_private_state(discussion, first_post=first_post)
        if first_post is not None:
            first_post.save(update_fields=["is_private"])
            if content is not None:
                _apply_post_updated_extensions(
                    first_post,
                    context={
                        "content": content,
                        "actor": user,
                        "discussion": discussion,
                        "is_first_post": True,
                    },
                )

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
                "is_private",
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
        else:
            discussion.save(update_fields=["is_private"])

        if title is not None and title != previous_title:
            dispatch_forum_event_after_commit(
                DiscussionRenamedEvent(
                    discussion_id=discussion.id,
                    actor_user_id=user.id,
                    old_title=previous_title,
                    new_title=title,
                )
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
    refresh_runtime_model_private(discussion)

    with transaction.atomic():
        discussion.save(update_fields=["hidden_at", "hidden_user", "is_private"])
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
        _apply_discussion_hidden_extensions(
            get_runtime_discussion_lifecycle_service(),
            discussion=discussion,
            context={
                "actor_user_id": user.id,
                "is_hidden": is_hidden,
            },
        )
    return discussion


def approve_discussion(
    discussion: Discussion,
    admin_user: User,
    note: str = "",
    *,
    approved_reply_counts_by_author_cb,
) -> Discussion:
    previous_status = discussion.approval_status
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
        refresh_runtime_model_private(discussion)
        discussion.save(update_fields=[
            "approval_status",
            "approved_at",
            "approved_by",
            "approval_note",
            "hidden_at",
            "hidden_user",
            "is_private",
        ])

        first_post = Post.objects.filter(id=discussion.first_post_id).first()
        if first_post is not None:
            first_post.approval_status = Post.APPROVAL_APPROVED
            first_post.approved_at = discussion.approved_at
            first_post.approved_by = admin_user
            first_post.approval_note = note
            first_post.hidden_at = None
            first_post.hidden_user = None
            first_post.is_private = discussion.is_private or refresh_runtime_model_private(first_post)
            first_post.save(update_fields=[
                "approval_status",
                "approved_at",
                "approved_by",
                "approval_note",
                "hidden_at",
                "hidden_user",
                "is_private",
            ])
        else:
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
            if first_post is not None:
                _apply_post_approved_extensions(
                    first_post,
                    context={
                        "content": first_post.content,
                        "actor": admin_user,
                        "discussion": discussion,
                        "is_first_post": True,
                        "previous_status": previous_status,
                    },
                )

        if not was_counted:
            dispatch_forum_event_after_commit(
                DiscussionApprovedEvent(
                    discussion_id=discussion.id,
                    admin_user_id=admin_user.id,
                    note=note,
                )
            )
        else:
            _apply_discussion_approved_extensions(
                get_runtime_discussion_lifecycle_service(),
                discussion=discussion,
                context={
                    "admin_user_id": admin_user.id,
                    "was_counted": was_counted,
                },
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
        refresh_runtime_model_private(discussion)
        discussion.save(update_fields=[
            "approval_status",
            "approved_at",
            "approved_by",
            "approval_note",
            "hidden_at",
            "hidden_user",
            "is_private",
        ])

        first_post = Post.objects.filter(id=discussion.first_post_id).first()
        if first_post is not None:
            first_post.approval_status = Post.APPROVAL_REJECTED
            first_post.approved_at = rejected_at
            first_post.approved_by = admin_user
            first_post.approval_note = note
            first_post.hidden_at = rejected_at
            first_post.hidden_user = admin_user
            first_post.is_private = discussion.is_private or refresh_runtime_model_private(first_post)
            first_post.save(update_fields=[
                "approval_status",
                "approved_at",
                "approved_by",
                "approval_note",
                "hidden_at",
                "hidden_user",
                "is_private",
            ])
        else:
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
        _apply_discussion_rejected_extensions(
            get_runtime_discussion_lifecycle_service(),
            discussion=discussion,
            context={
                "admin_user_id": admin_user.id,
                "previous_status": previous_status,
            },
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
        discussion_lifecycle = get_runtime_discussion_lifecycle_service()
        extension_states = _prepare_discussion_delete_extensions(
            discussion_lifecycle,
            discussion=discussion,
            user=user,
            context={"actor_user_id": user.id},
        )
        counted_discussion = (
            discussion.approval_status == Discussion.APPROVAL_APPROVED
            and discussion.hidden_at is None
        )
        approved_reply_counts = {}
        if counted_discussion:
            approved_reply_counts = approved_reply_counts_by_author_cb(discussion)

        deleted_posts = tuple(
            Post.objects.filter(discussion=discussion)
            .order_by("number")
            .values("id", "number", "approval_status", "hidden_at")
        )
        Post.objects.filter(discussion=discussion).delete()
        for deleted_post in deleted_posts:
            _apply_post_deleted_extensions(
                context={
                    "post_id": deleted_post["id"],
                    "discussion_id": discussion.id,
                    "actor": user,
                    "post_number": deleted_post["number"],
                    "is_first_post": deleted_post["number"] == 1,
                    "approval_status": deleted_post["approval_status"],
                    "was_hidden": deleted_post["hidden_at"] is not None,
                },
            )
        discussion.delete()

        _apply_discussion_delete_extensions(
            discussion_lifecycle,
            states=extension_states,
            context={"actor_user_id": user.id},
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
