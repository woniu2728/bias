from __future__ import annotations

from apps.core.resource_registry import ResourceFieldDefinition, get_resource_registry


_resources_bootstrapped = False


def bootstrap_forum_resource_fields() -> None:
    global _resources_bootstrapped
    if _resources_bootstrapped:
        return

    registry = get_resource_registry()

    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion",
            field="tags",
            module_id="tags",
            resolver=_resolve_discussion_tags,
            description="讨论关联的标签列表。",
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
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="viewer_has_open_flag",
            module_id="flags",
            resolver=_resolve_post_viewer_has_open_flag,
            description="当前用户是否已对该回复提交待处理举报。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="open_flag_count",
            module_id="flags",
            resolver=_resolve_post_open_flag_count,
            description="当前回复的待处理举报数量。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="open_flags",
            module_id="flags",
            resolver=_resolve_post_open_flags,
            description="当前回复的待处理举报明细。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="can_moderate_flags",
            module_id="flags",
            resolver=_resolve_post_can_moderate_flags,
            description="当前用户是否可在前台处理举报。",
        )
    )

    _resources_bootstrapped = True


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


def _resolve_post_viewer_has_open_flag(post, context: dict) -> bool:
    return bool(getattr(post, "viewer_has_open_flag", False))


def _resolve_post_open_flag_count(post, context: dict) -> int:
    return int(getattr(post, "open_flag_count", 0) or 0)


def _resolve_post_open_flags(post, context: dict) -> list[dict]:
    open_flags = getattr(post, "open_flags_cache", [])
    return [
        {
            "id": flag.id,
            "reason": flag.reason,
            "message": flag.message,
            "created_at": flag.created_at,
            "user": {
                "id": flag.user.id,
                "username": flag.user.username,
                "display_name": flag.user.display_name,
            } if flag.user else None,
        }
        for flag in open_flags
    ]


def _resolve_post_can_moderate_flags(post, context: dict) -> bool:
    user = context.get("user")
    return bool(user and user.is_staff)
