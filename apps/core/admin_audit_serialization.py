from __future__ import annotations

from apps.core.models import AuditLog


def serialize_audit_log(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "data": log.data,
        "created_at": log.created_at,
        "user": {
            "id": log.user.id,
            "username": log.user.username,
            "display_name": log.user.display_name,
        } if log.user else None,
    }
