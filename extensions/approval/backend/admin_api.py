from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Body, Router

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.services import PaginationService
from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from extensions.posts.backend.models import Post
from apps.posts.services import PostService
from apps.users.services import UserService


router = Router()


def _require_admin_permission(request, permission_code: str, message: str):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    if not UserService.has_forum_permission(request.auth, permission_code):
        return api_error(message, status=403, code="permission_denied")
    return None


def _serialize_approval_item(content_type: str, item):
    if content_type == "discussion":
        first_post = Post.objects.filter(id=item.first_post_id).select_related("user").first()
        return {
            "type": "discussion",
            "id": item.id,
            "title": item.title,
            "content": first_post.content if first_post else "",
            "created_at": item.created_at,
            "approval_status": item.approval_status,
            "approval_note": item.approval_note,
            "author": {
                "id": item.user.id,
                "username": item.user.username,
                "display_name": item.user.display_name,
            } if item.user else None,
            "discussion": {
                "id": item.id,
                "title": item.title,
            },
            "post": {
                "id": first_post.id,
                "number": first_post.number,
            } if first_post else None,
        }

    return {
        "type": "post",
        "id": item.id,
        "title": item.discussion.title if item.discussion else "回复审核",
        "content": item.content,
        "created_at": item.created_at,
        "approval_status": item.approval_status,
        "approval_note": item.approval_note,
        "author": {
            "id": item.user.id,
            "username": item.user.username,
            "display_name": item.user.display_name,
        } if item.user else None,
        "discussion": {
            "id": item.discussion.id,
            "title": item.discussion.title,
        } if item.discussion else None,
        "post": {
            "id": item.id,
            "number": item.number,
        },
    }


def _process_approval_action(request, content_type: str, content_id: int, action: str, note: str = ""):
    if content_type == "discussion":
        discussion = get_object_or_404(
            Discussion.objects.select_related("user"),
            id=content_id,
            approval_status=Discussion.APPROVAL_PENDING,
        )
        if action == "approve":
            processed = DiscussionService.approve_discussion(discussion, request.auth, note=note)
            log_action = "admin.approval.approve"
        else:
            processed = DiscussionService.reject_discussion(discussion, request.auth, note=note)
            log_action = "admin.approval.reject"

        log_admin_action(
            request,
            log_action,
            target_type="discussion",
            target_id=processed.id,
            data={"note": note, "title": processed.title},
        )
        return _serialize_approval_item("discussion", processed)

    if content_type == "post":
        post = get_object_or_404(
            Post.objects.select_related("discussion", "user"),
            id=content_id,
            approval_status=Post.APPROVAL_PENDING,
        )
        if action == "approve":
            processed = PostService.approve_post(post, request.auth, note=note)
            log_action = "admin.approval.approve"
        else:
            processed = PostService.reject_post(post, request.auth, note=note)
            log_action = "admin.approval.reject"

        log_admin_action(
            request,
            log_action,
            target_type="post",
            target_id=processed.id,
            data={"note": note, "discussion_id": processed.discussion_id},
        )
        return _serialize_approval_item("post", processed)

    raise ValidationError("无效的审核内容类型")


@router.get("/approval-queue", auth=AccessTokenAuth(), tags=["Admin"])
def list_approval_queue(request, page: int = 1, limit: int = 20, content_type: str = "all"):
    denied = _require_admin_permission(request, "admin.approval.view", "没有查看审核队列的权限")
    if denied:
        return denied

    page, limit = PaginationService.normalize(page, limit)
    items = []

    if content_type in {"all", "discussion"}:
        discussions = Discussion.objects.filter(
            approval_status=Discussion.APPROVAL_PENDING
        ).select_related("user").order_by("-created_at")
        items.extend([_serialize_approval_item("discussion", discussion) for discussion in discussions])

    if content_type in {"all", "post"}:
        discussion_first_post_ids = Discussion.objects.filter(
            approval_status=Discussion.APPROVAL_PENDING
        ).values_list("first_post_id", flat=True)
        posts = Post.objects.filter(
            approval_status=Post.APPROVAL_PENDING
        ).exclude(
            id__in=discussion_first_post_ids
        ).select_related("user", "discussion").order_by("-created_at")
        items.extend([_serialize_approval_item("post", post) for post in posts])

    items.sort(key=lambda item: item["created_at"], reverse=True)
    total = len(items)
    offset = (page - 1) * limit
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": items[offset:offset + limit],
    }


@router.post("/approval-queue/{content_type}/{content_id}/approve", auth=AccessTokenAuth(), tags=["Admin"])
def approve_content(request, content_type: str, content_id: int, payload: dict = Body(...)):
    denied = _require_admin_permission(request, "admin.approval.approve", "没有通过审核内容的权限")
    if denied:
        return denied

    note = payload.get("note", "")
    try:
        return _process_approval_action(request, content_type, content_id, "approve", note)
    except ValidationError as exc:
        return api_error(str(exc), status=400)


@router.post("/approval-queue/{content_type}/{content_id}/reject", auth=AccessTokenAuth(), tags=["Admin"])
def reject_content(request, content_type: str, content_id: int, payload: dict = Body(...)):
    denied = _require_admin_permission(request, "admin.approval.reject", "没有拒绝审核内容的权限")
    if denied:
        return denied

    note = payload.get("note", "")
    try:
        return _process_approval_action(request, content_type, content_id, "reject", note)
    except ValidationError as exc:
        return api_error(str(exc), status=400)


@router.post("/approval-queue/bulk/{action}", auth=AccessTokenAuth(), tags=["Admin"])
def bulk_process_approval_queue(request, action: str, payload: dict = Body(...)):
    if action not in {"approve", "reject"}:
        return api_error("无效的审核动作", status=400)

    permission_code = "admin.approval.approve" if action == "approve" else "admin.approval.reject"
    permission_message = "没有通过审核内容的权限" if action == "approve" else "没有拒绝审核内容的权限"
    denied = _require_admin_permission(request, permission_code, permission_message)
    if denied:
        return denied

    note = payload.get("note", "")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return api_error("请至少选择一条待审核内容", status=400)

    processed_items = []

    try:
        with transaction.atomic():
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    raise ValidationError("审核项格式无效")

                content_type = str(raw_item.get("type") or "").strip()
                content_id = raw_item.get("id")
                if not content_type or not content_id:
                    raise ValidationError("审核项缺少类型或 ID")

                processed_items.append(
                    _process_approval_action(request, content_type, int(content_id), action, note)
                )
    except ValidationError as exc:
        return api_error(str(exc), status=400)

    return {
        "processed_count": len(processed_items),
        "action": action,
        "data": processed_items,
    }
