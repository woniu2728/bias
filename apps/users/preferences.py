from __future__ import annotations

from apps.core.forum_registry import get_forum_registry


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


def get_user_preference_value(user, key: str, fallback: bool | None = None) -> bool:
    normalized = normalize_user_preferences(getattr(user, "preferences", None))
    if key in normalized:
        return normalized[key]
    return bool(fallback) if fallback is not None else False


def serialize_user_preferences(user) -> dict:
    normalized = normalize_user_preferences(getattr(user, "preferences", None))
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
        "definitions": definitions,
    }
