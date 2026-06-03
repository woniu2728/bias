from __future__ import annotations

import json
import os
from typing import Iterable

from django.db import transaction

from apps.core.models import ExtensionInstallation, Setting


SAFE_MODE_SETTING = "advanced.extension_safe_mode"
SAFE_MODE_EXTENSIONS_SETTING = "advanced.extension_safe_mode_extensions"
BISECT_STATE_SETTING = "extensions_bisect_state"
LOW_MAINTENANCE_SETTING = "advanced.maintenance_mode"
MAINTENANCE_MODE_KEY_SETTING = "advanced.maintenance_mode_key"


def is_extension_safe_mode_enabled() -> bool:
    env_value = os.environ.get("BIAS_EXTENSION_SAFE_MODE")
    if env_value is not None:
        return _parse_bool(env_value)

    record = Setting.objects.filter(key=SAFE_MODE_SETTING).first()
    if record is None:
        return False
    return _parse_bool(record.value)


def get_extension_safe_mode_extension_ids() -> set[str]:
    env_value = os.environ.get("BIAS_EXTENSION_SAFE_MODE_EXTENSIONS")
    if env_value:
        return _normalize_extension_ids(env_value.split(","))

    record = Setting.objects.filter(key=SAFE_MODE_EXTENSIONS_SETTING).first()
    if record is None:
        return set()
    return _normalize_extension_ids(_parse_json_list(record.value))


def is_extension_allowed_in_safe_mode(extension) -> bool:
    if not is_extension_safe_mode_enabled():
        return True
    extension_id = str(getattr(extension, "id", "") or "").strip()
    if not extension_id:
        return False
    if str(getattr(extension, "source", "") or "") == "builtin-module":
        return True
    allowed_ids = get_extension_safe_mode_extension_ids()
    return extension_id in allowed_ids


def serialize_extension_recovery_state() -> dict:
    enabled = is_extension_safe_mode_enabled()
    return {
        "safe_mode": enabled,
        "safe_mode_extensions": sorted(get_extension_safe_mode_extension_ids()) if enabled else [],
        "bisect": get_extension_bisect_state(),
    }


@transaction.atomic
def start_extension_bisect(extension_ids: Iterable[str]) -> dict:
    ids = sorted(_normalize_extension_ids(extension_ids))
    original_enabled = _get_enabled_extension_ids()
    state = {
        "active": bool(ids),
        "ids": ids,
        "original_enabled": original_enabled,
        "low": 0,
        "high": max(len(ids) - 1, 0),
        "current": [],
        "culprit": "",
        "steps": 0,
    }
    state["current"] = _bisect_current_ids(state)
    _save_bisect_state(state)
    if ids:
        _set_low_maintenance_mode(True)
        _rotate_enabled_extensions(state)
    return state


@transaction.atomic
def advance_extension_bisect(issue_present: bool) -> dict:
    state = get_extension_bisect_state()
    if not state.get("active"):
        return state

    ids = list(state.get("ids") or [])
    low = int(state.get("low") or 0)
    high = int(state.get("high") or max(len(ids) - 1, 0))
    midpoint = (low + high) // 2

    if issue_present:
        high = midpoint
    else:
        low = midpoint + 1

    state.update({
        "low": low,
        "high": high,
        "steps": int(state.get("steps") or 0) + 1,
    })
    if low >= high and 0 <= low < len(ids):
        state["active"] = False
        state["culprit"] = ids[low]
        state["current"] = [ids[low]]
        _restore_original_enabled_extensions(state)
        _set_low_maintenance_mode(False)
    else:
        state["current"] = _bisect_current_ids(state)
    _save_bisect_state(state)
    if state.get("active"):
        _rotate_enabled_extensions(state)
    else:
        _reset_runtime_state()
    return state


@transaction.atomic
def stop_extension_bisect() -> dict:
    state = get_extension_bisect_state()
    _restore_original_enabled_extensions(state)
    _set_low_maintenance_mode(False)
    Setting.objects.filter(key=BISECT_STATE_SETTING).delete()
    _reset_runtime_state()
    return _default_bisect_state()


def get_extension_bisect_state() -> dict:
    record = Setting.objects.filter(key=BISECT_STATE_SETTING).first()
    if record is None:
        return _default_bisect_state()
    try:
        state = json.loads(record.value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return _default_bisect_state()
    ids = sorted(_normalize_extension_ids(state.get("ids") or []))
    original_enabled = list(state.get("original_enabled") or ids)
    return {
        "active": bool(state.get("active")) and bool(ids),
        "ids": ids,
        "original_enabled": sorted(_normalize_extension_ids(original_enabled)),
        "low": int(state.get("low") or 0),
        "high": int(state.get("high") or max(len(ids) - 1, 0)),
        "current": list(state.get("current") or []),
        "culprit": str(state.get("culprit") or "").strip(),
        "steps": int(state.get("steps") or 0),
    }


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    try:
        return bool(json.loads(text))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


def _parse_json_list(value) -> list:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, str):
        return [parsed]
    return []


def _normalize_extension_ids(values: Iterable) -> set[str]:
    return {
        str(value or "").strip()
        for value in values
        if str(value or "").strip()
    }


def _bisect_current_ids(state: dict) -> list[str]:
    ids = list(state.get("ids") or [])
    if not ids:
        return []
    low = max(0, int(state.get("low") or 0))
    high = min(len(ids) - 1, int(state.get("high") or len(ids) - 1))
    midpoint = (low + high) // 2
    return ids[low:midpoint + 1]


def _save_bisect_state(state: dict) -> None:
    Setting.objects.update_or_create(
        key=BISECT_STATE_SETTING,
        defaults={"value": json.dumps(state, ensure_ascii=False)},
    )


def _get_enabled_extension_ids() -> list[str]:
    return sorted(_normalize_extension_ids(
        ExtensionInstallation.objects.filter(
            installed=True,
            enabled=True,
        )
        .exclude(source="builtin-module")
        .values_list("extension_id", flat=True)
    ))


def _rotate_enabled_extensions(state: dict) -> None:
    current = set(_normalize_extension_ids(state.get("current") or []))
    candidates = set(_normalize_extension_ids(state.get("ids") or []))
    if not candidates:
        _reset_runtime_state()
        return

    for installation in ExtensionInstallation.objects.filter(extension_id__in=candidates):
        installation.enabled = installation.extension_id in current
        installation.booted = installation.enabled
        installation.save(update_fields=["enabled", "booted", "updated_at"])
    _reset_runtime_state()


def _restore_original_enabled_extensions(state: dict) -> None:
    ids = set(_normalize_extension_ids(state.get("ids") or []))
    original = set(_normalize_extension_ids(state.get("original_enabled") or ids))
    if not ids:
        return
    for installation in ExtensionInstallation.objects.filter(extension_id__in=ids):
        installation.enabled = installation.extension_id in original
        installation.booted = installation.enabled
        installation.save(update_fields=["enabled", "booted", "updated_at"])


def _set_low_maintenance_mode(enabled: bool) -> None:
    Setting.objects.update_or_create(
        key=MAINTENANCE_MODE_KEY_SETTING,
        defaults={"value": json.dumps("low" if enabled else "none")},
    )
    Setting.objects.update_or_create(
        key=LOW_MAINTENANCE_SETTING,
        defaults={"value": json.dumps(bool(enabled))},
    )


def _reset_runtime_state() -> None:
    from apps.core.extensions.lifecycle import reset_extension_runtime_state

    reset_extension_runtime_state()


def _default_bisect_state() -> dict:
    return {
        "active": False,
        "ids": [],
        "original_enabled": [],
        "low": 0,
        "high": 0,
        "current": [],
        "culprit": "",
        "steps": 0,
    }
