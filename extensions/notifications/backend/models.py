from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    通知记录，由 notifications 扩展拥有。
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    type = models.CharField(max_length=100, db_index=True)
    subject_type = models.CharField(max_length=100, null=True, blank=True)
    subject_id = models.IntegerField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "notifications"
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"], name="notificatio_user_id_e78525_idx"),
            models.Index(fields=["user", "is_read"], name="notificatio_user_id_a4dd5c_idx"),
            models.Index(fields=["created_at"], name="notificatio_created_e4c995_idx"),
            models.Index(fields=["subject_type", "subject_id"], name="notificatio_subject_ba2cbf_idx"),
        ]

    def __str__(self):
        return f"{self.type} for {self.user.username}"

    def mark_as_read(self):
        if not self.is_read:
            from django.utils import timezone

            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
