from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.checks import Critical, Tags, Warning, register

from apps.core import runtime_diagnostics
from apps.core.bootstrap_config import _is_test_process
from apps.core.queue_service import QueueService
from apps.core.settings_service import get_advanced_settings


NETWORK_PROBE_TIMEOUT_SECONDS = runtime_diagnostics.NETWORK_PROBE_TIMEOUT_SECONDS
PRODUCTION_RUNTIME_CHECK_TAG = "bias_runtime"


def detect_database_label() -> str:
    return runtime_diagnostics.detect_database_label()


def detect_cache_driver() -> str:
    return runtime_diagnostics.detect_cache_driver()


def detect_realtime_driver() -> str:
    return runtime_diagnostics.detect_realtime_driver()


def detect_queue_driver_label(queue_enabled: bool, queue_driver: str) -> str:
    return runtime_diagnostics.detect_queue_driver_label(queue_enabled, queue_driver)


def is_redis_enabled(queue_enabled: bool = False, queue_driver: str = "") -> bool:
    return runtime_diagnostics.is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver)


def _probe_cache_connection() -> dict[str, Any]:
    return runtime_diagnostics.probe_cache_connection(settings_obj=settings, cache_backend=cache)


def _redis_command(*parts: str) -> bytes:
    return runtime_diagnostics.redis_command(*parts)


def _probe_redis_ping(host: str | None, port: int | None, *, label: str, password: str = "") -> dict[str, Any]:
    return runtime_diagnostics.probe_redis_ping(host, port, label=label, password=password)


def _probe_realtime_connection() -> dict[str, Any]:
    return runtime_diagnostics.probe_realtime_connection(
        settings_obj=settings,
        redis_probe=lambda host, port, label, password="": _probe_redis_ping(
            host,
            port,
            label=label,
            password=password,
        ),
    )


def _probe_queue_broker_connection(queue_enabled: bool, queue_driver: str) -> dict[str, Any]:
    return runtime_diagnostics.probe_queue_broker_connection(
        settings_obj=settings,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        redis_probe=lambda host, port, label, password="": _probe_redis_ping(
            host,
            port,
            label=label,
            password=password,
        ),
    )


def build_auth_secret_risks() -> list[dict[str, Any]]:
    secret_key = runtime_diagnostics.normalize_secret_value(settings.SECRET_KEY)
    jwt_algorithm = str(settings.NINJA_JWT.get("ALGORITHM") or "").strip().upper()
    jwt_signing_key = runtime_diagnostics.normalize_secret_value(
        settings.NINJA_JWT.get("SIGNING_KEY") or settings.SECRET_KEY
    )
    return runtime_diagnostics.build_auth_secret_risks(
        secret_key=secret_key,
        jwt_algorithm=jwt_algorithm,
        jwt_signing_key=jwt_signing_key,
    )


def build_auth_secret_status() -> dict[str, Any]:
    return runtime_diagnostics.build_auth_secret_status(risks=build_auth_secret_risks())


def build_runtime_risks(
    *,
    debug_mode: bool,
    database_label: str,
    cache_driver: str,
    realtime_driver: str,
    queue_enabled: bool,
    queue_driver: str,
    queue_worker_status: dict[str, Any],
    redis_enabled: bool,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
    web_concurrency: int | None = None,
) -> list[dict[str, Any]]:
    normalized_database_label = str(database_label or "").lower()
    risks = runtime_diagnostics.build_runtime_risks(
        debug_mode=debug_mode,
        database_label=database_label,
        cache_driver=cache_driver,
        realtime_driver=realtime_driver,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        queue_worker_status=queue_worker_status,
        redis_enabled=redis_enabled,
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        auth_secret_risks=build_auth_secret_risks(),
        web_concurrency=web_concurrency if web_concurrency is not None else getattr(settings, "WEB_CONCURRENCY", 1),
    )
    is_production_like = "postgresql" in normalized_database_label
    if is_production_like:
        frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
        if not frontend_url:
            risks.append(
                {
                    "code": "frontend-url-missing-production",
                    "level": "danger",
                    "title": "生产形态下缺少 FRONTEND_URL",
                    "message": "邮件链接、验证链接和前台跳转依赖 FRONTEND_URL，生产环境必须提供有效前端地址。",
                }
            )

        email_backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").strip().lower()
        if "console" in email_backend or "locmem" in email_backend:
            risks.append(
                {
                    "code": "email-backend-development-production",
                    "level": "danger",
                    "title": "生产形态下仍在使用开发型邮件后端",
                    "message": "当前邮件后端仍是 console/locmem，生产环境会导致邮件无法真正发送。",
                }
            )

    return risks


def build_runtime_dependency_checks(
    *,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
    queue_worker_status: dict[str, Any],
) -> list[dict[str, Any]]:
    return runtime_diagnostics.build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
        queue_status_disabled=QueueService.STATUS_DISABLED,
        queue_status_sync=QueueService.STATUS_SYNC,
    )


def collect_runtime_readiness() -> dict[str, Any]:
    advanced_settings = get_advanced_settings()
    queue_driver = str(advanced_settings.get("queue_driver") or "sync").strip().lower()
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    database_label = detect_database_label()
    cache_driver = detect_cache_driver()
    realtime_driver = detect_realtime_driver()
    redis_enabled = is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver)
    cache_connection = _probe_cache_connection()
    realtime_connection = _probe_realtime_connection()
    queue_broker_connection = _probe_queue_broker_connection(queue_enabled, queue_driver)
    runtime_risks = build_runtime_risks(
        debug_mode=settings.DEBUG,
        database_label=database_label,
        cache_driver=cache_driver,
        realtime_driver=realtime_driver,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        queue_worker_status=queue_worker_status,
        redis_enabled=redis_enabled,
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        web_concurrency=getattr(settings, "WEB_CONCURRENCY", 1),
    )
    runtime_dependency_checks = build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )
    auth_secret_status = build_auth_secret_status()
    return {
        "advanced_settings": advanced_settings,
        "queue_driver": queue_driver,
        "queue_enabled": queue_enabled,
        "queue_worker_status": queue_worker_status,
        "database_label": database_label,
        "cache_driver": cache_driver,
        "realtime_driver": realtime_driver,
        "redis_enabled": redis_enabled,
        "cache_connection": cache_connection,
        "realtime_connection": realtime_connection,
        "queue_broker_connection": queue_broker_connection,
        "runtime_risks": runtime_risks,
        "runtime_dependency_checks": runtime_dependency_checks,
        "auth_secret_status": auth_secret_status,
    }


def is_production_runtime() -> bool:
    bootstrap = getattr(settings, "BOOTSTRAP", None)
    return not settings.DEBUG and bool(getattr(bootstrap, "installed", False)) and not _is_test_process()


def build_runtime_check_messages(**kwargs: Any) -> list[Any]:
    readiness = kwargs or collect_runtime_readiness()
    messages: list[Any] = []

    for risk in readiness["runtime_risks"]:
        text = f"{risk['title']}：{risk['message']}"
        hint = ""
        for dependency in readiness["runtime_dependency_checks"]:
            if dependency.get("message") and dependency["key"] in risk["code"]:
                hint = dependency.get("recommended_action") or ""
                break

        check_id = f"bias.{risk['code']}"
        if risk.get("level") == "danger":
            messages.append(Critical(text, hint=hint, id=check_id))
        else:
            messages.append(Warning(text, hint=hint, id=check_id))

    return messages


@register(Tags.security, PRODUCTION_RUNTIME_CHECK_TAG)
def check_production_runtime_configuration(app_configs, **kwargs):
    if not is_production_runtime():
        return []
    return build_runtime_check_messages()
