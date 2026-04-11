"""
管理后台API端点
"""
import json
import sys
import functools

from ninja import Router, Body
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from typing import List, Dict, Any
from django.db.models import Count, Q
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from apps.core.models import Setting
from apps.users.models import User, Group, Permission
from apps.discussions.models import Discussion
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag

router = Router()

BASIC_SETTINGS_DEFAULTS = {
    "forum_title": "PyFlarum",
    "forum_description": "",
    "welcome_title": "欢迎来到PyFlarum",
    "welcome_message": "这是一个基于Django和Vue 3的现代化论坛",
    "default_locale": "zh-CN",
    "show_language_selector": False,
}

APPEARANCE_SETTINGS_DEFAULTS = {
    "primary_color": "#4d698e",
    "accent_color": "#e74c3c",
    "logo_url": "",
    "favicon_url": "",
    "custom_css": "",
    "custom_header": "",
}

MAIL_SETTINGS_DEFAULTS = {
    "mail_driver": "smtp",
    "mail_host": getattr(settings, "EMAIL_HOST", ""),
    "mail_port": getattr(settings, "EMAIL_PORT", 587),
    "mail_encryption": "tls" if getattr(settings, "EMAIL_USE_TLS", False) else "",
    "mail_username": getattr(settings, "EMAIL_HOST_USER", ""),
    "mail_password": "",
    "mail_from_address": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    "mail_from_name": "PyFlarum",
}

ADVANCED_SETTINGS_DEFAULTS = {
    "cache_driver": "redis" if "redis" in settings.CACHES.get("default", {}).get("BACKEND", "").lower() else "file",
    "cache_lifetime": 3600,
    "queue_driver": "redis" if "redis" in getattr(settings, "CELERY_BROKER_URL", "") else "sync",
    "queue_enabled": False,
    "maintenance_mode": False,
    "maintenance_message": "论坛正在维护中，请稍后再试...",
    "debug_mode": settings.DEBUG,
    "log_queries": False,
}


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


def get_setting_group(prefix: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    values = defaults.copy()
    stored_settings = Setting.objects.filter(
        key__in=[f"{prefix}.{key}" for key in defaults.keys()]
    )

    for setting in stored_settings:
        key = setting.key.split(".", 1)[1]
        try:
            values[key] = json.loads(setting.value)
        except json.JSONDecodeError:
            values[key] = setting.value

    return values


def save_setting_group(prefix: str, defaults: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    values = get_setting_group(prefix, defaults)

    for key in defaults.keys():
        if key not in payload:
            continue

        values[key] = payload[key]
        Setting.objects.update_or_create(
            key=f"{prefix}.{key}",
            defaults={"value": json.dumps(payload[key], ensure_ascii=False)}
        )

    return values


# ==================== 统计数据 ====================

@router.get("/stats", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_stats(request):
    """获取系统统计数据"""
    return {
        "phpVersion": f"Python {sys.version.split()[0]}",
        "dbDriver": "SQLite/PostgreSQL/MySQL",
        "queueDriver": "sync",
        "sessionDriver": "database",
        "totalUsers": User.objects.count(),
        "totalDiscussions": Discussion.objects.count(),
        "totalPosts": Post.objects.count(),
        "openFlags": PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).count(),
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

    mail_settings = get_setting_group("mail", MAIL_SETTINGS_DEFAULTS)
    from_email = mail_settings.get("mail_from_address") or settings.DEFAULT_FROM_EMAIL

    try:
        sent_count = send_mail(
            subject="PyFlarum 测试邮件",
            message="如果你收到这封邮件，说明 PyFlarum 的邮件发送链路可用。",
            from_email=from_email,
            recipient_list=[request.auth.email],
            fail_silently=False,
        )
    except Exception as e:
        return admin_error(str(e), status=400)

    return {"message": "测试邮件已发送", "sent_count": sent_count}


@router.get("/advanced", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_advanced_settings(request):
    """获取高级设置"""
    return get_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS)


@router.post("/advanced", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_advanced_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存高级设置"""
    settings_data = save_setting_group("advanced", ADVANCED_SETTINGS_DEFAULTS, payload)
    return {"message": "高级设置保存成功", "settings": settings_data}


@router.post("/cache/clear", auth=AuthBearer(), tags=["Admin"])
@require_staff
def clear_cache(request):
    """清除 Django 缓存"""
    try:
        cache.clear()
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
    from apps.tags.services import TagService
    TagService.refresh_tag_stats()

    tags = Tag.objects.all().order_by('position', 'name')

    return [
        {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "description": tag.description,
            "color": tag.color or "#888",
            "icon": tag.icon,
            "position": tag.position,
            "discussion_count": tag.discussion_count,
            "is_hidden": tag.is_hidden,
            "is_restricted": tag.is_restricted,
        }
        for tag in tags
    ]


@router.post("/tags", auth=AuthBearer(), tags=["Admin"])
@require_staff
def create_admin_tag(request, payload: Dict[str, Any] = Body(...)):
    """创建标签"""
    try:
        tag = Tag.objects.create(
            name=payload.get('name'),
            description=payload.get('description', ''),
            color=payload.get('color', '#888'),
            icon=payload.get('icon', ''),
            position=payload.get('position', 0),
            is_hidden=payload.get('is_hidden', False),
            is_restricted=payload.get('is_restricted', False),
        )

        return {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "description": tag.description,
            "color": tag.color,
            "icon": tag.icon,
            "position": tag.position,
            "discussion_count": tag.discussion_count,
            "is_hidden": tag.is_hidden,
            "is_restricted": tag.is_restricted,
        }
    except Exception as e:
        return admin_error(str(e), status=400)


@router.put("/tags/{tag_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def update_admin_tag(request, tag_id: int, payload: Dict[str, Any] = Body(...)):
    """更新标签"""
    try:
        tag = get_object_or_404(Tag, id=tag_id)

        if 'name' in payload:
            tag.name = payload['name']
        if 'description' in payload:
            tag.description = payload['description']
        if 'color' in payload:
            tag.color = payload['color']
        if 'icon' in payload:
            tag.icon = payload['icon']
        if 'position' in payload:
            tag.position = payload['position']
        if 'is_hidden' in payload:
            tag.is_hidden = payload['is_hidden']
        if 'is_restricted' in payload:
            tag.is_restricted = payload['is_restricted']

        tag.save()

        return {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "description": tag.description,
            "color": tag.color,
            "icon": tag.icon,
            "position": tag.position,
            "discussion_count": tag.discussion_count,
            "is_hidden": tag.is_hidden,
            "is_restricted": tag.is_restricted,
        }
    except Exception as e:
        return admin_error(str(e), status=400)


@router.delete("/tags/{tag_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def delete_admin_tag(request, tag_id: int):
    """删除标签"""
    tag = get_object_or_404(Tag, id=tag_id)
    tag.delete()

    return {"message": "标签删除成功"}
