from typing import Optional

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.forum_events import (
    DiscussionTagStatsRefreshEvent,
    PostApprovedEvent,
    PostLikedEvent,
    PostRejectedEvent,
    UserMentionedEvent,
)
from apps.core.mentions import extract_mentioned_usernames
from apps.discussions.models import Discussion, DiscussionUser
from apps.posts.models import Post, PostFlag, PostLike, PostMentionsUser
from apps.tags.services import TagService
from apps.users.models import User
from apps.users.preferences import get_user_preference_value
from apps.users.services import UserService


def like_post(post_id: int, user: User, *, can_view_post) -> bool:
    UserService.ensure_not_suspended(user, "点赞帖子")
    post = Post.objects.get(id=post_id)
    if not can_view_post(post, user):
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


def unlike_post(post_id: int, user: User, *, can_view_post) -> bool:
    UserService.ensure_not_suspended(user, "点赞帖子")
    post = Post.objects.get(id=post_id)
    if not can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")

    deleted_count, _ = PostLike.objects.filter(post=post, user=user).delete()
    if deleted_count == 0:
        raise ValueError("还没有点赞")
    return True


def report_post(post_id: int, user: User, reason: str, message: str = "", *, can_view_post) -> PostFlag:
    UserService.ensure_not_suspended(user, "举报帖子")
    post = Post.objects.select_related("user", "discussion").get(id=post_id)
    if not can_view_post(post, user):
        raise PermissionDenied("没有权限查看此帖子")

    if not user or not user.is_authenticated:
        raise PermissionDenied("请先登录")
    if post.user_id == user.id:
        raise ValueError("不能举报自己的帖子")
    if post.hidden_at is not None:
        raise ValueError("该帖子已被隐藏")

    try:
        existing = PostFlag.objects.get(
            post=post,
            user=user,
            status=PostFlag.STATUS_OPEN,
        )
        existing.reason = reason
        existing.message = message
        existing.save(update_fields=["reason", "message"])
        return existing
    except PostFlag.DoesNotExist:
        return PostFlag.objects.create(
            post=post,
            user=user,
            reason=reason,
            message=message,
        )


def get_flag_list(status: Optional[str] = None, page: int = 1, limit: int = 20):
    queryset = PostFlag.objects.select_related(
        "post",
        "post__discussion",
        "post__user",
        "user",
        "resolved_by",
    )

    if status:
        queryset = queryset.filter(status=status)

    total = queryset.count()
    offset = (page - 1) * limit
    return list(queryset[offset:offset + limit]), total


def resolve_flag(flag_id: int, admin_user: User, status: str, resolution_note: str = "") -> PostFlag:
    if status not in {PostFlag.STATUS_RESOLVED, PostFlag.STATUS_IGNORED}:
        raise ValueError("无效的处理状态")

    flag = PostFlag.objects.select_related("post", "post__discussion", "user").get(id=flag_id)
    flag.status = status
    flag.resolution_note = resolution_note
    flag.resolved_by = admin_user
    flag.resolved_at = timezone.now()
    flag.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])
    return flag


def resolve_post_flags(post_id: int, admin_user: User, status: str, resolution_note: str = "") -> int:
    if not admin_user.is_staff:
        raise PermissionDenied("只有管理员可以处理举报")
    if status not in {PostFlag.STATUS_RESOLVED, PostFlag.STATUS_IGNORED}:
        raise ValueError("无效的处理状态")

    open_flags = list(PostFlag.objects.filter(post_id=post_id, status=PostFlag.STATUS_OPEN))
    if not open_flags:
        raise ValueError("当前帖子没有待处理举报")

    resolved_at = timezone.now()
    for flag in open_flags:
        flag.status = status
        flag.resolution_note = resolution_note
        flag.resolved_by = admin_user
        flag.resolved_at = resolved_at

    PostFlag.objects.bulk_update(
        open_flags,
        ["status", "resolution_note", "resolved_by", "resolved_at"],
    )
    return len(open_flags)


def refresh_discussion_approved_stats(discussion: Discussion, *, discussion_counted_post_types, user_counted_post_types):
    approved_posts = Post.objects.filter(
        discussion=discussion,
        type__in=discussion_counted_post_types,
        approval_status=Post.APPROVAL_APPROVED,
        hidden_at__isnull=True,
    ).order_by("number")

    approved_count = approved_posts.count()
    last_post = approved_posts.order_by("-number").select_related("user").first()

    discussion.comment_count = approved_count
    if last_post:
        discussion.last_post_id = last_post.id
        discussion.last_post_number = last_post.number
        discussion.last_posted_at = last_post.created_at
        discussion.last_posted_user = last_post.user
    else:
        discussion.last_post_id = None
        discussion.last_post_number = None
        discussion.last_posted_at = None
        discussion.last_posted_user = None

    discussion.save(update_fields=[
        "comment_count",
        "last_post_id",
        "last_post_number",
        "last_posted_at",
        "last_posted_user",
    ])
    dispatch_forum_event_after_commit(
        DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
    )
    return discussion


def process_mentions(post: Post, content: str):
    mentions = extract_mentioned_usernames(content)
    if not mentions:
        return

    mentioned_users = User.objects.filter(username__in=mentions)
    for mentioned_user in mentioned_users:
        PostMentionsUser.objects.get_or_create(
            post=post,
            mentions_user=mentioned_user
        )

        dispatch_forum_event_after_commit(
            UserMentionedEvent(
                post_id=post.id,
                discussion_id=post.discussion_id,
                actor_user_id=post.user_id,
                mentioned_user_id=mentioned_user.id,
                post_number=post.number,
            )
        )


def approve_post(
    post: Post,
    admin_user: User,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    process_mentions_cb,
    refresh_discussion_approved_stats_cb,
) -> Post:
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        now = timezone.now()
        post.approval_status = Post.APPROVAL_APPROVED
        post.approved_at = now
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = None
        post.hidden_user = None
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user"
        ])

        discussion = post.discussion
        if not was_counted:
            discussion.comment_count = F("comment_count") + 1
            if not discussion.last_post_number or post.number >= discussion.last_post_number:
                discussion.last_posted_at = now
                discussion.last_posted_user = post.user
                discussion.last_post_id = post.id
                discussion.last_post_number = post.number
            discussion.save()

            if post.user and post.type in user_counted_post_types:
                post.user.comment_count = F("comment_count") + 1
                post.user.save(update_fields=["comment_count"])
                follow_after_reply = get_user_preference_value(post.user, "follow_after_reply", fallback=False)
                approval_defaults = {
                    "last_read_at": now,
                    "last_read_post_number": post.number,
                }
                if follow_after_reply:
                    approval_defaults["is_subscribed"] = True
                DiscussionUser.objects.update_or_create(
                    discussion=discussion,
                    user=post.user,
                    defaults=approval_defaults,
                )

            process_mentions_cb(post, post.content)

            dispatch_forum_event_after_commit(
                PostApprovedEvent(
                    post_id=post.id,
                    discussion_id=discussion.id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                )
            )
        else:
            dispatch_forum_event_after_commit(
                DiscussionTagStatsRefreshEvent(discussion_id=discussion.id)
            )

    post.refresh_from_db()
    return post


def reject_post(
    post: Post,
    admin_user: User,
    note: str = "",
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    rejected_at = timezone.now()
    previous_status = post.approval_status
    was_counted = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.hidden_at is None
        and post.type in discussion_counted_post_types
    )

    with transaction.atomic():
        post.approval_status = Post.APPROVAL_REJECTED
        post.approved_at = rejected_at
        post.approved_by = admin_user
        post.approval_note = note
        post.hidden_at = rejected_at
        post.hidden_user = admin_user
        post.save(update_fields=[
            "approval_status", "approved_at", "approved_by", "approval_note", "hidden_at", "hidden_user"
        ])

        if was_counted:
            refresh_discussion_approved_stats_cb(post.discussion)
            if post.user and post.type in user_counted_post_types:
                post.user.comment_count = F("comment_count") - 1
                post.user.save(update_fields=["comment_count"])

        if previous_status != Post.APPROVAL_REJECTED:
            dispatch_forum_event_after_commit(
                PostRejectedEvent(
                    post_id=post.id,
                    discussion_id=post.discussion_id,
                    actor_user_id=post.user_id,
                    admin_user_id=admin_user.id,
                    note=note,
                    previous_status=previous_status,
                )
            )
    return post
