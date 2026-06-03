from dataclasses import replace

from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiRoutesExtender,
    EventListenersExtender,
    LifecycleExtender,
    ModelVisibilityExtender,
    ResourceExtender,
    SettingsExtender,
)
from apps.core.extensions.backend import _build_setting_field_definition
from apps.core.extensions.types import ExtensionEventListenerDefinition, ExtensionModelVisibilityDefinition
from apps.core.forum_events import PostDeletedEvent, PostFlagCreatedEvent, PostFlagsDeletedEvent, PostFlagsResolvedEvent
from apps.core.forum_registry_types import AdminPageDefinition, PermissionDefinition
from apps.core.forum_resources_flags import (
    _resolve_post_can_flag,
    _resolve_post_can_moderate_flags,
    _resolve_post_flag_identifiers,
    _resolve_post_flags,
    _resolve_post_open_flag_count,
    _resolve_post_open_flags,
    _resolve_post_viewer_has_open_flag,
    _resolve_forum_can_view_flags,
    _resolve_forum_flag_count,
    _resolve_user_new_flag_count,
    scope_flag_visibility,
)
from apps.posts.models import PostFlag
from apps.core.resource_registry import (
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
)
from extensions.flags.backend.handlers import (
    dispatch_post_delete_flags,
    dispatch_post_report,
    dispatch_post_resolve_flags,
)
from extensions.flags.backend.listeners import (
    handle_post_deleted_flags,
    handle_post_flag_created,
    handle_post_flags_deleted,
    handle_post_flags_resolved,
)
from extensions.flags.backend.resource import FlagResource
from extensions.flags.backend.routes import router as flags_router


EXTENSION_ID = "flags"


def extend():
    return [
        SettingsExtender(
            fields=setting_definitions(),
            expose_to_forum=("guidelines_url",),
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            admin_pages=admin_page_definitions(),
            generated_permissions_page=True,
        ),
        ResourceExtender(
            resources=flag_resource_definitions(),
            fields=post_resource_field_definitions(),
            relationships=post_resource_relationship_definitions(),
            endpoints=post_resource_endpoint_definitions(),
        ),
        ApiRoutesExtender(
            mounts=(("", flags_router),),
            tags=("Posts",),
        ),
        ModelVisibilityExtender(
            definitions=flag_model_visibility_definitions(),
        ),
        EventListenersExtender(
            listeners=flag_event_listener_definitions(),
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


def post_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="forum",
            field="can_view_flags",
            module_id=EXTENSION_ID,
            resolver=_resolve_forum_can_view_flags,
            description="当前用户是否可以查看举报队列。",
        ),
        ResourceFieldDefinition(
            resource="forum",
            field="flag_count",
            module_id=EXTENSION_ID,
            resolver=_resolve_forum_flag_count,
            description="当前用户可见的待处理举报帖子数量。",
            visible=_visible_to_forum_flag_moderators,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="can_flag",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_can_flag,
            description="当前用户是否可以举报该回复。",
        ),
        ResourceFieldDefinition(
            resource="post",
            field="viewer_has_open_flag",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_viewer_has_open_flag,
            description="当前用户是否已对该回复提交待处理举报。",
        ),
        ResourceFieldDefinition(
            resource="post",
            field="open_flag_count",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_open_flag_count,
            description="当前回复的待处理举报数量。",
        ),
        ResourceFieldDefinition(
            resource="post",
            field="open_flags",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_open_flags,
            description="当前回复的待处理举报明细。",
        ),
        ResourceFieldDefinition(
            resource="post",
            field="flags",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_flags,
            description="当前回复可见的待处理举报明细。",
            visible=_visible_to_flag_moderators,
        ),
        ResourceFieldDefinition(
            resource="post",
            field="can_moderate_flags",
            module_id=EXTENSION_ID,
            resolver=_resolve_post_can_moderate_flags,
            description="当前用户是否可在前台处理举报。",
        ),
        ResourceFieldDefinition(
            resource="user_detail",
            field="new_flag_count",
            module_id=EXTENSION_ID,
            resolver=_resolve_user_new_flag_count,
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
            resolver=_resolve_post_flag_identifiers,
            description="当前回复可见的待处理举报关系。",
            visible=_visible_to_flag_moderators,
            resource_type="flag",
            many=True,
        ),
    )


def post_resource_endpoint_definitions():
    return (
        ResourceEndpointDefinition(
            resource="post",
            endpoint="index",
            module_id=EXTENSION_ID,
            operation="mutate",
            mutator=_add_post_flags_default_include,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="show",
            module_id=EXTENSION_ID,
            operation="mutate",
            mutator=_add_post_flags_default_include,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="report",
            module_id=EXTENSION_ID,
            handler=dispatch_post_report,
            methods=("POST",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="flags/resolve",
            module_id=EXTENSION_ID,
            handler=dispatch_post_resolve_flags,
            methods=("POST",),
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="post",
            endpoint="flags/delete",
            module_id=EXTENSION_ID,
            handler=dispatch_post_delete_flags,
            methods=("DELETE",),
            auth_required=True,
        ),
    )


def flag_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=PostFlagCreatedEvent,
            handler=handle_post_flag_created,
            description="帖子被举报后向讨论实时流广播举报状态变更。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostFlagsResolvedEvent,
            handler=handle_post_flags_resolved,
            description="帖子举报被处理后向讨论实时流广播举报状态变更。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostFlagsDeletedEvent,
            handler=handle_post_flags_deleted,
            description="帖子举报被删除后向讨论实时流广播举报状态变更。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostDeletedEvent,
            handler=handle_post_deleted_flags,
            description="帖子被删除后向讨论实时流广播举报状态变更。",
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
    return _resolve_forum_can_view_flags(None, context)


def _visible_to_forum_flag_moderators(forum, context: dict) -> bool:
    return _resolve_forum_can_view_flags(forum, context)


def _visible_to_self(user, context: dict) -> bool:
    actor = context.get("user")
    return bool(actor and actor.is_authenticated and user and actor.id == user.id)


def _add_post_flags_default_include(endpoint: ResourceEndpointDefinition) -> ResourceEndpointDefinition:
    includes = list(endpoint.default_include or ())
    if "flags" not in includes:
        includes.append("flags")
    return replace(endpoint, default_include=tuple(includes))


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
