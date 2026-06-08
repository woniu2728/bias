from __future__ import annotations


def user_model_provider() -> dict:
    return {
        "get_by_id": get_user_by_id,
        "serialize_many_by_ids": serialize_users_by_ids,
        "ensure_admin": ensure_admin_user,
    }


def get_user_by_id(user_id):
    from extensions.users.backend.models import User

    return User.objects.get(id=user_id)


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
