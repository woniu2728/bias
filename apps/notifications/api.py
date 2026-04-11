"""
通知系统API端点
"""
from typing import Optional
from ninja import Router
from django.shortcuts import get_object_or_404

from apps.notifications.models import Notification
from apps.notifications.schemas import (
    NotificationFilterSchema,
    NotificationOutSchema,
    NotificationListSchema,
    NotificationStatsSchema,
)
from apps.notifications.services import NotificationService
from apps.core.auth import AuthBearer

router = Router()


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
    notifications, total, unread_count = NotificationService.get_notification_list(
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
        "data": notifications,
    }


@router.get("/notifications/stats", response=NotificationStatsSchema, auth=AuthBearer(), tags=["Notifications"])
def get_notification_stats(request):
    """
    获取通知统计

    需要认证
    """
    stats = NotificationService.get_stats(request.auth)
    return stats


@router.get("/notifications/{notification_id}", response=NotificationOutSchema, auth=AuthBearer(), tags=["Notifications"])
def get_notification(request, notification_id: int):
    """
    获取通知详情

    需要认证
    """
    notification = NotificationService.get_notification_by_id(notification_id, request.auth)

    if not notification:
        return router.create_response(
            request,
            {"error": "通知不存在"},
            status=404
        )

    return notification


@router.post("/notifications/{notification_id}/read", auth=AuthBearer(), tags=["Notifications"])
def mark_notification_as_read(request, notification_id: int):
    """
    标记通知为已读

    需要认证
    """
    success = NotificationService.mark_as_read(notification_id, request.auth)

    if not success:
        return router.create_response(
            request,
            {"error": "通知不存在"},
            status=404
        )

    return {"message": "已标记为已读"}


@router.post("/notifications/read-all", auth=AuthBearer(), tags=["Notifications"])
def mark_all_as_read(request):
    """
    标记所有通知为已读

    需要认证
    """
    count = NotificationService.mark_all_as_read(request.auth)

    return {"message": f"已标记{count}条通知为已读", "count": count}


@router.delete("/notifications/{notification_id}", auth=AuthBearer(), tags=["Notifications"])
def delete_notification(request, notification_id: int):
    """
    删除通知

    需要认证
    """
    success = NotificationService.delete_notification(notification_id, request.auth)

    if not success:
        return router.create_response(
            request,
            {"error": "通知不存在"},
            status=404
        )

    return {"message": "通知已删除"}


@router.delete("/notifications/read", auth=AuthBearer(), tags=["Notifications"])
def delete_all_read(request):
    """
    删除所有已读通知

    需要认证
    """
    count = NotificationService.delete_all_read(request.auth)

    return {"message": f"已删除{count}条已读通知", "count": count}
