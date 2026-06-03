from dataclasses import dataclass
from math import ceil
from typing import List, Optional

from django.db.models import Count, Exists, OuterRef, Prefetch, Q

from apps.core.visibility import apply_post_visibility_scope, can_view_model_instance
from apps.posts.models import Post, PostFlag, PostLike
from apps.users.models import User


@dataclass
class PostStreamWindow:
    posts: List[Post]
    total: int
    page: int
    limit: int
    current_start: int
    current_end: int
    has_previous: bool
    has_more: bool


def annotate_flag_state(queryset, user: Optional[User] = None):
    if user and user.is_authenticated:
        queryset = queryset.annotate(
            viewer_has_open_flag=Exists(
                PostFlag.objects.filter(
                    post=OuterRef("pk"),
                    user=user,
                    status=PostFlag.STATUS_OPEN,
                )
            )
        )

    if user and user.is_staff:
        queryset = queryset.annotate(
            open_flag_count=Count(
                "flags",
                filter=Q(flags__status=PostFlag.STATUS_OPEN),
                distinct=True,
            )
        ).prefetch_related(
            Prefetch(
                "flags",
                queryset=PostFlag.objects.filter(status=PostFlag.STATUS_OPEN).select_related(
                    "post",
                    "post__discussion",
                    "post__user",
                    "user",
                    "resolved_by",
                ),
                to_attr="open_flags_cache",
            )
        )

    return queryset


def can_view_post(post: Post, user: Optional[User]) -> bool:
    return can_view_model_instance(Post, post, user=user, ability="view")


def apply_visibility_filters(queryset, user: Optional[User] = None):
    return apply_post_visibility_scope(queryset, user)


def build_visible_post_queryset(
    discussion_id: int,
    *,
    stream_post_types,
    user: Optional[User] = None,
    preload=None,
):
    queryset = Post.objects.filter(
        discussion_id=discussion_id,
        type__in=stream_post_types,
    ).annotate(
        like_count=Count("likes", distinct=True)
    )
    if preload is not None:
        queryset = preload(queryset)
    queryset = annotate_flag_state(queryset, user)
    queryset = apply_visibility_filters(queryset, user)
    return queryset.order_by("number")


def attach_like_state(posts: List[Post], user: Optional[User]) -> None:
    if user and user.is_authenticated:
        post_ids = [post.id for post in posts]
        liked_post_ids = set(
            PostLike.objects.filter(
                post_id__in=post_ids,
                user=user,
            ).values_list("post_id", flat=True)
        )
        for post in posts:
            post.is_liked = post.id in liked_post_ids
    else:
        for post in posts:
            post.is_liked = False


def get_post_window(
    discussion_id: int,
    *,
    stream_post_types,
    limit: int = 20,
    page: int = 1,
    near: Optional[int] = None,
    before: Optional[int] = None,
    after: Optional[int] = None,
    user: Optional[User] = None,
    preload=None,
) -> PostStreamWindow:
    queryset = build_visible_post_queryset(
        discussion_id=discussion_id,
        stream_post_types=stream_post_types,
        user=user,
        preload=preload,
    )
    total = queryset.count()

    if total <= 0:
        return PostStreamWindow(
            posts=[],
            total=0,
            page=1,
            limit=limit,
            current_start=0,
            current_end=0,
            has_previous=False,
            has_more=False,
        )

    mode_count = sum(1 for value in (near, before, after) if value is not None)
    if mode_count > 1:
        raise ValueError("near、before、after 只能传一个")

    if near is not None:
        posts = list(queryset.filter(number__gte=near).order_by("number")[:limit])
        if not posts:
            posts = list(queryset.order_by("-number")[:limit])
            posts.reverse()
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
    elif before is not None:
        posts = list(queryset.filter(number__lt=before).order_by("-number")[:limit])
        posts.reverse()
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
    elif after is not None:
        posts = list(queryset.filter(number__gt=after).order_by("number")[:limit])
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0
    else:
        offset = (page - 1) * limit
        posts = list(queryset[offset:offset + limit])
        current_start = posts[0].number if posts else 0
        current_end = posts[-1].number if posts else 0

    attach_like_state(posts, user)

    has_previous = queryset.filter(number__lt=current_start).exists() if current_start else False
    has_more = queryset.filter(number__gt=current_end).exists() if current_end else False
    resolved_page = page
    if current_end:
        resolved_position = queryset.filter(number__lte=current_end).count()
        resolved_page = max(1, ceil(resolved_position / limit))

    return PostStreamWindow(
        posts=posts,
        total=total,
        page=resolved_page,
        limit=limit,
        current_start=current_start,
        current_end=current_end,
        has_previous=has_previous,
        has_more=has_more,
    )


def get_page_for_near_post(
    discussion_id: int,
    near: int,
    *,
    stream_post_types,
    limit: int = 20,
    user: Optional[User] = None,
) -> int:
    queryset = Post.objects.filter(
        discussion_id=discussion_id,
        number__lte=near,
        type__in=stream_post_types,
    )

    queryset = apply_visibility_filters(queryset, user)

    position = queryset.count()
    if position <= 0:
        return 1

    return max(1, ceil(position / limit))
