"""
通知系统API端点
"""
from typing import Optional
from ninja import Router
from django.http import JsonResponse

from apps.notifications.schemas import (
    NotificationOutSchema,
    NotificationListSchema,
    NotificationStatsSchema,
)
from apps.notifications.services import NotificationService
from apps.core.auth import AuthBearer
from apps.core.resource_api import ResourceQueryOptions, parse_resource_query_options
from apps.core.resource_registry import get_resource_registry
from apps.core.services import PaginationService
from apps.core.api_errors import api_error

router = Router()
RESOURCE_REGISTRY = get_resource_registry()


def _normalize_notification_type(type_value: Optional[str]) -> Optional[str]:
    if type_value is None:
        return None
    normalized = type_value.strip()
    return normalized or None


def _serialize_notification(notification, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return RESOURCE_REGISTRY.serialize(
        "notification",
        notification,
        only=resource_options.fields,
    )


def _apply_notification_resource_preloads(queryset, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return RESOURCE_REGISTRY.apply_preload_plan(
        queryset,
        "notification",
        only=resource_options.fields,
    )


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
    page, limit = PaginationService.normalize(page, limit)
    resource_options = parse_resource_query_options(request, "notification")
    notifications, total, unread_count, type_counts, unread_type_counts = NotificationService.get_notification_list(
        user=request.auth,
        is_read=is_read,
        type=_normalize_notification_type(type),
        page=page,
        limit=limit,
        preload=lambda queryset: _apply_notification_resource_preloads(
            queryset,
            resource_options=resource_options,
        ),
    )

    response_payload = {
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
        "type_counts": type_counts,
        "unread_type_counts": unread_type_counts,
        "data": [_serialize_notification(notification, resource_options=resource_options) for notification in notifications],
    }
    return JsonResponse(response_payload)


@router.get("/notifications/stats", response=NotificationStatsSchema, auth=AuthBearer(), tags=["Notifications"])
def get_notification_stats(request):
    """
    获取通知统计

    需要认证
    """
    stats = NotificationService.get_stats(request.auth)
    return stats


@router.delete("/notifications/read/clear", auth=AuthBearer(), tags=["Notifications"])
def delete_all_read(request):
    """
    删除所有已读通知

    需要认证
    """
    count = NotificationService.delete_all_read(request.auth)

    return {"message": f"已删除{count}条已读通知", "count": count}


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
    normalized_type = _normalize_notification_type(type)
    count, type_counts = NotificationService.delete_filtered_read(
        request.auth,
        type=normalized_type,
        discussion_id=discussion_id,
    )

    return {
        "message": f"已删除{count}条已读通知",
        "count": count,
        "type_counts": type_counts,
    }


@router.post("/notifications/{notification_id}/read", auth=AuthBearer(), tags=["Notifications"])
def mark_notification_as_read(request, notification_id: int):
    """
    标记通知为已读

    需要认证
    """
    success = NotificationService.mark_as_read(notification_id, request.auth)

    if not success:
        return api_error("通知不存在", status=404)

    return {"message": "已标记为已读"}


@router.post("/notifications/read-all", auth=AuthBearer(), tags=["Notifications"])
def mark_all_as_read(request):
    """
    标记所有通知为已读

    需要认证
    """
    count = NotificationService.mark_all_as_read(request.auth)

    return {"message": f"已标记{count}条通知为已读", "count": count}


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
    normalized_type = _normalize_notification_type(type)
    count, type_counts = NotificationService.mark_filtered_as_read(
        request.auth,
        type=normalized_type,
        discussion_id=discussion_id,
    )

    return {
        "message": f"已标记{count}条通知为已读",
        "count": count,
        "type_counts": type_counts,
    }


@router.get("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def get_notification(request, notification_id: int):
    """
    获取通知详情

    需要认证
    """
    resource_options = parse_resource_query_options(request, "notification")
    notification = NotificationService.get_notification_by_id(
        notification_id,
        request.auth,
        preload=lambda queryset: _apply_notification_resource_preloads(
            queryset,
            resource_options=resource_options,
        ),
    )

    if not notification:
        return api_error("通知不存在", status=404)

    return JsonResponse(_serialize_notification(notification, resource_options=resource_options))


@router.delete("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def delete_notification(request, notification_id: int):
    """
    删除通知

    需要认证
    """
    success = NotificationService.delete_notification(notification_id, request.auth)

    if not success:
        return api_error("通知不存在", status=404)

    return {"message": "通知已删除"}
