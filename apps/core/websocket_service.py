"""
WebSocket工具函数
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from typing import Any, Dict


class WebSocketService:
    """WebSocket服务"""

    @staticmethod
    def _group_send(group_name: str, payload: Dict[str, Any]):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(group_name, payload)

    @staticmethod
    def send_notification_to_user(user_id: int, notification_data: Dict[Any, Any]):
        """
        发送通知给指定用户

        Args:
            user_id: 用户ID
            notification_data: 通知数据
        """
        group_name = f'notifications_{user_id}'
        WebSocketService._group_send(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )

    @staticmethod
    def broadcast_user_status(user_id: int, username: str, status: str):
        """
        广播用户状态变化

        Args:
            user_id: 用户ID
            username: 用户名
            status: 状态 (online/offline)
        """
        group_name = 'online_users'
        WebSocketService._group_send(
            group_name,
            {
                'type': 'user_status',
                'user_id': user_id,
                'username': username,
                'status': status
            }
        )

    @staticmethod
    def send_typing_indicator(discussion_id: int, user_id: int, username: str, is_typing: bool):
        """
        发送正在输入指示器

        Args:
            discussion_id: 讨论ID
            user_id: 用户ID
            username: 用户名
            is_typing: 是否正在输入
        """
        group_name = f'discussion_{discussion_id}'
        WebSocketService._group_send(
            group_name,
            {
                'type': 'typing_indicator',
                'discussion_id': discussion_id,
                'user_id': user_id,
                'username': username,
                'is_typing': is_typing
            }
        )

    @staticmethod
    def broadcast_discussion_event(discussion_id: int, event_type: str, payload: Dict[str, Any]):
        """广播讨论实时事件。"""
        WebSocketService._group_send(
            f'discussion_{discussion_id}',
            {
                'type': 'forum_event_message',
                'event': {
                    'scope': 'discussion',
                    'discussion_id': discussion_id,
                    'event_type': event_type,
                    'payload': payload,
                }
            }
        )
