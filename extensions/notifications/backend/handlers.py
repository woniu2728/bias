from __future__ import annotations

from typing import Optional

from apps.core.api_errors import api_error
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.resource_api import ResourceQueryOptions, parse_resource_query_options
from apps.core.services import PaginationService
from extensions.notifications.backend.services import NotificationService


def _get_resource_registry():
    return get_runtime_resource_registry()


def _normalize_notification_type(type_value: Optional[str]) -> Optional[str]:
    if type_value is None:
        return None
    normalized = type_value.strip()
    return normalized or None


def _serialize_notification(notification, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().serialize(
        "notification",
        notification,
        only=resource_options.fields,
        include=resource_options.includes,
    )


def _apply_notification_resource_preloads(queryset, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().apply_preload_plan(
        queryset,
        "notification",
        only=resource_options.fields,
        include=resource_options.includes,
    )


def _notification_query_value(context, key: str, default=None):
    return dict(context.get("query") or {}).get(key, default)


def _notification_bool_query_value(context, key: str):
    value = _notification_query_value(context, key)
    if value is None or isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _notification_int_query_value(context, key: str):
    value = _notification_query_value(context, key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _notification_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


def dispatch_notification_index(context):
    request = context["request"]
    page, limit = PaginationService.normalize(
        _notification_query_value(context, "page", 1),
        _notification_query_value(context, "limit", 20),
    )
    resource_options = parse_resource_query_options(request, "notification")
    notifications, total, unread_count, type_counts, unread_type_counts = NotificationService.get_notification_list(
        user=context["user"],
        is_read=_notification_bool_query_value(context, "is_read"),
        type=_normalize_notification_type(_notification_query_value(context, "type")),
        page=page,
        limit=limit,
        preload=lambda queryset: _apply_notification_resource_preloads(
            queryset,
            resource_options=resource_options,
        ),
    )

    return {
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
        "type_counts": type_counts,
        "unread_type_counts": unread_type_counts,
        "data": [
            _serialize_notification(notification, resource_options=resource_options)
            for notification in notifications
        ],
    }


def dispatch_notification_stats(context):
    return NotificationService.get_stats(context["user"])


def dispatch_notification_delete_all_read(context):
    count = NotificationService.delete_all_read(context["user"])
    return {"message": f"已删除{count}条已读通知", "count": count}


def dispatch_notification_delete_filtered_read(context):
    normalized_type = _normalize_notification_type(_notification_query_value(context, "type"))
    discussion_id = _notification_int_query_value(context, "discussion_id")
    count, type_counts = NotificationService.delete_filtered_read(
        context["user"],
        type=normalized_type,
        discussion_id=discussion_id,
    )

    return {
        "message": f"已删除{count}条已读通知",
        "count": count,
        "type_counts": type_counts,
    }


def dispatch_notification_mark_read(context):
    success = NotificationService.mark_as_read(_notification_object_id(context), context["user"])
    if not success:
        return api_error("通知不存在", status=404)
    return {"message": "已标记为已读"}


def dispatch_notification_mark_all_read(context):
    count = NotificationService.mark_all_as_read(context["user"])
    return {"message": f"已标记{count}条通知为已读", "count": count}


def dispatch_notification_mark_filtered_read(context):
    normalized_type = _normalize_notification_type(_notification_query_value(context, "type"))
    discussion_id = _notification_int_query_value(context, "discussion_id")
    count, type_counts = NotificationService.mark_filtered_as_read(
        context["user"],
        type=normalized_type,
        discussion_id=discussion_id,
    )

    return {
        "message": f"已标记{count}条通知为已读",
        "count": count,
        "type_counts": type_counts,
    }


def dispatch_notification_show(context):
    request = context["request"]
    resource_options = parse_resource_query_options(request, "notification")
    notification = NotificationService.get_notification_by_id(
        _notification_object_id(context),
        context["user"],
        preload=lambda queryset: _apply_notification_resource_preloads(
            queryset,
            resource_options=resource_options,
        ),
    )

    if not notification:
        return api_error("通知不存在", status=404)

    return _serialize_notification(notification, resource_options=resource_options)


def dispatch_notification_delete(context):
    success = NotificationService.delete_notification(_notification_object_id(context), context["user"])
    if not success:
        return api_error("通知不存在", status=404)
    return {"message": "通知已删除"}
