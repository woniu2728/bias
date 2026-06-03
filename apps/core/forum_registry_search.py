from __future__ import annotations

from datetime import datetime

from django.db import models


def _parse_author_search_filter(token: str) -> str | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "author":
        return None

    normalized = value.strip()
    return normalized or None


def _apply_discussion_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def _apply_post_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def _parse_sticky_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="sticky")


def _apply_discussion_sticky_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_sticky=enabled)


def _parse_locked_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="locked")


def _apply_discussion_locked_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_locked=enabled)


def _parse_following_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="following")


def _apply_discussion_following_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)


def _parse_unread_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="unread")


def _apply_discussion_unread_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )


def _parse_mentioned_me_search_filter(token: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "mentioned":
        return None

    return True if value.strip().lower() == "me" else None


def _apply_post_mentioned_me_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(mentions__mentions_user=user)


def _parse_created_month_search_filter(token: str) -> tuple[int, int] | None:
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


def _apply_discussion_created_month_search_filter(queryset, year_month: tuple[int, int], context: dict):
    year, month = year_month
    return queryset.filter(created_at__year=year, created_at__month=month)


def _apply_post_created_month_search_filter(queryset, year_month: tuple[int, int], context: dict):
    year, month = year_month
    return queryset.filter(created_at__year=year, created_at__month=month)


def _apply_discussion_latest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-last_posted_at", "-id")


def _apply_discussion_top_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-comment_count", "-view_count", "-last_posted_at", "-id")


def _apply_discussion_oldest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "created_at", "id")


def _apply_discussion_newest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-created_at", "-id")


def _apply_discussion_unanswered_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "comment_count", "-created_at", "-id")


def _apply_all_discussion_list_filter(queryset, context: dict):
    return queryset


def _apply_following_discussion_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)


def _apply_my_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user=user)


def _apply_unread_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )


def _parse_is_search_filter(token: str, expected: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "is":
        return None

    return True if value.strip().lower() == expected else None
