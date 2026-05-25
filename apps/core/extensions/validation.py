from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from apps.core.extensions.types import ExtensionManifest


SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
EXTENSION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class ExtensionValidationIssue:
    level: str
    code: str
    message: str
    extension_id: str = ""
    field: str = ""


@dataclass(frozen=True)
class ExtensionValidationResult:
    manifests: tuple[ExtensionManifest, ...] = ()
    issues: tuple[ExtensionValidationIssue, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.issues if item.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.issues if item.level == "warning")

    @property
    def ok(self) -> bool:
        return self.error_count == 0


@dataclass
class ExtensionValidationCollector:
    manifests: list[ExtensionManifest] = field(default_factory=list)
    issues: list[ExtensionValidationIssue] = field(default_factory=list)

    def add_error(self, code: str, message: str, *, extension_id: str = "", field: str = "") -> None:
        self.issues.append(ExtensionValidationIssue(
            level="error",
            code=code,
            message=message,
            extension_id=extension_id,
            field=field,
        ))

    def add_warning(self, code: str, message: str, *, extension_id: str = "", field: str = "") -> None:
        self.issues.append(ExtensionValidationIssue(
            level="warning",
            code=code,
            message=message,
            extension_id=extension_id,
            field=field,
        ))

    def build(self) -> ExtensionValidationResult:
        return ExtensionValidationResult(
            manifests=tuple(self.manifests),
            issues=tuple(self.issues),
        )


def validate_extension_manifests(manifests: list[ExtensionManifest], *, extensions_base_path: Path | None = None) -> ExtensionValidationResult:
    return validate_extension_manifests_with_available_ids(
        manifests,
        available_extension_ids=None,
        extensions_base_path=extensions_base_path,
    )


def validate_extension_manifests_with_available_ids(
    manifests: list[ExtensionManifest],
    *,
    available_extension_ids: set[str] | None,
    extensions_base_path: Path | None = None,
) -> ExtensionValidationResult:
    collector = ExtensionValidationCollector()
    collector.manifests.extend(manifests)

    manifest_ids = {manifest.id for manifest in manifests}
    known_extension_ids = set(available_extension_ids or set()) | manifest_ids
    seen_ids: set[str] = set()
    base_path = Path(extensions_base_path) if extensions_base_path else None

    for manifest in manifests:
        _validate_single_manifest(collector, manifest, seen_ids=seen_ids, base_path=base_path)

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

    return collector.build()


def _validate_single_manifest(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    *,
    seen_ids: set[str],
    base_path: Path | None,
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
        _validate_frontend_admin_entry(collector, manifest, base_path)


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
    entry = str(manifest.frontend_admin_entry or "").strip()
    if not entry:
        return
    if entry.startswith("builtin:"):
        return
    if not entry.startswith("extensions/"):
        collector.add_warning(
            "frontend_admin_entry_outside_extensions",
            "frontend_admin_entry 建议使用 extensions/... 相对仓库根目录的路径",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )
        return

    absolute_path = base_path.parent / entry
    if not absolute_path.exists():
        collector.add_error(
            "missing_frontend_admin_entry",
            f"找不到 frontend_admin_entry 对应文件: {entry}",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )
