from django.core.exceptions import PermissionDenied
from django.db import IntegrityError

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.policy_runtime_service import evaluate_extension_policy
from apps.core.forum_events import PostLikedEvent
from apps.posts import post_query_service
from apps.posts.models import Post, PostLike
from apps.users.models import User
from apps.users.services import UserService


def like_post(post_id: int, user: User) -> bool:
    UserService.ensure_not_suspended(user, "点赞帖子")
    post = Post.objects.get(id=post_id)
    if not post_query_service.can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")
    if post.user_id == user.id:
        raise ValueError("不能给自己的帖子点赞")
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


def unlike_post(post_id: int, user: User) -> bool:
    UserService.ensure_not_suspended(user, "点赞帖子")
    post = Post.objects.get(id=post_id)
    if not post_query_service.can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")

    deleted_count, _ = PostLike.objects.filter(post=post, user=user).delete()
    if deleted_count == 0:
        raise ValueError("还没有点赞")
    return True


def can_like_post(post: Post, user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_suspended:
        return False
    if post.user_id == user.id:
        return False
    return bool(evaluate_extension_policy(
        "post.like",
        default=True,
        user=user,
        post=post,
    ))


def resolve_post_can_like(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and can_like_post(post, user))
