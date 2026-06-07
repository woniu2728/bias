from __future__ import annotations

from django.db import models


def apply_discussion_latest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-last_posted_at", "-id")


def apply_discussion_top_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-comment_count", "-view_count", "-last_posted_at", "-id")


def apply_discussion_oldest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "created_at", "id")


def apply_discussion_newest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-created_at", "-id")


def apply_discussion_unanswered_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "comment_count", "-created_at", "-id")


def apply_all_discussion_list_filter(queryset, context: dict):
    return queryset


def apply_my_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user=user)


def apply_unread_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )
