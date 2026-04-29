"""
WebSocket消费者
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from typing import Optional

from apps.core.online_service import OnlineUserService


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
        from apps.notifications.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.mark_as_read()
        except Notification.DoesNotExist:
            pass


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
