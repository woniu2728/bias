from apps.core.extensions import (
    ConditionalExtender,
    ApiResourceExtender,
    EventListenersExtender,
    FormatterExtender,
    ForumCapabilitiesExtender,
    FrontendExtender,
    LifecycleExtender,
    NotificationsExtender,
    PostLifecycleExtender,
    SettingsExtender,
)
from apps.core.extensions.backend import _build_setting_field_definition
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import UserMentionedEvent
from apps.core.forum_registry_types import NotificationTypeDefinition, SearchFilterDefinition, UserPreferenceDefinition
from apps.core.resource_registry import ResourceRelationshipDefinition
from extensions.mentions.backend.formatter import render_mentions_html
from extensions.mentions.backend.lifecycle import (
    apply_post_approved_mentions,
    apply_post_created_mentions,
    apply_post_hidden_mentions,
    apply_post_updated_mentions,
    prepare_post_delete_mentions,
)
from extensions.mentions.backend.listeners import handle_user_mentioned_notification
from extensions.mentions.backend.resources import post_mentions_preload_resolver, resolve_post_mentions_users
from extensions.mentions.backend.search import (
    apply_post_mentioned_me_search_filter,
    parse_mentioned_me_search_filter,
)
from extensions.mentions.backend.tag_mentions import render_tag_mentions_html


EXTENSION_ID = "mentions"


def extend():
    return [
        FrontendExtender(
            forum_entry="extensions/mentions/frontend/forum/index.js",
        ),
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
        SettingsExtender(fields=setting_definitions(), expose_to_forum=("allow_username_format",))
        .default("allow_username_format", False)
        .serialize_to_forum("allowUsernameMentionFormat", "allow_username_format", parse_bool_setting),
        ConditionalExtender().when_extension_enabled("tags", tag_mentions_extenders),
        ApiResourceExtender("post").relationships(post_resource_relationship_definitions),
        PostLifecycleExtender().handler(
            "mentions",
            apply_created=apply_post_created_mentions,
            apply_updated=apply_post_updated_mentions,
            apply_approved=apply_post_approved_mentions,
            apply_hidden=apply_post_hidden_mentions,
            prepare_delete=prepare_post_delete_mentions,
            description="帖子可见性变化与生命周期变更时维护提及关系并派发提及事件。",
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def setting_definitions():
    return (
        _build_setting_field_definition({
            "key": "allow_username_format",
            "label": "允许用户名提及格式",
            "type": "boolean",
            "default": False,
            "help_text": "向前端暴露 allowUsernameMentionFormat，用于控制是否兼容纯用户名提及格式。",
            "order": 10,
        }),
    )


def parse_bool_setting(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


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


def post_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="post",
            relationship="mentions_users",
            module_id=EXTENSION_ID,
            resolver=resolve_post_mentions_users,
            description="帖子中被提及的用户摘要列表。",
            prefetch_related=("mentions__mentions_user",),
            preload_resolver=post_mentions_preload_resolver,
            resource_type="user_summary",
            many=True,
        ),
    )


def tag_mentions_extenders():
    return [
        FormatterExtender().render(render_tag_mentions_html),
    ]


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
