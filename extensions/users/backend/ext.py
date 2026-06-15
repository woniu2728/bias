from apps.core.extensions import (
    AdminPageDefinition,
    ApiResourceExtender,
    ApiRoutesExtender,
    AdminSurfaceExtender,
    ForumPermissionExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    PermissionDefinition,
    SearchIndexExtender,
    SettingsExtender,
    ServiceProviderExtender,
    UserExtender,
)
from extensions.users.backend.admin_api import router as admin_users_router
from extensions.users.backend.api import router as users_router
from extensions.users.backend.handlers import user_resource_endpoints
from extensions.users.backend.mail_templates import mail_setting_defaults
from extensions.users.backend.models import AccessToken, EmailToken, Group, PasswordToken, Permission, User
from extensions.users.backend.resources import (
    admin_stats_resource_field_definitions,
    user_resource_definitions,
    user_resource_field_definitions,
    user_resource_relationship_definitions,
)
from extensions.users.backend.runtime import user_model_provider, user_service_provider
from extensions.users.backend.search_targets import user_search_target_provider
from extensions.users.backend.services import UserService


EXTENSION_ID = "users"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/users/frontend/admin/index.js",
            forum_entry="extensions/users/frontend/forum/index.js",
        )
        .route(
            "/login",
            "login",
            "./AuthRouteView.vue",
            order=20,
        )
        .route(
            "/register",
            "register",
            "./AuthRouteView.vue",
            order=21,
        )
        .route(
            "/forgot-password",
            "forgot-password",
            "./AuthRouteView.vue",
            order=22,
        )
        .route(
            "/verify-email",
            "verify-email",
            "./VerifyEmailView.vue",
            title="验证邮箱",
            description="验证你的账号邮箱地址。",
            order=23,
        )
        .route(
            "/reset-password",
            "reset-password",
            "./ResetPasswordView.vue",
            title="重置密码",
            description="设置新的账号登录密码。",
            order=24,
        )
        .route(
            "/profile",
            "profile",
            "./ProfileView.vue",
            requires_auth=True,
            order=50,
        )
        .route(
            "/u/:id",
            "user-profile",
            "./ProfileView.vue",
            order=51,
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            admin_pages=admin_page_definitions(),
            permissions_pages=("/admin/extensions/users/permissions",),
        ),
        ApiRoutesExtender(
            mounts=(("/users", users_router), ("/admin", admin_users_router)),
            tags=("Users",),
        ),
        ApiResourceExtender("user_detail")
        .endpoints_with(*user_resource_endpoints())
        .fields(user_resource_field_definitions)
        .relationships(user_resource_relationship_definitions),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        *[
            ApiResourceExtender(definition)
            for definition in user_resource_definitions()
        ],
        ModelExtender()
        .owns(User, description="用户账号由 users 扩展拥有。")
        .owns(Group, description="用户组由 users 扩展拥有。")
        .owns(Permission, description="用户组权限由 users 扩展拥有。")
        .owns(AccessToken, description="用户访问令牌由 users 扩展拥有。")
        .owns(EmailToken, description="邮箱验证令牌由 users 扩展拥有。")
        .owns(PasswordToken, description="密码重置令牌由 users 扩展拥有。"),
        LifecycleExtender(),
        ForumPermissionExtender().checker(
            "users.forum-permissions",
            UserService.has_forum_permission,
            description="基于用户组、后台权限与扩展策略判断论坛权限。",
        ),
        build_mail_settings_extender(),
        UserExtender().model_provider(
            user_model_provider,
            description="提供 core 运行时需要的用户模型查询、在线用户序列化与管理员账号管理能力。",
        ),
        ServiceProviderExtender(
            key="users.service",
            provider=user_service_provider,
        ),
        ServiceProviderExtender(
            key="search.target.user",
            provider=user_search_target_provider,
        ),
        SearchIndexExtender().postgres_index(
            "users_profile_fts_idx",
            drop="DROP INDEX CONCURRENTLY IF EXISTS users_profile_fts_idx",
            create="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS users_profile_fts_idx
                ON users
                USING GIN (
                    to_tsvector(
                        'simple',
                        coalesce(username, '') || ' ' || coalesce(display_name, '') || ' ' || coalesce(bio, '')
                    )
                )
            """,
            description="为用户名称、显示名和简介提供 PostgreSQL 全文搜索索引。",
        ),
    ]


def build_mail_settings_extender():
    extender = SettingsExtender(generated_page=False)
    for key, value in mail_setting_defaults().items():
        extender = extender.default(f"mail.{key}", value)
    return extender


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
