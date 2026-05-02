from typing import Any, Dict

from apps.core.models import AuditLog


def get_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_admin_action(
    request,
    action: str,
    target_type: str = "",
    target_id: int = None,
    data: Dict[str, Any] = None,
):
    """Record an admin/moderation operation without coupling callers to AuditLog fields."""
    return AuditLog.objects.create(
        user=request.auth if getattr(request, "auth", None) and request.auth.is_authenticated else None,
        action=action,
        target_type=target_type or "",
        target_id=target_id,
        ip_address=get_client_ip(request) or None,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        data=data or {},
    )
