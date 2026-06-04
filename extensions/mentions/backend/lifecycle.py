from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.forum_events import UserMentionedEvent
from apps.posts.models import PostMentionsUser
from apps.users.models import User
from extensions.mentions.backend.parser import extract_mentioned_usernames


def apply_post_created_mentions(*, post, context: dict | None = None, **kwargs) -> dict:
    content = (context or {}).get("content", post.content)
    mentioned_user_ids = _sync_post_mentions(post, content, replace_existing=False)
    return {"mentioned_user_ids": mentioned_user_ids}


def apply_post_updated_mentions(*, post, context: dict | None = None, **kwargs) -> dict:
    content = (context or {}).get("content", post.content)
    mentioned_user_ids = _sync_post_mentions(post, content, replace_existing=True)
    return {"mentioned_user_ids": mentioned_user_ids}


def apply_post_approved_mentions(*, post, context: dict | None = None, **kwargs) -> dict:
    content = (context or {}).get("content", post.content)
    mentioned_user_ids = _sync_post_mentions(post, content, replace_existing=True)
    return {"mentioned_user_ids": mentioned_user_ids}


def apply_post_hidden_mentions(*, post, context: dict | None = None, **kwargs) -> dict:
    if (context or {}).get("is_hidden"):
        deleted_count, _ = PostMentionsUser.objects.filter(post=post).delete()
        return {"mentioned_user_ids": (), "deleted_count": deleted_count}

    content = (context or {}).get("content", post.content)
    mentioned_user_ids = _sync_post_mentions(post, content, replace_existing=True)
    return {"mentioned_user_ids": mentioned_user_ids}


def prepare_post_delete_mentions(*, post, context: dict | None = None, **kwargs) -> dict:
    mentioned_user_ids = tuple(PostMentionsUser.objects.filter(post=post).values_list("mentions_user_id", flat=True))
    if mentioned_user_ids:
        PostMentionsUser.objects.filter(post=post).delete()
    return {"mentioned_user_ids": mentioned_user_ids}


def _sync_post_mentions(post, content: str, *, replace_existing: bool) -> tuple[int, ...]:
    if replace_existing:
        PostMentionsUser.objects.filter(post=post).delete()

    mentions = extract_mentioned_usernames(content)
    if not mentions:
        return ()

    mentioned_user_ids: list[int] = []
    mentioned_users = User.objects.filter(username__in=mentions)
    for mentioned_user in mentioned_users:
        _, created = PostMentionsUser.objects.get_or_create(
            post=post,
            mentions_user=mentioned_user,
        )
        mentioned_user_ids.append(mentioned_user.id)

        if created:
            dispatch_forum_event_after_commit(
                UserMentionedEvent(
                    post_id=post.id,
                    discussion_id=post.discussion_id,
                    actor_user_id=post.user_id,
                    mentioned_user_id=mentioned_user.id,
                    post_number=post.number,
                )
            )

    return tuple(mentioned_user_ids)
