from __future__ import annotations

from django.db.models import Q

from apps.core.api_errors import api_error
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.file_service import FileUploadService
from apps.core.resource_api import ResourceQueryOptions, apply_resource_preloads, parse_resource_query_options
from apps.core.resource_registry import ResourceEndpointDefinition
from apps.core.services import PaginationService
from apps.users.models import User
from apps.users.schemas import PasswordChangeSchema, UserUpdateSchema
from apps.users.services import UserService


def get_resource_registry():
    return get_runtime_resource_registry()


def attach_current_user_context(user):
    if user:
        user.forum_permissions = UserService.get_serialized_forum_permissions(user)
    return user


def serialize_user_detail_payload(user, include_forum_permissions: bool = False, resource_options=None, actor=None):
    resource_options = resource_options or ResourceQueryOptions()
    payload = get_resource_registry().serialize(
        "user_detail",
        user,
        {"user": actor} if actor is not None else {},
        only=resource_options.fields,
        include=resource_options.includes,
    ) or {}
    payload.update(
        {
            "email": user.email,
            "is_email_confirmed": user.is_email_confirmed,
            "is_suspended": user.is_suspended,
            "is_staff": user.is_staff,
        }
    )
    if "groups" not in payload and hasattr(user, "user_groups"):
        payload["groups"] = [
            {
                "id": group.id,
                "name": group.name,
                "color": group.color,
                "icon": group.icon,
                "is_hidden": group.is_hidden,
            }
            for group in user.user_groups.all()
        ]
    if hasattr(user, "preferences"):
        payload["preferences"] = user.preferences or {}
    if include_forum_permissions:
        payload["forum_permissions"] = getattr(user, "forum_permissions", [])
        payload["suspended_until"] = user.suspended_until
        payload["suspend_reason"] = user.suspend_reason
        payload["suspend_message"] = user.suspend_message
    return payload


def serialize_user_groups_for_schema(user):
    if not hasattr(user, "user_groups"):
        return []
    return [
        {
            "id": group.id,
            "name": group.name,
            "name_singular": group.name,
            "name_plural": group.name,
            "color": group.color,
            "icon": group.icon,
            "is_hidden": group.is_hidden,
        }
        for group in user.user_groups.all()
    ]


def register_user_core_resource_endpoints(registry=None):
    registry = registry or get_resource_registry()
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="current",
            module_id="core",
            handler=dispatch_current_user,
            methods=("GET",),
            path="users/me",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="index",
            module_id="core",
            handler=dispatch_user_index,
            methods=("GET",),
            path="users",
            absolute_path=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="by-username",
            module_id="core",
            handler=dispatch_user_by_username,
            methods=("GET",),
            path="users/by-username/{object_id}",
            absolute_path=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="show",
            module_id="core",
            handler=dispatch_user_show,
            methods=("GET",),
            path="users/{object_id}",
            absolute_path=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="update",
            module_id="core",
            handler=dispatch_user_update,
            methods=("PATCH",),
            path="users/{object_id}",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="password",
            module_id="core",
            handler=dispatch_user_change_password,
            methods=("POST",),
            path="users/{object_id}/password",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="user_detail",
            endpoint="avatar.upload",
            module_id="core",
            handler=dispatch_user_upload_avatar,
            methods=("POST",),
            path="users/{object_id}/avatar",
            absolute_path=True,
            auth_required=True,
        )
    )


def _user_query_value(context, key: str, default=None):
    return dict(context.get("query") or {}).get(key, default)


def _user_payload(context) -> dict:
    payload = context.get("payload")
    return payload if isinstance(payload, dict) else {}


def _user_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


def dispatch_current_user(context):
    user = attach_current_user_context(context["user"])
    payload = serialize_user_detail_payload(user, include_forum_permissions=True, actor=user)
    payload["groups"] = serialize_user_groups_for_schema(user)
    return payload


def dispatch_user_index(context):
    request = context["request"]
    user = context.get("user")
    if user:
        user = attach_current_user_context(user)
    page, limit = PaginationService.normalize(
        _user_query_value(context, "page", 1),
        _user_query_value(context, "limit", 20),
    )
    q = _user_query_value(context, "q")

    if q:
        if not UserService.has_forum_permission(user, "searchUsers"):
            return api_error("没有权限搜索用户", status=403)
    elif not UserService.has_forum_permission(user, "viewUserList"):
        return api_error("没有权限查看用户列表", status=403)

    resource_options = parse_resource_query_options(request, "user_detail")
    queryset = apply_resource_preloads(
        get_resource_registry(),
        User.objects.all(),
        "user_detail",
        resource_options=resource_options,
        default_includes=("groups",),
    )

    if q:
        queryset = queryset.filter(Q(username__icontains=q) | Q(display_name__icontains=q))

    start = (page - 1) * limit
    end = start + limit
    users = list(queryset[start:end])
    return [serialize_user_detail_payload(item, resource_options=resource_options, actor=user) for item in users]


def dispatch_user_by_username(context):
    request = context["request"]
    actor = context.get("user")
    username = str(context.get("object_id") or "").strip()
    resource_options = parse_resource_query_options(request, "user_detail")
    user = apply_resource_preloads(
        get_resource_registry(),
        User.objects.filter(username=username),
        "user_detail",
        resource_options=resource_options,
        default_includes=("groups",),
    ).first()
    if not user:
        return api_error("用户不存在", status=404)
    return serialize_user_detail_payload(user, resource_options=resource_options, actor=actor)


def dispatch_user_show(context):
    request = context["request"]
    actor = context.get("user")
    resource_options = parse_resource_query_options(request, "user_detail")
    user = apply_resource_preloads(
        get_resource_registry(),
        User.objects.filter(id=_user_object_id(context)),
        "user_detail",
        resource_options=resource_options,
        default_includes=("groups",),
    ).first()
    if not user:
        return api_error("用户不存在", status=404)
    return serialize_user_detail_payload(user, resource_options=resource_options, actor=actor)


def dispatch_user_update(context):
    user_id = _user_object_id(context)
    user = User.objects.filter(id=user_id).first()
    if not user:
        return api_error("用户不存在", status=404)
    actor = context["user"]

    if actor.id != user.id and not actor.is_staff:
        return api_error("无权限", status=403)

    payload = UserUpdateSchema(**_user_payload(context))
    try:
        user = UserService.update_user(
            user,
            display_name=payload.display_name,
            bio=payload.bio,
            email=payload.email,
        )
        user = User.objects.prefetch_related("user_groups").get(id=user.id)
        return serialize_user_detail_payload(user, actor=actor)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_user_change_password(context):
    user_id = _user_object_id(context)
    user = User.objects.filter(id=user_id).first()
    if not user:
        return api_error("用户不存在", status=404)

    if context["user"].id != user.id:
        return api_error("无权限", status=403)

    payload = PasswordChangeSchema(**_user_payload(context))
    try:
        UserService.change_password(user, payload.old_password, payload.new_password)
        return {"message": "密码修改成功"}
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_user_upload_avatar(context):
    request = context["request"]
    user_id = _user_object_id(context)
    user = User.objects.filter(id=user_id).first()
    if not user:
        return api_error("用户不存在", status=404)

    if context["user"].id != user.id:
        return api_error("无权限", status=403)

    avatar = request.FILES.get("avatar")
    if not avatar:
        return api_error("请选择要上传的头像", status=400)

    try:
        previous_avatar = user.avatar_url
        avatar_url, _ = FileUploadService.upload_avatar(avatar, user.id)
        user.avatar_url = avatar_url
        user.save(update_fields=["avatar_url"])

        if previous_avatar and previous_avatar != avatar_url:
            FileUploadService.delete_file(previous_avatar)

        user = User.objects.prefetch_related("user_groups").get(id=user.id)
        return serialize_user_detail_payload(user)
    except ValueError as e:
        return api_error(str(e), status=400)
