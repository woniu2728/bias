"""
User API endpoints
"""
from ninja import Router
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.db.models import Q
from typing import List

from apps.core.auth import get_optional_user
from apps.core.api_errors import api_error
from apps.core.forum_resources import serialize_user_payload
from apps.core.resource_api import ResourceQueryOptions, apply_resource_preloads, parse_resource_query_options
from apps.core.resource_registry import get_resource_registry
from apps.core.human_verification import HumanVerificationError, verify_human_verification
from apps.core.jwt_auth import (
    ACCESS_TOKEN_COOKIE_NAME,
    ACCESS_TOKEN_COOKIE_PATH,
    AccessTokenAuth,
    REFRESH_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_PATH,
    access_token_max_age,
    refresh_token_max_age,
)
from apps.core.services import PaginationService
from .models import User
from .preferences import normalize_user_preferences, normalize_user_ui_preferences, serialize_user_preferences
from apps.core.file_service import FileUploadService
from .schemas import (
    UserRegisterSchema,
    UserLoginSchema,
    TokenSchema,
    UserOutSchema,
    UserDetailSchema,
    CurrentUserSchema,
    UserUpdateSchema,
    PasswordChangeSchema,
    PasswordResetRequestSchema,
    PasswordResetSchema,
    EmailVerifySchema,
    UserPreferencesSchema,
    UserPreferencesUpdateSchema,
)
from .services import UserService

router = Router()
RESOURCE_REGISTRY = get_resource_registry()


def _set_refresh_token_cookie(response: JsonResponse, refresh: RefreshToken) -> JsonResponse:
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        str(refresh),
        max_age=refresh_token_max_age(),
        path=REFRESH_TOKEN_COOKIE_PATH,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="Lax",
    )
    return response


def _set_access_token_cookie(response: JsonResponse, access_token: str) -> JsonResponse:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=access_token_max_age(),
        path=ACCESS_TOKEN_COOKIE_PATH,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="Lax",
    )
    return response


def _clear_access_token_cookie(response: JsonResponse) -> JsonResponse:
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        path=ACCESS_TOKEN_COOKIE_PATH,
        samesite="Lax",
    )
    return response


def _clear_refresh_token_cookie(response: JsonResponse) -> JsonResponse:
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
        samesite="Lax",
    )
    return response


def _attach_current_user_context(user):
    if user:
        user.forum_permissions = UserService.get_serialized_forum_permissions(user)
    return user


def _serialize_user_detail_payload(user, include_forum_permissions: bool = False, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    payload = RESOURCE_REGISTRY.serialize(
        "user_detail",
        user,
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


def _serialize_user_groups_for_schema(user):
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


def _serialize_user_out_payload(user):
    payload = _serialize_user_detail_payload(user)
    payload.setdefault("email", user.email)
    payload.setdefault("is_email_confirmed", user.is_email_confirmed)
    payload.setdefault("is_suspended", user.is_suspended)
    payload.setdefault("is_staff", user.is_staff)
    return payload


# ==================== 认证相关 ====================

@router.post("/register", response=UserOutSchema, tags=["Auth"])
def register(request, payload: UserRegisterSchema):
    """用户注册"""
    try:
        verify_human_verification(request, "register", payload.human_verification_token)
        user = UserService.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
        return user
    except HumanVerificationError as e:
        return api_error(str(e), status=e.status_code)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/login", response=TokenSchema, tags=["Auth"])
def login(request, payload: UserLoginSchema):
    """用户登录"""
    try:
        verify_human_verification(request, "login", payload.human_verification_token)
        user = UserService.authenticate_user(
            identification=payload.identification,
            password=payload.password,
        )

        # 生成JWT Token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        response = JsonResponse({"access": access_token})
        response = _set_access_token_cookie(response, access_token)
        return _set_refresh_token_cookie(response, refresh)
    except HumanVerificationError as e:
        return api_error(str(e), status=e.status_code)
    except ValueError as e:
        return api_error(str(e), status=401)


@router.post("/token/refresh", response=TokenSchema, tags=["Auth"])
def refresh_access_token(request):
    """使用 HttpOnly Cookie 中的 refresh token 换取新的 access token"""
    refresh_token = request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        return api_error("登录状态已过期，请重新登录", status=401)

    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        response = JsonResponse({"access": access_token})
        return _set_access_token_cookie(response, access_token)
    except TokenError:
        response = api_error("登录状态已过期，请重新登录", status=401)
        response = _clear_access_token_cookie(response)
        return _clear_refresh_token_cookie(response)


@router.post("/logout", tags=["Auth"])
def logout(request):
    """用户登出"""
    response = JsonResponse({"message": "登出成功"})
    response = _clear_access_token_cookie(response)
    return _clear_refresh_token_cookie(response)


@router.post("/verify-email", response=UserOutSchema, tags=["Auth"])
def verify_email(request, payload: EmailVerifySchema):
    """验证邮箱"""
    try:
        user = UserService.verify_email(payload.token)
        return user
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/me/resend-email-verification", auth=AccessTokenAuth(), tags=["Users"])
def resend_email_verification(request):
    """重新发送邮箱验证邮件"""
    try:
        email_token = UserService.resend_email_verification(request.auth)
        response = {"message": "验证邮件已重新发送"}

        if settings.DEBUG:
            response["debug_token"] = email_token.token
            response["debug_verify_url"] = f"{settings.FRONTEND_URL}/verify-email?token={email_token.token}"

        return response
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/forgot-password", tags=["Auth"])
def forgot_password(request, payload: PasswordResetRequestSchema):
    """请求重置密码"""
    try:
        password_token = UserService.create_password_reset_token(payload.email)
        response = {"message": "重置密码邮件已发送"}

        if settings.DEBUG:
            response["debug_token"] = password_token.token
            response["debug_reset_url"] = f"{settings.FRONTEND_URL}/reset-password?token={password_token.token}"

        return response
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/reset-password", response=UserOutSchema, tags=["Auth"])
def reset_password(request, payload: PasswordResetSchema):
    """重置密码"""
    try:
        user = UserService.reset_password(payload.token, payload.password)
        return user
    except ValueError as e:
        return api_error(str(e), status=400)


# ==================== 用户信息 ====================

@router.get("/me", response=CurrentUserSchema, auth=AccessTokenAuth(), tags=["Users"])
def get_current_user(request):
    """获取当前用户信息"""
    user = _attach_current_user_context(request.auth)
    payload = _serialize_user_detail_payload(user, include_forum_permissions=True)
    payload["groups"] = _serialize_user_groups_for_schema(user)
    return payload


@router.get("/me/preferences", response=UserPreferencesSchema, auth=AccessTokenAuth(), tags=["Users"])
def get_preferences(request):
    return serialize_user_preferences(request.auth)


@router.patch("/me/preferences", response=UserPreferencesSchema, auth=AccessTokenAuth(), tags=["Users"])
def update_preferences(request, payload: UserPreferencesUpdateSchema):
    request.auth.preferences = {
        **(request.auth.preferences or {}),
        **normalize_user_preferences(payload.values),
    }
    request.auth.preferences_ui = normalize_user_ui_preferences(request.auth.preferences_ui)
    request.auth.save(update_fields=["preferences", "preferences_ui"])
    return serialize_user_preferences(request.auth)


@router.get("", tags=["Users"])
def list_users(request, page: int = 1, limit: int = 20, q: str = None):
    """获取用户列表"""
    user = get_optional_user(request)
    if user:
        user = _attach_current_user_context(user)
    page, limit = PaginationService.normalize(page, limit)

    if q:
        if not UserService.has_forum_permission(user, "searchUsers"):
            return api_error("没有权限搜索用户", status=403)
    elif not UserService.has_forum_permission(user, "viewUserList"):
        return api_error("没有权限查看用户列表", status=403)

    resource_options = parse_resource_query_options(request, "user_detail")
    queryset = apply_resource_preloads(
        RESOURCE_REGISTRY,
        User.objects.all(),
        "user_detail",
        resource_options=resource_options,
        default_includes=("groups",),
    )

    # 搜索
    if q:
        queryset = queryset.filter(Q(username__icontains=q) | Q(display_name__icontains=q))

    # 分页
    start = (page - 1) * limit
    end = start + limit

    users = list(queryset[start:end])
    return JsonResponse(
        [_serialize_user_detail_payload(item, resource_options=resource_options) for item in users],
        safe=False,
    )


@router.get("/by-username/{username}", tags=["Users"])
def get_user_by_username(request, username: str):
    """按用户名获取用户详情，兼容旧版 @提及 链接"""
    resource_options = parse_resource_query_options(request, "user_detail")
    user = get_object_or_404(
        apply_resource_preloads(
            RESOURCE_REGISTRY,
            User.objects.filter(username=username),
            "user_detail",
            resource_options=resource_options,
            default_includes=("groups",),
        )
    )
    return JsonResponse(_serialize_user_detail_payload(user, resource_options=resource_options))


@router.get("/{user_id}", tags=["Users"])
def get_user(request, user_id: int):
    """获取用户详情"""
    resource_options = parse_resource_query_options(request, "user_detail")
    user = get_object_or_404(
        apply_resource_preloads(
            RESOURCE_REGISTRY,
            User.objects.filter(id=user_id),
            "user_detail",
            resource_options=resource_options,
            default_includes=("groups",),
        )
    )
    return JsonResponse(_serialize_user_detail_payload(user, resource_options=resource_options))


@router.patch("/{user_id}", response=UserOutSchema, auth=AccessTokenAuth(), tags=["Users"])
def update_user(request, user_id: int, payload: UserUpdateSchema):
    """更新用户信息"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限：只能修改自己的信息
    if request.auth.id != user.id and not request.auth.is_staff:
        return api_error("无权限", status=403)

    try:
        user = UserService.update_user(
            user,
            display_name=payload.display_name,
            bio=payload.bio,
            email=payload.email,
        )
        user = User.objects.prefetch_related("user_groups").get(id=user.id)
        return _serialize_user_detail_payload(user)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/{user_id}/password", auth=AccessTokenAuth(), tags=["Users"])
def change_password(request, user_id: int, payload: PasswordChangeSchema):
    """修改密码"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限：只能修改自己的密码
    if request.auth.id != user.id:
        return api_error("无权限", status=403)

    try:
        UserService.change_password(user, payload.old_password, payload.new_password)
        return {"message": "密码修改成功"}
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/{user_id}/avatar", response=UserOutSchema, auth=AccessTokenAuth(), tags=["Users"])
def upload_avatar(request, user_id: int):
    """上传头像"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限
    if request.auth.id != user.id:
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
        return _serialize_user_detail_payload(user)
    except ValueError as e:
        return api_error(str(e), status=400)
