from __future__ import annotations

from pathlib import Path

from apps.core.extensions.types import ExtensionDefinition, ExtensionDeliveryCheckDefinition


def inspect_extension_runtime(definition: ExtensionDefinition) -> dict:
    if definition.source == "builtin-module":
        return {
            "healthy": True,
            "migration_state": definition.runtime.migration_state,
            "migration_label": definition.runtime.migration_label,
            "runtime_issues": (),
            "delivery_checks": (
                ExtensionDeliveryCheckDefinition(
                    key="builtin-bundle",
                    label="内置交付",
                    status="ready",
                    status_label="已就绪",
                    message="该扩展随核心应用一起交付，不依赖独立扩展目录。",
                ),
            ),
            "uninstall_warnings": (
                "内置扩展不支持卸载，只能通过启停协议控制可见性。",
            ),
        }

    root_path = Path(definition.manifest.path) if definition.manifest.path else None
    checks: list[ExtensionDeliveryCheckDefinition] = []
    runtime_issues: list[str] = []

    checks.append(_build_root_check(root_path))
    checks.append(_build_backend_entry_check(root_path, definition))
    checks.append(_build_frontend_admin_check(root_path, definition))
    checks.append(_build_migration_check(root_path, definition))
    checks.append(_build_documentation_check(root_path, definition))
    checks.append(_build_locale_check(root_path))
    checks.append(_build_frontend_forum_check(root_path, definition))

    healthy = True
    for check in checks:
        if check.status == "attention" and not check.optional:
            healthy = False
            if check.message:
                runtime_issues.append(check.message)

    uninstall_warnings = _build_uninstall_warnings(root_path, definition, checks)
    migration_state, migration_label = _build_migration_summary(root_path, definition)

    return {
        "healthy": healthy,
        "migration_state": migration_state,
        "migration_label": migration_label,
        "runtime_issues": tuple(runtime_issues),
        "delivery_checks": tuple(checks),
        "uninstall_warnings": tuple(uninstall_warnings),
    }


def _build_root_check(root_path: Path | None) -> ExtensionDeliveryCheckDefinition:
    if root_path and root_path.exists():
        return ExtensionDeliveryCheckDefinition(
            key="root",
            label="扩展目录",
            status="ready",
            status_label="已就绪",
            message="扩展目录已发现。",
            path=str(root_path),
        )
    return ExtensionDeliveryCheckDefinition(
        key="root",
        label="扩展目录",
        status="attention",
        status_label="缺失",
        message="扩展目录不存在，无法继续检测交付资源。",
        path=str(root_path or ""),
    )


def _build_backend_entry_check(root_path: Path | None, definition: ExtensionDefinition) -> ExtensionDeliveryCheckDefinition:
    backend_entry = str(definition.manifest.backend_entry or "").strip()
    backend_file = root_path / "backend" / "ext.py" if root_path else None
    if not backend_entry:
        return ExtensionDeliveryCheckDefinition(
            key="backend-entry",
            label="后端入口",
            status="pending",
            status_label="未声明",
            message="当前扩展未声明后端入口。",
            optional=True,
        )
    if backend_file and backend_file.exists():
        return ExtensionDeliveryCheckDefinition(
            key="backend-entry",
            label="后端入口",
            status="ready",
            status_label="已就绪",
            message="后端入口文件存在。",
            path=str(backend_file),
        )
    return ExtensionDeliveryCheckDefinition(
        key="backend-entry",
        label="后端入口",
        status="attention",
        status_label="缺失",
        message="manifest 已声明 backend_entry，但 backend/ext.py 不存在。",
        path=str(backend_file or ""),
    )


def _build_frontend_admin_check(root_path: Path | None, definition: ExtensionDefinition) -> ExtensionDeliveryCheckDefinition:
    admin_entry = str(definition.manifest.frontend_admin_entry or "").strip()
    admin_file = root_path / "frontend" / "admin" / "index.js" if root_path else None
    if not admin_entry:
        return ExtensionDeliveryCheckDefinition(
            key="frontend-admin-entry",
            label="后台入口",
            status="pending",
            status_label="未声明",
            message="当前扩展未声明后台前端入口。",
            optional=True,
        )
    if admin_file and admin_file.exists():
        return ExtensionDeliveryCheckDefinition(
            key="frontend-admin-entry",
            label="后台入口",
            status="ready",
            status_label="已就绪",
            message="后台入口文件存在。",
            path=str(admin_file),
        )
    return ExtensionDeliveryCheckDefinition(
        key="frontend-admin-entry",
        label="后台入口",
        status="attention",
        status_label="缺失",
        message="manifest 已声明 frontend_admin_entry，但 frontend/admin/index.js 不存在。",
        path=str(admin_file or ""),
    )


def _build_migration_check(root_path: Path | None, definition: ExtensionDefinition) -> ExtensionDeliveryCheckDefinition:
    migration_namespace = str(definition.manifest.migration_namespace or "").strip()
    migration_dir = root_path / "backend" / "migrations" if root_path else None
    has_migration_dir = bool(migration_dir and migration_dir.exists())

    if migration_namespace and has_migration_dir:
        return ExtensionDeliveryCheckDefinition(
            key="migrations",
            label="迁移资源",
            status="ready",
            status_label="已就绪",
            message="已声明迁移命名空间且迁移目录存在。",
            path=str(migration_dir),
        )
    if migration_namespace and not has_migration_dir:
        return ExtensionDeliveryCheckDefinition(
            key="migrations",
            label="迁移资源",
            status="attention",
            status_label="缺失",
            message="已声明 migration_namespace，但 backend/migrations 目录不存在。",
            path=str(migration_dir or ""),
        )
    if has_migration_dir:
        return ExtensionDeliveryCheckDefinition(
            key="migrations",
            label="迁移资源",
            status="pending",
            status_label="待完善",
            message="迁移目录存在，但 manifest 尚未声明 migration_namespace。",
            path=str(migration_dir),
        )
    return ExtensionDeliveryCheckDefinition(
        key="migrations",
        label="迁移资源",
        status="pending",
        status_label="未声明",
        message="当前扩展尚未声明数据库迁移资源。",
        optional=True,
    )


def _build_documentation_check(root_path: Path | None, definition: ExtensionDefinition) -> ExtensionDeliveryCheckDefinition:
    docs_file = root_path / "docs" / "README.md" if root_path else None
    if docs_file and docs_file.exists():
        return ExtensionDeliveryCheckDefinition(
            key="documentation",
            label="文档资源",
            status="ready",
            status_label="已就绪",
            message="扩展自带 README 文档。",
            path=str(docs_file),
            optional=True,
        )
    if definition.manifest.documentation_url:
        return ExtensionDeliveryCheckDefinition(
            key="documentation",
            label="文档资源",
            status="ready",
            status_label="已链接",
            message="当前扩展通过 documentation_url 提供文档入口。",
            path=definition.manifest.documentation_url,
            optional=True,
        )
    return ExtensionDeliveryCheckDefinition(
        key="documentation",
        label="文档资源",
        status="pending",
        status_label="未提供",
        message="当前扩展尚未提供 README 或 documentation_url。",
        optional=True,
    )


def _build_locale_check(root_path: Path | None) -> ExtensionDeliveryCheckDefinition:
    locale_dir = root_path / "locale" if root_path else None
    if locale_dir and locale_dir.exists():
        files = [item for item in locale_dir.iterdir() if item.is_file() and item.name != ".gitkeep"]
        if files:
            return ExtensionDeliveryCheckDefinition(
                key="locale-assets",
                label="语言资源",
                status="ready",
                status_label="已就绪",
                message="扩展目录中存在语言资源文件。",
                path=str(locale_dir),
                optional=True,
            )
        return ExtensionDeliveryCheckDefinition(
            key="locale-assets",
            label="语言资源",
            status="pending",
            status_label="待补充",
            message="locale 目录存在，但还没有真实语言资源文件。",
            path=str(locale_dir),
            optional=True,
        )
    return ExtensionDeliveryCheckDefinition(
        key="locale-assets",
        label="语言资源",
        status="pending",
        status_label="未提供",
        message="当前扩展未提供语言资源目录。",
        optional=True,
    )


def _build_frontend_forum_check(root_path: Path | None, definition: ExtensionDefinition) -> ExtensionDeliveryCheckDefinition:
    forum_entry = str(definition.manifest.frontend_forum_entry or "").strip()
    if not forum_entry:
        return ExtensionDeliveryCheckDefinition(
            key="frontend-forum-entry",
            label="前台入口",
            status="pending",
            status_label="未声明",
            message="当前扩展尚未声明前台入口。",
            optional=True,
        )

    forum_file = root_path / "frontend" / "forum" / "index.js" if root_path else None
    if forum_file and forum_file.exists():
        return ExtensionDeliveryCheckDefinition(
            key="frontend-forum-entry",
            label="前台入口",
            status="ready",
            status_label="已就绪",
            message="前台入口文件存在。",
            path=str(forum_file),
            optional=True,
        )
    return ExtensionDeliveryCheckDefinition(
        key="frontend-forum-entry",
        label="前台入口",
        status="attention",
        status_label="缺失",
        message="manifest 已声明 frontend_forum_entry，但 frontend/forum/index.js 不存在。",
        path=str(forum_file or ""),
        optional=True,
    )


def _build_uninstall_warnings(
    root_path: Path | None,
    definition: ExtensionDefinition,
    checks: list[ExtensionDeliveryCheckDefinition],
) -> list[str]:
    warnings = [
        "卸载只会移除扩展安装登记，不会自动回滚数据库迁移。",
        "卸载后会移除扩展后台入口、运行能力和相关启停状态。",
    ]

    migration_dir = root_path / "backend" / "migrations" if root_path else None
    has_migrations = bool(str(definition.manifest.migration_namespace or "").strip()) or bool(migration_dir and migration_dir.exists())
    if has_migrations:
        warnings.append("如果该扩展已经执行过数据库迁移，需要由开发者或运维显式处理回滚/清理策略。")

    has_frontend_assets = bool(definition.manifest.frontend_admin_entry or definition.manifest.frontend_forum_entry)
    has_locale_assets = any(item.key == "locale-assets" and item.status == "ready" for item in checks)
    if has_frontend_assets or has_locale_assets:
        warnings.append("如已构建静态资源或语言包产物，卸载后仍可能需要手动清理发布目录中的残留文件。")

    return warnings


def _build_migration_summary(root_path: Path | None, definition: ExtensionDefinition) -> tuple[str, str]:
    migration_namespace = str(definition.manifest.migration_namespace or "").strip()
    migration_dir = root_path / "backend" / "migrations" if root_path else None
    has_migration_dir = bool(migration_dir and migration_dir.exists())

    if migration_namespace and has_migration_dir:
        return "ready", "已声明迁移"
    if migration_namespace and not has_migration_dir:
        return "attention", "迁移目录缺失"
    if has_migration_dir:
        return "pending", "迁移命名空间待声明"
    return "pending", "未声明迁移"
