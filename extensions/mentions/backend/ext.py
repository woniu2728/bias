from apps.core.extensions import (
    EventListenersExtender,
    FormatterExtender,
    ForumCapabilitiesExtender,
    LifecycleExtender,
    NotificationsExtender,
    PostLifecycleExtender,
)
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import UserMentionedEvent
from apps.core.forum_registry_types import NotificationTypeDefinition, SearchFilterDefinition, UserPreferenceDefinition
from extensions.mentions.backend.formatter import render_mentions_html
from extensions.mentions.backend.lifecycle import (
    apply_post_approved_mentions,
    apply_post_created_mentions,
    apply_post_updated_mentions,
)
from extensions.mentions.backend.listeners import handle_user_mentioned_notification
from extensions.mentions.backend.search import (
    apply_post_mentioned_me_search_filter,
    parse_mentioned_me_search_filter,
)


EXTENSION_ID = "mentions"


def extend():
    return [
        ForumCapabilitiesExtender(
            search_filters=search_filter_definitions(),
        ),
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        EventListenersExtender(
            listeners=mention_event_listener_definitions(),
        ),
        FormatterExtender(transforms=(
            render_mentions_html,
        )),
        PostLifecycleExtender().handler(
            "mentions",
            apply_created=apply_post_created_mentions,
            apply_updated=apply_post_updated_mentions,
            apply_approved=apply_post_approved_mentions,
            description="帖子创建、编辑、审核通过时维护提及关系并派发提及事件。",
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def search_filter_definitions():
    return (
        SearchFilterDefinition(
            code="mentioned_me",
            label="提及我的回复",
            module_id=EXTENSION_ID,
            target="post",
            parser=parse_mentioned_me_search_filter,
            applier=apply_post_mentioned_me_search_filter,
            syntax="mentioned:me",
            description="仅返回提及当前用户的回复。",
        ),
    )


def notification_type_definitions():
    return (
        NotificationTypeDefinition(
            code="userMentioned",
            label="@提及通知",
            module_id=EXTENSION_ID,
            description="通知用户其在回复中被提及。",
            icon="fas fa-at",
            navigation_scope="post",
            preference_key="notify_user_mentioned",
            preference_label="@提及通知",
            preference_description="当其他用户在回复中提及你时通知你。",
        ),
    )


def user_preference_definitions():
    return (
        UserPreferenceDefinition(
            key="notify_user_mentioned",
            label="@提及通知",
            module_id=EXTENSION_ID,
            description="当其他用户在回复中提及你时通知你。",
            category="notification",
            default_value=True,
        ),
    )


def mention_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=UserMentionedEvent,
            handler=handle_user_mentioned_notification,
            description="用户被提及时派发提及通知。",
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Mentions 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Mentions 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Mentions 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Mentions 扩展已卸载。",
    }
