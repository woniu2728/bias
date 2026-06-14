from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ninja import Router

from apps.core.extensions.runtime import get_runtime_resource_registry
from apps.core.resource_dispatcher import dispatch_resource_endpoint
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceRegistry


@dataclass(frozen=True)
class ResourceRouteDefinition:
    resource: str
    endpoint: str
    methods: tuple[str, ...]
    path: str
    object_id_param: str = ""
    module_id: str = ""


@dataclass(frozen=True)
class ResourceRouteOperation:
    resource: str
    endpoint: str
    methods: tuple[str, ...]
    module_id: str = ""


@dataclass(frozen=True)
class ResourcePathRouteDefinition:
    path: str
    methods: tuple[str, ...]
    operations: tuple[ResourceRouteOperation, ...]
    object_id_param: str = ""


def build_resource_endpoint_router(registry: ResourceRegistry | None = None) -> Router:
    resolved_registry = registry or get_runtime_resource_registry()
    router = Router()
    for route in build_resource_path_route_definitions(resolved_registry):
        router.add_api_operation(
            route.path,
            list(route.methods),
            _make_resource_endpoint_view(route),
            tags=["Resources"],
            url_name=f"resource_{_route_url_name(route)}".replace("-", "_"),
        )
    return router


def build_resource_path_route_definitions(registry: ResourceRegistry) -> list[ResourcePathRouteDefinition]:
    grouped: dict[str, list[ResourceRouteDefinition]] = {}
    for route in build_resource_route_definitions(registry):
        grouped.setdefault(route.path, []).append(route)

    routes: list[ResourcePathRouteDefinition] = []
    for path, route_group in grouped.items():
        operations = tuple(
            ResourceRouteOperation(
                resource=route.resource,
                endpoint=route.endpoint,
                methods=route.methods,
                module_id=route.module_id,
            )
            for route in route_group
        )
        methods = tuple(sorted({method for route in route_group for method in route.methods}))
        routes.append(
            ResourcePathRouteDefinition(
                path=path,
                methods=methods,
                operations=operations,
                object_id_param=_object_id_param(path),
            )
        )
    return routes


def build_resource_route_definitions(registry: ResourceRegistry) -> list[ResourceRouteDefinition]:
    routes: list[ResourceRouteDefinition] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for resource_name in _iter_dispatch_resource_names(registry):
        for endpoint in registry.get_dispatch_endpoints(resource_name):
            route = route_definition_for_endpoint(endpoint)
            key = (route.path, tuple(sorted(route.methods)))
            if key in seen:
                continue
            seen.add(key)
            routes.append(route)
    return routes


def _iter_dispatch_resource_names(registry: ResourceRegistry) -> tuple[str, ...]:
    names = {resource.resource for resource in registry.get_resources()}
    names.update(endpoint.resource for endpoint in registry.get_all_endpoints())
    return tuple(sorted(name for name in names if name))


def route_definition_for_endpoint(definition: ResourceEndpointDefinition) -> ResourceRouteDefinition:
    path = _endpoint_route_path(definition)
    return ResourceRouteDefinition(
        resource=definition.resource,
        endpoint=definition.endpoint,
        methods=tuple(sorted(_normalize_methods(definition.methods))),
        path=path,
        object_id_param=_object_id_param(path),
        module_id=definition.module_id,
    )


def _make_resource_endpoint_view(route: ResourcePathRouteDefinition):
    if route.object_id_param:
        def view(request, object_id: str):
            operation = _resolve_route_operation(route, request)
            return dispatch_resource_endpoint(
                request,
                resource=operation.resource,
                endpoint=operation.endpoint,
                object_id=str(object_id),
            )
    else:
        def view(request):
            operation = _resolve_route_operation(route, request)
            return dispatch_resource_endpoint(
                request,
                resource=operation.resource,
                endpoint=operation.endpoint,
            )

    view.__name__ = f"dispatch_resource_{_route_url_name(route)}".replace("-", "_")
    return view


def _resolve_route_operation(route: ResourcePathRouteDefinition, request) -> ResourceRouteOperation:
    method = str(getattr(request, "method", "GET") or "GET").upper()
    for operation in route.operations:
        if method in operation.methods:
            return operation
    return route.operations[0]


def _route_url_name(route: ResourcePathRouteDefinition) -> str:
    if len(route.operations) == 1:
        operation = route.operations[0]
        return f"{operation.resource}_{operation.endpoint}"
    normalized = route.path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
    return normalized


def _endpoint_route_path(definition: ResourceEndpointDefinition) -> str:
    raw_path = str(definition.path or "").strip()
    if raw_path:
        if bool(getattr(definition, "absolute_path", False)):
            return _normalize_absolute_route_path(raw_path)
        return _normalize_route_path(definition.resource, raw_path)

    kind = str(definition.kind or definition.endpoint or "").strip().lower()
    if kind in {"index", "create"}:
        return f"/{definition.resource}"
    if kind in {"show", "update", "delete"}:
        return f"/{definition.resource}/{{object_id}}"
    return f"/{definition.resource}/{_normalize_endpoint_path(definition.endpoint)}"


def _normalize_route_path(resource: str, path: str) -> str:
    normalized = "/" + path.strip().strip("/")
    normalized = normalized.replace("{id}", "{object_id}")
    if normalized in {"", "/"}:
        return f"/{resource}"
    if normalized.startswith(f"/{resource}/") or normalized == f"/{resource}":
        return normalized
    return f"/{resource}{normalized}"


def _normalize_absolute_route_path(path: str) -> str:
    normalized = "/" + str(path or "").strip().lstrip("/")
    if len(normalized) > 1:
        normalized = normalized.replace("//", "/")
    return normalized


def _normalize_endpoint_path(value: str) -> str:
    return str(value or "").strip().strip("/") or "index"


def _normalize_methods(methods: tuple[str, ...] | list[str] | str | None) -> set[str]:
    if methods is None:
        return {"GET"}
    if isinstance(methods, str):
        values = (methods,)
    else:
        values = methods
    return {str(method or "").strip().upper() for method in values if str(method or "").strip()} or {"GET"}


def _object_id_param(path: str) -> str:
    for segment in path.split("/"):
        segment = segment.strip()
        if segment.startswith("{") and segment.endswith("}"):
            return segment.strip("{}")
    return ""
