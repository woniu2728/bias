from __future__ import annotations

from apps.core.api_errors import api_error


def require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None
