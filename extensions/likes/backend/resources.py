from __future__ import annotations

from django.db.models import Count, Prefetch

from apps.core.extensions.runtime import serialize_runtime_user
from extensions.likes.backend.models import PostLike


def post_like_preload_resolver(context: dict):
    prefetches = []
    user = context.get("user")
    if user and user.is_authenticated:
        prefetches.append(
            Prefetch(
                "likes",
                queryset=PostLike.objects.filter(user=user).select_related("user"),
                to_attr="viewer_likes_cache",
            )
        )
    return (), tuple(prefetches)


def post_likes_relationship_preload_resolver(context: dict):
    return (), (
        Prefetch(
            "likes",
            queryset=PostLike.objects.select_related("user"),
            to_attr="likes_cache",
        ),
    )


def post_like_count_annotate_resolver(context: dict) -> dict:
    return {"likes_count": Count("likes", distinct=True)}


def resolve_post_like_count(post, context: dict) -> int:
    annotated_count = getattr(post, "likes_count", None)
    if annotated_count is not None:
        return int(annotated_count or 0)
    cached = getattr(post, "likes_cache", None)
    if cached is not None:
        return len(cached)
    return PostLike.objects.filter(post_id=post.id).count()


def resolve_post_is_liked(post, context: dict) -> bool:
    cached = getattr(post, "viewer_likes_cache", None)
    if cached is not None:
        return bool(cached)
    user = context.get("user")
    if not user or not user.is_authenticated:
        return False
    return PostLike.objects.filter(post_id=post.id, user=user).exists()


def resolve_post_likes(post, context: dict) -> list[dict]:
    cached = getattr(post, "likes_cache", None)
    likes = cached if cached is not None else PostLike.objects.filter(post_id=post.id).select_related("user")
    return [
        serialize_runtime_user(like.user, resource="post_user", context=context)
        for like in likes
        if getattr(like, "user", None)
    ]

