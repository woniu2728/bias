"""
论坛设置读取与保存服务
"""
import json

from django.conf import settings
from django.core.cache import cache

from apps.core.models import Setting


ADVANCED_SETTINGS_CACHE_KEY = "settings.group.advanced"
PUBLIC_FORUM_SETTINGS_CACHE_KEY = "settings.public.forum"


BASIC_SETTINGS_DEFAULTS = {
    "forum_title": "PyFlarum",
    "forum_description": "",
    "welcome_title": "欢迎来到PyFlarum",
    "welcome_message": "这是一个基于Django和Vue 3的现代化论坛",
    "default_locale": "zh-CN",
    "show_language_selector": False,
}

APPEARANCE_SETTINGS_DEFAULTS = {
    "primary_color": "#4d698e",
    "accent_color": "#e74c3c",
    "logo_url": "",
    "favicon_url": "",
    "custom_css": "",
    "custom_header": "",
}

MAIL_SETTINGS_DEFAULTS = {
    "mail_driver": "smtp",
    "mail_host": getattr(settings, "EMAIL_HOST", ""),
    "mail_port": getattr(settings, "EMAIL_PORT", 587),
    "mail_encryption": "tls" if getattr(settings, "EMAIL_USE_TLS", False) else "",
    "mail_username": getattr(settings, "EMAIL_HOST_USER", ""),
    "mail_password": "",
    "mail_from_address": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    "mail_from_name": "PyFlarum",
}

ADVANCED_SETTINGS_DEFAULTS = {
    "cache_driver": "redis" if "redis" in settings.CACHES.get("default", {}).get("BACKEND", "").lower() else "file",
    "cache_lifetime": 3600,
    "queue_driver": "redis" if "redis" in getattr(settings, "CELERY_BROKER_URL", "") else "sync",
    "queue_enabled": False,
    "maintenance_mode": False,
    "maintenance_message": "论坛正在维护中，请稍后再试...",
    "debug_mode": settings.DEBUG,
    "log_queries": False,
    "storage_driver": "local",
    "storage_attachments_dir": "attachments",
    "storage_avatars_dir": "avatars",
    "storage_local_path": str(getattr(settings, "MEDIA_ROOT", "")),
    "storage_local_base_url": getattr(settings, "MEDIA_URL", "/media/"),
    "storage_s3_bucket": "",
    "storage_s3_region": "",
    "storage_s3_endpoint": "",
    "storage_s3_access_key_id": "",
    "storage_s3_secret_access_key": "",
    "storage_s3_public_url": "",
    "storage_s3_object_prefix": "",
    "storage_s3_path_style": False,
    "storage_r2_bucket": "",
    "storage_r2_endpoint": "",
    "storage_r2_access_key_id": "",
    "storage_r2_secret_access_key": "",
    "storage_r2_public_url": "",
    "storage_r2_object_prefix": "",
    "storage_oss_bucket": "",
    "storage_oss_endpoint": "",
    "storage_oss_access_key_id": "",
    "storage_oss_access_key_secret": "",
    "storage_oss_public_url": "",
    "storage_oss_object_prefix": "",
    "storage_imagebed_endpoint": "",
    "storage_imagebed_method": "POST",
    "storage_imagebed_file_field": "file",
    "storage_imagebed_headers": "{}",
    "storage_imagebed_form_data": "{}",
    "storage_imagebed_url_path": "data.url",
}


def get_setting_group(prefix: str, defaults: dict) -> dict:
    values = defaults.copy()
    stored_settings = Setting.objects.filter(
        key__in=[f"{prefix}.{key}" for key in defaults.keys()]
    )

    for setting in stored_settings:
        key = setting.key.split(".", 1)[1]
        try:
            values[key] = json.loads(setting.value)
        except json.JSONDecodeError:
            values[key] = setting.value

    return values


def clear_runtime_setting_caches():
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


def get_advanced_settings() -> dict:
    cached = _cache_get(ADVANCED_SETTINGS_CACHE_KEY)
    if cached is not None:
        return cached

    advanced_settings = get_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS)
    advanced_settings["debug_mode"] = settings.DEBUG
    _cache_set(ADVANCED_SETTINGS_CACHE_KEY, advanced_settings, None)
    return advanced_settings


def get_cache_lifetime() -> int:
    try:
        lifetime = int(get_advanced_settings().get("cache_lifetime", 0) or 0)
    except (TypeError, ValueError):
        lifetime = 0
    return max(lifetime, 0)


def is_maintenance_mode_enabled() -> bool:
    return bool(get_advanced_settings().get("maintenance_mode", False))


def get_maintenance_message() -> str:
    message = (get_advanced_settings().get("maintenance_message") or "").strip()
    return message or ADVANCED_SETTINGS_DEFAULTS["maintenance_message"]


def is_query_logging_enabled() -> bool:
    return bool(get_advanced_settings().get("log_queries", False))


def save_setting_group(prefix: str, defaults: dict, payload: dict) -> dict:
    values = get_setting_group(prefix, defaults)

    for key in defaults.keys():
        if key not in payload:
            continue

        values[key] = payload[key]
        Setting.objects.update_or_create(
            key=f"{prefix}.{key}",
            defaults={"value": json.dumps(payload[key], ensure_ascii=False)}
        )

    clear_runtime_setting_caches()
    return values


def get_public_forum_settings() -> dict:
    cache_lifetime = get_cache_lifetime()
    if cache_lifetime > 0:
        cached = _cache_get(PUBLIC_FORUM_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached

    forum_settings = get_setting_group("basic", BASIC_SETTINGS_DEFAULTS)
    forum_settings.update(get_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS))

    advanced_settings = get_advanced_settings()
    forum_settings.update({
        "maintenance_mode": bool(advanced_settings.get("maintenance_mode", False)),
        "maintenance_message": get_maintenance_message(),
    })

    if cache_lifetime > 0:
        _cache_set(PUBLIC_FORUM_SETTINGS_CACHE_KEY, forum_settings, cache_lifetime)

    return forum_settings
