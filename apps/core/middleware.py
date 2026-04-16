import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.utils.deprecation import MiddlewareMixin
from ninja_jwt.authentication import JWTAuth

from apps.core.settings_service import (
    get_maintenance_message,
    is_maintenance_mode_enabled,
    is_query_logging_enabled,
)


sql_logger = logging.getLogger("pyflarum.sql")


class QueryLoggingMiddleware(MiddlewareMixin):
    def __call__(self, request):
        if not is_query_logging_enabled():
            return self.get_response(request)

        from django.db import connections

        initial_counts = {}
        enabled_connections = []
        original_force_debug = {}

        for connection in connections.all():
            initial_counts[connection.alias] = len(connection.queries)
            original_force_debug[connection.alias] = connection.force_debug_cursor
            connection.force_debug_cursor = True
            enabled_connections.append(connection)

        try:
            response = self.get_response(request)
        finally:
            for connection in enabled_connections:
                queries = connection.queries[initial_counts.get(connection.alias, 0):]
                total_time = 0.0

                for query in queries:
                    try:
                        total_time += float(query.get("time") or 0)
                    except (TypeError, ValueError):
                        pass
                    sql_logger.info(
                        "[%s] %s %s SQL %.4fs %s",
                        connection.alias,
                        request.method,
                        request.path,
                        float(query.get("time") or 0),
                        query.get("sql"),
                    )

                if queries:
                    sql_logger.info(
                        "[%s] %s %s total_queries=%s total_time=%.4fs",
                        connection.alias,
                        request.method,
                        request.path,
                        len(queries),
                        total_time,
                    )
                connection.force_debug_cursor = original_force_debug.get(connection.alias, False)

        return response


class MaintenanceModeMiddleware(MiddlewareMixin):
    allowed_public_paths = {
        "/api/forum",
        "/api/health",
        "/api/users/login",
    }

    def __call__(self, request):
        if not is_maintenance_mode_enabled():
            return self.get_response(request)

        if self._is_exempt(request):
            return self.get_response(request)

        return self._maintenance_response(request)

    def _is_exempt(self, request) -> bool:
        path = request.path or "/"

        if path.startswith("/admin/") or path.startswith("/api/admin"):
            return True

        if path in self.allowed_public_paths:
            return True

        static_url = getattr(settings, "STATIC_URL", None)
        media_url = getattr(settings, "MEDIA_URL", None)
        if static_url and path.startswith(static_url):
            return True
        if media_url and path.startswith(media_url):
            return True

        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
            return True

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False

        token = header.split(" ", 1)[1].strip()
        if not token:
            return False

        try:
            auth_user = JWTAuth().authenticate(request, token)
        except Exception:
            return False

        return bool(getattr(auth_user, "is_staff", False))

    def _maintenance_response(self, request):
        message = get_maintenance_message()

        if request.path.startswith("/api/"):
            response = JsonResponse(
                {"error": message, "maintenance": True},
                status=503,
            )
        else:
            response = HttpResponse(
                f"<h1>论坛维护中</h1><p>{escape(message)}</p>",
                status=503,
                content_type="text/html; charset=utf-8",
            )

        response["Retry-After"] = "300"
        return response
