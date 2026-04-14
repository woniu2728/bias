"""
通知系统业务逻辑层
"""
from typing import Optional, List, Tuple
from django.db import transaction
from django.db.models import Q, F, Count
from django.utils import timezone
from apps.notifications.models import Notification
from apps.users.models import User
from apps.discussions.models import DiscussionUser


class NotificationService:
    """通知服务"""

    # 通知类型常量
    TYPE_DISCUSSION_REPLY = 'discussionReply'
    TYPE_POST_LIKED = 'postLiked'
    TYPE_USER_MENTIONED = 'userMentioned'
    TYPE_POST_REPLY = 'postReply'

    @staticmethod
    def create_notification(
        user: User,
        type: str,
        from_user: Optional[User] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[int] = None,
        data: Optional[dict] = None,
    ) -> Notification:
        """
        创建通知

        Args:
            user: 接收通知的用户
            type: 通知类型
            from_user: 触发通知的用户
            subject_type: 主体类型
            subject_id: 主体ID
            data: 额外数据

        Returns:
            Notification: 创建的通知对象
        """
        # 不给自己发通知
        if from_user and from_user.id == user.id:
            return None

        # 检查是否已存在相同通知（防止重复）
        existing = Notification.objects.filter(
            user=user,
            type=type,
            subject_type=subject_type,
            subject_id=subject_id,
            is_read=False,
        ).first()

        if existing:
            # 更新现有通知
            existing.from_user = from_user
            existing.data = data or {}
            existing.created_at = timezone.now()
            existing.save()
            return existing

        notification = Notification.objects.create(
            user=user,
            from_user=from_user,
            type=type,
            subject_type=subject_type,
            subject_id=subject_id,
            data=data or {},
        )

        # 发送WebSocket实时通知
        NotificationService._send_websocket_notification(notification)

        return notification

    @staticmethod
    def get_notification_list(
        user: User,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Notification], int, int]:
        """
        获取通知列表

        Args:
            user: 用户
            is_read: 是否已读（None表示全部）
            type: 通知类型
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Notification], int, int]: (通知列表, 总数, 未读数)
        """
        queryset = Notification.objects.filter(
            user=user
        ).select_related('from_user')

        # 过滤已读状态
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read)

        # 过滤通知类型
        if type:
            queryset = queryset.filter(type=type)

        # 排序
        queryset = queryset.order_by('-created_at')

        # 统计
        total = queryset.count()
        unread_count = Notification.objects.filter(user=user, is_read=False).count()

        # 分页
        offset = (page - 1) * limit
        notifications = list(queryset[offset:offset + limit])

        return notifications, total, unread_count

    @staticmethod
    def get_notification_by_id(notification_id: int, user: User) -> Optional[Notification]:
        """
        获取通知详情

        Args:
            notification_id: 通知ID
            user: 用户（用于权限检查）

        Returns:
            Optional[Notification]: 通知对象
        """
        try:
            notification = Notification.objects.select_related('from_user').get(
                id=notification_id,
                user=user
            )
            return notification
        except Notification.DoesNotExist:
            return None

    @staticmethod
    def mark_as_read(notification_id: int, user: User) -> bool:
        """
        标记通知为已读

        Args:
            notification_id: 通知ID
            user: 用户

        Returns:
            bool: 是否成功
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user: User) -> int:
        """
        标记所有通知为已读

        Args:
            user: 用户

        Returns:
            int: 标记的数量
        """
        count = Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        return count

    @staticmethod
    def delete_notification(notification_id: int, user: User) -> bool:
        """
        删除通知

        Args:
            notification_id: 通知ID
            user: 用户

        Returns:
            bool: 是否成功
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.delete()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def delete_all_read(user: User) -> int:
        """
        删除所有已读通知

        Args:
            user: 用户

        Returns:
            int: 删除的数量
        """
        count, _ = Notification.objects.filter(
            user=user,
            is_read=True
        ).delete()
        return count

    @staticmethod
    def get_unread_count(user: User) -> int:
        """
        获取未读通知数量

        Args:
            user: 用户

        Returns:
            int: 未读数量
        """
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def get_stats(user: User) -> dict:
        """
        获取通知统计

        Args:
            user: 用户

        Returns:
            dict: 统计数据
        """
        total = Notification.objects.filter(user=user).count()
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        read_count = total - unread_count

        return {
            'total': total,
            'unread_count': unread_count,
            'read_count': read_count,
        }

    @staticmethod
    def notify_discussion_reply(discussion_id: int, post_id: int, from_user: User):
        """
        通知讨论有新回复

        Args:
            discussion_id: 讨论ID
            post_id: 帖子ID
            from_user: 回复者
        """
        from apps.discussions.models import Discussion
        from apps.posts.models import Post

        try:
            discussion = Discussion.objects.select_related('user').get(id=discussion_id)
            post = Post.objects.only('id', 'number').get(id=post_id)

            # 通知讨论作者
            if discussion.user and discussion.user.id != from_user.id:
                NotificationService.create_notification(
                    user=discussion.user,
                    type=NotificationService.TYPE_DISCUSSION_REPLY,
                    from_user=from_user,
                    subject_type='discussion',
                    subject_id=discussion_id,
                    data={
                        'discussion_id': discussion_id,
                        'discussion_title': discussion.title,
                        'post_id': post_id,
                        'post_number': post.number,
                    }
                )

            subscribed_user_ids = list(
                DiscussionUser.objects.filter(
                    discussion_id=discussion_id,
                    is_subscribed=True,
                ).exclude(
                    user_id=from_user.id
                ).values_list('user_id', flat=True)
            )

            if subscribed_user_ids:
                subscribed_users = User.objects.filter(id__in=subscribed_user_ids)
                for subscriber in subscribed_users:
                    if subscriber.preferences.get('notify_new_post', True):
                        NotificationService.create_notification(
                            user=subscriber,
                            type=NotificationService.TYPE_DISCUSSION_REPLY,
                            from_user=from_user,
                            subject_type='discussion',
                            subject_id=discussion_id,
                            data={
                                'discussion_id': discussion_id,
                                'discussion_title': discussion.title,
                                'post_id': post_id,
                                'post_number': post.number,
                            }
                        )
        except (Discussion.DoesNotExist, Post.DoesNotExist):
            pass

    @staticmethod
    def notify_post_reply(reply_to_post_id: int, post_id: int, from_user: User):
        """
        通知某条帖子被回复

        Args:
            reply_to_post_id: 被回复帖子ID
            post_id: 新回复帖子ID
            from_user: 回复者
        """
        from apps.posts.models import Post

        try:
            reply_to_post = Post.objects.select_related('user', 'discussion__user').get(id=reply_to_post_id)
            post = Post.objects.only('id', 'number').get(id=post_id)

            if (
                reply_to_post.user
                and reply_to_post.user.id != from_user.id
                and reply_to_post.user.id != getattr(reply_to_post.discussion.user, 'id', None)
            ):
                NotificationService.create_notification(
                    user=reply_to_post.user,
                    type=NotificationService.TYPE_POST_REPLY,
                    from_user=from_user,
                    subject_type='post',
                    subject_id=reply_to_post_id,
                    data={
                        'post_id': post_id,
                        'post_number': post.number,
                        'discussion_id': reply_to_post.discussion_id,
                        'discussion_title': reply_to_post.discussion.title,
                        'reply_to_post_id': reply_to_post_id,
                        'reply_to_post_number': reply_to_post.number,
                    }
                )
        except Post.DoesNotExist:
            pass

    @staticmethod
    def notify_post_liked(post_id: int, from_user: User):
        """
        通知帖子被点赞

        Args:
            post_id: 帖子ID
            from_user: 点赞者
        """
        from apps.posts.models import Post

        try:
            post = Post.objects.select_related('user', 'discussion').get(id=post_id)

            # 通知帖子作者
            if post.user and post.user.id != from_user.id:
                NotificationService.create_notification(
                    user=post.user,
                    type=NotificationService.TYPE_POST_LIKED,
                    from_user=from_user,
                    subject_type='post',
                    subject_id=post_id,
                    data={
                        'post_id': post_id,
                        'post_number': post.number,
                        'discussion_id': post.discussion_id,
                        'discussion_title': post.discussion.title,
                    }
                )
        except Post.DoesNotExist:
            pass

    @staticmethod
    def notify_user_mentioned(post_id: int, mentioned_user: User, from_user: User):
        """
        通知用户被@提及

        Args:
            post_id: 帖子ID
            mentioned_user: 被提及的用户
            from_user: 提及者
        """
        from apps.posts.models import Post

        try:
            post = Post.objects.select_related('discussion').get(id=post_id)

            NotificationService.create_notification(
                user=mentioned_user,
                type=NotificationService.TYPE_USER_MENTIONED,
                from_user=from_user,
                subject_type='post',
                subject_id=post_id,
                data={
                    'post_id': post_id,
                    'post_number': post.number,
                    'discussion_id': post.discussion_id,
                    'discussion_title': post.discussion.title,
                }
            )
        except Post.DoesNotExist:
            pass

    @staticmethod
    def _send_websocket_notification(notification):
        """
        发送WebSocket实时通知

        Args:
            notification: 通知对象
        """
        try:
            from apps.core.websocket_service import WebSocketService

            notification_data = {
                'id': notification.id,
                'type': notification.type,
                'from_user': {
                    'id': notification.from_user.id,
                    'username': notification.from_user.username,
                    'display_name': notification.from_user.display_name,
                    'avatar_url': notification.from_user.avatar_url,
                } if notification.from_user else None,
                'data': notification.data,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
            }

            WebSocketService.send_notification_to_user(
                user_id=notification.user_id,
                notification_data=notification_data
            )
        except Exception:
            # WebSocket发送失败不影响主流程
            pass
