from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    RuntimeServiceProxy,
    get_extension_host_service,
    require_extension_host_service,
)

_discussion = RuntimeServiceProxy("discussions.service")


def get_runtime_discussion_service(default: Any = None):
    return get_extension_host_service("discussions.service", default)


def require_runtime_discussion_service():
    return require_extension_host_service("discussions.service")


def get_runtime_discussion_model():
    return _discussion.value("model", required_message="discussions.service 未提供讨论模型")


def get_runtime_discussion_state_model():
    return _discussion.value("state_model", required_message="discussions.service 未提供讨论状态模型")


def get_runtime_discussion_approval_approved() -> str:
    value = _discussion.value("approval_approved", "")
    if not value:
        raise RuntimeError("discussions.service 未提供已审核状态常量")
    return str(value)


def is_runtime_discussion_not_found(exc: Exception) -> bool:
    try:
        return isinstance(exc, get_runtime_discussion_model().DoesNotExist)
    except Exception:
        return False


def approve_runtime_discussion(discussion: Any, admin_user: Any, note: str = ""):
    return _discussion.approve(discussion, admin_user, note=note)


def reject_runtime_discussion(discussion: Any, admin_user: Any, note: str = ""):
    return _discussion.reject(discussion, admin_user, note=note)


def create_runtime_discussion(*, title: str, content: str, user: Any, extension_payload: dict | None = None):
    return _discussion.create(title=title, content=content, user=user, extension_payload=extension_payload)


def update_runtime_discussion(discussion_id: int, user: Any, **kwargs):
    return _discussion.update(discussion_id, user, **kwargs)


def delete_runtime_discussion(discussion_id: int, user: Any) -> bool:
    return bool(_discussion.delete(discussion_id, user))


def set_runtime_discussion_hidden_state(discussion: Any, user: Any, hidden: bool):
    return _discussion.set_hidden_state(discussion, user, hidden)


def list_runtime_discussions(**kwargs):
    return _discussion.list(**kwargs)


def validate_runtime_replyable_discussion(discussion_id: int, user: Any, *, discussion: Any = None):
    return _discussion.validate_replyable(discussion_id, user, discussion=discussion)


def lock_runtime_discussion_for_post_number(discussion_id: int):
    return _discussion.lock_for_post_number(discussion_id)


def apply_runtime_counted_discussion_filter(queryset, *, prefix: str = ""):
    return _discussion.apply_counted_filter(queryset, prefix=prefix)


def refresh_runtime_discussion_approved_stats(
    discussion: Any,
    *,
    discussion_counted_post_types,
) -> Any:
    return _discussion.refresh_approved_stats(discussion, discussion_counted_post_types=discussion_counted_post_types)


def get_runtime_discussion_subscription_state(discussion: Any, user: Any) -> bool:
    return bool(_discussion.is_subscribed(discussion, user))


def set_runtime_discussion_subscription_state(discussion_id: int, user: Any, subscribed: bool) -> bool:
    return bool(_discussion.set_subscription(discussion_id, user, subscribed))


def follow_runtime_discussion(
    *,
    discussion_id: int,
    user_id: int,
    last_read_post_number: int | None = None,
) -> bool:
    return bool(_discussion.follow_if_enabled(
        discussion_id=discussion_id,
        user_id=user_id,
        last_read_post_number=last_read_post_number,
    ))


def mark_runtime_discussion_read(
    *,
    discussion_id: int,
    user: Any,
    last_read_post_number: int,
    subscribed: bool | None = None,
) -> bool:
    return bool(_discussion.mark_read(
        discussion_id=discussion_id,
        user=user,
        last_read_post_number=last_read_post_number,
        subscribed=subscribed,
    ))


def get_runtime_discussion_reply_notification_context(discussion_id: int, post_id: int, from_user: Any):
    return _discussion.reply_notification_context(discussion_id, post_id, from_user)
