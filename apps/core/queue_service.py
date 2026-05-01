"""
Runtime queue dispatch helpers.
"""
import logging
from typing import Callable, Optional

from apps.core.settings_service import get_advanced_settings


logger = logging.getLogger(__name__)


class QueueService:
    """Dispatch Celery tasks according to runtime queue settings."""

    STATUS_DISABLED = "disabled"
    STATUS_SYNC = "sync"
    STATUS_UNSUPPORTED = "unsupported"
    STATUS_AVAILABLE = "available"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_UNKNOWN = "unknown"

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
    def dispatch_celery_task(task, *args, fallback: Optional[Callable[[], object]] = None, **kwargs):
        """
        Dispatch a Celery task when the runtime queue is enabled.

        If the queue is disabled, or enqueueing fails, the optional fallback is
        executed synchronously. This keeps user-facing flows working while still
        allowing deployed worker stacks to take the expensive path off-request.
        """
        if QueueService.should_enqueue():
            try:
                return task.delay(*args, **kwargs)
            except Exception:
                logger.warning(
                    "Queue dispatch failed for task %s; falling back to sync execution.",
                    getattr(task, "name", repr(task)),
                    exc_info=True,
                )
                if fallback is None:
                    raise

        if fallback is not None:
            return fallback()

        return None
