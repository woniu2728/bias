from __future__ import annotations

from apps.core.resource_registry import ResourceDefinition, ResourceFieldDefinition


def discussion_resource_definitions():
    return (
        ResourceDefinition(
            resource="search_discussion",
            module_id="discussions",
            resolver=serialize_search_discussion_base,
            description="搜索讨论结果资源。",
        ),
    )


def discussion_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="discussion",
            field="can_edit",
            module_id="discussions",
            resolver=resolve_discussion_can_edit,
            description="当前用户是否可以编辑讨论。",
        ),
        ResourceFieldDefinition(
            resource="discussion",
            field="can_delete",
            module_id="discussions",
            resolver=resolve_discussion_can_delete,
            description="当前用户是否可以删除讨论。",
        ),
        ResourceFieldDefinition(
            resource="discussion",
            field="can_reply",
            module_id="discussions",
            resolver=resolve_discussion_can_reply,
            description="当前用户是否可以回复讨论。",
        ),
    )


def serialize_search_discussion_base(discussion, context: dict) -> dict:
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


def resolve_discussion_can_edit(discussion, context: dict) -> bool:
    from extensions.discussions.backend.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_edit_discussion(discussion, user))


def resolve_discussion_can_delete(discussion, context: dict) -> bool:
    from extensions.discussions.backend.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_delete_discussion(discussion, user))


def resolve_discussion_can_reply(discussion, context: dict) -> bool:
    from extensions.discussions.backend.services import DiscussionService

    user = context.get("user")
    return bool(user and DiscussionService.can_reply_discussion(discussion, user))
