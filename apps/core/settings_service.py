"""
论坛设置读取与保存服务
"""
import json

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
from apps.core.mail_drivers import serialize_mail_settings
from apps.core.mail_templates import (
    DEFAULT_PASSWORD_RESET_HTML,
    DEFAULT_PASSWORD_RESET_SUBJECT,
    DEFAULT_PASSWORD_RESET_TEXT,
    DEFAULT_VERIFICATION_HTML,
    DEFAULT_VERIFICATION_SUBJECT,
    DEFAULT_VERIFICATION_TEXT,
)
from apps.core.models import Setting
from apps.core.forum_registry import get_forum_registry


ADVANCED_SETTINGS_CACHE_KEY = "settings.group.advanced"
PUBLIC_FORUM_SETTINGS_CACHE_KEY = "settings.public.forum"
FORUM_REGISTRY = get_forum_registry()


BASIC_SETTINGS_DEFAULTS = {
    "forum_title": "Bias",
    "forum_description": "",
    "seo_title": "",
    "seo_description": "",
    "seo_keywords": "",
    "seo_robots_index": True,
    "seo_robots_follow": True,
    "welcome_title": "欢迎来到Bias",
    "welcome_message": "这是一个基于Django和Vue 3的现代化论坛",
    "announcement_enabled": False,
    "announcement_message": "",
    "announcement_tone": "info",
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

MAIL_SETTINGS_STATIC_DEFAULTS = {
    "mail_driver": "smtp",
    "mail_format": "multipart",
    "mail_password": "",
    "mail_from_name": "Bias",
    "mail_test_recipient": "",
    "mail_verification_subject": DEFAULT_VERIFICATION_SUBJECT,
    "mail_verification_text": DEFAULT_VERIFICATION_TEXT,
    "mail_verification_html": DEFAULT_VERIFICATION_HTML,
    "mail_password_reset_subject": DEFAULT_PASSWORD_RESET_SUBJECT,
    "mail_password_reset_text": DEFAULT_PASSWORD_RESET_TEXT,
    "mail_password_reset_html": DEFAULT_PASSWORD_RESET_HTML,
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
    "upload_avatar_max_size_mb": 2,
    "upload_attachment_max_size_mb": 10,
    "upload_site_asset_max_size_mb": 2,
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
    "auth_human_verification_provider": "off",
    "auth_turnstile_site_key": "",
    "auth_turnstile_secret_key": "",
    "auth_human_verification_login_enabled": True,
    "auth_human_verification_register_enabled": True,
}


def get_setting_group(prefix: str, defaults: dict) -> dict:
    values = defaults.copy()
    try:
        stored_settings = Setting.objects.filter(
            key__in=[f"{prefix}.{key}" for key in defaults.keys()]
        )
    except (OperationalError, ProgrammingError):
        return values

    try:
        for setting in stored_settings:
            key = setting.key.split(".", 1)[1]
            try:
                values[key] = json.loads(setting.value)
            except json.JSONDecodeError:
                values[key] = setting.value
    except (OperationalError, ProgrammingError):
        return defaults.copy()

    return values


def get_mail_settings_defaults() -> dict:
    mail_defaults = MAIL_SETTINGS_STATIC_DEFAULTS.copy()

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
    advanced_settings = get_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS)
    advanced_settings["cache_driver"] = (
        "redis" if "redis" in settings.CACHES.get("default", {}).get("BACKEND", "").lower() else "file"
    )
    advanced_settings["queue_driver"] = (
        "redis" if "redis" in getattr(settings, "CELERY_BROKER_URL", "").lower() else "sync"
    )
    advanced_settings["storage_local_path"] = str(getattr(settings, "MEDIA_ROOT", ""))
    advanced_settings["debug_mode"] = settings.DEBUG
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
        "auth_human_verification_provider": "off",
        "auth_turnstile_site_key": "",
        "auth_human_verification_login_enabled": False,
        "auth_human_verification_register_enabled": False,
    })

    provider = str(advanced_settings.get("auth_human_verification_provider") or "off").strip().lower()
    site_key = str(advanced_settings.get("auth_turnstile_site_key") or "").strip()
    secret_key = str(advanced_settings.get("auth_turnstile_secret_key") or "").strip()
    if provider == "turnstile" and site_key and secret_key:
        forum_settings.update({
            "auth_human_verification_provider": "turnstile",
            "auth_turnstile_site_key": site_key,
            "auth_human_verification_login_enabled": bool(
                advanced_settings.get("auth_human_verification_login_enabled", True)
            ),
            "auth_human_verification_register_enabled": bool(
                advanced_settings.get("auth_human_verification_register_enabled", True)
            ),
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
        for definition in FORUM_REGISTRY.get_notification_types()
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
        for definition in FORUM_REGISTRY.get_user_preferences()
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
        for definition in FORUM_REGISTRY.get_post_types()
    ]

    if cache_lifetime > 0:
        _cache_set(PUBLIC_FORUM_SETTINGS_CACHE_KEY, forum_settings, cache_lifetime)

    return forum_settings
