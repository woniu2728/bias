from __future__ import annotations

from pathlib import Path
from apps.core.extensions.types import ExtensionManifest
from apps.core.extensions.validation_rules import (
    EXTENSION_ID_PATTERN,
    MIGRATION_FILE_PATTERN,
    SEMVER_PATTERN,
)
from apps.core.extensions.validation_manifest import (
    validate_admin_actions,
    validate_admin_page_bindings,
    validate_django_app_config,
    validate_ecosystem_metadata,
    validate_runtime_actions,
    validate_settings_schema,
)
from apps.core.extensions.validation_source import (
    extension_root_path,
    validate_cross_extension_imports,
    validate_distribution_signature,
    validate_extension_source_contracts,
    validate_manifest_field_contracts,
)
from apps.core.extensions.validation_types import (
    ExtensionValidationCollector,
    ExtensionValidationIssue,
    ExtensionValidationResult,
)
from apps.core.extensions.validation_inspection import (
    build_required_frontend_admin_exports,
    expected_frontend_entry,
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    resolve_admin_surface_implementation,
    resolve_surface_from_export_name,
)
from apps.core.extensions.version_compatibility import resolve_bias_version_compatibility


def validate_extension_manifests(manifests: list[ExtensionManifest], *, extensions_base_path: Path | None = None) -> ExtensionValidationResult:
    return validate_extension_manifests_with_available_ids(
        manifests,
        available_extension_ids=None,
        extensions_base_path=extensions_base_path,
        strict_runtime_hooks=False,
    )


def validate_extension_manifests_with_available_ids(
    manifests: list[ExtensionManifest],
    *,
    available_extension_ids: set[str] | None,
    extensions_base_path: Path | None = None,
    strict_runtime_hooks: bool = False,
) -> ExtensionValidationResult:
    collector = ExtensionValidationCollector()
    collector.manifests.extend(manifests)

    manifest_ids = {manifest.id for manifest in manifests}
    known_extension_ids = set(available_extension_ids or set()) | manifest_ids
    seen_ids: set[str] = set()
    base_path = Path(extensions_base_path) if extensions_base_path else None

    for manifest in manifests:
        _validate_single_manifest(
            collector,
            manifest,
            seen_ids=seen_ids,
            base_path=base_path,
            strict_runtime_hooks=strict_runtime_hooks,
        )

    for manifest in manifests:
        for dependency in manifest.dependencies:
            if dependency not in known_extension_ids:
                collector.add_error(
                    "missing_dependency",
                    f"必需依赖不存在: {dependency}",
                    extension_id=manifest.id,
                    field="dependencies",
                )
        for conflict in manifest.conflicts:
            if conflict == manifest.id:
                collector.add_error(
                    "self_conflict",
                    "扩展不能把自己声明为冲突项",
                    extension_id=manifest.id,
                    field="conflicts",
                )

    if base_path is not None:
        for manifest in manifests:
            validate_cross_extension_imports(
                collector,
                manifest,
                base_path,
                known_extension_ids=known_extension_ids,
            )

    return collector.build()

def _validate_single_manifest(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    *,
    seen_ids: set[str],
    base_path: Path | None,
    strict_runtime_hooks: bool,
) -> None:
    if manifest.id in seen_ids:
        collector.add_error(
            "duplicate_extension_id",
            f"扩展 ID 重复: {manifest.id}",
            extension_id=manifest.id,
            field="id",
        )
    else:
        seen_ids.add(manifest.id)

    if not EXTENSION_ID_PATTERN.match(manifest.id):
        collector.add_error(
            "invalid_extension_id",
            "扩展 ID 只能包含小写字母、数字和中划线，且不能以中划线开头或结尾",
            extension_id=manifest.id,
            field="id",
        )

    if not SEMVER_PATTERN.match(manifest.version):
        collector.add_error(
            "invalid_extension_version",
            "扩展版本号必须是 X.Y.Z 形式的语义化版本",
            extension_id=manifest.id,
            field="version",
        )

    _validate_unique_strings(collector, manifest, "dependencies", manifest.dependencies)
    _validate_unique_strings(collector, manifest, "optional_dependencies", manifest.optional_dependencies)
    _validate_unique_strings(collector, manifest, "conflicts", manifest.conflicts)
    _validate_unique_strings(collector, manifest, "provides", manifest.provides)
    _validate_unique_strings(collector, manifest, "settings_pages", manifest.settings_pages)
    _validate_unique_strings(collector, manifest, "permissions_pages", manifest.permissions_pages)
    _validate_unique_strings(collector, manifest, "operations_pages", manifest.operations_pages)
    validate_admin_actions(collector, manifest)
    validate_admin_page_bindings(collector, manifest)
    validate_ecosystem_metadata(collector, manifest)
    validate_runtime_actions(collector, manifest)
    validate_settings_schema(collector, manifest)
    validate_django_app_config(collector, manifest)

    for field_name, pages in (
        ("settings_pages", manifest.settings_pages),
        ("permissions_pages", manifest.permissions_pages),
        ("operations_pages", manifest.operations_pages),
    ):
        for page in pages:
            if not page.startswith("/admin/extensions/"):
                collector.add_warning(
                    "non_extension_admin_page",
                    f"{field_name} 建议使用 /admin/extensions/... 作为扩展后台入口",
                    extension_id=manifest.id,
                    field=field_name,
                )

    if base_path is not None:
        validate_manifest_field_contracts(collector, manifest, base_path)
        validate_extension_source_contracts(collector, manifest, base_path)
        validate_distribution_signature(collector, manifest, base_path)
        _validate_frontend_admin_entry(collector, manifest, base_path)
        _validate_frontend_forum_entry(collector, manifest, base_path)
        _validate_backend_entry(
            collector,
            manifest,
            base_path,
            strict_runtime_hooks=strict_runtime_hooks,
        )
        _validate_migration_files(
            collector,
            manifest,
            base_path,
        )

def _validate_backend_entry(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
    *,
    strict_runtime_hooks: bool,
) -> None:
    debug_payload = inspect_backend_entry(manifest, extensions_base_path=base_path)
    entry = str(debug_payload["entry"] or "").strip()
    requires_backend = bool(entry or manifest.runtime_actions)

    if requires_backend and not entry:
        collector.add_error(
            "missing_backend_entry_declaration",
            "声明 runtime_actions 时必须同时提供 backend_entry",
            extension_id=manifest.id,
            field="backend_entry",
        )
        return

    if not entry:
        return
    if debug_payload["entry_type"] == "external":
        collector.add_warning(
            "backend_entry_outside_extensions",
            "backend_entry 建议使用 extensions.<extension_id>.backend.ext 形式的扩展入口",
            extension_id=manifest.id,
            field="backend_entry",
        )
        return
    expected_backend_prefix = f"extensions.{manifest.id.replace('-', '_')}.backend."
    if not entry.startswith(expected_backend_prefix):
        collector.add_error(
            "invalid_backend_entry_namespace",
            f"backend_entry 必须归属当前扩展命名空间，建议使用 {expected_backend_prefix}...",
            extension_id=manifest.id,
            field="backend_entry",
        )
        return
    if not debug_payload["exists"]:
        collector.add_error(
            "missing_backend_entry",
            f"找不到 backend_entry 对应文件: {entry}",
            extension_id=manifest.id,
            field="backend_entry",
        )
        return

    if not strict_runtime_hooks:
        return

    available_hooks = set(debug_payload["available_hooks"])
    for action in manifest.runtime_actions:
        if action.hook and action.hook not in available_hooks:
            collector.add_error(
                "missing_backend_hook",
                f"runtime_actions 声明的后端钩子不存在: {action.hook}",
                extension_id=manifest.id,
                field="runtime_actions",
            )


def _validate_unique_strings(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    field_name: str,
    values: tuple[str, ...],
) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            collector.add_error(
                "duplicate_manifest_value",
                f"{field_name} 中存在重复值: {value}",
                extension_id=manifest.id,
                field=field_name,
            )
        else:
            seen.add(value)


def _validate_frontend_admin_entry(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    debug_payload = inspect_frontend_admin_entry(manifest, extensions_base_path=base_path)
    entry = str(debug_payload["entry"] or "").strip()
    if not entry:
        return
    if debug_payload["entry_type"] == "external":
        collector.add_warning(
            "frontend_admin_entry_outside_extensions",
            "frontend_admin_entry 建议使用 extensions/... 相对仓库根目录的路径",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )
        return
    expected_entry = expected_frontend_entry(manifest, base_path, "admin")
    if entry != expected_entry:
        collector.add_error(
            "invalid_frontend_admin_entry_path",
            f"frontend_admin_entry 必须指向当前扩展的标准后台入口: {expected_entry}",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )
        return

    if not debug_payload["exists"]:
        collector.add_error(
            "missing_frontend_admin_entry",
            f"找不到 frontend_admin_entry 对应文件: {entry}",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )
        return

    required_exports = list(debug_payload["required_exports"])
    available_exports = set(debug_payload["available_exports"])

    if not required_exports and "resolveDetailPage" not in available_exports:
        collector.add_warning(
            "missing_frontend_admin_detail_export",
            "frontend_admin_entry 未导出 resolveDetailPage，扩展详情页将回退到平台默认视图",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )

    for export_name in required_exports:
        surface = resolve_surface_from_export_name(export_name)
        if surface and resolve_admin_surface_implementation(manifest, surface, available_exports).get("mode") == "generated":
            continue
        if export_name not in available_exports:
            collector.add_error(
                "missing_frontend_admin_export",
                f"frontend_admin_entry 缺少导出函数: {export_name}",
                extension_id=manifest.id,
                field="frontend_admin_entry",
            )


def _validate_frontend_forum_entry(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    debug_payload = inspect_frontend_forum_entry(manifest, extensions_base_path=base_path)
    entry = str(debug_payload["entry"] or "").strip()
    if not entry:
        return
    if debug_payload["entry_type"] == "external":
        collector.add_warning(
            "frontend_forum_entry_outside_extensions",
            "frontend_forum_entry 建议使用 extensions/... 相对仓库根目录的路径",
            extension_id=manifest.id,
            field="frontend_forum_entry",
        )
        return
    expected_entry = expected_frontend_entry(manifest, base_path, "forum")
    if entry != expected_entry:
        collector.add_error(
            "invalid_frontend_forum_entry_path",
            f"frontend_forum_entry 必须指向当前扩展的标准前台入口: {expected_entry}",
            extension_id=manifest.id,
            field="frontend_forum_entry",
        )
        return

    if not debug_payload["exists"]:
        collector.add_error(
            "missing_frontend_forum_entry",
            f"找不到 frontend_forum_entry 对应文件: {entry}",
            extension_id=manifest.id,
            field="frontend_forum_entry",
        )
        return

    required_exports = list(debug_payload["required_exports"])
    available_exports = set(debug_payload["available_exports"])
    for export_name in required_exports:
        if export_name not in available_exports:
            collector.add_error(
                "missing_frontend_forum_export",
                f"frontend_forum_entry 缺少导出: {export_name}",
                extension_id=manifest.id,
                field="frontend_forum_entry",
            )


def _validate_migration_files(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    extension_root = extension_root_path(manifest, base_path)
    legacy_migration_dir = extension_root / "backend" / "migrations"
    if legacy_migration_dir.exists():
        collector.add_error(
            "legacy_extension_migration_dir",
            "扩展不能继续使用 legacy backend/migrations；请迁移到 backend/django_migrations 并通过 django_app_config 接入 Django。",
            extension_id=manifest.id,
            field="django_app_config",
        )

    django_app_config = str(manifest.django_app_config or "").strip()
    migration_dir = extension_root / "backend" / "django_migrations"
    if not django_app_config:
        if migration_dir.exists():
            collector.add_error(
                "django_migrations_without_app_config",
                "扩展提供了 backend/django_migrations，但 manifest 未声明 django_app_config。",
                extension_id=manifest.id,
                field="django_app_config",
            )
        return

    if not migration_dir.exists():
        collector.add_error(
            "missing_extension_django_migration_dir",
            "manifest 已声明 django_app_config，但 backend/django_migrations 目录不存在",
            extension_id=manifest.id,
            field="django_app_config",
        )
        return

    init_file = migration_dir / "__init__.py"
    if not init_file.exists():
        collector.add_error(
            "missing_extension_django_migration_package",
            "backend/django_migrations 缺少 __init__.py",
            extension_id=manifest.id,
            field="django_app_config",
        )
        return

    migration_files = sorted(
        item for item in migration_dir.glob("*.py")
        if item.name != "__init__.py"
    )
    if not migration_files:
        return

    for file_path in migration_files:
        if not MIGRATION_FILE_PATTERN.match(file_path.name):
            collector.add_warning(
                "invalid_extension_migration_filename",
                f"迁移文件命名建议使用四位编号前缀，例如 0001_initial.py：{file_path.name}",
                extension_id=manifest.id,
                field="django_app_config",
            )
