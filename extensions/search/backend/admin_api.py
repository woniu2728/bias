from __future__ import annotations

from ninja import Router

from apps.core.extensions.platform import api_error
from apps.core.extensions.platform import log_admin_action
from apps.core.extensions.platform import AccessTokenAuth
from apps.core.extensions.forum import AuditLog
from apps.core.extensions.forum import detect_database_label
from apps.core.extensions.forum import SearchIndexService
from apps.core.extensions.platform import QueueService


router = Router()


def _require_staff(request):
    if not request.auth or not request.auth.is_staff:
        return api_error("需要管理员权限", status=403)
    return None


@router.get("/search-indexes/status", auth=AccessTokenAuth(), tags=["Admin"])
def get_search_index_status(request):
    denied = _require_staff(request)
    if denied:
        return denied

    queue_worker_status = QueueService.get_worker_status()
    latest_rebuild = AuditLog.objects.filter(action="admin.search_indexes.rebuild").first()
    search_index_status = SearchIndexService.get_status()

    last_rebuild = None
    if latest_rebuild:
        last_rebuild = {
            "created_at": latest_rebuild.created_at,
            "duration_ms": latest_rebuild.data.get("duration_ms", 0),
            "indexes": latest_rebuild.data.get("indexes", []),
        }

    return {
        **search_index_status,
        "databaseLabel": detect_database_label(),
        "lastRebuild": last_rebuild,
        "queueWorkerStatus": queue_worker_status["status"],
        "queueWorkerLabel": queue_worker_status["label"],
        "queueWorkerAvailable": queue_worker_status["available"],
        "queueWorkerCount": queue_worker_status["worker_count"],
        "queueWorkerMessage": queue_worker_status["message"],
    }


@router.post("/search-indexes/rebuild", auth=AccessTokenAuth(), tags=["Admin"])
def rebuild_search_indexes(request):
    denied = _require_staff(request)
    if denied:
        return denied

    try:
        result = SearchIndexService.rebuild_postgres_indexes()
    except RuntimeError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        return api_error(f"搜索索引重建失败: {exc}", status=503)

    log_admin_action(
        request,
        "admin.search_indexes.rebuild",
        target_type="search_index",
        data={
            "indexes": result.get("indexes", []),
            "duration_ms": result.get("duration_ms", 0),
        },
    )
    return result
