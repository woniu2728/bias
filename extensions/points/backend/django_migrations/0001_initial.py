import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PointAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("balance", models.IntegerField(default=0)),
                ("earned_total", models.IntegerField(default=0)),
                ("spent_total", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="point_account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "point_accounts",
                "indexes": [
                    models.Index(fields=["user"], name="point_acct_user_id_idx"),
                    models.Index(fields=["balance"], name="point_acct_balance_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PointLedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delta", models.IntegerField()),
                ("balance_after", models.IntegerField()),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("award", "奖励"),
                            ("spend", "消费"),
                            ("refund", "退款"),
                            ("adjust", "调整"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("reason", models.CharField(db_index=True, max_length=120)),
                ("source_type", models.CharField(blank=True, db_index=True, max_length=80)),
                ("source_id", models.CharField(blank=True, db_index=True, max_length=80)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="point_ledger_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "point_ledger_entries",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="point_ledger_user_created_idx"),
                    models.Index(fields=["reason"], name="point_ledger_reason_idx"),
                    models.Index(fields=["source_type", "source_id"], name="point_ledger_source_idx"),
                ],
            },
        ),
    ]

