from django.db import models
from apps.users.models import User
from apps.discussions.models import Discussion


class Post(models.Model):
    """
    Bias 帖子模型
    """
    APPROVAL_APPROVED = "approved"
    APPROVAL_PENDING = "pending"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_APPROVED, "已通过"),
        (APPROVAL_PENDING, "待审核"),
        (APPROVAL_REJECTED, "已拒绝"),
    ]

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='posts')
    number = models.IntegerField()  # 楼层号
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='posts')

    # 帖子类型（comment, discussionRenamed等）
    type = models.CharField(max_length=50, default='comment', db_index=True)

    # 内容
    content = models.TextField(blank=True)
    content_html = models.TextField(blank=True)  # 渲染后的HTML

    # IP地址
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 编辑相关
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_posts'
    )

    # 隐藏相关
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hidden_posts'
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
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_posts',
    )
    approval_note = models.TextField(blank=True)

    # 私密标志
    is_private = models.BooleanField(default=False)

    class Meta:
        db_table = 'posts'
        unique_together = [['discussion', 'number']]
        ordering = ['discussion', 'number']
        indexes = [
            models.Index(fields=['discussion']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"Post #{self.number} in {self.discussion.title}"

    def save(self, *args, **kwargs):
        # 自动设置楼层号
        if not self.number:
            last_post = Post.objects.filter(discussion=self.discussion).order_by('-number').first()
            self.number = (last_post.number + 1) if last_post else 1
        super().save(*args, **kwargs)

    @property
    def is_hidden(self):
        """检查帖子是否被隐藏"""
        return self.hidden_at is not None

    @property
    def is_approved(self):
        return self.approval_status == self.APPROVAL_APPROVED

    @property
    def is_pending_approval(self):
        return self.approval_status == self.APPROVAL_PENDING


from extensions.flags.backend.models import PostFlag  # noqa: E402,F401
from extensions.likes.backend.models import PostLike  # noqa: E402,F401
from extensions.mentions.backend.models import PostMentionsUser  # noqa: E402,F401
