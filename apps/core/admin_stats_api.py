import sys

import django
from django.conf import settings
from ninja import Router

from apps.core import runtime_diagnostics
from apps.core.admin_auth import require_staff
from apps.core.admin_runtime_summary import (
    probe_cache_connection,
    probe_queue_broker_connection,
    probe_realtime_connection,
)
from apps.core.extensions.runtime import get_runtime_resource_registry
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.queue_service import QueueService
from apps.core.runtime_diagnostics import (
    build_runtime_dependency_checks,
    detect_cache_driver,
    detect_database_label,
    detect_queue_driver_label,
    detect_realtime_driver,
    is_redis_enabled,
)
from apps.core.settings_service import get_advanced_settings as get_runtime_advanced_settings


router = Router()


def _build_auth_secret_risks() -> list[dict]:
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


def _build_auth_secret_status() -> dict:
    return runtime_diagnostics.build_auth_secret_status(risks=_build_auth_secret_risks())


def _build_runtime_risks(
    *,
    database_label: str,
    cache_driver: str,
    realtime_driver: str,
    queue_enabled: bool,
    queue_driver: str,
    queue_worker_status: dict,
    redis_enabled: bool,
    cache_connection: dict,
    realtime_connection: dict,
    queue_broker_connection: dict,
) -> list[dict]:
    return runtime_diagnostics.build_runtime_risks(
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
        auth_secret_risks=_build_auth_secret_risks(),
        web_concurrency=getattr(settings, "WEB_CONCURRENCY", 1),
    )


@router.get("/stats", auth=AccessTokenAuth(), tags=["Admin"])
def get_stats(request):
    denied = require_staff(request)
    if denied:
        return denied

    advanced_settings = get_runtime_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    queue_metrics = QueueService.get_metrics()
    database_label = detect_database_label()
    cache_driver = detect_cache_driver()
    realtime_driver = detect_realtime_driver()
    redis_enabled = is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver)
    cache_connection = probe_cache_connection()
    realtime_connection = probe_realtime_connection()
    queue_broker_connection = probe_queue_broker_connection(queue_enabled, queue_driver)
    runtime_risks = _build_runtime_risks(
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
    )
    auth_secret_status = _build_auth_secret_status()
    runtime_dependency_checks = build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )

    stats = {
        "runtimeName": "Python",
        "pythonVersion": sys.version.split()[0],
        "djangoVersion": django.get_version(),
        "databaseLabel": database_label,
        "cacheDriver": cache_driver,
        "queueDriver": queue_driver,
        "queueEnabled": queue_enabled,
        "queueLabel": detect_queue_driver_label(queue_enabled, queue_driver),
        "queueWorkerStatus": queue_worker_status["status"],
        "queueWorkerLabel": queue_worker_status["label"],
        "queueWorkerAvailable": queue_worker_status["available"],
        "queueWorkerCount": queue_worker_status["worker_count"],
        "queueWorkerMessage": queue_worker_status["message"],
        "queueMetrics": queue_metrics,
        "realtimeDriver": realtime_driver,
        "redisEnabled": redis_enabled,
        "cacheConnectionStatus": cache_connection["status"],
        "cacheConnectionLabel": cache_connection["label"],
        "cacheConnectionAvailable": cache_connection["available"],
        "cacheConnectionMessage": cache_connection["message"],
        "realtimeConnectionStatus": realtime_connection["status"],
        "realtimeConnectionLabel": realtime_connection["label"],
        "realtimeConnectionAvailable": realtime_connection["available"],
        "realtimeConnectionMessage": realtime_connection["message"],
        "queueBrokerStatus": queue_broker_connection["status"],
        "queueBrokerLabel": queue_broker_connection["label"],
        "queueBrokerAvailable": queue_broker_connection["available"],
        "queueBrokerMessage": queue_broker_connection["message"],
        "runtimeDependencyChecks": runtime_dependency_checks,
        "runtimeRisks": runtime_risks,
        "authSecretStatus": auth_secret_status["status"],
        "authSecretLabel": auth_secret_status["label"],
        "authSecretMessage": auth_secret_status["message"],
        "debugMode": settings.DEBUG,
        "maintenanceMode": bool(advanced_settings.get("maintenance_mode", False)),
        "maintenanceModeKey": advanced_settings.get("maintenance_mode_key", "none"),
        "maintenanceModeLabel": advanced_settings.get("maintenance_mode_label", "未启用"),
    }
    return get_runtime_resource_registry().serialize(
        "admin_stats",
        stats,
        {"user": request.auth, "request": request},
    )
