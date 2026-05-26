from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apps.core.extensions.types import ExtensionManifest


SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
EXTENSION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPORT_FUNCTION_PATTERN = re.compile(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(")


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


def inspect_frontend_admin_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = str(manifest.frontend_admin_entry or "").strip()
    required_exports = _build_required_frontend_admin_exports(manifest)
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "required_exports": tuple(required_exports),
        "optional_exports": ("resolveDetailPage",),
        "available_exports": (),
        "exists": False,
        "resolved_path": "",
    }

    if not entry:
        return payload

    if entry.startswith("builtin:"):
        payload.update({
            "entry_type": "builtin",
            "exists": True,
        })
        return payload

    if not entry.startswith("extensions/"):
        payload.update({
            "entry_type": "external",
            "exists": False,
        })
        return payload

    if extensions_base_path is None:
        payload.update({
            "entry_type": "filesystem",
            "exists": False,
        })
        return payload

    absolute_path = Path(extensions_base_path).parent / entry
    payload.update({
        "entry_type": "filesystem",
        "exists": absolute_path.exists(),
        "resolved_path": str(absolute_path),
    })

    if not absolute_path.exists():
        return payload

    source = absolute_path.read_text(encoding="utf-8")
    payload["available_exports"] = tuple(sorted(set(EXPORT_FUNCTION_PATTERN.findall(source))))
    return payload


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
    _validate_admin_actions(collector, manifest)
    _validate_admin_page_bindings(collector, manifest)

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


def _validate_admin_actions(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
) -> None:
    seen_keys: set[str] = set()
    allowed_kinds = {"route", "link"}
    allowed_tones = {"default", "primary", "subtle", "danger"}

    for action in manifest.admin_actions:
        if not action.key:
            collector.add_error(
                "invalid_admin_action",
                "admin_actions 中的 key 不能为空",
                extension_id=manifest.id,
                field="admin_actions",
            )
        elif action.key in seen_keys:
            collector.add_error(
                "duplicate_admin_action_key",
                f"admin_actions 中存在重复 key: {action.key}",
                extension_id=manifest.id,
                field="admin_actions",
            )
        else:
            seen_keys.add(action.key)

        if not action.label:
            collector.add_error(
                "invalid_admin_action",
                "admin_actions 中的 label 不能为空",
                extension_id=manifest.id,
                field="admin_actions",
            )

        if action.kind not in allowed_kinds:
            collector.add_error(
                "invalid_admin_action_kind",
                f"admin_actions.kind 不支持: {action.kind}",
                extension_id=manifest.id,
                field="admin_actions",
            )

        if action.tone not in allowed_tones:
            collector.add_error(
                "invalid_admin_action_tone",
                f"admin_actions.tone 不支持: {action.tone}",
                extension_id=manifest.id,
                field="admin_actions",
            )

        if not action.target:
            collector.add_error(
                "invalid_admin_action",
                "admin_actions 中的 target 不能为空",
                extension_id=manifest.id,
                field="admin_actions",
            )
            continue

        if action.kind == "route" and not action.target.startswith("/"):
            collector.add_error(
                "invalid_admin_action_target",
                "route 类型的 admin_actions.target 必须以 / 开头",
                extension_id=manifest.id,
                field="admin_actions",
            )


def _validate_admin_page_bindings(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
) -> None:
    admin_page_fields = (
        ("settings_pages", manifest.settings_pages, "settings"),
        ("permissions_pages", manifest.permissions_pages, "permissions"),
        ("operations_pages", manifest.operations_pages, "operations"),
    )
    has_declared_admin_pages = any(pages for _, pages, _ in admin_page_fields)

    if has_declared_admin_pages and not str(manifest.frontend_admin_entry or "").strip():
        collector.add_error(
            "missing_frontend_admin_entry_declaration",
            "声明后台页面时必须同时提供 frontend_admin_entry",
            extension_id=manifest.id,
            field="frontend_admin_entry",
        )

    for field_name, pages, surface in admin_page_fields:
        expected_path = f"/admin/extensions/{manifest.id}/{surface}"
        for page in pages:
            if page.startswith("/admin/extensions/") and page != expected_path:
                collector.add_error(
                    "invalid_extension_admin_page",
                    f"{field_name} 必须指向当前扩展的标准后台入口: {expected_path}",
                    extension_id=manifest.id,
                    field=field_name,
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
    if debug_payload["entry_type"] == "builtin":
        return
    if debug_payload["entry_type"] == "external":
        collector.add_warning(
            "frontend_admin_entry_outside_extensions",
            "frontend_admin_entry 建议使用 extensions/... 相对仓库根目录的路径",
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
        if export_name not in available_exports:
            collector.add_error(
                "missing_frontend_admin_export",
                f"frontend_admin_entry 缺少导出函数: {export_name}",
                extension_id=manifest.id,
                field="frontend_admin_entry",
            )


def _build_required_frontend_admin_exports(manifest: ExtensionManifest) -> list[str]:
    required_exports = []
    if manifest.settings_pages:
        required_exports.append("resolveSettingsPage")
    if manifest.permissions_pages:
        required_exports.append("resolvePermissionsPage")
    if manifest.operations_pages:
        required_exports.append("resolveOperationsPage")
    return required_exports
