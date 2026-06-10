from __future__ import annotations

from django.db.models import Subquery

from apps.core.extensions.runtime_access import (
    get_runtime_discussion_model,
    get_runtime_post_model,
)
from apps.core.resource_registry import ResourceFieldDefinition


APPROVAL_POST_EVENT_TYPES = (
    "discussionApproved",
    "discussionRejected",
    "discussionResubmitted",
    "postApproved",
    "postRejected",
    "postResubmitted",
)


def admin_stats_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="admin_stats",
            field="pendingApprovals",
            module_id="approval",
            resolver=resolve_admin_pending_approvals,
            description="后台统计中的待审核内容数量。",
        ),
    )


def resolve_admin_pending_approvals(stats, context: dict) -> int:
    discussion_model = get_runtime_discussion_model()
    post_model = get_runtime_post_model()
    pending_discussions = discussion_model.objects.filter(approval_status=discussion_model.APPROVAL_PENDING)
    pending_posts = post_model.objects.filter(approval_status=post_model.APPROVAL_PENDING).exclude(
        id__in=Subquery(pending_discussions.values("first_post_id"))
    )
    return pending_discussions.count() + pending_posts.count()


def resolve_approval_event_data(post, context: dict) -> dict | None:
    post_type = getattr(post, "type", "")
    if post_type not in APPROVAL_POST_EVENT_TYPES:
        return None

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


def _normalized_lines(content: str | None) -> list[str]:
    return [
        line.strip()
        for line in (content or "").splitlines()
        if line.strip()
    ]

