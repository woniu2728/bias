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
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="post_type",
            module_id="posts",
            resolver=_resolve_post_type_definition,
            description="当前帖子的类型定义元数据。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="event_data",
            module_id="posts",
            resolver=_resolve_post_event_data,
            description="系统事件帖的结构化元数据。",
        )
    )

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
        )
    )

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

    _resources_bootstrapped = True


def serialize_user_summary(user) -> dict | None:
    if not user:
        return None

    payload = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }
    payload.update(get_resource_registry().serialize("user_summary", user))
    return payload


def serialize_user_payload(user, resource: str = "user_summary") -> dict | None:
    if not user:
        return None

    payload = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": getattr(user, "bio", ""),
        "discussion_count": getattr(user, "discussion_count", 0),
        "comment_count": getattr(user, "comment_count", 0),
        "joined_at": getattr(user, "joined_at", None),
        "last_seen_at": getattr(user, "last_seen_at", None),
    }
    payload.update(get_resource_registry().serialize(resource, user))
    return payload


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


def _resolve_post_type_definition(post, context: dict) -> dict | None:
    from apps.core.forum_registry import get_forum_registry

    definition = get_forum_registry().get_post_type(getattr(post, "type", ""))
    if not definition:
        return None

    return {
        "code": definition.code,
        "label": definition.label,
        "description": definition.description,
        "icon": definition.icon,
        "module_id": definition.module_id,
        "is_default": definition.is_default,
        "is_stream_visible": definition.is_stream_visible,
        "counts_toward_discussion": definition.counts_toward_discussion,
        "counts_toward_user": definition.counts_toward_user,
        "searchable": definition.searchable,
    }


def _resolve_post_event_data(post, context: dict) -> dict | None:
    post_type = getattr(post, "type", "")
    if post_type == "discussionRenamed":
        lines = [
            line.strip()
            for line in (getattr(post, "content", "") or "").splitlines()
            if line.strip()
        ]
        if len(lines) < 2:
            return None

        previous_title = lines[0].removeprefix("from:").strip()
        current_title = lines[1].removeprefix("to:").strip()
        if not previous_title or not current_title:
            return None

        return {
            "kind": "discussionRenamed",
            "old_title": previous_title,
            "new_title": current_title,
        }

    if post_type == "discussionLocked":
        normalized = (getattr(post, "content", "") or "").strip().lower()
        if normalized not in {"locked", "unlocked"}:
            return None

        return {
            "kind": "discussionLocked",
            "is_locked": normalized == "locked",
        }

    if post_type == "discussionSticky":
        normalized = (getattr(post, "content", "") or "").strip().lower()
        if normalized not in {"sticky", "unsticky"}:
            return None

        return {
            "kind": "discussionSticky",
            "is_sticky": normalized == "sticky",
        }

    if post_type == "discussionHidden":
        normalized = (getattr(post, "content", "") or "").strip().lower()
        if normalized not in {"hidden", "restored"}:
            return None

        return {
            "kind": "discussionHidden",
            "is_hidden": normalized == "hidden",
        }

    if post_type == "postHidden":
        lines = [
            line.strip()
            for line in (getattr(post, "content", "") or "").splitlines()
            if line.strip()
        ]
        is_hidden = None
        target_post_id = None
        target_post_number = None
        for line in lines:
            if line.startswith("state:"):
                normalized = line.removeprefix("state:").strip().lower()
                if normalized in {"hidden", "restored"}:
                    is_hidden = normalized == "hidden"
            elif line.startswith("target_post_id:"):
                raw_value = line.removeprefix("target_post_id:").strip()
                if raw_value.isdigit():
                    target_post_id = int(raw_value)
            elif line.startswith("target_post_number:"):
                raw_value = line.removeprefix("target_post_number:").strip()
                if raw_value.isdigit():
                    target_post_number = int(raw_value)

        if is_hidden is None:
            return None

        event_data = {
            "kind": "postHidden",
            "is_hidden": is_hidden,
        }
        if target_post_id is not None:
            event_data["target_post_id"] = target_post_id
        if target_post_number is not None:
            event_data["target_post_number"] = target_post_number
        return event_data

    if post_type == "discussionTagged":
        lines = [
            line.strip()
            for line in (getattr(post, "content", "") or "").splitlines()
            if line.strip()
        ]
        added = []
        removed = []
        for line in lines:
            if line.startswith("added:"):
                added = [item for item in line.removeprefix("added:").split("|") if item]
            elif line.startswith("removed:"):
                removed = [item for item in line.removeprefix("removed:").split("|") if item]

        return {
            "kind": "discussionTagged",
            "added_tags": added,
            "removed_tags": removed,
        }

    if post_type in {
        "discussionApproved",
        "discussionRejected",
        "discussionResubmitted",
        "postApproved",
        "postRejected",
        "postResubmitted",
    }:
        lines = [
            line.strip()
            for line in (getattr(post, "content", "") or "").splitlines()
            if line.strip()
        ]
        note = ""
        previous_status = ""
        target_post_id = None
        target_post_number = None
        for line in lines:
            if line.startswith("note:"):
                note = line.removeprefix("note:").strip()
            elif line.startswith("previous_status:"):
                previous_status = line.removeprefix("previous_status:").strip()
            elif line.startswith("target_post_id:"):
                raw_value = line.removeprefix("target_post_id:").strip()
                if raw_value.isdigit():
                    target_post_id = int(raw_value)
            elif line.startswith("target_post_number:"):
                raw_value = line.removeprefix("target_post_number:").strip()
                if raw_value.isdigit():
                    target_post_number = int(raw_value)

        event_data = {
            "kind": post_type,
            "note": note,
        }
        if previous_status:
            event_data["previous_status"] = previous_status
        if target_post_id is not None:
            event_data["target_post_id"] = target_post_id
        if target_post_number is not None:
            event_data["target_post_number"] = target_post_number
        return event_data

    return None


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


def _resolve_search_discussion_user(discussion, context: dict) -> dict | None:
    return serialize_user_summary(getattr(discussion, "user", None))


def _resolve_search_post_user(post, context: dict) -> dict | None:
    return serialize_user_summary(getattr(post, "user", None))


def _resolve_user_primary_group(user, context: dict) -> dict | None:
    from apps.users.group_utils import get_primary_group, serialize_group_badge

    return serialize_group_badge(get_primary_group(user))


def _resolve_notification_from_user(notification, context: dict) -> dict | None:
    return serialize_user_summary(getattr(notification, "from_user", None))
