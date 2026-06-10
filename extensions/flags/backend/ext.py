from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    ApiRoutesExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    ModelVisibilityExtender,
    PostLifecycleExtender,
    RealtimeExtender,
    SettingsExtender,
    ServiceProviderExtender,
)
from apps.core.extensions.backend import _build_setting_field_definition
from apps.core.extensions.types import ExtensionModelVisibilityDefinition
from extensions.flags.backend.events import PostFlagCreatedEvent, PostFlagsDeletedEvent, PostFlagsResolvedEvent
from apps.core.forum_registry_types import AdminPageDefinition, PermissionDefinition
from apps.core.resource_registry import (
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
)
from extensions.flags.backend.models import PostFlag
from extensions.flags.backend.handlers import (
    dispatch_post_delete_flags,
    dispatch_post_report,
    dispatch_post_resolve_flags,
)
from extensions.flags.backend.admin_api import router as flags_admin_router
from extensions.flags.backend.lifecycle import prepare_post_delete_flags
from extensions.flags.backend.resource import FlagResource
from extensions.flags.backend.runtime import flag_service_provider
from extensions.flags.backend.resources import (
    resolve_admin_open_flags,
    resolve_forum_can_view_flags,
    resolve_forum_flag_count,
    post_flag_preload_resolver,
    resolve_post_can_flag,
    resolve_post_can_moderate_flags,
    resolve_post_flag_identifiers,
    resolve_post_flags,
    resolve_post_open_flag_count,
    resolve_post_open_flags,
    resolve_post_viewer_has_open_flag,
    resolve_user_new_flag_count,
    scope_flag_visibility,
)


EXTENSION_ID = "flags"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/flags/frontend/admin/index.js",
            forum_entry="extensions/flags/frontend/forum/index.js",
        ),
        SettingsExtender(
            fields=setting_definitions(),
            expose_to_forum=("guidelines_url",),
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            admin_pages=admin_page_definitions(),
            permissions_pages=("/admin/extensions/flags/permissions",),
            operations_pages=("/admin/extensions/flags/operations",),
        ),
        ApiRoutesExtender(
            mounts=(("/admin", flags_admin_router),),
            tags=("Admin",),
        ),
        ServiceProviderExtender(
            key="flags.service",
            provider=flag_service_provider,
        ),
        ApiResourceExtender(FlagResource),
        ApiResourceExtender("forum").fields(forum_resource_field_definitions),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        ApiResourceExtender("post")
        .fields(post_resource_field_definitions)
        .relationships(post_resource_relationship_definitions)
        .endpoints(post_resource_endpoint_definitions)
        .add_default_include(("index", "show"), ("flags",)),
        ApiResourceExtender("user_detail").fields(user_detail_resource_field_definitions),
        ModelExtender().owns(
            PostFlag,
            description="帖子举报记录由 flags 扩展拥有。",
        ),
        ModelVisibilityExtender(
            definitions=flag_model_visibility_definitions(),
        ),
        RealtimeExtender()
        .broadcast_discussion_event(
            PostFlagCreatedEvent,
            "post.flagged",
            include_discussion=True,
            include_post=True,
            post_id="post_id",
            description="帖子被举报后向讨论实时流广播举报状态变更。",
        )
        .broadcast_discussion_event(
            PostFlagsResolvedEvent,
            "post.flags_resolved",
            include_discussion=True,
            include_post=True,
            post_id="post_id",
            description="帖子举报被处理后向讨论实时流广播举报状态变更。",
        )
        .broadcast_discussion_event(
            PostFlagsDeletedEvent,
            "post.flags_deleted",
            include_discussion=True,
            include_post=True,
            post_id="post_id",
            description="帖子举报被删除后向讨论实时流广播举报状态变更。",
        ),
        PostLifecycleExtender().handler(
            "flags",
            prepare_delete=prepare_post_delete_flags,
            description="帖子删除前清理关联举报并派发举报删除事件。",
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
            "key": "guidelines_url",
            "label": "社区规则 URL",
            "type": "text",
            "default": "",
            "placeholder": "https://example.com/community-guidelines",
            "help_text": "前台举报原因说明中使用的社区规则链接。",
            "order": 10,
        }),
        _build_setting_field_definition({
            "key": "can_flag_own",
            "label": "允许举报自己的帖子",
            "type": "boolean",
            "default": False,
            "help_text": "关闭时，帖子作者不能举报自己的帖子。",
            "order": 20,
        }),
    )


def permission_definitions():
    return (
        PermissionDefinition(
            code="admin.flag.view",
            label="查看举报队列",
            section="moderation",
            section_label="审核与举报",
            module_id=EXTENSION_ID,
            icon="fas fa-flag",
            description="允许在后台查看帖子举报记录。",
        ),
        PermissionDefinition(
            code="admin.flag.resolve",
            label="处理帖子举报",
            section="moderation",
            section_label="审核与举报",
            module_id=EXTENSION_ID,
            icon="fas fa-gavel",
            description="允许在后台把帖子举报标记为已处理或已忽略。",
            required_permissions=("admin.flag.view",),
        ),
    )


def admin_page_definitions():
    return (
        AdminPageDefinition(
            path="/admin/flags",
            label="举报管理",
            icon="fas fa-flag",
            module_id=EXTENSION_ID,
            nav_section="feature",
            description="查看并处理帖子举报。",
        ),
    )


def flag_resource_definitions():
    return (
        FlagResource(),
    )


def forum_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="forum",
            field="can_view_flags",
            module_id=EXTENSION_ID,
            resolver=resolve_forum_can_view_flags,
            description="当前用户是否可以查看举报队列。",
        ),
        ResourceFieldDefinition(
            resource="forum",
            field="flag_count",
            module_id=EXTENSION_ID,
            resolver=resolve_forum_flag_count,
            description="当前用户可见的待处理举报帖子数量。",
            visible=_visible_to_forum_flag_moderators,
        ),
    )


def admin_stats_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="admin_stats",
            field="openFlags",
            module_id=EXTENSION_ID,
            resolver=resolve_admin_open_flags,
            description="后台统计中的待处理举报数量。",
        ),
    )


def post_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="post",
            field="can_flag",
            module_id=EXTENSION_ID,
            resolver=resolve_post_can_flag,
            description="当前用户是否可以举报该回复。",
        ),
        ResourceFieldDefinition(
            resource="post",
            field="viewer_has_open_flag",
            module_id=EXTENSION_ID,
            resolver=resolve_post_viewer_has_open_flag,
            description="当前用户是否已对该回复提交待处理举报。",
            preload_resolver=post_flag_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="open_flag_count",
            module_id=EXTENSION_ID,
            resolver=resolve_post_open_flag_count,
            description="当前回复的待处理举报数量。",
            preload_resolver=post_flag_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="open_flags",
            module_id=EXTENSION_ID,
            resolver=resolve_post_open_flags,
            description="当前回复的待处理举报明细。",
            preload_resolver=post_flag_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="flags",
            module_id=EXTENSION_ID,
            resolver=resolve_post_flags,
            description="当前回复可见的待处理举报明细。",
            visible=_visible_to_flag_moderators,
            preload_resolver=post_flag_preload_resolver,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="can_moderate_flags",
            module_id=EXTENSION_ID,
            resolver=resolve_post_can_moderate_flags,
            description="当前用户是否可在前台处理举报。",
        ),
    )


def user_detail_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="user_detail",
            field="new_flag_count",
            module_id=EXTENSION_ID,
            resolver=resolve_user_new_flag_count,
            description="当前用户可见的待处理举报帖子数量。",
            visible=_visible_to_self,
        ),
    )


def post_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="post",
            relationship="flags",
            module_id=EXTENSION_ID,
            resolver=resolve_post_flag_identifiers,
            description="当前回复可见的待处理举报关系。",
            visible=_visible_to_flag_moderators,
            resource_type="flag",
            many=True,
            preload_resolver=post_flag_preload_resolver,
        ),
    )


def post_resource_endpoint_definitions():
    return (
        ResourceEndpointDefinition(
            resource="post",
            endpoint="report",
            module_id=EXTENSION_ID,
            handler=dispatch_post_report,
            methods=("POST",),
            path="posts/{object_id}/report",
            absolute_path=True,
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="flags/resolve",
            module_id=EXTENSION_ID,
            handler=dispatch_post_resolve_flags,
            methods=("POST",),
            path="posts/{object_id}/flags/resolve",
            absolute_path=True,
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="flags/delete",
            module_id=EXTENSION_ID,
            handler=dispatch_post_delete_flags,
            methods=("DELETE",),
            path="posts/{object_id}/flags",
            absolute_path=True,
            auth_required=True,
        ),
    )


def flag_model_visibility_definitions():
    return (
        ExtensionModelVisibilityDefinition(
            model=PostFlag,
            ability="view",
            scope=scope_flag_visibility,
            description="限制举报记录只对可查看举报队列且能查看对应帖子的用户可见。",
        ),
    )


def _visible_to_flag_moderators(post, context: dict) -> bool:
    return resolve_forum_can_view_flags(None, context)


def _visible_to_forum_flag_moderators(forum, context: dict) -> bool:
    return resolve_forum_can_view_flags(forum, context)


def _visible_to_self(user, context: dict) -> bool:
    actor = context.get("user")
    return bool(actor and actor.is_authenticated and user and actor.id == user.id)


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Flags 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Flags 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Flags 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Flags 扩展已卸载。",
    }
