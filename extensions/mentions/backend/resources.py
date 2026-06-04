from __future__ import annotations

from django.db.models import Prefetch

from apps.core.forum_resources_users import serialize_user_summary
from apps.posts.models import PostMentionsUser


def post_mentions_preload_resolver(context: dict):
    return (), (
        Prefetch(
            "mentions",
            queryset=PostMentionsUser.objects.select_related("mentions_user"),
            to_attr="mentions_user_links_cache",
        ),
    )


def resolve_post_mentions_users(post, context: dict) -> list[dict]:
    links = getattr(post, "mentions_user_links_cache", None)
    if links is None:
        links = PostMentionsUser.objects.filter(post_id=post.id).select_related("mentions_user")

    return [
        user_payload
        for user_payload in (
            serialize_user_summary(getattr(link, "mentions_user", None))
            for link in links
        )
        if user_payload is not None
    ]
