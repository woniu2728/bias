import json

from ninja import Body, Router
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.domain_events import dispatch_forum_event_after_commit
from extensions.users.backend.events import UserSuspendedEvent, UserUnsuspendedEvent
from apps.core.forum_registry import get_forum_registry
from extensions.users.backend.admin_user_helpers import (
    is_builtin_group,
    normalize_permission_code,
    parse_optional_datetime,
    serialize_admin_user,
    serialize_group,
    validate_group_payload,
)
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.services import PaginationService
from apps.core.settings_service import get_mail_settings_defaults, get_setting_group
from extensions.users.backend.models import Group, Permission, User
from extensions.users.backend.mail import send_test_email
from extensions.users.backend.services import UserService


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None


@router.get("/groups", auth=AccessTokenAuth(), tags=["Admin"])
def list_groups(request):
    denied = _require_staff(request)
    if denied:
        return denied

    groups = Group.objects.all().order_by("id", "name")
    return [serialize_group(group) for group in groups]


@router.post("/groups", auth=AccessTokenAuth(), tags=["Admin"])
def create_group(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

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
    except ValueError as exc:
        return api_error(str(exc), status=400)


@router.put("/groups/{group_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_group(request, group_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    group = get_object_or_404(Group, id=group_id)

    try:
        validated = validate_group_payload(payload, group=group)
    except ValueError as exc:
        return api_error(str(exc), status=400)

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


@router.delete("/groups/{group_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_group(request, group_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    group = get_object_or_404(Group, id=group_id)

    if is_builtin_group(group):
        return api_error("系统默认用户组不允许删除", status=400)

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


@router.get("/permissions/meta", auth=AccessTokenAuth(), tags=["Admin"])
def get_permissions_meta(request):
    denied = _require_staff(request)
    if denied:
        return denied

    registry = get_forum_registry()
    return {
        "sections": registry.get_permission_sections(),
        "modules": [
            {
                "id": module.module_id,
                "name": module.name,
                "category": module.category,
                "enabled": module.enabled,
            }
            for module in registry.get_modules()
        ],
    }


@router.get("/permissions", auth=AccessTokenAuth(), tags=["Admin"])
def get_permissions(request):
    denied = _require_staff(request)
    if denied:
        return denied

    permissions = Permission.objects.select_related("group").all()
    result = {}
    for perm in permissions:
        group_id = perm.group.id
        if group_id not in result:
            result[group_id] = []
        normalized = normalize_permission_code(perm.permission)
        if normalized and normalized not in result[group_id]:
            result[group_id].append(normalized)

    admin_group = Group.objects.filter(id=1, name="Admin").first()
    if admin_group is not None:
        admin_runtime_permissions = sorted(
            set(UserService.STAFF_BASE_FORUM_PERMISSIONS)
            | UserService.get_staff_group_managed_forum_permissions()
        )
        if admin_group.id not in result:
            result[admin_group.id] = []
        for permission_name in admin_runtime_permissions:
            if permission_name not in result[admin_group.id]:
                result[admin_group.id].append(permission_name)

    return result


@router.post("/permissions", auth=AccessTokenAuth(), tags=["Admin"])
def save_permissions(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    normalized_payload = {}
    registry = get_forum_registry()

    for raw_group_id, permission_names in payload.items():
        try:
            group_id = int(raw_group_id)
        except (TypeError, ValueError):
            return api_error("用户组参数无效", status=400)

        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return api_error(f"用户组不存在: {group_id}", status=400)

        normalized_permissions = []
        for permission_name in permission_names or []:
            normalized_permission = normalize_permission_code(permission_name)
            if not normalized_permission:
                return api_error(f"未知权限: {permission_name}", status=400)
            if normalized_permission not in normalized_permissions:
                normalized_permissions.append(normalized_permission)

        if is_builtin_group(group) and group.id == 1:
            normalized_permissions = sorted(
                set(normalized_permissions)
                | set(UserService.STAFF_BASE_FORUM_PERMISSIONS)
                | UserService.get_staff_group_managed_forum_permissions()
            )

        normalized_permissions = registry.expand_permissions(normalized_permissions)
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


@router.post("/mail/test", auth=AccessTokenAuth(), tags=["Admin"])
def send_admin_test_email(request):
    denied = _require_staff(request)
    if denied:
        return denied

    payload = {}
    if request.body:
        raw_body = request.body.decode("utf-8", errors="ignore").strip()
        content_type = str(request.headers.get("content-type") or "")
        should_parse_json = "application/json" in content_type or raw_body[:1] in {"{", "["}
        if should_parse_json:
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                return api_error("测试邮件请求格式无效", status=400)
            if not isinstance(payload, dict):
                payload = {}

    mail_settings = get_setting_group("mail", get_mail_settings_defaults())
    to_email = (
        str(payload.get("to_email") or "").strip()
        or str(mail_settings.get("mail_test_recipient") or "").strip()
        or str(request.auth.email or "").strip()
    )
    if not to_email:
        return api_error("请先填写测试收件箱", status=400)

    try:
        validate_email(to_email)
    except ValidationError:
        return api_error("测试收件箱格式无效", status=400)

    try:
        sent_count = send_test_email(to_email)
    except Exception as exc:
        return api_error(str(exc), status=400)

    log_admin_action(
        request,
        "admin.mail.test",
        target_type="mail",
        data={"to_email": to_email, "sent_count": sent_count},
    )
    return {"message": "测试邮件已发送", "sent_count": sent_count, "to_email": to_email}


@router.get("/users", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_users(request, page: int = 1, limit: int = 20, q: str = None):
    denied = _require_staff(request)
    if denied:
        return denied

    page, limit = PaginationService.normalize(page, limit)
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
        "data": [serialize_admin_user(user) for user in users],
    }


@router.get("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_user(request, user_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    user = get_object_or_404(User.objects.prefetch_related("user_groups"), id=user_id)
    return serialize_admin_user(user, include_details=True)


@router.put("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_admin_user(request, user_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    user = get_object_or_404(User.objects.prefetch_related("user_groups"), id=user_id)
    was_suspended = user.is_suspended
    previous_group_ids = set(user.user_groups.values_list("id", flat=True))

    if user.id == request.auth.id and "is_staff" in payload and not payload.get("is_staff"):
        return api_error("不能取消自己的管理员权限", status=400)

    username = payload.get("username")
    if username and username != user.username:
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            return api_error("用户名已存在", status=400)
        user.username = username

    email = payload.get("email")
    if email is not None and email != user.email:
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            return api_error("邮箱已被使用", status=400)
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
    except ValueError as exc:
        return api_error(str(exc), status=400)

    if "suspend_reason" in payload:
        user.suspend_reason = payload.get("suspend_reason") or ""
    if "suspend_message" in payload:
        user.suspend_message = payload.get("suspend_message") or ""

    group_ids = payload.get("group_ids")
    if group_ids is not None:
        try:
            normalized_group_ids = [int(group_id) for group_id in group_ids]
        except (TypeError, ValueError):
            return api_error("用户组参数无效", status=400)

        groups = list(Group.objects.filter(id__in=normalized_group_ids))
        if len(groups) != len(set(normalized_group_ids)):
            return api_error("包含无效的用户组", status=400)
    else:
        groups = None

    user.save()
    is_suspended = user.is_suspended

    touched_suspension_fields = bool(
        {"suspended_until", "suspend_reason", "suspend_message"} & set(payload.keys())
    )
    if touched_suspension_fields:
        if is_suspended:
            dispatch_forum_event_after_commit(
                UserSuspendedEvent(
                    user_id=user.id,
                    actor_user_id=getattr(request.auth, "id", None),
                )
            )
        elif was_suspended:
            dispatch_forum_event_after_commit(
                UserUnsuspendedEvent(
                    user_id=user.id,
                    actor_user_id=getattr(request.auth, "id", None),
                )
            )

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


@router.delete("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_admin_user(request, user_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    user = get_object_or_404(User, id=user_id)

    if user.id == request.auth.id:
        return api_error("不能删除当前登录的管理员账号", status=400)

    if user.is_staff and User.objects.filter(is_staff=True).exclude(id=user.id).count() == 0:
        return api_error("至少需要保留一个管理员账号", status=400)

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
