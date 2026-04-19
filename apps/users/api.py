"""
User API endpoints
"""
from ninja import Router
from ninja.security import HttpBearer
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from typing import List

from apps.core.human_verification import HumanVerificationError, verify_human_verification
from .models import User
from apps.core.file_service import FileUploadService
from apps.users.group_utils import get_primary_group, serialize_group_badge
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
)
from .services import UserService

router = Router()


def _attach_primary_group(user):
    if not user:
        return None

    user.primary_group = serialize_group_badge(get_primary_group(user))
    return user


def _attach_primary_groups(users):
    for user in users:
        _attach_primary_group(user)
    return users


class AuthBearer(HttpBearer):
    """JWT认证"""
    def authenticate(self, request, token):
        try:
            from ninja_jwt.authentication import JWTAuth
            jwt_auth = JWTAuth()
            return jwt_auth.authenticate(request, token)
        except Exception:
            return None


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
        return JsonResponse({"error": str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


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
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
    except HumanVerificationError as e:
        return JsonResponse({"error": str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=401)


@router.post("/logout", auth=AuthBearer(), tags=["Auth"])
def logout(request):
    """用户登出"""
    # JWT是无状态的，客户端删除token即可
    return {"message": "登出成功"}


@router.post("/verify-email", response=UserOutSchema, tags=["Auth"])
def verify_email(request, payload: EmailVerifySchema):
    """验证邮箱"""
    try:
        user = UserService.verify_email(payload.token)
        return user
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/me/resend-email-verification", auth=AuthBearer(), tags=["Users"])
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
        return JsonResponse({"error": str(e)}, status=400)


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
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/reset-password", response=UserOutSchema, tags=["Auth"])
def reset_password(request, payload: PasswordResetSchema):
    """重置密码"""
    try:
        user = UserService.reset_password(payload.token, payload.password)
        return user
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


# ==================== 用户信息 ====================

@router.get("/me", response=CurrentUserSchema, auth=AuthBearer(), tags=["Users"])
def get_current_user(request):
    """获取当前用户信息"""
    return _attach_primary_group(request.auth)


@router.get("/me/preferences", response=UserPreferencesSchema, auth=AuthBearer(), tags=["Users"])
def get_preferences(request):
    prefs = request.auth.preferences or {}
    return {
        "follow_after_reply": prefs.get("follow_after_reply", False),
        "follow_after_create": prefs.get("follow_after_create", False),
        "notify_new_post": prefs.get("notify_new_post", True),
    }


@router.patch("/me/preferences", response=UserPreferencesSchema, auth=AuthBearer(), tags=["Users"])
def update_preferences(request, payload: UserPreferencesSchema):
    request.auth.preferences = {
        **(request.auth.preferences or {}),
        "follow_after_reply": payload.follow_after_reply,
        "follow_after_create": payload.follow_after_create,
        "notify_new_post": payload.notify_new_post,
    }
    request.auth.save(update_fields=["preferences"])

    return {
        "follow_after_reply": request.auth.preferences.get("follow_after_reply", False),
        "follow_after_create": request.auth.preferences.get("follow_after_create", False),
        "notify_new_post": request.auth.preferences.get("notify_new_post", True),
    }


@router.get("", response=List[UserOutSchema], tags=["Users"])
def list_users(request, page: int = 1, limit: int = 20, q: str = None):
    """获取用户列表"""
    queryset = User.objects.prefetch_related("user_groups").all()

    # 搜索
    if q:
        queryset = queryset.filter(username__icontains=q) | queryset.filter(display_name__icontains=q)

    # 分页
    start = (page - 1) * limit
    end = start + limit

    return _attach_primary_groups(list(queryset[start:end]))


@router.get("/{user_id}", response=UserDetailSchema, tags=["Users"])
def get_user(request, user_id: int):
    """获取用户详情"""
    user = get_object_or_404(User.objects.prefetch_related("user_groups"), id=user_id)
    return _attach_primary_group(user)


@router.patch("/{user_id}", response=UserOutSchema, auth=AuthBearer(), tags=["Users"])
def update_user(request, user_id: int, payload: UserUpdateSchema):
    """更新用户信息"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限：只能修改自己的信息
    if request.auth.id != user.id and not request.auth.is_staff:
        return JsonResponse({"error": "无权限"}, status=403)

    try:
        user = UserService.update_user(
            user,
            display_name=payload.display_name,
            bio=payload.bio,
            email=payload.email,
        )
        user = User.objects.prefetch_related("user_groups").get(id=user.id)
        return _attach_primary_group(user)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/{user_id}/password", auth=AuthBearer(), tags=["Users"])
def change_password(request, user_id: int, payload: PasswordChangeSchema):
    """修改密码"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限：只能修改自己的密码
    if request.auth.id != user.id:
        return JsonResponse({"error": "无权限"}, status=403)

    try:
        UserService.change_password(user, payload.old_password, payload.new_password)
        return {"message": "密码修改成功"}
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/{user_id}/avatar", response=UserOutSchema, auth=AuthBearer(), tags=["Users"])
def upload_avatar(request, user_id: int):
    """上传头像"""
    user = get_object_or_404(User, id=user_id)

    # 检查权限
    if request.auth.id != user.id:
        return JsonResponse({"error": "无权限"}, status=403)

    avatar = request.FILES.get("avatar")
    if not avatar:
        return JsonResponse({"error": "请选择要上传的头像"}, status=400)

    try:
        previous_avatar = user.avatar_url
        avatar_url, _ = FileUploadService.upload_avatar(avatar, user.id)
        user.avatar_url = avatar_url
        user.save(update_fields=["avatar_url"])

        if previous_avatar and previous_avatar != avatar_url:
            FileUploadService.delete_file(previous_avatar)

        user = User.objects.prefetch_related("user_groups").get(id=user.id)
        return _attach_primary_group(user)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
