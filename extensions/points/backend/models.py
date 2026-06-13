from django.conf import settings
from django.db import models


class PointAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="point_account")
    balance = models.IntegerField(default=0)
    earned_total = models.IntegerField(default=0)
    spent_total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "points"
        db_table = "point_accounts"
        indexes = [
            models.Index(fields=["user"], name="point_acct_user_id_idx"),
            models.Index(fields=["balance"], name="point_acct_balance_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}: {self.balance}"


class PointLedgerEntry(models.Model):
    KIND_AWARD = "award"
    KIND_SPEND = "spend"
    KIND_REFUND = "refund"
    KIND_ADJUST = "adjust"

    KIND_CHOICES = (
        (KIND_AWARD, "奖励"),
        (KIND_SPEND, "消费"),
        (KIND_REFUND, "退款"),
        (KIND_ADJUST, "调整"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="point_ledger_entries")
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    reason = models.CharField(max_length=120, db_index=True)
    source_type = models.CharField(max_length=80, blank=True, db_index=True)
    source_id = models.CharField(max_length=80, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=180, unique=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "points"
        db_table = "point_ledger_entries"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="point_ledger_user_created_idx"),
            models.Index(fields=["reason"], name="point_ledger_reason_idx"),
            models.Index(fields=["source_type", "source_id"], name="point_ledger_source_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.delta} {self.reason}"

