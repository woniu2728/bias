from __future__ import annotations

from collections import OrderedDict

from apps.core.forum_runtime import iter_realtime_included_enrichers
from apps.core.websocket_service import WebSocketService


def broadcast_discussion_event(
    discussion_id: int,
    event_type: str,
    *,
    include_discussion: bool = False,
    include_post: bool = False,
    post_id: int | None = None,
    post_id_getter=None,
    extension_context: dict | None = None,
) -> None:
    payload = {}
    discussion = load_discussion_for_realtime(discussion_id) if include_discussion or post_id_getter else None
    if include_discussion and discussion is not None:
        payload["discussion"] = serialize_discussion_for_realtime(discussion)

    resolved_post_id = post_id
    if resolved_post_id is None and discussion is not None and post_id_getter is not None:
        resolved_post_id = post_id_getter(discussion)

    if include_post and resolved_post_id:
        post_payload = serialize_post_for_realtime(resolved_post_id)
        if post_payload is not None:
            payload["post"] = post_payload

    payload.update(
        build_realtime_included_payload(
            discussion=discussion,
            post_payload=payload.get("post"),
            extension_context=extension_context,
        )
    )

    WebSocketService.broadcast_discussion_event(
        discussion_id,
        event_type,
        payload,
    )


def load_discussion_for_realtime(discussion_id: int):
    from extensions.discussions.backend.handlers import apply_discussion_resource_preloads
    from extensions.discussions.backend.models import Discussion

    return (
        apply_discussion_resource_preloads(Discussion.objects.all(), user=None)
        .filter(id=discussion_id)
        .first()
    )


def serialize_discussion_for_realtime(discussion):
    from extensions.discussions.backend.handlers import serialize_discussion_payload

    return serialize_discussion_payload(discussion, user=None)


def serialize_post_for_realtime(post_id: int):
    from extensions.posts.backend.handlers import apply_post_resource_preloads, serialize_post
    from extensions.posts.backend.models import Post

    post = (
        apply_post_resource_preloads(
            Post.objects.select_related("discussion"),
            user=None,
        )
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return None
    return serialize_post(post, user=None)


def build_realtime_included_payload(
    *,
    discussion=None,
    post_payload: dict | None = None,
    extension_context: dict | None = None,
) -> dict:
    users = OrderedDict()
    extension_context = dict(extension_context or {})

    if discussion is not None:
        collect_discussion_users(users, discussion)

    if post_payload:
        collect_post_users(users, post_payload)

    payload = {}
    if users:
        payload["users"] = list(users.values())
    for enricher in iter_realtime_included_enrichers():
        extra = enricher(
            discussion=discussion,
            post_payload=post_payload,
            extension_context=extension_context,
            payload=payload,
        )
        if not isinstance(extra, dict):
            continue
        for key, value in extra.items():
            if not value:
                continue
            if isinstance(payload.get(key), list) and isinstance(value, list):
                payload[key] = [*payload[key], *value]
            else:
                payload[key] = value
    return payload


def collect_discussion_users(target: OrderedDict, discussion) -> None:
    from extensions.users.backend.resources import serialize_user_payload

    for user in (
        getattr(discussion, "user", None),
        getattr(discussion, "last_posted_user", None),
    ):
        payload = serialize_user_payload(user, resource="discussion_user")
        if payload and payload.get("id") is not None:
            merge_included_resource(target, payload)


def collect_post_users(target: OrderedDict, post_payload: dict) -> None:
    for key in ("user", "edited_user"):
        payload = post_payload.get(key)
        if payload and payload.get("id") is not None:
            merge_included_resource(target, payload)


def merge_included_resource(target: OrderedDict, payload: dict) -> None:
    resource_id = int(payload["id"])
    target[resource_id] = {
        **(target.get(resource_id) or {}),
        **payload,
    }
