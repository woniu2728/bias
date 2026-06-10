from apps.core.extensions import runtime_access
from apps.core.extensions.runtime_access import (
    get_runtime_discussion_model,
    get_runtime_user_by_id,
)
from apps.core.extensions.runtime_access import (
    get_runtime_post_model,
)


def handle_discussion_approved(event) -> None:
    discussion = _resolve_discussion_or_none(event.discussion_id, select_related=("user",))
    admin_user = _resolve_user_or_none(event.admin_user_id)
    if discussion is None or admin_user is None:
        return

    runtime_access.notify_runtime_notification("notify_discussion_approved", discussion, admin_user, note=event.note)
    runtime_access.create_runtime_timeline_from_builder(
        event,
        "discussion_review",
        extra={
            "actor_user_id": event.admin_user_id,
            "post_type": "discussionApproved",
            "previous_status": "pending",
        },
        update_discussion_last_post=False,
    )


def handle_discussion_rejected(event) -> None:
    discussion = _resolve_discussion_or_none(event.discussion_id, select_related=("user",))
    admin_user = _resolve_user_or_none(event.admin_user_id)
    if discussion is None or admin_user is None:
        return

    runtime_access.notify_runtime_notification("notify_discussion_rejected", discussion, admin_user, note=event.note)
    runtime_access.create_runtime_timeline_from_builder(
        event,
        "discussion_review",
        extra={
            "actor_user_id": event.admin_user_id,
            "post_type": "discussionRejected",
        },
        update_discussion_last_post=False,
    )


def handle_discussion_resubmitted(event) -> None:
    runtime_access.create_runtime_timeline_from_builder(
        event,
        "discussion_resubmitted",
        extra={
            "post_type": "discussionResubmitted",
        },
        update_discussion_last_post=False,
    )


def handle_post_approved(event) -> None:
    post = _resolve_post_or_none(event.post_id, select_related=("user", "discussion"))
    admin_user = _resolve_user_or_none(event.admin_user_id)
    if post is None or admin_user is None:
        return

    runtime_access.notify_runtime_notification("notify_post_approved", post, admin_user, note=event.note)
    runtime_access.create_runtime_timeline_from_builder(
        event,
        "post_review",
        extra={
            "actor_user_id": event.admin_user_id,
            "post_type": "postApproved",
            "post_number": getattr(post, "number", None),
        },
        update_discussion_last_post=False,
    )


def handle_post_rejected(event) -> None:
    post = _resolve_post_or_none(event.post_id, select_related=("discussion", "user"))
    admin_user = _resolve_user_or_none(event.admin_user_id)
    if post is None or admin_user is None:
        return

    runtime_access.notify_runtime_notification("notify_post_rejected", post, admin_user, note=event.note)
    runtime_access.create_runtime_timeline_from_builder(
        event,
        "post_review",
        extra={
            "actor_user_id": event.admin_user_id,
            "post_type": "postRejected",
            "post_number": getattr(post, "number", None),
        },
        update_discussion_last_post=False,
    )


def handle_post_resubmitted(event) -> None:
    post = _resolve_post_or_none(event.post_id)
    if post is None:
        return

    runtime_access.create_runtime_timeline_from_builder(
        event,
        "post_resubmitted",
        extra={
            "post_type": "postResubmitted",
            "post_number": getattr(post, "number", None),
        },
        update_discussion_last_post=False,
    )


def _resolve_user_or_none(user_id: int):
    try:
        return get_runtime_user_by_id(user_id)
    except Exception:
        return None


def _resolve_discussion_or_none(discussion_id: int, *, select_related: tuple[str, ...] = ()):
    try:
        queryset = get_runtime_discussion_model().objects
        if select_related:
            queryset = queryset.select_related(*select_related)
        return queryset.get(id=discussion_id)
    except Exception:
        return None


def _resolve_post_or_none(post_id: int, *, select_related: tuple[str, ...] = ()):
    try:
        queryset = get_runtime_post_model().objects
        if select_related:
            queryset = queryset.select_related(*select_related)
        return queryset.get(id=post_id)
    except Exception:
        return None

