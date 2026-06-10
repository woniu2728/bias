from __future__ import annotations

def discussion_service_provider() -> dict:
    from extensions.discussions.backend.models import Discussion, DiscussionUser
    from extensions.discussions.backend.services import DiscussionService

    return {
        "model": Discussion,
        "state_model": DiscussionUser,
        "approval_approved": Discussion.APPROVAL_APPROVED,
        "create": DiscussionService.create_discussion,
        "update": DiscussionService.update_discussion,
        "delete": DiscussionService.delete_discussion,
        "set_hidden_state": DiscussionService.set_hidden_state,
        "list": DiscussionService.get_discussion_list,
        "approve": DiscussionService.approve_discussion,
        "reject": DiscussionService.reject_discussion,
        "can_edit": DiscussionService.can_edit_discussion,
        "can_delete": DiscussionService.can_delete_discussion,
        "can_reply": DiscussionService.can_reply_discussion,
        "validate_replyable": _validate_replyable,
        "lock_for_post_number": _lock_for_post_number,
        "apply_counted_filter": _apply_counted_filter,
        "refresh_approved_stats": _refresh_approved_stats,
        "reply_notification_context": _reply_notification_context,
        "is_subscribed": _is_subscribed,
        "set_subscription": _set_subscription,
        "follow_if_enabled": _follow_if_enabled,
        "mark_read": _mark_read,
    }


def discussion_timeline_provider() -> dict:
    return {
        "create_from_builder": create_timeline_from_builder,
    }


def _validate_replyable(discussion_id: int, user, *, discussion=None):
    from django.core.exceptions import PermissionDenied
    from apps.core.extensions.runtime_access import evaluate_runtime_model_policy
    from extensions.discussions.backend.models import Discussion

    if discussion is None:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            raise ValueError("讨论不存在")

    if discussion.approval_status != Discussion.APPROVAL_APPROVED and not getattr(user, "is_staff", False):
        raise ValueError("讨论正在审核中，暂时无法回复")

    if discussion.is_locked and not getattr(user, "is_staff", False):
        raise ValueError("讨论已锁定，无法回复")

    if evaluate_runtime_model_policy(
        "reply",
        user=user,
        model=discussion,
        default=True,
        discussion=discussion,
    ) is False:
        raise PermissionDenied("没有权限回复此讨论")
    return discussion


def _lock_for_post_number(discussion_id: int):
    from extensions.discussions.backend.models import Discussion

    return Discussion.objects.select_for_update().get(id=discussion_id)


def _apply_counted_filter(queryset, *, prefix: str = ""):
    from extensions.discussions.backend.models import Discussion

    normalized_prefix = str(prefix or "").strip()
    field_prefix = f"{normalized_prefix}__" if normalized_prefix else ""
    return queryset.filter(
        **{
            f"{field_prefix}hidden_at__isnull": True,
            f"{field_prefix}approval_status": Discussion.APPROVAL_APPROVED,
        }
    )


def _refresh_approved_stats(discussion, *, discussion_counted_post_types):
    from apps.core.extensions.runtime_access import get_runtime_approved_discussion_post_stats

    stats = get_runtime_approved_discussion_post_stats(
        discussion,
        discussion_counted_post_types=discussion_counted_post_types,
    )
    discussion.comment_count = int(stats.get("comment_count") or 0)
    discussion.last_post_id = stats.get("last_post_id")
    discussion.last_post_number = stats.get("last_post_number")
    discussion.last_posted_at = stats.get("last_posted_at")
    discussion.last_posted_user = stats.get("last_posted_user")

    discussion.save(update_fields=[
        "comment_count",
        "last_post_id",
        "last_post_number",
        "last_posted_at",
        "last_posted_user",
    ])
    return discussion


def _reply_notification_context(discussion_id: int, post_id: int, from_user):
    from apps.core.extensions.runtime_access import get_runtime_post_number
    from extensions.discussions.backend.models import Discussion, DiscussionUser

    try:
        discussion = Discussion.objects.select_related("user").get(id=discussion_id)
    except Discussion.DoesNotExist:
        return None
    post_number = get_runtime_post_number(post_id)
    if post_number is None:
        return None

    author = discussion.user
    excluded_user_ids = {getattr(from_user, "id", None), getattr(author, "id", None)}
    excluded_user_ids = {int(item) for item in excluded_user_ids if item}
    subscribers = [
        state.user
        for state in DiscussionUser.objects.filter(
            discussion_id=discussion_id,
            is_subscribed=True,
        ).select_related("user")
        if state.user_id not in excluded_user_ids
    ]

    return {
        "discussion": discussion,
        "discussion_author": author,
        "subscribers": subscribers,
        "payload": {
            "discussion_id": discussion_id,
            "discussion_title": discussion.title,
            "post_id": post_id,
            "post_number": post_number,
        },
    }


def _is_subscribed(discussion, user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    from extensions.discussions.backend.models import DiscussionUser

    return DiscussionUser.objects.filter(
        discussion=discussion,
        user=user,
        is_subscribed=True,
    ).exists()


def _set_subscription(discussion_id: int, user, subscribed: bool) -> bool:
    from django.utils import timezone
    from apps.core.visibility import can_view_model_instance
    from django.core.exceptions import PermissionDenied
    from extensions.discussions.backend.models import Discussion, DiscussionUser

    discussion = Discussion.objects.get(id=discussion_id)
    if not can_view_model_instance(Discussion, discussion, user=user, ability="view"):
        raise PermissionDenied("没有权限查看此讨论")

    state, _ = DiscussionUser.objects.get_or_create(
        discussion=discussion,
        user=user,
        defaults={
            "last_read_at": timezone.now(),
            "last_read_post_number": discussion.last_post_number or 0,
        },
    )
    if state.is_subscribed == subscribed:
        return False
    state.is_subscribed = subscribed
    state.save(update_fields=["is_subscribed"])
    return True


def _follow_if_enabled(
    *,
    discussion_id: int,
    user_id: int,
    last_read_post_number: int | None = None,
) -> bool:
    from django.utils import timezone
    from extensions.discussions.backend.models import DiscussionUser

    defaults = {"is_subscribed": True}
    if last_read_post_number:
        defaults["last_read_at"] = timezone.now()
        defaults["last_read_post_number"] = last_read_post_number

    DiscussionUser.objects.update_or_create(
        discussion_id=discussion_id,
        user_id=user_id,
        defaults=defaults,
    )
    return True


def _mark_read(
    *,
    discussion_id: int,
    user,
    last_read_post_number: int,
    subscribed: bool | None = None,
) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    from django.utils import timezone
    from extensions.discussions.backend.models import DiscussionUser

    defaults = {
        "last_read_at": timezone.now(),
        "last_read_post_number": int(last_read_post_number or 0),
    }
    if subscribed is not None:
        defaults["is_subscribed"] = bool(subscribed)

    DiscussionUser.objects.update_or_create(
        discussion_id=int(discussion_id),
        user=user,
        defaults=defaults,
    )
    return True


def create_timeline_from_builder(
    event,
    builder: str,
    *,
    extra: dict | None = None,
    update_discussion_last_post: bool = True,
):
    from extensions.discussions.backend import timeline

    builders = {
        "discussion_renamed": timeline.build_discussion_renamed_content,
        "discussion_tagged": timeline.build_discussion_tagged_content,
        "discussion_locked": timeline.build_discussion_locked_content,
        "discussion_sticky": timeline.build_discussion_sticky_content,
        "discussion_hidden": timeline.build_discussion_hidden_content,
        "discussion_review": timeline.build_discussion_review_content,
        "discussion_resubmitted": timeline.build_discussion_resubmitted_content,
        "post_review": timeline.build_post_review_content,
        "post_resubmitted": timeline.build_post_resubmitted_content,
        "post_hidden": timeline.build_post_hidden_content,
    }
    build_content = builders.get(str(builder or "").strip())
    if build_content is None:
        raise RuntimeError(f"讨论时间线构建器未注册: {builder}")

    context = timeline.make_timeline_context(event, **dict(extra or {}))
    return timeline.create_timeline_from_builder(
        context,
        build_content,
        update_discussion_last_post=update_discussion_last_post,
    )

