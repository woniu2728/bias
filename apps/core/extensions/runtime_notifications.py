from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    get_extension_host_service,
    require_extension_host_service,
    runtime_service_method,
)


def get_runtime_notification_service(default: Any = None):
    return get_extension_host_service("notifications.service", default)


def require_runtime_notification_service():
    return require_extension_host_service("notifications.service")


def get_runtime_notification_model():
    service = require_runtime_notification_service()
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("notifications.service 未提供通知模型")
    return model


def notify_runtime_notification(method_name: str, *args, **kwargs):
    service = get_runtime_notification_service()
    if service is None:
        return None
    return runtime_service_method(service, method_name)(*args, **kwargs)


def delete_runtime_discussion_reply_notifications_for_post(post_id: int) -> int:
    result = notify_runtime_notification("delete_discussion_reply_for_post", post_id)
    return int(result or 0)
