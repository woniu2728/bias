"""
URL configuration for bias project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI

# 创建API实例
api = NinjaAPI(
    title="Bias API",
    version="1.0.0",
    description="Flarum 风格论坛的 Python RESTful API",
    docs_url="/api/docs",
)

# 导入路由
from apps.users.api import router as users_router
from apps.discussions.api import router as discussions_router
from apps.posts.api import router as posts_router
from apps.tags.api import router as tags_router
from apps.notifications.api import router as notifications_router
from apps.core.api import router as core_router
from apps.core.admin_api import router as admin_router

# 注册路由
api.add_router("/users", users_router, tags=["Users"])
api.add_router("/discussions", discussions_router, tags=["Discussions"])
api.add_router("", posts_router, tags=["Posts"])
api.add_router("", tags_router, tags=["Tags"])
api.add_router("", notifications_router, tags=["Notifications"])
api.add_router("", core_router, tags=["Search"])
api.add_router("/admin", admin_router, tags=["Admin"])

# 健康检查端点
@api.get("/health", tags=["System"])
def health_check(request):
    """健康检查"""
    return {"status": "ok", "message": "Bias API is running"}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]

# 开发环境下提供媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug Toolbar
    if getattr(settings, 'ENABLE_DEBUG_TOOLBAR', False):
        urlpatterns = [
            path('__debug__/', include('debug_toolbar.urls')),
        ] + urlpatterns
