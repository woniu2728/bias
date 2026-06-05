from __future__ import annotations

from django.db.models import Prefetch

from apps.posts.models import PostMentionsUser


def post_mentions_preload_resolver(context: dict):
    return (), (
        Prefetch(
            "mentions",
            queryset=PostMentionsUser.objects.select_related("mentions_user"),
            to_attr="mentions_user_links_cache",
        ),
    )


def resolve_post_mentions_user_models(post, context: dict | None = None) -> list:
    links = getattr(post, "mentions_user_links_cache", None)
    if links is None:
        links = PostMentionsUser.objects.filter(post_id=post.id).select_related("mentions_user")

    return [
        user
        for user in (getattr(link, "mentions_user", None) for link in links)
        if user is not None
    ]
