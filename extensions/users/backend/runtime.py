from __future__ import annotations


def user_model_provider() -> dict:
    from extensions.users.backend.models import User

    return {
        "model": User,
        "get_by_id": get_user_by_id,
        "get_by_username": get_user_by_username,
        "list_by_usernames": list_users_by_usernames,
        "username_id_map": get_username_id_map,
        "serialize": serialize_user,
        "serialize_many_by_ids": serialize_users_by_ids,
        "ensure_admin": ensure_admin_user,
    }


def user_service_provider() -> dict:
    from extensions.users.backend.models import Group, Permission, User
    from extensions.users.backend.preferences import get_user_preference_value
    from extensions.users.backend.services import UserService

    return {
        "model": User,
        "group_model": Group,
        "permission_model": Permission,
        "get_by_id": get_user_by_id,
        "get_by_username": get_user_by_username,
        "list_by_usernames": list_users_by_usernames,
        "username_id_map": get_username_id_map,
        "serialize_many_by_ids": serialize_users_by_ids,
        "ensure_admin": ensure_admin_user,
        "ensure_not_suspended": UserService.ensure_not_suspended,
        "ensure_email_confirmed": UserService.ensure_email_confirmed,
        "ensure_forum_permission": UserService.ensure_forum_permission,
        "has_forum_permission": UserService.has_forum_permission,
        "requires_content_approval": UserService.requires_content_approval,
        "build_suspension_notice": UserService.build_suspension_notice,
        "get_preference": get_user_preference_value,
        "increment_discussion_count": increment_discussion_count,
        "increment_comment_count": increment_comment_count,
        "apply_comment_count_deltas": apply_comment_count_deltas,
    }


def get_user_by_id(user_id):
    from extensions.users.backend.models import User

    return User.objects.get(id=user_id)


def get_user_by_username(username: str):
    from extensions.users.backend.models import User

    return User.objects.get(username=username)


def list_users_by_usernames(usernames) -> list:
    from extensions.users.backend.models import User

    normalized_names = _normalize_usernames(usernames)
    if not normalized_names:
        return []

    users_by_name = {
        user.username: user
        for user in User.objects.filter(username__in=normalized_names, is_active=True)
    }
    return [users_by_name[name] for name in normalized_names if name in users_by_name]


def get_username_id_map(usernames) -> dict[str, int]:
    from extensions.users.backend.models import User

    normalized_names = _normalize_usernames(usernames)
    if not normalized_names:
        return {}

    return {
        item["username"]: item["id"]
        for item in User.objects.filter(username__in=normalized_names, is_active=True).values("id", "username")
    }


def increment_discussion_count(user_id: int, delta: int) -> int:
    from django.db.models import F
    from extensions.users.backend.models import User

    normalized_user_id = int(user_id or 0)
    normalized_delta = int(delta or 0)
    if normalized_user_id <= 0 or normalized_delta == 0:
        return 0
    return User.objects.filter(id=normalized_user_id).update(
        discussion_count=F("discussion_count") + normalized_delta,
    )


def increment_comment_count(user_id: int, delta: int) -> int:
    from django.db.models import F
    from extensions.users.backend.models import User

    normalized_user_id = int(user_id or 0)
    normalized_delta = int(delta or 0)
    if normalized_user_id <= 0 or normalized_delta == 0:
        return 0
    return User.objects.filter(id=normalized_user_id).update(
        comment_count=F("comment_count") + normalized_delta,
    )


def apply_comment_count_deltas(deltas: dict | None) -> int:
    updated = 0
    for raw_user_id, raw_delta in dict(deltas or {}).items():
        try:
            user_id = int(raw_user_id)
            delta = int(raw_delta or 0)
        except (TypeError, ValueError):
            continue
        updated += increment_comment_count(user_id, delta)
    return updated


def serialize_user(user, *, resource: str = "user_detail", context: dict | None = None) -> dict | None:
    if not user:
        return None

    from apps.core.extensions.runtime import get_runtime_resource_registry

    return get_runtime_resource_registry().serialize(
        str(resource or "user_detail"),
        user,
        context or {},
    )


def serialize_users_by_ids(user_ids, *, limit: int = 50) -> list[dict]:
    from extensions.users.backend.models import User

    normalized_ids = []
    seen = set()
    for raw_id in user_ids or []:
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        normalized_ids.append(user_id)
        if len(normalized_ids) >= int(limit or 50):
            break

    if not normalized_ids:
        return []

    users = User.objects.filter(id__in=normalized_ids, is_active=True).only(
        "id",
        "username",
        "display_name",
        "avatar_url",
    )
    users_by_id = {user.id: user for user in users}
    return [
        {
            "id": users_by_id[user_id].id,
            "username": users_by_id[user_id].username,
            "display_name": users_by_id[user_id].display_name,
            "avatar_url": users_by_id[user_id].avatar_url,
        }
        for user_id in normalized_ids
        if user_id in users_by_id
    ]


def _normalize_usernames(usernames) -> list[str]:
    normalized_names = []
    seen = set()
    for raw_name in usernames or []:
        username = str(raw_name or "").strip()
        if not username or username in seen:
            continue
        seen.add(username)
        normalized_names.append(username)
    return normalized_names


def ensure_admin_user(*, username: str, email: str, password: str) -> dict:
    from extensions.users.backend.models import Group, User

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": True,
            "is_superuser": True,
            "is_email_confirmed": True,
        },
    )

    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.is_email_confirmed = True
    user.set_password(password)
    user.save()

    admin_group = Group.objects.filter(name="Admin").first()
    if admin_group is not None:
        user.user_groups.add(admin_group)

    return {
        "user": user,
        "created": bool(created),
        "username": user.username,
    }

