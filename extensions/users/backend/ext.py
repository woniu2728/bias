from apps.core.extensions import AdminSurfaceExtender, FrontendExtender, LifecycleExtender
from apps.core.forum_registry_types import AdminPageDefinition, PermissionDefinition


EXTENSION_ID = "users"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/users/frontend/admin/index.js",
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            admin_pages=admin_page_definitions(),
            permissions_pages=("/admin/extensions/users/permissions",),
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
            code="viewUserList",
            label="查看用户列表",
            section="view",
            section_label="查看权限",
            module_id=EXTENSION_ID,
            icon="fas fa-users",
            description="允许浏览用户列表与公开资料。",
        ),
        PermissionDefinition(
            code="searchUsers",
            label="搜索用户",
            section="view",
            section_label="查看权限",
            module_id=EXTENSION_ID,
            icon="fas fa-search",
            description="允许在论坛搜索中查询用户。",
        ),
        PermissionDefinition(
            code="user.edit",
            label="编辑用户资料",
            section="user",
            section_label="用户管理",
            module_id=EXTENSION_ID,
            icon="fas fa-user-edit",
            description="允许管理员编辑任意用户资料与用户组。",
        ),
        PermissionDefinition(
            code="user.suspend",
            label="封禁用户",
            section="user",
            section_label="用户管理",
            module_id=EXTENSION_ID,
            icon="fas fa-user-slash",
            description="允许暂停用户发言能力。",
        ),
    )


def admin_page_definitions():
    return (
        AdminPageDefinition(
            path="/admin/users",
            label="用户管理",
            icon="fas fa-users",
            module_id=EXTENSION_ID,
            nav_section="core",
            description="查看、编辑、分组与封禁论坛用户。",
        ),
    )


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Users 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Users 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Users 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Users 扩展已卸载。",
    }
