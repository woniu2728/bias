from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.auth import AuthMiddlewareStack
from django.contrib.auth.models import AnonymousUser
from ninja_jwt.tokens import RefreshToken

from apps.core.jwt_auth import ACCESS_TOKEN_COOKIE_NAME, resolve_user_from_access_token
from extensions.users.backend.models import User


REFRESH_TOKEN_COOKIE_NAME = "bias_refresh_token"


def resolve_user_from_token(token: str):
    return resolve_user_from_access_token(token) or AnonymousUser()


def resolve_user_from_refresh_token(token: str):
    if not token:
        return AnonymousUser()

    try:
        refresh = RefreshToken(token)
        user_id = refresh.payload.get("user_id")
        if not user_id:
            return AnonymousUser()
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()


@sync_to_async
def get_user_from_token(token: str):
    return resolve_user_from_token(token)


@sync_to_async
def get_user_from_refresh_token(token: str):
    return resolve_user_from_refresh_token(token)


def _parse_cookie_header(scope) -> dict[str, str]:
    headers = dict(scope.get("headers", []))
    raw_cookie = headers.get(b"cookie", b"").decode()
    cookies: dict[str, str] = {}
    for item in raw_cookie.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


class JWTQueryAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        cookies = _parse_cookie_header(scope)
        access_token = cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        if access_token:
            scope["user"] = await get_user_from_token(access_token)
            if not isinstance(scope["user"], AnonymousUser):
                return await self.inner(scope, receive, send)

        refresh_token = cookies.get(REFRESH_TOKEN_COOKIE_NAME)
        if refresh_token:
            scope["user"] = await get_user_from_refresh_token(refresh_token)
            if not isinstance(scope["user"], AnonymousUser):
                return await self.inner(scope, receive, send)

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTQueryAuthMiddleware(AuthMiddlewareStack(inner))
