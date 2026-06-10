from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.extensions.runtime_access import (
    approve_runtime_discussion,
    get_runtime_discussion_model,
    reject_runtime_discussion,
)
from apps.core.extensions.runtime_access import (
    approve_runtime_post,
    get_runtime_post_model,
    reject_runtime_post,
)


def approval_service_provider() -> dict:
    return {
        "serialize_item": serialize_approval_item,
        "list_queue": list_approval_queue_items,
        "process_item": process_approval_item,
        "bulk_process": bulk_process_approval_items,
    }


def serialize_approval_item(content_type: str, item) -> dict:
    if content_type == "discussion":
        post_model = get_runtime_post_model()
        first_post = post_model.objects.filter(id=item.first_post_id).select_related("user").first()
        return {
            "type": "discussion",
            "id": item.id,
            "title": item.title,
            "content": first_post.content if first_post else "",
            "created_at": item.created_at,
            "approval_status": item.approval_status,
            "approval_note": item.approval_note,
            "author": _serialize_user(getattr(item, "user", None)),
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
        "author": _serialize_user(getattr(item, "user", None)),
        "discussion": {
            "id": item.discussion.id,
            "title": item.discussion.title,
        } if item.discussion else None,
        "post": {
            "id": item.id,
            "number": item.number,
        },
    }


def list_approval_queue_items(*, content_type: str = "all") -> list[dict]:
    items = []
    discussion_model = get_runtime_discussion_model()
    post_model = get_runtime_post_model()

    if content_type in {"all", "discussion"}:
        discussions = discussion_model.objects.filter(
            approval_status=discussion_model.APPROVAL_PENDING
        ).select_related("user").order_by("-created_at")
        items.extend(serialize_approval_item("discussion", discussion) for discussion in discussions)

    if content_type in {"all", "post"}:
        discussion_first_post_ids = discussion_model.objects.filter(
            approval_status=discussion_model.APPROVAL_PENDING
        ).values_list("first_post_id", flat=True)
        posts = post_model.objects.filter(
            approval_status=post_model.APPROVAL_PENDING
        ).exclude(
            id__in=discussion_first_post_ids
        ).select_related("user", "discussion").order_by("-created_at")
        items.extend(serialize_approval_item("post", post) for post in posts)

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def process_approval_item(*, content_type: str, content_id: int, action: str, actor, note: str = "") -> dict:
    normalized_type = str(content_type or "").strip()
    normalized_action = str(action or "").strip()
    if normalized_type == "discussion":
        return _process_discussion_approval(content_id, normalized_action, actor, note)
    if normalized_type == "post":
        return _process_post_approval(content_id, normalized_action, actor, note)
    raise ValidationError("无效的审核内容类型")


def bulk_process_approval_items(*, action: str, items, actor, note: str = "") -> list[dict]:
    if action not in {"approve", "reject"}:
        raise ValidationError("无效的审核动作")
    if not isinstance(items, list) or not items:
        raise ValidationError("请至少选择一条待审核内容")

    processed_items = []
    with transaction.atomic():
        for raw_item in items:
            if not isinstance(raw_item, dict):
                raise ValidationError("审核项格式无效")

            content_type = str(raw_item.get("type") or "").strip()
            content_id = raw_item.get("id")
            if not content_type or not content_id:
                raise ValidationError("审核项缺少类型或 ID")

            processed_items.append(
                process_approval_item(
                    content_type=content_type,
                    content_id=int(content_id),
                    action=action,
                    actor=actor,
                    note=note,
                )
            )
    return processed_items


def _process_discussion_approval(content_id: int, action: str, actor, note: str) -> dict:
    discussion_model = get_runtime_discussion_model()
    discussion = get_object_or_404(
        discussion_model.objects.select_related("user"),
        id=content_id,
        approval_status=discussion_model.APPROVAL_PENDING,
    )
    if action == "approve":
        processed = approve_runtime_discussion(discussion, actor, note=note)
    elif action == "reject":
        processed = reject_runtime_discussion(discussion, actor, note=note)
    else:
        raise ValidationError("无效的审核动作")
    return serialize_approval_item("discussion", processed)


def _process_post_approval(content_id: int, action: str, actor, note: str) -> dict:
    post_model = get_runtime_post_model()
    post = get_object_or_404(
        post_model.objects.select_related("discussion", "user"),
        id=content_id,
        approval_status=post_model.APPROVAL_PENDING,
    )
    if action == "approve":
        processed = approve_runtime_post(post, actor, note=note)
    elif action == "reject":
        processed = reject_runtime_post(post, actor, note=note)
    else:
        raise ValidationError("无效的审核动作")
    return serialize_approval_item("post", processed)


def _serialize_user(user) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
    }

