from __future__ import annotations

from apps.core.forum_registry import get_forum_registry


ALLOWED_UI_THEME_MODES = {"light", "dark", "system"}


def get_user_preference_definitions(category: str | None = None):
    return get_forum_registry().get_user_preferences(category=category)


def get_default_user_preferences() -> dict[str, bool]:
    return {
        definition.key: bool(definition.default_value)
        for definition in get_user_preference_definitions()
    }


def normalize_user_preferences(values: dict | None) -> dict[str, bool]:
    merged = get_default_user_preferences()
    for key, value in (values or {}).items():
        if key not in merged:
            continue
        merged[key] = bool(value)
    return merged


def normalize_user_ui_preferences(values: dict | None, *, default_locale: str = "zh-CN") -> dict[str, str]:
    normalized = {
        "theme_mode": "system",
        "locale": default_locale or "zh-CN",
    }

    payload = values or {}
    theme_mode = str(payload.get("theme_mode") or normalized["theme_mode"]).strip().lower()
    normalized["theme_mode"] = theme_mode if theme_mode in ALLOWED_UI_THEME_MODES else "system"

    locale = str(payload.get("locale") or normalized["locale"]).strip()
    normalized["locale"] = locale or (default_locale or "zh-CN")
    return normalized


def get_user_preference_value(user, key: str, fallback: bool | None = None) -> bool:
    normalized = normalize_user_preferences(getattr(user, "preferences", None))
    if key in normalized:
        return normalized[key]
    return bool(fallback) if fallback is not None else False


def serialize_user_preferences(user) -> dict:
    normalized = normalize_user_preferences(getattr(user, "preferences", None))
    default_locale = str(getattr(user, "_forum_default_locale", "") or "zh-CN").strip() or "zh-CN"
    ui_values = normalize_user_ui_preferences(getattr(user, "preferences_ui", None), default_locale=default_locale)
    definitions = [
        {
            "key": definition.key,
            "label": definition.label,
            "description": definition.description,
            "category": definition.category,
            "module_id": definition.module_id,
            "value": normalized.get(definition.key, bool(definition.default_value)),
            "default_value": bool(definition.default_value),
        }
        for definition in get_user_preference_definitions()
    ]
    return {
        "values": normalized,
        "ui_values": ui_values,
        "definitions": definitions,
    }
