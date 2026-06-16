from __future__ import annotations

from ninja import Router

from apps.core.admin_audit_serialization import serialize_audit_log
from apps.core.admin_auth import require_staff
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.models import AuditLog
from apps.core.services import PaginationService


router = Router()


@router.get("/audit-logs", auth=AccessTokenAuth(), tags=["Admin"])
def list_audit_logs(
    request,
    page: int = 1,
    limit: int = 20,
    action: str = "",
    target_type: str = "",
    user_id: int = None,
):
    denied = require_staff(request)
    if denied:
        return denied

    page, limit = PaginationService.normalize(page, limit)
    queryset = (
        AuditLog.objects.select_related("user")
        .filter(action__startswith="admin.")
        .order_by("-created_at", "-id")
    )

    if action:
        queryset = queryset.filter(action=action)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    total = queryset.count()
    offset = (page - 1) * limit
    logs = queryset[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [serialize_audit_log(log) for log in logs],
    }
