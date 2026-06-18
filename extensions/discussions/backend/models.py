from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Discussion(models.Model):
    """
    Bias 讨论模型
    """
    APPROVAL_APPROVED = "approved"
    APPROVAL_PENDING = "pending"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_APPROVED, "已通过"),
        (APPROVAL_PENDING, "待审核"),
        (APPROVAL_REJECTED, "已拒绝"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)

    # 作者
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='discussions')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_posted_at = models.DateTimeField(null=True, blank=True)

    # 最后发帖用户
    last_posted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='last_posted_discussions',
    )
    last_post_id = models.IntegerField(null=True, blank=True)
    last_post_number = models.IntegerField(null=True, blank=True)

    # 统计数据
    comment_count = models.IntegerField(default=0)
    participant_count = models.IntegerField(default=0)

    # 第一个帖子
    first_post_id = models.IntegerField(null=True, blank=True)

    # 状态标志
    is_locked = models.BooleanField(default=False)
    is_sticky = models.BooleanField(default=False, db_index=True)
    is_private = models.BooleanField(default=False)

    # 隐藏相关
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hidden_discussions',
    )

    # 审核相关
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_APPROVED,
        db_index=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_discussions',
    )
    approval_note = models.TextField(blank=True)

    # 浏览次数
    view_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'discussions'
        ordering = ['-is_sticky', '-last_posted_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['last_posted_at']),
            models.Index(fields=['is_sticky', 'last_posted_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # 自动生成slug
        if not self.slug:
            self.slug = slugify(self.title)
            # 确保slug唯一
            original_slug = self.slug
            counter = 1
            while Discussion.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def is_hidden(self):
        """检查讨论是否被隐藏"""
        return self.hidden_at is not None

    @property
    def is_approved(self):
        return self.approval_status == self.APPROVAL_APPROVED

    @property
    def is_pending_approval(self):
        return self.approval_status == self.APPROVAL_PENDING


class DiscussionUser(models.Model):
    """
    Bias 讨论-用户状态表
    """
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='user_states')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='discussion_states')

    # 阅读状态
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_post_number = models.IntegerField(default=0)

    # 订阅状态
    is_subscribed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_user'
        unique_together = [['discussion', 'user']]

    def __str__(self):
        return f"{self.user.username} - {self.discussion.title}"
