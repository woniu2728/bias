from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.forum_events import PostFlagsDeletedEvent
from extensions.flags.backend.models import PostFlag


def prepare_post_delete_flags(*, post, context: dict | None = None, **kwargs) -> dict:
    flag_ids = tuple(PostFlag.objects.filter(post_id=post.id).values_list("id", flat=True))
    if not flag_ids:
        return {"flag_ids": ()}

    PostFlag.objects.filter(id__in=flag_ids).delete()
    actor = (context or {}).get("actor")
    dispatch_forum_event_after_commit(
        PostFlagsDeletedEvent(
            flag_ids=flag_ids,
            post_id=post.id,
            discussion_id=post.discussion_id,
            actor_user_id=getattr(actor, "id", None),
        )
    )
    return {"flag_ids": flag_ids}
