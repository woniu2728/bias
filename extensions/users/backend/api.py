from ninja import Router
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken
from django.conf import settings
from django.http import JsonResponse

from apps.core.api_errors import api_error
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
from extensions.users.backend.preferences import normalize_user_preferences, normalize_user_ui_preferences, serialize_user_preferences
from extensions.users.backend.schemas import (
    EmailVerifySchema,
    PasswordResetRequestSchema,
    PasswordResetSchema,
    TokenSchema,
    UserLoginSchema,
    UserOutSchema,
    UserPreferencesSchema,
    UserPreferencesUpdateSchema,
    UserRegisterSchema,
)
from extensions.users.backend.services import UserService


router = Router()


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


@router.post("/register", response=UserOutSchema, tags=["Auth"])
def register(request, payload: UserRegisterSchema):
    try:
        verify_human_verification(request, "register", payload.human_verification_token)
        return UserService.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except HumanVerificationError as e:
        return api_error(str(e), status=e.status_code)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/login", response=TokenSchema, tags=["Auth"])
def login(request, payload: UserLoginSchema):
    try:
        verify_human_verification(request, "login", payload.human_verification_token)
        user = UserService.authenticate_user(
            identification=payload.identification,
            password=payload.password,
        )

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
    response = JsonResponse({"message": "登出成功"})
    response = _clear_access_token_cookie(response)
    return _clear_refresh_token_cookie(response)


@router.post("/verify-email", response=UserOutSchema, tags=["Auth"])
def verify_email(request, payload: EmailVerifySchema):
    try:
        return UserService.verify_email(payload.token)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/me/resend-email-verification", auth=AccessTokenAuth(), tags=["Users"])
def resend_email_verification(request):
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
    try:
        return UserService.reset_password(payload.token, payload.password)
    except ValueError as e:
        return api_error(str(e), status=400)


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
