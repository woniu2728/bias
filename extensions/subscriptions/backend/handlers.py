from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.extensions.platform import api_error
from apps.core.extensions.runtime import (
    is_runtime_discussion_not_found,
    set_runtime_discussion_subscription_state,
)
from apps.core.extensions.runtime import ensure_runtime_user_not_suspended


def dispatch_discussion_subscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        ensure_runtime_user_not_suspended(context["user"], "关注讨论")
        set_runtime_discussion_subscription_state(discussion_id, context["user"], True)
        return {"message": "已关注讨论", "is_subscribed": True}
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except Exception as e:
        if is_runtime_discussion_not_found(e):
            return api_error("讨论不存在", status=404)
        raise


def dispatch_discussion_unsubscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        ensure_runtime_user_not_suspended(context["user"], "关注讨论")
        set_runtime_discussion_subscription_state(discussion_id, context["user"], False)
        return {"message": "已取消关注", "is_subscribed": False}
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except Exception as e:
        if is_runtime_discussion_not_found(e):
            return api_error("讨论不存在", status=404)
        raise


def _discussion_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0
