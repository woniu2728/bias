from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.users.models import User


class Notification(models.Model):
    """
    通知模型
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    from_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications'
    )

    # 通知类型（discussionReply, postLiked, userMentioned等）
    type = models.CharField(max_length=100, db_index=True)

    # 通知主体（使用GenericForeignKey支持多种模型）
    subject_type = models.CharField(max_length=100, null=True, blank=True)
    subject_id = models.IntegerField(null=True, blank=True)

    # 额外数据（JSON格式）
    data = models.JSONField(default=dict, blank=True)

    # 阅读状态
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['subject_type', 'subject_id']),
        ]

    def __str__(self):
        return f"{self.type} for {self.user.username}"

    def mark_as_read(self):
        """标记为已读"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
