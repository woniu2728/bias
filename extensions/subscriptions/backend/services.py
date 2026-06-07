from typing import Optional

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.core.visibility import can_view_model_instance
from extensions.discussions.backend.models import Discussion, DiscussionUser
from apps.users.models import User


def get_subscription_state(discussion: Discussion, user: Optional[User]) -> bool:
    if not user or not user.is_authenticated:
        return False

    return DiscussionUser.objects.filter(
        discussion=discussion,
        user=user,
        is_subscribed=True,
    ).exists()


def set_subscription_state(discussion_id: int, user: User, subscribed: bool) -> bool:
    discussion = Discussion.objects.get(id=discussion_id)
    if not can_view_model_instance(Discussion, discussion, user=user, ability="view"):
        raise PermissionDenied("没有权限查看此讨论")

    state, _ = DiscussionUser.objects.get_or_create(
        discussion=discussion,
        user=user,
        defaults={
            "last_read_at": timezone.now(),
            "last_read_post_number": discussion.last_post_number or 0,
        },
    )
    if state.is_subscribed == subscribed:
        return False
    state.is_subscribed = subscribed
    state.save(update_fields=["is_subscribed"])
    return True
