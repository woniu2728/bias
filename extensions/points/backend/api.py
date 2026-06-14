from __future__ import annotations

from ninja import Router

from apps.core.extensions.platform import api_error
from apps.core.extensions.platform import AuthBearer
from extensions.points.backend.services import get_account, list_ledger, serialize_account


router = Router()


@router.get("/points/me", auth=AuthBearer(), tags=["Points"])
def current_points(request):
    try:
        return serialize_account(get_account(request.auth))
    except ValueError as exc:
        return api_error(str(exc), status=400)


@router.get("/points/ledger", auth=AuthBearer(), tags=["Points"])
def points_ledger(request, page: int = 1, limit: int = 20):
    try:
        return list_ledger(request.auth, page=page, limit=limit)
    except ValueError as exc:
        return api_error(str(exc), status=400)
