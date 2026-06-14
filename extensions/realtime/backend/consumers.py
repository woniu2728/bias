from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.core.extensions.platform import has_forum_permission
from apps.core.extensions.forum import can_view_realtime_discussion, resolve_realtime_visible_discussion_ids
from apps.core.extensions.forum import OnlineUserService
from apps.core.extensions.platform import get_extension_settings


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        self.notification_group_name = f"notifications_{self.user.id}"

        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name,
        )

        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "已连接到通知服务",
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "notification_group_name"):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get("type")
        if message_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        if message_type == "mark_read":
            notification_id = data.get("notification_id")
            if notification_id:
                await self.mark_notification_read(notification_id)

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification": event["notification"],
        }))

    @database_sync_to_async
    def mark_notification_read(self, notification_id: int):
        from apps.core.extensions.runtime import get_runtime_resource_registry

        registry = get_runtime_resource_registry()
        context = {
            "request": None,
            "resource": "notification",
            "endpoint": "read",
            "method": "POST",
            "user": self.user,
            "object_id": str(notification_id),
            "payload": {},
            "query": {},
        }
        definition = registry.get_dispatch_endpoint("notification", "read", "POST", context)
        if definition is not None:
            registry.dispatch_resource_endpoint(definition, context)


class OnlineUsersConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.online_group_name = "online_users"

        await self.channel_layer.group_add(
            self.online_group_name,
            self.channel_name,
        )

        await self.accept()

        if not isinstance(self.user, AnonymousUser):
            became_online = await self.mark_user_online()
            if became_online:
                await self.channel_layer.group_send(
                    self.online_group_name,
                    {
                        "type": "user_status",
                        "user_id": self.user.id,
                        "username": self.user.username,
                        "status": "online",
                    },
                )

        online_users = await self.get_online_users()
        await self.send(text_data=json.dumps({
            "type": "online_users",
            "users": online_users,
        }))

    async def disconnect(self, close_code):
        if not isinstance(self.user, AnonymousUser):
            became_offline = await self.mark_user_offline()
            if became_offline:
                await self.channel_layer.group_send(
                    self.online_group_name,
                    {
                        "type": "user_status",
                        "user_id": self.user.id,
                        "username": self.user.username,
                        "status": "offline",
                    },
                )

        await self.channel_layer.group_discard(
            self.online_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get("type") == "ping":
            if not isinstance(self.user, AnonymousUser):
                await self.touch_user_online()
            await self.send(text_data=json.dumps({"type": "pong"}))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_status",
            "user_id": event["user_id"],
            "username": event["username"],
            "status": event["status"],
        }))

    @database_sync_to_async
    def mark_user_online(self):
        return OnlineUserService.mark_user_online(self.user.id)

    @database_sync_to_async
    def touch_user_online(self):
        return OnlineUserService.touch_user_online(self.user.id)

    @database_sync_to_async
    def mark_user_offline(self):
        return OnlineUserService.mark_user_offline(self.user.id)

    @database_sync_to_async
    def get_online_users(self):
        return OnlineUserService.get_online_users(limit=50)


class DiscussionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        raw_discussion_id = self.scope.get("url_route", {}).get("kwargs", {}).get("discussion_id")
        try:
            self.discussion_id = int(raw_discussion_id)
        except (TypeError, ValueError):
            await self.close()
            return

        self.user = self.scope["user"]
        can_view = await self.can_view_discussion()
        if not can_view:
            await self.close()
            return

        self.discussion_group_name = f"discussion_{self.discussion_id}"
        await self.channel_layer.group_add(
            self.discussion_group_name,
            self.channel_name,
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "discussion_id": self.discussion_id,
            "message": "已连接到讨论实时流",
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "discussion_group_name"):
            await self.channel_layer.group_discard(
                self.discussion_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get("type")
        if message_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        if message_type == "typing_indicator":
            await self.handle_typing_indicator_message(data)

    async def forum_event_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "forum_event",
            "event": event["event"],
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing_indicator",
            "discussion_id": self.discussion_id,
            "user_id": event["user_id"],
            "username": event["username"],
            "is_typing": event["is_typing"],
        }))

    async def handle_typing_indicator_message(self, data):
        if isinstance(self.user, AnonymousUser):
            return
        if not await self.can_send_typing_indicator(self.discussion_id):
            return

        await self.channel_layer.group_send(
            self.discussion_group_name,
            {
                "type": "typing_indicator",
                "discussion_id": self.discussion_id,
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": bool(data.get("is_typing", False)),
            },
        )

    @database_sync_to_async
    def can_view_discussion(self):
        return can_view_realtime_discussion(self.discussion_id, self.user)

    @database_sync_to_async
    def can_send_typing_indicator(self, discussion_id: int) -> bool:
        return can_send_typing_indicator(self.user, discussion_id)


class ForumRealtimeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.discussion_group_names = set()
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "已连接到论坛实时服务",
        }))

    async def disconnect(self, close_code):
        for group_name in list(self.discussion_group_names):
            await self.channel_layer.group_discard(group_name, self.channel_name)
        self.discussion_group_names.clear()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get("type")
        if message_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        if message_type == "subscribe_discussions":
            subscribed_ids = await self.subscribe_discussions(data.get("discussion_ids"))
            await self.send(text_data=json.dumps({
                "type": "subscribed",
                "discussion_ids": subscribed_ids,
            }))
            return

        if message_type == "unsubscribe_discussions":
            unsubscribed_ids = await self.unsubscribe_discussions(data.get("discussion_ids"))
            await self.send(text_data=json.dumps({
                "type": "unsubscribed",
                "discussion_ids": unsubscribed_ids,
            }))
            return

        if message_type == "typing_indicator":
            await self.handle_typing_indicator_message(data)

    async def forum_event_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "forum_event",
            "event": event["event"],
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing_indicator",
            "discussion_id": event.get("discussion_id"),
            "user_id": event["user_id"],
            "username": event["username"],
            "is_typing": event["is_typing"],
        }))

    async def handle_typing_indicator_message(self, data):
        if isinstance(self.user, AnonymousUser):
            return

        try:
            discussion_id = int(data.get("discussion_id"))
        except (TypeError, ValueError):
            return

        if not await self.can_send_typing_indicator(discussion_id):
            return

        await self.channel_layer.group_send(
            f"discussion_{discussion_id}",
            {
                "type": "typing_indicator",
                "discussion_id": discussion_id,
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": bool(data.get("is_typing", False)),
            },
        )

    async def subscribe_discussions(self, discussion_ids):
        visible_ids = await self.get_visible_discussion_ids(discussion_ids)
        for discussion_id in visible_ids:
            group_name = f"discussion_{discussion_id}"
            if group_name in self.discussion_group_names:
                continue
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.discussion_group_names.add(group_name)
        return visible_ids

    async def unsubscribe_discussions(self, discussion_ids):
        removed_ids = []
        for discussion_id in await self.get_visible_discussion_ids(discussion_ids):
            group_name = f"discussion_{discussion_id}"
            if group_name not in self.discussion_group_names:
                continue
            await self.channel_layer.group_discard(group_name, self.channel_name)
            self.discussion_group_names.remove(group_name)
            removed_ids.append(discussion_id)
        return removed_ids

    @database_sync_to_async
    def get_visible_discussion_ids(self, discussion_ids):
        return resolve_realtime_visible_discussion_ids(discussion_ids, self.user)

    @database_sync_to_async
    def can_send_typing_indicator(self, discussion_id: int) -> bool:
        return can_send_typing_indicator(self.user, discussion_id)


def can_send_typing_indicator(user, discussion_id: int) -> bool:
    if not _is_typing_indicator_enabled():
        return False
    if not has_forum_permission(user, "discussion.typing"):
        return False
    visible_ids = resolve_realtime_visible_discussion_ids([discussion_id], user)
    return discussion_id in visible_ids


def _is_typing_indicator_enabled() -> bool:
    return bool(get_extension_settings("realtime").get("typing_enabled", True))
