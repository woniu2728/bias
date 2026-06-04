from apps.core.extensions import ApiResourceExtender, LifecycleExtender, NotificationsExtender
from apps.core.forum_registry_types import NotificationTypeDefinition, UserPreferenceDefinition
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceFieldDefinition
from extensions.likes.backend.handlers import dispatch_post_like_mutation
from extensions.likes.backend.resources import (
    post_like_preload_resolver,
    resolve_post_is_liked,
    resolve_post_like_count,
)
from extensions.likes.backend.services import resolve_post_can_like


EXTENSION_ID = "likes"


def extend():
    return [
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        ApiResourceExtender("post")
        .fields(post_resource_field_definitions)
        .endpoints(post_resource_endpoints),
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
            code="postLiked",
            label="回复被点赞",
            module_id=EXTENSION_ID,
            description="通知回复作者其内容被点赞。",
            icon="fas fa-thumbs-up",
            navigation_scope="post",
            preference_key="notify_post_liked",
            preference_label="回复被点赞通知",
            preference_description="当你的回复被其他用户点赞时通知你。",
        ),
    )


def user_preference_definitions():
    return (
        UserPreferenceDefinition(
            key="notify_post_liked",
            label="回复被点赞通知",
            module_id=EXTENSION_ID,
            description="当你的回复被其他用户点赞时通知你。",
            category="notification",
            default_value=True,
        ),
    )


def post_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="post",
            field="like_count",
            module_id=EXTENSION_ID,
            resolver=resolve_post_like_count,
            description="当前回复的点赞数量。",
            preload_resolver=post_like_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="is_liked",
            module_id=EXTENSION_ID,
            resolver=resolve_post_is_liked,
            description="当前用户是否已点赞该回复。",
            preload_resolver=post_like_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="can_like",
            module_id=EXTENSION_ID,
            resolver=resolve_post_can_like,
            description="当前用户是否可以点赞该回复。",
        ),
    )


def post_resource_endpoints():
    return (
        ResourceEndpointDefinition(
            resource="post",
            endpoint="like",
            module_id=EXTENSION_ID,
            handler=dispatch_post_like_mutation,
            methods=("POST", "DELETE"),
            path="posts/{object_id}/like",
            absolute_path=True,
            auth_required=True,
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Likes 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Likes 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Likes 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Likes 扩展已卸载。",
    }
