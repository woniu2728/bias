from apps.core.extensions import (
    ApiResourceExtender,
    EventListenersExtender,
    ForumCapabilitiesExtender,
    LifecycleExtender,
    NotificationsExtender,
)
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import (
    DiscussionCreatedEvent,
    PostApprovedEvent,
    PostCreatedEvent,
    PostDeletedEvent,
    PostHiddenEvent,
)
from apps.core.forum_registry_types import (
    DiscussionListFilterDefinition,
    NotificationTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceFieldDefinition
from extensions.subscriptions.backend.handlers import (
    dispatch_discussion_subscribe,
    dispatch_discussion_unsubscribe,
)
from extensions.subscriptions.backend.listeners import (
    handle_discussion_created_follow_after_create,
    handle_post_approved_discussion_reply_notification,
    handle_post_approved_follow_after_reply,
    handle_post_created_discussion_reply_notification,
    handle_post_created_follow_after_reply,
    handle_post_deleted_discussion_reply_notifications,
    handle_post_hidden_discussion_reply_notifications,
)
from extensions.subscriptions.backend.resources import resolve_discussion_subscription_state
from extensions.subscriptions.backend.search import (
    apply_discussion_following_search_filter,
    apply_following_discussion_list_filter,
    parse_following_search_filter,
)


EXTENSION_ID = "subscriptions"


def extend():
    return [
        ForumCapabilitiesExtender(
            discussion_list_filters=discussion_list_filter_definitions(),
            search_filters=search_filter_definitions(),
        ),
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        ApiResourceExtender("discussion")
        .fields(discussion_resource_field_definitions)
        .endpoints(discussion_resource_endpoint_definitions),
        EventListenersExtender(
            listeners=subscription_event_listener_definitions(),
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def discussion_list_filter_definitions():
    return (
        DiscussionListFilterDefinition(
            code="following",
            label="关注中",
            module_id=EXTENSION_ID,
            applier=apply_following_discussion_list_filter,
            description="仅显示当前用户已关注的讨论。",
            icon="fas fa-bell",
            requires_authenticated_user=True,
            order=20,
            route_path="/following",
        ),
    )


def search_filter_definitions():
    return (
        SearchFilterDefinition(
            code="is_following",
            label="仅关注讨论",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_following_search_filter,
            applier=apply_discussion_following_search_filter,
            syntax="is:following",
            description="仅返回当前用户已关注的讨论。",
        ),
    )


def notification_type_definitions():
    return (
        NotificationTypeDefinition(
            code="discussionReply",
            label="讨论新回复",
            module_id=EXTENSION_ID,
            description="通知讨论作者和关注者有新回复。",
            icon="fas fa-reply",
            navigation_scope="post",
            preference_key="notify_new_post",
            preference_label="关注讨论有新回复时通知我",
            preference_description="关闭后仍保留关注状态，但不再接收关注讨论的新回复通知。",
        ),
    )


def user_preference_definitions():
    return (
        UserPreferenceDefinition(
            key="follow_after_reply",
            label="回复后自动关注",
            module_id=EXTENSION_ID,
            description="参与讨论后自动把该讨论加入关注列表。",
            category="behavior",
            default_value=False,
        ),
        UserPreferenceDefinition(
            key="follow_after_create",
            label="发起讨论后自动关注",
            module_id=EXTENSION_ID,
            description="你创建的新讨论默认加入关注列表。",
            category="behavior",
            default_value=False,
        ),
        UserPreferenceDefinition(
            key="notify_new_post",
            label="关注讨论有新回复时通知我",
            module_id=EXTENSION_ID,
            description="关闭后仍保留关注状态，但不再接收关注讨论的新回复通知。",
            category="notification",
            default_value=True,
        ),
    )


def discussion_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="discussion",
            field="is_subscribed",
            module_id=EXTENSION_ID,
            resolver=resolve_discussion_subscription_state,
            description="当前用户是否关注该讨论。",
        ),
    )


def discussion_resource_endpoint_definitions():
    return (
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="subscribe",
            module_id=EXTENSION_ID,
            handler=dispatch_discussion_subscribe,
            methods=("POST",),
            path="discussions/{object_id}/subscribe",
            absolute_path=True,
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="subscribe",
            module_id=EXTENSION_ID,
            handler=dispatch_discussion_unsubscribe,
            methods=("DELETE",),
            path="discussions/{object_id}/subscribe",
            absolute_path=True,
            auth_required=True,
        ),
    )


def subscription_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=DiscussionCreatedEvent,
            handler=handle_discussion_created_follow_after_create,
            description="讨论创建后按用户偏好自动关注新讨论。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostCreatedEvent,
            handler=handle_post_created_discussion_reply_notification,
            description="已发布回复后为讨论作者和关注者派发讨论回复通知。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostCreatedEvent,
            handler=handle_post_created_follow_after_reply,
            description="已发布回复后按用户偏好自动关注参与的讨论。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostApprovedEvent,
            handler=handle_post_approved_discussion_reply_notification,
            description="回复审核通过后为讨论作者和关注者派发讨论回复通知。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostApprovedEvent,
            handler=handle_post_approved_follow_after_reply,
            description="回复审核通过后按用户偏好自动关注参与的讨论。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostHiddenEvent,
            handler=handle_post_hidden_discussion_reply_notifications,
            description="回复隐藏后清理该回复产生的关注讨论通知。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostDeletedEvent,
            handler=handle_post_deleted_discussion_reply_notifications,
            description="回复删除后清理该回复产生的关注讨论通知。",
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Subscriptions 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Subscriptions 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Subscriptions 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Subscriptions 扩展已卸载。",
    }
