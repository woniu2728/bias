from __future__ import annotations

from ninja import NinjaAPI, Router

from apps.core.runtime_state import get_runtime_status
from apps.core.version import APP_VERSION


_api_namespace_counter = 0


def next_api_urls_namespace() -> str:
    global _api_namespace_counter
    _api_namespace_counter += 1
    return f"bias-api-{_api_namespace_counter}"


def build_api_application(*, extension_host=None, urls_namespace: str | None = None) -> NinjaAPI:
    api = NinjaAPI(
        title="Bias API",
        version=APP_VERSION,
        description="Bias forum RESTful API",
        docs_url="/docs",
        csrf=True,
        urls_namespace=urls_namespace or next_api_urls_namespace(),
    )

    _register_core_routes(api)
    _register_extension_routes(api, extension_host=extension_host)
    _register_health_route(api)
    return api


def _register_core_routes(api: NinjaAPI) -> None:
    from apps.core.admin_api import router as admin_router
    from apps.core.api import router as core_router
    from apps.core.resource_runtime_api import router as resource_runtime_router

    _add_router_once(api, "", core_router, tags=["Search"])
    _add_router_once(api, "", resource_runtime_router, tags=["Resources"])
    _add_router_once(api, "/admin", admin_router, tags=["Admin"])


def _register_extension_routes(api: NinjaAPI, *, extension_host=None) -> None:
    host = extension_host
    if host is None:
        from apps.core.extensions.bootstrap import get_extension_host

        host = get_extension_host()
    if host is None:
        from apps.core.resource_registry import get_resource_registry

        registry = get_resource_registry()
        from apps.core.resource_routes import build_resource_endpoint_router

        _add_router_once(api, "", build_resource_endpoint_router(registry), tags=["Resources"])
        return

    routes = host.make("routes")
    for mount in routes.get_mounts():
        _add_router_once(api, mount.prefix, mount.router, tags=list(mount.tags))
    get_named_routes = getattr(routes, "get_routes", None)
    if callable(get_named_routes):
        for route in get_named_routes(app_name="api"):
            _add_named_route(api, route)

    from apps.core.resource_routes import build_resource_endpoint_router

    _add_router_once(api, "", build_resource_endpoint_router(host.resources), tags=["Resources"])


def _register_health_route(api: NinjaAPI) -> None:
    @api.get("/health", tags=["System"])
    def health_check(request):
        runtime = get_runtime_status()
        return {
            "status": "ok" if runtime.state == "ready" else "degraded",
            "message": "Bias API is running",
            "state": runtime.state,
            "current_version": runtime.current_version,
            "installed_version": runtime.installed_version,
        }


def _add_router_once(api: NinjaAPI, prefix, router, *, tags=None) -> None:
    if getattr(router, "api", None) is api:
        return
    if getattr(router, "api", None) is not None:
        _detach_router_from_api(router)
    api.add_router(prefix, router, tags=tags or [])


def _detach_router_from_api(router) -> None:
    router.api = None
    for path_view in getattr(router, "path_operations", {}).values():
        path_view.api = None
        for operation in getattr(path_view, "operations", ()):
            operation.api = None
    for _prefix, child in getattr(router, "_routers", ()):
        _detach_router_from_api(child)


def _add_named_route(api: NinjaAPI, route) -> None:
    view = _make_named_route_view(route)
    router = Router()
    router.add_api_operation(
        "",
        [route.method],
        view,
        tags=list(route.tags or ()),
        url_name=str(route.name or "").replace("-", "_").replace(".", "_"),
    )
    _add_router_once(api, route.path, router, tags=list(route.tags or ()))


def _make_named_route_view(route):
    handler = route.handler

    def view(request, **path_params):
        try:
            return handler(request, **path_params)
        except TypeError:
            if path_params:
                try:
                    return handler(**path_params)
                except TypeError:
                    pass
            return handler(request)

    view.__name__ = f"extension_route_{route.module_id}_{route.name}".replace("-", "_").replace(".", "_")
    return view
