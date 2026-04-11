from django.db import models
from apps.users.models import User
from apps.discussions.models import Discussion


class Post(models.Model):
    """
    帖子模型 - 对标Flarum的Post模型
    """
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


class PostLike(models.Model):
    """
    帖子点赞模型 - 对标Flarum的post_likes表
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'post_likes'
        unique_together = [['post', 'user']]
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} likes Post #{self.post.number}"


class PostMentionsUser(models.Model):
    """
    帖子提及用户模型 - 对标Flarum的post_mentions_user表
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='mentions')
    mentions_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentioned_in_posts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'post_mentions_user'
        unique_together = [['post', 'mentions_user']]
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['mentions_user']),
        ]

    def __str__(self):
        return f"Post #{self.post.number} mentions {self.mentions_user.username}"


class PostFlag(models.Model):
    """
    帖子举报模型 - 对标 Flarum Flags 扩展的基础能力
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
        db_table = "post_flags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["post"]),
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
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
