"""
通知系统API端点
"""
from typing import Optional
from ninja import Router

from apps.notifications.schemas import (
    NotificationStatsSchema,
)
from apps.notifications.services import NotificationService
from apps.core.auth import AuthBearer
from apps.core.resource_api import ResourceQueryOptions, parse_resource_query_options
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.resource_dispatcher import dispatch_resource_endpoint
from apps.core.services import PaginationService
from apps.core.api_errors import api_error

router = Router()


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


def _dispatch_notification_index(context):
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
        "data": [_serialize_notification(notification, resource_options=resource_options) for notification in notifications],
    }


def _dispatch_notification_stats(context):
    return NotificationService.get_stats(context["user"])


def _dispatch_notification_delete_all_read(context):
    count = NotificationService.delete_all_read(context["user"])
    return {"message": f"已删除{count}条已读通知", "count": count}


def _dispatch_notification_delete_filtered_read(context):
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


def _dispatch_notification_mark_read(context):
    success = NotificationService.mark_as_read(_notification_object_id(context), context["user"])
    if not success:
        return api_error("通知不存在", status=404)
    return {"message": "已标记为已读"}


def _dispatch_notification_mark_all_read(context):
    count = NotificationService.mark_all_as_read(context["user"])
    return {"message": f"已标记{count}条通知为已读", "count": count}


def _dispatch_notification_mark_filtered_read(context):
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


def _dispatch_notification_show(context):
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


def _dispatch_notification_delete(context):
    success = NotificationService.delete_notification(_notification_object_id(context), context["user"])
    if not success:
        return api_error("通知不存在", status=404)
    return {"message": "通知已删除"}


@router.get("/notifications", auth=AuthBearer(), tags=["Notifications"])
def list_notifications(
    request,
    is_read: Optional[bool] = None,
    type: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
):
    """
    获取通知列表

    需要认证

    参数:
    - is_read: 是否已读（不传表示全部）
    - type: 通知类型
    - page: 页码
    - limit: 每页数量
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="index")


@router.get("/notifications/stats", response=NotificationStatsSchema, auth=AuthBearer(), tags=["Notifications"])
def get_notification_stats(request):
    """
    获取通知统计

    需要认证
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="stats")


@router.delete("/notifications/read/clear", auth=AuthBearer(), tags=["Notifications"])
def delete_all_read(request):
    """
    删除所有已读通知

    需要认证
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="clear-read")


@router.delete("/notifications/read/clear-filtered", auth=AuthBearer(), tags=["Notifications"])
def delete_filtered_read(
    request,
    type: Optional[str] = None,
    discussion_id: Optional[int] = None,
):
    """
    删除当前筛选范围内的已读通知

    需要认证
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="clear-filtered-read")


@router.post("/notifications/{notification_id}/read", auth=AuthBearer(), tags=["Notifications"])
def mark_notification_as_read(request, notification_id: int):
    """
    标记通知为已读

    需要认证
    """
    return dispatch_resource_endpoint(
        request,
        resource="notification",
        object_id=str(notification_id),
        endpoint="read",
    )


@router.post("/notifications/read-all", auth=AuthBearer(), tags=["Notifications"])
def mark_all_as_read(request):
    """
    标记所有通知为已读

    需要认证
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="read-all")


@router.post("/notifications/read-filtered", auth=AuthBearer(), tags=["Notifications"])
def mark_filtered_as_read(
    request,
    type: Optional[str] = None,
    discussion_id: Optional[int] = None,
):
    """
    标记当前筛选范围内的未读通知为已读

    需要认证
    """
    return dispatch_resource_endpoint(request, resource="notification", endpoint="read-filtered")


@router.get("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def get_notification(request, notification_id: int):
    """
    获取通知详情

    需要认证
    """
    return dispatch_resource_endpoint(
        request,
        resource="notification",
        object_id=str(notification_id),
        endpoint="show",
    )


@router.delete("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def delete_notification(request, notification_id: int):
    """
    删除通知

    需要认证
    """
    return dispatch_resource_endpoint(
        request,
        resource="notification",
        object_id=str(notification_id),
        endpoint="delete",
    )
