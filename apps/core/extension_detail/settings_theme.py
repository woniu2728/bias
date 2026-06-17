from __future__ import annotations


def _build_extension_settings_runtime(runtime_record=None) -> dict:
    from apps.core.extension_detail.debug import _serialize_debug_value
    if runtime_record is None:
        return {
            "defaults": [],
            "reset_rules": [],
            "frontend_cache_keys": [],
            "theme_variables": [],
            "forum_serializations": [],
            "forum_settings_keys": [],
        }

    return {
        "defaults": [
            {
                "key": str(getattr(definition, "key", "") or ""),
                "value": _serialize_debug_value(getattr(definition, "value", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_defaults", ()) or ()
        ],
        "reset_rules": [
            {
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_reset_rules", ()) or ()
        ],
        "frontend_cache_keys": [
            str(key)
            for key in getattr(runtime_record, "settings_frontend_cache_keys", ()) or ()
            if str(key or "").strip()
        ],
        "theme_variables": [
            {
                "name": str(getattr(definition, "name", "") or ""),
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_theme_variables", ()) or ()
        ],
        "forum_serializations": [
            {
                "attribute": str(getattr(definition, "attribute", "") or ""),
                "key": str(getattr(definition, "key", "") or ""),
                "callback": _serialize_debug_value(getattr(definition, "callback", None)),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            }
            for definition in getattr(runtime_record, "settings_forum_serializations", ()) or ()
        ],
        "forum_settings_keys": [
            str(key)
            for key in getattr(runtime_record, "forum_settings_keys", ()) or ()
            if str(key or "").strip()
        ],
    }

def _build_extension_theme_runtime(runtime_record=None) -> dict:
    from apps.core.extension_detail.debug import _serialize_debug_value
    if runtime_record is None:
        return {
            "handlers": [],
            "variables": [],
            "document_attributes": [],
            "head_tags": [],
        }

    handlers = []
    variables = []
    document_attributes = []
    head_tags = []
    for definition in getattr(runtime_record, "theme_handlers", ()) or ():
        payload = getattr(definition, "callback", None)
        payload_value = _serialize_debug_value(payload)
        item = {
            "key": str(getattr(definition, "key", "") or ""),
            "payload": payload_value,
            "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
            "description": str(getattr(definition, "description", "") or ""),
            "order": int(getattr(definition, "order", 100) or 100),
        }
        handlers.append(item)
        if item["key"] == "variables":
            variables.append(payload_value)
        elif item["key"] == "document_attributes":
            document_attributes.append(payload_value)
        elif item["key"] == "head_tag":
            head_tags.append(payload_value)

    return {
        "handlers": sorted(handlers, key=lambda item: (item["order"], item["key"])),
        "variables": variables,
        "document_attributes": document_attributes,
        "head_tags": head_tags,
    }

def _build_extension_system_hooks(runtime_record=None) -> list[dict]:
    if runtime_record is None:
        return []

    groups = (
        ("error.handling", "错误处理", "error_handlers"),
        ("auth", "认证", "auth_handlers"),
        ("csrf", "CSRF", "csrf_handlers"),
        ("filesystem", "文件系统", "filesystem_drivers"),
        ("console", "控制台", "console_commands"),
        ("session", "会话", "session_handlers"),
        ("theme", "主题", "theme_handlers"),
        ("throttle.api", "API 限流", "throttle_api_handlers"),
        ("user", "用户", "user_handlers"),
    )
    hooks = []
    for service, service_label, attribute in groups:
        for definition in getattr(runtime_record, attribute, ()) or ():
            payload = getattr(definition, "callback", None)
            payload_dict = payload if isinstance(payload, dict) else {}
            hooks.append({
                "service": service,
                "service_label": service_label,
                "key": str(getattr(definition, "key", "") or ""),
                "name": str(payload_dict.get("name") or payload_dict.get("route_name") or payload_dict.get("identifier") or ""),
                "module_id": str(getattr(definition, "module_id", "") or getattr(runtime_record, "extension_id", "") or ""),
                "description": str(getattr(definition, "description", "") or payload_dict.get("description") or ""),
                "order": int(getattr(definition, "order", 100) or 100),
            })
    return sorted(hooks, key=lambda item: (item["service"], item["order"], item["key"]))
