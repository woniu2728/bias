from __future__ import annotations

from django.db.models import Prefetch

from apps.posts.models import PostLike


def post_like_preload_resolver(context: dict):
    user = context.get("user")
    prefetches = [
        Prefetch(
            "likes",
            queryset=PostLike.objects.select_related("user"),
            to_attr="likes_cache",
        )
    ]
    if user and user.is_authenticated:
        prefetches.append(
            Prefetch(
                "likes",
                queryset=PostLike.objects.filter(user=user).select_related("user"),
                to_attr="viewer_likes_cache",
            )
        )
    return (), tuple(prefetches)


def resolve_post_like_count(post, context: dict) -> int:
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
