from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.module_loader import resolve_extension_backend_file
from apps.core.extensions.types import ExtensionDeliveryCheckDefinition
from apps.core.extensions.validation import resolve_bias_version_compatibility


def inspect_extension_runtime(extension: Extension) -> dict:
    root_path = Path(extension.manifest.path) if extension.manifest.path else None
    checks: list[ExtensionDeliveryCheckDefinition] = []
    runtime_issues: list[str] = []

    checks.append(_build_root_check(root_path))
    checks.append(_build_backend_entry_check(root_path, extension))
    checks.append(_build_frontend_admin_check(root_path, extension))
    checks.append(_build_migration_check(root_path, extension))
    checks.append(_build_documentation_check(root_path, extension))
    checks.append(_build_locale_check(root_path))
    checks.append(_build_frontend_forum_check(root_path, extension))
    checks.append(_build_bias_compatibility_check(extension))

    healthy = True
    for check in checks:
        if check.status == "attention" and not check.optional:
            healthy = False
            if check.message:
                runtime_issues.append(check.message)

    uninstall_warnings = _build_uninstall_warnings(root_path, extension, checks)
    migration_state, migration_label = _build_migration_summary(root_path, extension)
    migration_execution = _build_migration_execution_summary(extension)
    migration_plan = _build_migration_plan_summary(root_path, extension)
    if migration_execution:
        migration_state = str(migration_execution.get("state") or migration_state)
        migration_label = str(migration_execution.get("label") or migration_label)

    return {
        "healthy": healthy,
        "migration_state": migration_state,
        "migration_label": migration_label,
        "migration_execution": migration_execution,
        "migration_plan": migration_plan,
        "runtime_issues": tuple(runtime_issues),
        "delivery_checks": tuple(checks),
        "uninstall_warnings": tuple(uninstall_warnings),
    }


def resolve_extension_frontend_admin_entry(extension: Extension) -> str:
    return extension.frontend_admin_entry


def resolve_extension_frontend_forum_entry(extension: Extension) -> str:
    return extension.frontend_forum_entry


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


def _build_backend_entry_check(root_path: Path | None, extension: Extension) -> ExtensionDeliveryCheckDefinition:
    backend_entry = str(extension.manifest.backend_entry or "").strip()
    backend_file = resolve_extension_backend_file(extension) if root_path else None
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
        message="manifest 已声明 backend_entry，但对应后端入口文件不存在。",
        path=str(backend_file or ""),
    )


def _build_frontend_admin_check(root_path: Path | None, extension: Extension) -> ExtensionDeliveryCheckDefinition:
    admin_entry = resolve_extension_frontend_admin_entry(extension)
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
        message="contract 已声明 frontend_admin_entry，但 frontend/admin/index.js 不存在。",
        path=str(admin_file or ""),
    )


def _build_migration_check(root_path: Path | None, extension: Extension) -> ExtensionDeliveryCheckDefinition:
    migration_namespace = str(extension.manifest.migration_namespace or "").strip()
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


def _build_documentation_check(root_path: Path | None, extension: Extension) -> ExtensionDeliveryCheckDefinition:
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
    if extension.manifest.documentation_url:
        return ExtensionDeliveryCheckDefinition(
            key="documentation",
            label="文档资源",
            status="ready",
            status_label="已链接",
            message="当前扩展通过 documentation_url 提供文档入口。",
            path=extension.manifest.documentation_url,
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


def _build_frontend_forum_check(root_path: Path | None, extension: Extension) -> ExtensionDeliveryCheckDefinition:
    forum_entry = resolve_extension_frontend_forum_entry(extension)
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
        source = forum_file.read_text(encoding="utf-8")
        if not _source_exports_extend(source):
            return ExtensionDeliveryCheckDefinition(
                key="frontend-forum-entry",
                label="前台入口",
                status="attention",
                status_label="缺少导出",
                message="frontend/forum/index.js 存在，但没有导出 extend。",
                path=str(forum_file),
                optional=True,
            )
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
        message="contract 已声明 frontend_forum_entry，但 frontend/forum/index.js 不存在。",
        path=str(forum_file or ""),
        optional=True,
    )


def _source_exports_extend(source: str) -> bool:
    return (
        "export const extend" in source
        or "export let extend" in source
        or "export var extend" in source
        or "export { extend" in source
    )


def _build_bias_compatibility_check(extension: Extension) -> ExtensionDeliveryCheckDefinition:
    summary = resolve_bias_version_compatibility(extension.manifest)
    required_range = str(summary["required_range"] or "").strip()
    if not required_range:
        return ExtensionDeliveryCheckDefinition(
            key="bias-compatibility",
            label="Bias 兼容性",
            status="pending",
            status_label="未声明",
            message="当前扩展未声明 Bias 兼容版本范围。",
            optional=True,
        )

    if bool(summary["compatible"]):
        return ExtensionDeliveryCheckDefinition(
            key="bias-compatibility",
            label="Bias 兼容性",
            status="ready",
            status_label="兼容",
            message=f"当前 Bias 版本满足扩展声明的兼容范围 {required_range}。",
            optional=True,
        )

    return ExtensionDeliveryCheckDefinition(
        key="bias-compatibility",
        label="Bias 兼容性",
        status="attention",
        status_label="不兼容",
        message=str(summary["message"] or f"当前 Bias 版本不满足兼容范围 {required_range}。"),
    )


def _build_uninstall_warnings(
    root_path: Path | None,
    extension: Extension,
    checks: list[ExtensionDeliveryCheckDefinition],
) -> list[str]:
    warnings = [
        "卸载只会移除扩展安装登记，不会自动回滚数据库迁移。",
        "卸载后会移除扩展后台入口、运行能力和相关启停状态。",
    ]

    migration_dir = root_path / "backend" / "migrations" if root_path else None
    has_migrations = bool(str(extension.manifest.migration_namespace or "").strip()) or bool(migration_dir and migration_dir.exists())
    if has_migrations:
        warnings.append("如果该扩展已经执行过数据库迁移，需要由开发者或运维显式处理回滚/清理策略。")

    has_frontend_assets = bool(
        resolve_extension_frontend_admin_entry(extension)
        or resolve_extension_frontend_forum_entry(extension)
    )
    has_locale_assets = any(item.key == "locale-assets" and item.status == "ready" for item in checks)
    if has_frontend_assets or has_locale_assets:
        warnings.append("如已构建静态资源或语言包产物，卸载后仍可能需要手动清理发布目录中的残留文件。")

    return warnings


def _build_migration_summary(root_path: Path | None, extension: Extension) -> tuple[str, str]:
    migration_namespace = str(extension.manifest.migration_namespace or "").strip()
    migration_dir = root_path / "backend" / "migrations" if root_path else None
    has_migration_dir = bool(migration_dir and migration_dir.exists())

    if migration_namespace and has_migration_dir:
        return "ready", "已声明迁移"
    if migration_namespace and not has_migration_dir:
        return "attention", "迁移目录缺失"
    if has_migration_dir:
        return "pending", "迁移命名空间待声明"
    return "pending", "未声明迁移"


def _build_migration_execution_summary(extension: Extension) -> dict[str, Any]:
    payload = dict(extension.runtime.backend_hooks or {}).get("run_migrations")
    if not isinstance(payload, dict):
        payload = dict(extension.runtime.migration_execution or {})
    if not isinstance(payload, dict) or not payload:
        return {}

    status = str(payload.get("status") or "").strip()
    summary = {
        "status": status or "pending",
        "status_label": str(payload.get("status_label") or "").strip(),
        "message": str(payload.get("message") or "").strip(),
        "executed_at": str(payload.get("executed_at") or "").strip(),
        "details": dict(payload.get("details") or {}),
    }
    if status == "ok":
        return {
            **summary,
            "state": "applied",
            "label": "最近已执行",
        }
    if status == "skipped":
        return {
            **summary,
            "state": "skipped",
            "label": "最近已跳过",
        }
    if status:
        return {
            **summary,
            "state": "attention",
            "label": "最近执行异常",
        }
    return {}


def _build_migration_plan_summary(root_path: Path | None, extension: Extension) -> dict[str, Any]:
    migration_dir = root_path / "backend" / "migrations" if root_path else None
    if not migration_dir or not migration_dir.exists():
        return {
            "declared_files": [],
            "applied_files": [],
            "pending_files": [],
        }

    declared_files = sorted(
        item.name
        for item in migration_dir.glob("*.py")
        if item.name != "__init__.py"
    )
    applied_files = list(extension.runtime.applied_migration_files or ())

    applied_file_set = set(applied_files)
    pending_files = [item for item in declared_files if item not in applied_file_set]
    return {
        "declared_files": declared_files,
        "applied_files": applied_files,
        "pending_files": pending_files,
    }
