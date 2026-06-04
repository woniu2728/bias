from __future__ import annotations

from ninja import NinjaAPI, Router

from apps.core.runtime_checks import collect_runtime_readiness
from apps.core.runtime_state import get_runtime_status
from apps.core.version import APP_VERSION


def build_api_application(*, extension_host=None, urls_namespace: str | None = None) -> NinjaAPI:
    api = NinjaAPI(
        title="Bias API",
        version=APP_VERSION,
        description="Bias forum RESTful API",
        docs_url="/docs",
        csrf=True,
        urls_namespace=urls_namespace,
    )

    _register_core_routes(api)
    _register_extension_routes(api, extension_host=extension_host)
    _register_health_route(api)
    return api


def _register_core_routes(api: NinjaAPI) -> None:
    from apps.core.admin_api import router as admin_router
    from apps.core.api import router as core_router
    from apps.core.resource_runtime_api import router as resource_runtime_router
    from apps.users.api import router as users_router

    _add_router_once(api, "/users", users_router, tags=["Users"])
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
    else:
        registry = host.resources
    from apps.core.core_resource_endpoints import bootstrap_core_resource_endpoints
    from apps.core.resource_routes import build_resource_endpoint_router

    bootstrap_core_resource_endpoints(registry)
    _add_router_once(api, "", build_resource_endpoint_router(registry), tags=["Resources"])
    if host is None:
        return
    routes = host.make("routes")
    for mount in routes.get_mounts():
        _add_router_once(api, mount.prefix, mount.router, tags=list(mount.tags))
    get_named_routes = getattr(routes, "get_routes", None)
    if not callable(get_named_routes):
        return
    for route in get_named_routes(app_name="api"):
        _add_named_route(api, route)


def _register_health_route(api: NinjaAPI) -> None:
    @api.get("/health", tags=["System"])
    def health_check(request):
        runtime = get_runtime_status()
        readiness = collect_runtime_readiness()
        return {
            "status": "ok" if runtime.state == "ready" else "degraded",
            "message": "Bias API is running",
            "state": runtime.state,
            "current_version": runtime.current_version,
            "installed_version": runtime.installed_version,
            "readiness": {
                "database_label": readiness["database_label"],
                "cache_driver": readiness["cache_driver"],
                "realtime_driver": readiness["realtime_driver"],
                "queue_driver": readiness["queue_driver"],
                "queue_enabled": readiness["queue_enabled"],
                "queue_worker_status": readiness["queue_worker_status"],
                "redis_enabled": readiness["redis_enabled"],
                "auth_secret_status": readiness["auth_secret_status"],
                "runtime_risks": readiness["runtime_risks"],
                "runtime_dependency_checks": readiness["runtime_dependency_checks"],
            },
        }


def _add_router_once(api: NinjaAPI, prefix, router, *, tags=None) -> None:
    if getattr(router, "api", None) is not None:
        return
    api.add_router(prefix, router, tags=tags or [])


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
