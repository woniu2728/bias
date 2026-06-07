import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("posts", "0004_post_approval_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="PostLike",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "post",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="likes",
                                to="posts.post",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="post_likes",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "post_likes",
                        "indexes": [
                            models.Index(fields=["post"], name="post_likes_post_id_c6421f_idx"),
                            models.Index(fields=["user"], name="post_likes_user_id_7d46ab_idx"),
                        ],
                        "unique_together": {("post", "user")},
                    },
                ),
            ],
        ),
    ]
