from apps.core.extensions import (
    ApiRoutesExtender,
    EventListenersExtender,
    ExtensionEventListenerDefinition,
    FrontendExtender,
    LifecycleExtender,
    RealtimeExtender,
    SettingsExtender,
    WebSocketRoutesExtender,
    setting_field,
)
from apps.core.extensions.runtime import get_runtime_notification_service
from extensions.realtime.backend.admin_api import router as realtime_admin_router
from extensions.realtime.backend.consumers import (
    DiscussionConsumer,
    ForumRealtimeConsumer,
    NotificationConsumer,
    OnlineUsersConsumer,
)
from extensions.realtime.backend.websocket_service import WebSocketService


EXTENSION_ID = "realtime"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/realtime/frontend/admin/index.js",
            forum_entry="extensions/realtime/frontend/forum/index.js",
        ),
        ApiRoutesExtender(
            mounts=(("/admin", realtime_admin_router),),
            tags=("Admin",),
        ),
        SettingsExtender(fields=setting_definitions())
        .default("typing_enabled", True)
        .serialize_to_forum("realtime_typing_enabled", "typing_enabled", bool),
        EventListenersExtender(
            listeners=(
                ExtensionEventListenerDefinition(
                    event_type="extensions.notifications.backend.events.NotificationCreatedEvent",
                    handler=dispatch_notification_batch,
                    description="通知创建后通过 WebSocket 批量推送到前端。",
                ),
            ),
        ),
        RealtimeExtender().discussion_transport(
            "realtime.discussion.websocket",
            WebSocketService.broadcast_discussion_event,
            description="通过 WebSocket 广播讨论实时事件。",
        ),
        WebSocketRoutesExtender()
            .route(r"ws/notifications/$", "realtime.notifications", NotificationConsumer)
            .route(r"ws/online/$", "realtime.online", OnlineUsersConsumer)
            .route(r"ws/forum/$", "realtime.forum", ForumRealtimeConsumer)
            .route(r"ws/discussions/(?P<discussion_id>\d+)/$", "realtime.discussion", DiscussionConsumer),
        LifecycleExtender(),
    ]


def setting_definitions():
    return (
        setting_field({
            "key": "typing_enabled",
            "label": "回复输入提示",
            "type": "boolean",
            "default": True,
            "help_text": "关闭后，讨论详情页不再广播正在输入状态；其他实时通知与更新不受影响。",
            "order": 10,
        }),
    )


def dispatch_notification_batch(event) -> None:
    notification_ids = tuple(int(item) for item in event.notification_ids if item)
    if not notification_ids:
        return

    service = get_runtime_notification_service()
    if service is None:
        return
    loader = _runtime_method(service, "load_realtime_notifications")
    serializer = _runtime_method(service, "serialize_realtime_notification")
    if loader is None or serializer is None:
        return
    for notification in loader(list(notification_ids)) or []:
        try:
            WebSocketService.send_notification_to_user(
                user_id=notification.user_id,
                notification_data=serializer(notification),
            )
        except Exception:
            continue


def _runtime_method(service, name: str):
    if isinstance(service, dict):
        method = service.get(name)
    else:
        method = getattr(service, name, None)
    return method if callable(method) else None
