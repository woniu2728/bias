"""
WebSocket消费者
"""
import json
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.core.online_service import OnlineUserService
from apps.core.settings_service import get_advanced_settings
from apps.users.services import UserService


def resolve_visible_discussion_ids(discussion_ids, user) -> list[int]:
    normalized_ids = []
    seen = set()
    for raw_id in discussion_ids or []:
        try:
            discussion_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if discussion_id <= 0 or discussion_id in seen:
            continue
        seen.add(discussion_id)
        normalized_ids.append(discussion_id)

    if isinstance(user, AnonymousUser):
        user = None

    discussions = {
        discussion.id: discussion
        for discussion in Discussion.objects.filter(id__in=normalized_ids)
    }
    return [
        discussion_id
        for discussion_id in normalized_ids
        if discussions.get(discussion_id) is not None
        and DiscussionService._can_view_discussion(discussions[discussion_id], user)
    ]


class NotificationConsumer(AsyncWebsocketConsumer):
    """通知WebSocket消费者"""

    async def connect(self):
        """连接时"""
        self.user = self.scope["user"]

        if isinstance(self.user, AnonymousUser):
            # 拒绝未认证用户
            await self.close()
            return

        # 加入用户专属通知组
        self.notification_group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )

        await self.accept()

        # 发送连接成功消息
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': '已连接到通知服务'
        }))

    async def disconnect(self, close_code):
        """断开连接时"""
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """接收消息"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # 心跳检测
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))

            elif message_type == 'mark_read':
                # 标记通知为已读
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)

        except json.JSONDecodeError:
            pass

    async def notification_message(self, event):
        """发送通知消息"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))

    @database_sync_to_async
    def mark_notification_read(self, notification_id: int):
        """标记通知为已读"""
        from apps.notifications.services import NotificationService

        NotificationService.mark_as_read(notification_id, self.user)


class OnlineUsersConsumer(AsyncWebsocketConsumer):
    """在线用户WebSocket消费者"""

    async def connect(self):
        """连接时"""
        self.user = self.scope["user"]
        self.online_group_name = 'online_users'

        # 加入在线用户组
        await self.channel_layer.group_add(
            self.online_group_name,
            self.channel_name
        )

        await self.accept()

        # 如果是认证用户，广播上线消息
        if not isinstance(self.user, AnonymousUser):
            became_online = await self.mark_user_online()
            if became_online:
                await self.channel_layer.group_send(
                    self.online_group_name,
                    {
                        'type': 'user_status',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'status': 'online'
                    }
                )

        # 发送当前在线用户列表
        online_users = await self.get_online_users()
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': online_users
        }))

    async def disconnect(self, close_code):
        """断开连接时"""
        # 如果是认证用户，广播下线消息
        if not isinstance(self.user, AnonymousUser):
            became_offline = await self.mark_user_offline()
            if became_offline:
                await self.channel_layer.group_send(
                    self.online_group_name,
                    {
                        'type': 'user_status',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'status': 'offline'
                    }
                )

        await self.channel_layer.group_discard(
            self.online_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """接收消息"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # 心跳检测
                if not isinstance(self.user, AnonymousUser):
                    await self.touch_user_online()
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))

        except json.JSONDecodeError:
            pass

    async def user_status(self, event):
        """发送用户状态变化"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'username': event['username'],
            'status': event['status']
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
        """获取在线用户列表"""
        return OnlineUserService.get_online_users(limit=50)


class DiscussionConsumer(AsyncWebsocketConsumer):
    """讨论详情实时事件消费者"""

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
        from apps.discussions.models import Discussion

        user = self.user
        if isinstance(user, AnonymousUser):
            user = None
        discussion = Discussion.objects.filter(id=self.discussion_id).first()
        if discussion is None:
            return False
        return DiscussionService._can_view_discussion(discussion, user)

    @database_sync_to_async
    def can_send_typing_indicator(self, discussion_id: int) -> bool:
        if not bool(get_advanced_settings().get("realtime_typing_enabled", True)):
            return False
        if not UserService.has_forum_permission(self.user, "discussion.typing"):
            return False
        visible_ids = resolve_visible_discussion_ids([discussion_id], self.user)
        return discussion_id in visible_ids


class ForumRealtimeConsumer(AsyncWebsocketConsumer):
    """统一论坛实时流消费者。"""

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
        for discussion_id in resolve_visible_discussion_ids(discussion_ids, self.user):
            group_name = f"discussion_{discussion_id}"
            if group_name not in self.discussion_group_names:
                continue
            await self.channel_layer.group_discard(group_name, self.channel_name)
            self.discussion_group_names.remove(group_name)
            removed_ids.append(discussion_id)
        return removed_ids

    @database_sync_to_async
    def get_visible_discussion_ids(self, discussion_ids):
        return resolve_visible_discussion_ids(discussion_ids, self.user)

    @database_sync_to_async
    def can_send_typing_indicator(self, discussion_id: int) -> bool:
        if not bool(get_advanced_settings().get("realtime_typing_enabled", True)):
            return False
        if not UserService.has_forum_permission(self.user, "discussion.typing"):
            return False
        visible_ids = resolve_visible_discussion_ids([discussion_id], self.user)
        return discussion_id in visible_ids
