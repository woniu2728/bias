from typing import Any, Dict, Optional

from apps.users.models import Group, User


DEFAULT_GROUP_ICONS = {
    1: "fas fa-user-shield",
    4: "fas fa-shield-alt",
}

BUILTIN_GROUP_PRIORITIES = {
    1: 400,
    4: 300,
    3: 100,
    2: 50,
}

ADMIN_FALLBACK_GROUP = {
    "id": 1,
    "name": "Admin",
    "color": "#B72A2A",
    "icon": DEFAULT_GROUP_ICONS[1],
    "is_hidden": False,
}


def get_default_group_icon(group: Optional[Group]) -> str:
    if not group:
        return ""

    if group.id in DEFAULT_GROUP_ICONS:
        return DEFAULT_GROUP_ICONS[group.id]

    return {
        "admin": DEFAULT_GROUP_ICONS[1],
        "moderator": DEFAULT_GROUP_ICONS[4],
    }.get((group.name or "").strip().lower(), "")


def serialize_group_badge(group: Optional[Group]) -> Optional[Dict[str, Any]]:
    if not group:
        return None

    return {
        "id": group.id,
        "name": group.name,
        "color": group.color,
        "icon": (group.icon or "").strip() or get_default_group_icon(group),
        "is_hidden": group.is_hidden,
    }


def get_admin_fallback_group() -> Group:
    return Group(
        id=ADMIN_FALLBACK_GROUP["id"],
        name=ADMIN_FALLBACK_GROUP["name"],
        color=ADMIN_FALLBACK_GROUP["color"],
        icon=ADMIN_FALLBACK_GROUP["icon"],
        is_hidden=ADMIN_FALLBACK_GROUP["is_hidden"],
    )


def _group_priority(group: Group) -> int:
    if group.id in BUILTIN_GROUP_PRIORITIES:
        return BUILTIN_GROUP_PRIORITIES[group.id]

    if group.is_hidden:
        return 10

    return 200


def get_primary_group(user: Optional[User]) -> Optional[Group]:
    if not user:
        return None

    groups = list(user.user_groups.all())
    has_admin_group = any(
        group.id == ADMIN_FALLBACK_GROUP["id"] or (group.name or "").strip().lower() == "admin"
        for group in groups
    )
    if user.is_staff and not has_admin_group:
        groups.insert(0, get_admin_fallback_group())

    if not groups:
        return None

    visible_groups = [group for group in groups if not group.is_hidden]
    candidates = visible_groups or groups

    return max(
        candidates,
        key=lambda group: (
            _group_priority(group),
            int(bool((group.icon or "").strip() or get_default_group_icon(group))),
            group.id,
        ),
    )
