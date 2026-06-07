from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apps.core.extensions.backend import inspect_extension_backend_entry
from apps.core.extensions.types import ExtensionManifest
from apps.core.version import APP_VERSION


SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
EXTENSION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPORT_FUNCTION_PATTERN = re.compile(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(")
EXPORT_DECLARATION_PATTERN = re.compile(r"export\s+(?:const|let|var|class)\s+([A-Za-z0-9_]+)\b")
VERSION_RANGE_PATTERN = re.compile(r"^(?:\^|~|>=|<=|>|<)?\d+\.\d+\.\d+$")
API_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
MIGRATION_FILE_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.py$")
MIGRATION_FUNCTION_PATTERN = re.compile(r"^(?:async\s+)?def\s+(apply|run|upgrade)\s*\(", re.MULTILINE)
EXTENSION_SOURCE_SUFFIXES = {".json", ".js", ".jsx", ".ts", ".tsx", ".vue", ".py", ".md", ".css", ".scss", ".less"}
SKIPPED_SOURCE_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "dist", "build", ".venv", "venv"}
EXTERNAL_PROJECT_NAME_PATTERN = re.compile(r"\b" + "fla" + "rum" + r"\b", re.IGNORECASE)
FORBIDDEN_EXTENSION_SOURCE_PATTERNS = (
    (
        "forbidden_low_level_resource_extender",
        re.compile(r"\bResourceExtender\b"),
        "扩展源码不能直接使用 ResourceExtender；请使用 ApiResourceExtender 注册资源、字段、关系、端点和排序。",
    ),
    (
        "forbidden_external_project_name",
        EXTERNAL_PROJECT_NAME_PATTERN,
        "扩展源码不能包含外部项目命名残留；产品命名必须使用 Bias/bias。",
    ),
    (
        "forbidden_core_module_frontend_contribution",
        re.compile(r"\bmoduleId\s*:\s*['\"]core['\"]"),
        "扩展前端贡献不能声明为 core 模块；请使用当前扩展 ID 作为 moduleId，或省略 moduleId 由扩展运行域归属。",
    ),
    (
        "forbidden_legacy_forum_frontend_extender",
        re.compile(r"\bnew\s+Forum(?:Extender)?\s*\("),
        "扩展前台入口不能使用旧 Forum 构造器；请使用 extendForum(...) 声明前台贡献。",
    ),
    (
        "forbidden_legacy_admin_frontend_extender",
        re.compile(r"\bnew\s+Admin(?:(?:Dashboard|Page)?Extender|Dashboard|Page)?\s*\("),
        "扩展后台入口不能使用旧 Admin 构造器；请使用 extendAdmin(...) 声明后台贡献。",
    ),
    (
        "forbidden_legacy_admin_frontend_import",
        re.compile(
            r"import\s*\{[^}]*\bAdmin(?:DashboardExtender|PageExtender|Dashboard|Page|Extender)?\b[^}]*\}\s*from\s*['\"]@bias/admin['\"]",
            re.MULTILINE | re.DOTALL,
        ),
        "扩展后台入口不能导入旧 Admin 构造器；请从 @bias/admin 导入 extendAdmin。",
    ),
    (
        "forbidden_django_app_entry_import",
        re.compile(r"^\s*(?:from|import)\s+apps\.[A-Za-z0-9_]+(?:\.(?:admin|views|tasks|signals)\b|\s+import\s+(?:admin|views|tasks|signals)\b)", re.MULTILINE),
        "扩展后端不能直接导入 Django app 的 admin/views/tasks/signals 入口；请把运行入口声明到扩展 backend 下。",
    ),
)


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

    return collector.build()


def _resolve_frontend_admin_entry(target: ExtensionManifest) -> str:
    return str(getattr(target, "frontend_admin_entry", "") or "").strip()


def _resolve_frontend_forum_entry(target: ExtensionManifest) -> str:
    return str(getattr(target, "frontend_forum_entry", "") or "").strip()


def inspect_frontend_admin_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = _resolve_frontend_admin_entry(manifest)
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
    payload["available_exports"] = _inspect_available_frontend_exports(source)
    return payload


def resolve_admin_surface_implementation(
    manifest: ExtensionManifest,
    surface: str,
    available_exports: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, str | bool]:
    normalized_surface = str(surface or "").strip()
    export_names = {
        "detail": "resolveDetailPage",
        "settings": "resolveSettingsPage",
        "permissions": "resolvePermissionsPage",
        "operations": "resolveOperationsPage",
    }
    export_name = export_names.get(normalized_surface, "")
    export_set = set(available_exports or [])

    if export_name and export_name in export_set:
        return {
            "surface": normalized_surface,
            "mode": "custom",
            "mode_label": "自定义组件",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "settings" and getattr(manifest, "settings_schema", ()):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "自动生成表单",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "permissions" and getattr(manifest, "permissions_pages", ()):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "统一权限宿主",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "operations" and getattr(manifest, "operations_pages", ()) and (
        getattr(manifest, "admin_actions", ()) or getattr(manifest, "runtime_actions", ())
    ):
        return {
            "surface": normalized_surface,
            "mode": "generated",
            "mode_label": "统一操作宿主",
            "export_name": export_name,
            "available": True,
        }

    if normalized_surface == "detail":
        return {
            "surface": normalized_surface,
            "mode": "default",
            "mode_label": "平台默认详情",
            "export_name": export_name,
            "available": True,
        }

    return {
        "surface": normalized_surface,
        "mode": "missing",
        "mode_label": "未提供",
        "export_name": export_name,
        "available": False,
    }


def inspect_frontend_forum_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = _resolve_frontend_forum_entry(manifest)
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "required_exports": ("extend",),
        "optional_exports": (),
        "available_exports": (),
        "exists": False,
        "resolved_path": "",
    }

    if not entry:
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
    payload["available_exports"] = _inspect_available_frontend_exports(source)
    return payload


def inspect_backend_entry(
    manifest: ExtensionManifest,
    *,
    extensions_base_path: Path | None = None,
) -> dict[str, Any]:
    entry = str(manifest.backend_entry or "").strip()
    payload: dict[str, Any] = {
        "entry": entry,
        "entry_type": "missing",
        "exists": False,
        "resolved_path": "",
        "available_hooks": (),
    }

    if not entry:
        return payload

    if not entry.startswith("extensions."):
        payload.update({
            "entry_type": "external",
            "exists": False,
        })
        return payload

    if extensions_base_path is None:
        payload["entry_type"] = "filesystem"
        return payload

    extension_dir = Path(extensions_base_path) / manifest.id
    debug_definition = type("_DebugExtensionDefinition", (), {
        "manifest": type("_DebugManifest", (), {
            "id": manifest.id,
            "backend_entry": entry,
            "path": str(extension_dir),
        })(),
        "source": "filesystem",
    })()
    inspection = inspect_extension_backend_entry(debug_definition)
    payload.update(inspection)
    return payload


def _inspect_available_frontend_exports(source: str) -> tuple[str, ...]:
    return tuple(sorted(set(
        EXPORT_FUNCTION_PATTERN.findall(source)
        + EXPORT_DECLARATION_PATTERN.findall(source)
    )))


def resolve_bias_version_compatibility(manifest: ExtensionManifest, *, current_version: str | None = None) -> dict[str, str | bool]:
    target_version = str(current_version or APP_VERSION or "").strip()
    version_range = str(manifest.compatibility.bias_version or "").strip()
    if not version_range:
        return {
            "compatible": True,
            "current_version": target_version,
            "required_range": "",
            "message": "",
        }

    if not target_version or not SEMVER_PATTERN.match(target_version):
        return {
            "compatible": False,
            "current_version": target_version,
            "required_range": version_range,
            "message": f"当前 Bias 版本 {target_version or '未知'} 无法用于校验扩展兼容范围 {version_range}。",
        }

    if not VERSION_RANGE_PATTERN.match(version_range):
        return {
            "compatible": False,
            "current_version": target_version,
            "required_range": version_range,
            "message": f"扩展声明的 Bias 兼容范围非法：{version_range}。",
        }

    compatible = _matches_simple_version_range(target_version, version_range)
    if compatible:
        return {
            "compatible": True,
            "current_version": target_version,
            "required_range": version_range,
            "message": "",
        }
    return {
        "compatible": False,
        "current_version": target_version,
        "required_range": version_range,
        "message": f"当前 Bias 版本 {target_version} 不满足扩展声明的兼容范围 {version_range}。",
    }


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
    _validate_admin_actions(collector, manifest)
    _validate_admin_page_bindings(collector, manifest)
    _validate_ecosystem_metadata(collector, manifest)
    _validate_runtime_actions(collector, manifest)
    _validate_settings_schema(collector, manifest)
    _validate_django_app_config(collector, manifest)

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
        _validate_extension_source_contracts(collector, manifest, base_path)
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


def _validate_django_app_config(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
    app_config = str(getattr(manifest, "django_app_config", "") or "").strip()
    if not app_config:
        return
    expected_prefix = f"extensions.{manifest.id.replace('-', '_')}.backend.apps."
    if not app_config.startswith(expected_prefix):
        collector.add_error(
            "invalid_django_app_config_namespace",
            f"django_app_config 必须归属当前扩展命名空间，建议使用 {expected_prefix}...AppConfig",
            extension_id=manifest.id,
            field="django_app_config",
        )


def _validate_extension_source_contracts(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    extension_dir = Path(base_path) / manifest.id
    if not extension_dir.exists():
        return

    for file_path in _iter_extension_source_files(extension_dir):
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        relative_path = file_path.relative_to(base_path.parent).as_posix()
        for code, pattern, message in FORBIDDEN_EXTENSION_SOURCE_PATTERNS:
            if pattern.search(source):
                collector.add_error(
                    code,
                    f"{message} 文件: {relative_path}",
                    extension_id=manifest.id,
                    field=relative_path,
                )


def _iter_extension_source_files(extension_dir: Path):
    for file_path in extension_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in SKIPPED_SOURCE_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in EXTENSION_SOURCE_SUFFIXES:
            continue
        yield file_path


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

    has_generated_admin_surface = bool(
        manifest.settings_schema
        or manifest.runtime_actions
        or manifest.admin_actions
    )

    if has_declared_admin_pages and not str(manifest.frontend_admin_entry or "").strip() and not has_generated_admin_surface:
        collector.add_error(
            "missing_frontend_admin_entry_declaration",
            "声明后台页面时必须同时提供 frontend_admin_entry，或通过代码声明生成式后台能力",
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


def _validate_ecosystem_metadata(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
) -> None:
    compatibility = manifest.compatibility
    security = manifest.security
    distribution = manifest.distribution

    allowed_stability = {
        "experimental": "实验性",
        "beta": "测试中",
        "stable": "稳定",
        "deprecated": "废弃中",
        "internal": "内部",
    }
    allowed_channels = {
        "private": "私有分发",
        "bundled": "随平台内置",
        "partner": "合作方分发",
        "public": "公开分发",
    }

    if compatibility.bias_version and not VERSION_RANGE_PATTERN.match(compatibility.bias_version):
        collector.add_error(
            "invalid_bias_version_range",
            "compatibility.bias_version 必须是简单语义化版本约束，例如 ^1.0.0 或 >=1.2.3",
            extension_id=manifest.id,
            field="compatibility.bias_version",
        )

    if not API_VERSION_PATTERN.match(compatibility.api_version):
        collector.add_error(
            "invalid_api_version",
            "compatibility.api_version 必须是主次版本格式，例如 1.0",
            extension_id=manifest.id,
            field="compatibility.api_version",
        )

    if compatibility.api_stability not in allowed_stability:
        collector.add_error(
            "invalid_api_stability",
            f"compatibility.api_stability 不支持: {compatibility.api_stability}",
            extension_id=manifest.id,
            field="compatibility.api_stability",
        )
    elif compatibility.api_stability_label and compatibility.api_stability_label != allowed_stability[compatibility.api_stability]:
        collector.add_warning(
            "mismatched_api_stability_label",
            f"compatibility.api_stability_label 建议与 {compatibility.api_stability} 对应的默认标签保持一致",
            extension_id=manifest.id,
            field="compatibility.api_stability_label",
        )

    if distribution.channel not in allowed_channels:
        collector.add_error(
            "invalid_distribution_channel",
            f"distribution.channel 不支持: {distribution.channel}",
            extension_id=manifest.id,
            field="distribution.channel",
        )
    elif distribution.channel_label and distribution.channel_label != allowed_channels[distribution.channel]:
        collector.add_warning(
            "mismatched_distribution_channel_label",
            f"distribution.channel_label 建议与 {distribution.channel} 对应的默认标签保持一致",
            extension_id=manifest.id,
            field="distribution.channel_label",
        )

    if distribution.signature_url and not distribution.signing_key_id:
        collector.add_warning(
            "signature_url_without_key",
            "distribution.signature_url 已声明，但 signing_key_id 为空",
            extension_id=manifest.id,
            field="distribution.signing_key_id",
        )

    if distribution.signing_key_id and not distribution.signature_url:
        collector.add_warning(
            "signing_key_without_signature_url",
            "distribution.signing_key_id 已声明，但 signature_url 为空",
            extension_id=manifest.id,
            field="distribution.signature_url",
        )

    if security.support_email and "@" not in security.support_email:
        collector.add_error(
            "invalid_security_support_email",
            "security.support_email 必须是有效邮箱格式",
            extension_id=manifest.id,
            field="security.support_email",
        )

    if compatibility.api_stability in {"experimental", "beta"} and not security.capabilities_notice:
        collector.add_warning(
            "missing_security_capabilities_notice",
            "实验性或测试中扩展建议声明 security.capabilities_notice，说明高权限或风险边界",
            extension_id=manifest.id,
            field="security.capabilities_notice",
        )

def _validate_runtime_actions(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
) -> None:
    seen_keys: set[str] = set()
    allowed_tones = {"default", "primary", "subtle", "danger"}

    for action in manifest.runtime_actions:
        if not action.key:
            collector.add_error(
                "invalid_runtime_action",
                "runtime_actions 中的 key 不能为空",
                extension_id=manifest.id,
                field="runtime_actions",
            )
        elif action.key in seen_keys:
            collector.add_error(
                "duplicate_runtime_action_key",
                f"runtime_actions 中存在重复 key: {action.key}",
                extension_id=manifest.id,
                field="runtime_actions",
            )
        else:
            seen_keys.add(action.key)

        if not action.label:
            collector.add_error(
                "invalid_runtime_action",
                "runtime_actions 中的 label 不能为空",
                extension_id=manifest.id,
                field="runtime_actions",
            )

        if not action.hook:
            collector.add_error(
                "invalid_runtime_action",
                "runtime_actions 中的 hook 不能为空",
                extension_id=manifest.id,
                field="runtime_actions",
            )

        if action.tone not in allowed_tones:
            collector.add_error(
                "invalid_runtime_action_tone",
                f"runtime_actions.tone 不支持: {action.tone}",
                extension_id=manifest.id,
                field="runtime_actions",
            )


def _validate_settings_schema(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
) -> None:
    seen_keys: set[str] = set()
    allowed_types = {"text", "textarea", "boolean", "select", "number"}

    for field in manifest.settings_schema:
        if not field.key:
            collector.add_error(
                "invalid_extension_setting",
                "settings_schema 中的 key 不能为空",
                extension_id=manifest.id,
                field="settings_schema",
            )
            continue
        if field.key in seen_keys:
            collector.add_error(
                "duplicate_extension_setting_key",
                f"settings_schema 中存在重复 key: {field.key}",
                extension_id=manifest.id,
                field="settings_schema",
            )
        else:
            seen_keys.add(field.key)

        if not field.label:
            collector.add_error(
                "invalid_extension_setting",
                f"settings_schema.{field.key} 的 label 不能为空",
                extension_id=manifest.id,
                field="settings_schema",
            )

        if field.type not in allowed_types:
            collector.add_error(
                "invalid_extension_setting_type",
                f"settings_schema.{field.key} 的 type 不支持: {field.type}",
                extension_id=manifest.id,
                field="settings_schema",
            )

        if field.type == "select":
            if not field.options:
                collector.add_error(
                    "invalid_extension_setting_options",
                    f"settings_schema.{field.key} 是 select 类型时必须提供 options",
                    extension_id=manifest.id,
                    field="settings_schema",
                )
            option_values = set()
            for option in field.options:
                if not option.value or not option.label:
                    collector.add_error(
                        "invalid_extension_setting_options",
                        f"settings_schema.{field.key} 的 options 必须同时提供 value 和 label",
                        extension_id=manifest.id,
                        field="settings_schema",
                    )
                    continue
                if option.value in option_values:
                    collector.add_error(
                        "duplicate_extension_setting_option",
                        f"settings_schema.{field.key} 的 options 存在重复 value: {option.value}",
                        extension_id=manifest.id,
                        field="settings_schema",
                    )
                option_values.add(option.value)


def _validate_backend_entry(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
    *,
    strict_runtime_hooks: bool,
) -> None:
    debug_payload = inspect_backend_entry(manifest, extensions_base_path=base_path)
    entry = str(debug_payload["entry"] or "").strip()
    requires_backend = bool(entry or manifest.migration_namespace or manifest.runtime_actions)

    if requires_backend and not entry:
        collector.add_error(
            "missing_backend_entry_declaration",
            "声明 migration_namespace 或 runtime_actions 时必须同时提供 backend_entry",
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
    if manifest.migration_namespace and "run_migrations" not in available_hooks:
        collector.add_error(
            "missing_backend_hook",
            "已声明 migration_namespace，但 backend/ext.py 缺少 run_migrations",
            extension_id=manifest.id,
            field="migration_namespace",
        )

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
    expected_entry = f"extensions/{manifest.id}/frontend/admin/index.js"
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
        surface = _resolve_surface_from_export_name(export_name)
        if surface and resolve_admin_surface_implementation(manifest, surface, available_exports).get("mode") == "generated":
            continue
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


def _resolve_surface_from_export_name(export_name: str) -> str:
    return {
        "resolveSettingsPage": "settings",
        "resolvePermissionsPage": "permissions",
        "resolveOperationsPage": "operations",
        "resolveDetailPage": "detail",
    }.get(str(export_name or "").strip(), "")


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
    expected_entry = f"extensions/{manifest.id}/frontend/forum/index.js"
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
    migration_namespace = str(manifest.migration_namespace or "").strip()
    if not migration_namespace:
        return
    expected_namespace = f"extensions.{manifest.id.replace('-', '_')}.backend.migrations"
    if migration_namespace != expected_namespace:
        collector.add_error(
            "invalid_migration_namespace",
            f"migration_namespace 必须指向当前扩展的标准迁移命名空间: {expected_namespace}",
            extension_id=manifest.id,
            field="migration_namespace",
        )
        return

    migration_dir = Path(base_path) / manifest.id / "backend" / "migrations"
    if not migration_dir.exists():
        collector.add_error(
            "missing_extension_migration_dir",
            "已声明 migration_namespace，但 backend/migrations 目录不存在",
            extension_id=manifest.id,
            field="migration_namespace",
        )
        return

    migration_files = sorted(
        item for item in migration_dir.glob("*.py")
        if item.name != "__init__.py"
    )
    if not migration_files:
        collector.add_error(
            "missing_extension_migration_files",
            "已声明 migration_namespace，但 backend/migrations 目录没有可执行迁移文件",
            extension_id=manifest.id,
            field="migration_namespace",
        )
        return

    for file_path in migration_files:
        if not MIGRATION_FILE_PATTERN.match(file_path.name):
            collector.add_warning(
                "invalid_extension_migration_filename",
                f"迁移文件命名建议使用四位编号前缀，例如 0001_initial.py：{file_path.name}",
                extension_id=manifest.id,
                field="migration_namespace",
            )

        source = file_path.read_text(encoding="utf-8")
        if not MIGRATION_FUNCTION_PATTERN.search(source):
            collector.add_error(
                "missing_extension_migration_entrypoint",
                f"迁移文件缺少可执行入口函数 apply/run/upgrade：{file_path.name}",
                extension_id=manifest.id,
                field="migration_namespace",
            )


def _matches_simple_version_range(version: str, version_range: str) -> bool:
    normalized = version_range.strip()
    operator = ""
    for candidate in ("^", "~", ">=", "<=", ">", "<"):
        if normalized.startswith(candidate):
            operator = candidate
            normalized = normalized[len(candidate):]
            break

    current = _parse_semver_tuple(version)
    target = _parse_semver_tuple(normalized)

    if operator == "^":
        if current < target:
            return False
        upper_bound = (target[0] + 1, 0, 0)
        return current < upper_bound
    if operator == "~":
        if current < target:
            return False
        upper_bound = (target[0], target[1] + 1, 0)
        return current < upper_bound
    if operator == ">=":
        return current >= target
    if operator == "<=":
        return current <= target
    if operator == ">":
        return current > target
    if operator == "<":
        return current < target
    return current == target


def _parse_semver_tuple(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.strip().split(".")
    return int(major), int(minor), int(patch)
