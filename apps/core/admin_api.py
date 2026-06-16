"""管理后台 API 路由聚合。"""
from ninja import Router

from apps.core.admin_audit_api import router as audit_router
from apps.core.admin_content_api import router as content_router
from apps.core.admin_extension_recovery_api import router as extension_recovery_router
from apps.core.admin_settings_api import router as settings_router
from apps.core.admin_stats_api import router as stats_router


router = Router()
router.add_router("", audit_router)
router.add_router("", content_router)
router.add_router("", extension_recovery_router)
router.add_router("", settings_router)
router.add_router("", stats_router)
