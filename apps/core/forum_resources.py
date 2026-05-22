from __future__ import annotations

from apps.core.resource_registry import (
    ResourceDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
    get_resource_registry,
)
from apps.core.forum_resources_post_events import register_forum_post_event_resource_fields
from apps.core.forum_resources_users import (
    register_forum_user_fields,
    register_forum_user_relationships,
    register_forum_user_resources,
    serialize_user_payload,
    serialize_user_summary,
)


_resources_bootstrapped = False


def bootstrap_forum_resource_fields() -> None:
    global _resources_bootstrapped
    if _resources_bootstrapped:
        return

    from apps.core.forum_resources_flags import register_forum_flag_resource_fields

    registry = get_resource_registry()

    register_forum_user_resources(registry)
    registry.register_resource(
        ResourceDefinition(
            resource="search_discussion",
            module_id="discussions",
            resolver=_serialize_search_discussion_base,
            description="搜索讨论结果资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="search_post",
            module_id="posts",
            resolver=_serialize_search_post_base,
            description="搜索帖子结果资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="tag",
            module_id="tags",
            resolver=_serialize_tag_base,
            description="论坛标签主资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="notification",
            module_id="notifications",
            resolver=_serialize_notification_base,
            description="论坛通知主资源。",
        )
    )

    register_forum_user_relationships(registry)
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="tag",
            relationship="last_posted_discussion",
            module_id="tags",
            resolver=_resolve_tag_last_posted_discussion,
            description="标签下最后活跃讨论摘要。",
            select_related=("last_posted_discussion",),
        )
    )

    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="tags",
            module_id="tags",
            resolver=_resolve_discussion_tags,
            description="讨论关联的标签列表。",
            prefetch_related=("discussion_tags__tag",),
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="can_edit",
            module_id="discussions",
            resolver=_resolve_discussion_can_edit,
            description="当前用户是否可以编辑讨论。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="can_delete",
            module_id="discussions",
            resolver=_resolve_discussion_can_delete,
            description="当前用户是否可以删除讨论。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="can_reply",
            module_id="discussions",
            resolver=_resolve_discussion_can_reply,
            description="当前用户是否可以回复讨论。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="is_subscribed",
            module_id="subscriptions",
            resolver=_resolve_discussion_subscription_state,
            description="当前用户是否关注该讨论。",
        )
    )

    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="can_edit",
            module_id="discussions",
            resolver=_resolve_post_can_edit,
            description="当前用户是否可以编辑该回复。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="can_delete",
            module_id="discussions",
            resolver=_resolve_post_can_delete,
            description="当前用户是否可以删除该回复。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="can_like",
            module_id="likes",
            resolver=_resolve_post_can_like,
            description="当前用户是否可以点赞该回复。",
        )
    )
    register_forum_flag_resource_fields()
    register_forum_post_event_resource_fields(registry)

    registry.register_field(
        ResourceFieldDefinition(
            resource="tag",
            field="can_start_discussion",
            module_id="tags",
            resolver=_resolve_tag_can_start_discussion,
            description="当前用户是否可以在该标签下发起讨论。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="tag",
            field="can_reply",
            module_id="tags",
            resolver=_resolve_tag_can_reply,
            description="当前用户是否可以在该标签下回复。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="tag",
            field="last_posted_discussion",
            module_id="tags",
            resolver=_resolve_tag_last_posted_discussion,
            description="标签下最后活跃讨论摘要。",
            select_related=("last_posted_discussion",),
        )
    )

    register_forum_user_fields(registry)

    _resources_bootstrapped = True


def _serialize_search_discussion_base(discussion, context: dict) -> dict:
    return {
        "id": discussion.id,
        "title": discussion.title,
        "slug": discussion.slug,
        "comment_count": discussion.comment_count,
        "view_count": discussion.view_count,
        "is_sticky": discussion.is_sticky,
        "is_locked": discussion.is_locked,
        "created_at": discussion.created_at,
        "last_posted_at": discussion.last_posted_at,
        "excerpt": discussion.excerpt,
    }


def _serialize_search_post_base(post, context: dict) -> dict:
    return {
        "id": post.id,
        "discussion_id": post.discussion_id,
        "discussion_title": post.discussion_title,
        "number": post.number,
        "content": post.content,
        "created_at": post.created_at,
        "excerpt": post.excerpt,
    }


def _serialize_tag_base(tag, context: dict) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "description": tag.description,
        "color": tag.color,
        "icon": tag.icon,
        "background_url": tag.background_url,
        "position": tag.position,
        "parent_id": tag.parent_id,
        "is_hidden": tag.is_hidden,
        "is_restricted": tag.is_restricted,
        "view_scope": tag.view_scope,
        "start_discussion_scope": tag.start_discussion_scope,
        "reply_scope": tag.reply_scope,
        "discussion_count": tag.discussion_count,
        "last_posted_at": tag.last_posted_at,
        "created_at": tag.created_at,
        "updated_at": tag.updated_at,
    }


def _serialize_notification_base(notification, context: dict) -> dict:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": notification.type,
        "subject_type": notification.subject_type,
        "subject_id": notification.subject_id,
        "data": notification.data,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }


def _resolve_discussion_tags(discussion, context: dict) -> list[dict]:
    return [
        {
            "id": dt.tag.id,
            "name": dt.tag.name,
            "slug": dt.tag.slug,
            "color": dt.tag.color,
            "icon": dt.tag.icon,
        }
        for dt in discussion.discussion_tags.all()
    ]


def _resolve_discussion_can_edit(discussion, context: dict) -> bool:
    from apps.discussions.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_edit_discussion(discussion, user))


def _resolve_discussion_can_delete(discussion, context: dict) -> bool:
    from apps.discussions.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_delete_discussion(discussion, user))


def _resolve_discussion_can_reply(discussion, context: dict) -> bool:
    from apps.discussions.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_reply_discussion(discussion, user))


def _resolve_discussion_subscription_state(discussion, context: dict) -> bool:
    from apps.discussions.services import DiscussionService

    user = context.get("user")
    return DiscussionService.get_subscription_state(discussion, user)


def _resolve_post_can_edit(post, context: dict) -> bool:
    from apps.posts.services import PostService

    user = context.get("user")
    return bool(user and PostService.can_edit_post(post, user))


def _resolve_post_can_delete(post, context: dict) -> bool:
    from apps.posts.services import PostService

    user = context.get("user")
    return bool(user and PostService.can_delete_post(post, user))


def _resolve_post_can_like(post, context: dict) -> bool:
    from apps.posts.services import PostService

    user = context.get("user")
    return bool(user and PostService.can_like_post(post, user))


def _resolve_tag_can_start_discussion(tag, context: dict) -> bool:
    from apps.tags.services import TagService

    user = context.get("user")
    return TagService.can_start_discussion_in_tag(tag, user)


def _resolve_tag_can_reply(tag, context: dict) -> bool:
    from apps.tags.services import TagService

    user = context.get("user")
    return TagService.can_reply_in_tag(tag, user)


def _resolve_tag_last_posted_discussion(tag, context: dict) -> dict | None:
    discussion = getattr(tag, "last_posted_discussion", None)
    if not discussion:
        return None

    return {
        "id": discussion.id,
        "title": discussion.title,
        "slug": discussion.slug,
        "last_post_number": discussion.last_post_number,
        "last_posted_at": discussion.last_posted_at,
    }
