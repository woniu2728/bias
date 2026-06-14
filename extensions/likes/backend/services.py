from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from typing import Any

from apps.core.extensions.platform import AuthorizationPolicy
from apps.core.extensions.platform import dispatch_forum_event_after_commit
from apps.core.extensions.platform import evaluate_extension_policy
from apps.core.extensions.platform import get_extension_settings
from extensions.likes.backend.events import PostLikedEvent
from extensions.likes.backend.models import PostLike
from apps.core.extensions.runtime import (
    can_runtime_view_post,
    get_runtime_post_by_id,
)
from apps.core.extensions.runtime import (
    ensure_runtime_user_not_suspended,
)


def like_post(post_id: int, user: Any) -> bool:
    ensure_runtime_user_not_suspended(user, "点赞帖子")
    post = get_runtime_post_by_id(post_id, user=user, require_visible=True)
    if post.user_id == user.id and not can_like_own_post():
        raise ValueError("不能给自己的帖子点赞")
    if not evaluate_extension_policy("post.like", default=True, user=user, post=post):
        raise PermissionDenied("没有权限点赞此帖子")
    if PostLike.objects.filter(post=post, user=user).exists():
        raise ValueError("已经点赞过了")

    try:
        PostLike.objects.create(post=post, user=user)
    except IntegrityError:
        raise ValueError("已经点赞过了")

    dispatch_forum_event_after_commit(
        PostLikedEvent(
            post_id=post.id,
            discussion_id=post.discussion_id,
            actor_user_id=user.id,
            post_number=post.number,
        )
    )
    return True


def unlike_post(post_id: int, user: Any) -> bool:
    ensure_runtime_user_not_suspended(user, "点赞帖子")
    post = get_runtime_post_by_id(post_id, user=user, require_visible=True)

    deleted_count, _ = PostLike.objects.filter(post=post, user=user).delete()
    if deleted_count == 0:
        raise ValueError("还没有点赞")
    return True


def can_like_post(post: Any, user: Any) -> bool:
    if not _can_like_post_without_extension_policy(post, user):
        return False
    return bool(evaluate_extension_policy(
        "post.like",
        default=True,
        user=user,
        post=post,
    ))


def _can_like_post_without_extension_policy(post: Any, user: Any) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_suspended:
        return False
    if post.user_id == user.id and not can_like_own_post():
        return False
    return can_runtime_view_post(post, user)


def can_like_own_post() -> bool:
    return bool(get_extension_settings("likes").get("like_own_post", False))


class LikePostPolicy(AuthorizationPolicy):
    def can(self, user, ability, model, **context):
        if ability != "post.like":
            return None
        post = context.get("post") or model
        return _can_like_post_without_extension_policy(post, user) if post is not None else None


def resolve_post_can_like(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and can_like_post(post, user))
