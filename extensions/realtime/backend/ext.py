from apps.core.extensions import EventListenersExtender, LifecycleExtender
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import NotificationCreatedEvent


EXTENSION_ID = "realtime"


def extend():
    return [
        EventListenersExtender(
            listeners=(
                ExtensionEventListenerDefinition(
                    event_type=NotificationCreatedEvent,
                    handler=dispatch_notification_batch,
                    description="通知创建后通过 WebSocket 批量推送到前端。",
                ),
            ),
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def dispatch_notification_batch(event: NotificationCreatedEvent) -> None:
    notification_ids = tuple(int(item) for item in event.notification_ids if item)
    if not notification_ids:
        return

    from apps.core.queue_service import QueueService
    from extensions.notifications.backend.services import NotificationService
    from extensions.notifications.backend.tasks import dispatch_notification_batch as dispatch_task

    QueueService.dispatch_celery_task(
        dispatch_task,
        list(notification_ids),
        fallback=lambda: NotificationService._send_notifications_batch(list(notification_ids)),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Realtime 扩展已安装。",
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Realtime 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Realtime 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Realtime 扩展已卸载。",
    }
