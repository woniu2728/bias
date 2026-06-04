from django.db import models


class Setting(models.Model):
    """
    Bias 系统设置模型
    """
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'settings'
        indexes = [
            models.Index(fields=['key']),
        ]

    def __str__(self):
        return self.key


class AuditLog(models.Model):
    """
    审计日志模型 - 用于记录管理员操作
    """
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100, db_index=True)

    # 操作目标
    target_type = models.CharField(max_length=100, null=True, blank=True)
    target_id = models.IntegerField(null=True, blank=True)

    # 请求信息
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # 额外数据
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['action']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.action} by {self.user.username if self.user else 'Unknown'}"


class ExtensionInstallation(models.Model):
    """
    扩展安装状态 - 用于持久化扩展启停与安装信息
    """
    extension_id = models.CharField(max_length=120, unique=True, db_index=True)
    version = models.CharField(max_length=32, blank=True)
    source = models.CharField(max_length=32, default="filesystem")
    enabled = models.BooleanField(default=True)
    installed = models.BooleanField(default=True)
    booted = models.BooleanField(default=True)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extension_installations"
        ordering = ["extension_id"]
        indexes = [
            models.Index(fields=["extension_id"]),
            models.Index(fields=["enabled"]),
            models.Index(fields=["installed"]),
        ]

    def __str__(self):
        return self.extension_id
