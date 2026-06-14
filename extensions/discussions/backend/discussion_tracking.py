from __future__ import annotations

from typing import Any, List, Optional

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.utils import timezone

from apps.core.extensions.platform import can_view_model_instance
from extensions.discussions.backend.visibility import apply_discussion_visibility_scope
from extensions.discussions.backend.models import Discussion, DiscussionUser


def viewer_cache_identity(user: Optional[Any]) -> str:
    if user and user.is_authenticated:
        return f"user:{user.id}"
    return "guest"


def view_count_cache_key(discussion_id: int, user: Optional[Any]) -> str:
    return f"discussion.viewed.{discussion_id}.{viewer_cache_identity(user)}"


def view_count_pending_cache_key(discussion_id: int) -> str:
    return f"discussion.view_count.pending.{discussion_id}"


def view_count_flush_lock_cache_key(discussion_id: int) -> str:
    return f"discussion.view_count.flush_lock.{discussion_id}"


def record_view(
    discussion: Discussion,
    *,
    user: Optional[Any],
    throttle_seconds: int,
    cache_timeout: int,
    pending_ids_cache_key: str,
    flush_delay_seconds: int,
) -> bool:
    cache_key = view_count_cache_key(discussion.id, user)
    try:
        if cache.get(cache_key):
            return False
        cache.set(cache_key, True, throttle_seconds)
    except Exception:
        pass

    try:
        pending_count = increment_pending_view_count(
            discussion.id,
            cache_timeout=cache_timeout,
            pending_ids_cache_key=pending_ids_cache_key,
        )
        dispatch_view_count_flush(
            discussion.id,
            pending_count=pending_count,
            cache_timeout=cache_timeout,
            flush_delay_seconds=flush_delay_seconds,
        )
    except Exception:
        Discussion.objects.filter(id=discussion.id).update(view_count=F("view_count") + 1)

    discussion.view_count = (discussion.view_count or 0) + 1
    return True


def increment_pending_view_count(
    discussion_id: int,
    *,
    cache_timeout: int,
    pending_ids_cache_key: str,
) -> int:
    pending_key = view_count_pending_cache_key(discussion_id)
    cache.add(pending_key, 0, cache_timeout)
    pending_count = cache.incr(pending_key)
    remember_pending_view_discussion(
        discussion_id,
        cache_timeout=cache_timeout,
        pending_ids_cache_key=pending_ids_cache_key,
    )
    return int(pending_count or 0)


def remember_pending_view_discussion(
    discussion_id: int,
    *,
    cache_timeout: int,
    pending_ids_cache_key: str,
) -> None:
    pending_ids = cache.get(pending_ids_cache_key) or []
    if discussion_id not in pending_ids:
        pending_ids.append(discussion_id)
        cache.set(pending_ids_cache_key, pending_ids, cache_timeout)


def dispatch_view_count_flush(
    discussion_id: int,
    *,
    pending_count: int = 0,
    cache_timeout: int,
    flush_delay_seconds: int,
):
    from apps.core.extensions.platform import QueueService
    from extensions.discussions.backend.tasks import flush_discussion_view_count_task

    def fallback():
        return flush_pending_view_count(
            discussion_id,
            cache_timeout=cache_timeout,
            flush_delay_seconds=flush_delay_seconds,
        )

    if QueueService.should_enqueue():
        lock_key = view_count_flush_lock_cache_key(discussion_id)
        lock_timeout = flush_delay_seconds + 30
        if cache.add(lock_key, True, lock_timeout):
            return QueueService.dispatch_celery_task(
                flush_discussion_view_count_task,
                discussion_id,
                countdown=flush_delay_seconds,
                fallback=fallback,
            )
        return None

    return QueueService.dispatch_celery_task(
        flush_discussion_view_count_task,
        discussion_id,
        fallback=fallback,
    )


def flush_pending_view_count(
    discussion_id: int,
    *,
    cache_timeout: int,
    flush_delay_seconds: int,
) -> int:
    pending_key = view_count_pending_cache_key(discussion_id)
    lock_key = view_count_flush_lock_cache_key(discussion_id)
    cache.delete(lock_key)

    try:
        pending_count = int(cache.get(pending_key) or 0)
    except (TypeError, ValueError):
        pending_count = 0
    if pending_count <= 0:
        return 0

    try:
        remaining = cache.decr(pending_key, pending_count)
        if remaining <= 0:
            cache.delete(pending_key)
    except Exception:
        cache.delete(pending_key)
        remaining = 0

    Discussion.objects.filter(id=discussion_id).update(view_count=F("view_count") + pending_count)
    if remaining > 0:
        dispatch_view_count_flush(
            discussion_id,
            pending_count=remaining,
            cache_timeout=cache_timeout,
            flush_delay_seconds=flush_delay_seconds,
        )
    return pending_count


def flush_all_pending_view_counts(
    *,
    cache_timeout: int,
    pending_ids_cache_key: str,
    flush_delay_seconds: int,
) -> int:
    pending_ids = cache.get(pending_ids_cache_key) or []
    flushed_count = 0
    active_ids = []
    for discussion_id in pending_ids:
        normalized_id = int(discussion_id)
        flushed_count += flush_pending_view_count(
            normalized_id,
            cache_timeout=cache_timeout,
            flush_delay_seconds=flush_delay_seconds,
        )
        if cache.get(view_count_pending_cache_key(normalized_id)):
            active_ids.append(normalized_id)

    if active_ids:
        cache.set(pending_ids_cache_key, active_ids, cache_timeout)
    else:
        cache.delete(pending_ids_cache_key)
    return flushed_count


def can_view_discussion(discussion: Discussion, user: Optional[Any]) -> bool:
    return can_view_model_instance(Discussion, discussion, user=user, ability="view")


def apply_visibility_filters(queryset, user: Optional[Any] = None):
    return apply_discussion_visibility_scope(queryset, user)


def attach_user_read_state(discussions: List[Discussion], user: Optional[Any]) -> None:
    if not discussions:
        return

    if not user or not user.is_authenticated:
        for discussion in discussions:
            discussion.is_subscribed = False
            discussion.last_read_at = None
            discussion.last_read_post_number = 0
            discussion.unread_count = 0
            discussion.is_unread = False
        return

    states = {
        state.discussion_id: state
        for state in DiscussionUser.objects.filter(
            user=user,
            discussion_id__in=[discussion.id for discussion in discussions],
        )
    }
    marked_all_as_read_at = getattr(user, "marked_all_as_read_at", None)

    for discussion in discussions:
        state = states.get(discussion.id)
        last_read_at = state.last_read_at if state else None
        last_read_post_number = state.last_read_post_number if state else 0

        if (
            marked_all_as_read_at
            and discussion.last_posted_at
            and discussion.last_posted_at <= marked_all_as_read_at
        ):
            last_read_at = marked_all_as_read_at
            last_read_post_number = max(last_read_post_number, discussion.last_post_number or 0)

        discussion.is_subscribed = bool(state and state.is_subscribed)
        discussion.last_read_at = last_read_at
        discussion.last_read_post_number = last_read_post_number
        discussion.unread_count = max((discussion.last_post_number or 0) - last_read_post_number, 0)
        discussion.is_unread = discussion.unread_count > 0


def mark_all_as_read(user: Any):
    now = timezone.now()
    user.marked_all_as_read_at = now
    user.save(update_fields=["marked_all_as_read_at"])
    return now


def update_read_state(discussion_id: int, user: Any, last_read_post_number: int) -> DiscussionUser:
    discussion = Discussion.objects.get(id=discussion_id)
    if not can_view_discussion(discussion, user):
        raise PermissionDenied("没有权限查看此讨论")

    clamped_number = max(1, min(last_read_post_number, discussion.last_post_number or 1))
    state, _ = DiscussionUser.objects.get_or_create(
        discussion=discussion,
        user=user,
        defaults={
            "last_read_at": timezone.now(),
            "last_read_post_number": clamped_number,
        },
    )

    next_number = max(state.last_read_post_number, clamped_number)
    update_fields = []
    if next_number != state.last_read_post_number:
        state.last_read_post_number = next_number
        update_fields.append("last_read_post_number")

    now = timezone.now()
    if not state.last_read_at or next_number >= state.last_read_post_number:
        state.last_read_at = now
        update_fields.append("last_read_at")

    if update_fields:
        state.save(update_fields=update_fields)

    return state
