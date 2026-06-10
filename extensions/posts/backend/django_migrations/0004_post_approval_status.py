from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def mark_existing_posts_as_approved(apps, schema_editor):
    Post = apps.get_model("posts", "Post")
    Post.objects.filter(approved_at__isnull=True).update(approved_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0003_postflag"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="approval_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="post",
            name="approval_status",
            field=models.CharField(
                choices=[("approved", "已通过"), ("pending", "待审核"), ("rejected", "已拒绝")],
                db_index=True,
                default="approved",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_posts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(mark_existing_posts_as_approved, migrations.RunPython.noop),
    ]
