import sys
from typing import Any

import django
from django.conf import settings
from django.core.cache import cache

from apps.core import admin_runtime_helpers
from apps.core.queue_service import QueueService
from apps.core.runtime_checks import (
    _probe_redis_ping as runtime_probe_redis_ping,
    build_runtime_dependency_checks,
    detect_cache_driver,
    detect_database_label,
    detect_queue_driver_label,
    detect_realtime_driver,
    is_redis_enabled,
)
from apps.core.settings_service import get_advanced_settings


def probe_cache_connection() -> dict[str, Any]:
    return admin_runtime_helpers.probe_cache_connection(settings_obj=settings, cache_backend=cache)


def probe_realtime_connection() -> dict[str, Any]:
    return admin_runtime_helpers.probe_realtime_connection(
        settings_obj=settings,
        redis_probe=lambda host, port, label, password="": runtime_probe_redis_ping(
            host,
            port,
            label=label,
            password=password,
        ),
    )


def probe_queue_broker_connection(queue_enabled: bool, queue_driver: str) -> dict[str, Any]:
    return admin_runtime_helpers.probe_queue_broker_connection(
        settings_obj=settings,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        redis_probe=lambda host, port, label, password="": runtime_probe_redis_ping(
            host,
            port,
            label=label,
            password=password,
        ),
    )


def build_runtime_dependency_summary() -> dict[str, Any]:
    advanced_settings = get_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    cache_connection = probe_cache_connection()
    realtime_connection = probe_realtime_connection()
    queue_broker_connection = probe_queue_broker_connection(queue_enabled, queue_driver)
    checks = build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )
    issues = [
        f"{item['label']}：{item['status_label']}"
        for item in checks
        if item.get("available") is False
    ]
    return {
        "status": "attention" if issues else "healthy",
        "label": "需关注" if issues else "健康",
        "issues": issues,
        "checks": checks,
    }


def build_runtime_stats_base() -> dict[str, Any]:
    advanced_settings = get_advanced_settings()
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

    return {
        "advanced_settings": advanced_settings,
        "queue_driver": queue_driver,
        "queue_enabled": queue_enabled,
        "queue_worker_status": queue_worker_status,
        "queue_metrics": queue_metrics,
        "database_label": database_label,
        "cache_driver": cache_driver,
        "realtime_driver": realtime_driver,
        "redis_enabled": redis_enabled,
        "cache_connection": cache_connection,
        "realtime_connection": realtime_connection,
        "queue_broker_connection": queue_broker_connection,
        "runtime_name": "Python",
        "python_version": sys.version.split()[0],
        "django_version": django.get_version(),
        "queue_label": detect_queue_driver_label(queue_enabled, queue_driver),
    }
