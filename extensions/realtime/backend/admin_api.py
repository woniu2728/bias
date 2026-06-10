from ninja import Router

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.jwt_auth import AccessTokenAuth
from apps.core.queue_service import QueueService


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None


@router.post("/queue/metrics/reset", auth=AccessTokenAuth(), tags=["Admin"])
def reset_queue_metrics(request):
    denied = _require_staff(request)
    if denied:
        return denied

    metrics = QueueService.reset_metrics()
    log_admin_action(request, "admin.queue_metrics.reset", data={"metrics": metrics})
    return {
        "message": "队列运行指标已重置",
        "metrics": metrics,
    }
