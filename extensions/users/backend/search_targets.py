from __future__ import annotations


def user_search_target_provider() -> dict:
    from extensions.users.backend.models import User

    return {
        "model": User,
    }
