import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTBaseAuthentication
from ninja_jwt.tokens import RefreshToken


logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE_NAME = "bias_access_token"
ACCESS_TOKEN_COOKIE_PATH = "/"
REFRESH_TOKEN_COOKIE_NAME = "bias_refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/users"

# JWT 黑名单缓存前缀 + TTL 缓冲（秒）
_BLACKLIST_CACHE_PREFIX = "jwt:blacklist:"
_BLACKLIST_TTL_BUFFER = 300  # 额外保留 5 分钟防止时钟偏差"


def access_token_max_age() -> int:
    lifetime = settings.NINJA_JWT.get("ACCESS_TOKEN_LIFETIME", 900)
    return int(lifetime.total_seconds() if hasattr(lifetime, "total_seconds") else lifetime)


def refresh_token_max_age() -> int:
    lifetime = settings.NINJA_JWT.get("REFRESH_TOKEN_LIFETIME", 86400)
    return int(lifetime.total_seconds() if hasattr(lifetime, "total_seconds") else lifetime)


def auth_cookie_secure() -> bool:
    return bool(
        getattr(settings, "SESSION_COOKIE_SECURE", not settings.DEBUG)
        or getattr(settings, "CSRF_COOKIE_SECURE", False)
    )


def set_access_token_cookie(response, access_token: str):
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=access_token_max_age(),
        path=ACCESS_TOKEN_COOKIE_PATH,
        secure=auth_cookie_secure(),
        httponly=True,
        samesite="Lax",
    )
    return response


def set_refresh_token_cookie(response, refresh_token: str):
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=refresh_token_max_age(),
        path=REFRESH_TOKEN_COOKIE_PATH,
        secure=auth_cookie_secure(),
        httponly=True,
        samesite="Lax",
    )
    return response


def clear_access_token_cookie(response):
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        path=ACCESS_TOKEN_COOKIE_PATH,
        samesite="Lax",
    )
    return response


def clear_refresh_token_cookie(response):
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
        samesite="Lax",
    )
    return response


def resolve_user_from_access_token(token: str):
    if not token:
        return None

    if is_jwt_blacklisted(token):
        logger.debug("JWT token is blacklisted, rejecting.")
        return None

    try:
        auth = JWTBaseAuthentication()
        validated_token = auth.get_validated_token(token)
        return auth.get_user(validated_token)
    except Exception as exc:
        logger.debug("Failed to resolve JWT access token: %s", exc, exc_info=True)
        return None


def blacklist_jwt_token(token_str: str) -> None:
    """将 JWT token 加入黑名单，使其在剩余有效期内失效。"""
    try:
        from ninja_jwt.authentication import JWTBaseAuthentication

        auth = JWTBaseAuthentication()
        validated = auth.get_validated_token(token_str)
        jti = validated.get("jti", "")
        exp = validated.get("exp", 0)
        if not jti:
            return
        now = datetime.now(tz=timezone.utc).timestamp()
        ttl = max(int(exp - now) + _BLACKLIST_TTL_BUFFER, _BLACKLIST_TTL_BUFFER)
        cache.set(f"{_BLACKLIST_CACHE_PREFIX}{jti}", "1", timeout=ttl)
    except Exception as exc:
        logger.warning("Failed to blacklist JWT token: %s", exc, exc_info=True)


def is_jwt_blacklisted(token_str: str) -> bool:
    """检查 JWT token 是否已被加入黑名单。"""
    try:
        from ninja_jwt.authentication import JWTBaseAuthentication

        auth = JWTBaseAuthentication()
        validated = auth.get_validated_token(token_str)
        jti = validated.get("jti", "")
        if not jti:
            return False
        return bool(_get_jwt_blacklist_cache(jti))
    except Exception:
        return False


def _get_jwt_blacklist_cache(jti: str) -> str | None:
    """内部函数：读取 JWT 黑名单缓存，避免被测试中的 cache.get mock 意外干扰。"""
    return cache.get(f"{_BLACKLIST_CACHE_PREFIX}{jti}")


def blacklist_refresh_token(token_str: str) -> None:
    """将 RefreshToken 加入黑名单。blacklist_jwt_token 的别名。"""
    blacklist_jwt_token(token_str)


def resolve_authenticated_user(request: HttpRequest):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.split(" ", 1)[1].strip()
        if token:
            user = resolve_user_from_access_token(token)
            if getattr(user, "is_authenticated", False):
                return user

    cookie_token = request.COOKIES.get(ACCESS_TOKEN_COOKIE_NAME)
    user = resolve_user_from_access_token(cookie_token or "")
    if getattr(user, "is_authenticated", False):
        return user

    return None


class AccessTokenAuth(HttpBearer):
    """JWT auth that accepts bearer header or HttpOnly access token cookie."""

    def __call__(self, request: HttpRequest):
        return resolve_authenticated_user(request)

    def authenticate(self, request: HttpRequest, token: str):
        return resolve_user_from_access_token(token)
