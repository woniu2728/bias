"""
管理后台API端点
"""
import json
import sys
import functools
from pathlib import Path

import django
from ninja import Router, Body
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from typing import List, Dict, Any
from django.db import transaction
from django.db.models import Count, Max, Q
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.core.email_service import EmailService
from apps.core.audit import log_admin_action
from apps.core.mail_drivers import (
    can_mail_driver_send,
    get_driver_definitions,
    parse_mail_from,
    serialize_mail_settings,
    validate_mail_settings,
)
from apps.core.queue_service import QueueService
from apps.core.forum_registry import get_forum_registry
from apps.core.resource_registry import get_resource_registry
from apps.core.search_index_service import SearchIndexService
from apps.core.file_service import FileUploadService
from apps.core.settings_service import (
    ADVANCED_SETTINGS_DEFAULTS,
    APPEARANCE_SETTINGS_DEFAULTS,
    BASIC_SETTINGS_DEFAULTS,
    clear_runtime_setting_caches,
    get_advanced_settings as get_runtime_advanced_settings,
    get_mail_settings as get_runtime_mail_settings,
    get_mail_settings_defaults,
    get_setting_group,
    save_setting_group,
    sync_mail_settings_to_site_config,
)
from apps.core.models import AuditLog
from apps.users.models import User, Group, Permission
from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.tags.services import TagService
from apps.notifications.services import NotificationService
from apps.users.group_utils import get_primary_group, serialize_group_badge

router = Router()

REGISTRY = get_forum_registry()
RESOURCE_REGISTRY = get_resource_registry()

BUILTIN_GROUPS = {
    1: "Admin",
    2: "Guest",
    3: "Member",
    4: "Moderator",
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


def serialize_audit_log(log: AuditLog) -> Dict[str, Any]:
    return {
        "id": log.id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "data": log.data,
        "created_at": log.created_at,
        "user": {
            "id": log.user.id,
            "username": log.user.username,
            "display_name": log.user.display_name,
        } if log.user else None,
    }


def serialize_group(group: Group) -> Dict[str, Any]:
    payload = serialize_group_badge(group) or {}
    payload["is_system"] = is_builtin_group(group)
    return payload


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
        "view_scope": tag.view_scope,
        "start_discussion_scope": tag.start_discussion_scope,
        "reply_scope": tag.reply_scope,
        "view_scope_label": TagService.get_scope_label(tag.view_scope),
        "start_discussion_scope_label": TagService.get_scope_label(tag.start_discussion_scope),
        "reply_scope_label": TagService.get_scope_label(tag.reply_scope),
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
        "name_singular": name,
        "name_plural": name,
        "color": payload.get("color") or "#4d698e",
        "icon": (payload.get("icon") or "").strip(),
        "is_hidden": bool(payload.get("is_hidden", False)),
    }


def is_builtin_group(group: Group) -> bool:
    return BUILTIN_GROUPS.get(group.id) == group.name


def normalize_permission_code(permission: str):
    return REGISTRY.normalize_permission_code(permission)


def serialize_admin_user(user: User, include_details: bool = False) -> Dict[str, Any]:
    primary_group = get_primary_group(user)
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
        "primary_group": serialize_group(primary_group) if primary_group else None,
    }

    if include_details:
        payload.update({
            "bio": user.bio,
            "suspended_until": user.suspended_until,
            "suspend_reason": user.suspend_reason,
            "suspend_message": user.suspend_message,
        })

    return payload


def serialize_module_definition(module) -> Dict[str, Any]:
    resource_fields = [
        {
            "resource": definition.resource,
            "field": definition.field,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_all_fields()
        if definition.module_id == module.module_id
    ]
    return {
        "id": module.module_id,
        "name": module.name,
        "description": module.description,
        "version": module.version,
        "category": module.category,
        "is_core": module.is_core,
        "enabled": module.enabled,
        "dependencies": list(module.dependencies),
        "capabilities": list(module.capabilities),
        "notification_types": [
            {
                "code": notification_type.code,
                "label": notification_type.label,
                "description": notification_type.description,
            }
            for notification_type in module.notification_types
        ],
        "event_listeners": [
            {
                "event": listener.event,
                "listener": listener.listener,
                "description": listener.description,
            }
            for listener in module.event_listeners
        ],
        "post_types": [
            {
                "code": post_type.code,
                "label": post_type.label,
                "description": post_type.description,
                "icon": post_type.icon,
                "is_default": post_type.is_default,
                "is_stream_visible": post_type.is_stream_visible,
                "counts_toward_discussion": post_type.counts_toward_discussion,
                "counts_toward_user": post_type.counts_toward_user,
                "searchable": post_type.searchable,
            }
            for post_type in module.post_types
        ],
        "search_filters": [
            {
                "code": search_filter.code,
                "label": search_filter.label,
                "target": search_filter.target,
                "syntax": search_filter.syntax,
                "description": search_filter.description,
            }
            for search_filter in module.search_filters
        ],
        "resource_fields": resource_fields,
        "permissions": [
            {
                "code": permission.code,
                "label": permission.label,
                "section": permission.section,
                "section_label": permission.section_label,
                "icon": permission.icon,
                "description": permission.description,
                "required_permissions": list(permission.required_permissions),
                "aliases": list(permission.aliases),
            }
            for permission in module.permissions
        ],
        "admin_pages": [
            {
                "path": page.path,
                "label": page.label,
                "icon": page.icon,
                "nav_section": page.nav_section,
                "description": page.description,
            }
            for page in module.admin_pages
        ],
    }


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


def detect_database_label() -> str:
    config = settings.DATABASES.get("default", {})
    engine = (config.get("ENGINE") or "").lower()
    if "sqlite" in engine:
        filename = Path(str(config.get("NAME") or "db.sqlite3")).name
        return f"SQLite ({filename})"
    if "postgresql" in engine:
        return f"PostgreSQL ({config.get('NAME') or '-'} @ {config.get('HOST') or 'localhost'})"
    if "mysql" in engine:
        return f"MySQL ({config.get('NAME') or '-'})"
    return engine or "未知"


def detect_cache_driver() -> str:
    backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    if "django_redis" in backend or "redis" in backend:
        return "Redis"
    if "locmem" in backend:
        return "内存"
    if "filebased" in backend:
        return "文件"
    if "database" in backend:
        return "数据库"
    return backend or "未知"


def detect_realtime_driver() -> str:
    backend = (settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND") or "").lower()
    if "channels_redis" in backend or "redis" in backend:
        return "Redis"
    if "inmemory" in backend:
        return "In-memory"
    return backend or "未知"


def build_mail_settings_response(admin_email: str = "") -> Dict[str, Any]:
    settings_data = get_runtime_mail_settings()
    errors = validate_mail_settings(settings_data)
    driver_definitions = get_driver_definitions()
    effective_test_to_email = (
        str(settings_data.get("mail_test_recipient") or "").strip()
        or str(admin_email or "").strip()
    )
    settings_data.update({
        "drivers": driver_definitions,
        "driver_options": [
            {"value": key, "label": value.get("label") or key}
            for key, value in driver_definitions.items()
        ],
        "sending": can_mail_driver_send(settings_data, errors),
        "errors": errors,
        "mail_test_recipient": str(settings_data.get("mail_test_recipient") or "").strip(),
        "test_to_email": effective_test_to_email,
    })
    return settings_data


def detect_queue_driver_label(queue_enabled: bool, queue_driver: str) -> str:
    if not queue_enabled:
        return "同步执行"
    if queue_driver == "redis":
        return "Redis"
    return queue_driver or "未知"


def is_redis_enabled(queue_enabled: bool = False, queue_driver: str = "") -> bool:
    cache_backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    channel_backend = (settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND") or "").lower()
    broker = getattr(settings, "CELERY_BROKER_URL", "").lower()

    cache_uses_redis = "redis" in cache_backend
    realtime_uses_redis = "redis" in channel_backend
    queue_uses_redis = bool(queue_enabled and queue_driver == "redis" and "redis" in broker)

    return cache_uses_redis or realtime_uses_redis or queue_uses_redis


# ==================== 统计数据 ====================

@router.get("/stats", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_stats(request):
    """获取系统统计数据"""
    advanced_settings = get_runtime_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    queue_metrics = QueueService.get_metrics()

    return {
        "runtimeName": "Python",
        "pythonVersion": sys.version.split()[0],
        "djangoVersion": django.get_version(),
        "databaseLabel": detect_database_label(),
        "cacheDriver": detect_cache_driver(),
        "queueDriver": queue_driver,
        "queueEnabled": queue_enabled,
        "queueLabel": detect_queue_driver_label(queue_enabled, queue_driver),
        "queueWorkerStatus": queue_worker_status["status"],
        "queueWorkerLabel": queue_worker_status["label"],
        "queueWorkerAvailable": queue_worker_status["available"],
        "queueWorkerCount": queue_worker_status["worker_count"],
        "queueWorkerMessage": queue_worker_status["message"],
        "queueMetrics": queue_metrics,
        "realtimeDriver": detect_realtime_driver(),
        "redisEnabled": is_redis_enabled(queue_enabled=queue_enabled, queue_driver=queue_driver),
        "debugMode": settings.DEBUG,
        "maintenanceMode": bool(advanced_settings.get("maintenance_mode", False)),
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


@router.post("/queue/metrics/reset", auth=AuthBearer(), tags=["Admin"])
@require_staff
def reset_queue_metrics(request):
    """重置队列运行指标"""
    metrics = QueueService.reset_metrics()
    log_admin_action(request, "admin.queue_metrics.reset", data={"metrics": metrics})
    return {
        "message": "队列运行指标已重置",
        "metrics": metrics,
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
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "basic", "keys": sorted(payload.keys())},
    )
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
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "appearance", "keys": sorted(payload.keys())},
    )
    return {"message": "外观设置保存成功", "settings": settings_data}


@router.post("/appearance/upload", auth=AuthBearer(), tags=["Admin"])
@require_staff
def upload_appearance_asset(request, target: str):
    """上传站点 Logo 或 Favicon"""
    if target not in {"logo", "favicon"}:
        return admin_error("仅支持上传 logo 或 favicon", status=400)

    file = request.FILES.get("file")
    if not file:
        return admin_error("请选择要上传的文件", status=400)

    try:
        file_url, file_info = FileUploadService.upload_site_asset(file, target)
    except ValueError as e:
        return admin_error(str(e), status=400)

    log_admin_action(
        request,
        "admin.appearance_asset.upload",
        target_type="appearance_asset",
        data={
            "target": target,
            "original_name": file_info.get("original_name") or file.name,
            "size": file_info.get("size") or file.size,
            "mime_type": file_info.get("mime_type") or file.content_type,
        },
    )
    return {
        "target": target,
        "url": file_url,
        "original_name": file_info.get("original_name") or file.name,
        "size": file_info.get("size") or file.size,
        "mime_type": file_info.get("mime_type") or file.content_type,
    }


@router.get("/mail", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_mail_settings(request):
    """获取邮件设置"""
    return build_mail_settings_response(request.auth.email if request.auth else "")


@router.post("/mail", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_mail_settings(request, payload: Dict[str, Any] = Body(...)):
    """保存邮件设置"""
    normalized_payload = dict(payload)
    if "mail_from" in normalized_payload:
        mail_from_address, mail_from_name = parse_mail_from(normalized_payload.pop("mail_from"))
        normalized_payload["mail_from_address"] = mail_from_address
        normalized_payload["mail_from_name"] = mail_from_name

    defaults = get_mail_settings_defaults()
    settings_data = save_setting_group("mail", defaults, normalized_payload)
    expected_settings = serialize_mail_settings(settings_data)
    try:
        config_path = sync_mail_settings_to_site_config(settings_data)
    except Exception as exc:
        return admin_error(f"邮件设置写入站点配置失败: {exc}", status=500)

    response = build_mail_settings_response(request.auth.email if request.auth else "")
    if response.get("mail_from") != expected_settings.get("mail_from"):
        location = config_path or "数据库设置"
        return admin_error(
            "邮件设置保存后校验失败，运行时读取到的发件地址与刚保存的不一致。"
            f" 期望值: {expected_settings.get('mail_from') or '(空)'};"
            f" 实际值: {response.get('mail_from') or '(空)'};"
            f" 配置来源: {location}",
            status=500,
        )
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "mail", "keys": sorted(normalized_payload.keys())},
    )
    response["message"] = "邮件设置保存成功"
    response["settings"] = serialize_mail_settings(settings_data)
    return response


@router.post("/mail/test", auth=AuthBearer(), tags=["Admin"])
@require_staff
def send_test_email(request):
    """发送测试邮件"""
    payload = {}
    if request.body:
        raw_body = request.body.decode("utf-8", errors="ignore").strip()
        content_type = str(request.headers.get("content-type") or "")
        should_parse_json = "application/json" in content_type or raw_body[:1] in {"{", "["}
        if should_parse_json:
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                return admin_error("测试邮件请求格式无效", status=400)
            if not isinstance(payload, dict):
                payload = {}

    mail_settings = get_setting_group("mail", get_mail_settings_defaults())
    to_email = (
        str(payload.get("to_email") or "").strip()
        or str(mail_settings.get("mail_test_recipient") or "").strip()
        or str(request.auth.email or "").strip()
    )
    if not to_email:
        return admin_error("请先填写测试收件箱", status=400)

    try:
        validate_email(to_email)
    except ValidationError:
        return admin_error("测试收件箱格式无效", status=400)

    try:
        sent_count = EmailService.send_test_email(to_email)
    except Exception as e:
        return admin_error(str(e), status=400)

    log_admin_action(
        request,
        "admin.mail.test",
        target_type="mail",
        data={"to_email": to_email, "sent_count": sent_count},
    )
    return {"message": "测试邮件已发送", "sent_count": sent_count, "to_email": to_email}


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
    log_admin_action(
        request,
        "admin.settings.update",
        target_type="settings",
        data={"group": "advanced", "keys": sorted(runtime_payload.keys())},
    )
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

    log_admin_action(request, "admin.cache.clear", target_type="cache")
    return {"message": "缓存已清除"}


@router.post("/search-indexes/rebuild", auth=AuthBearer(), tags=["Admin"])
@require_staff
def rebuild_search_indexes(request):
    """后台手动重建 PostgreSQL 全文搜索索引"""
    try:
        result = SearchIndexService.rebuild_postgres_indexes()
    except RuntimeError as e:
        return admin_error(str(e), status=400)
    except Exception as e:
        return admin_error(f"搜索索引重建失败: {e}", status=503)

    log_admin_action(
        request,
        "admin.search_indexes.rebuild",
        target_type="search_index",
        data={
            "indexes": result.get("indexes", []),
            "duration_ms": result.get("duration_ms", 0),
        },
    )
    return result


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
        log_admin_action(
            request,
            "admin.group.create",
            target_type="group",
            target_id=group.id,
            data={"name": group.name, "is_hidden": group.is_hidden},
        )
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

    log_admin_action(
        request,
        "admin.group.update",
        target_type="group",
        target_id=group.id,
        data={"name": group.name, "changed_fields": sorted(validated.keys())},
    )
    return serialize_group(group)


@router.delete("/groups/{group_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def delete_group(request, group_id: int):
    """删除用户组"""
    group = get_object_or_404(Group, id=group_id)

    if is_builtin_group(group):
        return admin_error("系统默认用户组不允许删除", status=400)

    group_snapshot = {"name": group.name, "permission_count": group.permissions.count()}
    group.delete()
    log_admin_action(
        request,
        "admin.group.delete",
        target_type="group",
        target_id=group_id,
        data=group_snapshot,
    )
    return {"message": "用户组删除成功"}


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

@router.get("/modules", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_admin_modules(request):
    """获取内置模块注册信息"""
    modules = [serialize_module_definition(module) for module in REGISTRY.get_modules()]
    pages = [
        {
            "path": page.path,
            "label": page.label,
            "icon": page.icon,
            "module_id": page.module_id,
            "nav_section": page.nav_section,
            "description": page.description,
        }
        for page in REGISTRY.get_admin_pages()
    ]
    notification_types = [
        {
            "code": notification_type.code,
            "label": notification_type.label,
            "module_id": notification_type.module_id,
            "description": notification_type.description,
        }
        for notification_type in REGISTRY.get_notification_types()
    ]
    event_listeners = [
        {
            "event": listener.event,
            "listener": listener.listener,
            "module_id": listener.module_id,
            "description": listener.description,
        }
        for listener in REGISTRY.get_event_listeners()
    ]
    post_types = [
        {
            "code": post_type.code,
            "label": post_type.label,
            "module_id": post_type.module_id,
            "description": post_type.description,
            "icon": post_type.icon,
            "is_default": post_type.is_default,
            "is_stream_visible": post_type.is_stream_visible,
            "counts_toward_discussion": post_type.counts_toward_discussion,
            "counts_toward_user": post_type.counts_toward_user,
            "searchable": post_type.searchable,
        }
        for post_type in REGISTRY.get_post_types()
    ]
    search_filters = [
        {
            "code": search_filter.code,
            "label": search_filter.label,
            "module_id": search_filter.module_id,
            "target": search_filter.target,
            "syntax": search_filter.syntax,
            "description": search_filter.description,
        }
        for search_filter in REGISTRY.get_search_filters()
    ]
    resource_fields = [
        {
            "resource": definition.resource,
            "field": definition.field,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_all_fields()
    ]
    return {
        "modules": modules,
        "admin_pages": pages,
        "notification_types": notification_types,
        "event_listeners": event_listeners,
        "post_types": post_types,
        "search_filters": search_filters,
        "resource_fields": resource_fields,
        "permission_aliases": REGISTRY.get_permission_aliases(),
    }


@router.get("/permissions/meta", auth=AuthBearer(), tags=["Admin"])
@require_staff
def get_permissions_meta(request):
    """获取注册化权限元数据"""
    return {
        "sections": REGISTRY.get_permission_sections(),
        "aliases": REGISTRY.get_permission_aliases(),
    }


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
        normalized = normalize_permission_code(perm.permission)
        if normalized and normalized not in result[group_id]:
            result[group_id].append(normalized)

    return result


@router.post("/permissions", auth=AuthBearer(), tags=["Admin"])
@require_staff
def save_permissions(request, payload: Dict[int, List[str]] = Body(...)):
    """保存权限配置"""
    normalized_payload = {}

    for raw_group_id, permission_names in payload.items():
        try:
            group_id = int(raw_group_id)
        except (TypeError, ValueError):
            return admin_error("用户组参数无效", status=400)

        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return admin_error(f"用户组不存在: {group_id}", status=400)

        normalized_permissions = []
        for permission_name in permission_names or []:
            normalized_permission = normalize_permission_code(permission_name)
            if not normalized_permission:
                return admin_error(f"未知权限: {permission_name}", status=400)
            if normalized_permission not in normalized_permissions:
                normalized_permissions.append(normalized_permission)

        normalized_payload[group.id] = {
            "group": group,
            "permissions": normalized_permissions,
        }

    with transaction.atomic():
        Permission.objects.all().delete()

        for entry in normalized_payload.values():
            for permission in entry["permissions"]:
                Permission.objects.create(
                    group=entry["group"],
                    permission=permission,
                )

    log_admin_action(
        request,
        "admin.permissions.update",
        target_type="permissions",
        data={
            "group_ids": sorted(normalized_payload.keys()),
            "permission_count": sum(len(entry["permissions"]) for entry in normalized_payload.values()),
        },
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
    was_suspended = user.is_suspended
    previous_group_ids = set(user.user_groups.values_list("id", flat=True))

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
    is_suspended = user.is_suspended

    touched_suspension_fields = bool(
        {"suspended_until", "suspend_reason", "suspend_message"} & set(payload.keys())
    )
    if touched_suspension_fields:
        if is_suspended:
            NotificationService.notify_user_suspended(user, request.auth)
        elif was_suspended:
            NotificationService.notify_user_unsuspended(user, request.auth)

    if groups is not None:
        user.user_groups.set(groups)

    user.refresh_from_db()
    next_group_ids = set(user.user_groups.values_list("id", flat=True))
    log_admin_action(
        request,
        "admin.user.update",
        target_type="user",
        target_id=user.id,
        data={
            "username": user.username,
            "changed_fields": sorted(payload.keys()),
            "suspension_changed": touched_suspension_fields and was_suspended != user.is_suspended,
            "groups_changed": groups is not None and previous_group_ids != next_group_ids,
        },
    )
    return serialize_admin_user(user, include_details=True)


@router.delete("/users/{user_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def delete_admin_user(request, user_id: int):
    """删除用户"""
    user = get_object_or_404(User, id=user_id)

    if user.id == request.auth.id:
        return admin_error("不能删除当前登录的管理员账号", status=400)

    if user.is_staff and User.objects.filter(is_staff=True).exclude(id=user.id).count() == 0:
        return admin_error("至少需要保留一个管理员账号", status=400)

    user_snapshot = {
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
    }
    user.delete()
    log_admin_action(
        request,
        "admin.user.delete",
        target_type="user",
        target_id=user_id,
        data=user_snapshot,
    )
    return {"message": "用户删除成功"}


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
        log_admin_action(
            request,
            "admin.approval.approve",
            target_type="discussion",
            target_id=approved.id,
            data={"note": note, "title": approved.title},
        )
        return serialize_approval_item("discussion", approved)

    if content_type == "post":
        post = get_object_or_404(Post.objects.select_related("discussion", "user"), id=content_id, approval_status=Post.APPROVAL_PENDING)
        approved = PostService.approve_post(post, request.auth, note=note)
        log_admin_action(
            request,
            "admin.approval.approve",
            target_type="post",
            target_id=approved.id,
            data={"note": note, "discussion_id": approved.discussion_id},
        )
        return serialize_approval_item("post", approved)

    return admin_error("无效的审核内容类型", status=400)


@router.post("/approval-queue/{content_type}/{content_id}/reject", auth=AuthBearer(), tags=["Admin"])
@require_staff
def reject_content(request, content_type: str, content_id: int, payload: Dict[str, Any] = Body(...)):
    note = payload.get("note", "")

    if content_type == "discussion":
        discussion = get_object_or_404(Discussion, id=content_id, approval_status=Discussion.APPROVAL_PENDING)
        rejected = DiscussionService.reject_discussion(discussion, request.auth, note=note)
        log_admin_action(
            request,
            "admin.approval.reject",
            target_type="discussion",
            target_id=rejected.id,
            data={"note": note, "title": rejected.title},
        )
        return serialize_approval_item("discussion", rejected)

    if content_type == "post":
        post = get_object_or_404(Post.objects.select_related("discussion", "user"), id=content_id, approval_status=Post.APPROVAL_PENDING)
        rejected = PostService.reject_post(post, request.auth, note=note)
        log_admin_action(
            request,
            "admin.approval.reject",
            target_type="post",
            target_id=rejected.id,
            data={"note": note, "discussion_id": rejected.discussion_id},
        )
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
        log_admin_action(
            request,
            "admin.flag.resolve",
            target_type="post_flag",
            target_id=flag.id,
            data={
                "status": flag.status,
                "post_id": flag.post_id,
                "resolution_note": flag.resolution_note,
            },
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
    except ValueError as e:
        return admin_error(str(e), status=400)
    except Exception as e:
        return admin_error(str(e), status=400)


@router.post("/tags/{tag_id}/move", auth=AuthBearer(), tags=["Admin"])
@require_staff
def move_admin_tag(request, tag_id: int, payload: Dict[str, Any] = Body(...)):
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
            "data": [serialize_admin_tag(tag) for tag in tags],
        }
    except ValueError as e:
        return admin_error(str(e), status=400)
    except Tag.DoesNotExist:
        return admin_error("标签不存在", status=404)


@router.delete("/tags/{tag_id}", auth=AuthBearer(), tags=["Admin"])
@require_staff
def delete_admin_tag(request, tag_id: int):
    """删除标签"""
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
    except ValueError as e:
        return admin_error(str(e), status=400)


@router.post("/tags/stats/refresh", auth=AuthBearer(), tags=["Admin"])
@require_staff
def refresh_admin_tag_stats(request):
    """手动刷新标签统计"""
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


# ==================== 审计日志 ====================

@router.get("/audit-logs", auth=AuthBearer(), tags=["Admin"])
@require_staff
def list_audit_logs(
    request,
    page: int = 1,
    limit: int = 20,
    action: str = "",
    target_type: str = "",
    user_id: int = None,
):
    """获取管理员操作审计日志"""
    page = max(1, int(page or 1))
    limit = min(max(1, int(limit or 20)), 100)
    queryset = (
        AuditLog.objects.select_related("user")
        .filter(action__startswith="admin.")
        .order_by("-created_at", "-id")
    )

    if action:
        queryset = queryset.filter(action=action)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    total = queryset.count()
    offset = (page - 1) * limit
    logs = queryset[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [serialize_audit_log(log) for log in logs],
    }
