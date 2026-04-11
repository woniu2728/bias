from ninja.security import HttpBearer


class AuthBearer(HttpBearer):
    """JWT bearer auth shared by public and protected API routers."""

    def authenticate(self, request, token):
        try:
            from ninja_jwt.authentication import JWTAuth

            return JWTAuth().authenticate(request, token)
        except Exception:
            return None


def get_optional_user(request):
    if getattr(request, "auth", None) and request.auth.is_authenticated:
        return request.auth

    if getattr(request, "user", None) and request.user.is_authenticated:
        return request.user

    user = AuthBearer()(request)
    if user and user.is_authenticated:
        return user

    return None
