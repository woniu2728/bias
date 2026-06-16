from __future__ import annotations

from ninja import Body, Router

from apps.core.admin_auth import require_staff
from apps.core.extensions.recovery import (
    advance_extension_bisect,
    get_extension_bisect_state,
    start_extension_bisect,
    stop_extension_bisect,
)
from apps.core.extensions.registry import get_extension_registry
from apps.core.jwt_auth import AccessTokenAuth


router = Router()


@router.get("/extensions/bisect", auth=AccessTokenAuth(), tags=["Admin"])
def get_admin_extension_bisect(request):
    denied = require_staff(request)
    if denied:
        return denied
    return {"bisect": get_extension_bisect_state()}


@router.post("/extensions/bisect/start", auth=AccessTokenAuth(), tags=["Admin"])
def start_admin_extension_bisect(request, payload: dict = Body(default={})):
    denied = require_staff(request)
    if denied:
        return denied
    requested_ids = payload.get("extension_ids")
    if requested_ids is None:
        requested_ids = [
            extension.id
            for extension in get_extension_registry().get_enabled_extensions()
        ]
    return {"bisect": start_extension_bisect(requested_ids)}


@router.post("/extensions/bisect/step", auth=AccessTokenAuth(), tags=["Admin"])
def step_admin_extension_bisect(request, payload: dict = Body(...)):
    denied = require_staff(request)
    if denied:
        return denied
    return {"bisect": advance_extension_bisect(bool(payload.get("issue_present")))}


@router.post("/extensions/bisect/stop", auth=AccessTokenAuth(), tags=["Admin"])
def stop_admin_extension_bisect(request):
    denied = require_staff(request)
    if denied:
        return denied
    return {"bisect": stop_extension_bisect()}
