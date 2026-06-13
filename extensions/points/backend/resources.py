from __future__ import annotations

from apps.core.resource_registry import ResourceFieldDefinition


def user_detail_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="user_detail",
            field="points_balance",
            module_id="points",
            resolver=resolve_user_points_balance,
            description="用户当前积分余额。",
            select_related=("point_account",),
        ),
    )


def user_summary_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="user_summary",
            field="points_balance",
            module_id="points",
            resolver=resolve_user_points_balance,
            description="用户当前积分余额。",
            select_related=("point_account",),
        ),
    )


def resolve_user_points_balance(user, context: dict) -> int:
    try:
        account = getattr(user, "point_account", None)
        if account is not None:
            return int(getattr(account, "balance", 0) or 0)
    except Exception:
        return 0
    return 0
