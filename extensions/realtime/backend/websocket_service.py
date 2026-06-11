from __future__ import annotations

import json
from typing import Any

from asgiref.sync import async_to_sync
from django.core.serializers.json import DjangoJSONEncoder
from channels.layers import get_channel_layer


def make_channel_payload_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))


class WebSocketService:
    @staticmethod
    def _group_send(group_name: str, payload: dict[str, Any]) -> None:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(group_name, make_channel_payload_safe(payload))

    @staticmethod
    def send_notification_to_user(user_id: int, notification_data: dict[Any, Any]) -> None:
        WebSocketService._group_send(
            f"notifications_{user_id}",
            {
                "type": "notification_message",
                "notification": notification_data,
            },
        )

    @staticmethod
    def broadcast_user_status(user_id: int, username: str, status: str) -> None:
        WebSocketService._group_send(
            "online_users",
            {
                "type": "user_status",
                "user_id": user_id,
                "username": username,
                "status": status,
            },
        )

    @staticmethod
    def send_typing_indicator(discussion_id: int, user_id: int, username: str, is_typing: bool) -> None:
        WebSocketService._group_send(
            f"discussion_{discussion_id}",
            {
                "type": "typing_indicator",
                "discussion_id": discussion_id,
                "user_id": user_id,
                "username": username,
                "is_typing": is_typing,
            },
        )

    @staticmethod
    def broadcast_discussion_event(discussion_id: int, event_type: str, payload: dict[str, Any]) -> None:
        WebSocketService._group_send(
            f"discussion_{discussion_id}",
            {
                "type": "forum_event_message",
                "event": {
                    "scope": "discussion",
                    "discussion_id": discussion_id,
                    "event_type": event_type,
                    "payload": payload,
                },
            },
        )
