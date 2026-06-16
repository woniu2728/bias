from __future__ import annotations

from ninja import Body, Router

from apps.core.extensions.platform import api_error
from apps.core.extensions.platform import AccessTokenAuth
from apps.core.extensions.platform import PaginationService
from apps.core.extensions.platform import log_admin_action
from apps.core.extensions.platform import require_forum_permission
from apps.core.extensions.runtime import (
    get_runtime_post_flag_model,
    list_runtime_post_flags,
    resolve_runtime_post_flag,
)
from extensions.flags.backend.handlers import serialize_flag


router = Router()


def _require_admin_permission(request, permission_code: str, message: str):
    return require_forum_permission(request, permission_code, message)


@router.get("/flags", auth=AccessTokenAuth(), tags=["Admin"])
def list_post_flags(request, page: int = 1, limit: int = 20, status: str = "open"):
    denied = _require_admin_permission(request, "admin.flag.view", "没有查看举报队列的权限")
    if denied:
        return denied

    page, limit = PaginationService.normalize(page, limit)
    flags, total = list_runtime_post_flags(status=status, page=page, limit=limit, user=request.auth)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [serialize_flag(flag) for flag in flags],
    }


@router.post("/flags/{flag_id}/resolve", auth=AccessTokenAuth(), tags=["Admin"])
def resolve_post_flag(request, flag_id: int, payload: dict = Body(...)):
    denied = _require_admin_permission(request, "admin.flag.resolve", "没有处理举报的权限")
    if denied:
        return denied

    flag_model = get_runtime_post_flag_model()
    try:
        flag = resolve_runtime_post_flag(
            flag_id=flag_id,
            admin_user=request.auth,
            status=payload.get("status", flag_model.STATUS_RESOLVED),
            resolution_note=payload.get("resolution_note", ""),
        )
        log_admin_action(
            request,
            "admin.flag.resolve",
            target_type="post_flag",
            target_id=flag.id,
            data={
                "status": flag.status,
                "post_id": flag.post_id,
                "resolution_note": flag.resolution_note,
            },
        )
        return serialize_flag(flag)
    except flag_model.DoesNotExist:
        return api_error("举报记录不存在", status=404)
    except ValueError as exc:
        return api_error(str(exc), status=400)
