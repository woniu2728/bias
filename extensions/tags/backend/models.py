from django.db import models

from extensions.discussions.backend.models import Discussion


class Tag(models.Model):
    """
    标签模型，由 tags 扩展拥有。
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
    color = models.CharField(max_length=20, blank=True)
    icon = models.CharField(max_length=100, blank=True)
    background_url = models.URLField(max_length=500, blank=True)
    position = models.IntegerField(default=0, db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_hidden = models.BooleanField(default=False)
    is_restricted = models.BooleanField(default=False)
    view_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_PUBLIC)
    start_discussion_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_MEMBERS)
    reply_scope = models.CharField(max_length=20, choices=ACCESS_SCOPE_CHOICES, default=ACCESS_MEMBERS)
    discussion_count = models.IntegerField(default=0)
    last_posted_at = models.DateTimeField(null=True, blank=True)
    last_posted_discussion = models.ForeignKey(
        Discussion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tags"
        db_table = "tags"
        ordering = ["position", "name"]
        indexes = [
            models.Index(fields=["slug"], name="tags_slug_c72f9b_idx"),
            models.Index(fields=["parent"], name="tags_parent__7fcc39_idx"),
            models.Index(fields=["position"], name="tags_positio_894349_idx"),
        ]

    def __str__(self):
        return self.name

    def increment_discussion_count(self):
        self.discussion_count += 1
        self.save(update_fields=["discussion_count"])

    def decrement_discussion_count(self):
        if self.discussion_count > 0:
            self.discussion_count -= 1
            self.save(update_fields=["discussion_count"])


class DiscussionTag(models.Model):
    """
    讨论标签关系，由 tags 扩展拥有。
    """

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="discussion_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="discussion_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tags"
        db_table = "discussion_tag"
        unique_together = [["discussion", "tag"]]
        indexes = [
            models.Index(fields=["discussion"], name="discussion__discuss_d30c2c_idx"),
            models.Index(fields=["tag"], name="discussion__tag_id_4f1793_idx"),
        ]

    def __str__(self):
        return f"{self.discussion.title} - {self.tag.name}"
