from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from extensions.points.backend.models import PointAccount, PointLedgerEntry


class InsufficientPointsError(ValueError):
    def __init__(self, required: int, balance: int):
        self.required = int(required)
        self.balance = int(balance)
        super().__init__(f"积分不足，当前 {self.balance}，需要 {self.required}")


def get_account(user: Any) -> PointAccount:
    if not user or not getattr(user, "is_authenticated", False):
        raise ValueError("需要登录后才能使用积分")
    account, _ = PointAccount.objects.get_or_create(user=user)
    return account


def get_balance(user: Any) -> int:
    return int(get_account(user).balance)


def award_points(
    user: Any,
    amount: int,
    *,
    reason: str,
    idempotency_key: str,
    source_type: str = "",
    source_id: Any = "",
    meta: dict | None = None,
) -> dict:
    amount = int(amount or 0)
    if amount <= 0:
        return {"created": False, "entry": None, "balance": get_balance(user)}
    return _write_entry(
        user,
        delta=amount,
        kind=PointLedgerEntry.KIND_AWARD,
        reason=reason,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        meta=meta,
    )


def spend_points(
    user: Any,
    amount: int,
    *,
    reason: str,
    idempotency_key: str,
    source_type: str = "",
    source_id: Any = "",
    meta: dict | None = None,
) -> dict:
    amount = int(amount or 0)
    if amount <= 0:
        return {"created": False, "entry": None, "balance": get_balance(user)}
    return _write_entry(
        user,
        delta=-amount,
        kind=PointLedgerEntry.KIND_SPEND,
        reason=reason,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        meta=meta,
    )


def refund_points(
    user: Any,
    amount: int,
    *,
    reason: str,
    idempotency_key: str,
    source_type: str = "",
    source_id: Any = "",
    meta: dict | None = None,
) -> dict:
    amount = int(amount or 0)
    if amount <= 0:
        return {"created": False, "entry": None, "balance": get_balance(user)}
    return _write_entry(
        user,
        delta=amount,
        kind=PointLedgerEntry.KIND_REFUND,
        reason=reason,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        meta=meta,
    )


def adjust_points(
    user: Any,
    delta: int,
    *,
    reason: str,
    idempotency_key: str,
    source_type: str = "",
    source_id: Any = "",
    meta: dict | None = None,
) -> dict:
    delta = int(delta or 0)
    if delta == 0:
        return {"created": False, "entry": None, "balance": get_balance(user)}
    return _write_entry(
        user,
        delta=delta,
        kind=PointLedgerEntry.KIND_ADJUST,
        reason=reason,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        meta=meta,
    )


def refund_spend(
    user: Any,
    spend_idempotency_key: str,
    *,
    reason: str = "refund",
    meta: dict | None = None,
) -> dict | None:
    spend_key = str(spend_idempotency_key or "").strip()
    if not spend_key:
        return None
    spend = PointLedgerEntry.objects.filter(
        user=user,
        idempotency_key=spend_key,
        delta__lt=0,
    ).first()
    if spend is None:
        return None
    return refund_points(
        user,
        abs(int(spend.delta)),
        reason=reason,
        idempotency_key=f"refund:{spend_key}",
        source_type=spend.source_type,
        source_id=spend.source_id,
        meta={
            "refund_of": spend_key,
            **dict(meta or {}),
        },
    )


def list_ledger(user: Any, *, page: int = 1, limit: int = 20) -> dict:
    page = max(1, int(page or 1))
    limit = max(1, min(int(limit or 20), 100))
    queryset = PointLedgerEntry.objects.filter(user=user).order_by("-created_at", "-id")
    total = queryset.count()
    start = (page - 1) * limit
    entries = [
        serialize_ledger_entry(item)
        for item in queryset[start:start + limit]
    ]
    return {
        "data": entries,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
        },
    }


def serialize_account(account: PointAccount) -> dict:
    return {
        "balance": int(account.balance),
        "earned_total": int(account.earned_total),
        "spent_total": int(account.spent_total),
        "updated_at": account.updated_at,
    }


def serialize_ledger_entry(entry: PointLedgerEntry | None) -> dict | None:
    if entry is None:
        return None
    return {
        "id": entry.id,
        "delta": int(entry.delta),
        "balance_after": int(entry.balance_after),
        "kind": entry.kind,
        "reason": entry.reason,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "idempotency_key": entry.idempotency_key,
        "meta": entry.meta or {},
        "created_at": entry.created_at,
    }


def _write_entry(
    user: Any,
    *,
    delta: int,
    kind: str,
    reason: str,
    idempotency_key: str,
    source_type: str,
    source_id: Any,
    meta: dict | None,
) -> dict:
    if not user or not getattr(user, "is_authenticated", False):
        raise ValueError("需要登录后才能使用积分")
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("积分账本缺少幂等键")

    existing = PointLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing is not None:
        return {
            "created": False,
            "entry": serialize_ledger_entry(existing),
            "balance": int(existing.balance_after),
        }

    try:
        with transaction.atomic():
            account, _ = PointAccount.objects.select_for_update().get_or_create(user=user)
            next_balance = int(account.balance) + int(delta)
            if next_balance < 0:
                raise InsufficientPointsError(required=abs(int(delta)), balance=int(account.balance))

            account.balance = next_balance
            if delta > 0 and kind in {PointLedgerEntry.KIND_AWARD, PointLedgerEntry.KIND_ADJUST}:
                account.earned_total = int(account.earned_total) + int(delta)
            if delta < 0:
                account.spent_total = int(account.spent_total) + abs(int(delta))
            account.save(update_fields=["balance", "earned_total", "spent_total", "updated_at"])

            entry = PointLedgerEntry.objects.create(
                user=user,
                delta=int(delta),
                balance_after=next_balance,
                kind=kind,
                reason=str(reason or "").strip() or kind,
                source_type=str(source_type or "").strip(),
                source_id=str(source_id or "").strip(),
                idempotency_key=key,
                meta=dict(meta or {}),
            )
    except IntegrityError:
        existing = PointLedgerEntry.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return {
                "created": False,
                "entry": serialize_ledger_entry(existing),
                "balance": int(existing.balance_after),
            }
        raise

    return {
        "created": True,
        "entry": serialize_ledger_entry(entry),
        "balance": next_balance,
    }
