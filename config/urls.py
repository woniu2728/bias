"""
URL configuration for bias project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.api_runtime import build_api_application
from apps.core.extensions.bootstrap import get_extension_host


api = None
urlpatterns = []


def build_api():
    extension_host = get_extension_host()
    if extension_host is not None:
        return extension_host.make("api.application")
    return build_api_application(extension_host=None)


def build_urlpatterns():
    resolved_api = build_api()
    patterns = [
        path('admin/', admin.site.urls),
        path('api/', resolved_api.urls),
    ]

    # 开发环境下提供媒体文件服务
    if settings.DEBUG:
        patterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        patterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

        # Debug Toolbar
        if getattr(settings, 'ENABLE_DEBUG_TOOLBAR', False):
            patterns = [
                path('__debug__/', include('debug_toolbar.urls')),
            ] + patterns
    return resolved_api, patterns


def rebuild_api_urlpatterns():
    global api
    global urlpatterns
    api, urlpatterns = build_urlpatterns()
    return urlpatterns


rebuild_api_urlpatterns()
