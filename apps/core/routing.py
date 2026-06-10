from django.urls import re_path

from apps.core.extensions.bootstrap import get_extension_host


def build_websocket_urlpatterns():
    host = get_extension_host()
    if host is None:
        return []

    patterns = []
    for route in host.get_websocket_routes():
        consumer = route.consumer
        as_asgi = getattr(consumer, "as_asgi", None)
        if not callable(as_asgi):
            continue
        patterns.append(re_path(route.path, as_asgi(), name=route.name))
    return patterns


websocket_urlpatterns = build_websocket_urlpatterns()
