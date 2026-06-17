from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    RuntimeServiceProxy,
    get_extension_host_service,
    require_extension_host_service,
    runtime_service_method,
    runtime_service_value,
)

_post_service = RuntimeServiceProxy("posts.service")


def get_runtime_post_service(default: Any = None):
    return get_extension_host_service("posts.service", default)


def require_runtime_post_service():
    return require_extension_host_service("posts.service")


def get_runtime_post_model():
    return _post_service.value("model", required_message="posts.service 未提供帖子模型")


def get_runtime_post_by_id(
    post_id: int,
    *,
    user: Any = None,
    preload=None,
    require_visible: bool = False,
    select_related: tuple[str, ...] = (),
):
    if require_visible and not select_related:
        return _post_service.get_by_id(post_id, user, preload=preload)
    model = get_runtime_post_model()
    queryset = model.objects
    if select_related:
        queryset = queryset.select_related(*select_related)
    post = queryset.get(id=post_id)
    if require_visible and not can_runtime_view_post(post, user):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("没有权限查看此帖子")
    return post


def can_runtime_view_post(post: Any, user: Any = None) -> bool:
    return bool(_post_service.can_view(post, user))


def approve_runtime_post(post: Any, admin_user: Any, note: str = ""):
    return _post_service.approve(post, admin_user, note=note)


def reject_runtime_post(post: Any, admin_user: Any, note: str = ""):
    return _post_service.reject(post, admin_user, note=note)


def get_runtime_post_approval_approved() -> str:
    value = _post_service.value("approval_approved", "")
    if not value:
        raise RuntimeError("posts.service 未提供已审核状态常量")
    return str(value)


def get_runtime_post_approval_pending() -> str:
    value = _post_service.value("approval_pending", "")
    if not value:
        raise RuntimeError("posts.service 未提供待审核状态常量")
    return str(value)


def get_runtime_post_approval_rejected() -> str:
    value = _post_service.value("approval_rejected", "")
    if not value:
        raise RuntimeError("posts.service 未提供已拒绝状态常量")
    return str(value)


def create_runtime_post(*, discussion_id: int, content: str, user: Any, reply_to_post_id: int | None = None):
    return _post_service.create(
        discussion_id=discussion_id,
        content=content,
        user=user,
        reply_to_post_id=reply_to_post_id,
    )


def update_runtime_post(post_id: int, user: Any, content: str):
    return _post_service.update(post_id, user, content)


def delete_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_post_service.delete(post_id, user))


def set_runtime_post_hidden_state(post: Any, user: Any, hidden: bool):
    return _post_service.set_hidden_state(post, user, hidden)


def create_runtime_first_post(**kwargs):
    return _post_service.create_first_post(**kwargs)


def get_runtime_first_post(discussion: Any):
    return _post_service.get_first_post(discussion)


def resolve_runtime_post_content_html(post: Any) -> str:
    return str(_post_service.resolve_content_html(post) or "")


def update_runtime_first_post_content(discussion: Any, *, content: str, content_html: str, editor: Any):
    return _post_service.update_first_post_content(
        discussion,
        content=content,
        content_html=content_html,
        editor=editor,
    )


def resubmit_runtime_first_post(discussion: Any):
    return _post_service.resubmit_first_post(discussion)


def approve_runtime_first_post(discussion: Any, *, approved_at: Any, approved_by: Any, note: str = ""):
    return _post_service.approve_first_post(
        discussion,
        approved_at=approved_at,
        approved_by=approved_by,
        note=note,
    )


def reject_runtime_first_post(discussion: Any, *, rejected_at: Any, rejected_by: Any, note: str = ""):
    return _post_service.reject_first_post(
        discussion,
        rejected_at=rejected_at,
        rejected_by=rejected_by,
        note=note,
    )


def get_runtime_approved_reply_counts_by_author(
    discussion: Any,
    *,
    user_counted_post_types,
) -> dict:
    return dict(_post_service.approved_reply_counts_by_author(
        discussion,
        user_counted_post_types=user_counted_post_types,
    ) or {})


def get_runtime_approved_discussion_post_stats(
    discussion: Any,
    *,
    discussion_counted_post_types,
) -> dict:
    return dict(_post_service.approved_discussion_stats(
        discussion,
        discussion_counted_post_types=discussion_counted_post_types,
    ) or {})


def delete_runtime_discussion_posts(discussion: Any) -> tuple[dict, ...]:
    return tuple(_post_service.delete_discussion_posts(discussion) or ())


def is_runtime_post_not_found(exc: Exception) -> bool:
    try:
        return isinstance(exc, get_runtime_post_model().DoesNotExist)
    except Exception:
        return False


def serialize_runtime_post(post: Any, user: Any = None, **kwargs) -> dict:
    return _post_service.serialize(post, user=user, **kwargs)


def serialize_runtime_post_by_id(post_id: int, user: Any = None, **kwargs) -> dict | None:
    return _post_service.serialize_by_id(post_id, user=user, **kwargs)


def create_runtime_post_event(**kwargs):
    return _post_service.create_event_post(**kwargs)


def get_runtime_post_reply_notification_context(reply_to_post_id: int, post_id: int, from_user: Any):
    return _post_service.reply_notification_context(reply_to_post_id, post_id, from_user)


def get_runtime_post_notification_context(post_id: int):
    return _post_service.notification_context(post_id)


def get_runtime_post_number(post_id: int):
    return _post_service.get_number(post_id)
