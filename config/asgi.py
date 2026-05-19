"""
ASGI config for bias project.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.core.startup_guard import enforce_production_runtime_checks

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

enforce_production_runtime_checks()

django_asgi_app = get_asgi_application()

from apps.core import routing
from apps.core.websocket_auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    ),
})
