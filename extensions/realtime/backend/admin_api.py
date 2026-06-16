from ninja import Router

from apps.core.extensions.platform import AccessTokenAuth
from apps.core.extensions.platform import QueueService
from apps.core.extensions.platform import log_admin_action
from apps.core.extensions.platform import require_staff


router = Router()


@router.post("/queue/metrics/reset", auth=AccessTokenAuth(), tags=["Admin"])
def reset_queue_metrics(request):
    denied = require_staff(request)
    if denied:
        return denied

    metrics = QueueService.reset_metrics()
    log_admin_action(request, "admin.queue_metrics.reset", data={"metrics": metrics})
    return {
        "message": "队列运行指标已重置",
        "metrics": metrics,
    }
