"""
Runtime queue dispatch helpers.
"""
import logging
import os
from unittest.mock import Mock
from django.core.cache import cache
from django.utils import timezone
from typing import Callable, Optional

from apps.core.bootstrap_config import _is_test_process
from apps.core.settings_service import get_advanced_settings


logger = logging.getLogger(__name__)
QUEUE_METRICS_CACHE_KEY = "queue.runtime.metrics"
QUEUE_METRICS_TIMEOUT = 60 * 60 * 24 * 30
DEFAULT_QUEUE_METRICS = {
    "enqueued_count": 0,
    "sync_count": 0,
    "fallback_count": 0,
    "last_task": "",
    "last_error": "",
    "last_event_at": "",
}


class QueueService:
    """Dispatch Celery tasks according to runtime queue settings."""

    STATUS_DISABLED = "disabled"
    STATUS_SYNC = "sync"
    STATUS_UNSUPPORTED = "unsupported"
    STATUS_AVAILABLE = "available"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_UNKNOWN = "unknown"
    TEST_SKIP_LIVE_IO_ENV = "BIAS_TEST_ALLOW_LIVE_QUEUE_IO"

    @staticmethod
    def _allows_live_queue_io_in_tests() -> bool:
        return str(os.getenv(QueueService.TEST_SKIP_LIVE_IO_ENV, "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _should_skip_live_worker_check() -> bool:
        return _is_test_process() and not QueueService._allows_live_queue_io_in_tests()

    @staticmethod
    def _should_skip_live_task_enqueue(task) -> bool:
        if not _is_test_process() or QueueService._allows_live_queue_io_in_tests():
            return False

        delay = getattr(task, "delay", None)
        apply_async = getattr(task, "apply_async", None)
        if isinstance(delay, Mock) or isinstance(apply_async, Mock):
            return False

        task_module = getattr(task, "__module__", "") or ""
        task_name = getattr(task, "name", "") or ""
        if ".tests" in task_module or task_name.startswith("tests."):
            return False

        return task_module.startswith("apps.")

    @staticmethod
    def get_runtime_config() -> dict:
        settings = get_advanced_settings()
        return {
            "enabled": bool(settings.get("queue_enabled", False)),
            "driver": str(settings.get("queue_driver") or "sync").strip().lower(),
        }

    @staticmethod
    def should_enqueue() -> bool:
        config = QueueService.get_runtime_config()
        return config["enabled"] and config["driver"] == "redis"

    @staticmethod
    def get_worker_status() -> dict:
        config = QueueService.get_runtime_config()
        if not config["enabled"]:
            return {
                "status": QueueService.STATUS_DISABLED,
                "label": "未启用",
                "available": False,
                "worker_count": 0,
                "message": "队列关闭，任务同步执行。",
            }

        if config["driver"] == "sync":
            return {
                "status": QueueService.STATUS_SYNC,
                "label": "同步执行",
                "available": False,
                "worker_count": 0,
                "message": "当前选择同步执行，不需要 worker。",
            }

        if config["driver"] != "redis":
            return {
                "status": QueueService.STATUS_UNSUPPORTED,
                "label": "暂未接入",
                "available": False,
                "worker_count": 0,
                "message": f"{config['driver']} 队列驱动尚未接入 worker 检测。",
            }

        if QueueService._should_skip_live_worker_check():
            return {
                "status": QueueService.STATUS_UNAVAILABLE,
                "label": "测试环境跳过",
                "available": False,
                "worker_count": 0,
                "message": "测试环境默认跳过真实 worker 检测。",
            }

        try:
            from config.celery import app as celery_app

            inspector = celery_app.control.inspect(timeout=0.5)
            ping_result = inspector.ping() or {}
        except Exception as exc:
            logger.warning("Queue worker health check failed.", exc_info=True)
            return {
                "status": QueueService.STATUS_UNKNOWN,
                "label": "检测失败",
                "available": False,
                "worker_count": 0,
                "message": str(exc) or "无法检测 worker 状态。",
            }

        worker_count = len(ping_result)
        if worker_count > 0:
            return {
                "status": QueueService.STATUS_AVAILABLE,
                "label": f"{worker_count} 个 worker 在线",
                "available": True,
                "worker_count": worker_count,
                "message": "Celery worker 可用。",
            }

        return {
            "status": QueueService.STATUS_UNAVAILABLE,
            "label": "无 worker 响应",
            "available": False,
            "worker_count": 0,
            "message": "队列已启用，但没有检测到在线 worker。",
        }

    @staticmethod
    def get_metrics() -> dict:
        try:
            metrics = cache.get(QUEUE_METRICS_CACHE_KEY) or {}
        except Exception:
            metrics = {}

        return {
            **DEFAULT_QUEUE_METRICS,
            **{key: metrics.get(key) for key in DEFAULT_QUEUE_METRICS.keys() if key in metrics},
        }

    @staticmethod
    def reset_metrics() -> dict:
        metrics = DEFAULT_QUEUE_METRICS.copy()
        try:
            cache.set(QUEUE_METRICS_CACHE_KEY, metrics, QUEUE_METRICS_TIMEOUT)
        except Exception:
            return metrics
        return metrics

    @staticmethod
    def _record_metric(event: str, task_name: str, error: str = "") -> None:
        metrics = QueueService.get_metrics()
        counter_key = {
            "enqueued": "enqueued_count",
            "sync": "sync_count",
            "fallback": "fallback_count",
        }.get(event)

        if counter_key:
            metrics[counter_key] = int(metrics.get(counter_key, 0) or 0) + 1

        metrics["last_task"] = task_name
        metrics["last_error"] = error
        metrics["last_event_at"] = timezone.now().isoformat()

        try:
            cache.set(QUEUE_METRICS_CACHE_KEY, metrics, QUEUE_METRICS_TIMEOUT)
        except Exception:
            return None

    @staticmethod
    def dispatch_celery_task(
        task,
        *args,
        fallback: Optional[Callable[[], object]] = None,
        countdown: Optional[int] = None,
        **kwargs,
    ):
        """
        Dispatch a Celery task when the runtime queue is enabled.

        If the queue is disabled, or enqueueing fails, the optional fallback is
        executed synchronously. This keeps user-facing flows working while still
        allowing deployed worker stacks to take the expensive path off-request.
        """
        task_name = getattr(task, "name", repr(task))
        if QueueService.should_enqueue():
            if QueueService._should_skip_live_task_enqueue(task):
                if fallback is not None:
                    result = fallback()
                    QueueService._record_metric("sync", task_name)
                    return result
                return None
            try:
                if countdown is not None and hasattr(task, "apply_async"):
                    result = task.apply_async(args=args, kwargs=kwargs, countdown=countdown)
                else:
                    result = task.delay(*args, **kwargs)
                QueueService._record_metric("enqueued", task_name)
                return result
            except Exception as exc:
                logger.warning(
                    "Queue dispatch failed for task %s; falling back to sync execution.",
                    task_name,
                    exc_info=True,
                )
                QueueService._record_metric("fallback", task_name, error=str(exc))
                if fallback is None:
                    raise

        if fallback is not None:
            result = fallback()
            if not QueueService.should_enqueue():
                QueueService._record_metric("sync", task_name)
            return result

        return None
