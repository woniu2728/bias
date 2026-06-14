from __future__ import annotations

from apps.core.extensions.types import ExtensionManifest
from apps.core.extensions.validation_rules import (
    API_VERSION_PATTERN,
    DJANGO_APP_LABEL_PATTERN,
    EXTENSION_ID_PATTERN,
    PACKAGE_NAME_PATTERN,
    VERSION_RANGE_PATTERN,
)
from apps.core.extensions.validation_types import ExtensionValidationCollector


def validate_django_app_config(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
    app_config = str(getattr(manifest, "django_app_config", "") or "").strip()
    app_label = str(getattr(manifest, "django_app_label", "") or "").strip()
    if not app_config:
        if app_label:
            collector.add_error(
                "django_app_label_without_app_config",
                "声明 django_app_label 时必须同时声明 django_app_config，确保模型归属绑定到扩展 AppConfig。",
                extension_id=manifest.id,
                field="django_app_label",
            )
        return
    if app_label and not DJANGO_APP_LABEL_PATTERN.match(app_label):
        collector.add_error(
            "invalid_django_app_label",
            "django_app_label 必须是合法 Django app label，只能包含字母、数字和下划线，且不能以数字开头。",
            extension_id=manifest.id,
            field="django_app_label",
        )
    expected_prefix = f"extensions.{manifest.id.replace('-', '_')}.backend.apps."
    if not app_config.startswith(expected_prefix):
        collector.add_error(
            "invalid_django_app_config_namespace",
            f"django_app_config 必须归属当前扩展命名空间，建议使用 {expected_prefix}...AppConfig",
            extension_id=manifest.id,
            field="django_app_config",
        )


def validate_admin_actions(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
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


def validate_admin_page_bindings(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
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


def validate_ecosystem_metadata(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
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

    if distribution.replacement and not (
        EXTENSION_ID_PATTERN.match(distribution.replacement)
        or PACKAGE_NAME_PATTERN.match(distribution.replacement)
    ):
        collector.add_error(
            "invalid_distribution_replacement",
            "distribution.replacement 必须是 Bias 扩展 ID 或包名形式，例如 vendor/package。",
            extension_id=manifest.id,
            field="distribution.replacement",
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


def validate_runtime_actions(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
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


def validate_settings_schema(collector: ExtensionValidationCollector, manifest: ExtensionManifest) -> None:
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
