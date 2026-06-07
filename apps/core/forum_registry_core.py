from __future__ import annotations

from apps.core.forum_registry_types import (
    AdminPageDefinition,
    ForumModuleDefinition,
    LanguagePackDefinition,
)


def _register_core_modules(registry) -> None:
    registry.register_module(
        ForumModuleDefinition(
            module_id="core",
            name="Core",
            description="论坛核心配置、权限、外观与高级设置底座。",
            category="core",
            is_core=True,
            admin_pages=(
                AdminPageDefinition(
                    path="/admin",
                    label="仪表盘",
                    icon="fas fa-chart-bar",
                    module_id="core",
                    nav_section="core",
                    description="查看论坛概况和系统状态。",
                ),
                AdminPageDefinition(
                    path="/admin/basics",
                    label="基础设置",
                    icon="fas fa-pencil-alt",
                    module_id="core",
                    nav_section="core",
                    description="维护论坛标题、公告与 SEO 基础信息。",
                    settings_group="basic",
                ),
                AdminPageDefinition(
                    path="/admin/permissions",
                    label="权限管理",
                    icon="fas fa-key",
                    module_id="core",
                    nav_section="core",
                    description="配置用户组权限矩阵。",
                ),
                AdminPageDefinition(
                    path="/admin/appearance",
                    label="外观设置",
                    icon="fas fa-paint-brush",
                    module_id="core",
                    nav_section="core",
                    description="维护主题色、Logo 与自定义样式。",
                    settings_group="appearance",
                ),
                AdminPageDefinition(
                    path="/admin/mail",
                    label="邮件设置",
                    icon="fas fa-envelope",
                    module_id="core",
                    nav_section="feature",
                    description="配置邮件驱动与测试投递。",
                    settings_group="mail",
                ),
                AdminPageDefinition(
                    path="/admin/advanced",
                    label="高级设置",
                    icon="fas fa-cog",
                    module_id="core",
                    nav_section="feature",
                    description="管理缓存、队列、存储和维护模式。",
                    settings_group="advanced",
                ),
                AdminPageDefinition(
                    path="/admin/audit-logs",
                    label="审计日志",
                    icon="fas fa-clipboard-list",
                    module_id="core",
                    nav_section="feature",
                    description="查看后台关键管理操作审计记录。",
                ),
                AdminPageDefinition(
                    path="/admin/docs",
                    label="开发者文档",
                    icon="fas fa-book",
                    module_id="core",
                    nav_section="feature",
                    description="查看模块开发、资源字段、事件订阅与前后端接入指南。",
                ),
            ),
            capabilities=(
                "settings",
                "permissions",
                "appearance",
                "mail",
                "advanced",
                "audit-log",
                "developer-docs",
            ),
            settings_groups=("basic", "appearance", "mail", "advanced"),
            language_packs=(
                LanguagePackDefinition(
                    code="zh-CN",
                    label="简体中文",
                    native_label="简体中文",
                    module_id="core",
                    description="论坛内置默认语言包，仅提供中文界面元数据。",
                    is_default=True,
                ),
            ),
        )
    )
