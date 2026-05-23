from ninja import Body, Router
from django.shortcuts import get_object_or_404

from apps.core.jwt_auth import AccessTokenAuth


router = Router()


def _legacy():
    from apps.core import admin_api as legacy

    return legacy


def _require_staff(request):
    legacy = _legacy()
    if not request.auth or not request.auth.is_staff:
        return legacy.admin_error("需要管理员权限", status=403)
    return None


@router.get("/groups", auth=AccessTokenAuth(), tags=["Admin"])
def list_groups(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    groups = legacy.Group.objects.all().order_by("id", "name")
    return [legacy.serialize_group(group) for group in groups]


@router.post("/groups", auth=AccessTokenAuth(), tags=["Admin"])
def create_group(request, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    try:
        validated = legacy.validate_group_payload(payload)
        group = legacy.Group.objects.create(**validated)
        legacy.log_admin_action(
            request,
            "admin.group.create",
            target_type="group",
            target_id=group.id,
            data={"name": group.name, "is_hidden": group.is_hidden},
        )
        return legacy.serialize_group(group)
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)


@router.put("/groups/{group_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_group(request, group_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    group = get_object_or_404(legacy.Group, id=group_id)

    try:
        validated = legacy.validate_group_payload(payload, group=group)
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)

    for field, value in validated.items():
        setattr(group, field, value)
    group.save()

    legacy.log_admin_action(
        request,
        "admin.group.update",
        target_type="group",
        target_id=group.id,
        data={"name": group.name, "changed_fields": sorted(validated.keys())},
    )
    return legacy.serialize_group(group)


@router.delete("/groups/{group_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_group(request, group_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    group = get_object_or_404(legacy.Group, id=group_id)

    if legacy.is_builtin_group(group):
        return legacy.admin_error("系统默认用户组不允许删除", status=400)

    group_snapshot = {"name": group.name, "permission_count": group.permissions.count()}
    group.delete()
    legacy.log_admin_action(
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

    legacy = _legacy()
    return {
        "sections": legacy.REGISTRY.get_permission_sections(),
        "aliases": legacy.REGISTRY.get_permission_aliases(),
        "modules": [
            {
                "id": module.module_id,
                "name": module.name,
                "category": module.category,
                "enabled": module.enabled,
            }
            for module in legacy.REGISTRY.get_modules()
        ],
    }


@router.get("/permissions", auth=AccessTokenAuth(), tags=["Admin"])
def get_permissions(request):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    permissions = legacy.Permission.objects.select_related("group").all()
    result = {}
    for perm in permissions:
        group_id = perm.group.id
        if group_id not in result:
            result[group_id] = []
        normalized = legacy.normalize_permission_code(perm.permission)
        if normalized and normalized not in result[group_id]:
            result[group_id].append(normalized)

    admin_group = legacy.Group.objects.filter(id=1, name="Admin").first()
    if admin_group is not None:
        admin_runtime_permissions = sorted(
            set(legacy.UserService.STAFF_BASE_FORUM_PERMISSIONS)
            | legacy.UserService.get_staff_group_managed_forum_permissions()
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

    legacy = _legacy()
    normalized_payload = {}

    for raw_group_id, permission_names in payload.items():
        try:
            group_id = int(raw_group_id)
        except (TypeError, ValueError):
            return legacy.admin_error("用户组参数无效", status=400)

        try:
            group = legacy.Group.objects.get(id=group_id)
        except legacy.Group.DoesNotExist:
            return legacy.admin_error(f"用户组不存在: {group_id}", status=400)

        normalized_permissions = []
        for permission_name in permission_names or []:
            normalized_permission = legacy.normalize_permission_code(permission_name)
            if not normalized_permission:
                return legacy.admin_error(f"未知权限: {permission_name}", status=400)
            if normalized_permission not in normalized_permissions:
                normalized_permissions.append(normalized_permission)

        if legacy.is_builtin_group(group) and group.id == 1:
            normalized_permissions = sorted(
                set(normalized_permissions)
                | set(legacy.UserService.STAFF_BASE_FORUM_PERMISSIONS)
                | legacy.UserService.get_staff_group_managed_forum_permissions()
            )

        normalized_permissions = legacy.REGISTRY.expand_permissions(normalized_permissions)
        normalized_payload[group.id] = {
            "group": group,
            "permissions": normalized_permissions,
        }

    with legacy.transaction.atomic():
        legacy.Permission.objects.all().delete()

        for entry in normalized_payload.values():
            for permission in entry["permissions"]:
                legacy.Permission.objects.create(
                    group=entry["group"],
                    permission=permission,
                )

    legacy.log_admin_action(
        request,
        "admin.permissions.update",
        target_type="permissions",
        data={
            "group_ids": sorted(normalized_payload.keys()),
            "permission_count": sum(len(entry["permissions"]) for entry in normalized_payload.values()),
        },
    )
    return {"message": "权限保存成功"}


@router.get("/users", auth=AccessTokenAuth(), tags=["Admin"])
def list_admin_users(request, page: int = 1, limit: int = 20, q: str = None):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    page, limit = legacy.PaginationService.normalize(page, limit)
    queryset = legacy.User.objects.prefetch_related("user_groups").all().order_by("-joined_at")

    if q:
        queryset = queryset.filter(
            legacy.Q(username__icontains=q)
            | legacy.Q(email__icontains=q)
            | legacy.Q(display_name__icontains=q)
        )

    total = queryset.count()
    offset = (page - 1) * limit
    users = queryset[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [legacy.serialize_admin_user(user) for user in users],
    }


@router.get("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_user(request, user_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    user = get_object_or_404(legacy.User.objects.prefetch_related("user_groups"), id=user_id)
    return legacy.serialize_admin_user(user, include_details=True)


@router.put("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def update_admin_user(request, user_id: int, payload: dict = Body(...)):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    user = get_object_or_404(legacy.User.objects.prefetch_related("user_groups"), id=user_id)
    was_suspended = user.is_suspended
    previous_group_ids = set(user.user_groups.values_list("id", flat=True))

    if user.id == request.auth.id and "is_staff" in payload and not payload.get("is_staff"):
        return legacy.admin_error("不能取消自己的管理员权限", status=400)

    username = payload.get("username")
    if username and username != user.username:
        if legacy.User.objects.filter(username=username).exclude(id=user.id).exists():
            return legacy.admin_error("用户名已存在", status=400)
        user.username = username

    email = payload.get("email")
    if email is not None and email != user.email:
        if legacy.User.objects.filter(email=email).exclude(id=user.id).exists():
            return legacy.admin_error("邮箱已被使用", status=400)
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
            user.suspended_until = legacy.parse_optional_datetime(payload.get("suspended_until"))
    except ValueError as exc:
        return legacy.admin_error(str(exc), status=400)

    if "suspend_reason" in payload:
        user.suspend_reason = payload.get("suspend_reason") or ""
    if "suspend_message" in payload:
        user.suspend_message = payload.get("suspend_message") or ""

    group_ids = payload.get("group_ids")
    if group_ids is not None:
        try:
            normalized_group_ids = [int(group_id) for group_id in group_ids]
        except (TypeError, ValueError):
            return legacy.admin_error("用户组参数无效", status=400)

        groups = list(legacy.Group.objects.filter(id__in=normalized_group_ids))
        if len(groups) != len(set(normalized_group_ids)):
            return legacy.admin_error("包含无效的用户组", status=400)
    else:
        groups = None

    user.save()
    is_suspended = user.is_suspended

    touched_suspension_fields = bool(
        {"suspended_until", "suspend_reason", "suspend_message"} & set(payload.keys())
    )
    if touched_suspension_fields:
        if is_suspended:
            legacy.dispatch_forum_event_after_commit(
                legacy.UserSuspendedEvent(
                    user_id=user.id,
                    actor_user_id=getattr(request.auth, "id", None),
                )
            )
        elif was_suspended:
            legacy.dispatch_forum_event_after_commit(
                legacy.UserUnsuspendedEvent(
                    user_id=user.id,
                    actor_user_id=getattr(request.auth, "id", None),
                )
            )

    if groups is not None:
        user.user_groups.set(groups)

    user.refresh_from_db()
    next_group_ids = set(user.user_groups.values_list("id", flat=True))
    legacy.log_admin_action(
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
    return legacy.serialize_admin_user(user, include_details=True)


@router.delete("/users/{user_id}", auth=AccessTokenAuth(), tags=["Admin"])
def delete_admin_user(request, user_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    legacy = _legacy()
    user = get_object_or_404(legacy.User, id=user_id)

    if user.id == request.auth.id:
        return legacy.admin_error("不能删除当前登录的管理员账号", status=400)

    if user.is_staff and legacy.User.objects.filter(is_staff=True).exclude(id=user.id).count() == 0:
        return legacy.admin_error("至少需要保留一个管理员账号", status=400)

    user_snapshot = {
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
    }
    user.delete()
    legacy.log_admin_action(
        request,
        "admin.user.delete",
        target_type="user",
        target_id=user_id,
        data=user_snapshot,
    )
    return {"message": "用户删除成功"}
