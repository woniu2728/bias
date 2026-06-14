"""
论坛设置读取与保存服务
"""
import json
from types import SimpleNamespace

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError

from apps.core.bootstrap_config import (
    _is_test_process,
    get_site_config_path,
    load_site_bootstrap,
    read_site_config,
    write_site_config,
)
from apps.core.extensions.runtime_service import (
    get_enabled_extension_locales,
    get_enabled_extension_runtime_entries,
)
from apps.core.extensions.frontend_runtime_service import build_enabled_frontend_document_payload
from apps.core.extensions.recovery import serialize_extension_recovery_state
from apps.core.mail_drivers import serialize_mail_settings
from apps.core.models import Setting
from apps.core.forum_registry import get_forum_registry


ADVANCED_SETTINGS_CACHE_KEY = "settings.group.advanced"
PUBLIC_FORUM_SETTINGS_CACHE_KEY = "settings.public.forum"
ADVANCED_SETTINGS_CACHE_TIMEOUT_SECONDS = 60
_EXTENSION_SETTING_GROUP_DEFAULTS_CACHE: dict[str, dict] = {}


def _get_forum_registry():
    return get_forum_registry()


BASIC_SETTINGS_DEFAULTS = {
    "forum_title": "Bias",
    "forum_description": "",
    "seo_title": "",
    "seo_description": "",
    "seo_keywords": "",
    "seo_robots_index": True,
    "seo_robots_follow": True,
    "announcement_enabled": False,
    "announcement_message": "",
    "announcement_tone": "info",
}

APPEARANCE_SETTINGS_DEFAULTS = {
    "primary_color": "#4d698e",
    "accent_color": "#e74c3c",
    "logo_url": "",
    "favicon_url": "",
    "custom_head_html": "",
    "custom_footer_html": "",
}

MAIL_SETTINGS_STATIC_DEFAULTS = {
    "mail_driver": "smtp",
    "mail_format": "multipart",
    "mail_password": "",
    "mail_from_name": "Bias",
    "mail_test_recipient": "",
}

ADVANCED_SETTINGS_DEFAULTS = {
    "cache_driver": "redis" if "redis" in settings.CACHES.get("default", {}).get("BACKEND", "").lower() else "file",
    "cache_lifetime": 3600,
    "queue_driver": "redis" if "redis" in getattr(settings, "CELERY_BROKER_URL", "") else "sync",
    "queue_enabled": False,
    "maintenance_mode": False,
    "maintenance_mode_key": "none",
    "maintenance_message": "论坛正在维护中，请稍后再试...",
    "extension_safe_mode": False,
    "extension_safe_mode_extensions": [],
    "debug_mode": settings.DEBUG,
    "log_queries": False,
}


def get_setting_group(prefix: str, defaults: dict) -> dict:
    values = defaults.copy()
    found_keys = set()
    try:
        stored_settings = Setting.objects.filter(
            key__in=[f"{prefix}.{key}" for key in defaults.keys()]
        )
    except (OperationalError, ProgrammingError):
        return values

    try:
        for setting in stored_settings:
            key = setting.key.split(".", 1)[1]
            found_keys.add(key)
            try:
                values[key] = json.loads(setting.value)
            except json.JSONDecodeError:
                values[key] = setting.value
    except (OperationalError, ProgrammingError):
        return defaults.copy()

    return values


def get_mail_settings_defaults() -> dict:
    mail_defaults = MAIL_SETTINGS_STATIC_DEFAULTS.copy()
    mail_defaults.update(get_extension_mail_setting_defaults())

    site_config = None
    try:
        config_path = get_site_config_path(settings.BASE_DIR)
        if config_path.exists():
            site_config = read_site_config(config_path)
    except Exception:
        site_config = None

    if site_config is not None:
        mail_defaults.update({
            "mail_host": site_config.email_host or "smtp.gmail.com",
            "mail_port": int(site_config.email_port or 587),
            "mail_encryption": "tls" if site_config.email_use_tls else "",
            "mail_username": site_config.email_host_user or "",
            "mail_from_address": site_config.default_from_email or "",
        })
    else:
        mail_defaults.update({
            "mail_host": getattr(settings, "EMAIL_HOST", "smtp.gmail.com") or "smtp.gmail.com",
            "mail_port": getattr(settings, "EMAIL_PORT", 587) or 587,
            "mail_encryption": (
                "ssl"
                if getattr(settings, "EMAIL_USE_SSL", False)
                else "tls"
            ),
            "mail_username": getattr(settings, "EMAIL_HOST_USER", ""),
            "mail_from_address": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        })

    return mail_defaults


def get_extension_mail_setting_defaults() -> dict:
    return get_extension_setting_group_defaults("mail")


def get_advanced_settings_defaults() -> dict:
    defaults = ADVANCED_SETTINGS_DEFAULTS.copy()
    defaults.update(get_extension_setting_group_defaults("advanced"))
    return defaults


def get_extension_setting_group_defaults(prefix: str) -> dict:
    normalized_prefix = str(prefix or "").strip()
    if normalized_prefix in _EXTENSION_SETTING_GROUP_DEFAULTS_CACHE:
        return _EXTENSION_SETTING_GROUP_DEFAULTS_CACHE[normalized_prefix].copy()

    defaults = {}

    def collect(definitions) -> None:
        for definition in definitions or ():
            key = str(getattr(definition, "key", "") or "").strip()
            if not key.startswith(f"{normalized_prefix}."):
                continue
            defaults[key.split(".", 1)[1]] = getattr(definition, "value", None)

    try:
        from apps.core.extensions.bootstrap import get_extension_host

        host = get_extension_host()
        if host is not None:
            extension_map = {
                extension.id: extension
                for extension in host.get_runtime_extensions()
            }
            for runtime_view in host.get_extension_views():
                extension = extension_map.get(runtime_view.extension_id)
                if extension is None or not getattr(extension.runtime, "enabled", False):
                    continue
                collect(getattr(runtime_view, "settings_defaults", ()) or ())
            _EXTENSION_SETTING_GROUP_DEFAULTS_CACHE[normalized_prefix] = defaults.copy()
            return defaults
    except Exception:
        pass

    loaded_from_manager = False
    try:
        from apps.core.extensions.manager import get_extension_manager

        for extension in get_extension_manager().get_extensions():
            if not getattr(extension.runtime, "enabled", False):
                continue
            collect(getattr(extension, "settings_defaults", ()) or ())
        loaded_from_manager = True
    except Exception:
        pass
    if loaded_from_manager:
        _EXTENSION_SETTING_GROUP_DEFAULTS_CACHE[normalized_prefix] = defaults.copy()
    return defaults


def get_mail_settings() -> dict:
    return serialize_mail_settings(get_setting_group("mail", get_mail_settings_defaults()))


def sync_mail_settings_to_site_config(mail_settings: dict) -> str | None:
    config_path = get_site_config_path(settings.BASE_DIR)
    if config_path.exists():
        site_config = read_site_config(config_path)
    else:
        if _is_test_process():
            return None
        site_config = load_site_bootstrap(settings.BASE_DIR)

    encryption = str(mail_settings.get("mail_encryption") or "").strip().lower()

    site_config.email_backend = "django.core.mail.backends.smtp.EmailBackend"
    site_config.email_host = str(mail_settings.get("mail_host") or site_config.email_host or "smtp.gmail.com").strip()
    try:
        site_config.email_port = int(mail_settings.get("mail_port") or site_config.email_port or 587)
    except (TypeError, ValueError):
        site_config.email_port = 587
    site_config.email_use_tls = encryption == "tls"
    site_config.email_host_user = str(mail_settings.get("mail_username") or "").strip()
    site_config.email_host_password = str(mail_settings.get("mail_password") or "").strip()
    site_config.default_from_email = str(
        mail_settings.get("mail_from_address") or site_config.default_from_email or ""
    ).strip()

    write_site_config(config_path, site_config)
    return str(config_path)


def clear_runtime_setting_caches():
    _EXTENSION_SETTING_GROUP_DEFAULTS_CACHE.clear()
    _cache_delete(ADVANCED_SETTINGS_CACHE_KEY)
    _cache_delete(PUBLIC_FORUM_SETTINGS_CACHE_KEY)


def _cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        return default


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        return None
    return value


def _cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        return None
    return True


def _is_valid_public_forum_settings_cache(payload) -> bool:
    if not isinstance(payload, dict):
        return False

    required_list_fields = (
        "notification_types",
        "user_preferences",
        "post_types",
        "enabled_modules",
        "enabled_extensions",
    )
    for field in required_list_fields:
        if field not in payload or not isinstance(payload.get(field), list):
            return False

    if "extension_document" not in payload or not isinstance(payload.get("extension_document"), dict):
        return False

    return True


def get_advanced_settings() -> dict:
    cached = _cache_get(ADVANCED_SETTINGS_CACHE_KEY)
    if isinstance(cached, dict):
        return cached.copy()

    advanced_settings = get_setting_group("advanced", get_advanced_settings_defaults())
    advanced_settings["cache_driver"] = (
        "redis" if "redis" in settings.CACHES.get("default", {}).get("BACKEND", "").lower() else "file"
    )
    advanced_settings["queue_driver"] = (
        "redis" if "redis" in getattr(settings, "CELERY_BROKER_URL", "").lower() else "sync"
    )
    advanced_settings["debug_mode"] = settings.DEBUG
    mode = normalize_maintenance_mode(
        advanced_settings.get("maintenance_mode_key", advanced_settings.get("maintenance_mode"))
    )
    advanced_settings["maintenance_mode_key"] = mode
    advanced_settings["maintenance_mode"] = mode != "none"
    advanced_settings["maintenance_mode_label"] = get_maintenance_mode_label(mode)
    _cache_set(ADVANCED_SETTINGS_CACHE_KEY, advanced_settings, ADVANCED_SETTINGS_CACHE_TIMEOUT_SECONDS)
    return advanced_settings.copy()


def get_cache_lifetime() -> int:
    try:
        lifetime = int(get_advanced_settings().get("cache_lifetime", 0) or 0)
    except (TypeError, ValueError):
        lifetime = 0
    return max(lifetime, 0)


def is_maintenance_mode_enabled() -> bool:
    return get_maintenance_mode() != "none"


def get_maintenance_mode() -> str:
    return normalize_maintenance_mode(get_advanced_settings().get("maintenance_mode_key"))


def is_low_maintenance_mode() -> bool:
    return get_maintenance_mode() == "low"


def is_high_maintenance_mode() -> bool:
    return get_maintenance_mode() == "high"


def is_safe_maintenance_mode() -> bool:
    return get_maintenance_mode() == "safe"


def normalize_maintenance_mode(value) -> str:
    if isinstance(value, bool):
        return "high" if value else "none"
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return "high"
    if text in {"0", "false", "no", "off", "disabled", ""}:
        return "none"
    if text in {"none", "low", "high", "safe"}:
        return text
    return "none"


def get_maintenance_mode_label(mode: str | None = None) -> str:
    labels = {
        "none": "未启用",
        "low": "低维护",
        "high": "高维护",
        "safe": "恢复模式",
    }
    return labels.get(normalize_maintenance_mode(mode), labels["none"])


def get_maintenance_message() -> str:
    message = (get_advanced_settings().get("maintenance_message") or "").strip()
    return message or ADVANCED_SETTINGS_DEFAULTS["maintenance_message"]


def is_query_logging_enabled() -> bool:
    return bool(get_advanced_settings().get("log_queries", False))


def save_setting_group(prefix: str, defaults: dict, payload: dict) -> dict:
    values = get_setting_group(prefix, defaults)
    normalized_payload = dict(payload or {})
    if prefix == "advanced":
        mode = normalize_maintenance_mode(
            normalized_payload.get("maintenance_mode_key", normalized_payload.get("maintenance_mode"))
        )
        normalized_payload["maintenance_mode_key"] = mode
        normalized_payload["maintenance_mode"] = mode != "none"

    for key in defaults.keys():
        if key not in normalized_payload:
            continue

        values[key] = normalized_payload[key]
        Setting.objects.update_or_create(
            key=f"{prefix}.{key}",
            defaults={"value": json.dumps(normalized_payload[key], ensure_ascii=False)}
        )

    clear_runtime_setting_caches()
    return values


def get_public_forum_settings(user=None) -> dict:
    cache_lifetime = 0 if user is not None else get_cache_lifetime()
    if cache_lifetime > 0:
        cached = _cache_get(PUBLIC_FORUM_SETTINGS_CACHE_KEY)
        if _is_valid_public_forum_settings_cache(cached):
            return cached
        if cached is not None:
            _cache_delete(PUBLIC_FORUM_SETTINGS_CACHE_KEY)

    forum_settings = get_setting_group("basic", BASIC_SETTINGS_DEFAULTS)
    forum_settings.update(get_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS))

    advanced_settings = get_advanced_settings()
    forum_settings.update({
        "maintenance_mode": bool(advanced_settings.get("maintenance_mode", False)),
        "maintenance_mode_key": advanced_settings.get("maintenance_mode_key", "none"),
        "maintenance_mode_label": advanced_settings.get("maintenance_mode_label", "未启用"),
        "maintenance_message": get_maintenance_message(),
    })

    forum_settings["notification_types"] = [
        {
            "code": definition.code,
            "label": definition.label,
            "description": definition.description,
            "icon": definition.icon,
            "module_id": definition.module_id,
            "navigation_scope": definition.navigation_scope,
            "preference_key": definition.preference_key,
            "preference_label": definition.preference_label,
            "preference_description": definition.preference_description,
            "preference_default_enabled": definition.preference_default_enabled,
        }
        for definition in _get_forum_registry().get_notification_types()
    ]

    forum_settings["user_preferences"] = [
        {
            "key": definition.key,
            "label": definition.label,
            "description": definition.description,
            "module_id": definition.module_id,
            "category": definition.category,
            "default_value": definition.default_value,
        }
        for definition in _get_forum_registry().get_user_preferences()
    ]

    forum_settings["post_types"] = [
        {
            "code": definition.code,
            "label": definition.label,
            "description": definition.description,
            "icon": definition.icon,
            "module_id": definition.module_id,
            "is_default": definition.is_default,
            "is_stream_visible": definition.is_stream_visible,
            "counts_toward_discussion": definition.counts_toward_discussion,
            "counts_toward_user": definition.counts_toward_user,
            "searchable": definition.searchable,
        }
        for definition in _get_forum_registry().get_post_types()
    ]

    forum_settings["enabled_modules"] = [
        module.module_id
        for module in _get_forum_registry().get_modules()
        if module.enabled
    ]

    forum_settings["extension_runtime"] = _serialize_extension_runtime_stamp()
    forum_settings["extension_recovery"] = serialize_extension_recovery_state()
    enabled_extension_entries = get_enabled_extension_runtime_entries(product_visible_only=True)
    forum_settings["enabled_extensions"] = [
        {
            "id": extension["id"],
            "name": extension["name"],
            "frontend_common_entry": extension.get("frontend_common_entry", ""),
            "frontend_forum_entry": extension["frontend_forum_entry"],
            "frontend_outputs": dict(extension.get("frontend_outputs") or {}),
            "frontend_routes": [
                route
                for route in extension.get("frontend_routes", [])
                if route.get("frontend") == "forum"
            ],
            "source": extension["source"],
            "product_visible": extension["product_visible"],
            "module_ids": extension["module_ids"],
            "settings_values": extension["settings_values"],
            "forum_settings": extension["forum_settings"],
        }
        for extension in enabled_extension_entries
        if str(extension["frontend_forum_entry"] or "").strip()
        or str(extension.get("frontend_common_entry", "") or "").strip()
        or any(route.get("frontend") == "forum" for route in extension.get("frontend_routes", []))
    ]
    forum_settings.update(_serialize_extension_forum_settings(enabled_extension_entries))

    forum_settings["extension_locales"] = get_enabled_extension_locales()
    forum_settings["extension_document"] = build_enabled_frontend_document_payload()
    forum_settings.update(_serialize_forum_resource_fields(forum_settings, user=user))

    if cache_lifetime > 0:
        _cache_set(PUBLIC_FORUM_SETTINGS_CACHE_KEY, forum_settings, cache_lifetime)

    return forum_settings


def _serialize_extension_forum_settings(enabled_extensions: list[dict]) -> dict:
    output: dict = {}
    for extension in enabled_extensions:
        forum_settings = extension.get("forum_settings")
        if isinstance(forum_settings, dict):
            output.update(forum_settings)
    return output


def _serialize_extension_runtime_stamp() -> dict:
    from apps.core.models import Setting
    from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY, RUNTIME_VERSION_KEY

    enabled_order = Setting.objects.filter(key="extensions_enabled_order").first()
    rebuild_marker = Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).first()
    runtime_version = Setting.objects.filter(key=RUNTIME_VERSION_KEY).first()
    raw_order = str(getattr(enabled_order, "value", "") or "")
    raw_marker = str(getattr(rebuild_marker, "value", "") or "")
    raw_version = str(getattr(runtime_version, "value", "") or "")
    return {
        "stamp": f"{raw_order}:{raw_version or raw_marker}",
        "rebuild_required": bool(raw_marker),
    }


def _serialize_forum_resource_fields(forum_settings: dict, *, user=None) -> dict:
    from apps.core.extensions.runtime import get_runtime_resource_registry

    return get_runtime_resource_registry().serialize(
        "forum",
        SimpleNamespace(settings=forum_settings),
        {"user": user},
    )
