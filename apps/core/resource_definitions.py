from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Tuple


ResourceFieldResolver = Callable[[Any, dict], Any]
ResourceBaseFieldResolver = Callable[[Any, dict], dict]
ResourceRelationshipResolver = Callable[[Any, dict], Any]
ResourcePreloadResolver = Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]]
ResourceAnnotateResolver = Callable[[dict], dict[str, Any]]
ResourceEndpointHandler = Callable[[dict], Any]


@dataclass(frozen=True)
class ResourceFieldDefinition:
    resource: str
    field: str
    module_id: str
    resolver: ResourceFieldResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: ResourcePreloadResolver | None = None
    annotate_resolver: ResourceAnnotateResolver | None = None
    visible: Callable[[Any, dict], bool] | bool = True
    writable: Callable[[Any, dict], bool] | bool = False
    required_on_create: bool = False
    required_on_update: bool = False
    nullable: bool = False
    value_type: str = ""
    validation_rules: Tuple[Any, ...] = ()
    has_validation_rules: bool = False
    setter: Callable[[Any, Any, dict], None] | None = None
    validator: Callable[[Any, dict], None] | None = None
    field_object: Any = None


@dataclass(frozen=True)
class ResourceDefinition:
    resource: str
    module_id: str
    resolver: ResourceBaseFieldResolver
    description: str = ""


@dataclass(frozen=True)
class ResourceRelationshipDefinition:
    resource: str
    relationship: str
    module_id: str
    resolver: ResourceRelationshipResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: ResourcePreloadResolver | None = None
    visible: Callable[[Any, dict], bool] | bool = True
    includable: Callable[[dict], bool] | bool = True
    resource_type: str = ""
    many: bool = False
    inverse: str = ""
    setter: Callable[[Any, Any, dict], None] | None = None
    writable: Callable[[Any, dict], bool] | bool = False
    linkage: Callable[[Any, dict], Any] | bool = True
    required_on_create: bool = False
    required_on_update: bool = False
    nullable: bool = False
    value_type: str = ""
    validation_rules: Tuple[Any, ...] = ()
    has_validation_rules: bool = False
    validator: Callable[[Any, dict], None] | None = None
    field_object: Any = None


@dataclass(frozen=True)
class ResourceEndpointDefinition:
    resource: str
    endpoint: str
    module_id: str
    mutator: Callable[[Any], Any] | None = None
    description: str = ""
    operation: str = "mutate"
    anchor: str = ""
    condition: Callable[[dict], bool] | None = None
    handler: Callable[[dict], Any] | None = None
    methods: Tuple[str, ...] = ("GET",)
    path: str = ""
    absolute_path: bool = False
    auth_required: bool = False
    permission: str = ""
    default_include: Tuple[str, ...] = ()
    eager_load: Tuple[Any, ...] = ()
    eager_load_when_included_rules: Tuple[tuple[str, Tuple[Any, ...]], ...] = ()
    eager_load_where_rules: Tuple[tuple[str, Callable[[Any, dict], Any]], ...] = ()
    default_sort: str = ""
    paginate: bool = False
    pagination_default_limit: int = 20
    pagination_max_limit: int = 50
    kind: str = ""
    ability: Any = None
    forum_permission: str = ""
    before_hook: Callable[[dict], Any] | None = None
    after_hook: Callable[[dict, Any], Any] | None = None
    meta_resolver: Callable[[dict, Any], dict] | None = None
    links_resolver: Callable[[dict, Any], dict] | None = None
    query_callback: Callable[[dict], dict | None] | None = None
    action_callback: Callable[[dict], Any] | None = None
    before_serialization_callback: Callable[[dict, Any], Any] | None = None
    response_callback: Callable[[dict, Any], Any] | None = None

    def build_pipeline(self, registry, resource_object):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint

        endpoint = DatabaseResourceEndpoint(registry, resource_object, self)
        kind = str(self.kind or self.endpoint or "").strip().lower()
        if kind == "index":
            return endpoint.index_pipeline()
        if kind == "show":
            return endpoint.show_pipeline()
        if kind == "create":
            return endpoint.create_pipeline()
        if kind == "update":
            return endpoint.update_pipeline()
        if kind == "delete":
            return endpoint.delete_pipeline()
        raise ValueError("资源端点没有处理器")


@dataclass(frozen=True)
class ResourceFieldMutatorDefinition:
    resource: str
    field: str
    module_id: str
    mutator: Callable[[Any], Any]
    description: str = ""
    operation: str = "mutate"
    anchor: str = ""
    condition: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class ResourceSortDefinition:
    resource: str
    sort: str
    module_id: str
    handler: Any = None
    description: str = ""
    operation: str = "add"
    anchor: str = ""
    mutator: Callable[[Any], Any] | None = None
    condition: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class ResourceFilterDefinition:
    resource: str
    filter: str
    module_id: str
    handler: Callable[[Any, Any, dict], Any]
    description: str = ""
    visible: Callable[[dict], bool] | bool = True
    operation: str = "add"
    anchor: str = ""
    mutator: Callable[[Any], Any] | None = None
    condition: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class ResourcePreloadPlan:
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[Any, ...] = ()
    prefetch_where: tuple[tuple[str, Callable[[Any, dict], Any]], ...] = ()
    annotations: tuple[tuple[str, Any], ...] = ()
