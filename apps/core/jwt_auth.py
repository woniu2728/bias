import logging

from django.conf import settings
from django.http import HttpRequest
from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth, JWTBaseAuthentication


logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE_NAME = "bias_access_token"
ACCESS_TOKEN_COOKIE_PATH = "/"
REFRESH_TOKEN_COOKIE_NAME = "bias_refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/users"


def access_token_max_age() -> int:
    lifetime = settings.NINJA_JWT.get("ACCESS_TOKEN_LIFETIME", 900)
    return int(lifetime.total_seconds() if hasattr(lifetime, "total_seconds") else lifetime)


def refresh_token_max_age() -> int:
    lifetime = settings.NINJA_JWT.get("REFRESH_TOKEN_LIFETIME", 86400)
    return int(lifetime.total_seconds() if hasattr(lifetime, "total_seconds") else lifetime)


def resolve_user_from_access_token(token: str):
    if not token:
        return None

    try:
        auth = JWTBaseAuthentication()
        validated_token = auth.get_validated_token(token)
        return auth.get_user(validated_token)
    except Exception as exc:
        logger.debug("Failed to resolve JWT access token: %s", exc, exc_info=True)
        return None


def resolve_authenticated_user(request: HttpRequest):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.split(" ", 1)[1].strip()
        if token:
            try:
                user = JWTAuth().authenticate(request, token)
            except Exception as exc:
                logger.debug("Failed to authenticate bearer token: %s", exc, exc_info=True)
                user = None
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
