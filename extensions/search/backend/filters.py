from __future__ import annotations

from datetime import datetime

from django.db import models


def parse_author_search_filter(token: str) -> str | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "author":
        return None

    normalized = value.strip()
    return normalized or None


def apply_discussion_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def apply_post_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def parse_sticky_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="sticky")


def apply_discussion_sticky_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_sticky=enabled)


def parse_locked_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="locked")


def apply_discussion_locked_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_locked=enabled)


def parse_unread_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="unread")


def apply_discussion_unread_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )


def parse_created_month_search_filter(token: str) -> tuple[int, int] | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "created":
        return None

    normalized = value.strip()
    try:
        parsed = datetime.strptime(normalized, "%Y-%m")
    except ValueError:
        return None

    return parsed.year, parsed.month


def apply_discussion_created_month_search_filter(queryset, year_month: tuple[int, int], context: dict):
    year, month = year_month
    return queryset.filter(created_at__year=year, created_at__month=month)


def apply_post_created_month_search_filter(queryset, year_month: tuple[int, int], context: dict):
    year, month = year_month
    return queryset.filter(created_at__year=year, created_at__month=month)


def _parse_is_search_filter(token: str, expected: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "is":
        return None

    return True if value.strip().lower() == expected else None
