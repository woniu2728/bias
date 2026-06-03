from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.utils import timezone

from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.runtime_access import evaluate_runtime_model_policy
from apps.core.forum_events import (
    PostCreatedEvent,
    PostDeletedEvent,
    PostHiddenEvent,
    PostResubmittedEvent,
)
from apps.discussions.models import Discussion, DiscussionUser
from apps.core.forum_events import UserMentionedEvent
from apps.posts.models import Post, PostFlag, PostLike, PostMentionsUser
from apps.users.models import User
from apps.users.services import UserService


def create_post(
    discussion_id: int,
    content: str,
    user: User,
    *,
    reply_to_post_id=None,
    default_post_type,
    can_reply_in_discussion,
    render_markdown_cb,
    process_mentions_cb,
    lock_discussion_for_post_number_cb,
    create_post_with_sequential_number_cb,
) -> Post:
    UserService.ensure_not_suspended(user, "回复讨论")
    UserService.ensure_email_confirmed(user, "回复讨论")
    UserService.ensure_forum_permission(user, "discussion.reply", "没有权限回复讨论")
    requires_approval = UserService.requires_content_approval(user, "replyWithoutApproval")

    discussion = can_reply_in_discussion(discussion_id, user)

    with transaction.atomic():
        discussion = lock_discussion_for_post_number_cb(discussion.id)
        discussion = can_reply_in_discussion(discussion.id, user, discussion=discussion)

        reply_target = None
        if reply_to_post_id:
            reply_target = Post.objects.filter(
                id=reply_to_post_id,
                discussion=discussion,
            ).select_related("user").first()

        post = create_post_with_sequential_number_cb(
            discussion=discussion,
            user=user,
            content=content,
            content_html=render_markdown_cb(content),
            type=default_post_type,
            approval_status=Post.APPROVAL_PENDING if requires_approval else Post.APPROVAL_APPROVED,
            approved_at=None if requires_approval else timezone.now(),
            approved_by=None if requires_approval else user,
        )

        if not requires_approval:
            discussion.comment_count = F("comment_count") + 1
            discussion.last_posted_at = timezone.now()
            discussion.last_posted_user = user
            discussion.last_post_id = post.id
            discussion.last_post_number = post.number
            discussion.save()

            user.comment_count = F("comment_count") + 1
            user.save(update_fields=["comment_count"])

            state_defaults = {
                "last_read_at": timezone.now(),
                "last_read_post_number": post.number,
            }
            DiscussionUser.objects.update_or_create(
                discussion=discussion,
                user=user,
                defaults=state_defaults,
            )

            process_mentions_cb(post, content)

            dispatch_forum_event_after_commit(
                PostCreatedEvent(
                    post_id=post.id,
                    discussion_id=discussion.id,
                    actor_user_id=user.id,
                    reply_to_post_id=reply_target.id if reply_target else None,
                    is_approved=True,
                )
            )

        return post


def validate_replyable_discussion(
    discussion_id: int,
    user: User,
    *,
    discussion=None,
) -> Discussion:
    if discussion is None:
        try:
            discussion = Discussion.objects.get(id=discussion_id)
        except Discussion.DoesNotExist:
            raise ValueError("讨论不存在")

    if discussion.approval_status != Discussion.APPROVAL_APPROVED and not user.is_staff:
        raise ValueError("讨论正在审核中，暂时无法回复")

    if discussion.is_locked and not user.is_staff:
        raise ValueError("讨论已锁定，无法回复")

    if evaluate_runtime_model_policy(
        "reply",
        user=user,
        model=discussion,
        default=True,
        discussion=discussion,
    ) is False:
        raise PermissionDenied("没有权限回复此讨论")
    return discussion


def get_post_list(
    discussion_id: int,
    *,
    page: int = 1,
    limit: int = 20,
    user=None,
    preload=None,
    stream_post_types,
    annotate_flag_state_cb,
    apply_visibility_filters_cb,
):
    queryset = Post.objects.filter(
        discussion_id=discussion_id,
        type__in=stream_post_types,
    ).annotate(
        like_count=Count("likes", distinct=True)
    )
    if preload is not None:
        queryset = preload(queryset)
    queryset = annotate_flag_state_cb(queryset, user)
    queryset = apply_visibility_filters_cb(queryset, user)
    queryset = queryset.order_by("number")

    total = queryset.count()
    offset = (page - 1) * limit
    posts = list(queryset[offset:offset + limit])

    _annotate_like_state(posts, user)
    return posts, total


def get_post_by_id(
    post_id: int,
    *,
    user=None,
    preload=None,
    can_view_post_cb,
    annotate_flag_state_cb,
):
    try:
        post = Post.objects.select_related("discussion").annotate(
            like_count=Count("likes", distinct=True)
        )
        if preload is not None:
            post = preload(post)
        post = annotate_flag_state_cb(post, user).get(id=post_id)
        if not can_view_post_cb(post, user):
            return None

        if user and user.is_authenticated:
            post.is_liked = PostLike.objects.filter(post=post, user=user).exists()
        else:
            post.is_liked = False
        return post
    except Post.DoesNotExist:
        return None


def update_post(
    post_id: int,
    user: User,
    content: str,
    *,
    can_edit_post_cb,
    render_markdown_cb,
    process_mentions_cb,
) -> Post:
    UserService.ensure_not_suspended(user, "编辑帖子")
    post = Post.objects.get(id=post_id)

    if not can_edit_post_cb(post, user):
        raise PermissionDenied("没有权限编辑此帖子")

    with transaction.atomic():
        post.content = content
        post.content_html = render_markdown_cb(content)
        post.edited_at = timezone.now()
        post.edited_user = user
        update_fields = ["content", "content_html", "edited_at", "edited_user"]
        previous_approval_status = None

        if (
            post.approval_status == Post.APPROVAL_REJECTED
            and not user.is_staff
            and post.user_id == user.id
        ):
            previous_approval_status = post.approval_status
            post.approval_status = Post.APPROVAL_PENDING
            post.approved_at = None
            post.approved_by = None
            post.approval_note = ""
            post.hidden_at = None
            post.hidden_user = None
            update_fields.extend([
                "approval_status",
                "approved_at",
                "approved_by",
                "approval_note",
                "hidden_at",
                "hidden_user",
            ])

        post.save(update_fields=update_fields)

        PostMentionsUser.objects.filter(post=post).delete()
        process_mentions_cb(post, content)

        if previous_approval_status:
            dispatch_forum_event_after_commit(
                PostResubmittedEvent(
                    post_id=post.id,
                    discussion_id=post.discussion_id,
                    actor_user_id=user.id,
                    previous_status=previous_approval_status,
                )
            )

        return post


def delete_post(
    post_id: int,
    user: User,
    *,
    can_delete_post_cb,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> bool:
    UserService.ensure_not_suspended(user, "删除帖子")
    post = Post.objects.select_related("discussion").get(id=post_id)

    if not can_delete_post_cb(post, user):
        raise PermissionDenied("没有权限删除此帖子")
    if post.number == 1:
        raise ValueError("不能删除第一条帖子")

    with transaction.atomic():
        discussion = post.discussion
        deleted_post_id = post.id
        deleted_post_number = post.number
        deleted_discussion_id = post.discussion_id
        deleted_flag_ids = tuple(
            PostFlag.objects.filter(post_id=post.id).values_list("id", flat=True)
        )
        counted_post = (
            post.approval_status == Post.APPROVAL_APPROVED
            and post.type in discussion_counted_post_types
        )

        post.delete()

        if counted_post:
            refresh_discussion_approved_stats_cb(discussion)
            if post.user and post.type in user_counted_post_types:
                post.user.comment_count = F("comment_count") - 1
                post.user.save(update_fields=["comment_count"])

        dispatch_forum_event_after_commit(
            PostDeletedEvent(
                post_id=deleted_post_id,
                discussion_id=deleted_discussion_id,
                actor_user_id=user.id,
                post_number=deleted_post_number,
                flag_ids=deleted_flag_ids,
            )
        )

    return True


def set_hidden_state(
    post: Post,
    admin_user: User,
    is_hidden: bool,
    *,
    discussion_counted_post_types,
    user_counted_post_types,
    refresh_discussion_approved_stats_cb,
) -> Post:
    if not admin_user.is_staff:
        raise PermissionDenied("只有管理员可以隐藏或恢复回复")
    if post.number == 1:
        raise ValueError("不能直接隐藏首贴，请改为隐藏讨论")

    was_hidden = post.hidden_at is not None
    if was_hidden == is_hidden:
        return post

    should_adjust_counts = (
        post.approval_status == Post.APPROVAL_APPROVED
        and post.type in discussion_counted_post_types
    )
    hidden_at = timezone.now() if is_hidden else None

    with transaction.atomic():
        post.hidden_at = hidden_at
        post.hidden_user = admin_user if is_hidden else None
        post.save(update_fields=["hidden_at", "hidden_user"])

        if should_adjust_counts:
            refresh_discussion_approved_stats_cb(post.discussion)
            if post.user and post.type in user_counted_post_types:
                delta = -1 if is_hidden else 1
                post.user.comment_count = F("comment_count") + delta
                post.user.save(update_fields=["comment_count"])

        dispatch_forum_event_after_commit(
            PostHiddenEvent(
                post_id=post.id,
                discussion_id=post.discussion_id,
                actor_user_id=admin_user.id,
                post_number=post.number,
                is_hidden=is_hidden,
            )
        )

    post.refresh_from_db()
    return post


def refresh_discussion_approved_stats(
    discussion: Discussion,
    *,
    discussion_counted_post_types,
):
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
    return discussion


def _annotate_like_state(posts, user) -> None:
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
        return

    for post in posts:
        post.is_liked = False


def process_mentions(post: Post, content: str, *, extract_mentions_cb) -> None:
    mentions = extract_mentions_cb(content)
    if not mentions:
        return

    mentioned_users = User.objects.filter(username__in=mentions)
    for mentioned_user in mentioned_users:
        PostMentionsUser.objects.get_or_create(
            post=post,
            mentions_user=mentioned_user,
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


def is_post_number_conflict(exc: IntegrityError) -> bool:
    message = str(exc).lower()
    return (
        "unique" in message
        and "post" in message
        and "number" in message
    )


def create_post_with_sequential_number(*, attempts: int, allocate_next_post_number_cb, **post_kwargs) -> Post:
    last_error = None

    for attempt in range(attempts):
        next_number = allocate_next_post_number_cb(post_kwargs["discussion"])
        try:
            return Post.objects.create(
                **post_kwargs,
                number=next_number,
            )
        except IntegrityError as exc:
            if not is_post_number_conflict(exc):
                raise
            last_error = exc
            if attempt == attempts - 1:
                raise

    if last_error:
        raise last_error
    raise IntegrityError("帖子楼层分配失败")
