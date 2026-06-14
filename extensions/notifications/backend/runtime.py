from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime import (
    delete_runtime_discussion_reply_notifications_for_post,
    get_runtime_notification_model,
    get_runtime_notification_service,
    notify_runtime_notification,
)


def _runtime_service_method(service: Any, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    if not callable(method):
        raise RuntimeError(f"Notifications 扩展运行时服务缺少方法: {name}")
    return method


def notification_service_provider() -> dict:
    from extensions.notifications.backend.models import Notification
    from extensions.notifications.backend.services import NotificationService

    return {
        "model": Notification,
        "notify_discussion_reply": NotificationService.notify_discussion_reply,
        "notify_discussion_approved": NotificationService.notify_discussion_approved,
        "notify_discussion_rejected": NotificationService.notify_discussion_rejected,
        "notify_post_approved": NotificationService.notify_post_approved,
        "notify_post_rejected": NotificationService.notify_post_rejected,
        "notify_post_liked": NotificationService.notify_post_liked,
        "notify_user_mentioned": NotificationService.notify_user_mentioned,
        "dispatch_batch": dispatch_notification_batch,
        "send_batch": _send_notification_batch_now,
        "load_realtime_notifications": NotificationService.load_notifications_for_realtime,
        "serialize_realtime_notification": serialize_realtime_notification,
        "delete_discussion_reply_for_post": _delete_discussion_reply_for_post,
    }


def get_notification_service(default: Any = None):
    return get_runtime_notification_service(default)


def get_notification_model():
    return get_runtime_notification_model()


def notify(method_name: str, *args, **kwargs):
    return notify_runtime_notification(method_name, *args, **kwargs)


def dispatch_runtime_notification_batch(notification_ids) -> Any:
    return notify("dispatch_batch", list(notification_ids or ()))


def delete_discussion_reply_notifications_for_post(post_id: int) -> int:
    return delete_runtime_discussion_reply_notifications_for_post(post_id)


def dispatch_notification_batch(notification_ids):
    from apps.core.extensions.platform import QueueService
    from extensions.notifications.backend.tasks import dispatch_notification_batch as dispatch_task

    normalized_ids = [int(item) for item in notification_ids or () if item]
    if not normalized_ids:
        return None

    return QueueService.dispatch_celery_task(
        dispatch_task,
        normalized_ids,
        fallback=lambda: _send_notification_batch_now(normalized_ids),
    )


def _send_notification_batch_now(notification_ids):
    from extensions.notifications.backend.services import NotificationService

    return NotificationService.load_notifications_for_realtime(notification_ids or [])


def serialize_realtime_notification(notification) -> dict:
    from apps.core.extensions.runtime import serialize_runtime_user

    return {
        "id": notification.id,
        "type": notification.type,
        "from_user": serialize_runtime_user(
            getattr(notification, "from_user", None),
            resource="user_summary",
            context={},
        ),
        "data": notification.data,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


def _delete_discussion_reply_for_post(post_id: int) -> int:
    from extensions.notifications.backend.models import Notification
    from extensions.notifications.backend.services import NotificationService

    deleted_count, _ = Notification.objects.filter(
        type=NotificationService.TYPE_DISCUSSION_REPLY,
        data__post_id=post_id,
    ).delete()
    return deleted_count
