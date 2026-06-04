from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.api_errors import api_error
from apps.discussions import discussion_tracking
from apps.discussions.models import Discussion
from apps.users.services import UserService


def dispatch_discussion_subscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        UserService.ensure_not_suspended(context["user"], "关注讨论")
        discussion_tracking.set_subscription_state(discussion_id, context["user"], True)
        return {"message": "已关注讨论", "is_subscribed": True}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


def dispatch_discussion_unsubscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        UserService.ensure_not_suspended(context["user"], "关注讨论")
        discussion_tracking.set_subscription_state(discussion_id, context["user"], False)
        return {"message": "已取消关注", "is_subscribed": False}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


def _discussion_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0
