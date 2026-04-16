from django.db import models
from django.utils.text import slugify
from apps.discussions.models import Discussion


class Tag(models.Model):
    """
    标签模型 - 对标Flarum的Tag模型
    """
    ACCESS_PUBLIC = "public"
    ACCESS_MEMBERS = "members"
    ACCESS_STAFF = "staff"
    ACCESS_SCOPE_CHOICES = [
        (ACCESS_PUBLIC, "所有人"),
        (ACCESS_MEMBERS, "已登录用户"),
        (ACCESS_STAFF, "仅管理员"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)

    # 样式
    color = models.CharField(max_length=20, blank=True)
    icon = models.CharField(max_length=100, blank=True)
    background_url = models.URLField(max_length=500, blank=True)

    # 位置（用于排序）
    position = models.IntegerField(default=0, db_index=True)

    # 父标签（支持层级结构）
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children'
    )

    # 状态标志
    is_hidden = models.BooleanField(default=False)
    is_restricted = models.BooleanField(default=False)  # 是否限制发帖
    view_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_PUBLIC)
    start_discussion_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_MEMBERS)
    reply_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_MEMBERS)

    # 统计数据
    discussion_count = models.IntegerField(default=0)
    last_posted_at = models.DateTimeField(null=True, blank=True)
    last_posted_discussion = models.ForeignKey(
        Discussion, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tags'
        ordering = ['position', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['parent']),
            models.Index(fields=['position']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 自动生成slug
        if not self.slug:
            from django.utils.text import slugify
            import uuid

            # 尝试使用名称生成slug
            self.slug = slugify(self.name, allow_unicode=True)

            # 如果slug为空（比如纯中文），使用UUID
            if not self.slug:
                self.slug = str(uuid.uuid4())[:8]

            # 确保slug唯一
            original_slug = self.slug
            counter = 1
            while Tag.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def increment_discussion_count(self):
        """增加讨论数"""
        self.discussion_count += 1
        self.save(update_fields=['discussion_count'])

    def decrement_discussion_count(self):
        """减少讨论数"""
        if self.discussion_count > 0:
            self.discussion_count -= 1
            self.save(update_fields=['discussion_count'])


class DiscussionTag(models.Model):
    """
    讨论-标签关联表 - 对标Flarum的discussion_tag表
    """
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='discussion_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='discussion_tags')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_tag'
        unique_together = [['discussion', 'tag']]
        indexes = [
            models.Index(fields=['discussion']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f"{self.discussion.title} - {self.tag.name}"
