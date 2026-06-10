"""
通知系统业务逻辑层
"""
from typing import Any, Optional, List, Tuple
from django.db.models import Q, Count
from django.core.cache import cache
from django.utils import timezone
from apps.core.domain_events import dispatch_forum_event_after_commit
from apps.core.extensions.runtime_access import (
    get_runtime_discussion_reply_notification_context,
)
from extensions.notifications.backend.events import NotificationCreatedEvent
from extensions.notifications.backend.models import Notification
from apps.core.extensions.runtime_access import (
    get_runtime_post_notification_context,
    get_runtime_post_reply_notification_context,
)
from apps.core.extensions.runtime_access import (
    get_runtime_user_preference,
)


UNREAD_COUNT_CACHE_KEY = "notifications.unread_count.{user_id}"
UNREAD_COUNT_CACHE_TIMEOUT = 60 * 5


class NotificationService:
    """通知服务"""

    # 通知类型常量
    TYPE_DISCUSSION_REPLY = 'discussionReply'
    TYPE_POST_LIKED = 'postLiked'
    TYPE_USER_MENTIONED = 'userMentioned'
    TYPE_POST_REPLY = 'postReply'
    TYPE_DISCUSSION_APPROVED = 'discussionApproved'
    TYPE_DISCUSSION_REJECTED = 'discussionRejected'
    TYPE_POST_APPROVED = 'postApproved'
    TYPE_POST_REJECTED = 'postRejected'
    TYPE_USER_SUSPENDED = 'userSuspended'
    TYPE_USER_UNSUSPENDED = 'userUnsuspended'

    @staticmethod
    def is_notification_enabled(user: Any | None, type_code: str) -> bool:
        if not user:
            return False

        from apps.core.forum_registry import get_forum_registry

        definition = get_forum_registry().get_notification_type(type_code)
        if not definition or not definition.preference_key:
            return True

        return get_runtime_user_preference(
            user,
            definition.preference_key,
            fallback=definition.preference_default_enabled,
        )

    @staticmethod
    def _unread_count_cache_key(user_id: int) -> str:
        return UNREAD_COUNT_CACHE_KEY.format(user_id=user_id)

    @staticmethod
    def invalidate_unread_count(user_id: int) -> None:
        if not user_id:
            return
        try:
            cache.delete(NotificationService._unread_count_cache_key(user_id))
        except Exception:
            return None

    @staticmethod
    def invalidate_unread_counts(user_ids: List[int]) -> None:
        for user_id in set(user_ids or []):
            NotificationService.invalidate_unread_count(user_id)

    @staticmethod
    def create_notification(
        user: Any,
        type: str,
        from_user: Optional[Any] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[int] = None,
        data: Optional[dict] = None,
        allow_merge: bool = True,
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

        if not NotificationService.is_notification_enabled(user, type):
            return None

        # 检查是否已存在相同通知（防止重复）
        existing = None
        if allow_merge:
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

        NotificationService.invalidate_unread_count(user.id)
        NotificationService._dispatch_notifications_after_commit([notification.id])

        return notification

    @staticmethod
    def create_notifications_bulk(notifications: List[Notification]) -> List[Notification]:
        if not notifications:
            return []

        created = Notification.objects.bulk_create(notifications)
        NotificationService.invalidate_unread_counts([item.user_id for item in created])
        NotificationService._dispatch_notifications_after_commit([item.id for item in created if item.id])
        return created

    @staticmethod
    def _dispatch_notifications_after_commit(notification_ids: List[int]):
        if not notification_ids:
            return

        dispatch_forum_event_after_commit(
            NotificationCreatedEvent(notification_ids=tuple(int(item) for item in notification_ids if item)),
        )

    @staticmethod
    def _collect_type_counts(queryset) -> dict:
        return {
            item["type"]: item["count"]
            for item in queryset.values("type").annotate(count=Count("id"))
        }

    @staticmethod
    def _build_filtered_queryset(
        user: Any,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        discussion_id: Optional[int] = None,
    ):
        queryset = Notification.objects.filter(user=user)

        if is_read is not None:
            queryset = queryset.filter(is_read=is_read)

        if type:
            queryset = queryset.filter(type=type)

        if discussion_id is not None:
            queryset = queryset.filter(
                Q(subject_type='discussion', subject_id=discussion_id)
                | Q(data__discussion_id=discussion_id)
            )

        return queryset

    @staticmethod
    def get_notification_list(
        user: Any,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        preload=None,
    ) -> Tuple[List[Notification], int, int, dict, dict]:
        """
        获取通知列表

        Args:
            user: 用户
            is_read: 是否已读（None表示全部）
            type: 通知类型
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Notification], int, int, dict, dict]: (通知列表, 总数, 未读数, 各类型总数, 各类型未读数)
        """
        base_queryset = Notification.objects.filter(user=user)
        queryset = NotificationService._build_filtered_queryset(
            user=user,
            is_read=is_read,
            type=type,
        )
        if preload is not None:
            queryset = preload(queryset)

        type_counts = NotificationService._collect_type_counts(base_queryset)
        unread_type_counts = NotificationService._collect_type_counts(base_queryset.filter(is_read=False))

        # 排序
        queryset = queryset.order_by('-created_at', '-id')

        # 统计
        total = queryset.count()
        unread_count = NotificationService.get_unread_count(user)

        # 分页
        offset = (page - 1) * limit
        notifications = list(queryset[offset:offset + limit])

        return notifications, total, unread_count, type_counts, unread_type_counts

    @staticmethod
    def get_notification_by_id(notification_id: int, user: Any, preload=None) -> Optional[Notification]:
        """
        获取通知详情

        Args:
            notification_id: 通知ID
            user: 用户（用于权限检查）

        Returns:
            Optional[Notification]: 通知对象
        """
        try:
            queryset = Notification.objects.filter(user=user)
            if preload is not None:
                queryset = preload(queryset)
            notification = queryset.get(id=notification_id)
            return notification
        except Notification.DoesNotExist:
            return None

    @staticmethod
    def mark_as_read(notification_id: int, user: Any) -> bool:
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
            was_unread = not notification.is_read
            notification.mark_as_read()
            if was_unread:
                NotificationService.invalidate_unread_count(user.id)
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user: Any) -> int:
        """
        标记所有通知为已读

        Args:
            user: 用户

        Returns:
            int: 标记的数量
        """
        count, _ = NotificationService.mark_filtered_as_read(user)
        return count

    @staticmethod
    def mark_filtered_as_read(
        user: Any,
        type: Optional[str] = None,
        discussion_id: Optional[int] = None,
    ) -> Tuple[int, dict]:
        queryset = NotificationService._build_filtered_queryset(
            user=user,
            is_read=False,
            type=type,
            discussion_id=discussion_id,
        )
        type_counts = NotificationService._collect_type_counts(queryset)

        if not type_counts:
            return 0, {}

        count = queryset.update(
            is_read=True,
            read_at=timezone.now()
        )
        if count:
            NotificationService.invalidate_unread_count(user.id)
        return count, type_counts

    @staticmethod
    def delete_notification(notification_id: int, user: Any) -> bool:
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
            was_unread = not notification.is_read
            notification.delete()
            if was_unread:
                NotificationService.invalidate_unread_count(user.id)
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def delete_all_read(user: Any) -> int:
        """
        删除所有已读通知

        Args:
            user: 用户

        Returns:
            int: 删除的数量
        """
        count, _ = NotificationService.delete_filtered_read(user)
        return count

    @staticmethod
    def delete_filtered_read(
        user: Any,
        type: Optional[str] = None,
        discussion_id: Optional[int] = None,
    ) -> Tuple[int, dict]:
        queryset = NotificationService._build_filtered_queryset(
            user=user,
            is_read=True,
            type=type,
            discussion_id=discussion_id,
        )
        type_counts = NotificationService._collect_type_counts(queryset)

        if not type_counts:
            return 0, {}

        count, _ = queryset.delete()
        return count, type_counts

    @staticmethod
    def get_unread_count(user: Any) -> int:
        """
        获取未读通知数量

        Args:
            user: 用户

        Returns:
            int: 未读数量
        """
        cache_key = NotificationService._unread_count_cache_key(user.id)
        try:
            cached = cache.get(cache_key)
        except Exception:
            cached = None

        if cached is not None:
            return int(cached)

        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        try:
            cache.set(cache_key, unread_count, UNREAD_COUNT_CACHE_TIMEOUT)
        except Exception:
            pass
        return unread_count

    @staticmethod
    def get_stats(user: Any) -> dict:
        """
        获取通知统计

        Args:
            user: 用户

        Returns:
            dict: 统计数据
        """
        total = Notification.objects.filter(user=user).count()
        unread_count = NotificationService.get_unread_count(user)
        read_count = total - unread_count

        return {
            'total': total,
            'unread_count': unread_count,
            'read_count': read_count,
        }

    @staticmethod
    def notify_discussion_reply(discussion_id: int, post_id: int, from_user: Any):
        """
        通知讨论有新回复

        Args:
            discussion_id: 讨论ID
            post_id: 帖子ID
            from_user: 回复者
        """
        context = get_runtime_discussion_reply_notification_context(discussion_id, post_id, from_user)
        if not context:
            return

        payload = dict(context.get("payload") or {})
        notifications = []
        discussion_author = context.get("discussion_author")
        if discussion_author and discussion_author.id != getattr(from_user, "id", None):
            notifications.append(
                Notification(
                    user=discussion_author,
                    from_user=from_user,
                    type=NotificationService.TYPE_DISCUSSION_REPLY,
                    subject_type='discussion',
                    subject_id=discussion_id,
                    data=payload,
                )
            )

        for subscriber in context.get("subscribers") or ():
            if NotificationService.is_notification_enabled(subscriber, NotificationService.TYPE_DISCUSSION_REPLY):
                notifications.append(
                    Notification(
                        user=subscriber,
                        from_user=from_user,
                        type=NotificationService.TYPE_DISCUSSION_REPLY,
                        subject_type='discussion',
                        subject_id=discussion_id,
                        data=payload,
                    )
                )
        NotificationService.create_notifications_bulk(notifications)

    @staticmethod
    def notify_post_reply(reply_to_post_id: int, post_id: int, from_user: Any):
        """
        通知某条帖子被回复

        Args:
            reply_to_post_id: 被回复帖子ID
            post_id: 新回复帖子ID
            from_user: 回复者
        """
        context = get_runtime_post_reply_notification_context(reply_to_post_id, post_id, from_user)
        if not context:
            return

        NotificationService.create_notification(
            user=context["recipient"],
            type=NotificationService.TYPE_POST_REPLY,
            from_user=from_user,
            subject_type='post',
            subject_id=reply_to_post_id,
            allow_merge=False,
            data=dict(context.get("payload") or {}),
        )

    @staticmethod
    def notify_post_liked(post_id: int, from_user: Any):
        """
        通知帖子被点赞

        Args:
            post_id: 帖子ID
            from_user: 点赞者
        """
        context = get_runtime_post_notification_context(post_id)
        if not context:
            return

        author = context.get("author")
        if author and author.id != getattr(from_user, "id", None):
            NotificationService.create_notification(
                user=author,
                type=NotificationService.TYPE_POST_LIKED,
                from_user=from_user,
                subject_type='post',
                subject_id=post_id,
                data=dict(context.get("payload") or {}),
            )

    @staticmethod
    def notify_user_mentioned(post_id: int, mentioned_user: Any, from_user: Any):
        """
        通知用户被@提及

        Args:
            post_id: 帖子ID
            mentioned_user: 被提及的用户
            from_user: 提及者
        """
        context = get_runtime_post_notification_context(post_id)
        if not context:
            return

        NotificationService.create_notification(
            user=mentioned_user,
            type=NotificationService.TYPE_USER_MENTIONED,
            from_user=from_user,
            subject_type='post',
            subject_id=post_id,
            data=dict(context.get("payload") or {}),
        )

    @staticmethod
    def notify_discussion_approved(discussion, admin_user: Any, note: str = ""):
        if not getattr(discussion, "user", None):
            return

        NotificationService.create_notification(
            user=discussion.user,
            type=NotificationService.TYPE_DISCUSSION_APPROVED,
            from_user=admin_user,
            subject_type='discussion',
            subject_id=discussion.id,
            data={
                'discussion_id': discussion.id,
                'discussion_title': discussion.title,
                'approval_note': note or "",
            }
        )

    @staticmethod
    def notify_discussion_rejected(discussion, admin_user: Any, note: str = ""):
        if not getattr(discussion, "user", None):
            return

        NotificationService.create_notification(
            user=discussion.user,
            type=NotificationService.TYPE_DISCUSSION_REJECTED,
            from_user=admin_user,
            subject_type='discussion',
            subject_id=discussion.id,
            data={
                'discussion_id': discussion.id,
                'discussion_title': discussion.title,
                'approval_note': note or "",
            }
        )

    @staticmethod
    def notify_post_approved(post, admin_user: Any, note: str = ""):
        if not getattr(post, "user", None):
            return

        NotificationService.create_notification(
            user=post.user,
            type=NotificationService.TYPE_POST_APPROVED,
            from_user=admin_user,
            subject_type='post',
            subject_id=post.id,
            data={
                'discussion_id': post.discussion_id,
                'discussion_title': post.discussion.title if getattr(post, "discussion", None) else "",
                'post_id': post.id,
                'post_number': post.number,
                'approval_note': note or "",
            }
        )

    @staticmethod
    def notify_post_rejected(post, admin_user: Any, note: str = ""):
        if not getattr(post, "user", None):
            return

        NotificationService.create_notification(
            user=post.user,
            type=NotificationService.TYPE_POST_REJECTED,
            from_user=admin_user,
            subject_type='post',
            subject_id=post.id,
            data={
                'discussion_id': post.discussion_id,
                'discussion_title': post.discussion.title if getattr(post, "discussion", None) else "",
                'post_id': post.id,
                'post_number': post.number,
                'approval_note': note or "",
            }
        )

    @staticmethod
    def notify_user_suspended(user: Any, admin_user: Optional[Any] = None):
        NotificationService.create_notification(
            user=user,
            type=NotificationService.TYPE_USER_SUSPENDED,
            from_user=admin_user,
            subject_type='user',
            subject_id=user.id,
            data={
                'suspended_until': user.suspended_until.isoformat() if user.suspended_until else None,
                'suspend_reason': user.suspend_reason or "",
                'suspend_message': user.suspend_message or "",
            }
        )

    @staticmethod
    def notify_user_unsuspended(user: Any, admin_user: Optional[Any] = None):
        NotificationService.create_notification(
            user=user,
            type=NotificationService.TYPE_USER_UNSUSPENDED,
            from_user=admin_user,
            subject_type='user',
            subject_id=user.id,
            data={}
        )

    @staticmethod
    @staticmethod
    def load_notifications_for_realtime(notification_ids: List[int]):
        if not notification_ids:
            return []

        notifications = list(
            Notification.objects.filter(id__in=notification_ids).select_related('from_user')
        )
        notification_map = {notification.id: notification for notification in notifications}
        return [
            notification_map[notification_id]
            for notification_id in notification_ids
            if notification_id in notification_map
        ]


