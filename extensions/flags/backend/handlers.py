from __future__ import annotations

from django.core.exceptions import PermissionDenied
from pydantic import BaseModel, Field, validator

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from extensions.posts.backend.models import Post
from apps.posts.services import PostService
from extensions.flags.backend.services import delete_post_flags, report_post, resolve_post_flags


class PostReportSchema(BaseModel):
    reason: str = Field(..., min_length=1, max_length=100)
    message: str = Field("", max_length=1000)

    @validator("reason")
    def validate_reason(cls, value):
        if not value.strip():
            raise ValueError("举报原因不能为空")
        return value.strip()

    @validator("message")
    def validate_message(cls, value):
        return (value or "").strip()


class PostFlagResolveSchema(BaseModel):
    status: str = Field(...)
    resolution_note: str = Field("", max_length=1000)

    @validator("status")
    def validate_status(cls, value):
        normalized = (value or "").strip()
        if normalized not in {"resolved", "ignored"}:
            raise ValueError("无效的处理状态")
        return normalized

    @validator("resolution_note")
    def validate_resolution_note(cls, value):
        return (value or "").strip()


def serialize_flag(flag):
    return {
        "id": flag.id,
        "reason": flag.reason,
        "message": flag.message,
        "status": flag.status,
        "created_at": flag.created_at,
        "resolved_at": flag.resolved_at,
        "resolution_note": flag.resolution_note,
        "post": {
            "id": flag.post.id,
            "number": flag.post.number,
            "content": flag.post.content,
            "discussion_id": flag.post.discussion_id,
            "discussion_title": flag.post.discussion.title if flag.post.discussion else "",
            "author": {
                "id": flag.post.user.id,
                "username": flag.post.user.username,
                "display_name": flag.post.user.display_name,
            } if flag.post.user else None,
        },
        "user": {
            "id": flag.user.id,
            "username": flag.user.username,
            "display_name": flag.user.display_name,
        },
        "resolved_by": {
            "id": flag.resolved_by.id,
            "username": flag.resolved_by.username,
            "display_name": flag.resolved_by.display_name,
        } if flag.resolved_by else None,
    }


def dispatch_post_report(context):
    post_id = _post_object_id(context)
    payload = PostReportSchema(**_post_payload(context))
    try:
        flag = report_post(
            post_id=post_id,
            user=context["user"],
            reason=payload.reason,
            message=payload.message,
        )
        return serialize_flag(flag)
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as exc:
        return api_error(str(exc), status=403)
    except ValueError as exc:
        return api_error(str(exc), status=400)


def dispatch_post_resolve_flags(context):
    request = context["request"]
    post_id = _post_object_id(context)
    payload = PostFlagResolveSchema(**_post_payload(context))
    try:
        resolved_count = resolve_post_flags(
            post_id=post_id,
            admin_user=context["user"],
            status=payload.status,
            resolution_note=payload.resolution_note,
        )
        log_admin_action(
            request,
            "admin.flag.resolve",
            target_type="post",
            target_id=post_id,
            data={
                "status": payload.status,
                "resolved_count": resolved_count,
                "resolution_note": payload.resolution_note,
            },
        )
        post = PostService.get_post_by_id(post_id, context["user"])
        if not post:
            return api_error("帖子不存在", status=404)
        from apps.posts.handlers import serialize_post

        return {
            "message": "举报已处理",
            "resolved_count": resolved_count,
            "post": serialize_post(post, context["user"]),
        }
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as exc:
        return api_error(str(exc), status=403)
    except ValueError as exc:
        return api_error(str(exc), status=400)


def dispatch_post_delete_flags(context):
    request = context["request"]
    post_id = _post_object_id(context)
    try:
        deleted_count = delete_post_flags(post_id, context["user"])
        log_admin_action(
            request,
            "admin.flag.delete",
            target_type="post",
            target_id=post_id,
            data={"deleted_count": deleted_count},
        )
        return 204, None
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as exc:
        return api_error(str(exc), status=403)
    except ValueError as exc:
        return api_error(str(exc), status=400)


def _post_payload(context) -> dict:
    payload = context.get("payload")
    return payload if isinstance(payload, dict) else {}


def _post_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0
