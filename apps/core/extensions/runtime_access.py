from __future__ import annotations

from typing import Any


def get_extension_host_service(key: str, default: Any = None) -> Any:
    from apps.core.extensions.bootstrap import get_extension_host

    host = get_extension_host()
    if host is None:
        return default
    return host.make(key, default)


def require_extension_host_service(key: str) -> Any:
    service = get_extension_host_service(key)
    if service is None:
        raise RuntimeError(f"扩展运行时服务未注册: {key}")
    return service


def _runtime_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"扩展运行时服务缺少方法: {name}")
    return method


def get_runtime_resource_registry():
    from apps.core.resource_registry import get_resource_registry

    return get_extension_host_service("resource.registry", get_resource_registry())


def get_runtime_model_service():
    return get_extension_host_service("models")


def get_runtime_model_url_service():
    return get_extension_host_service("model.urls")


def generate_runtime_model_slug(model: Any, source: Any, **kwargs) -> str | None:
    service = get_runtime_model_url_service()
    if service is None:
        return None
    try:
        return service.generate_slug(model, source, **kwargs)
    except KeyError:
        return None


def get_runtime_model_relation(model: Any, name: str):
    service = get_runtime_model_service()
    if service is None or not hasattr(service, "get_relation"):
        return None
    return service.get_relation(model, name)


def resolve_runtime_model_relation(instance: Any, name: str, *, model: Any | None = None, default: Any = None):
    service = get_runtime_model_service()
    if service is None or instance is None:
        return default
    if hasattr(service, "resolve_relation"):
        resolved = service.resolve_relation(model or instance.__class__, name, instance)
        return default if resolved is None else resolved
    return default


def apply_runtime_model_visibility(model: Any, queryset, context: dict | None = None):
    model_service = get_runtime_model_service()
    if model_service is None:
        return queryset
    return model_service.apply_visibility(model, queryset, context or {})


def has_runtime_model_visibility(model: Any, *, ability: str | None = None) -> bool:
    model_service = get_runtime_model_service()
    if model_service is None:
        return False
    if hasattr(model_service, "has_visibility"):
        return bool(model_service.has_visibility(model, ability=ability))
    try:
        definitions = model_service.get_visibility()
    except Exception:
        return False
    requested_ability = str(ability or "view")
    return any(
        _model_matches(definition.model, model)
        and str(definition.ability or "*") in {"*", requested_ability}
        for definition in definitions
    )


def is_runtime_model_private(instance: Any, *, model: Any | None = None, default: bool | None = None) -> bool:
    model_service = get_runtime_model_service()
    fallback = bool(False if default is None else default)
    if model_service is None:
        return fallback
    model_class = model or instance.__class__
    return bool(model_service.is_private(model_class, instance, default=fallback))


def refresh_runtime_model_private(instance: Any, *, model: Any | None = None, save: bool = False) -> bool:
    if instance is None or not hasattr(instance, "is_private"):
        return bool(getattr(instance, "is_private", False))
    resolved = is_runtime_model_private(instance, model=model)
    if bool(getattr(instance, "is_private", False)) == resolved:
        return resolved
    instance.is_private = resolved
    if save and getattr(instance, "pk", None):
        instance.save(update_fields=["is_private"])
    return resolved


def can_view_runtime_model_private(model: Any, *, user=None, default: bool = False, **context) -> bool:
    return bool(evaluate_runtime_model_policy(
        "viewPrivate",
        user=user,
        model=model,
        default=default,
        **context,
    ))


def can_view_runtime_private_instance(instance: Any, *, user=None, model: Any | None = None, **context) -> bool:
    if not getattr(instance, "is_private", False):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return can_view_runtime_model_private(
        model or instance,
        user=user,
        instance=instance,
        **context,
    )


def evaluate_runtime_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_model_policy

    return evaluate_model_policy(
        ability,
        user=user,
        model=model,
        default=default,
        **context,
    )


def evaluate_runtime_extension_policy(key: str, *, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_extension_policy

    return evaluate_extension_policy(
        key,
        default=default,
        **context,
    )


def evaluate_runtime_query_model_policy(ability: str, *, user=None, model=None, default=None, **context):
    from apps.core.extensions.policy_runtime_service import evaluate_query_model_policy

    return evaluate_query_model_policy(
        ability,
        user=user,
        model=model,
        default=default,
        **context,
    )


def get_runtime_search_service():
    return get_extension_host_service("search")


def get_runtime_search_extension_service(default: Any = None):
    return get_extension_host_service("search.service", default)


def apply_runtime_discussion_search(queryset, query: str, *, user: Any = None):
    service = get_runtime_search_extension_service()
    if service is None:
        return queryset
    return _runtime_service_method(service, "apply_discussion_search")(queryset, query, user=user)


def get_runtime_notification_service(default: Any = None):
    return get_extension_host_service("notifications.service", default)


def require_runtime_notification_service():
    return require_extension_host_service("notifications.service")


def get_runtime_notification_model():
    service = require_runtime_notification_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("notifications.service 未提供通知模型")
    return model


def notify_runtime_notification(method_name: str, *args, **kwargs):
    service = get_runtime_notification_service()
    if service is None:
        return None
    return _runtime_service_method(service, method_name)(*args, **kwargs)


def delete_runtime_discussion_reply_notifications_for_post(post_id: int) -> int:
    result = notify_runtime_notification("delete_discussion_reply_for_post", post_id)
    return int(result or 0)


def get_runtime_like_service(default: Any = None):
    return get_extension_host_service("likes.service", default)


def require_runtime_like_service():
    return require_extension_host_service("likes.service")


def like_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_runtime_service_method(require_runtime_like_service(), "like_post")(post_id, user))


def unlike_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_runtime_service_method(require_runtime_like_service(), "unlike_post")(post_id, user))


def can_runtime_like_post(post: Any, user: Any) -> bool:
    service = get_runtime_like_service()
    if service is None:
        return False
    return bool(_runtime_service_method(service, "can_like_post")(post, user))


def get_runtime_post_like_model():
    service = require_runtime_like_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("likes.service 未提供点赞模型")
    return model


def get_runtime_flag_service(default: Any = None):
    return get_extension_host_service("flags.service", default)


def require_runtime_flag_service():
    return require_extension_host_service("flags.service")


def report_runtime_post_flag(post_id: int, user: Any, reason: str, message: str = ""):
    return _runtime_service_method(require_runtime_flag_service(), "report_post")(
        post_id,
        user,
        reason,
        message,
    )


def list_runtime_post_flags(*, status: str | None = None, page: int = 1, limit: int = 20, user: Any | None = None):
    return _runtime_service_method(require_runtime_flag_service(), "get_flag_list")(
        status=status,
        page=page,
        limit=limit,
        user=user,
    )


def resolve_runtime_post_flag(flag_id: int, admin_user: Any, status: str, resolution_note: str = ""):
    return _runtime_service_method(require_runtime_flag_service(), "resolve_flag")(
        flag_id,
        admin_user,
        status,
        resolution_note,
    )


def resolve_runtime_post_flags(post_id: int, admin_user: Any, status: str, resolution_note: str = "") -> int:
    return int(_runtime_service_method(require_runtime_flag_service(), "resolve_post_flags")(
        post_id,
        admin_user,
        status,
        resolution_note,
    ) or 0)


def delete_runtime_post_flags(post_id: int, user: Any) -> int:
    return int(_runtime_service_method(require_runtime_flag_service(), "delete_post_flags")(
        post_id,
        user,
    ) or 0)


def get_runtime_post_flag_model():
    service = require_runtime_flag_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("flags.service 未提供举报模型")
    return model


def get_runtime_approval_service(default: Any = None):
    return get_extension_host_service("approval.service", default)


def require_runtime_approval_service():
    return require_extension_host_service("approval.service")


def list_runtime_approval_queue_items(*, content_type: str = "all") -> list[dict]:
    return list(_runtime_service_method(require_runtime_approval_service(), "list_queue")(
        content_type=content_type,
    ) or [])


def process_runtime_approval_item(*, content_type: str, content_id: int, action: str, actor, note: str = "") -> dict:
    return dict(_runtime_service_method(require_runtime_approval_service(), "process_item")(
        content_type=content_type,
        content_id=content_id,
        action=action,
        actor=actor,
        note=note,
    ) or {})


def bulk_process_runtime_approval_items(*, action: str, items, actor, note: str = "") -> list[dict]:
    return list(_runtime_service_method(require_runtime_approval_service(), "bulk_process")(
        action=action,
        items=items,
        actor=actor,
        note=note,
    ) or [])


def get_runtime_user_service(default: Any = None):
    return get_extension_host_service("users.service", default)


def require_runtime_user_service():
    return require_extension_host_service("users.service")


def ensure_runtime_user_not_suspended(user: Any, action_label: str = "") -> None:
    _runtime_service_method(require_runtime_user_service(), "ensure_not_suspended")(user, action_label)


def ensure_runtime_user_email_confirmed(user: Any, action_label: str = "") -> None:
    _runtime_service_method(require_runtime_user_service(), "ensure_email_confirmed")(user, action_label)


def ensure_runtime_forum_permission(user: Any, permission_names, message: str = "无权限") -> None:
    _runtime_service_method(require_runtime_user_service(), "ensure_forum_permission")(
        user,
        permission_names,
        message,
    )


def has_runtime_forum_permission(user: Any, permission_names) -> bool:
    from apps.core.forum_permissions import has_forum_permission

    return has_forum_permission(user, permission_names)


def requires_runtime_content_approval(user: Any, bypass_permission: str) -> bool:
    return bool(
        _runtime_service_method(require_runtime_user_service(), "requires_content_approval")(
            user,
            bypass_permission,
        )
    )


def get_runtime_user_preference(user: Any, key: str, fallback: Any = None) -> Any:
    service = require_runtime_user_service()
    try:
        return _runtime_service_method(service, "get_preference")(user, key, fallback=fallback)
    except RuntimeError:
        return fallback


def get_runtime_user_model():
    service = require_runtime_user_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("users.service 未提供用户模型")
    return model


def get_runtime_group_model():
    service = require_runtime_user_service()
    model = service.get("group_model") if isinstance(service, dict) else getattr(service, "group_model", None)
    if model is None:
        raise RuntimeError("users.service 未提供用户组模型")
    return model


def get_runtime_permission_model():
    service = require_runtime_user_service()
    model = service.get("permission_model") if isinstance(service, dict) else getattr(service, "permission_model", None)
    if model is None:
        raise RuntimeError("users.service 未提供权限模型")
    return model


def resolve_runtime_user_by_username(username: str):
    return _runtime_service_method(require_runtime_user_service(), "get_by_username")(username)


def get_runtime_user_by_id(user_id: int):
    return _runtime_service_method(require_runtime_user_service(), "get_by_id")(user_id)


def list_runtime_users_by_usernames(usernames) -> list[Any]:
    return list(_runtime_service_method(require_runtime_user_service(), "list_by_usernames")(usernames) or [])


def get_runtime_username_id_map(usernames) -> dict[str, int]:
    return dict(_runtime_service_method(require_runtime_user_service(), "username_id_map")(usernames) or {})


def serialize_runtime_users_by_ids(user_ids, *, limit: int = 50) -> list[dict]:
    service = require_runtime_user_service()
    try:
        serializer = _runtime_service_method(service, "serialize_many_by_ids")
    except RuntimeError:
        return []
    return list(serializer(list(user_ids or []), limit=int(limit or 50)) or [])


def serialize_runtime_user(user: Any, *, resource: str = "user_detail", context: dict | None = None) -> dict | None:
    if not user:
        return None
    return get_runtime_resource_registry().serialize(
        str(resource or "user_detail"),
        user,
        context or {},
    )


def increment_runtime_user_discussion_count(user_id: int, delta: int) -> int:
    return int(
        _runtime_service_method(require_runtime_user_service(), "increment_discussion_count")(
            user_id,
            delta,
        )
        or 0
    )


def increment_runtime_user_comment_count(user_id: int, delta: int) -> int:
    return int(
        _runtime_service_method(require_runtime_user_service(), "increment_comment_count")(
            user_id,
            delta,
        )
        or 0
    )


def apply_runtime_user_comment_count_deltas(deltas: dict | None) -> int:
    return int(
        _runtime_service_method(require_runtime_user_service(), "apply_comment_count_deltas")(
            dict(deltas or {}),
        )
        or 0
    )


def ensure_runtime_admin_user(*, username: str, email: str, password: str) -> dict:
    service = require_runtime_user_service()
    try:
        handler = _runtime_service_method(service, "ensure_admin")
    except RuntimeError as exc:
        raise RuntimeError("用户扩展尚未提供管理员账号管理能力") from exc
    return dict(handler(username=username, email=email, password=password) or {})


def get_runtime_discussion_service(default: Any = None):
    return get_extension_host_service("discussions.service", default)


def require_runtime_discussion_service():
    return require_extension_host_service("discussions.service")


def get_runtime_discussion_model():
    service = require_runtime_discussion_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("discussions.service 未提供讨论模型")
    return model


def get_runtime_discussion_state_model():
    service = require_runtime_discussion_service()
    model = service.get("state_model") if isinstance(service, dict) else getattr(service, "state_model", None)
    if model is None:
        raise RuntimeError("discussions.service 未提供讨论状态模型")
    return model


def get_runtime_discussion_approval_approved() -> str:
    service = require_runtime_discussion_service()
    value = service.get("approval_approved") if isinstance(service, dict) else getattr(service, "approval_approved", "")
    if not value:
        raise RuntimeError("discussions.service 未提供已审核状态常量")
    return str(value)


def is_runtime_discussion_not_found(exc: Exception) -> bool:
    try:
        return isinstance(exc, get_runtime_discussion_model().DoesNotExist)
    except Exception:
        return False


def approve_runtime_discussion(discussion: Any, admin_user: Any, note: str = ""):
    return _runtime_service_method(require_runtime_discussion_service(), "approve")(
        discussion,
        admin_user,
        note=note,
    )


def reject_runtime_discussion(discussion: Any, admin_user: Any, note: str = ""):
    return _runtime_service_method(require_runtime_discussion_service(), "reject")(
        discussion,
        admin_user,
        note=note,
    )


def create_runtime_discussion(*, title: str, content: str, user: Any, extension_payload: dict | None = None):
    return _runtime_service_method(require_runtime_discussion_service(), "create")(
        title=title,
        content=content,
        user=user,
        extension_payload=extension_payload,
    )


def update_runtime_discussion(discussion_id: int, user: Any, **kwargs):
    return _runtime_service_method(require_runtime_discussion_service(), "update")(
        discussion_id,
        user,
        **kwargs,
    )


def delete_runtime_discussion(discussion_id: int, user: Any) -> bool:
    return bool(_runtime_service_method(require_runtime_discussion_service(), "delete")(discussion_id, user))


def set_runtime_discussion_hidden_state(discussion: Any, user: Any, hidden: bool):
    return _runtime_service_method(require_runtime_discussion_service(), "set_hidden_state")(discussion, user, hidden)


def list_runtime_discussions(**kwargs):
    return _runtime_service_method(require_runtime_discussion_service(), "list")(**kwargs)


def validate_runtime_replyable_discussion(discussion_id: int, user: Any, *, discussion: Any = None):
    return _runtime_service_method(require_runtime_discussion_service(), "validate_replyable")(
        discussion_id,
        user,
        discussion=discussion,
    )


def lock_runtime_discussion_for_post_number(discussion_id: int):
    return _runtime_service_method(require_runtime_discussion_service(), "lock_for_post_number")(discussion_id)


def apply_runtime_counted_discussion_filter(queryset, *, prefix: str = ""):
    return _runtime_service_method(require_runtime_discussion_service(), "apply_counted_filter")(
        queryset,
        prefix=prefix,
    )


def refresh_runtime_discussion_approved_stats(
    discussion: Any,
    *,
    discussion_counted_post_types,
) -> Any:
    return _runtime_service_method(require_runtime_discussion_service(), "refresh_approved_stats")(
        discussion,
        discussion_counted_post_types=discussion_counted_post_types,
    )


def get_runtime_discussion_subscription_state(discussion: Any, user: Any) -> bool:
    return bool(_runtime_service_method(require_runtime_discussion_service(), "is_subscribed")(discussion, user))


def set_runtime_discussion_subscription_state(discussion_id: int, user: Any, subscribed: bool) -> bool:
    return bool(
        _runtime_service_method(require_runtime_discussion_service(), "set_subscription")(
            discussion_id,
            user,
            subscribed,
        )
    )


def follow_runtime_discussion(
    *,
    discussion_id: int,
    user_id: int,
    last_read_post_number: int | None = None,
) -> bool:
    return bool(
        _runtime_service_method(require_runtime_discussion_service(), "follow_if_enabled")(
            discussion_id=discussion_id,
            user_id=user_id,
            last_read_post_number=last_read_post_number,
        )
    )


def mark_runtime_discussion_read(
    *,
    discussion_id: int,
    user: Any,
    last_read_post_number: int,
    subscribed: bool | None = None,
) -> bool:
    return bool(
        _runtime_service_method(require_runtime_discussion_service(), "mark_read")(
            discussion_id=discussion_id,
            user=user,
            last_read_post_number=last_read_post_number,
            subscribed=subscribed,
        )
    )


def get_runtime_discussion_reply_notification_context(discussion_id: int, post_id: int, from_user: Any):
    return _runtime_service_method(require_runtime_discussion_service(), "reply_notification_context")(
        discussion_id,
        post_id,
        from_user,
    )


def get_runtime_post_service(default: Any = None):
    return get_extension_host_service("posts.service", default)


def require_runtime_post_service():
    return require_extension_host_service("posts.service")


def get_runtime_post_model():
    service = require_runtime_post_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("posts.service 未提供帖子模型")
    return model


def get_runtime_post_by_id(
    post_id: int,
    *,
    user: Any = None,
    preload=None,
    require_visible: bool = False,
    select_related: tuple[str, ...] = (),
):
    if require_visible and not select_related:
        return _runtime_service_method(require_runtime_post_service(), "get_by_id")(
            post_id,
            user,
            preload=preload,
        )
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
    return bool(_runtime_service_method(require_runtime_post_service(), "can_view")(post, user))


def approve_runtime_post(post: Any, admin_user: Any, note: str = ""):
    return _runtime_service_method(require_runtime_post_service(), "approve")(
        post,
        admin_user,
        note=note,
    )


def reject_runtime_post(post: Any, admin_user: Any, note: str = ""):
    return _runtime_service_method(require_runtime_post_service(), "reject")(
        post,
        admin_user,
        note=note,
    )


def get_runtime_post_approval_approved() -> str:
    service = require_runtime_post_service()
    value = service.get("approval_approved") if isinstance(service, dict) else getattr(service, "approval_approved", "")
    if not value:
        raise RuntimeError("posts.service 未提供已审核状态常量")
    return str(value)


def get_runtime_post_approval_pending() -> str:
    service = require_runtime_post_service()
    value = service.get("approval_pending") if isinstance(service, dict) else getattr(service, "approval_pending", "")
    if not value:
        raise RuntimeError("posts.service 未提供待审核状态常量")
    return str(value)


def get_runtime_post_approval_rejected() -> str:
    service = require_runtime_post_service()
    value = service.get("approval_rejected") if isinstance(service, dict) else getattr(service, "approval_rejected", "")
    if not value:
        raise RuntimeError("posts.service 未提供已拒绝状态常量")
    return str(value)


def create_runtime_post(*, discussion_id: int, content: str, user: Any, reply_to_post_id: int | None = None):
    return _runtime_service_method(require_runtime_post_service(), "create")(
        discussion_id=discussion_id,
        content=content,
        user=user,
        reply_to_post_id=reply_to_post_id,
    )


def update_runtime_post(post_id: int, user: Any, content: str):
    return _runtime_service_method(require_runtime_post_service(), "update")(
        post_id,
        user,
        content,
    )


def delete_runtime_post(post_id: int, user: Any) -> bool:
    return bool(_runtime_service_method(require_runtime_post_service(), "delete")(post_id, user))


def set_runtime_post_hidden_state(post: Any, user: Any, hidden: bool):
    return _runtime_service_method(require_runtime_post_service(), "set_hidden_state")(post, user, hidden)


def create_runtime_first_post(**kwargs):
    return _runtime_service_method(require_runtime_post_service(), "create_first_post")(**kwargs)


def get_runtime_first_post(discussion: Any):
    return _runtime_service_method(require_runtime_post_service(), "get_first_post")(discussion)


def update_runtime_first_post_content(discussion: Any, *, content: str, content_html: str, editor: Any):
    return _runtime_service_method(require_runtime_post_service(), "update_first_post_content")(
        discussion,
        content=content,
        content_html=content_html,
        editor=editor,
    )


def resubmit_runtime_first_post(discussion: Any):
    return _runtime_service_method(require_runtime_post_service(), "resubmit_first_post")(discussion)


def approve_runtime_first_post(discussion: Any, *, approved_at: Any, approved_by: Any, note: str = ""):
    return _runtime_service_method(require_runtime_post_service(), "approve_first_post")(
        discussion,
        approved_at=approved_at,
        approved_by=approved_by,
        note=note,
    )


def reject_runtime_first_post(discussion: Any, *, rejected_at: Any, rejected_by: Any, note: str = ""):
    return _runtime_service_method(require_runtime_post_service(), "reject_first_post")(
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
    return dict(
        _runtime_service_method(require_runtime_post_service(), "approved_reply_counts_by_author")(
            discussion,
            user_counted_post_types=user_counted_post_types,
        )
        or {}
    )


def get_runtime_approved_discussion_post_stats(
    discussion: Any,
    *,
    discussion_counted_post_types,
) -> dict:
    return dict(
        _runtime_service_method(require_runtime_post_service(), "approved_discussion_stats")(
            discussion,
            discussion_counted_post_types=discussion_counted_post_types,
        )
        or {}
    )


def delete_runtime_discussion_posts(discussion: Any) -> tuple[dict, ...]:
    return tuple(
        _runtime_service_method(require_runtime_post_service(), "delete_discussion_posts")(discussion)
        or ()
    )


def is_runtime_post_not_found(exc: Exception) -> bool:
    try:
        return isinstance(exc, get_runtime_post_model().DoesNotExist)
    except Exception:
        return False


def serialize_runtime_post(post: Any, user: Any = None, **kwargs) -> dict:
    return _runtime_service_method(require_runtime_post_service(), "serialize")(post, user=user, **kwargs)


def serialize_runtime_post_by_id(post_id: int, user: Any = None, **kwargs) -> dict | None:
    return _runtime_service_method(require_runtime_post_service(), "serialize_by_id")(post_id, user=user, **kwargs)


def create_runtime_post_event(**kwargs):
    return _runtime_service_method(require_runtime_post_service(), "create_event_post")(**kwargs)


def get_runtime_post_reply_notification_context(reply_to_post_id: int, post_id: int, from_user: Any):
    return _runtime_service_method(require_runtime_post_service(), "reply_notification_context")(
        reply_to_post_id,
        post_id,
        from_user,
    )


def get_runtime_post_notification_context(post_id: int):
    return _runtime_service_method(require_runtime_post_service(), "notification_context")(post_id)


def get_runtime_post_number(post_id: int):
    return _runtime_service_method(require_runtime_post_service(), "get_number")(post_id)


def get_runtime_tag_service(default: Any = None):
    return get_extension_host_service("tags.service", default)


def require_runtime_tag_service():
    return require_extension_host_service("tags.service")


def get_runtime_tag_model():
    service = require_runtime_tag_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("tags.service 未提供标签模型")
    return model


def get_runtime_discussion_tag_model():
    service = require_runtime_tag_service()
    model = service.get("relationship_model") if isinstance(service, dict) else getattr(service, "relationship_model", None)
    if model is None:
        raise RuntimeError("tags.service 未提供讨论标签关系模型")
    return model


def get_runtime_tag_summaries_by_slugs(slugs) -> dict[str, dict]:
    service = get_runtime_tag_service()
    if service is None:
        return {}
    return dict(_runtime_service_method(service, "summaries_by_slugs")(slugs) or {})


def runtime_tag_method(name: str):
    return _runtime_service_method(require_runtime_tag_service(), name)


def get_runtime_tag_scope_label(scope: str) -> str:
    return str(runtime_tag_method("get_scope_label")(scope))


def validate_runtime_tag_parent_assignment(tag: Any, parent: Any) -> None:
    runtime_tag_method("validate_parent_assignment")(tag, parent)


def validate_runtime_tag_scope_configuration(view_scope: str, start_discussion_scope: str, reply_scope: str):
    return runtime_tag_method("validate_scope_configuration")(view_scope, start_discussion_scope, reply_scope)


def create_runtime_tag(**kwargs):
    return runtime_tag_method("create_tag")(**kwargs)


def move_runtime_tag(*, tag_id: int, direction: str, user: Any) -> bool:
    return bool(runtime_tag_method("move_tag")(tag_id, direction, user))


def delete_runtime_tag(tag_id: int, user: Any) -> bool:
    return bool(runtime_tag_method("delete_tag")(tag_id, user))


def dispatch_runtime_tag_stats_refresh(tag_ids=None) -> dict:
    return dict(runtime_tag_method("dispatch_refresh_tag_stats")(tag_ids) or {})


def filter_runtime_tags_for_user(queryset, user: Any, *, action: str = "view"):
    return runtime_tag_method("filter_tags_for_user")(queryset, user, action=action)


def can_runtime_view_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_view_tag")(tag, user))


def can_runtime_start_discussion_in_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_start_discussion_in_tag")(tag, user))


def can_runtime_reply_in_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_reply_in_tag")(tag, user))


def refresh_runtime_discussion_tag_stats(discussion) -> None:
    runtime_tag_method("refresh_discussion_tag_stats")(discussion)


def refresh_runtime_tag_stats(tag_ids=None) -> None:
    runtime_tag_method("refresh_tag_stats")(tag_ids)


def ensure_can_start_discussion_in_runtime_tags(user: Any, tag_ids) -> list[Any]:
    return list(runtime_tag_method("ensure_can_start_discussion")(user, tag_ids))


def get_runtime_locale_service():
    return get_extension_host_service("locales")


def get_runtime_formatter_service():
    return get_extension_host_service("formatters")


def get_runtime_view_service():
    return get_extension_host_service("views")


def render_runtime_template(template_name: str, context: dict | None = None, *, request: Any = None) -> str:
    service = get_runtime_view_service()
    if service is None:
        raise RuntimeError("扩展视图服务尚未启动")
    return service.render(template_name, context or {}, request=request)


def get_runtime_discussion_lifecycle_service():
    return get_extension_host_service("discussion.lifecycle")


def get_runtime_post_lifecycle_service():
    return get_extension_host_service("post.lifecycle")


def get_runtime_post_event_data_service():
    return get_extension_host_service("post.events")


def get_runtime_timeline_service():
    return require_extension_host_service("discussions.timeline")


def create_runtime_timeline_from_builder(
    event: Any,
    builder: str,
    *,
    extra: dict | None = None,
    update_discussion_last_post: bool = True,
):
    return _runtime_service_method(get_runtime_timeline_service(), "create_from_builder")(
        event,
        builder,
        extra=dict(extra or {}),
        update_discussion_last_post=update_discussion_last_post,
    )


def broadcast_runtime_discussion_event(
    discussion_id: int,
    event_type: str,
    *,
    include_discussion: bool = False,
    include_post: bool = False,
    post_id: int | None = None,
    post_id_getter=None,
    extension_context: dict | None = None,
) -> None:
    broadcaster = get_extension_host_service("realtime.discussion_broadcaster")
    if not callable(broadcaster):
        raise RuntimeError("扩展运行时服务未注册: realtime.discussion_broadcaster")
    return broadcaster(
        discussion_id,
        event_type,
        include_discussion=include_discussion,
        include_post=include_post,
        post_id=post_id,
        post_id_getter=post_id_getter,
        extension_context=extension_context,
    )


def _model_matches(registered_model: Any, model: Any) -> bool:
    from apps.core.extensions.model_references import model_matches

    return model_matches(registered_model, model)
