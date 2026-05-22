from __future__ import annotations

from apps.core.resource_registry import (
    ResourceDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
    get_resource_registry,
)


def register_forum_user_resources(registry) -> None:
    registry.register_resource(
        ResourceDefinition(
            resource="user_summary",
            module_id="users",
            resolver=_serialize_user_summary_base,
            description="论坛内通用用户摘要资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="user_detail",
            module_id="users",
            resolver=_serialize_user_detail_base,
            description="论坛内通用用户详情资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="discussion_user",
            module_id="users",
            resolver=_serialize_user_summary_base,
            description="讨论作者摘要资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="post_user",
            module_id="users",
            resolver=_serialize_user_summary_base,
            description="帖子作者摘要资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="search_user",
            module_id="users",
            resolver=_serialize_user_search_base,
            description="搜索用户结果资源。",
        )
    )


def register_forum_user_relationships(registry) -> None:
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="discussion",
            relationship="user",
            module_id="discussions",
            resolver=_resolve_discussion_user,
            description="讨论作者摘要。",
            select_related=("user",),
            prefetch_related=("user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="discussion",
            relationship="last_posted_user",
            module_id="discussions",
            resolver=_resolve_discussion_last_posted_user,
            description="讨论最后回复用户摘要。",
            select_related=("last_posted_user",),
            prefetch_related=("last_posted_user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="post",
            relationship="user",
            module_id="posts",
            resolver=_resolve_post_user,
            description="帖子作者摘要。",
            select_related=("user",),
            prefetch_related=("user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="post",
            relationship="edited_user",
            module_id="posts",
            resolver=_resolve_post_edited_user,
            description="帖子编辑者摘要。",
            select_related=("edited_user",),
            prefetch_related=("edited_user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="search_discussion",
            relationship="user",
            module_id="discussions",
            resolver=_resolve_search_discussion_user,
            description="搜索结果中的讨论作者摘要。",
            select_related=("user",),
            prefetch_related=("user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="search_post",
            relationship="user",
            module_id="posts",
            resolver=_resolve_search_post_user,
            description="搜索结果中的回复作者摘要。",
            select_related=("user",),
            prefetch_related=("user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="notification",
            relationship="from_user",
            module_id="notifications",
            resolver=_resolve_notification_from_user,
            description="通知来源用户摘要。",
            select_related=("from_user",),
            prefetch_related=("from_user__user_groups",),
        )
    )
    registry.register_relationship(
        ResourceRelationshipDefinition(
            resource="user_detail",
            relationship="groups",
            module_id="users",
            resolver=_resolve_user_groups,
            description="用户详情中的用户组列表。",
            prefetch_related=("user_groups",),
        )
    )


def register_forum_user_fields(registry) -> None:
    registry.register_field(
        ResourceFieldDefinition(
            resource="search_discussion",
            field="user",
            module_id="discussions",
            resolver=_resolve_search_discussion_user,
            description="搜索结果中的讨论作者摘要。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="search_post",
            field="user",
            module_id="posts",
            resolver=_resolve_search_post_user,
            description="搜索结果中的回复作者摘要。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="user_summary",
            field="primary_group",
            module_id="users",
            resolver=_resolve_user_primary_group,
            description="用户摘要中的主用户组徽章。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="notification",
            field="from_user",
            module_id="notifications",
            resolver=_resolve_notification_from_user,
            description="通知来源用户摘要。",
            select_related=("from_user",),
            prefetch_related=("from_user__user_groups",),
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="user_detail",
            field="primary_group",
            module_id="users",
            resolver=_resolve_user_primary_group,
            description="用户详情中的主用户组徽章。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="search_user",
            field="primary_group",
            module_id="users",
            resolver=_resolve_user_primary_group,
            description="搜索用户结果中的主用户组徽章。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="discussion_user",
            field="primary_group",
            module_id="users",
            resolver=_resolve_user_primary_group,
            description="讨论作者摘要中的主用户组徽章。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post_user",
            field="primary_group",
            module_id="users",
            resolver=_resolve_user_primary_group,
            description="帖子作者摘要中的主用户组徽章。",
        )
    )


def serialize_user_summary(user) -> dict | None:
    if not user:
        return None

    return get_resource_registry().serialize("user_summary", user)


def serialize_user_payload(user, resource: str = "user_detail") -> dict | None:
    if not user:
        return None

    return get_resource_registry().serialize(resource, user)


def _serialize_user_summary_base(user, context: dict) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


def _serialize_user_detail_base(user, context: dict) -> dict:
    return {
        **_serialize_user_summary_base(user, context),
        "bio": getattr(user, "bio", ""),
        "discussion_count": getattr(user, "discussion_count", 0),
        "comment_count": getattr(user, "comment_count", 0),
        "joined_at": getattr(user, "joined_at", None),
        "last_seen_at": getattr(user, "last_seen_at", None),
    }


def _serialize_user_search_base(user, context: dict) -> dict:
    return _serialize_user_detail_base(user, context)


def _resolve_search_discussion_user(discussion, context: dict) -> dict | None:
    return serialize_user_summary(getattr(discussion, "user", None))


def _resolve_search_post_user(post, context: dict) -> dict | None:
    return serialize_user_summary(getattr(post, "user", None))


def _resolve_discussion_user(discussion, context: dict) -> dict | None:
    return serialize_user_payload(getattr(discussion, "user", None), resource="discussion_user")


def _resolve_discussion_last_posted_user(discussion, context: dict) -> dict | None:
    return serialize_user_payload(getattr(discussion, "last_posted_user", None), resource="discussion_user")


def _resolve_post_user(post, context: dict) -> dict | None:
    return serialize_user_payload(getattr(post, "user", None), resource="post_user")


def _resolve_post_edited_user(post, context: dict) -> dict | None:
    return serialize_user_payload(getattr(post, "edited_user", None), resource="post_user")


def _resolve_user_primary_group(user, context: dict) -> dict | None:
    from apps.users.group_utils import get_primary_group, serialize_group_badge

    return serialize_group_badge(get_primary_group(user))


def _resolve_user_groups(user, context: dict) -> list[dict]:
    if not hasattr(user, "user_groups"):
        return []

    return [
        {
            "id": group.id,
            "name": group.name,
            "color": group.color,
            "icon": group.icon,
            "is_hidden": group.is_hidden,
        }
        for group in user.user_groups.all()
    ]


def _resolve_notification_from_user(notification, context: dict) -> dict | None:
    return serialize_user_summary(getattr(notification, "from_user", None))
