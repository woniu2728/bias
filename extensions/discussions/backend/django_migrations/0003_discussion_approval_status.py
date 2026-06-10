from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def mark_existing_discussions_as_approved(apps, schema_editor):
    Discussion = apps.get_model("discussions", "Discussion")
    Discussion.objects.filter(approved_at__isnull=True).update(approved_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("discussions", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="discussion",
            name="approval_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="discussion",
            name="approval_status",
            field=models.CharField(
                choices=[("approved", "已通过"), ("pending", "待审核"), ("rejected", "已拒绝")],
                db_index=True,
                default="approved",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="discussion",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discussion",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_discussions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(mark_existing_discussions_as_approved, migrations.RunPython.noop),
    ]
