"""
管理后台API端点
"""
import sys
import functools

from ninja import Router, Body
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from typing import List, Dict, Any
from django.db.models import Count, Max, Q
from django.core.cache import cache

from apps.core.email_service import EmailService
from apps.core.settings_service import (
    ADVANCED_SETTINGS_DEFAULTS,
    APPEARANCE_SETTINGS_DEFAULTS,
    BASIC_SETTINGS_DEFAULTS,
    MAIL_SETTINGS_DEFAULTS,
    clear_runtime_setting_caches,
    get_advanced_settings as get_runtime_advanced_settings,
    get_setting_group,
    save_setting_group,
)
from apps.users.models import User, Group, Permission
from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.tags.services import TagService

router = Router()


class AuthBearer(HttpBearer):
    """JWT认证"""
    def authenticate(self, request, token):
        try:
            from ninja_jwt.authentication import JWTAuth
            jwt_auth = JWTAuth()
            return jwt_auth.authenticate(request, token)
        except Exception:
            return None


def admin_error(message: str, status: int = 400):
    return JsonResponse({"error": message}, status=status)


def serialize_group(group: Group) -> Dict[str, Any]:
    return {
        "id": group.id,
        "name": group.name,
        "name_singular": group.name_singular,
        "name_plural": group.name_plural,
        "color": group.color,
        "icon": group.icon,
        "is_hidden": group.is_hidden,
    }


def serialize_admin_tag(tag: Tag) -> Dict[str, Any]:
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
    }


def normalize_optional_tag_parent(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    if "parent_id" in normalized:
        parent_id = normalized.get("parent_id")
        normalized["parent_id"] = None if parent_id in ("", 0, "0") else parent_id
    return normalized


def normalize_tag_position(payload: Dict[str, Any], parent_id=None, current_tag: Tag = None) -> int:
    if "position" in payload and payload.get("position") is not None:
        return int(payload["position"])

    queryset = Tag.objects.filter(parent_id=parent_id)
    if current_tag is not None:
        queryset = queryset.exclude(id=current_tag.id)
    return (queryset.aggregate(max_position=Max("position")).get("max_position") or 0) + 1


def validate_group_payload(payload: Dict[str, Any], group: Group = None):
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("用户组名称不能为空")

    queryset = Group.objects.filter(name=name)
    if group is not None:
        queryset = queryset.exclude(id=group.id)
    if queryset.exists():
        raise ValueError("用户组名称已存在")

    return {
        "name": name,
        "name_singular": (payload.get("name_singular") or name).strip(),
        "name_plural": (payload.get("name_plural") or f"{name}s").strip(),
        "color": payload.get("color") or "#4d698e",
        "icon": (payload.get("icon") or "").strip(),
        "is_hidden": bool(payload.get("is_hidden", False)),
    }


def serialize_admin_user(user: User, include_details: bool = False) -> Dict[str, Any]:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_email_confirmed": user.is_email_confirmed,
        "is_staff": user.is_staff,
        "is_suspended": user.is_suspended,
        "joined_at": user.joined_at,
        "last_seen_at": user.last_seen_at,
        "discussion_count": user.discussion_count,
        "comment_count": user.comment_count,
        "groups": [serialize_group(group) for group in user.user_groups.all().order_by("name")],
    }

    if include_details:
        payload.update({
            "bio": user.bio,
            "suspended_until": user.suspended_until,
            "suspend_reason": user.suspend_reason,
            "suspend_message": user.suspend_message,
        })

    return payload


def parse_optional_datetime(value):
    if value in (None, "", False):
        return None

    parsed = parse_datetime(str(value))
    if not parsed:
        raise ValueError("封禁截止时间格式无效")

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())

    return parsed


def require_staff(func):
    """装饰器：要求管理员权限"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.auth or not request.auth.is_staff:
            return admin_error("需要管理员权限", status=403)
        return func(request, *args, **kwargs)
    return wrapper


# ==================== 统计数据 ====================

@router.get("/stats", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_stats(request):
    """获取系统统计数据"""
    advanced_settings = get_runtime_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    if not advanced_settings.get("queue_enabled", False):
        queue_driver = "sync"

    return {
        "phpVersion": f"Python {sys.version.split()[0]}",
        "dbDriver": "SQLite/PostgreSQL/MySQL",
        "queueDriver": queue_driver,
        "sessionDriver": "database",
        "totalUsers": User.objects.count(),
        "totalDiscussions": Discussion.objects.count(),
        "totalPosts": Post.objects.count(),
        "openFlags": PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).count(),
        "pendingApprovals": (
            Discussion.objects.filter(approval_status=Discussion.APPROVAL_PENDING).count()
            + Post.objects.filter(approval_status=Post.APPROVAL_PENDING).exclude(
                id__in=Discussion.objects.filter(
                    approval_status=Discussion.APPROVAL_PENDING
                ).values_list("first_post_id", flat=True)
            ).count()
        ),
    }


# ==================== 设置管理 ====================

@router.get("/settings", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_settings(request):
    """获取论坛设置"""
    return get_setting_group("basic", BASIC_SETTINGS_DEFAULTS)


@router.post("/settings", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存论坛设置"""
    settings_data = save_setting_group("basic", BASIC_SETTINGS_DEFAULTS, payload)
    return {"message": "设置保存成功", "settings": settings_data}


@router.get("/appearance", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_appearance_settings(request):
    """获取外观设置"""
    return get_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS)


@router.post("/appearance", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_appearance_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存外观设置"""
    settings_data = save_setting_group("appearance", APPEARANCE_SETTINGS_DEFAULTS, payload)
    return {"message": "外观设置保存成功", "settings": settings_data}


@router.get("/mail", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_mail_settings(request):
    """获取邮件设置"""
    return get_setting_group("mail", MAIL_SETTINGS_DEFAULTS)


@router.post("/mail", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_mail_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存邮件设置"""
    settings_data = save_setting_group("mail", MAIL_SETTINGS_DEFAULTS, payload)
    return {"message": "邮件设置保存成功", "settings": settings_data}


@router.post("/mail/test", auth=AuthBearer(), tags=["Admin"])
@require_staff
def send_test_email(request):
    """发送测试邮件"""
    if not request.auth.email:
        return admin_error("当前管理员没有邮箱地址", status=400)

    try:
        sent_count = EmailService.send_test_email(request.auth.email)
    except Exception as e:
        return admin_error(str(e), status=400)

    return {"message": "测试邮件已发送", "sent_count": sent_count}


@router.get("/advanced", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_advanced_settings(request):
    """获取高级设置"""
    return get_runtime_advanced_settings()


@router.post("/advanced", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_advanced_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存高级设置"""
    runtime_payload = dict(payload)
    runtime_payload.pop("debug_mode", None)

    settings_data = save_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS, runtime_payload)
    settings_data["debug_mode"] = get_runtime_advanced_settings()["debug_mode"]
    return {"message": "高级设置保存成功", "settings": settings_data}


@router.post("/cache/clear", auth=AuthBearer(), tags=["Admin"])
@require_staff
def clear_cache(request):
    """清除 Django 缓存"""
    try:
        cache.clear()
        clear_runtime_setting_caches()
    except Exception as e:
        return admin_error(f"缓存清理失败: {e}", status=503)

    return {"message": "缓存已清除"}


# ==================== 用户组管理 ====================

@router.get("/groups", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_groups(request):
    """获取用户组列表"""
    groups = Group.objects.all().order_by("id", "name")
    return [serialize_group(group) for group in groups]


@router.post("/groups", auth=AuthBearer(), tags=["Admin"])
@require_staff
def create_group(request, payload: Dict[str, Any] = Body(...)):
    """创建用户组"""
    try:
        validated = validate_group_payload(payload)
        group = Group.objects.create(**validated)
        return serialize_group(group)
    except ValueError as e:
        return admin_error(str(e), status=400)


@router.put("/groups/{group_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def update_group(request, group_id: int, payload: Dict[str, Any] = Body(...)):
    """更新用户组"""
    group = get_object_or_404(Group, id=group_id)

    try:
        validated = validate_group_payload(payload, group=group)
    except ValueError as e:
        return admin_error(str(e), status=400)

    for field, value in validated.items():
        setattr(group, field, value)
    group.save()

    return serialize_group(group)


def serialize_post_flag(flag: PostFlag) -> Dict[str, Any]:
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


def serialize_approval_item(content_type: str, item) -> Dict[str, Any]:
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


# ==================== 权限管理 ====================

@router.get("/permissions", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_permissions(request):
    """获取权限配置"""
    permissions = Permission.objects.select_related('group').all()

    # 按用户组组织权限
    result = {}
    for perm in permissions:
        group_id = perm.group.id
        if group_id not in result:
            result[group_id] = []
        result[group_id].append(perm.permission)

    return result


@router.post("/permissions", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_permissions(request, payload: Dict[int, List[str]] = Body(...)):
    """保存权限配置"""
    # 删除所有现有权限
    Permission.objects.all().delete()

    # 创建新权限
    for group_id, permissions in payload.items():
        group = Group.objects.get(id=group_id)
        for permission in permissions:
            Permission.objects.create(
                group=group,
                permission=permission
            )

    return {"message": "权限保存成功"}


# ==================== 用户管理 ====================

@router.get("/users", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_admin_users(request, page: int = 1, limit: int = 20, q: str = None):
    """获取用户列表（管理后台）"""
    queryset = User.objects.prefetch_related("user_groups").all().order_by("-joined_at")

    if q:
        queryset = queryset.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(display_name__icontains=q)
        )

    total = queryset.count()
    offset = (page - 1) * limit
    users = queryset[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [serialize_admin_user(user) for user in users]
    }


@router.get("/users/{user_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_admin_user(request, user_id: int):
    """获取单个用户详情（管理后台）"""
    user = get_object_or_404(User.objects.prefetch_related("user_groups"), id=user_id)
    return serialize_admin_user(user, include_details=True)


@router.put("/users/{user_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def update_admin_user(request, user_id: int, payload: Dict[str, Any] = Body(...)):
    """更新用户信息（管理后台）"""
    user = get_object_or_404(User.objects.prefetch_related("user_groups"), id=user_id)

    if user.id == request.auth.id and "is_staff" in payload and not payload.get("is_staff"):
        return admin_error("不能取消自己的管理员权限", status=400)

    username = payload.get("username")
    if username and username != user.username:
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            return admin_error("用户名已存在", status=400)
        user.username = username

    email = payload.get("email")
    if email is not None and email != user.email:
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            return admin_error("邮箱已被使用", status=400)
        user.email = email

    if "display_name" in payload:
        user.display_name = payload.get("display_name") or ""
    if "bio" in payload:
        user.bio = payload.get("bio") or ""
    if "is_staff" in payload:
        user.is_staff = bool(payload.get("is_staff"))
    if "is_email_confirmed" in payload:
        user.is_email_confirmed = bool(payload.get("is_email_confirmed"))

    try:
        if "suspended_until" in payload:
            user.suspended_until = parse_optional_datetime(payload.get("suspended_until"))
    except ValueError as e:
        return admin_error(str(e), status=400)

    if "suspend_reason" in payload:
        user.suspend_reason = payload.get("suspend_reason") or ""
    if "suspend_message" in payload:
        user.suspend_message = payload.get("suspend_message") or ""

    group_ids = payload.get("group_ids")
    if group_ids is not None:
        try:
            normalized_group_ids = [int(group_id) for group_id in group_ids]
        except (TypeError, ValueError):
            return admin_error("用户组参数无效", status=400)

        groups = list(Group.objects.filter(id__in=normalized_group_ids))
        if len(groups) != len(set(normalized_group_ids)):
            return admin_error("包含无效的用户组", status=400)
    else:
        groups = None

    user.save()

    if groups is not None:
        user.user_groups.set(groups)

    user.refresh_from_db()
    return serialize_admin_user(user, include_details=True)


@router.get("/flags", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_post_flags(request, page: int = 1, limit: int = 20, status: str = PostFlag.STATUS_OPEN):
    """获取帖子举报列表"""
    flags, total = PostService.get_flag_list(status=status, page=page, limit=limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [serialize_post_flag(flag) for flag in flags],
    }


@router.get("/approval-queue", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_approval_queue(request, page: int = 1, limit: int = 20, content_type: str = "all"):
    items = []

    if content_type in {"all", "discussion"}:
        discussions = Discussion.objects.filter(
            approval_status=Discussion.APPROVAL_PENDING
        ).select_related("user").order_by("-created_at")
        items.extend([serialize_approval_item("discussion", discussion) for discussion in discussions])

    if content_type in {"all", "post"}:
        discussion_first_post_ids = Discussion.objects.filter(
            approval_status=Discussion.APPROVAL_PENDING
        ).values_list("first_post_id", flat=True)
        posts = Post.objects.filter(
            approval_status=Post.APPROVAL_PENDING
        ).exclude(
            id__in=discussion_first_post_ids
        ).select_related("user", "discussion").order_by("-created_at")
        items.extend([serialize_approval_item("post", post) for post in posts])

    items.sort(key=lambda item: item["created_at"], reverse=True)
    total = len(items)
    offset = (page - 1) * limit
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": items[offset:offset + limit],
    }


@router.post("/approval-queue/{content_type}/{content_id}/approve", auth=AuthBearer(), tags=["Admin"])
@require_staff
def approve_content(request, content_type: str, content_id: int, payload: Dict[str, Any] = Body(...)):
    note = payload.get("note", "")

    if content_type == "discussion":
        discussion = get_object_or_404(Discussion, id=content_id, approval_status=Discussion.APPROVAL_PENDING)
        approved = DiscussionService.approve_discussion(discussion, request.auth, note=note)
        return serialize_approval_item("discussion", approved)

    if content_type == "post":
        post = get_object_or_404(Post.objects.select_related("discussion", "user"), id=content_id, approval_status=Post.APPROVAL_PENDING)
        approved = PostService.approve_post(post, request.auth, note=note)
        return serialize_approval_item("post", approved)

    return admin_error("无效的审核内容类型", status=400)


@router.post("/approval-queue/{content_type}/{content_id}/reject", auth=AuthBearer(), tags=["Admin"])
@require_staff
def reject_content(request, content_type: str, content_id: int, payload: Dict[str, Any] = Body(...)):
    note = payload.get("note", "")

    if content_type == "discussion":
        discussion = get_object_or_404(Discussion, id=content_id, approval_status=Discussion.APPROVAL_PENDING)
        rejected = DiscussionService.reject_discussion(discussion, request.auth, note=note)
        return serialize_approval_item("discussion", rejected)

    if content_type == "post":
        post = get_object_or_404(Post.objects.select_related("discussion", "user"), id=content_id, approval_status=Post.APPROVAL_PENDING)
        rejected = PostService.reject_post(post, request.auth, note=note)
        return serialize_approval_item("post", rejected)

    return admin_error("无效的审核内容类型", status=400)


@router.post("/flags/{flag_id}/resolve", auth=AuthBearer(), tags=["Admin"])
@require_staff
def resolve_post_flag(request, flag_id: int, payload: Dict[str, Any] = Body(...)):
    """处理帖子举报"""
    try:
        flag = PostService.resolve_flag(
            flag_id=flag_id,
            admin_user=request.auth,
            status=payload.get("status", PostFlag.STATUS_RESOLVED),
            resolution_note=payload.get("resolution_note", ""),
        )
        return serialize_post_flag(flag)
    except PostFlag.DoesNotExist:
        return admin_error("举报记录不存在", status=404)
    except ValueError as e:
        return admin_error(str(e), status=400)


# ==================== 标签管理 ====================

@router.get("/tags", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_admin_tags(request):
    """获取标签列表（管理后台）"""
    TagService.refresh_tag_stats()

    tags = Tag.objects.select_related("parent").all().order_by("position", "name")
    return [serialize_admin_tag(tag) for tag in tags]


@router.post("/tags", auth=AuthBearer(), tags=["Admin"])
@require_staff
def create_admin_tag(request, payload: Dict[str, Any] = Body(...)):
    """创建标签"""
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
            user=request.auth,
        )
        tag = Tag.objects.select_related("parent").get(id=tag.id)
        return serialize_admin_tag(tag)
    except ValueError as e:
        return admin_error(str(e), status=400)
    except Exception as e:
        return admin_error(str(e), status=400)


@router.put("/tags/{tag_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def update_admin_tag(request, tag_id: int, payload: Dict[str, Any] = Body(...)):
    """更新标签"""
    try:
        tag = get_object_or_404(Tag, id=tag_id)
        normalized = normalize_optional_tag_parent(payload)

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
                if int(parent_id) == tag.id:
                    raise ValueError("标签不能设置自己为父标签")
                parent = get_object_or_404(Tag, id=parent_id)
                if TagService._would_create_cycle(tag, parent):
                    raise ValueError("不能设置子标签为父标签")
                tag.parent = parent
        if "is_hidden" in normalized:
            tag.is_hidden = bool(normalized["is_hidden"])
        if "is_restricted" in normalized:
            tag.is_restricted = bool(normalized["is_restricted"])
        tag.save()
        tag.refresh_from_db()
        return serialize_admin_tag(tag)
    except ValueError as e:
        return admin_error(str(e), status=400)
    except Exception as e:
        return admin_error(str(e), status=400)


@router.delete("/tags/{tag_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def delete_admin_tag(request, tag_id: int):
    """删除标签"""
    try:
        TagService.delete_tag(tag_id, request.auth)
        return {"message": "标签删除成功"}
    except ValueError as e:
        return admin_error(str(e), status=400)
