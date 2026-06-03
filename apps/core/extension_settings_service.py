from __future__ import annotations

import json
from typing import Any

from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.settings_runtime_service import get_extension_settings_definition
from apps.core.models import Setting


ALLOWED_EXTENSION_SETTING_TYPES = {
    "text",
    "textarea",
    "boolean",
    "select",
    "number",
}


def build_extension_settings_defaults(extension_id: str) -> dict[str, Any]:
    try:
        definition = get_extension_settings_definition(extension_id)
    except ExtensionNotFoundError:
        return {}
    return dict(definition["defaults"])


def get_extension_settings(extension_id: str) -> dict[str, Any]:
    defaults = build_extension_settings_defaults(extension_id)
    values = defaults.copy()
    if not defaults:
        return values

    prefix = _build_extension_settings_prefix(extension_id)
    setting_keys = [f"{prefix}{key}" for key in defaults.keys()]
    for setting in Setting.objects.filter(key__in=setting_keys):
        key = setting.key.removeprefix(prefix)
        try:
            values[key] = json.loads(setting.value)
        except json.JSONDecodeError:
            values[key] = setting.value
    return values


def save_extension_settings(extension_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    definition = get_extension_settings_definition(extension_id)
    schema_map = dict(definition["field_map"])
    normalized = get_extension_settings(extension_id)
    prefix = _build_extension_settings_prefix(extension_id)

    for key, raw_value in dict(payload or {}).items():
        field = schema_map.get(key)
        if field is None:
            raise ExtensionStateError(
                f"扩展 {extension_id} 不支持设置项 {key}",
                code="extension_settings_unknown_key",
                details={"extension_id": extension_id, "key": key},
            )
        normalized_value = _normalize_extension_setting_value(field, raw_value)
        normalized[key] = normalized_value
        Setting.objects.update_or_create(
            key=f"{prefix}{key}",
            defaults={"value": json.dumps(normalized_value, ensure_ascii=False)},
        )

    return normalized


def serialize_extension_settings_schema(extension_id: str) -> list[dict[str, Any]]:
    try:
        definition = get_extension_settings_definition(extension_id)
    except ExtensionNotFoundError:
        return []
    return [
        {
            "key": field.key,
            "label": field.label,
            "type": field.type,
            "default": field.default,
            "help_text": field.help_text,
            "placeholder": field.placeholder,
            "required": field.required,
            "multiline": field.multiline,
            "order": field.order,
            "options": [
                {
                    "value": option.value,
                    "label": option.label,
                }
                for option in field.options
            ],
        }
        for field in definition["fields"]
    ]


def _build_extension_settings_prefix(extension_id: str) -> str:
    return f"extensions.{extension_id}."


def _normalize_extension_setting_value(field, value: Any) -> Any:
    if field.type not in ALLOWED_EXTENSION_SETTING_TYPES:
        raise ExtensionStateError(
            f"扩展设置项 {field.key} 的类型 {field.type} 暂不支持",
            code="extension_settings_unsupported_type",
            details={"key": field.key, "type": field.type},
        )

    if field.type == "boolean":
        return bool(value)
    if field.type == "number":
        if value in ("", None):
            if field.required:
                raise ExtensionStateError(
                    f"扩展设置项 {field.key} 不能为空",
                    code="extension_settings_required",
                    details={"key": field.key},
                )
            return field.default
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ExtensionStateError(
                f"扩展设置项 {field.key} 必须是数字",
                code="extension_settings_invalid_number",
                details={"key": field.key},
            ) from exc

    normalized = str(value or "").strip()
    if field.required and not normalized:
        raise ExtensionStateError(
            f"扩展设置项 {field.key} 不能为空",
            code="extension_settings_required",
            details={"key": field.key},
        )

    if field.type == "select":
        allowed_values = {option.value for option in field.options}
        if normalized and normalized not in allowed_values:
            raise ExtensionStateError(
                f"扩展设置项 {field.key} 的值不合法",
                code="extension_settings_invalid_option",
                details={"key": field.key, "value": normalized},
            )
    return normalized
