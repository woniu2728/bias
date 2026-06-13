from __future__ import annotations


def points_service_provider(_host=None):
    from extensions.points.backend.models import PointAccount, PointLedgerEntry
    from extensions.points.backend.services import (
        adjust_points,
        award_points,
        get_account,
        get_balance,
        list_ledger,
        refund_points,
        refund_spend,
        spend_points,
    )
    from extensions.points.backend.settings import get_ai_action_cost, get_points_settings

    return {
        "account_model": PointAccount,
        "ledger_model": PointLedgerEntry,
        "settings": get_points_settings,
        "get_ai_action_cost": get_ai_action_cost,
        "get_account": get_account,
        "get_balance": get_balance,
        "award": award_points,
        "spend": spend_points,
        "refund": refund_points,
        "refund_spend": refund_spend,
        "adjust": adjust_points,
        "list_ledger": list_ledger,
    }

