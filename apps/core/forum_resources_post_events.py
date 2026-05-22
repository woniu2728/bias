from __future__ import annotations

from apps.core.resource_registry import ResourceFieldDefinition


def register_forum_post_event_resource_fields(registry) -> None:
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="post_type",
            module_id="posts",
            resolver=resolve_post_type_definition,
            description="当前帖子的类型定义元数据。",
        )
    )
    registry.register_field(
        ResourceFieldDefinition(
            resource="post",
            field="event_data",
            module_id="posts",
            resolver=resolve_post_event_data,
            description="系统事件帖的结构化元数据。",
        )
    )


def resolve_post_type_definition(post, context: dict) -> dict | None:
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


def resolve_post_event_data(post, context: dict) -> dict | None:
    post_type = getattr(post, "type", "")
    if post_type == "discussionRenamed":
        lines = _normalized_lines(getattr(post, "content", ""))
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
        parsed = _parse_post_target_state_content(getattr(post, "content", ""))
        if parsed["is_hidden"] is None:
            return None

        event_data = {
            "kind": "postHidden",
            "is_hidden": parsed["is_hidden"],
        }
        if parsed["target_post_id"] is not None:
            event_data["target_post_id"] = parsed["target_post_id"]
        if parsed["target_post_number"] is not None:
            event_data["target_post_number"] = parsed["target_post_number"]
        return event_data

    if post_type == "discussionTagged":
        added = []
        removed = []
        for line in _normalized_lines(getattr(post, "content", "")):
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
        parsed = _parse_approval_event_content(getattr(post, "content", ""))
        event_data = {
            "kind": post_type,
            "note": parsed["note"],
        }
        if parsed["previous_status"]:
            event_data["previous_status"] = parsed["previous_status"]
        if parsed["target_post_id"] is not None:
            event_data["target_post_id"] = parsed["target_post_id"]
        if parsed["target_post_number"] is not None:
            event_data["target_post_number"] = parsed["target_post_number"]
        return event_data

    return None


def _normalized_lines(content: str | None) -> list[str]:
    return [
        line.strip()
        for line in (content or "").splitlines()
        if line.strip()
    ]


def _parse_post_target_state_content(content: str | None) -> dict:
    is_hidden = None
    target_post_id = None
    target_post_number = None
    for line in _normalized_lines(content):
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

    return {
        "is_hidden": is_hidden,
        "target_post_id": target_post_id,
        "target_post_number": target_post_number,
    }


def _parse_approval_event_content(content: str | None) -> dict:
    note = ""
    previous_status = ""
    target_post_id = None
    target_post_number = None
    for line in _normalized_lines(content):
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

    return {
        "note": note,
        "previous_status": previous_status,
        "target_post_id": target_post_id,
        "target_post_number": target_post_number,
    }
