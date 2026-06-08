from django.db import models

from extensions.posts.backend.models import Post
from extensions.users.backend.models import User


class PostMentionsUser(models.Model):
    """
    帖子提及用户关系，由 mentions 扩展拥有。
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="mentions")
    mentions_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mentioned_in_posts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "mentions"
        db_table = "post_mentions_user"
        unique_together = [["post", "mentions_user"]]
        indexes = [
            models.Index(fields=["post"], name="post_mentio_post_id_b5c7ae_idx"),
            models.Index(fields=["mentions_user"], name="post_mentio_mention_4f2ed3_idx"),
        ]

    def __str__(self):
        return f"Post #{self.post.number} mentions {self.mentions_user.username}"
