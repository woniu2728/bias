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
from apps.core.resource_registry import get_resource_registry

router = Router()
RESOURCE_REGISTRY = get_resource_registry()


def _serialize_notification(notification):
    payload = {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": notification.type,
        "subject_type": notification.subject_type,
        "subject_id": notification.subject_id,
        "data": notification.data,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }
    payload.update(RESOURCE_REGISTRY.serialize("notification", notification))
    return payload


@router.get("/notifications", response=NotificationListSchema, auth=AuthBearer(), tags=["Notifications"])
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
    notifications, total, unread_count, type_counts, unread_type_counts = NotificationService.get_notification_list(
        user=request.auth,
        is_read=is_read,
        type=type,
        page=page,
        limit=limit,
    )

    return {
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
        "type_counts": type_counts,
        "unread_type_counts": unread_type_counts,
        "data": [_serialize_notification(notification) for notification in notifications],
    }


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


@router.post("/notifications/{notification_id}/read", auth=AuthBearer(), tags=["Notifications"])
def mark_notification_as_read(request, notification_id: int):
    """
    标记通知为已读

    需要认证
    """
    success = NotificationService.mark_as_read(notification_id, request.auth)

    if not success:
        return JsonResponse({"error": "通知不存在"}, status=404)

    return {"message": "已标记为已读"}


@router.post("/notifications/read-all", auth=AuthBearer(), tags=["Notifications"])
def mark_all_as_read(request):
    """
    标记所有通知为已读

    需要认证
    """
    count = NotificationService.mark_all_as_read(request.auth)

    return {"message": f"已标记{count}条通知为已读", "count": count}


@router.get("/notifications/{notification_id}", response=NotificationOutSchema, auth=AuthBearer(), tags=["Notifications"])
def get_notification(request, notification_id: int):
    """
    获取通知详情

    需要认证
    """
    notification = NotificationService.get_notification_by_id(notification_id, request.auth)

    if not notification:
        return JsonResponse({"error": "通知不存在"}, status=404)

    return _serialize_notification(notification)


@router.delete("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def delete_notification(request, notification_id: int):
    """
    删除通知

    需要认证
    """
    success = NotificationService.delete_notification(notification_id, request.auth)

    if not success:
        return JsonResponse({"error": "通知不存在"}, status=404)

    return {"message": "通知已删除"}
