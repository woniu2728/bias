from apps.core.extensions import EventListenersExtender, LifecycleExtender, NotificationsExtender, ResourceExtender
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import (
    PostCreatedEvent,
    PostLikedEvent,
    UserSuspendedEvent,
    UserUnsuspendedEvent,
)
from apps.core.forum_registry_types import NotificationTypeDefinition, UserPreferenceDefinition
from apps.core.resource_registry import ResourceEndpointDefinition
from apps.notifications.api import (
    _dispatch_notification_delete,
    _dispatch_notification_delete_all_read,
    _dispatch_notification_delete_filtered_read,
    _dispatch_notification_index,
    _dispatch_notification_mark_all_read,
    _dispatch_notification_mark_filtered_read,
    _dispatch_notification_mark_read,
    _dispatch_notification_show,
    _dispatch_notification_stats,
)
from extensions.notifications.backend.listeners import (
    handle_post_created_direct_reply_notification,
    handle_post_liked_notification,
    handle_user_suspended_notification,
    handle_user_unsuspended_notification,
)


EXTENSION_ID = "notifications"


def extend():
    return [
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        ResourceExtender(
            endpoints=notification_resource_endpoints(),
        ),
        EventListenersExtender(
            listeners=notification_event_listener_definitions(),
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def notification_type_definitions():
    return (
        NotificationTypeDefinition(
            code="postReply",
            label="回复被回应",
            module_id=EXTENSION_ID,
            description="通知被回复的楼层作者。",
            icon="fas fa-comment-dots",
            navigation_scope="post",
            preference_key="notify_post_reply",
            preference_label="回复被回应通知",
            preference_description="当其他用户直接回复你的某条帖子时通知你。",
        ),
        NotificationTypeDefinition(
            code="userSuspended",
            label="账号封禁通知",
            module_id=EXTENSION_ID,
            description="通知用户账号已被管理员封禁。",
            icon="fas fa-user-lock",
            navigation_scope="profile",
            preference_key="notify_account_status",
            preference_label="账号状态通知",
            preference_description="当你的账号被封禁或解除封禁时通知你。",
        ),
        NotificationTypeDefinition(
            code="userUnsuspended",
            label="账号解除封禁",
            module_id=EXTENSION_ID,
            description="通知用户账号已恢复正常。",
            icon="fas fa-user-check",
            navigation_scope="profile",
            preference_key="notify_account_status",
            preference_label="账号状态通知",
            preference_description="当你的账号被封禁或解除封禁时通知你。",
        ),
    )


def user_preference_definitions():
    return (
        UserPreferenceDefinition(
            key="notify_post_reply",
            label="回复被回应通知",
            module_id=EXTENSION_ID,
            description="当其他用户直接回复你的某条帖子时通知你。",
            category="notification",
            default_value=True,
        ),
        UserPreferenceDefinition(
            key="notify_account_status",
            label="账号状态通知",
            module_id=EXTENSION_ID,
            description="当你的账号被封禁或解除封禁时通知你。",
            category="notification",
            default_value=True,
        ),
    )


def notification_resource_endpoints():
    return (
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="index",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_index,
            methods=("GET",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="stats",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_stats,
            methods=("GET",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="clear-read",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_delete_all_read,
            methods=("DELETE",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="clear-filtered-read",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_delete_filtered_read,
            methods=("DELETE",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="read",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_mark_read,
            methods=("POST",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="read-all",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_mark_all_read,
            methods=("POST",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="read-filtered",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_mark_filtered_read,
            methods=("POST",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="show",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_show,
            methods=("GET",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="notification",
            endpoint="delete",
            module_id=EXTENSION_ID,
            handler=_dispatch_notification_delete,
            methods=("DELETE",),
            auth_required=True,
        ),
    )


def notification_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=PostCreatedEvent,
            handler=handle_post_created_direct_reply_notification,
            description="回复发布后通知被回复楼层作者。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostLikedEvent,
            handler=handle_post_liked_notification,
            description="回复被点赞后通知作者。",
        ),
        ExtensionEventListenerDefinition(
            event_type=UserSuspendedEvent,
            handler=handle_user_suspended_notification,
            description="账号封禁后通知用户。",
        ),
        ExtensionEventListenerDefinition(
            event_type=UserUnsuspendedEvent,
            handler=handle_user_unsuspended_notification,
            description="账号解除封禁后通知用户。",
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Notifications 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Notifications 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Notifications 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Notifications 扩展已卸载。",
    }
