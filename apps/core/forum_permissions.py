from __future__ import annotations

from typing import Any


_forum_permission_checkers: dict[str, Any] = {}


def register_forum_permission_checker(key: str, checker) -> None:
    normalized = str(key or "").strip()
    if not normalized or not callable(checker):
        return
    _forum_permission_checkers[normalized] = checker


def clear_forum_permission_checkers() -> None:
    _forum_permission_checkers.clear()


def iter_forum_permission_checkers():
    return tuple(_forum_permission_checkers.values())


def has_forum_permission(user: Any, permission_names) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    normalized_permissions = _normalize_permission_names(permission_names)
    if not normalized_permissions:
        return False

    _ensure_forum_permission_checkers_bootstrapped()
    for checker in iter_forum_permission_checkers():
        result = checker(user, normalized_permissions)
        if result is True:
            return True
    return False


def _normalize_permission_names(permission_names) -> tuple[str, ...]:
    if isinstance(permission_names, str):
        permission_names = (permission_names,)
    try:
        iterator = iter(permission_names)
    except TypeError:
        iterator = iter((permission_names,))
    return tuple(
        normalized
        for permission in iterator
        if (normalized := str(permission or "").strip())
    )


def _ensure_forum_permission_checkers_bootstrapped() -> None:
    if _forum_permission_checkers:
        return
    try:
        from apps.core.extensions.bootstrap import get_extension_application

        get_extension_application(force=True)
    except Exception:
        return
