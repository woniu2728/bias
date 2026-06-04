from __future__ import annotations


APPROVAL_POST_EVENT_TYPES = (
    "discussionApproved",
    "discussionRejected",
    "discussionResubmitted",
    "postApproved",
    "postRejected",
    "postResubmitted",
)


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
