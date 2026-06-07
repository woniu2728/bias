from apps.core.extensions import (
    ApiResourceExtender,
    ForumCapabilitiesExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    NotificationsExtender,
    PolicyExtender,
    SearchDriverExtender,
    SettingsExtender,
)
from apps.core.extensions.backend import _build_setting_field_definition
from apps.core.extensions.types import ExtensionModelRelationDefinition, ExtensionSearchDriverDefinition
from apps.core.forum_registry_types import NotificationTypeDefinition, UserPreferenceDefinition
from apps.core.forum_registry_types import SearchFilterDefinition
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceFieldDefinition, ResourceFilterDefinition, ResourceRelationshipDefinition
from apps.posts.models import Post
from apps.users.models import User
from extensions.likes.backend.models import PostLike
from extensions.likes.backend.handlers import dispatch_post_like_mutation
from extensions.likes.backend.resources import (
    post_like_preload_resolver,
    resolve_post_likes,
    resolve_post_is_liked,
    resolve_post_like_count,
)
from extensions.likes.backend.search import (
    apply_liked_by_filter,
    apply_liked_by_resource_filter,
    parse_liked_by_search_filter,
)
from extensions.likes.backend.services import like_post_policy, resolve_post_can_like


EXTENSION_ID = "likes"


def extend():
    return [
        FrontendExtender(
            forum_entry="extensions/likes/frontend/forum/index.js",
        ),
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        SettingsExtender(fields=setting_definitions())
        .default("like_own_post", False),
        ForumCapabilitiesExtender(
            search_filters=search_filter_definitions(),
        ),
        SearchDriverExtender(
            drivers=search_driver_definitions(),
        ),
        PolicyExtender(mounts=(("post.like", like_post_policy),)),
        ModelExtender(
            relations=model_relation_definitions(),
        ).owns(
            PostLike,
            description="帖子点赞记录由 likes 扩展拥有。",
        ),
        ApiResourceExtender("post")
        .fields(post_resource_field_definitions)
        .relationships(post_resource_relationship_definitions)
        .filters(post_resource_filter_definitions)
        .endpoints(post_resource_endpoints)
        .add_default_include(("index", "show"), ("likes",)),
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


def setting_definitions():
    return (
        _build_setting_field_definition({
            "key": "like_own_post",
            "label": "允许点赞自己的回复",
            "type": "boolean",
            "default": False,
            "help_text": "开启后用户可以给自己的回复点赞。",
            "order": 10,
        }),
    )


def search_filter_definitions():
    return (
        SearchFilterDefinition(
            code="likedBy",
            label="按点赞用户过滤",
            module_id=EXTENSION_ID,
            target="post",
            parser=parse_liked_by_search_filter,
            applier=apply_liked_by_filter,
            syntax="likedBy:<username>",
            description="仅返回被指定用户点赞过的回复。",
        ),
    )


def search_driver_definitions():
    return (
        ExtensionSearchDriverDefinition(
            target="post",
            driver="database",
            filters=search_filter_definitions(),
            description="按点赞用户过滤回复搜索。",
        ),
    )


def model_relation_definitions():
    return (
        ExtensionModelRelationDefinition(
            model=Post,
            name="likes",
            resolver=lambda post: [
                like.user
                for like in post.likes.select_related("user").all()
            ],
            relation_type="belongsToMany",
            related_model=User,
            description="点赞该回复的用户。",
            inject_attribute=False,
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


def post_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="post",
            relationship="likes",
            module_id=EXTENSION_ID,
            resolver=resolve_post_likes,
            description="点赞该回复的用户列表。",
            preload_resolver=post_like_preload_resolver,
            resource_type="post_user",
            many=True,
        ),
    )


def post_resource_filter_definitions():
    return (
        ResourceFilterDefinition(
            resource="post",
            filter="likedBy",
            module_id=EXTENSION_ID,
            handler=apply_liked_by_resource_filter,
            description="仅返回被指定用户点赞过的回复。",
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


def run_migrations(context):
    return _migration_hook_result(context, "run_migrations", "Likes 扩展迁移已执行。")


def rollback_migrations(context):
    return _migration_hook_result(context, "rollback_migrations", "Likes 扩展迁移已回滚。")


def _migration_hook_result(context, hook: str, message: str):
    return {
        "hook": hook,
        "status": "ok",
        "status_label": "已执行",
        "message": message,
        "details": {
            "migration_namespace": context.migration_namespace,
        },
    }
