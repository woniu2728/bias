from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    自定义用户模型 - 对标Flarum的User模型
    """
    # 覆盖username字段，添加唯一约束
    username = models.CharField(max_length=100, unique=True, db_index=True)

    # 显示名称
    display_name = models.CharField(max_length=100, blank=True)

    # 个人简介
    bio = models.TextField(blank=True)

    # 头像URL
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    # 邮箱确认状态
    is_email_confirmed = models.BooleanField(default=False)

    # 时间戳
    joined_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    marked_all_as_read_at = models.DateTimeField(null=True, blank=True)
    read_notifications_at = models.DateTimeField(null=True, blank=True)

    # 统计数据
    discussion_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)

    # 用户偏好设置（JSON字段）
    preferences = models.JSONField(default=dict, blank=True)
    preferences_ui = models.JSONField(default=dict, blank=True)

    # 封禁相关
    suspended_until = models.DateTimeField(null=True, blank=True)
    suspend_reason = models.TextField(blank=True)
    suspend_message = models.TextField(blank=True)

    class Meta:
        db_table = 'users'
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['last_seen_at']),
        ]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # 如果display_name为空，使用username
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    @property
    def is_suspended(self):
        """检查用户是否被封禁"""
        if self.suspended_until:
            return timezone.now() < self.suspended_until
        return False

    def update_last_seen(self):
        """更新最后活跃时间"""
        now = timezone.now()
        # 只有距离上次更新超过3分钟才更新（避免频繁写入）
        if not self.last_seen_at or (now - self.last_seen_at).seconds > 180:
            self.last_seen_at = now
            self.save(update_fields=['last_seen_at'])

    def increment_discussion_count(self):
        """增加讨论数"""
        self.discussion_count += 1
        self.save(update_fields=['discussion_count'])

    def decrement_discussion_count(self):
        """减少讨论数"""
        if self.discussion_count > 0:
            self.discussion_count -= 1
            self.save(update_fields=['discussion_count'])

    def increment_comment_count(self):
        """增加评论数"""
        self.comment_count += 1
        self.save(update_fields=['comment_count'])

    def decrement_comment_count(self):
        """减少评论数"""
        if self.comment_count > 0:
            self.comment_count -= 1
            self.save(update_fields=['comment_count'])


class Group(models.Model):
    """
    用户组模型 - 对标Flarum的Group模型
    """
    name = models.CharField(max_length=100, unique=True)
    name_singular = models.CharField(max_length=100, blank=True)
    name_plural = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    icon = models.CharField(max_length=100, blank=True)
    is_hidden = models.BooleanField(default=False)

    # 多对多关系
    users = models.ManyToManyField(User, related_name='user_groups', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups'
        ordering = ['name']

    def __str__(self):
        return self.name


class Permission(models.Model):
    """
    权限模型 - 对标Flarum的Permission模型
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='permissions')
    permission = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'permissions'
        unique_together = [['group', 'permission']]
        indexes = [
            models.Index(fields=['group']),
        ]

    def __str__(self):
        return f"{self.group.name} - {self.permission}"


class AccessToken(models.Model):
    """
    访问令牌模型 - 对标Flarum的AccessToken模型
    """
    token = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_tokens')
    type = models.CharField(max_length=50, default='session')
    title = models.CharField(max_length=150, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'access_tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.type}"


class EmailToken(models.Model):
    """
    邮箱验证令牌模型 - 对标Flarum的EmailToken模型
    """
    token = models.CharField(max_length=255, unique=True, db_index=True)
    email = models.EmailField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'email_tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.email}"


class PasswordToken(models.Model):
    """
    密码重置令牌模型 - 对标Flarum的PasswordToken模型
    """
    token = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'password_tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} - Password Reset"
