from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    ApiRoutesExtender,
    EventListenersExtender,
    FrontendExtender,
    ForumCapabilitiesExtender,
    LifecycleExtender,
    NotificationsExtender,
    PostEventExtender,
)
from apps.core.extensions.types import ExtensionEventListenerDefinition
from apps.core.forum_events import (
    DiscussionApprovedEvent,
    DiscussionRejectedEvent,
    DiscussionResubmittedEvent,
    PostApprovedEvent,
    PostRejectedEvent,
    PostResubmittedEvent,
)
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    UserPreferenceDefinition,
)
from extensions.approval.backend.admin_api import router as approval_admin_router
from extensions.approval.backend.listeners import (
    handle_discussion_approved,
    handle_discussion_rejected,
    handle_discussion_resubmitted,
    handle_post_approved,
    handle_post_rejected,
    handle_post_resubmitted,
)
from extensions.approval.backend.resources import (
    APPROVAL_POST_EVENT_TYPES,
    admin_stats_resource_field_definitions,
    resolve_approval_event_data,
)


EXTENSION_ID = "approval"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/approval/frontend/admin/index.js",
            forum_entry="extensions/approval/frontend/forum/index.js",
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            admin_pages=admin_page_definitions(),
            permissions_pages=("/admin/extensions/approval/permissions",),
            operations_pages=("/admin/extensions/approval/operations",),
        ),
        ApiRoutesExtender(
            mounts=(("/admin", approval_admin_router),),
            tags=("Admin",),
        ),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
        ),
        PostEventExtender().types(
            APPROVAL_POST_EVENT_TYPES,
            resolve_approval_event_data,
            description="审核系统事件帖的结构化 payload。",
        ),
        NotificationsExtender(
            notification_types=notification_type_definitions(),
            user_preferences=user_preference_definitions(),
        ),
        EventListenersExtender(
            listeners=approval_event_listener_definitions(),
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


def permission_definitions():
    return (
        PermissionDefinition(
            code="admin.approval.view",
            label="查看审核队列",
            section="moderation",
            section_label="审核与举报",
            module_id=EXTENSION_ID,
            icon="fas fa-user-check",
            description="允许在后台查看待审核讨论与回复队列。",
        ),
        PermissionDefinition(
            code="admin.approval.approve",
            label="通过审核内容",
            section="moderation",
            section_label="审核与举报",
            module_id=EXTENSION_ID,
            icon="fas fa-check-circle",
            description="允许在后台通过待审核讨论与回复。",
            required_permissions=("admin.approval.view",),
        ),
        PermissionDefinition(
            code="admin.approval.reject",
            label="拒绝审核内容",
            section="moderation",
            section_label="审核与举报",
            module_id=EXTENSION_ID,
            icon="fas fa-ban",
            description="允许在后台拒绝待审核讨论与回复并填写审核反馈。",
            required_permissions=("admin.approval.view",),
        ),
    )


def admin_page_definitions():
    return (
        AdminPageDefinition(
            path="/admin/approval",
            label="审核队列",
            icon="fas fa-user-check",
            module_id=EXTENSION_ID,
            nav_section="feature",
            description="处理待审核讨论与回复。",
        ),
    )


def post_type_definitions():
    return (
        PostTypeDefinition(
            code="discussionApproved",
            label="讨论审核通过",
            module_id=EXTENSION_ID,
            description="记录讨论被管理员审核通过的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-check-circle",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="discussionRejected",
            label="讨论审核拒绝",
            module_id=EXTENSION_ID,
            description="记录讨论被管理员审核拒绝的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-ban",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="discussionResubmitted",
            label="讨论重新提交审核",
            module_id=EXTENSION_ID,
            description="记录作者修改被拒讨论后重新提交审核的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-rotate-right",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="postApproved",
            label="回复审核通过",
            module_id=EXTENSION_ID,
            description="记录回复被管理员审核通过的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-check",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="postRejected",
            label="回复审核拒绝",
            module_id=EXTENSION_ID,
            description="记录回复被管理员审核拒绝的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-comment-slash",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="postResubmitted",
            label="回复重新提交审核",
            module_id=EXTENSION_ID,
            description="记录作者修改被拒回复后重新提交审核的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-reply",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
    )


def notification_type_definitions():
    return (
        NotificationTypeDefinition(
            code="discussionApproved",
            label="讨论审核通过",
            module_id=EXTENSION_ID,
            description="通知作者其讨论已通过审核。",
            icon="fas fa-circle-check",
            navigation_scope="discussion",
            preference_key="notify_discussion_approval",
            preference_label="讨论审核结果通知",
            preference_description="当你的讨论被审核通过或拒绝时通知你。",
        ),
        NotificationTypeDefinition(
            code="discussionRejected",
            label="讨论审核拒绝",
            module_id=EXTENSION_ID,
            description="通知作者其讨论未通过审核。",
            icon="fas fa-circle-xmark",
            navigation_scope="discussion",
            preference_key="notify_discussion_approval",
            preference_label="讨论审核结果通知",
            preference_description="当你的讨论被审核通过或拒绝时通知你。",
        ),
        NotificationTypeDefinition(
            code="postApproved",
            label="回复审核通过",
            module_id=EXTENSION_ID,
            description="通知作者其回复已通过审核。",
            icon="fas fa-check",
            navigation_scope="post",
            preference_key="notify_post_approval",
            preference_label="回复审核结果通知",
            preference_description="当你的回复被审核通过或拒绝时通知你。",
        ),
        NotificationTypeDefinition(
            code="postRejected",
            label="回复审核拒绝",
            module_id=EXTENSION_ID,
            description="通知作者其回复未通过审核。",
            icon="fas fa-xmark",
            navigation_scope="post",
            preference_key="notify_post_approval",
            preference_label="回复审核结果通知",
            preference_description="当你的回复被审核通过或拒绝时通知你。",
        ),
    )


def user_preference_definitions():
    return (
        UserPreferenceDefinition(
            key="notify_discussion_approval",
            label="讨论审核结果通知",
            module_id=EXTENSION_ID,
            description="当你的讨论被审核通过或拒绝时通知你。",
            category="notification",
            default_value=True,
        ),
        UserPreferenceDefinition(
            key="notify_post_approval",
            label="回复审核结果通知",
            module_id=EXTENSION_ID,
            description="当你的回复被审核通过或拒绝时通知你。",
            category="notification",
            default_value=True,
        ),
    )


def approval_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=DiscussionApprovedEvent,
            handler=handle_discussion_approved,
            description="讨论审核通过后通知作者、广播实时事件并写入讨论时间线。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionRejectedEvent,
            handler=handle_discussion_rejected,
            description="讨论审核拒绝后通知作者、广播实时事件并写入讨论时间线。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionResubmittedEvent,
            handler=handle_discussion_resubmitted,
            description="讨论重新提交审核后广播实时事件并写入讨论时间线。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostApprovedEvent,
            handler=handle_post_approved,
            description="回复审核通过后通知作者、广播实时事件并写入讨论时间线。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostRejectedEvent,
            handler=handle_post_rejected,
            description="回复审核拒绝后通知作者、广播实时事件并写入讨论时间线。",
        ),
        ExtensionEventListenerDefinition(
            event_type=PostResubmittedEvent,
            handler=handle_post_resubmitted,
            description="回复重新提交审核后广播实时事件并写入讨论时间线。",
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Approval 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Approval 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Approval 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Approval 扩展已卸载。",
    }


def run_migrations(context):
    return _migration_hook_result(context, "run_migrations", "Approval 扩展迁移已执行。")


def rollback_migrations(context):
    return _migration_hook_result(context, "rollback_migrations", "Approval 扩展迁移已回滚。")


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
