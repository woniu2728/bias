from ninja import Body, Router
from django.db.models import Max
from django.shortcuts import get_object_or_404

from apps.core.admin_api import admin_error
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.tags.models import Tag
from extensions.tags.backend.services import TagService


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return admin_error("需要管理员权限", status=403)
    return None


def serialize_admin_tag(tag: Tag):
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "description": tag.description,
        "color": tag.color or "#888",
        "icon": tag.icon,
        "position": tag.position,
        "parent_id": tag.parent_id,
        "parent_name": tag.parent.name if tag.parent else None,
        "discussion_count": tag.discussion_count,
        "is_hidden": tag.is_hidden,
        "is_restricted": tag.is_restricted,
        "view_scope": tag.view_scope,
        "start_discussion_scope": tag.start_discussion_scope,
        "reply_scope": tag.reply_scope,
        "view_scope_label": TagService.get_scope_label(tag.view_scope),
        "start_discussion_scope_label": TagService.get_scope_label(tag.start_discussion_scope),
        "reply_scope_label": TagService.get_scope_label(tag.reply_scope),
    }


def normalize_optional_tag_parent(payload):
    normalized = dict(payload)
    if "parent_id" in normalized:
        parent_id = normalized.get("parent_id")
        normalized["parent_id"] = None if parent_id in ("", 0, "0") else parent_id
    return normalized


def normalize_tag_position(payload, parent_id=None, current_tag: Tag = None) -> int:
    if "position" in payload and payload.get("position") is not None:
        return int(payload["position"])

    queryset = Tag.objects.filter(parent_id=parent_id)
    if current_tag is not None:
        queryset = queryset.exclude(id=current_tag.id)
    return (queryset.aggregate(max_position=Max("position")).get("max_position") or 0) + 1


@router.get("/tags", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_tags(request):
    denied = _require_staff(request)
    if denied:
        return denied

    tags = Tag.objects.select_related("parent").all().order_by("position", "name")
    return [serialize_admin_tag(tag) for tag in tags]


@router.post("/tags", auth=AccessTokenAuth(), tags=["Admin"])
def create_admin_tag(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        normalized = normalize_optional_tag_parent(payload)
        name = (normalized.get("name") or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")
        parent_id = normalized.get("parent_id")
        tag = TagService.create_tag(
            name=name,
            slug=(normalized.get("slug") or "").strip() or None,
            description=normalized.get("description", ""),
            color=normalized.get("color") or "#888",
            icon=(normalized.get("icon") or "").strip(),
            position=normalize_tag_position(normalized, parent_id=parent_id),
            parent_id=parent_id,
            is_hidden=bool(normalized.get("is_hidden", False)),
            is_restricted=bool(normalized.get("is_restricted", False)),
            view_scope=normalized.get("view_scope") or Tag.ACCESS_PUBLIC,
            start_discussion_scope=normalized.get("start_discussion_scope") or Tag.ACCESS_MEMBERS,
            reply_scope=normalized.get("reply_scope") or Tag.ACCESS_MEMBERS,
            user=request.auth,
        )
        tag = Tag.objects.select_related("parent").get(id=tag.id)
        log_admin_action(
            request,
            "admin.tag.create",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "slug": tag.slug, "parent_id": tag.parent_id},
        )
        return serialize_admin_tag(tag)
    except ValueError as exc:
        return admin_error(str(exc), status=400)
    except Exception as exc:
        return admin_error(str(exc), status=400)


@router.put("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_admin_tag(request, tag_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        tag = get_object_or_404(Tag, id=tag_id)
        normalized = normalize_optional_tag_parent(payload)
        next_view_scope = tag.view_scope
        next_start_scope = tag.start_discussion_scope
        next_reply_scope = tag.reply_scope

        if "name" in normalized:
            name = (normalized.get("name") or "").strip()
            if not name:
                raise ValueError("标签名称不能为空")
            tag.name = name
        if "slug" in normalized:
            tag.slug = (normalized.get("slug") or "").strip()
        if "description" in normalized:
            tag.description = normalized.get("description") or ""
        if "color" in normalized:
            tag.color = normalized.get("color") or "#888"
        if "icon" in normalized:
            tag.icon = (normalized.get("icon") or "").strip()
        if "position" in normalized and normalized.get("position") is not None:
            tag.position = int(normalized["position"])
        if "parent_id" in normalized:
            parent_id = normalized.get("parent_id")
            if parent_id is None:
                tag.parent = None
            else:
                parent = get_object_or_404(Tag, id=parent_id)
                TagService.validate_parent_assignment(tag, parent)
                tag.parent = parent
        if "is_hidden" in normalized:
            tag.is_hidden = bool(normalized["is_hidden"])
        if "is_restricted" in normalized:
            tag.is_restricted = bool(normalized["is_restricted"])
        if "view_scope" in normalized:
            next_view_scope = normalized.get("view_scope")
        if "start_discussion_scope" in normalized:
            next_start_scope = normalized.get("start_discussion_scope")
        if "reply_scope" in normalized:
            next_reply_scope = normalized.get("reply_scope")
        (
            tag.view_scope,
            tag.start_discussion_scope,
            tag.reply_scope,
        ) = TagService.validate_scope_configuration(
            next_view_scope,
            next_start_scope,
            next_reply_scope,
        )
        tag.save()
        tag.refresh_from_db()
        log_admin_action(
            request,
            "admin.tag.update",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "slug": tag.slug, "changed_fields": sorted(normalized.keys())},
        )
        return serialize_admin_tag(tag)
    except ValueError as exc:
        return admin_error(str(exc), status=400)
    except Exception as exc:
        return admin_error(str(exc), status=400)


@router.post("/tags/{tag_id}/move", auth=AccessTokenAuth(), tags=["Admin"])
def move_admin_tag(request, tag_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        tag = get_object_or_404(Tag, id=tag_id)
        moved = TagService.move_tag(
            tag_id=tag_id,
            direction=(payload.get("direction") or "").strip(),
            user=request.auth,
        )
        tags = Tag.objects.select_related("parent").all().order_by("position", "name")
        log_admin_action(
            request,
            "admin.tag.move",
            target_type="tag",
            target_id=tag.id,
            data={"name": tag.name, "direction": (payload.get("direction") or "").strip(), "moved": bool(moved)},
        )
        return {
            "moved": moved,
            "data": [serialize_admin_tag(item) for item in tags],
        }
    except ValueError as exc:
        return admin_error(str(exc), status=400)
    except Tag.DoesNotExist:
        return admin_error("标签不存在", status=404)


@router.delete("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_admin_tag(request, tag_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        tag = get_object_or_404(Tag, id=tag_id)
        tag_snapshot = {"name": tag.name, "slug": tag.slug, "parent_id": tag.parent_id}
        TagService.delete_tag(tag_id, request.auth)
        log_admin_action(
            request,
            "admin.tag.delete",
            target_type="tag",
            target_id=tag_id,
            data=tag_snapshot,
        )
        return {"message": "标签删除成功"}
    except ValueError as exc:
        return admin_error(str(exc), status=400)


@router.post("/tags/stats/refresh", auth=AccessTokenAuth(), tags=["Admin"])
def refresh_admin_tag_stats(request):
    denied = _require_staff(request)
    if denied:
        return denied

    result = TagService.dispatch_refresh_tag_stats()
    log_admin_action(
        request,
        "admin.tag.refresh_stats",
        target_type="tag",
        data={
            "mode": result.get("mode"),
            "tag_ids": result.get("tag_ids"),
        },
    )
    return result
