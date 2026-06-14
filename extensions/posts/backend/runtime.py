from __future__ import annotations

from typing import Any


def _runtime_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"Posts 扩展运行时服务缺少方法: {name}")
    return method


def post_service_provider() -> dict:
    from extensions.posts.backend import post_query_service
    from extensions.posts.backend.models import Post
    from extensions.posts.backend.services import PostService

    return {
        "model": Post,
        "approval_approved": Post.APPROVAL_APPROVED,
        "approval_pending": Post.APPROVAL_PENDING,
        "approval_rejected": Post.APPROVAL_REJECTED,
        "can_view": post_query_service.can_view_post,
        "apply_visibility": post_query_service.apply_visibility_filters,
        "build_visible_queryset": post_query_service.build_visible_post_queryset,
        "get_window": post_query_service.get_post_window,
        "get_page_for_near_post": post_query_service.get_page_for_near_post,
        "get_by_id": PostService.get_post_by_id,
        "create": PostService.create_post,
        "update": PostService.update_post,
        "delete": PostService.delete_post,
        "set_hidden_state": PostService.set_hidden_state,
        "approve": PostService.approve_post,
        "reject": PostService.reject_post,
        "can_edit": PostService.can_edit_post,
        "can_delete": PostService.can_delete_post,
        "create_event_post": _create_event_post,
        "create_first_post": _create_first_post,
        "get_first_post": _get_first_post,
        "resolve_content_html": PostService.resolve_content_html,
        "update_first_post_content": _update_first_post_content,
        "resubmit_first_post": _resubmit_first_post,
        "approve_first_post": _approve_first_post,
        "reject_first_post": _reject_first_post,
        "approved_reply_counts_by_author": _approved_reply_counts_by_author,
        "approved_discussion_stats": _approved_discussion_stats,
        "delete_discussion_posts": _delete_discussion_posts,
        "serialize": _serialize_post,
        "serialize_by_id": _serialize_post_by_id,
        "reply_notification_context": _reply_notification_context,
        "notification_context": _notification_context,
        "get_number": _get_post_number,
    }


def _create_event_post(
    *,
    discussion,
    actor,
    post_type: str,
    content: str,
    content_html: str = "",
    approved_at=None,
):
    from django.utils import timezone
    from extensions.posts.backend.models import Post
    from extensions.posts.backend.services import PostService

    locked_discussion = PostService._lock_discussion_for_post_number(discussion.id)
    return PostService._create_post_with_sequential_number(
        discussion=locked_discussion,
        user=actor,
        type=post_type,
        content=content,
        content_html=content_html,
        approval_status=Post.APPROVAL_APPROVED,
        approved_at=approved_at or timezone.now(),
        approved_by=actor,
    )


def _create_first_post(
    *,
    discussion,
    user,
    content: str,
    content_html: str,
    post_type: str,
    requires_approval: bool,
    approved_at=None,
    approved_by=None,
):
    from extensions.posts.backend.models import Post

    return Post.objects.create(
        discussion=discussion,
        number=1,
        user=user,
        content=content,
        content_html=content_html,
        type=post_type,
        approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
        approved_at=None if requires_approval else approved_at,
        approved_by=None if requires_approval else approved_by,
    )


def _get_first_post(discussion):
    from extensions.posts.backend.models import Post

    first_post_id = getattr(discussion, "first_post_id", None)
    if not first_post_id:
        return None
    return Post.objects.filter(id=first_post_id).first()


def _update_first_post_content(discussion, *, content: str, content_html: str, editor):
    from django.utils import timezone
    from extensions.posts.backend.models import Post

    first_post = Post.objects.get(id=discussion.first_post_id)
    first_post.content = content
    first_post.content_html = content_html
    first_post.edited_at = timezone.now()
    first_post.edited_user = editor
    first_post.save(update_fields=["content", "content_html", "edited_at", "edited_user"])
    return first_post


def _resubmit_first_post(discussion):
    from extensions.posts.backend.models import Post

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
    return first_post


def _approve_first_post(discussion, *, approved_at, approved_by, note: str = ""):
    from apps.core.extensions.runtime import refresh_runtime_model_private
    from extensions.posts.backend.models import Post

    first_post = Post.objects.filter(id=getattr(discussion, "first_post_id", None)).first()
    if first_post is None:
        return None
    first_post.approval_status = Post.APPROVAL_APPROVED
    first_post.approved_at = approved_at
    first_post.approved_by = approved_by
    first_post.approval_note = note
    first_post.hidden_at = None
    first_post.hidden_user = None
    first_post.is_private = bool(getattr(discussion, "is_private", False)) or refresh_runtime_model_private(first_post)
    first_post.save(update_fields=[
        "approval_status",
        "approved_at",
        "approved_by",
        "approval_note",
        "hidden_at",
        "hidden_user",
        "is_private",
    ])
    return first_post


def _reject_first_post(discussion, *, rejected_at, rejected_by, note: str = ""):
    from apps.core.extensions.runtime import refresh_runtime_model_private
    from extensions.posts.backend.models import Post

    first_post = Post.objects.filter(id=getattr(discussion, "first_post_id", None)).first()
    if first_post is None:
        return None
    first_post.approval_status = Post.APPROVAL_REJECTED
    first_post.approved_at = rejected_at
    first_post.approved_by = rejected_by
    first_post.approval_note = note
    first_post.hidden_at = rejected_at
    first_post.hidden_user = rejected_by
    first_post.is_private = bool(getattr(discussion, "is_private", False)) or refresh_runtime_model_private(first_post)
    first_post.save(update_fields=[
        "approval_status",
        "approved_at",
        "approved_by",
        "approval_note",
        "hidden_at",
        "hidden_user",
        "is_private",
    ])
    return first_post


def _approved_reply_counts_by_author(discussion, *, user_counted_post_types) -> dict:
    from django.db.models import Count
    from extensions.posts.backend.models import Post

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


def _approved_discussion_stats(discussion, *, discussion_counted_post_types) -> dict:
    from extensions.posts.backend.models import Post

    approved_posts = Post.objects.filter(
        discussion=discussion,
        type__in=discussion_counted_post_types,
        approval_status=Post.APPROVAL_APPROVED,
        hidden_at__isnull=True,
    ).order_by("number")

    approved_count = approved_posts.count()
    last_post = approved_posts.order_by("-number").select_related("user").first()
    if last_post is None:
        return {
            "comment_count": approved_count,
            "last_post_id": None,
            "last_post_number": None,
            "last_posted_at": None,
            "last_posted_user": None,
        }
    return {
        "comment_count": approved_count,
        "last_post_id": last_post.id,
        "last_post_number": last_post.number,
        "last_posted_at": last_post.created_at,
        "last_posted_user": last_post.user,
    }


def _delete_discussion_posts(discussion) -> tuple[dict, ...]:
    from extensions.posts.backend.models import Post

    deleted_posts = tuple(
        Post.objects.filter(discussion=discussion)
        .order_by("number")
        .values("id", "number", "approval_status", "hidden_at")
    )
    Post.objects.filter(discussion=discussion).delete()
    return deleted_posts


def _serialize_post(post, user=None, **kwargs):
    from extensions.posts.backend.handlers import serialize_post

    return serialize_post(post, user, **kwargs)


def _serialize_post_by_id(post_id: int, user=None, **kwargs):
    from extensions.posts.backend.handlers import apply_post_resource_preloads, serialize_post
    from extensions.posts.backend.models import Post

    post = (
        apply_post_resource_preloads(
            Post.objects.select_related("discussion"),
            user=user,
        )
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return None
    return serialize_post(post, user=user, **kwargs)


def _reply_notification_context(reply_to_post_id: int, post_id: int, from_user):
    from extensions.posts.backend.models import Post

    try:
        reply_to_post = Post.objects.select_related("user", "discussion__user").get(id=reply_to_post_id)
        post = Post.objects.only("id", "number").get(id=post_id)
    except Post.DoesNotExist:
        return None

    recipient = reply_to_post.user
    if (
        recipient is None
        or recipient.id == getattr(from_user, "id", None)
        or recipient.id == getattr(reply_to_post.discussion.user, "id", None)
    ):
        return None

    return {
        "recipient": recipient,
        "payload": {
            "post_id": post_id,
            "post_number": post.number,
            "discussion_id": reply_to_post.discussion_id,
            "discussion_title": reply_to_post.discussion.title,
            "reply_to_post_id": reply_to_post_id,
            "reply_to_post_number": reply_to_post.number,
        },
    }


def _notification_context(post_id: int):
    from extensions.posts.backend.models import Post

    try:
        post = Post.objects.select_related("user", "discussion").get(id=post_id)
    except Post.DoesNotExist:
        return None

    return {
        "post": post,
        "author": post.user,
        "payload": {
            "post_id": post_id,
            "post_number": post.number,
            "discussion_id": post.discussion_id,
            "discussion_title": post.discussion.title if post.discussion else "",
        },
    }


def _get_post_number(post_id: int):
    from extensions.posts.backend.models import Post

    return Post.objects.filter(id=post_id).values_list("number", flat=True).first()
