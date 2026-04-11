from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.auth import AuthMiddlewareStack
from django.contrib.auth.models import AnonymousUser
from ninja_jwt.authentication import JWTBaseAuthentication


@sync_to_async
def get_user_from_token(token: str):
    if not token:
        return AnonymousUser()

    try:
        auth = JWTBaseAuthentication()
        validated_token = auth.get_validated_token(token)
        return auth.get_user(validated_token)
    except Exception:
        return AnonymousUser()


class JWTQueryAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTQueryAuthMiddleware(AuthMiddlewareStack(inner))
