from __future__ import annotations

from django.core.exceptions import ValidationError
from ninja import Body, Router

from apps.core.extensions.platform import api_error
from apps.core.extensions.platform import log_admin_action
from apps.core.extensions.runtime import (
    bulk_process_runtime_approval_items,
    has_runtime_forum_permission,
    list_runtime_approval_queue_items,
    process_runtime_approval_item,
)
from apps.core.extensions.platform import AccessTokenAuth
from apps.core.extensions.platform import PaginationService


router = Router()


def _require_admin_permission(request, permission_code: str, message: str):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    if not has_runtime_forum_permission(request.auth, permission_code):
        return api_error(message, status=403, code="permission_denied")
    return None


@router.get("/approval-queue", auth=AccessTokenAuth(), tags=["Admin"])
def list_approval_queue(request, page: int = 1, limit: int = 20, content_type: str = "all"):
    denied = _require_admin_permission(request, "admin.approval.view", "没有查看审核队列的权限")
    if denied:
        return denied

    page, limit = PaginationService.normalize(page, limit)
    items = list_runtime_approval_queue_items(content_type=content_type)
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
        item = process_runtime_approval_item(
            content_type=content_type,
            content_id=content_id,
            action="approve",
            actor=request.auth,
            note=note,
        )
        _log_processed_approval_item(request, item, "approve", note)
        return item
    except ValidationError as exc:
        return api_error(str(exc), status=400)


@router.post("/approval-queue/{content_type}/{content_id}/reject", auth=AccessTokenAuth(), tags=["Admin"])
def reject_content(request, content_type: str, content_id: int, payload: dict = Body(...)):
    denied = _require_admin_permission(request, "admin.approval.reject", "没有拒绝审核内容的权限")
    if denied:
        return denied

    note = payload.get("note", "")
    try:
        item = process_runtime_approval_item(
            content_type=content_type,
            content_id=content_id,
            action="reject",
            actor=request.auth,
            note=note,
        )
        _log_processed_approval_item(request, item, "reject", note)
        return item
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
    try:
        processed_items = bulk_process_runtime_approval_items(
            action=action,
            items=payload.get("items"),
            actor=request.auth,
            note=note,
        )
    except ValidationError as exc:
        return api_error(str(exc), status=400)

    for item in processed_items:
        _log_processed_approval_item(request, item, action, note)

    return {
        "processed_count": len(processed_items),
        "action": action,
        "data": processed_items,
    }


def _log_processed_approval_item(request, item: dict, action: str, note: str = "") -> None:
    item_type = str(item.get("type") or "").strip()
    if item_type == "discussion":
        log_admin_action(
            request,
            f"admin.approval.{action}",
            target_type="discussion",
            target_id=item.get("id"),
            data={"note": note, "title": item.get("title", "")},
        )
        return
    if item_type == "post":
        discussion = item.get("discussion") or {}
        log_admin_action(
            request,
            f"admin.approval.{action}",
            target_type="post",
            target_id=item.get("id"),
            data={"note": note, "discussion_id": discussion.get("id")},
        )
