"""
URL configuration for bias project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.api_runtime import build_api_application
from apps.core.extensions.bootstrap import get_extension_host

extension_host = get_extension_host()
if extension_host is not None:
    api = extension_host.make("api.application")
else:
    api = build_api_application(extension_host=None)

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
