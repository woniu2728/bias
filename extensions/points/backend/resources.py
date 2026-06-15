from __future__ import annotations

from apps.core.extensions import ResourceFieldDefinition


USER_POINT_RESOURCES = (
    "user_detail",
    "user_summary",
    "discussion_user",
    "post_user",
    "search_user",
)


def user_points_resource_field_definitions():
    return tuple(
        ResourceFieldDefinition(
            resource=resource,
            field="points_balance",
            module_id="points",
            resolver=resolve_user_points_balance,
            description="用户当前积分余额。",
            select_related=("point_account",),
        )
        for resource in USER_POINT_RESOURCES
    )


def resolve_user_points_balance(user, context: dict) -> int:
    try:
        account = getattr(user, "point_account", None)
        if account is not None:
            return int(getattr(account, "balance", 0) or 0)
    except Exception:
        return 0
    return 0
