"""管理后台 API 路由聚合。"""
from ninja import Router

from apps.core.admin_content_api import router as content_router
from apps.core.admin_settings_api import router as settings_router
from apps.core.admin_users_api import router as users_router


router = Router()
router.add_router("", content_router)
router.add_router("", settings_router)
router.add_router("", users_router)
