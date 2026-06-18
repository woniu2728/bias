import logging
import inspect

from asgiref.sync import async_to_sync, iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from apps.core.extensions.bootstrap import get_extension_application
from apps.core.jwt_auth import ACCESS_TOKEN_COOKIE_NAME, resolve_authenticated_user
from apps.core.runtime_state import get_runtime_status
from apps.core.settings_service import (
    get_maintenance_mode,
    get_maintenance_message,
    is_query_logging_enabled,
)


sql_logger = logging.getLogger("bias.sql")


class _AsyncCapableMiddleware:
    """消除 sync/async 样板代码的基类。

    子类只需实现 _sync_call(request) 和 _async_call(request) 两个方法，
    __init__ 与 __call__ 分发由本基类统一处理。
    """
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)
        return self._sync_call(request)

    async def __acall__(self, request):
        return await self._async_call(request)

    def _sync_call(self, request):
        raise NotImplementedError

    async def _async_call(self, request):
        raise NotImplementedError


class ExtensionErrorHandlingMiddleware(_AsyncCapableMiddleware):

    def _sync_call(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            response = self._handle(request, exc)
            if response is not None:
                return response
            raise

    async def _async_call(self, request):
        try:
            return await self.get_response(request)
        except Exception as exc:
            response = await sync_to_async(self._handle, thread_sensitive=True)(request, exc)
            if response is not None:
                return response
            raise

    def _handle(self, request, exc):
        from apps.core.extensions.system_runtime import handle_runtime_error, report_runtime_error

        report_runtime_error(exc, request=request, operation="request")
        return handle_runtime_error(exc, request=request, operation="request")


class ExtensionCsrfMiddleware(_AsyncCapableMiddleware):

    def _sync_call(self, request):
        self._apply_exemption(request)
        return self.get_response(request)

    async def _async_call(self, request):
        await sync_to_async(self._apply_exemption, thread_sensitive=True)(request)
        return await self.get_response(request)

    def _apply_exemption(self, request):
        route_name = str(getattr(getattr(request, "resolver_match", None), "url_name", "") or "").strip()
        if not route_name:
            return
        from apps.core.extensions.system_runtime import is_runtime_csrf_exempt_route

        if is_runtime_csrf_exempt_route(route_name):
            request._dont_enforce_csrf_checks = True

    def process_view(self, request, view_func, view_args, view_kwargs):
        self._apply_exemption(request)
        return None


class ExtensionThrottleApiMiddleware(_AsyncCapableMiddleware):

    def _sync_call(self, request):
        return self.get_response(request)

    async def _async_call(self, request):
        return await self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        return self._throttle_response(request)

    def _throttle_response(self, request):
        if not str(getattr(request, "path", "") or "").startswith("/api/"):
            return None
        from apps.core.extensions.system_runtime import should_throttle_runtime_api_request

        if not should_throttle_runtime_api_request(request):
            return None
        return JsonResponse({"error": "请求过于频繁", "code": "rate_limit_exceeded"}, status=429)


class StartupStateMiddleware:
    sync_capable = True
    async_capable = True
    exempt_paths = {
        "/api/health",
        "/api/system/status",
        "/api/docs",
        "/api/openapi.json",
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

        if self._is_exempt(request):
            return self.get_response(request)

        status = get_runtime_status()
        if status.state == "ready":
            return self.get_response(request)

        return self._build_response(request, status)

    async def __acall__(self, request):
        if await sync_to_async(self._is_exempt, thread_sensitive=True)(request):
            return await self.get_response(request)

        status = await sync_to_async(get_runtime_status, thread_sensitive=True)()
        if status.state == "ready":
            return await self.get_response(request)

        return await sync_to_async(self._build_response, thread_sensitive=True)(request, status)

    def _is_exempt(self, request) -> bool:
        path = request.path or "/"
        if path in self.exempt_paths:
            return True

        static_url = getattr(settings, "STATIC_URL", None)
        media_url = getattr(settings, "MEDIA_URL", None)
        if static_url and path.startswith(static_url):
            return True
        if media_url and path.startswith(media_url):
            return True
        return False

    def _build_response(self, request, status):
        payload = {
            "state": status.state,
            "message": status.message,
            "current_version": status.current_version,
            "installed_version": status.installed_version,
        }

        if request.path.startswith("/api/") or request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse(payload, status=503)

        title = "Bias 尚未安装" if status.state == "uninstalled" else "Bias 需要升级"
        body = (
            f"<h1>{escape(title)}</h1>"
            f"<p>{escape(status.message)}</p>"
            f"<p>当前代码版本: {escape(status.current_version)}</p>"
        )
        if status.installed_version:
            body += f"<p>已安装版本: {escape(status.installed_version)}</p>"
        return HttpResponse(body, status=503, content_type="text/html; charset=utf-8")


class ExtensionRuntimeInvalidationMiddleware(_AsyncCapableMiddleware):

    def _sync_call(self, request):
        self._sync_runtime_state()
        return self.get_response(request)

    async def _async_call(self, request):
        await sync_to_async(self._sync_runtime_state, thread_sensitive=True)()
        return await self.get_response(request)

    def _sync_runtime_state(self):
        from apps.core.extensions.lifecycle import sync_extension_runtime_state_if_stale

        sync_extension_runtime_state_if_stale()


class QueryLoggingMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

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

    async def __acall__(self, request):
        if not await sync_to_async(is_query_logging_enabled, thread_sensitive=True)():
            return await self.get_response(request)

        # Async endpoints should still work when query logging is enabled.
        # Detailed per-query capture remains on the sync path.
        return await self.get_response(request)


class ExtensionRequestMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

        handler = self._build_sync_chain(request)
        return handler(request)

    async def __acall__(self, request):
        handler = await sync_to_async(self._build_async_chain, thread_sensitive=True)(request)
        return await handler(request)

    def _build_sync_chain(self, request):
        handler = self.get_response
        for mount in reversed(self._resolve_mounts(request)):
            handler = self._wrap_sync_handler(mount.middleware, handler)
        return handler

    def _build_async_chain(self, request):
        handler = self.get_response
        for mount in reversed(self._resolve_mounts(request)):
            handler = self._wrap_async_handler(mount.middleware, handler)
        return handler

    def _resolve_mounts(self, request):
        application = get_extension_application()
        if application is None:
            return []
        mounts = []
        for target in self._resolve_targets(request):
            mounts.extend(application.get_middleware_mounts(target=target))
        return mounts

    def _resolve_targets(self, request) -> list[str]:
        path = request.path or "/"
        targets = ["global"]

        if path.startswith("/api/admin") or path.startswith("/admin/"):
            if path.startswith("/api/"):
                targets.append("api")
            targets.append("admin")
            return targets

        if path.startswith("/api/"):
            targets.append("api")
            return targets

        targets.append("forum")
        return targets

    def _wrap_sync_handler(self, middleware, next_handler):
        def handler(request):
            if self._accepts_next_handler(middleware):
                if iscoroutinefunction(middleware):
                    return async_to_sync(middleware)(request, next_handler)
                return middleware(request, next_handler)

            if iscoroutinefunction(middleware):
                result = async_to_sync(middleware)(request)
            else:
                result = middleware(request)
            if result is None:
                return next_handler(request)
            return result

        return handler

    def _wrap_async_handler(self, middleware, next_handler):
        if self._accepts_next_handler(middleware):
            if iscoroutinefunction(middleware):
                async def handler(request):
                    return await middleware(request, next_handler)

                return handler

            async def handler(request):
                def invoke():
                    def sync_next(inner_request):
                        return async_to_sync(next_handler)(inner_request)

                    return middleware(request, sync_next)

                return await sync_to_async(invoke, thread_sensitive=True)()

            return handler

        if iscoroutinefunction(middleware):
            async def handler(request):
                result = await middleware(request)
                if result is None:
                    return await next_handler(request)
                return result

            return handler

        async def handler(request):
            result = await sync_to_async(middleware, thread_sensitive=True)(request)
            if result is None:
                return await next_handler(request)
            return result

        return handler

    @staticmethod
    def _accepts_next_handler(middleware) -> bool:
        try:
            signature = inspect.signature(middleware)
        except (TypeError, ValueError):
            return False

        positional_params = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if len(positional_params) >= 2:
            return True
        return any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        )


class MaintenanceModeMiddleware:
    sync_capable = True
    async_capable = True
    allowed_public_paths = {
        "/api/csrf",
        "/api/forum",
        "/api/health",
        "/api/users/login",
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)

        mode = get_maintenance_mode()
        if mode == "none":
            return self.get_response(request)

        if self._is_exempt(request, mode=mode):
            return self.get_response(request)

        return self._maintenance_response(request, mode=mode)

    async def __acall__(self, request):
        mode = await sync_to_async(get_maintenance_mode, thread_sensitive=True)()
        if mode == "none":
            return await self.get_response(request)

        if await sync_to_async(self._is_exempt, thread_sensitive=True)(request, mode=mode):
            return await self.get_response(request)

        return await sync_to_async(self._maintenance_response, thread_sensitive=True)(request, mode=mode)

    def _is_exempt(self, request, *, mode: str = "high") -> bool:
        path = request.path or "/"

        if path.startswith("/admin/") or path.startswith("/api/admin"):
            return True

        if path in self.allowed_public_paths:
            return True

        if mode == "low" and request.method in {"GET", "HEAD", "OPTIONS"}:
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

        authorization = str(request.headers.get("Authorization", "") or "")
        has_bearer_token = authorization.startswith("Bearer ") and bool(authorization.split(" ", 1)[1].strip())
        if not has_bearer_token and not request.COOKIES.get(ACCESS_TOKEN_COOKIE_NAME):
            return False

        auth_user = resolve_authenticated_user(request)
        return bool(getattr(auth_user, "is_staff", False))

    def _maintenance_response(self, request, *, mode: str = "high"):
        message = get_maintenance_message()

        if request.path.startswith("/api/"):
            response = JsonResponse(
                {"error": message, "maintenance": True, "maintenance_mode_key": mode},
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


class SecurityHeadersMiddleware(_AsyncCapableMiddleware):

    def _sync_call(self, request):
        request.csp_nonce = _generate_csp_nonce()
        response = self.get_response(request)
        return self._apply_headers(request, response)

    async def _async_call(self, request):
        request.csp_nonce = _generate_csp_nonce()
        response = await self.get_response(request)
        return self._apply_headers(request, response)

    def _apply_headers(self, request, response):
        nonce = getattr(request, "csp_nonce", "")
        nonce_directive = f" 'nonce-{nonce}'" if nonce else ""
        # 注：style-src 暂时保留 'unsafe-inline' 以兼容 Django admin 内联样式；
        # 同时提供 'nonce-{value}' 以便自定义模板逐步迁移到 nonce 方式。
        # 若项目不依赖 Django admin 可移除 'unsafe-inline'。
        csp = (
            "default-src 'self'; "
            "img-src 'self' data: blob:; "
            f"style-src 'self' 'unsafe-inline'{nonce_directive}; "
            f"script-src 'self'{nonce_directive}; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        response.setdefault("Content-Security-Policy", csp)
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        return response


def _generate_csp_nonce() -> str:
    import secrets
    return secrets.token_urlsafe(24)
