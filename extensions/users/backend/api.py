from ninja import Router
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken
from django.http import JsonResponse

from apps.core.extensions.platform import (
    ACCESS_TOKEN_COOKIE_NAME,
    AccessTokenAuth,
    REFRESH_TOKEN_COOKIE_NAME,
    api_error,
    blacklist_jwt_token,
    clear_access_token_cookie,
    clear_refresh_token_cookie,
    get_frontend_url,
    is_debug_mode,
    set_access_token_cookie,
    set_refresh_token_cookie,
)
from apps.core.extensions.runtime import RuntimeHumanVerificationError, verify_runtime_human_verification
from extensions.users.backend.auth_rate_limit import (
    AuthRateLimitExceeded,
    check_auth_rate_limit,
    clear_auth_rate_limit,
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
GENERIC_PASSWORD_RESET_MESSAGE = "重置密码邮件已发送"
GENERIC_LOGIN_ERROR_MESSAGE = "用户名或密码错误"


@router.post("/register", response=UserOutSchema, tags=["Auth"])
def register(request, payload: UserRegisterSchema):
    try:
        check_auth_rate_limit("register", request, payload.email)
        verify_runtime_human_verification(
            request,
            "register",
            payload.human_verification_token,
            context={"payload": payload.human_verification_payload or {}},
        )
        user = UserService.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
        return user
    except AuthRateLimitExceeded as e:
        return api_error(str(e), status=429)
    except RuntimeHumanVerificationError as e:
        return api_error(str(e), status=e.status_code)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/login", response=TokenSchema, tags=["Auth"])
def login(request, payload: UserLoginSchema):
    try:
        check_auth_rate_limit("login", request, payload.identification)
        verify_runtime_human_verification(
            request,
            "login",
            payload.human_verification_token,
            context={"payload": payload.human_verification_payload or {}},
        )
        user = UserService.authenticate_user(
            identification=payload.identification,
            password=payload.password,
        )

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        response = JsonResponse({"access": access_token})
        response = set_access_token_cookie(response, access_token)
        clear_auth_rate_limit("login", request, payload.identification)
        return set_refresh_token_cookie(response, str(refresh))
    except AuthRateLimitExceeded as e:
        return api_error(str(e), status=429)
    except RuntimeHumanVerificationError as e:
        return api_error(str(e), status=e.status_code)
    except ValueError as e:
        message = str(e) if "账号已被封禁" in str(e) else GENERIC_LOGIN_ERROR_MESSAGE
        return api_error(message, status=401)


@router.post("/token/refresh", response=TokenSchema, tags=["Auth"])
def refresh_access_token(request):
    refresh_token = request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        return api_error("登录状态已过期，请重新登录", status=401)

    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        response = JsonResponse({"access": access_token})
        return set_access_token_cookie(response, access_token)
    except TokenError:
        response = api_error("登录状态已过期，请重新登录", status=401)
        response = clear_access_token_cookie(response)
        return clear_refresh_token_cookie(response)


@router.post("/logout", tags=["Auth"])
def logout(request):
    # 将当前 access token 和 refresh token 加入黑名单
    access_token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if access_token:
        blacklist_jwt_token(access_token)
    cookie_token = request.COOKIES.get(ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        blacklist_jwt_token(cookie_token)
    refresh_cookie = request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME)
    if refresh_cookie:
        blacklist_jwt_token(refresh_cookie)

    response = JsonResponse({"message": "登出成功"})
    response = clear_access_token_cookie(response)
    return clear_refresh_token_cookie(response)


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

        if is_debug_mode():
            response["debug_token"] = email_token.token
            response["debug_verify_url"] = f"{get_frontend_url()}/verify-email?token={email_token.token}"

        return response
    except ValueError as e:
        return api_error(str(e), status=400)


@router.post("/forgot-password", tags=["Auth"])
def forgot_password(request, payload: PasswordResetRequestSchema):
    try:
        check_auth_rate_limit("forgot_password", request, payload.email)
        password_token = UserService.create_password_reset_token(payload.email)
        response = {"message": GENERIC_PASSWORD_RESET_MESSAGE}

        if is_debug_mode():
            response["debug_token"] = password_token.token
            response["debug_reset_url"] = f"{get_frontend_url()}/reset-password?token={password_token.token}"

        return response
    except AuthRateLimitExceeded as e:
        return api_error(str(e), status=429)
    except ValueError:
        return {"message": GENERIC_PASSWORD_RESET_MESSAGE}


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
