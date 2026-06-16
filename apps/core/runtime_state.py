from __future__ import annotations

import json
import time
from dataclasses import dataclass

from django.db import OperationalError, ProgrammingError

from apps.core.bootstrap_config import SiteBootstrapConfig, load_site_bootstrap
from apps.core.models import Setting
from apps.core.version import APP_VERSION


VERSION_SETTING_KEY = "system.version"
RUNTIME_STATUS_CACHE_TTL_SECONDS = 1.0
_runtime_status_cache: RuntimeStatus | None = None
_runtime_status_cache_key = ""
_runtime_status_cache_at = 0.0


@dataclass
class RuntimeStatus:
    state: str
    current_version: str
    installed_version: str | None
    message: str


def get_runtime_status(bootstrap: SiteBootstrapConfig | None = None) -> RuntimeStatus:
    global _runtime_status_cache
    global _runtime_status_cache_key
    global _runtime_status_cache_at

    config = bootstrap
    if config is None:
        from django.conf import settings

        config = load_site_bootstrap(settings.BASE_DIR)

    cache_key = _runtime_status_cache_key_for(config)
    now = time.monotonic()
    if (
        _runtime_status_cache is not None
        and _runtime_status_cache_key == cache_key
        and now - _runtime_status_cache_at < RUNTIME_STATUS_CACHE_TTL_SECONDS
    ):
        return _runtime_status_cache

    if not config.installed:
        return _remember_runtime_status(
            cache_key,
            RuntimeStatus(
                state="uninstalled",
                current_version=APP_VERSION,
                installed_version=None,
                message="Bias 尚未安装，请先执行安装流程。",
            ),
        )

    if config.source == "test":
        return _remember_runtime_status(
            cache_key,
            RuntimeStatus(
                state="ready",
                current_version=APP_VERSION,
                installed_version=APP_VERSION,
                message="测试环境可用。",
            ),
        )

    try:
        value = Setting.objects.filter(key=VERSION_SETTING_KEY).values_list("value", flat=True).first()
    except (OperationalError, ProgrammingError):
        return _remember_runtime_status(
            cache_key,
            RuntimeStatus(
                state="upgrade_required",
                current_version=APP_VERSION,
                installed_version=None,
                message="数据库尚未完成初始化或升级，请先执行迁移。",
            ),
        )

    installed_version = _parse_setting_value(value)
    if installed_version != APP_VERSION:
        return _remember_runtime_status(
            cache_key,
            RuntimeStatus(
                state="upgrade_required",
                current_version=APP_VERSION,
                installed_version=installed_version,
                message="Bias 代码版本与数据库版本不一致，请先执行升级。",
            ),
        )

    return _remember_runtime_status(
        cache_key,
        RuntimeStatus(
            state="ready",
            current_version=APP_VERSION,
            installed_version=installed_version,
            message="Bias 已就绪。",
        ),
    )


def sync_installed_version() -> str:
    Setting.objects.update_or_create(
        key=VERSION_SETTING_KEY,
        defaults={"value": json.dumps(APP_VERSION, ensure_ascii=False)},
    )
    clear_runtime_status_cache()
    return APP_VERSION


def clear_runtime_status_cache() -> None:
    global _runtime_status_cache
    global _runtime_status_cache_key
    global _runtime_status_cache_at

    _runtime_status_cache = None
    _runtime_status_cache_key = ""
    _runtime_status_cache_at = 0.0


def _remember_runtime_status(cache_key: str, status: RuntimeStatus) -> RuntimeStatus:
    global _runtime_status_cache
    global _runtime_status_cache_key
    global _runtime_status_cache_at

    _runtime_status_cache = status
    _runtime_status_cache_key = cache_key
    _runtime_status_cache_at = time.monotonic()
    return status


def _runtime_status_cache_key_for(config: SiteBootstrapConfig) -> str:
    return "|".join(
        [
            str(config.source),
            "1" if config.installed else "0",
            str(config.database_mode),
            str(config.sqlite_name),
            str(config.db_name),
            str(config.db_host),
            str(config.db_port),
        ]
    )


def _parse_setting_value(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
        return str(parsed) if parsed else None
    except json.JSONDecodeError:
        return value.strip() or None
