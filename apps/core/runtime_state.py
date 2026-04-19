from __future__ import annotations

import json
from dataclasses import dataclass

from django.db import OperationalError, ProgrammingError

from apps.core.bootstrap_config import SiteBootstrapConfig, load_site_bootstrap
from apps.core.models import Setting
from apps.core.version import APP_VERSION


VERSION_SETTING_KEY = "system.version"


@dataclass
class RuntimeStatus:
    state: str
    current_version: str
    installed_version: str | None
    message: str


def get_runtime_status(bootstrap: SiteBootstrapConfig | None = None) -> RuntimeStatus:
    config = bootstrap
    if config is None:
        from django.conf import settings

        config = load_site_bootstrap(settings.BASE_DIR)

    if not config.installed:
        return RuntimeStatus(
            state="uninstalled",
            current_version=APP_VERSION,
            installed_version=None,
            message="Bias 尚未安装，请先执行安装流程。",
        )

    if config.source == "test":
        return RuntimeStatus(
            state="ready",
            current_version=APP_VERSION,
            installed_version=APP_VERSION,
            message="测试环境可用。",
        )

    try:
        value = Setting.objects.filter(key=VERSION_SETTING_KEY).values_list("value", flat=True).first()
    except (OperationalError, ProgrammingError):
        return RuntimeStatus(
            state="upgrade_required",
            current_version=APP_VERSION,
            installed_version=None,
            message="数据库尚未完成初始化或升级，请先执行迁移。",
        )

    installed_version = _parse_setting_value(value)
    if installed_version != APP_VERSION:
        return RuntimeStatus(
            state="upgrade_required",
            current_version=APP_VERSION,
            installed_version=installed_version,
            message="Bias 代码版本与数据库版本不一致，请先执行升级。",
        )

    return RuntimeStatus(
        state="ready",
        current_version=APP_VERSION,
        installed_version=installed_version,
        message="Bias 已就绪。",
    )


def sync_installed_version() -> str:
    Setting.objects.update_or_create(
        key=VERSION_SETTING_KEY,
        defaults={"value": json.dumps(APP_VERSION, ensure_ascii=False)},
    )
    return APP_VERSION


def _parse_setting_value(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
        return str(parsed) if parsed else None
    except json.JSONDecodeError:
        return value.strip() or None

