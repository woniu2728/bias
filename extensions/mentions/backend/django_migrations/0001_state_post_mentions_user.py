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
                    name="PostMentionsUser",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "mentions_user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="mentioned_in_posts",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "post",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="mentions",
                                to="posts.post",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "post_mentions_user",
                        "indexes": [
                            models.Index(fields=["post"], name="post_mentio_post_id_b5c7ae_idx"),
                            models.Index(fields=["mentions_user"], name="post_mentio_mention_4f2ed3_idx"),
                        ],
                        "unique_together": {("post", "mentions_user")},
                    },
                ),
            ],
        ),
    ]
