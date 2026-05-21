"""
管理后台API端点
"""
import json
import sys
import functools
from pathlib import Path
from urllib.parse import urlparse

import django
from ninja import Router, Body
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from typing import List, Dict, Any
from django.db import transaction
from django.db.models import Count, Max, Q
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
from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.forum_events import UserSuspendedEvent, UserUnsuspendedEvent
from apps.core.jwt_auth import AccessTokenAuth
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
from apps.core.models import AuditLog, Setting
from apps.core.runtime_checks import (
    _probe_redis_ping as runtime_probe_redis_ping,
    build_runtime_dependency_checks as runtime_build_runtime_dependency_checks,
    detect_cache_driver as runtime_detect_cache_driver,
    detect_database_label as runtime_detect_database_label,
    detect_queue_driver_label as runtime_detect_queue_driver_label,
    detect_realtime_driver as runtime_detect_realtime_driver,
    is_redis_enabled as runtime_is_redis_enabled,
)
from apps.users.models import User, Group, Permission
from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.tags.services import TagService
from apps.users.group_utils import get_primary_group, serialize_group_badge
from apps.users.services import UserService
from apps.core.services import PaginationService
from apps.core.api_errors import api_error
from apps.core.admin_moderation_api import router as moderation_router
from apps.core.admin_settings_api import router as settings_router
from apps.core.admin_users_api import router as users_router

router = Router()
router.add_router("", moderation_router)
router.add_router("", settings_router)
router.add_router("", users_router)

REGISTRY = get_forum_registry()
RESOURCE_REGISTRY = get_resource_registry()

BUILTIN_GROUPS = {
    1: "Admin",
    2: "Guest",
    3: "Member",
    4: "Moderator",
}


def admin_error(
    message: str,
    status: int = 400,
    *,
    code: str | None = None,
    field_errors: dict[str, Any] | None = None,
):
    return api_error(
        message,
        status=status,
        code=code,
        field_errors=field_errors,
    )


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


def resolve_module_category_label(category: str) -> str:
    if category == "core":
        return "核心"
    if category == "infrastructure":
        return "基础设施"
    return "功能模块"


def build_module_dependency_state(module, module_map: Dict[str, Any]) -> Dict[str, Any]:
    missing_dependencies = []
    disabled_dependencies = []

    for dependency in module.dependencies:
        dependency_module = module_map.get(dependency)
        if dependency_module is None:
            missing_dependencies.append(dependency)
        elif not dependency_module.enabled:
            disabled_dependencies.append(dependency)

    if missing_dependencies:
        status = "missing"
        label = "缺少依赖"
    elif disabled_dependencies:
        status = "disabled"
        label = "依赖未启用"
    else:
        status = "healthy"
        label = "依赖正常"

    return {
        "status": status,
        "label": label,
        "missing": missing_dependencies,
        "disabled": disabled_dependencies,
    }


def build_module_health_state(module, dependency_state: Dict[str, Any]) -> Dict[str, Any]:
    issues = []

    if dependency_state["status"] != "healthy":
        issues.append(dependency_state["label"])

    if module.enabled and not module.capabilities:
        issues.append("未声明能力项")

    status = "healthy"
    label = "健康"
    if issues:
        status = "attention"
        label = "需关注"

    return {
        "status": status,
        "label": label,
        "issues": issues,
    }


def build_runtime_dependency_summary() -> dict[str, Any]:
    advanced_settings = get_runtime_advanced_settings()
    queue_driver = advanced_settings.get("queue_driver", "sync")
    queue_enabled = bool(advanced_settings.get("queue_enabled", False))
    queue_worker_status = QueueService.get_worker_status()
    cache_connection = _probe_cache_connection()
    realtime_connection = _probe_realtime_connection()
    queue_broker_connection = _probe_queue_broker_connection(queue_enabled, queue_driver)
    checks = build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )
    issues = [
        f"{item['label']}：{item['status_label']}"
        for item in checks
        if item.get("available") is False
    ]
    return {
        "status": "attention" if issues else "healthy",
        "label": "需关注" if issues else "健康",
        "issues": issues,
        "checks": checks,
    }


def build_module_settings_overview(module) -> Dict[str, Any]:
    setting_keys = []
    for group_name in module.settings_groups:
        if group_name == "basic":
            setting_keys.extend([f"basic.{key}" for key in BASIC_SETTINGS_DEFAULTS.keys()])
        elif group_name == "appearance":
            setting_keys.extend([f"appearance.{key}" for key in APPEARANCE_SETTINGS_DEFAULTS.keys()])
        elif group_name == "advanced":
            setting_keys.extend([f"advanced.{key}" for key in ADVANCED_SETTINGS_DEFAULTS.keys()])
        elif group_name == "mail":
            setting_keys.extend([f"mail.{key}" for key in get_mail_settings_defaults().keys()])

    configured_count = 0
    if setting_keys:
        configured_count = Setting.objects.filter(key__in=setting_keys).count()

    return {
        "groups": list(module.settings_groups),
        "group_count": len(module.settings_groups),
        "configured_key_count": configured_count,
        "has_settings": bool(module.settings_groups),
    }


def resolve_module_documentation_url(module) -> str:
    if module.documentation_url:
        return module.documentation_url
    return f"/admin.html#/admin/docs?guide=module-development&module={module.module_id}"


def build_module_runtime_state(module) -> Dict[str, Any]:
    migration_state = "built-in"
    migration_label = "内置模块"
    if module.module_id == "core":
        migration_label = "核心底座"

    settings_entry_path = None
    if len(module.settings_groups) == 1:
        group_name = next(iter(module.settings_groups), "")
        settings_entry_path = {
            "basic": "/admin/basics",
            "appearance": "/admin/appearance",
            "mail": "/admin/mail",
            "advanced": "/admin/advanced",
        }.get(group_name)

    return {
        "migration_state": migration_state,
        "migration_label": migration_label,
        "boot_mode": "static",
        "boot_mode_label": "启动时静态注册",
        "settings_entry_path": settings_entry_path,
        "permissions_entry_path": "/admin/permissions" if module.permissions else "",
        "module_center_path": f"/admin/modules?module={module.module_id}",
        "debug_items": [
            {"key": "module_id", "label": "模块 ID", "value": module.module_id},
            {"key": "category", "label": "模块分类", "value": resolve_module_category_label(module.category)},
            {"key": "boot_mode", "label": "启动方式", "value": "启动时静态注册"},
            {"key": "migration", "label": "迁移状态", "value": migration_label},
        ],
    }


def serialize_module_definition(module, module_map: Dict[str, Any]) -> Dict[str, Any]:
    dependency_state = build_module_dependency_state(module, module_map)
    health_state = build_module_health_state(module, dependency_state)
    settings_overview = build_module_settings_overview(module)
    runtime_state = build_module_runtime_state(module)
    resource_fields = [
        {
            "resource": definition.resource,
            "field": definition.field,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_all_fields()
        if definition.module_id == module.module_id
    ]
    resource_definitions = [
        {
            "resource": definition.resource,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_resources()
        if definition.module_id == module.module_id
    ]
    resource_relationships = [
        {
            "resource": definition.resource,
            "relationship": definition.relationship,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_all_relationships()
        if definition.module_id == module.module_id
    ]
    runtime_dependency_summary = None
    if module.module_id == "core":
        runtime_dependency_summary = build_runtime_dependency_summary()
        if runtime_dependency_summary["status"] != "healthy":
            health_state = {
                "status": "attention",
                "label": "需关注",
                "issues": [
                    *health_state["issues"],
                    *runtime_dependency_summary["issues"],
                ],
            }
    return {
        "id": module.module_id,
        "name": module.name,
        "description": module.description,
        "version": module.version,
        "category": module.category,
        "category_label": resolve_module_category_label(module.category),
        "is_core": module.is_core,
        "enabled": module.enabled,
        "dependencies": list(module.dependencies),
        "dependency_status": dependency_state["status"],
        "dependency_status_label": dependency_state["label"],
        "missing_dependencies": dependency_state["missing"],
        "disabled_dependencies": dependency_state["disabled"],
        "health_status": health_state["status"],
        "health_status_label": health_state["label"],
        "health_issues": health_state["issues"],
        "capabilities": list(module.capabilities),
        "settings": settings_overview,
        "documentation_url": resolve_module_documentation_url(module),
        "runtime": runtime_state,
        "notification_types": [
            {
                "code": notification_type.code,
                "label": notification_type.label,
                "description": notification_type.description,
                "icon": notification_type.icon,
                "navigation_scope": notification_type.navigation_scope,
                "preference_key": notification_type.preference_key,
                "preference_label": notification_type.preference_label,
                "preference_description": notification_type.preference_description,
                "preference_default_enabled": notification_type.preference_default_enabled,
            }
            for notification_type in module.notification_types
        ],
        "user_preferences": [
            {
                "key": preference.key,
                "label": preference.label,
                "description": preference.description,
                "category": preference.category,
                "default_value": preference.default_value,
            }
            for preference in module.user_preferences
        ],
        "language_packs": [
            {
                "code": language_pack.code,
                "label": language_pack.label,
                "native_label": language_pack.native_label,
                "description": language_pack.description,
                "is_default": language_pack.is_default,
            }
            for language_pack in module.language_packs
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
        "discussion_sorts": [
            {
                "code": discussion_sort.code,
                "label": discussion_sort.label,
                "description": discussion_sort.description,
                "icon": discussion_sort.icon,
                "is_default": discussion_sort.is_default,
                "toolbar_visible": discussion_sort.toolbar_visible,
            }
            for discussion_sort in module.discussion_sorts
        ],
        "discussion_list_filters": [
            {
                "code": discussion_list_filter.code,
                "label": discussion_list_filter.label,
                "description": discussion_list_filter.description,
                "icon": discussion_list_filter.icon,
                "is_default": discussion_list_filter.is_default,
                "requires_authenticated_user": discussion_list_filter.requires_authenticated_user,
                "sidebar_visible": discussion_list_filter.sidebar_visible,
                "route_path": discussion_list_filter.route_path,
            }
            for discussion_list_filter in module.discussion_list_filters
        ],
        "resource_definitions": resource_definitions,
        "resource_relationships": resource_relationships,
        "resource_fields": resource_fields,
        "runtime_dependency_summary": runtime_dependency_summary,
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
                "settings_group": page.settings_group,
            }
            for page in module.admin_pages
        ],
        "registration_counts": {
            "permissions": len(module.permissions),
            "admin_pages": len(module.admin_pages),
            "notification_types": len(module.notification_types),
            "user_preferences": len(module.user_preferences),
            "language_packs": len(module.language_packs),
            "event_listeners": len(module.event_listeners),
            "post_types": len(module.post_types),
            "search_filters": len(module.search_filters),
            "discussion_sorts": len(module.discussion_sorts),
            "discussion_list_filters": len(module.discussion_list_filters),
            "resource_definitions": len(resource_definitions),
            "resource_relationships": len(resource_relationships),
            "resource_fields": len(resource_fields),
            "settings_groups": len(module.settings_groups),
        },
    }


def build_module_category_summaries(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for module in modules:
        category_id = module["category"]
        group = grouped.setdefault(
            category_id,
            {
                "id": category_id,
                "label": module["category_label"],
                "module_count": 0,
                "enabled_count": 0,
                "attention_count": 0,
            },
        )
        group["module_count"] += 1
        if module["enabled"]:
            group["enabled_count"] += 1
        if module["health_status"] != "healthy":
            group["attention_count"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (
            0 if item["id"] == "core" else 1,
            item["label"],
        ),
    )


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


def require_admin_permission(permission_code: str, message: str):
    """装饰器：要求管理员具备指定后台权限码"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.auth or not request.auth.is_staff:
                return admin_error("需要管理员权限", status=403)
            if not UserService.has_forum_permission(request.auth, permission_code):
                return admin_error(message, status=403, code="permission_denied")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def detect_database_label() -> str:
    return runtime_detect_database_label()


def detect_cache_driver() -> str:
    return runtime_detect_cache_driver()


def detect_realtime_driver() -> str:
    return runtime_detect_realtime_driver()


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
    return runtime_detect_queue_driver_label(queue_enabled, queue_driver)


def is_redis_enabled(queue_enabled: bool = False, queue_driver: str = "") -> bool:
    return runtime_is_redis_enabled(queue_enabled, queue_driver)


def _probe_cache_connection() -> dict[str, Any]:
    backend = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
    if "django_redis" not in backend and "redis" not in backend:
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前默认缓存未使用 Redis。",
        }

    try:
        cache.set("admin.runtime.cache_probe", "ok", timeout=5)
        cache.get("admin.runtime.cache_probe")
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "unavailable",
            "label": "连接失败",
            "message": str(exc) or "无法访问缓存后端。",
        }

    return {
        "enabled": True,
        "available": True,
        "status": "available",
        "label": "可用",
        "message": "缓存后端可正常读写。",
    }


def _probe_redis_ping(host: str | None, port: int | None, *, label: str) -> dict[str, Any]:
    return runtime_probe_redis_ping(host, port, label=label)


def _probe_realtime_connection() -> dict[str, Any]:
    channel_config = settings.CHANNEL_LAYERS.get("default", {})
    backend = (channel_config.get("BACKEND") or "").lower()
    if "channels_redis" not in backend and "redis" not in backend:
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前实时层未使用 Redis Channel Layer。",
        }

    hosts = channel_config.get("CONFIG", {}).get("hosts") or []
    if not hosts:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "Redis Channel Layer 缺少 hosts 配置。",
        }

    first_host = hosts[0]
    if isinstance(first_host, (list, tuple)):
        host = first_host[0] if len(first_host) > 0 else None
        port = first_host[1] if len(first_host) > 1 else 6379
    elif isinstance(first_host, str):
        parsed = urlparse(first_host if "://" in first_host else f"redis://{first_host}")
        host = parsed.hostname
        port = parsed.port or 6379
    else:
        host = None
        port = None

    connectivity = _probe_redis_ping(host, port, label="Redis Channel Layer")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


def _probe_queue_broker_connection(queue_enabled: bool, queue_driver: str) -> dict[str, Any]:
    normalized_driver = str(queue_driver or "").strip().lower()
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
    if not queue_enabled or normalized_driver != "redis":
        return {
            "enabled": False,
            "available": None,
            "status": "disabled",
            "label": "未启用",
            "message": "当前未启用 Redis 队列 broker。",
        }

    if not broker_url:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "队列已启用，但 CELERY_BROKER_URL 为空。",
        }

    parsed = urlparse(broker_url)
    if "redis" not in (parsed.scheme or "").lower():
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "驱动不匹配",
            "message": "队列驱动为 Redis，但 broker URL 不是 Redis 协议。",
        }

    if not parsed.hostname:
        return {
            "enabled": True,
            "available": False,
            "status": "misconfigured",
            "label": "配置缺失",
            "message": "Redis broker 缺少主机配置。",
        }

    connectivity = _probe_redis_ping(parsed.hostname, parsed.port or 6379, label="Redis broker")
    return {
        "enabled": True,
        "available": connectivity["available"],
        "status": connectivity["status"],
        "label": connectivity["label"],
        "message": connectivity["message"],
    }


MIN_HS256_KEY_LENGTH = 32
KNOWN_PLACEHOLDER_SECRETS = {
    "django-insecure-change-this-in-production",
    "jwt-secret-key-change-this",
}


def _normalize_secret_value(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_placeholder_secret(value: str) -> bool:
    return value.lower() in KNOWN_PLACEHOLDER_SECRETS


def _jwt_key_length_requirement(algorithm: str) -> int:
    normalized = str(algorithm or "").strip().upper()
    if normalized.startswith("HS"):
        return MIN_HS256_KEY_LENGTH
    return 0


def build_auth_secret_risks() -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    secret_key = _normalize_secret_value(settings.SECRET_KEY)
    jwt_algorithm = str(settings.NINJA_JWT.get("ALGORITHM") or "").strip().upper()
    jwt_signing_key = _normalize_secret_value(settings.NINJA_JWT.get("SIGNING_KEY") or settings.SECRET_KEY)
    jwt_required_length = _jwt_key_length_requirement(jwt_algorithm)

    if _looks_like_placeholder_secret(secret_key):
        risks.append(
            {
                "code": "django-secret-placeholder",
                "level": "danger",
                "title": "Django SECRET_KEY 仍为默认占位值",
                "message": "当前 SECRET_KEY 仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if _looks_like_placeholder_secret(jwt_signing_key):
        risks.append(
            {
                "code": "jwt-secret-placeholder",
                "level": "danger",
                "title": "JWT 签名密钥仍为默认占位值",
                "message": "当前 JWT 签名密钥仍带有开发占位标记，生产环境必须替换为独立高强度密钥。",
            }
        )

    if jwt_required_length and len(jwt_signing_key) < jwt_required_length:
        risks.append(
            {
                "code": "jwt-secret-too-short",
                "level": "danger",
                "title": "JWT 签名密钥长度不足",
                "message": f"当前 {jwt_algorithm or 'JWT'} 签名密钥长度小于 {jwt_required_length} 字节，存在被弱密钥攻击的风险。",
            }
        )

    return risks


def build_auth_secret_status() -> dict[str, Any]:
    risks = build_auth_secret_risks()
    if risks:
        highest_level = "danger" if any(item.get("level") == "danger" for item in risks) else "warning"
        return {
            "status": highest_level,
            "label": "存在风险",
            "message": "；".join(item.get("title") or "" for item in risks if item.get("title")),
        }

    return {
        "status": "healthy",
        "label": "健康",
        "message": "Django 与 JWT 密钥未发现默认占位值或长度不足问题。",
    }


def build_runtime_risks(
    *,
    debug_mode: bool,
    database_label: str,
    cache_driver: str,
    realtime_driver: str,
    queue_enabled: bool,
    queue_driver: str,
    queue_worker_status: dict[str, Any],
    redis_enabled: bool,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    normalized_database_label = str(database_label or "").lower()
    normalized_cache_driver = str(cache_driver or "").lower()
    normalized_realtime_driver = str(realtime_driver or "").lower()
    normalized_queue_driver = str(queue_driver or "").lower()

    if debug_mode:
        risks.append(
            {
                "code": "debug-enabled",
                "level": "warning",
                "title": "DEBUG 模式仍处于开启状态",
                "message": "生产环境应关闭 DEBUG，避免泄露调试信息并影响缓存与异常处理行为。",
            }
        )

    is_production_like = "postgresql" in normalized_database_label
    if is_production_like and not redis_enabled:
        risks.append(
            {
                "code": "redis-disabled-production",
                "level": "danger",
                "title": "生产形态下未启用 Redis",
                "message": "当前使用 PostgreSQL，但缓存、实时层与队列未形成 Redis 底座，不符合路线图中的生产约束要求。",
            }
        )

    if is_production_like and "内存" in cache_driver:
        risks.append(
            {
                "code": "locmem-cache-production",
                "level": "danger",
                "title": "生产形态下仍在使用内存缓存",
                "message": "LocMemCache 只适合开发环境，多进程部署下会导致缓存割裂与状态不一致。",
            }
        )

    if queue_enabled and normalized_queue_driver == "redis" and not queue_worker_status.get("available"):
        risks.append(
            {
                "code": "queue-worker-unavailable",
                "level": "danger",
                "title": "队列已启用但没有可用 worker",
                "message": queue_worker_status.get("message") or "当前队列会持续回退到同步执行，后台异步任务无法稳定处理。",
            }
        )

    if cache_connection.get("enabled") and cache_connection.get("available") is False:
        risks.append(
            {
                "code": "cache-backend-unavailable",
                "level": "danger",
                "title": "缓存后端不可用",
                "message": cache_connection.get("message") or "当前缓存后端无法正常访问。",
            }
        )

    if realtime_connection.get("enabled") and realtime_connection.get("available") is False:
        risks.append(
            {
                "code": "realtime-backend-unavailable",
                "level": "warning",
                "title": "实时层配置不完整",
                "message": realtime_connection.get("message") or "当前实时层无法确认 Redis Channel Layer 可用。",
            }
        )

    if queue_broker_connection.get("enabled") and queue_broker_connection.get("available") is False:
        risks.append(
            {
                "code": "queue-broker-unavailable",
                "level": "danger",
                "title": "队列 broker 不可用",
                "message": queue_broker_connection.get("message") or "当前队列 broker 无法使用。",
            }
        )

    if queue_enabled and normalized_queue_driver != "redis":
        risks.append(
            {
                "code": "queue-driver-nonredis",
                "level": "warning",
                "title": "队列已启用但未使用 Redis 驱动",
                "message": "当前 worker 健康检测与稳定异步链路主要围绕 Redis/Celery 设计，其他驱动暂未形成完整生产闭环。",
            }
        )

    if is_production_like and normalized_realtime_driver == "in-memory":
        risks.append(
            {
                "code": "realtime-inmemory-production",
                "level": "warning",
                "title": "实时层仍使用内存通道",
                "message": "In-memory Channel Layer 不适合多实例部署，WebSocket 消息无法跨进程共享。",
            }
        )

    if is_production_like and normalized_cache_driver not in {"redis", "memcached"}:
        risks.append(
            {
                "code": "cache-driver-nonshared",
                "level": "warning",
                "title": "缓存驱动不是共享缓存",
                "message": "当前缓存驱动缺少跨实例共享能力，生产环境下容易出现配置和统计状态不一致。",
            }
        )

    risks.extend(build_auth_secret_risks())
    return risks


def build_runtime_dependency_checks(
    *,
    cache_connection: dict[str, Any],
    realtime_connection: dict[str, Any],
    queue_broker_connection: dict[str, Any],
    queue_worker_status: dict[str, Any],
) -> list[dict[str, Any]]:
    return runtime_build_runtime_dependency_checks(
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        queue_worker_status=queue_worker_status,
    )


def validate_advanced_runtime_settings(payload: Dict[str, Any]) -> list[str]:
    cache_driver = str(payload.get("cache_driver") or "").strip().lower()
    queue_driver = str(payload.get("queue_driver") or "").strip().lower()
    queue_enabled = bool(payload.get("queue_enabled", False))
    errors: list[str] = []

    is_postgres = "postgresql" in detect_database_label().lower()
    realtime_driver = detect_realtime_driver().lower()

    if is_postgres and cache_driver == "file":
        errors.append("PostgreSQL 生产形态下不允许将缓存驱动保存为文件缓存，请改用 Redis 或 Memcached。")

    if is_postgres and cache_driver == "内存":
        errors.append("PostgreSQL 生产形态下不允许继续使用内存缓存。")

    if queue_enabled and queue_driver != "redis":
        errors.append("启用队列处理时，当前仅允许使用 Redis 队列驱动。")

    if is_postgres and realtime_driver == "in-memory" and queue_enabled:
        errors.append("当前实时层仍是 In-memory，生产形态下启用队列前应先切换到 Redis Channel Layer。")

    return errors


# ==================== 权限管理 ====================

@router.get("/modules", auth=AccessTokenAuth(), tags=["Admin"])
@require_staff
def list_admin_modules(request):
    """获取内置模块注册信息"""
    registry_modules = REGISTRY.get_modules()
    module_map = {module.module_id: module for module in registry_modules}
    modules = [serialize_module_definition(module, module_map) for module in registry_modules]
    pages = [
        {
            "path": page.path,
            "label": page.label,
            "icon": page.icon,
            "module_id": page.module_id,
            "nav_section": page.nav_section,
            "description": page.description,
            "settings_group": page.settings_group,
        }
        for page in REGISTRY.get_admin_pages()
    ]
    notification_types = [
        {
            "code": notification_type.code,
            "label": notification_type.label,
            "module_id": notification_type.module_id,
            "description": notification_type.description,
            "icon": notification_type.icon,
            "navigation_scope": notification_type.navigation_scope,
            "preference_key": notification_type.preference_key,
            "preference_label": notification_type.preference_label,
            "preference_description": notification_type.preference_description,
            "preference_default_enabled": notification_type.preference_default_enabled,
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
    discussion_sorts = [
        {
            "code": discussion_sort.code,
            "label": discussion_sort.label,
            "module_id": discussion_sort.module_id,
            "description": discussion_sort.description,
            "icon": discussion_sort.icon,
            "is_default": discussion_sort.is_default,
            "toolbar_visible": discussion_sort.toolbar_visible,
        }
        for discussion_sort in REGISTRY.get_discussion_sorts()
    ]
    discussion_list_filters = [
        {
            "code": discussion_list_filter.code,
            "label": discussion_list_filter.label,
            "module_id": discussion_list_filter.module_id,
            "description": discussion_list_filter.description,
            "icon": discussion_list_filter.icon,
            "is_default": discussion_list_filter.is_default,
            "requires_authenticated_user": discussion_list_filter.requires_authenticated_user,
            "sidebar_visible": discussion_list_filter.sidebar_visible,
            "route_path": discussion_list_filter.route_path,
        }
        for discussion_list_filter in REGISTRY.get_discussion_list_filters()
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
    resource_definitions = [
        {
            "resource": definition.resource,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_resources()
    ]
    resource_relationships = [
        {
            "resource": definition.resource,
            "relationship": definition.relationship,
            "module_id": definition.module_id,
            "description": definition.description,
        }
        for definition in RESOURCE_REGISTRY.get_all_relationships()
    ]
    user_preferences = [
        {
            "key": preference.key,
            "label": preference.label,
            "module_id": preference.module_id,
            "description": preference.description,
            "category": preference.category,
            "default_value": preference.default_value,
        }
        for preference in REGISTRY.get_user_preferences()
    ]
    language_packs = [
        {
            "code": language_pack.code,
            "label": language_pack.label,
            "native_label": language_pack.native_label,
            "module_id": language_pack.module_id,
            "description": language_pack.description,
            "is_default": language_pack.is_default,
        }
        for language_pack in REGISTRY.get_language_packs()
    ]
    category_summaries = build_module_category_summaries(modules)
    dependency_attention = [
        {
            "module_id": module["id"],
            "module_name": module["name"],
            "status": module["dependency_status"],
            "label": module["dependency_status_label"],
            "missing": module["missing_dependencies"],
            "disabled": module["disabled_dependencies"],
        }
        for module in modules
        if module["dependency_status"] != "healthy"
    ]
    runtime_dependency_attention_count = sum(
        1
        for module in modules
        if module.get("runtime_dependency_summary") is not None
        and module["runtime_dependency_summary"]["status"] != "healthy"
    )
    summary = {
        "module_count": len(modules),
        "core_count": sum(1 for module in modules if module["is_core"]),
        "enabled_count": sum(1 for module in modules if module["enabled"]),
        "permission_count": sum(len(module["permissions"]) for module in modules),
        "admin_page_count": len(pages),
        "notification_type_count": len(notification_types),
        "user_preference_count": len(user_preferences),
        "language_pack_count": len(language_packs),
        "event_listener_count": len(event_listeners),
        "post_type_count": len(post_types),
        "resource_definition_count": len(resource_definitions),
        "resource_relationship_count": len(resource_relationships),
        "resource_field_count": len(resource_fields),
        "search_filter_count": len(search_filters),
        "discussion_sort_count": len(discussion_sorts),
        "discussion_list_filter_count": len(discussion_list_filters),
        "settings_group_count": sum(len(module["settings"]["groups"]) for module in modules),
        "dependency_issue_count": len(dependency_attention),
        "health_attention_count": sum(1 for module in modules if module["health_status"] != "healthy"),
        "runtime_dependency_attention_count": runtime_dependency_attention_count,
    }
    return {
        "summary": summary,
        "modules": modules,
        "category_summaries": category_summaries,
        "dependency_attention": dependency_attention,
        "admin_pages": pages,
        "notification_types": notification_types,
        "user_preferences": user_preferences,
        "language_packs": language_packs,
        "event_listeners": event_listeners,
        "post_types": post_types,
        "search_filters": search_filters,
        "discussion_sorts": discussion_sorts,
        "discussion_list_filters": discussion_list_filters,
        "resource_definitions": resource_definitions,
        "resource_relationships": resource_relationships,
        "resource_fields": resource_fields,
        "permission_aliases": REGISTRY.get_permission_aliases(),
    }


# ==================== 标签管理 ====================

@router.get("/tags", auth=AccessTokenAuth(), tags=["Admin"])
@require_staff
def list_admin_tags(request):
    """获取标签列表（管理后台）"""
    tags = Tag.objects.select_related("parent").all().order_by("position", "name")
    return [serialize_admin_tag(tag) for tag in tags]


@router.post("/tags", auth=AccessTokenAuth(), tags=["Admin"])
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


@router.put("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
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


@router.post("/tags/{tag_id}/move", auth=AccessTokenAuth(), tags=["Admin"])
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


@router.delete("/tags/{tag_id}", auth=AccessTokenAuth(), tags=["Admin"])
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


@router.post("/tags/stats/refresh", auth=AccessTokenAuth(), tags=["Admin"])
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

@router.get("/audit-logs", auth=AccessTokenAuth(), tags=["Admin"])
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
    page, limit = PaginationService.normalize(page, limit)
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
