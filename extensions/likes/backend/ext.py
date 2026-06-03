from apps.core.extensions import LifecycleExtender, NotificationsExtender, ResourceExtender
from apps.core.forum_registry_types import NotificationTypeDefinition, UserPreferenceDefinition
from apps.core.forum_resources import _resolve_post_can_like
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceFieldDefinition


EXTENSION_ID = "likes"


def extend():
    return [
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        ResourceExtender(
            fields=post_resource_field_definitions(),
            endpoints=post_resource_endpoints(),
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
            field="can_like",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_can_like,
            description="当前用户是否可以点赞该回复。",
        ),
    )


def post_resource_endpoints():
    return (
        ResourceEndpointDefinition(
            resource="post",
            endpoint="like",
            module_id=EXTENSION_ID,
            handler=_dispatch_post_like_mutation,
            methods=("POST", "DELETE"),
            auth_required=True,
        ),
    )


def _dispatch_post_like_mutation(context):
    from apps.posts.api import _dispatch_post_like, _dispatch_post_unlike

    method = str(context.get("method") or "GET").upper()
    if method == "DELETE":
        return _dispatch_post_unlike(context)
    return _dispatch_post_like(context)


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
