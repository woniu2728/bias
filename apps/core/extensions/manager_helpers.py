from __future__ import annotations

import json

from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.product import is_extension_auto_enabled, is_extension_protected


def normalize_lifecycle_result(result, hook_name: str) -> dict:
    from django.utils import timezone

    timestamp = timezone.now().isoformat()
    if result is None:
        return {
            "hook": hook_name,
            "status": "ok",
            "status_label": "已完成",
            "message": f"{hook_name} 已执行。",
            "executed_at": timestamp,
        }
    if isinstance(result, dict):
        payload = dict(result)
        payload.setdefault("hook", hook_name)
        payload.setdefault("status", "ok")
        payload.setdefault("status_label", "已完成")
        payload.setdefault("executed_at", timestamp)
        return payload
    return {
        "hook": hook_name,
        "status": "ok",
        "status_label": "已完成",
        "message": str(result),
        "executed_at": timestamp,
    }


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_extension_status_key(installed: bool, enabled: bool) -> str:
    if not installed:
        return "pending_install"
    if enabled:
        return "active"
    return "disabled"


def coerce_installation_runtime_state(
    extension: Extension,
    *,
    installed: bool,
    enabled: bool,
    booted: bool,
) -> tuple[bool, bool, bool]:
    installed = bool(installed)
    enabled = bool(enabled)
    booted = bool(booted)
    if is_extension_protected(extension) and is_extension_auto_enabled(extension):
        return True, True, True
    return installed, enabled, booted


def build_extension_status_label(installed: bool, enabled: bool) -> str:
    if not installed:
        return "待安装"
    if enabled:
        return "已启用"
    return "已停用"
