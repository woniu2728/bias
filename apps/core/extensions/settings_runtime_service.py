from __future__ import annotations

from typing import Any

from apps.core.extensions.exceptions import ExtensionNotFoundError
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.manager import get_extension_manager


def get_enabled_extension_settings_definitions(*, include_disabled: bool = True) -> dict[str, dict[str, Any]]:
    host = get_extension_host()
    definitions: dict[str, dict[str, Any]] = {}
    runtime_extension_ids: set[str] = set()
    if host is None:
        return _build_registry_settings_definitions(include_disabled=include_disabled)

    for runtime_view in host.get_extension_views():
        extension = host.get_runtime_extension(runtime_view.extension_id)
        if extension is None:
            continue
        if not include_disabled and not (extension.runtime.installed and extension.runtime.enabled):
            continue
        if not runtime_view.settings_schema:
            continue

        fields = tuple(sorted(runtime_view.settings_schema, key=lambda item: (item.order, item.key)))
        defaults = {
            field.key: field.default
            for field in fields
        }
        defaults.update({
            definition.key: definition.value
            for definition in runtime_view.settings_defaults
        })
        definitions[runtime_view.extension_id] = {
            "extension_id": runtime_view.extension_id,
            "extension_name": extension.name,
            "fields": fields,
            "field_map": {field.key: field for field in fields},
            "defaults": defaults,
            "reset_rules": tuple(runtime_view.settings_reset_rules),
            "frontend_cache_keys": tuple(runtime_view.settings_frontend_cache_keys),
            "theme_variables": tuple(runtime_view.settings_theme_variables),
            "forum_serializations": tuple(runtime_view.settings_forum_serializations),
            "forum_settings_keys": tuple(runtime_view.forum_settings_keys),
        }
        runtime_extension_ids.add(runtime_view.extension_id)

    for extension_id, definition in _build_registry_settings_definitions(
        include_disabled=include_disabled,
    ).items():
        if extension_id not in runtime_extension_ids:
            definitions[extension_id] = definition
    return definitions


def get_extension_settings_definition(extension_id: str) -> dict[str, Any]:
    definitions = get_enabled_extension_settings_definitions()
    normalized = str(extension_id or "").strip()
    if normalized not in definitions:
        raise ExtensionNotFoundError(f"扩展不存在或未声明设置项: {normalized}")
    return definitions[normalized]


def _build_registry_settings_definitions(*, include_disabled: bool) -> dict[str, dict[str, Any]]:
    manager = get_extension_manager()
    definitions: dict[str, dict[str, Any]] = {}
    for extension in manager.get_extensions():
        if not include_disabled and not (extension.runtime.installed and extension.runtime.enabled):
            continue
        if not extension.settings_schema:
            continue
        fields = tuple(sorted(extension.settings_schema, key=lambda item: (item.order, item.key)))
        defaults = {
            field.key: field.default
            for field in fields
        }
        defaults.update({
            definition.key: definition.value
            for definition in extension.settings_defaults
        })
        definitions[extension.id] = {
            "extension_id": extension.id,
            "extension_name": extension.name,
            "fields": fields,
            "field_map": {field.key: field for field in fields},
            "defaults": defaults,
            "reset_rules": tuple(extension.settings_reset_rules),
            "frontend_cache_keys": tuple(extension.settings_frontend_cache_keys),
            "theme_variables": tuple(extension.settings_theme_variables),
            "forum_serializations": tuple(extension.settings_forum_serializations),
            "forum_settings_keys": tuple(extension.forum_settings_keys),
        }
    return definitions
