from django.conf import settings
from django.db import models


class PostLike(models.Model):
    """
    帖子点赞记录，由 likes 扩展拥有。
    """

    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "likes"
        db_table = "post_likes"
        unique_together = [["post", "user"]]
        indexes = [
            models.Index(fields=["post"], name="post_likes_post_id_c6421f_idx"),
            models.Index(fields=["user"], name="post_likes_user_id_7d46ab_idx"),
        ]

    def __str__(self):
        return f"{self.user.username} likes Post #{self.post.number}"
