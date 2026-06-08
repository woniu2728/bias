from __future__ import annotations

from apps.core.resource_registry import (
    ResourceDefinition,
    ResourceFieldDefinition,
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

    registry = get_resource_registry()

    registry.register_resource(
        ResourceDefinition(
            resource="forum",
            module_id="core",
            resolver=_serialize_forum_base,
            description="论坛公开运行时资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="admin_stats",
            module_id="core",
            resolver=_serialize_admin_stats_base,
            description="后台运行状态与统计资源。",
        )
    )
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

    register_forum_user_relationships(registry)
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
    register_forum_post_event_resource_fields(registry)

    register_forum_user_fields(registry)

    _resources_bootstrapped = True


def _serialize_forum_base(forum, context: dict) -> dict:
    return {}


def _serialize_admin_stats_base(stats, context: dict) -> dict:
    return dict(stats or {})


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


def _resolve_post_can_edit(post, context: dict) -> bool:
    from extensions.posts.backend.services import PostService

    user = context.get("user")
    return bool(user and PostService.can_edit_post(post, user))


def _resolve_post_can_delete(post, context: dict) -> bool:
    from extensions.posts.backend.services import PostService

    user = context.get("user")
    return bool(user and PostService.can_delete_post(post, user))
