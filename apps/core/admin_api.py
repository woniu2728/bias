"""管理后台 API 聚合与共享 helper。"""
import functools
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import django
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ninja import Body, Router

from apps.core import admin_module_helpers, admin_runtime_helpers
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
from apps.core.admin_content_api import router as content_router
from apps.core.admin_moderation_api import router as moderation_router
from apps.core.admin_settings_api import router as settings_router
from apps.core.admin_users_api import router as users_router

router = Router()
router.add_router("", content_router)
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
    return admin_module_helpers.resolve_module_category_label(category)


def build_module_dependency_state(module, module_map: Dict[str, Any]) -> Dict[str, Any]:
    return admin_module_helpers.build_module_dependency_state(module, module_map)


def build_module_health_state(module, dependency_state: Dict[str, Any]) -> Dict[str, Any]:
    return admin_module_helpers.build_module_health_state(module, dependency_state)


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
    return admin_module_helpers.build_module_settings_overview(
        module,
        setting_model=Setting,
        basic_settings_defaults=BASIC_SETTINGS_DEFAULTS,
        appearance_settings_defaults=APPEARANCE_SETTINGS_DEFAULTS,
        advanced_settings_defaults=ADVANCED_SETTINGS_DEFAULTS,
        mail_settings_defaults=get_mail_settings_defaults(),
    )


def resolve_module_documentation_url(module) -> str:
    return admin_module_helpers.resolve_module_documentation_url(module)


def build_module_runtime_state(module) -> Dict[str, Any]:
    return admin_module_helpers.build_module_runtime_state(module)


def serialize_module_definition(module, module_map: Dict[str, Any]) -> Dict[str, Any]:
    return admin_module_helpers.serialize_module_definition(
        module,
        module_map,
        resource_registry=RESOURCE_REGISTRY,
        runtime_dependency_summary_builder=build_runtime_dependency_summary,
        setting_model=Setting,
        basic_settings_defaults=BASIC_SETTINGS_DEFAULTS,
        appearance_settings_defaults=APPEARANCE_SETTINGS_DEFAULTS,
        advanced_settings_defaults=ADVANCED_SETTINGS_DEFAULTS,
        mail_settings_defaults=get_mail_settings_defaults(),
    )


def build_module_category_summaries(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return admin_module_helpers.build_module_category_summaries(modules)


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
    return admin_runtime_helpers.probe_cache_connection(settings_obj=settings, cache_backend=cache)


def _probe_redis_ping(host: str | None, port: int | None, *, label: str) -> dict[str, Any]:
    return runtime_probe_redis_ping(host, port, label=label)


def _probe_realtime_connection() -> dict[str, Any]:
    return admin_runtime_helpers.probe_realtime_connection(
        settings_obj=settings,
        redis_probe=_probe_redis_ping,
    )


def _probe_queue_broker_connection(queue_enabled: bool, queue_driver: str) -> dict[str, Any]:
    return admin_runtime_helpers.probe_queue_broker_connection(
        settings_obj=settings,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        redis_probe=_probe_redis_ping,
    )


def _normalize_secret_value(value: Any) -> str:
    return admin_runtime_helpers.normalize_secret_value(value)


def _looks_like_placeholder_secret(value: str) -> bool:
    return admin_runtime_helpers.looks_like_placeholder_secret(value)


def _jwt_key_length_requirement(algorithm: str) -> int:
    return admin_runtime_helpers.jwt_key_length_requirement(algorithm)


def build_auth_secret_risks() -> list[dict[str, Any]]:
    secret_key = _normalize_secret_value(settings.SECRET_KEY)
    jwt_algorithm = str(settings.NINJA_JWT.get("ALGORITHM") or "").strip().upper()
    jwt_signing_key = _normalize_secret_value(settings.NINJA_JWT.get("SIGNING_KEY") or settings.SECRET_KEY)
    return admin_runtime_helpers.build_auth_secret_risks(
        secret_key=secret_key,
        jwt_algorithm=jwt_algorithm,
        jwt_signing_key=jwt_signing_key,
    )


def build_auth_secret_status() -> dict[str, Any]:
    return admin_runtime_helpers.build_auth_secret_status(risks=build_auth_secret_risks())


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
    return admin_runtime_helpers.build_runtime_risks(
        debug_mode=debug_mode,
        database_label=database_label,
        cache_driver=cache_driver,
        realtime_driver=realtime_driver,
        queue_enabled=queue_enabled,
        queue_driver=queue_driver,
        queue_worker_status=queue_worker_status,
        redis_enabled=redis_enabled,
        cache_connection=cache_connection,
        realtime_connection=realtime_connection,
        queue_broker_connection=queue_broker_connection,
        auth_secret_risks=build_auth_secret_risks(),
    )


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
    return admin_runtime_helpers.validate_advanced_runtime_settings(
        payload,
        database_label=detect_database_label(),
        realtime_driver=detect_realtime_driver(),
    )
