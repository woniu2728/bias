from django.db import models

from extensions.posts.backend.models import Post
from apps.users.models import User


class PostFlag(models.Model):
    """
    帖子举报记录，由 flags 扩展拥有。
    """

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_OPEN, "待处理"),
        (STATUS_RESOLVED, "已处理"),
        (STATUS_IGNORED, "已忽略"),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="flags")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_flags")
    reason = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_post_flags",
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        app_label = "flags"
        db_table = "post_flags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["post"], name="post_flags_post_id_8dc228_idx"),
            models.Index(fields=["user"], name="post_flags_user_id_3dffd5_idx"),
            models.Index(fields=["status"], name="post_flags_status_d951be_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user", "status"],
                condition=models.Q(status="open"),
                name="unique_open_post_flag_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user.username} flagged Post #{self.post.number}"
