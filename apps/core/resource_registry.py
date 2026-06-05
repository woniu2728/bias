from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from django.db import OperationalError, ProgrammingError

from apps.core.models import ExtensionInstallation
from apps.core.resource_objects import (
    DatabaseResource,
    Resource,
    ResourceEndpoint,
    ResourceFilter,
    ResourceField,
    ResourceRelationship,
    ResourceSearchCriteria,
    ResourceSearchResults,
    ResourceSort,
)
from apps.core.resource_errors import (
    BadJsonApiRequest,
    JsonApiConflict,
    JsonApiForbidden,
    JsonApiValidationError,
)
from apps.core.resource_search import ResourceSearchFilter, get_resource_search_manager
from apps.core.resource_serializer import ResourceSerializer
from apps.core.resource_context import ensure_resource_context
from apps.core.resource_validation import ResourceValidationError, ResourceValidator, ResourceValidatorFactory


ResourceFieldResolver = Callable[[Any, dict], Any]
ResourceBaseFieldResolver = Callable[[Any, dict], dict]
ResourceRelationshipResolver = Callable[[Any, dict], Any]
ResourcePreloadResolver = Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]]
ResourceEndpointHandler = Callable[[dict], Any]
_JSONAPI_SKIP = object()


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

    def build_pipeline(self, registry: "ResourceRegistry", resource_object: DatabaseResource):
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


class ResourceRegistry:
    def __init__(self):
        self._definitions: Dict[str, ResourceDefinition] = {}
        self._resource_objects: Dict[str, Resource] = {}
        self._fields: Dict[str, List[ResourceFieldDefinition]] = {}
        self._field_mutators: Dict[str, List[ResourceFieldMutatorDefinition]] = {}
        self._relationships: Dict[str, List[ResourceRelationshipDefinition]] = {}
        self._endpoints: Dict[str, List[ResourceEndpointDefinition]] = {}
        self._sorts: Dict[str, List[ResourceSortDefinition]] = {}
        self._filters: Dict[str, List[ResourceFilterDefinition]] = {}
        self._core_endpoint_keys: set[tuple[str, str, str]] = set()
        self._resolved_resource_cache: Dict[str, Resource] = {}
        self._resource_modifiers: dict[type, dict[str, list[Callable[[list[Any], Resource], list[Any]]]]] = {}

    def _get_enabled_module_ids(self) -> set[str] | None:
        try:
            overrides = {
                item["extension_id"]: bool(item["enabled"])
                for item in ExtensionInstallation.objects.filter(source="filesystem").values("extension_id", "enabled")
            }
        except (OperationalError, ProgrammingError, RuntimeError):
            return None

        if not overrides:
            return None

        disabled_ids = {
            extension_id
            for extension_id, enabled in overrides.items()
            if not enabled
        }
        if not disabled_ids:
            return None

        enabled_ids = set(self._definitions.keys())
        enabled_ids.update(definition.module_id for definition in self._resource_objects.values())
        enabled_ids.update(definition.module_id for definitions in self._fields.values() for definition in definitions)
        enabled_ids.update(definition.module_id for definitions in self._field_mutators.values() for definition in definitions)
        enabled_ids.update(
            definition.module_id
            for definitions in self._relationships.values()
            for definition in definitions
        )
        enabled_ids.update(definition.module_id for definitions in self._endpoints.values() for definition in definitions)
        enabled_ids.update(definition.module_id for definitions in self._sorts.values() for definition in definitions)
        enabled_ids.update(definition.module_id for definitions in self._filters.values() for definition in definitions)
        return enabled_ids - disabled_ids

    def _is_module_enabled(self, module_id: str, enabled_module_ids: set[str] | None) -> bool:
        if enabled_module_ids is None:
            return True
        return module_id in enabled_module_ids

    def register_resource(self, definition: ResourceDefinition) -> ResourceDefinition:
        if isinstance(definition, type) and issubclass(definition, Resource):
            return self.register_resource_object(definition())
        if isinstance(definition, Resource):
            return self.register_resource_object(definition)
        self._definitions[definition.resource] = definition
        self._resolved_resource_cache.pop(definition.resource, None)
        return definition

    def register_resource_object(self, resource: Resource) -> ResourceDefinition:
        name = str(resource.type() or "").strip()
        if not name:
            raise ValueError("资源对象必须提供 type()")
        self._resource_objects[name] = resource
        self._definitions[name] = ResourceDefinition(
            resource=name,
            module_id=getattr(resource, "module_id", "core") or "core",
            resolver=lambda instance, context, resource_object=resource: resource_object.serialize(instance, context),
            description=getattr(resource, "description", ""),
        )
        self._resolved_resource_cache.pop(name, None)
        return self._definitions[name]

    def register_resource_modifier(self, resource_class: type, kind: str, modifier: Callable[[list[Any], Resource], list[Any]]) -> None:
        if resource_class is None or not callable(modifier):
            return
        normalized_kind = str(kind or "").strip()
        if normalized_kind not in {"endpoints", "fields", "sorts", "filters"}:
            return
        modifiers = self._resource_modifiers.setdefault(resource_class, {}).setdefault(normalized_kind, [])
        if modifier not in modifiers:
            modifiers.append(modifier)
            mutate = getattr(resource_class, f"mutate_{normalized_kind}", None)
            if callable(mutate):
                mutate(modifier)
        self._clear_resource_object_resolve_caches()
        self._resolved_resource_cache.clear()

    def clear_resource_modifier_cache(self) -> None:
        self._clear_resource_object_resolve_caches()
        self._resolved_resource_cache.clear()

    def reset_resource_modifiers(self, resource_class: type | None = None, kind: str = "") -> None:
        if resource_class is None:
            self._resource_modifiers.clear()
            for resource in self._resource_objects.values():
                reset = getattr(type(resource), "reset_modifiers", None)
                if callable(reset):
                    reset()
            self._clear_resource_object_resolve_caches()
            self._resolved_resource_cache.clear()
            return
        normalized_kind = str(kind or "").strip()
        if not normalized_kind:
            self._resource_modifiers.pop(resource_class, None)
            reset = getattr(resource_class, "reset_modifiers", None)
            if callable(reset):
                reset()
            self._clear_resource_object_resolve_caches()
            self._resolved_resource_cache.clear()
            return
        kinds = self._resource_modifiers.get(resource_class)
        if kinds is not None:
            kinds.pop(normalized_kind, None)
            if not kinds:
                self._resource_modifiers.pop(resource_class, None)
        reset = getattr(resource_class, "reset_modifiers", None)
        if callable(reset):
            reset(normalized_kind)
        self._clear_resource_object_resolve_caches()
        self._resolved_resource_cache.clear()

    def _clear_resource_object_resolve_caches(self) -> None:
        for resource in self._resource_objects.values():
            clear_cache = getattr(resource, "clear_resolved_cache", None)
            if callable(clear_cache):
                clear_cache()

    def register_field(self, definition: ResourceFieldDefinition) -> ResourceFieldDefinition:
        fields = self._fields.setdefault(definition.resource, [])
        existing_index = next(
            (index for index, field in enumerate(fields) if field.field == definition.field),
            None,
        )
        if existing_index is not None:
            fields[existing_index] = definition
        else:
            fields.append(definition)
        fields.sort(key=lambda item: (item.module_id, item.field))
        return definition

    def register_relationship(self, definition: ResourceRelationshipDefinition) -> ResourceRelationshipDefinition:
        relationships = self._relationships.setdefault(definition.resource, [])
        existing_index = next(
            (
                index
                for index, relationship in enumerate(relationships)
                if relationship.relationship == definition.relationship
            ),
            None,
        )
        if existing_index is not None:
            relationships[existing_index] = definition
        else:
            relationships.append(definition)
        relationships.sort(key=lambda item: (item.module_id, item.relationship))
        return definition

    def register_endpoint(self, definition: ResourceEndpointDefinition) -> ResourceEndpointDefinition:
        return self._register_endpoint(definition, core=False)

    def register_core_endpoint(self, definition: ResourceEndpointDefinition) -> ResourceEndpointDefinition:
        return self._register_endpoint(definition, core=True)

    def _register_endpoint(self, definition: ResourceEndpointDefinition, *, core: bool) -> ResourceEndpointDefinition:
        endpoints = self._endpoints.setdefault(definition.resource, [])
        operation = self._endpoint_operation(definition)
        key = self._endpoint_registration_key(definition)
        if core and key in self._core_endpoint_keys:
            return definition
        if core:
            self._core_endpoint_keys.add(key)
            insert_index = next(
                (
                    index
                    for index, endpoint in enumerate(endpoints)
                    if self._endpoint_operation(endpoint) != "add"
                ),
                None,
            )
            if insert_index is None:
                endpoints.append(definition)
            else:
                endpoints.insert(insert_index, definition)
            return definition
        if operation != "add" or definition.handler is None:
            endpoints.append(definition)
            return definition

        existing_index = next(
            (
                index
                for index, endpoint in enumerate(endpoints)
                if endpoint.endpoint == definition.endpoint
                and endpoint.module_id == definition.module_id
                and self._endpoint_operation(endpoint) == "add"
                and endpoint.handler is not None
            ),
            None,
        )
        if existing_index is not None:
            endpoints[existing_index] = definition
        else:
            endpoints.append(definition)
        return definition

    def register_field_mutator(self, definition: ResourceFieldMutatorDefinition) -> ResourceFieldMutatorDefinition:
        mutators = self._field_mutators.setdefault(definition.resource, [])
        mutators.append(definition)
        return definition

    def register_sort(self, definition: ResourceSortDefinition) -> ResourceSortDefinition:
        sorts = self._sorts.setdefault(definition.resource, [])
        operation = str(definition.operation or "add").strip().lower()
        if operation != "add":
            sorts.append(definition)
            return definition

        add_definitions = [
            item
            for item in sorts
            if str(item.operation or "add").strip().lower() == "add"
        ]
        existing_index = next(
            (
                index
                for index, sort in enumerate(add_definitions)
                if sort.sort == definition.sort and sort.module_id == definition.module_id
            ),
            None,
        )
        if existing_index is not None:
            add_definitions[existing_index] = definition
        else:
            add_definitions.append(definition)
        add_definitions.sort(key=lambda item: (item.resource, item.sort, item.module_id))
        operation_definitions = [
            item
            for item in sorts
            if str(item.operation or "add").strip().lower() != "add"
        ]
        self._sorts[definition.resource] = [*add_definitions, *operation_definitions]
        return definition

    def register_filter(self, definition: ResourceFilterDefinition) -> ResourceFilterDefinition:
        filters = self._filters.setdefault(definition.resource, [])
        operation = str(definition.operation or "add").strip().lower()
        if operation != "add":
            filters.append(definition)
            return definition

        existing_index = next(
            (
                index
                for index, item in enumerate(filters)
                if item.filter == definition.filter
                and item.module_id == definition.module_id
                and str(item.operation or "add").strip().lower() == "add"
            ),
            None,
        )
        if existing_index is not None:
            filters[existing_index] = definition
        else:
            filters.append(definition)
        self._register_search_filter(definition)
        return definition

    def get_resource(self, resource: str) -> ResourceDefinition | None:
        enabled_module_ids = self._get_enabled_module_ids()
        definition = self._definitions.get(resource)
        if definition is None:
            return None
        if not self._is_module_enabled(definition.module_id, enabled_module_ids):
            return None
        return definition

    def get_resource_object(self, resource: str) -> Resource | None:
        enabled_module_ids = self._get_enabled_module_ids()
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return None
        if not self._is_module_enabled(getattr(resource_object, "module_id", "core"), enabled_module_ids):
            return None
        return resource_object

    def resolve_resource(self, resource: str) -> Resource | None:
        normalized = str(resource or "").strip()
        if not normalized:
            return None
        if normalized in self._resolved_resource_cache:
            return self._resolved_resource_cache[normalized]
        resource_object = self._resource_objects.get(normalized)
        if resource_object is None:
            definition = self._definitions.get(normalized)
            if definition is None:
                return None
            resource_object = _DefinitionBackedResource(definition)
        resource_object = resource_object.boot(self)
        self._resolved_resource_cache[normalized] = resource_object
        return resource_object

    def get_resources(self) -> List[ResourceDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            self._definitions[key]
            for key in sorted(self._definitions.keys())
            if self._is_module_enabled(self._definitions[key].module_id, enabled_module_ids)
        ]

    def get_fields(self, resource: str) -> List[ResourceFieldDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        definitions = [
            self._field_to_definition(resource, definition)
            for definition in self._resource_fields(resource)
        ]
        definitions.extend([
            definition
            for definition in self._fields.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ])
        return definitions

    def get_effective_fields(self, resource: str, context: dict | None = None) -> List[ResourceFieldDefinition]:
        output: list[ResourceFieldDefinition] = []
        resolved_context = dict(context or {})

        for definition in self.get_fields(resource):
            output.append(definition)

        for definition in self.get_field_mutators(resource):
            if self._mutator_kind(definition) == "relationship":
                continue
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                added = self._field_mutator_result(definition, None)
                if added is not None:
                    output.append(added)
            elif operation == "before":
                added = self._field_mutator_result(definition, None)
                if added is not None:
                    self._insert_before(output, definition.anchor, added)
            elif operation == "after":
                added = self._field_mutator_result(definition, None)
                if added is not None:
                    self._insert_after(output, definition.anchor, added)
            elif operation == "remove":
                output = [item for item in output if item.field != definition.field]
            elif operation == "mutate":
                output = [
                    self._field_mutator_result(definition, item) if item.field == definition.field else item
                    for item in output
                ]
                output = [item for item in output if item is not None]
        return output

    def get_relationships(self, resource: str) -> List[ResourceRelationshipDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        definitions = [
            self._relationship_to_definition(resource, definition)
            for definition in self._resource_relationships(resource)
        ]
        definitions.extend([
            definition
            for definition in self._relationships.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ])
        return definitions

    def get_effective_relationships(self, resource: str, context: dict | None = None) -> List[ResourceRelationshipDefinition]:
        output: list[ResourceRelationshipDefinition] = []
        resolved_context = dict(context or {})

        for definition in self.get_relationships(resource):
            output.append(definition)

        for definition in self.get_field_mutators(resource):
            if self._mutator_kind(definition) == "field":
                continue
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                added = self._relationship_mutator_result(definition, None)
                if added is not None:
                    output.append(added)
            elif operation == "before":
                added = self._relationship_mutator_result(definition, None)
                if added is not None:
                    self._insert_before(output, definition.anchor, added)
            elif operation == "after":
                added = self._relationship_mutator_result(definition, None)
                if added is not None:
                    self._insert_after(output, definition.anchor, added)
            elif operation == "remove":
                output = [item for item in output if item.relationship != definition.field]
            elif operation == "mutate":
                output = [
                    self._relationship_mutator_result(definition, item) if item.relationship == definition.field else item
                    for item in output
                ]
                output = [item for item in output if item is not None]
        return output

    def get_all_fields(self) -> List[ResourceFieldDefinition]:
        definitions: List[ResourceFieldDefinition] = []
        for resource in sorted(set(self._fields.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_fields(resource))
        return definitions

    def get_field_mutators(self, resource: str) -> List[ResourceFieldMutatorDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            definition
            for definition in self._field_mutators.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ]

    def get_all_field_mutators(self) -> List[ResourceFieldMutatorDefinition]:
        definitions: List[ResourceFieldMutatorDefinition] = []
        for resource in sorted(set(self._field_mutators.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_field_mutators(resource))
        return definitions

    def get_all_relationships(self) -> List[ResourceRelationshipDefinition]:
        definitions: List[ResourceRelationshipDefinition] = []
        for resource in sorted(set(self._relationships.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_relationships(resource))
        return definitions

    def get_endpoints(self, resource: str) -> List[ResourceEndpointDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        definitions = [
            self._endpoint_to_definition(resource, definition)
            for definition in self._resource_endpoints(resource)
        ]
        definitions.extend([
            definition
            for definition in self._endpoints.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ])
        return definitions

    def get_all_endpoints(self) -> List[ResourceEndpointDefinition]:
        definitions: List[ResourceEndpointDefinition] = []
        for resource in sorted(set(self._endpoints.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_endpoints(resource))
        return definitions

    def get_filters(self, resource: str) -> List[ResourceFilterDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        definitions = [
            self._filter_to_definition(resource, definition)
            for definition in self._resource_filters(resource)
        ]
        definitions.extend([
            definition
            for definition in self._filters.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ])
        return definitions

    def get_effective_filters(self, resource: str, context: dict | None = None) -> List[ResourceFilterDefinition]:
        output: list[ResourceFilterDefinition] = []
        resolved_context = dict(context or {})

        for definition in self.get_filters(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "add").strip().lower()
            if operation == "add":
                output.append(definition)
            elif operation == "before_all":
                output.insert(0, definition)
            elif operation == "before":
                self._insert_before(output, definition.anchor, definition)
            elif operation == "after":
                self._insert_after(output, definition.anchor, definition)
            elif operation == "remove":
                output = [item for item in output if item.filter != definition.filter]
            elif operation == "mutate":
                output = [
                    self._filter_mutator_result(definition, item) if item.filter == definition.filter else item
                    for item in output
                ]
                output = [item for item in output if item is not None]
        return output

    def get_all_filters(self) -> List[ResourceFilterDefinition]:
        definitions: List[ResourceFilterDefinition] = []
        for resource in sorted(set(self._filters.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_filters(resource))
        return definitions

    def get_sorts(self, resource: str) -> List[ResourceSortDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        definitions = [
            self._sort_to_definition(resource, definition)
            for definition in self._resource_sorts(resource)
        ]
        definitions.extend([
            definition
            for definition in self._sorts.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ])
        return definitions

    def get_effective_sorts(self, resource: str, context: dict | None = None) -> List[ResourceSortDefinition]:
        output: list[ResourceSortDefinition] = []
        resolved_context = dict(context or {})

        for definition in self.get_sorts(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "add").strip().lower()
            if operation == "add":
                output.append(definition)
            elif operation == "before_all":
                output.insert(0, definition)
            elif operation == "before":
                self._insert_before(output, definition.anchor, definition)
            elif operation == "after":
                self._insert_after(output, definition.anchor, definition)
            elif operation == "remove":
                output = [item for item in output if item.sort != definition.sort]
            elif operation == "mutate":
                output = [
                    self._sort_mutator_result(definition, item) if item.sort == definition.sort else item
                    for item in output
                ]
                output = [item for item in output if item is not None]
        return output

    def get_all_sorts(self) -> List[ResourceSortDefinition]:
        definitions: List[ResourceSortDefinition] = []
        for resource in sorted(set(self._sorts.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_sorts(resource))
        return definitions

    def apply_endpoint_mutators(self, resource: str, endpoint: str, endpoint_object: Any, context: dict | None = None):
        output = endpoint_object
        resolved_context = dict(context or {})
        for definition in self.get_endpoints(resource):
            if definition.endpoint != endpoint:
                continue
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            if definition.mutator is None:
                continue
            output = definition.mutator(output)
        return output

    def apply_endpoint_definitions(self, resource: str, endpoints: List[Any], context: dict | None = None) -> List[Any]:
        output = list(endpoints or [])
        resolved_context = dict(context or {})
        for definition in self.get_endpoints(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "remove":
                output = [item for item in output if self._item_name(item) != definition.endpoint]
                continue
            if definition.mutator is None:
                continue
            if operation == "add":
                output.append(definition.mutator(None))
            elif operation == "before_all":
                output.insert(0, definition.mutator(None))
            elif operation == "before":
                self._insert_before(output, definition.anchor, definition.mutator(None))
            elif operation == "after":
                self._insert_after(output, definition.anchor, definition.mutator(None))
            elif operation == "mutate":
                output = [
                    definition.mutator(item) if self._item_name(item) == definition.endpoint else item
                    for item in output
                ]
        return output

    def get_dispatch_endpoints(self, resource: str, context: dict | None = None) -> List[ResourceEndpointDefinition]:
        output: list[ResourceEndpointDefinition] = []
        resolved_context = dict(context or {})
        for definition in self.get_endpoints(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = self._endpoint_operation(definition)
            if operation == "add":
                if definition.handler is not None or getattr(definition, "kind", ""):
                    output.append(definition)
            elif operation == "before_all":
                if definition.handler is not None or getattr(definition, "kind", ""):
                    output.insert(0, definition)
            elif operation == "before":
                if definition.handler is not None or getattr(definition, "kind", ""):
                    self._insert_before(output, definition.anchor, definition)
            elif operation == "after":
                if definition.handler is not None or getattr(definition, "kind", ""):
                    self._insert_after(output, definition.anchor, definition)
            elif operation == "remove":
                output = [
                    item
                    for item in output
                    if not self._endpoint_definition_matches(item, definition.endpoint)
                ]
            elif operation == "mutate":
                output = [
                    self._mutate_endpoint_definition(definition, item)
                    if self._endpoint_definition_matches(item, definition.endpoint)
                    else item
                    for item in output
                ]
        return output

    def get_dispatch_endpoint(
        self,
        resource: str,
        endpoint: str,
        method: str,
        context: dict | None = None,
    ) -> ResourceEndpointDefinition | None:
        normalized_endpoint = self._normalize_endpoint_path(endpoint)
        normalized_method = str(method or "GET").strip().upper()
        resolved_context = dict(context or {})
        for definition in self.get_dispatch_endpoints(resource, resolved_context):
            if normalized_method not in self._normalize_endpoint_methods(definition.methods):
                continue
            if normalized_endpoint not in {
                self._normalize_endpoint_path(definition.endpoint),
                self._normalize_endpoint_path(definition.path),
            }:
                continue
            return definition
        return None

    def apply_field_definitions(self, resource: str, fields: List[Any], context: dict | None = None) -> List[Any]:
        output = list(fields or [])
        resolved_context = dict(context or {})
        for definition in self.get_field_mutators(resource):
            if self._mutator_kind(definition) == "relationship":
                continue
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                output.append(definition.mutator(None))
            elif operation == "before":
                self._insert_before(output, definition.anchor, definition.mutator(None))
            elif operation == "after":
                self._insert_after(output, definition.anchor, definition.mutator(None))
            elif operation == "remove":
                output = [item for item in output if self._item_name(item) != definition.field]
            elif operation == "mutate":
                output = [
                    definition.mutator(item) if self._item_name(item) == definition.field else item
                    for item in output
                ]
        return output

    def apply_sort_definitions(self, resource: str, sorts: List[Any], context: dict | None = None) -> List[Any]:
        output = list(sorts or [])
        resolved_context = dict(context or {})

        for definition in self.get_sorts(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "add").strip().lower()
            if operation == "remove":
                output = [item for item in output if self._item_name(item) != definition.sort]
            elif operation == "mutate" and definition.mutator is not None:
                output = [
                    self._external_sort_mutator_result(definition, item)
                    if self._item_name(item) == definition.sort
                    else item
                    for item in output
                ]

        for definition in self.get_effective_sorts(resource, resolved_context):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "add").strip().lower()
            value = definition.handler
            if operation in {"add", "before_all", "before", "after"}:
                output.append(value)
            elif operation == "remove":
                output = [item for item in output if self._item_name(item) != definition.sort]
        return output

    def build_preload_plan(
        self,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = context or {}
        select_related: list[str] = []
        prefetch_related: list[Any] = []
        prefetch_where: list[tuple[str, Callable[[Any, dict], Any]]] = []
        seen_select: set[str] = set()
        seen_prefetch: set[str] = set()

        selected_fields = set(only or [])
        for definition in self.get_effective_fields(resource, resolved_context):
            if selected_fields and definition.field not in selected_fields:
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
                prefetch_where,
            )

        include_tree = self._build_include_tree(include or ())
        include_set = set(include_tree.keys())
        for definition in self.get_effective_relationships(resource, resolved_context):
            if include_set and definition.relationship not in include_set:
                continue
            if not include_set and definition.relationship not in set():
                continue
            if not self._is_relationship_includable(definition, resolved_context):
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
                prefetch_where,
                include=include,
            )
            nested_include = include_tree.get(definition.relationship) or {}
            if nested_include and definition.resource_type:
                nested_plan = self.build_preload_plan(
                    definition.resource_type,
                    resolved_context,
                    include=tuple(self._flatten_include_tree(nested_include)),
                )
                for item in nested_plan.select_related:
                    nested_item = f"{definition.relationship}__{item}"
                    if nested_item not in seen_select:
                        seen_select.add(nested_item)
                        select_related.append(nested_item)
                for item in nested_plan.prefetch_related:
                    nested_item = self._prefix_prefetch(definition.relationship, item)
                    prefetch_key = self._prefetch_key(nested_item)
                    if prefetch_key and prefetch_key not in seen_prefetch:
                        seen_prefetch.add(prefetch_key)
                        prefetch_related.append(nested_item)
                for relation, callback in nested_plan.prefetch_where:
                    prefetch_where.append((f"{definition.relationship}__{relation}", callback))

        return ResourcePreloadPlan(
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
            prefetch_where=tuple(prefetch_where),
        )

    def apply_preload_plan(
        self,
        queryset,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ):
        plan = self.build_preload_plan(
            resource,
            context,
            only=only,
            include=include,
        )
        if plan.select_related:
            queryset = queryset.select_related(*plan.select_related)
        if plan.prefetch_related:
            queryset = queryset.prefetch_related(*plan.prefetch_related)
        return queryset

    def build_endpoint_preload_plan(
        self,
        resource: str,
        endpoint: str,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = dict(context or {})
        definition = self.get_dispatch_endpoint(
            resource,
            endpoint,
            str(resolved_context.get("method") or "GET"),
            resolved_context,
        )
        if definition is None:
            return ResourcePreloadPlan()

        return self.build_endpoint_definition_preload_plan(definition, resolved_context)

    def build_endpoint_definition_preload_plan(
        self,
        definition: ResourceEndpointDefinition,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = dict(context or {})
        include = tuple(resolved_context.get("include") or definition.default_include or ())
        plan = self.build_preload_plan(definition.resource, resolved_context, include=include)
        select_related = list(plan.select_related)
        prefetch_related = list(plan.prefetch_related)
        prefetch_where = list(plan.prefetch_where)
        seen_select = set(select_related)
        seen_prefetch = {self._prefetch_key(item) for item in prefetch_related}

        self._merge_preload_definition(
            definition,
            resolved_context,
            select_related,
            prefetch_related,
            seen_select,
            seen_prefetch,
            prefetch_where,
            include=include,
        )
        return ResourcePreloadPlan(
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
            prefetch_where=tuple(prefetch_where),
        )

    def apply_resource_payload(
        self,
        resource: str,
        instance: Any,
        payload: dict,
        context: dict | None = None,
        *,
        creating: bool = False,
    ) -> Any:
        resolved_context = dict(context or {})
        resolved_context["creating"] = bool(creating)
        input_payload = dict(payload or {})
        self._run_extension_validators(resource, instance, input_payload, resolved_context)
        fields = {
            definition.field: definition
            for definition in self.get_effective_fields(resource, resolved_context)
        }
        relationships = {
            definition.relationship: definition
            for definition in self.get_effective_relationships(resource, resolved_context)
        }

        missing = [
            definition.field
            for definition in fields.values()
            if (
                (creating and definition.required_on_create)
                or (not creating and definition.required_on_update)
            )
            and definition.field not in input_payload
        ]
        if missing:
            raise JsonApiValidationError(
                f"缺少必填字段: {', '.join(missing)}",
                pointer=f"/data/attributes/{missing[0]}",
            )

        for field_name, value in input_payload.items():
            definition = fields.get(field_name)
            if definition is None:
                continue
            if not self._is_field_writable(definition, instance, resolved_context):
                raise JsonApiForbidden(f"字段不可写: {field_name}", pointer=f"/data/attributes/{field_name}")
            value = self._deserialize_resource_value(definition, value, resolved_context)
            self._validate_resource_value(definition, value, resolved_context)
            self._set_resource_value(definition, instance, value, resolved_context)
        relationship_payload = self._extract_relationship_payload(context)
        missing_relationships = [
            definition.relationship
            for definition in relationships.values()
            if (
                (creating and definition.required_on_create)
                or (not creating and definition.required_on_update)
            )
            and definition.relationship not in relationship_payload
        ]
        if missing_relationships:
            raise JsonApiValidationError(
                f"缺少必填关系: {', '.join(missing_relationships)}",
                pointer=f"/data/relationships/{missing_relationships[0]}",
            )
        for relationship_name, value in relationship_payload.items():
            definition = relationships.get(relationship_name)
            if definition is None:
                continue
            if not self._is_field_writable(definition, instance, resolved_context):
                raise JsonApiForbidden(f"关系不可写: {relationship_name}", pointer=f"/data/relationships/{relationship_name}")
            value = self._deserialize_resource_value(definition, value, resolved_context)
            self._validate_resource_value(definition, value, resolved_context)
            self._set_resource_value(definition, instance, value, resolved_context)
        return instance

    def _run_extension_validators(self, resource: str, instance: Any, payload: dict, context: dict) -> None:
        try:
            from apps.core.extensions.bootstrap import get_extension_host
        except Exception:
            return
        host = get_extension_host()
        if host is None:
            return
        validators = getattr(host, "validators", None)
        if validators is None:
            return
        target_keys = [resource]
        if instance is not None:
            target_keys.extend([
                instance.__class__,
                f"{instance.__class__.__module__}.{instance.__class__.__qualname__}",
            ])
        seen = set()
        definitions = []
        for target in target_keys:
            for definition in validators.get_definitions(target=target):
                key = (definition.module_id, definition.key, definition.target)
                if key in seen:
                    continue
                seen.add(key)
                definitions.append(definition)
        for definition in definitions:
            try:
                definition.callback({
                    "resource": resource,
                    "instance": instance,
                    "payload": payload,
                    "context": context,
                    "creating": bool(context.get("creating")),
                }, context)
            except JsonApiValidationError:
                raise
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer="/data/attributes") from exc

    def dispatch_resource_endpoint(self, definition: ResourceEndpointDefinition, context: dict):
        from apps.core.resource_endpoint_runner import ResourceEndpointRunner

        return ResourceEndpointRunner(self).run(definition, ensure_resource_context(context))

    def _dispatch_index(self, resource_object: DatabaseResource, definition: ResourceEndpointDefinition, context: dict):
        self._call_endpoint_before(definition, context)
        queryset = resource_object.scope(resource_object.query(context), context)
        pagination = self._resolve_endpoint_pagination(definition, context) if definition.paginate else None
        include = self._resolve_endpoint_include(definition, context)
        sort = self._resolve_endpoint_sort(definition, context)
        filters = self._resolve_endpoint_filters(context)
        search_results = self._search_resource_index(
            resource_object,
            definition,
            queryset,
            context,
            filters=filters,
            sort=sort,
            pagination=pagination,
        )
        total = None
        if search_results is not None:
            queryset = search_results.results
            total = search_results.total
            if sort and not search_results.sort_applied:
                queryset = self.apply_named_sort(definition.resource, queryset, sort, context)
        else:
            if sort:
                queryset = self.apply_named_sort(definition.resource, queryset, sort, context)
            total = resource_object.count(queryset, context) if definition.paginate else None
        queryset = self.apply_preload_plan(
            queryset,
            definition.resource,
            context,
            include=include,
        )
        if pagination and not (search_results is not None and search_results.pagination_applied):
            pagination_context = dict(context)
            pagination_context["pagination"] = pagination
            queryset = resource_object.paginate(queryset, pagination_context)
        results = resource_object.results(queryset, context)
        results = self._call_endpoint_after(definition, context, results)
        document = self.serialize_jsonapi_document(definition.resource, results, context, include=include, many=True)
        if not definition.paginate:
            return document
        if total is None:
            total = resource_object.count(queryset, context)
        meta = dict(document.get("meta") or {})
        meta.update({
            "total": total,
            "count": len(document.get("data") or []),
            "limit": pagination["limit"] if pagination else None,
            "offset": pagination["offset"] if pagination else 0,
        })
        meta.update(self._resolve_endpoint_meta(definition, context, {"results": results, "total": total}) or {})
        document["meta"] = meta
        links = self._resolve_endpoint_links(definition, context, {"results": results, "total": total})
        if links:
            document["links"] = links
        return document

    def _dispatch_show(self, resource_object: DatabaseResource, definition: ResourceEndpointDefinition, context: dict):
        self._call_endpoint_before(definition, context)
        instance = resource_object.find(str(context.get("object_id") or ""), context)
        if instance is None:
            raise LookupError("资源不存在")
        self._ensure_resource_ability(resource_object, definition, instance, context)
        instance = self._call_endpoint_after(definition, context, instance)
        document = self.serialize_jsonapi_document(
            definition.resource,
            instance,
            context,
            include=self._resolve_endpoint_include(definition, context),
        )
        self._merge_endpoint_document_meta_links(document, definition, context, instance)
        return document

    def _dispatch_create(self, resource_object: DatabaseResource, definition: ResourceEndpointDefinition, context: dict):
        self._call_endpoint_before(definition, context)
        self._ensure_resource_ability(resource_object, definition, None, context)
        instance = resource_object.new_model(context)
        self._parse_jsonapi_data(context, definition.resource, creating=True)
        self.apply_resource_payload(
            definition.resource,
            instance,
            self._extract_resource_payload(context),
            context,
            creating=True,
        )
        instance = resource_object.create_action(instance, context)
        instance = self._call_endpoint_after(definition, context, instance)
        document = self.serialize_jsonapi_document(
            definition.resource,
            instance,
            context,
            include=self._resolve_endpoint_include(definition, context),
        )
        self._merge_endpoint_document_meta_links(document, definition, context, instance)
        return 201, document

    def _dispatch_update(self, resource_object: DatabaseResource, definition: ResourceEndpointDefinition, context: dict):
        self._call_endpoint_before(definition, context)
        instance = resource_object.find(str(context.get("object_id") or ""), context)
        if instance is None:
            raise LookupError("资源不存在")
        self._ensure_resource_ability(resource_object, definition, instance, context)
        self._parse_jsonapi_data(context, definition.resource, creating=False, instance=instance, resource_object=resource_object)
        self.apply_resource_payload(
            definition.resource,
            instance,
            self._extract_resource_payload(context),
            context,
            creating=False,
        )
        instance = resource_object.update_action(instance, context)
        instance = self._call_endpoint_after(definition, context, instance)
        document = self.serialize_jsonapi_document(
            definition.resource,
            instance,
            context,
            include=self._resolve_endpoint_include(definition, context),
        )
        self._merge_endpoint_document_meta_links(document, definition, context, instance)
        return document

    def _dispatch_delete(self, resource_object: DatabaseResource, definition: ResourceEndpointDefinition, context: dict):
        self._call_endpoint_before(definition, context)
        instance = resource_object.find(str(context.get("object_id") or ""), context)
        if instance is None:
            raise LookupError("资源不存在")
        self._ensure_resource_ability(resource_object, definition, instance, context)
        resource_object.delete_action(instance, context)
        self._call_endpoint_after(definition, context, None)
        return 204, None

    @staticmethod
    def _extract_resource_payload(context: dict) -> dict:
        payload = context.get("payload") or {}
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            data = payload["data"]
            if isinstance(data.get("attributes"), dict):
                return dict(data["attributes"])
            return {}
        if payload:
            raise BadJsonApiRequest("data must be an object", pointer="/data")
        return {}

    def _parse_jsonapi_data(
        self,
        context: dict,
        resource: str,
        *,
        creating: bool,
        instance: Any | None = None,
        resource_object: Resource | None = None,
    ) -> dict:
        payload = context.get("payload") or {}
        if not isinstance(payload, dict):
            raise BadJsonApiRequest("request body must be an object")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BadJsonApiRequest("data must be an object", pointer="/data")
        data_type = data.get("type")
        if data_type is None:
            raise BadJsonApiRequest("data.type must be present", pointer="/data/type")
        if str(data_type) != str(resource):
            raise JsonApiConflict("collection does not support this resource type", pointer="/data/type")
        if creating and data.get("id") not in (None, ""):
            raise JsonApiForbidden("Client-generated IDs are not supported", pointer="/data/id")
        if instance is not None and data.get("id") not in (None, ""):
            expected_id = self._resource_identifier(resource, instance, context, resource_object)
            if str(data.get("id")) != str(expected_id):
                raise JsonApiConflict("data.id does not match the resource ID", pointer="/data/id")
        if "attributes" in data and not isinstance(data.get("attributes"), dict):
            raise BadJsonApiRequest("data.attributes must be an object", pointer="/data/attributes")
        if "relationships" in data and not isinstance(data.get("relationships"), dict):
            raise BadJsonApiRequest("data.relationships must be an object", pointer="/data/relationships")
        mutate = getattr(resource_object, "mutate_data_before_validation", None)
        if callable(mutate):
            mutated = mutate(context, data)
            if isinstance(mutated, dict):
                payload["data"] = mutated
                context["payload"] = payload
                data = mutated
        self._run_validation_factory(resource_object, context, data)
        return data

    def _run_validation_factory(self, resource_object: Resource | None, context: dict, data: dict) -> None:
        if resource_object is None:
            return
        errors = self._collect_payload_validation_errors(resource_object, context, data)
        factory = getattr(resource_object, "validation_factory", lambda: None)()
        if factory is None:
            factory = ResourceValidatorFactory()
        result = None
        validation_payload = self._build_validation_payload(resource_object, context, data)
        try:
            result = factory(data, context, validation_payload)
        except TypeError:
            try:
                result = factory(data, context)
            except TypeError:
                result = self._invoke_validation_factory_object(factory, validation_payload, data, context)
        if result:
            errors.extend(self._normalize_validation_factory_errors(result))
        if errors:
            raise JsonApiValidationError("Validation failed", errors=errors)

    def _build_validation_payload(self, resource_object: Resource, context: dict, data: dict) -> dict:
        collected = self._collect_validation_state(resource_object, context)
        return {
            "attributes": data.get("attributes") or {},
            "relationships": data.get("relationships") or {},
            "rules": collected["rules"],
            "messages": collected["messages"],
            "validation_attributes": collected["validation_attributes"],
        }

    def _collect_validation_rules(self, resource_object: Resource, context: dict) -> dict:
        return self._collect_validation_state(resource_object, context)["rules"]

    def _collect_validation_state(self, resource_object: Resource, context: dict) -> dict:
        rules = {"attributes": {}, "relationships": {}}
        messages = dict(getattr(resource_object, "validation_messages", lambda: {})() or {})
        attributes = dict(getattr(resource_object, "validation_attributes", lambda: {})() or {})
        for definition in self.get_effective_fields(resource_object.type(), context):
            if not self._is_field_writable(definition, context.get("model"), context):
                continue
            self._merge_definition_validation_state(
                rules["attributes"],
                messages,
                attributes,
                definition,
                definition.field,
                context,
            )
        for definition in self.get_effective_relationships(resource_object.type(), context):
            if not self._is_field_writable(definition, context.get("model"), context):
                continue
            self._merge_definition_validation_state(
                rules["relationships"],
                messages,
                attributes,
                definition,
                definition.relationship,
                context,
            )
        return {
            "rules": rules,
            "messages": messages,
            "validation_attributes": attributes,
        }

    @staticmethod
    def _merge_definition_validation_state(
        rules: dict,
        messages: dict,
        attributes: dict,
        definition: Any,
        name: str,
        context: dict,
    ) -> None:
        field_object = getattr(definition, "field_object", None)
        object_rules = {}
        has_validation_rules = bool(getattr(definition, "has_validation_rules", False))
        used_field_object_rules = False
        if field_object is not None and has_validation_rules:
            get_rules = getattr(field_object, "get_validation_rules", None)
            if callable(get_rules):
                used_field_object_rules = True
                object_rules = get_rules(context) or {}
            get_messages = getattr(field_object, "get_validation_messages", None)
            if callable(get_messages):
                messages.update(get_messages(context) or {})
            get_attributes = getattr(field_object, "get_validation_attributes", None)
            if callable(get_attributes):
                attributes.update(get_attributes(context) or {})

        if object_rules:
            for key, values in object_rules.items():
                rules[str(key)] = tuple(values or ())
            return

        if used_field_object_rules:
            return

        if not has_validation_rules:
            return
        values = tuple(getattr(definition, "validation_rules", ()) or ())
        if values:
            rules[name] = values

    @staticmethod
    def _invoke_validation_factory_object(factory: Any, validation_payload: dict, data: dict, context: dict):
        make = getattr(factory, "make", None)
        if callable(make):
            errors = []
            for section in ("attributes", "relationships"):
                section_data = dict(validation_payload[section])
                other_section = "relationships" if section == "attributes" else "attributes"
                section_data[other_section] = validation_payload[other_section]
                try:
                    validator = make(
                        section_data,
                        validation_payload["rules"][section],
                        validation_payload["messages"],
                        validation_payload["validation_attributes"],
                        section=section,
                    )
                except TypeError:
                    validator = make(
                        section_data,
                        validation_payload["rules"][section],
                        validation_payload["messages"],
                        validation_payload["validation_attributes"],
                    )
                errors.extend(ResourceRegistry._validator_errors(section, validator))
            return errors
        validate = getattr(factory, "validate", None)
        if callable(validate):
            try:
                return validate(validation_payload, context)
            except TypeError:
                return validate(data, context)
        return None

    @staticmethod
    def _validator_errors(section: str, validator: Any) -> list[dict]:
        if validator is None:
            return []
        if isinstance(validator, ResourceValidator):
            return validator.jsonapi_errors()
        fails = getattr(validator, "fails", None)
        if callable(fails) and not fails():
            return []
        jsonapi_errors = getattr(validator, "jsonapi_errors", None)
        if callable(jsonapi_errors):
            try:
                return list(jsonapi_errors(section=section))
            except TypeError:
                return list(jsonapi_errors())
        messages = getattr(validator, "messages", None)
        if callable(messages):
            output = []
            for field, values in (messages() or {}).items():
                if isinstance(values, str):
                    values = [values]
                output.append(ResourceValidationError(
                    field=str(field),
                    message=" ".join(str(item) for item in values),
                    section=section,
                ).as_jsonapi_error())
            return output
        if isinstance(validator, (list, tuple)):
            return ResourceRegistry._normalize_validation_factory_errors(validator)
        if isinstance(validator, dict):
            return ResourceRegistry._normalize_validation_factory_errors(validator)
        return []

    def _collect_payload_validation_errors(self, resource_object: Resource, context: dict, data: dict) -> list[dict]:
        errors: list[dict] = []
        validation_state = self._collect_validation_state(resource_object, context)
        messages = validation_state["messages"]
        attributes = validation_state["validation_attributes"]
        for definition in self.get_effective_fields(resource_object.type(), context):
            attributes_payload = data.get("attributes") or {}
            if definition.field not in attributes_payload:
                continue
            value = attributes_payload.get(definition.field)
            try:
                value = self._deserialize_resource_value(definition, value, context)
                self._validate_resource_value(definition, value, context)
            except JsonApiValidationError as exc:
                errors.append(self._validation_error_to_document(exc, definition, messages, attributes))
        for definition in self.get_effective_relationships(resource_object.type(), context):
            relationships_payload = data.get("relationships") or {}
            if definition.relationship not in relationships_payload:
                continue
            value = relationships_payload.get(definition.relationship)
            if isinstance(value, dict) and "data" in value:
                value = value["data"]
            try:
                value = self._deserialize_resource_value(definition, value, context)
                self._validate_resource_value(definition, value, context)
            except JsonApiValidationError as exc:
                errors.append(self._validation_error_to_document(exc, definition, messages, attributes))
        return errors

    @staticmethod
    def _validation_error_to_document(exc: JsonApiValidationError, definition: Any, messages: dict, attributes: dict) -> dict:
        pointer = getattr(exc, "pointer", "") or ResourceRegistry._validation_pointer(definition)
        key = pointer.removeprefix("/data/attributes/").removeprefix("/data/relationships/")
        label = attributes.get(key, key)
        detail = messages.get(key) or messages.get(pointer) or str(exc)
        if label and key and label != key:
            detail = detail.replace(key, str(label))
        return {"source": {"pointer": pointer}, "detail": detail}

    @staticmethod
    def _normalize_validation_factory_errors(result: Any) -> list[dict]:
        errors = []
        if isinstance(result, dict):
            iterable = result.items()
        else:
            iterable = result
        for item in iterable:
            if isinstance(item, tuple) and len(item) == 2:
                field, message = item
                pointer = str(field)
                if not pointer.startswith("/"):
                    pointer = f"/data/attributes/{pointer}"
                errors.append({"source": {"pointer": pointer}, "detail": str(message)})
            elif isinstance(item, dict):
                errors.append(item)
            elif isinstance(item, ResourceValidationError):
                errors.append(item.as_jsonapi_error())
        return errors

    @staticmethod
    def _call_endpoint_before(definition: ResourceEndpointDefinition, context: dict) -> None:
        if callable(definition.before_hook):
            definition.before_hook(context)

    @staticmethod
    def _call_endpoint_after(definition: ResourceEndpointDefinition, context: dict, value: Any):
        if callable(definition.after_hook):
            updated = definition.after_hook(context, value)
            if updated is not None:
                return updated
        return value

    @staticmethod
    def _resolve_endpoint_meta(definition: ResourceEndpointDefinition, context: dict, value: Any) -> dict:
        if callable(definition.meta_resolver):
            output = definition.meta_resolver(context, value)
            if isinstance(output, dict):
                return output
        return {}

    @staticmethod
    def _resolve_endpoint_links(definition: ResourceEndpointDefinition, context: dict, value: Any) -> dict:
        if callable(definition.links_resolver):
            output = definition.links_resolver(context, value)
            if isinstance(output, dict):
                return output
        return {}

    def _merge_endpoint_document_meta_links(
        self,
        document: dict,
        definition: ResourceEndpointDefinition,
        context: dict,
        value: Any,
    ) -> None:
        meta = self._resolve_endpoint_meta(definition, context, value)
        if meta:
            document["meta"] = {**dict(document.get("meta") or {}), **meta}
        links = self._resolve_endpoint_links(definition, context, value)
        if links:
            document["links"] = {**dict(document.get("links") or {}), **links}

    @staticmethod
    def _extract_relationship_payload(context: dict) -> dict:
        context = context or {}
        payload = context.get("payload") or {}
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return {}
        relationships = payload["data"].get("relationships")
        if not isinstance(relationships, dict):
            return {}
        output = {}
        for name, value in relationships.items():
            if isinstance(value, dict) and "data" in value:
                output[name] = value["data"]
            else:
                output[name] = value
        return output

    @staticmethod
    def _ensure_resource_ability(
        resource_object: DatabaseResource,
        definition: ResourceEndpointDefinition,
        instance: Any | None,
        context: dict,
    ) -> None:
        ability = definition.ability
        if ability is None and not definition.forum_permission:
            ability = definition.permission
        if callable(ability):
            ability = ability(instance, context) if instance is not None else ability(context)
        ability = str(ability or "").strip()
        if not ability:
            return
        try:
            from apps.core.extensions.policy_runtime_service import evaluate_model_policy

            policy_decision = evaluate_model_policy(
                ability,
                user=context.get("user"),
                model=instance or getattr(resource_object, "model", None),
                default=None,
                resource=definition.resource,
                endpoint=definition.endpoint,
                context=context,
            )
        except Exception:
            policy_decision = None
        if policy_decision is False:
            raise PermissionError("无权限")
        if policy_decision is True:
            return
        if not resource_object.can(context.get("user"), ability, instance, context):
            raise PermissionError("无权限")

    @staticmethod
    def _resolve_endpoint_include(definition: ResourceEndpointDefinition, context: dict) -> tuple[str, ...]:
        raw_include = context.get("query", {}).get("include") if isinstance(context.get("query"), dict) else None
        if raw_include:
            if isinstance(raw_include, str):
                return tuple(item.strip() for item in raw_include.split(",") if item.strip())
            if isinstance(raw_include, (list, tuple)):
                return tuple(str(item).strip() for item in raw_include if str(item).strip())
        return tuple(definition.default_include or ())

    @staticmethod
    def _resolve_endpoint_sort(definition: ResourceEndpointDefinition, context: dict) -> str:
        query = context.get("query") if isinstance(context.get("query"), dict) else {}
        return str(query.get("sort") or definition.default_sort or "").strip()

    @staticmethod
    def _resolve_endpoint_filters(context: dict) -> dict[str, Any]:
        query = context.get("query") if isinstance(context.get("query"), dict) else {}
        filters: dict[str, Any] = {}
        for key, value in query.items():
            normalized = str(key or "").strip()
            if normalized == "filter":
                if isinstance(value, dict):
                    filters.update(value)
                elif value not in (None, ""):
                    filters["q"] = value
                continue
            if normalized.startswith("filter[") and normalized.endswith("]"):
                name = normalized[len("filter["):-1].strip()
                if name:
                    filters[name] = value
        return filters

    @staticmethod
    def _resolve_endpoint_pagination(definition: ResourceEndpointDefinition, context: dict) -> dict[str, int]:
        query = context.get("query") if isinstance(context.get("query"), dict) else {}
        default_limit = max(1, int(definition.pagination_default_limit or 20))
        max_limit = max(1, int(definition.pagination_max_limit or default_limit))
        raw_limit = query.get("page[limit]", default_limit)
        raw_offset = query.get("page[offset]", None)
        raw_page_number = query.get("page[number]", None)

        limit = ResourceRegistry._parse_non_negative_int(raw_limit, "page[limit]")
        if limit < 1:
            raise ValueError("page[limit] must be at least 1")
        limit = min(limit, max_limit)

        if raw_page_number not in (None, ""):
            page_number = ResourceRegistry._parse_non_negative_int(raw_page_number, "page[number]")
            if page_number < 1:
                raise ValueError("page[number] must be at least 1")
            offset = (page_number - 1) * limit
        else:
            offset = ResourceRegistry._parse_non_negative_int(raw_offset or 0, "page[offset]")
        return {"limit": limit, "offset": offset}

    @staticmethod
    def _parse_non_negative_int(value: Any, name: str) -> int:
        try:
            output = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer")
        if output < 0:
            raise ValueError(f"{name} must be at least 0")
        return output

    @staticmethod
    def _deserialize_resource_value(definition: Any, value: Any, context: dict) -> Any:
        if value is None:
            return None
        field_object = getattr(definition, "field_object", None)
        deserialize = getattr(field_object, "deserialize", None)
        if callable(deserialize):
            try:
                return deserialize(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceRegistry._validation_pointer(definition)) from exc
        value_type = str(getattr(definition, "value_type", "") or "").strip().lower()
        name = str(
            getattr(definition, "field", "")
            or getattr(definition, "relationship", "")
            or "value"
        )
        if value_type in {"", "any"}:
            return value
        if value_type == "string":
            if not isinstance(value, str):
                raise JsonApiValidationError(f"{name} must be a string", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        if value_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise JsonApiValidationError(f"{name} must be a number", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        if value_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise JsonApiValidationError(f"{name} must be an integer", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        if value_type == "boolean":
            if not isinstance(value, bool):
                raise JsonApiValidationError(f"{name} must be a boolean", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        if value_type == "array":
            if not isinstance(value, list):
                raise JsonApiValidationError(f"{name} must be an array", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        if value_type == "object":
            if not isinstance(value, dict):
                raise JsonApiValidationError(f"{name} must be an object", pointer=ResourceRegistry._validation_pointer(definition))
            return value
        return value

    @staticmethod
    def _validate_resource_value(definition: Any, value: Any, context: dict) -> None:
        name = str(
            getattr(definition, "field", "")
            or getattr(definition, "relationship", "")
            or "value"
        )
        if value is None:
            if not bool(getattr(definition, "nullable", False)):
                raise JsonApiValidationError(f"{name} cannot be null", pointer=ResourceRegistry._validation_pointer(definition))
            return
        field_object = getattr(definition, "field_object", None)
        validate = getattr(field_object, "validate", None)
        if callable(validate):
            try:
                validate(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceRegistry._validation_pointer(definition)) from exc
            return
        for rule in getattr(definition, "validation_rules", ()) or ():
            ResourceRegistry._validate_resource_rule(name, rule, value, context, definition)
        validator = getattr(definition, "validator", None)
        if validator is not None:
            try:
                validator(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceRegistry._validation_pointer(definition)) from exc

    @staticmethod
    def _validate_resource_rule(name: str, rule: Any, value: Any, context: dict, definition: Any = None) -> None:
        if callable(rule):
            try:
                rule(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(
                    str(exc),
                    pointer=ResourceRegistry._validation_pointer(definition),
                ) from exc
            return
        if isinstance(rule, str):
            ResourceRegistry._validate_named_resource_rule(name, rule, value, definition=definition)
            return
        if not isinstance(rule, (tuple, list)) or not rule:
            return
        rule_name = str(rule[0] or "").strip()
        argument = rule[1] if len(rule) > 1 else None
        ResourceRegistry._validate_named_resource_rule(name, rule_name, value, argument, definition=definition)

    @staticmethod
    def _validate_named_resource_rule(name: str, rule_name: str, value: Any, argument: Any = None, definition: Any = None) -> None:
        pointer = ResourceRegistry._validation_pointer(definition)
        if rule_name == "email":
            if not isinstance(value, str) or "@" not in value:
                raise JsonApiValidationError(f"{name} must be a valid email", pointer=pointer)
            return
        if rule_name == "min":
            if value < argument:
                raise JsonApiValidationError(f"{name} must be at least {argument}", pointer=pointer)
            return
        if rule_name == "max":
            if value > argument:
                raise JsonApiValidationError(f"{name} must be at most {argument}", pointer=pointer)
            return
        if rule_name == "min_length":
            if len(value) < int(argument):
                raise JsonApiValidationError(f"{name} length must be at least {argument}", pointer=pointer)
            return
        if rule_name == "max_length":
            if len(value) > int(argument):
                raise JsonApiValidationError(f"{name} length must be at most {argument}", pointer=pointer)
            return
        if rule_name == "in":
            compared_value = str(value["id"]) if ResourceRegistry._is_jsonapi_identifier(value) else value
            if compared_value not in set(argument or ()):
                raise JsonApiValidationError(f"{name} is invalid", pointer=pointer)
            return
        if rule_name == "regex":
            import re

            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                raise JsonApiValidationError(f"{name} format is invalid", pointer=pointer)

    @staticmethod
    def _validation_pointer(definition: Any) -> str:
        field = str(getattr(definition, "field", "") or "")
        if field:
            return f"/data/attributes/{field}"
        relationship = str(getattr(definition, "relationship", "") or "")
        if relationship:
            return f"/data/relationships/{relationship}"
        return "/data"

    def serialize(
        self,
        resource: str,
        instance: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> dict:
        resolved_context = context or {}
        payload = {}

        resource_definition = self.get_resource(resource)
        if resource_definition:
            payload.update(resource_definition.resolver(instance, resolved_context) or {})

        selected_fields = set(only or [])
        for definition in self.get_effective_fields(resource, resolved_context):
            if selected_fields and definition.field not in selected_fields:
                continue
            if not self._is_field_visible(definition, instance, resolved_context):
                continue
            payload[definition.field] = definition.resolver(instance, resolved_context)

        payload = self.apply_payload_field_mutators(resource, payload, resolved_context)

        include_set = set(include or [])
        if include_set:
            for definition in self.get_effective_relationships(resource, resolved_context):
                if definition.relationship not in include_set:
                    continue
                if not self._is_relationship_visible(definition, instance, resolved_context):
                    continue
                if not self._is_relationship_includable(definition, resolved_context):
                    continue
                payload[definition.relationship] = self._serialize_plain_relationship(
                    definition,
                    definition.resolver(instance, resolved_context),
                    resolved_context,
                )
        return payload

    def _serialize_plain_relationship(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
    ):
        if definition.many:
            return [
                self._serialize_plain_related_item(definition, item, context)
                for item in ResourceSerializer.relationship_values(value, many=True)
                if item is not None
            ]
        return self._serialize_plain_related_item(definition, value, context)

    def _serialize_plain_related_item(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
    ):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return value
        resource_type = ResourceSerializer(self, context).related_resource_type(definition, value, ensure_resource_context(context))
        if not resource_type or self.get_resource(resource_type) is None:
            return value
        return self.serialize(resource_type, value, context)

    def serialize_jsonapi_document(
        self,
        resource: str,
        data: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
        many: bool = False,
    ) -> dict:
        serializer = ResourceSerializer(self, context)
        return serializer.document(resource, data, only=only, include=include, many=many)

    def serialize_jsonapi_resource(
        self,
        resource: str,
        instance: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include_tree: dict[str, dict] | None = None,
        included: dict[tuple[str, str], tuple[tuple[str, str], dict]] | None = None,
        deferred: list[Callable[[], None]] | None = None,
    ) -> dict:
        return self._serialize_jsonapi_resource_internal(
            resource,
            instance,
            context,
            only=only,
            include_tree=include_tree,
            included=included,
            deferred=deferred,
        )

    def _serialize_jsonapi_resource_internal(
        self,
        resource: str,
        instance: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include_tree: dict[str, dict] | None = None,
        included: dict[tuple[str, str], tuple[tuple[str, str], dict]] | None = None,
        deferred: list[Callable[[], None]] | None = None,
    ) -> dict:
        serializer = ResourceSerializer(self, context)
        if included is not None:
            serializer.included = included
        if deferred is not None:
            serializer.deferred = deferred
        return serializer._build_resource(resource, instance, only=only, include_tree=include_tree or {})

    def apply_payload_field_mutators(self, resource: str, payload: dict, context: dict | None = None) -> dict:
        output = dict(payload or {})
        resolved_context = dict(context or {})
        for definition in self.get_field_mutators(resource):
            if not self._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                try:
                    mutated = definition.mutator(output.get(definition.field))
                except (AttributeError, TypeError):
                    continue
                if not self._is_resource_definition_mutation(mutated):
                    output[definition.field] = mutated
            elif operation == "remove":
                output.pop(definition.field, None)
            elif operation == "mutate" and definition.field in output:
                try:
                    mutated = definition.mutator(output[definition.field])
                except (AttributeError, TypeError):
                    continue
                if not self._is_resource_definition_mutation(mutated):
                    output[definition.field] = mutated
        return output

    @staticmethod
    def _build_include_tree(include: Tuple[str, ...] | List[str]) -> dict[str, dict]:
        tree: dict[str, dict] = {}
        for item in include or ():
            current = tree
            for part in str(item or "").split("."):
                normalized = part.strip()
                if not normalized:
                    continue
                current = current.setdefault(normalized, {})
        return tree

    @staticmethod
    def _flatten_include_tree(tree: dict[str, dict], prefix: str = "") -> list[str]:
        output: list[str] = []
        for name, children in tree.items():
            path = f"{prefix}.{name}" if prefix else name
            output.append(path)
            output.extend(ResourceRegistry._flatten_include_tree(children, path))
        return output

    @staticmethod
    def _prefix_prefetch(prefix: str, item: Any) -> Any:
        if isinstance(item, str):
            return f"{prefix}__{item}"
        return item

    def _add_jsonapi_included(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
        include_tree: dict,
        included: dict[tuple[str, str], tuple[tuple[str, str], dict]] | None,
        deferred: list[Callable[[], None]] | None = None,
    ) -> None:
        serializer = ResourceSerializer(self, context)
        serializer.included = included if included is not None else {}
        if deferred is not None:
            serializer.deferred = deferred
        serializer.add_relationship_included(definition, value, ensure_resource_context(context), include_tree)

    def _set_jsonapi_value(
        self,
        payload: dict,
        key: str,
        value: Any,
        deferred: list[Callable[[], None]] | None,
    ) -> None:
        serializer = ResourceSerializer(self)
        if deferred is not None:
            serializer.deferred = deferred
        serializer.set_value(payload, key, value)
        if deferred is None:
            serializer.resolve_deferred()

    def _set_jsonapi_relationship(
        self,
        relationship_payload: dict,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
        include_tree: dict,
        included: dict[tuple[str, str], tuple[tuple[str, str], dict]] | None,
        deferred: list[Callable[[], None]] | None,
    ) -> None:
        serializer = ResourceSerializer(self, context)
        serializer.included = included if included is not None else {}
        if deferred is not None:
            serializer.deferred = deferred
        serializer.set_relationship(relationship_payload, definition, value, ensure_resource_context(context), include_tree)
        if deferred is None:
            serializer.resolve_deferred()

    @staticmethod
    def _resolve_jsonapi_deferred(deferred: list[Callable[[], None]]) -> None:
        ResourceSerializer.resolve_deferred_callbacks(deferred)

    def _relationship_linkage(self, definition: ResourceRelationshipDefinition, value: Any, context: dict):
        return ResourceSerializer(self, context).relationship_linkage(definition, value, ensure_resource_context(context))

    def _resource_identifier_payload(self, resource: str, value: Any, context: dict) -> dict | None:
        return ResourceSerializer(self, context).resource_identifier_payload(resource, value, ensure_resource_context(context))

    def _resolve_related_resource_type(self, definition: ResourceRelationshipDefinition, value: Any, context: dict) -> str:
        return ResourceSerializer(self, context).related_resource_type(definition, value, ensure_resource_context(context))

    @staticmethod
    def _resource_self_link(resource: str, resource_id: str, context: dict) -> str:
        return ResourceSerializer.resource_self_link(resource, resource_id, context)

    @staticmethod
    def _resource_identifier(resource: str, instance: Any, context: dict, resource_object: Resource | None = None) -> str | None:
        return ResourceSerializer.resource_identifier(resource, instance, context, resource_object)

    @staticmethod
    def _relationship_values(value: Any, *, many: bool) -> list[Any]:
        return ResourceSerializer.relationship_values(value, many=many)

    @staticmethod
    def _is_jsonapi_identifier(value: Any) -> bool:
        return ResourceSerializer.is_jsonapi_identifier(value)

    def apply_named_sort(self, resource: str, queryset, sort: str, context: dict | None = None):
        normalized = str(sort or "").strip()
        resolved_context = dict(context or {})
        descending = normalized.startswith("-")
        sort_name = normalized[1:] if descending else normalized
        for definition in self.get_effective_sorts(resource, resolved_context):
            if definition.sort != sort_name:
                continue
            handler = definition.handler
            sort_context = {**resolved_context, "sort": sort_name, "descending": descending}
            if callable(handler):
                return handler(queryset, sort_context)
            if isinstance(handler, (list, tuple)):
                fields = self._sort_order_fields(handler, descending)
                return queryset.order_by(*fields)
            if isinstance(handler, str) and handler.strip():
                field = handler.strip()
                if descending and not field.startswith("-"):
                    field = f"-{field}"
                return queryset.order_by(field)
        return queryset

    def has_named_sort(self, resource: str, sort: str, context: dict | None = None) -> bool:
        normalized = str(sort or "").strip()
        resolved_context = dict(context or {})
        for definition in self.get_effective_sorts(resource, resolved_context):
            if definition.sort != normalized:
                continue
            handler = definition.handler
            if callable(handler):
                return True
            if isinstance(handler, (list, tuple)) and handler:
                return True
            if isinstance(handler, str) and handler.strip():
                return True
        return False

    def apply_resource_filters(self, resource: str, queryset, filters: dict[str, Any], context: dict | None = None):
        output = queryset
        resolved_context = dict(context or {})
        available = {
            definition.filter: definition
            for definition in self.get_effective_filters(resource, resolved_context)
            if self._is_filter_visible(definition, resolved_context)
        }
        for name, value in (filters or {}).items():
            normalized = str(name or "").strip()
            if normalized == "q":
                output = self._apply_default_fulltext_filter(resource, output, value, resolved_context)
                continue
            negate = normalized.startswith("-")
            filter_name = normalized[1:] if negate else normalized
            definition = available.get(filter_name)
            if definition is None:
                raise BadJsonApiRequest(f"Invalid filter: {filter_name}", parameter=f"filter[{filter_name}]")
            filter_context = {**resolved_context, "filter": filter_name, "negate": negate}
            output = definition.handler(output, value, filter_context)
        return output

    def _search_resource_index(
        self,
        resource_object: DatabaseResource,
        definition: ResourceEndpointDefinition,
        queryset,
        context: dict,
        *,
        filters: dict[str, Any],
        sort: str,
        pagination: dict[str, int] | None,
    ) -> ResourceSearchResults | None:
        criteria = ResourceSearchCriteria(
            user=context.get("user"),
            filters=dict(filters or {}),
            limit=pagination.get("limit") if pagination else None,
            offset=pagination.get("offset") if pagination else 0,
            sort=sort,
            default_sort=not bool((context.get("query") or {}).get("sort")),
            query=str((filters or {}).get("q") or ""),
            resource=definition.resource,
        )
        context_with_search = {**context, "queryset": queryset, "search_criteria": criteria}

        search = getattr(resource_object, "search", None)
        if callable(search):
            result = search(criteria, context_with_search)
            normalized = self._normalize_search_result(result)
            if normalized is not None:
                return normalized

        manager = self._runtime_search_manager()
        if manager is not None:
            model = getattr(resource_object, "model", None)
            if manager.searchable(model) or manager.filters_for(model, resource=definition.resource):
                return manager.query(model, queryset, criteria, context_with_search)

        try:
            from apps.core.extensions.runtime_access import get_runtime_search_service

            search_service = get_runtime_search_service()
        except Exception:
            search_service = None
        if search_service is not None:
            searchers = getattr(search_service, "get_searchers", lambda target: [])(definition.resource)
            for searcher in searchers:
                result = self._invoke_resource_searcher(searcher, queryset, criteria, context_with_search)
                normalized = self._normalize_search_result(result)
                if normalized is not None:
                    return normalized
        return None

    def _runtime_search_manager(self):
        try:
            from apps.core.extensions.runtime_access import get_runtime_search_service

            service = get_runtime_search_service()
            manager = getattr(service, "manager", None)
            if manager is not None:
                self._sync_resource_filters_to_search_manager(manager)
                return manager
        except Exception:
            pass
        manager = get_resource_search_manager()
        self._sync_resource_filters_to_search_manager(manager)
        return manager

    def _sync_resource_filters_to_search_manager(self, manager) -> None:
        for resource in set(self._definitions.keys()) | set(self._resource_objects.keys()) | set(self._filters.keys()):
            for definition in self.get_effective_filters(resource):
                self._register_search_filter(definition, manager=manager)

    def _register_search_filter(self, definition: ResourceFilterDefinition, *, manager=None) -> None:
        target_manager = manager or self._runtime_search_manager()
        if target_manager is None:
            return
        target_manager.register_filter(
            definition.resource,
            ResourceSearchFilter(
                name=definition.filter,
                handler=definition.handler,
                visible=definition.visible,
                module_id=definition.module_id,
            ),
        )

    @staticmethod
    def _normalize_search_result(result: Any) -> ResourceSearchResults | None:
        if result is None:
            return None
        if isinstance(result, ResourceSearchResults):
            return result
        if isinstance(result, tuple) and len(result) == 2:
            return ResourceSearchResults(results=result[0], total=result[1], sort_applied=True, pagination_applied=True)
        if isinstance(result, dict) and "results" in result:
            return ResourceSearchResults(
                results=result.get("results"),
                total=result.get("total"),
                sort_applied=bool(result.get("sort_applied", False)),
                pagination_applied=bool(result.get("pagination_applied", False)),
            )
        return ResourceSearchResults(results=result, total=None, sort_applied=False, pagination_applied=False)

    @staticmethod
    def _invoke_resource_searcher(searcher: Any, queryset, criteria: ResourceSearchCriteria, context: dict):
        if hasattr(searcher, "search") and callable(searcher.search):
            return searcher.search(queryset, criteria, context)
        if callable(searcher):
            return searcher(queryset, criteria, context)
        return None

    @staticmethod
    def _sort_order_fields(fields: tuple | list, descending: bool) -> list[str]:
        output = []
        for field in fields:
            normalized = str(field or "").strip()
            if not normalized:
                continue
            if descending and not normalized.startswith("-"):
                normalized = f"-{normalized}"
            output.append(normalized)
        return output

    def _apply_default_fulltext_filter(self, resource: str, queryset, value: Any, context: dict):
        query = str(value or "").strip()
        if not query:
            return queryset
        resource_object = self.get_resource_object(resource)
        fields = [
            definition.field
            for definition in self.get_effective_fields(resource, context)
            if str(getattr(definition, "value_type", "") or "").strip().lower() in {"", "string"}
        ]
        if not fields:
            return queryset
        try:
            from django.db.models import Q
        except Exception:
            return queryset
        condition = Q()
        for field in fields:
            condition |= Q(**{f"{field}__icontains": query})
        if not condition:
            return queryset
        return queryset.filter(condition)

    def _merge_preload_definition(
        self,
        definition,
        context: dict,
        select_related: list[str],
        prefetch_related: list[Any],
        seen_select: set[str],
        seen_prefetch: set[str],
        prefetch_where: list[tuple[str, Callable[[Any, dict], Any]]] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> None:
        for item in getattr(definition, "select_related", ()) or ():
            if item and item not in seen_select:
                seen_select.add(item)
                select_related.append(item)

        for item in getattr(definition, "prefetch_related", ()) or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

        preload_resolver = getattr(definition, "preload_resolver", None)
        if preload_resolver is not None:
            extra_select, extra_prefetch = preload_resolver(context)
            for item in extra_select or ():
                if item and item not in seen_select:
                    seen_select.add(item)
                    select_related.append(item)

            for item in extra_prefetch or ():
                prefetch_key = self._prefetch_key(item)
                if prefetch_key and prefetch_key not in seen_prefetch:
                    seen_prefetch.add(prefetch_key)
                    prefetch_related.append(item)

        for item in getattr(definition, "eager_load", ()) or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

        include_set = set(str(item or "").strip() for item in include or () if str(item or "").strip())
        when_included_rules = (
            getattr(definition, "eager_load_when_included_rules", ())
            or getattr(definition, "eager_load_when_included", ())
            or ()
        )
        for included, items in when_included_rules:
            if str(included or "").strip() not in include_set:
                continue
            for item in items or ():
                prefetch_key = self._prefetch_key(item)
                if prefetch_key and prefetch_key not in seen_prefetch:
                    seen_prefetch.add(prefetch_key)
                    prefetch_related.append(item)

        where_rules = (
            getattr(definition, "eager_load_where_rules", ())
            or getattr(definition, "eager_load_where", ())
            or ()
        )
        for relation, callback in where_rules:
            normalized = str(relation or "").strip()
            if not normalized or not callable(callback):
                continue
            if prefetch_where is not None:
                prefetch_where.append((normalized, callback))
            if normalized not in seen_prefetch:
                seen_prefetch.add(normalized)
                prefetch_related.append(normalized)

    @staticmethod
    def _prefetch_key(item: Any) -> str:
        if isinstance(item, str):
            return item
        lookup = getattr(item, "prefetch_to", None) or getattr(item, "lookup", None)
        if lookup:
            return str(lookup)
        return repr(item)

    @staticmethod
    def _is_applicable(condition, context: dict) -> bool:
        if condition is None:
            return True
        return bool(condition(context))

    @staticmethod
    def _is_field_visible(definition, instance: Any, context: dict) -> bool:
        visible = getattr(definition, "visible", True)
        if callable(visible):
            return bool(visible(instance, context))
        return bool(visible)

    @staticmethod
    def _is_relationship_visible(definition, instance: Any, context: dict) -> bool:
        visible = getattr(definition, "visible", True)
        if callable(visible):
            return bool(visible(instance, context))
        return bool(visible)

    @staticmethod
    def _is_relationship_includable(definition, context: dict) -> bool:
        includable = getattr(definition, "includable", True)
        if callable(includable):
            return bool(includable(context))
        return bool(includable)

    @staticmethod
    def _is_filter_visible(definition, context: dict) -> bool:
        visible = getattr(definition, "visible", True)
        if callable(visible):
            return bool(visible(context))
        return bool(visible)

    @staticmethod
    def _is_field_writable(definition, instance: Any, context: dict) -> bool:
        field_object = getattr(definition, "field_object", None)
        is_writable = getattr(field_object, "is_writable", None)
        if callable(is_writable):
            return bool(is_writable(ensure_resource_context(context).with_model(instance)))
        writable = getattr(definition, "writable", False)
        if callable(writable):
            return bool(writable(instance, context))
        return bool(writable)

    @staticmethod
    def _set_resource_value(definition, instance: Any, value: Any, context: dict) -> None:
        field_object = getattr(definition, "field_object", None)
        set_value = getattr(field_object, "set_value", None)
        if callable(set_value):
            set_value(instance, value, ensure_resource_context(context).with_model(instance))
            return
        if definition.setter is not None:
            definition.setter(instance, value, context)
        else:
            setattr(instance, getattr(definition, "field", "") or getattr(definition, "relationship", ""), value)

    def _resource_fields(self, resource: str) -> list[ResourceField]:
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return []
        return [
            definition
            for definition in self._resolve_resource_items(resource_object, "fields", list(resource_object.resolve_fields()))
            if isinstance(definition, ResourceField) and not isinstance(definition, ResourceRelationship)
        ]

    def _resource_relationships(self, resource: str) -> list[ResourceRelationship]:
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return []
        return [
            definition
            for definition in self._resolve_resource_items(resource_object, "fields", list(resource_object.resolve_fields()))
            if isinstance(definition, ResourceRelationship)
        ]

    def _resource_endpoints(self, resource: str) -> list[ResourceEndpoint]:
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return []
        return self._resolve_resource_items(resource_object, "endpoints", list(resource_object.resolve_endpoints()))

    def _resource_sorts(self, resource: str) -> list[ResourceSort]:
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return []
        return self._resolve_resource_items(resource_object, "sorts", list(resource_object.resolve_sorts()))

    def _resource_filters(self, resource: str) -> list[ResourceFilter]:
        resource_object = self.resolve_resource(resource)
        if resource_object is None:
            return []
        filters = getattr(resource_object, "filters", None)
        if not callable(filters):
            return []
        return [
            definition
            for definition in self._resolve_resource_items(resource_object, "filters", list(resource_object.resolve_filters()))
            if isinstance(definition, ResourceFilter)
        ]

    def _resolve_resource_items(self, resource_object: Resource, kind: str, items: list[Any]) -> list[Any]:
        output = list(items or [])
        modifiers = getattr(self, "_resource_modifiers", {})
        for cls in reversed(type(resource_object).mro()):
            for modifier in modifiers.get(cls, {}).get(kind, ()):
                class_modifiers = {
                    "endpoints": getattr(resource_object, "_endpoint_modifiers", {}),
                    "fields": getattr(resource_object, "_field_modifiers", {}),
                    "sorts": getattr(resource_object, "_sort_modifiers", {}),
                    "filters": getattr(resource_object, "_filter_modifiers", {}),
                }.get(kind, {})
                if modifier in class_modifiers.get(cls, ()):
                    continue
                output = modifier(output, resource_object)
        return output

    @staticmethod
    def _field_to_definition(resource: str, field: ResourceField) -> ResourceFieldDefinition:
        return ResourceFieldDefinition(
            resource=resource,
            field=field.name,
            module_id=field.module_id,
            resolver=lambda instance, context, field_object=field: field_object.resolve(instance, context),
            description=field.description,
            select_related=field.select_related,
            prefetch_related=field.prefetch_related,
            preload_resolver=field.preload_resolver,
            visible=field.visible,
            writable=field.writable,
            required_on_create=field.required_on_create,
            required_on_update=field.required_on_update,
            nullable=field.nullable,
            value_type=field.value_type,
            validation_rules=field.validation_rules,
            has_validation_rules=field.has_validation_rules,
            setter=field.setter,
            validator=field.validator,
            field_object=field,
        )

    @staticmethod
    def _relationship_to_definition(resource: str, relationship: ResourceRelationship) -> ResourceRelationshipDefinition:
        return ResourceRelationshipDefinition(
            resource=resource,
            relationship=relationship.name,
            module_id=relationship.module_id,
            resolver=lambda instance, context, relationship_object=relationship: relationship_object.resolve(instance, context),
            description=relationship.description,
            select_related=relationship.select_related,
            prefetch_related=relationship.prefetch_related,
            preload_resolver=relationship.preload_resolver,
            visible=relationship.visible,
            includable=relationship.includable,
            resource_type=relationship.resource_type,
            many=relationship.many,
            inverse=relationship.inverse,
            setter=relationship.relationship_setter or relationship.setter,
            writable=relationship.writable,
            linkage=relationship.linkage,
            required_on_create=relationship.required_on_create,
            required_on_update=relationship.required_on_update,
            nullable=relationship.nullable,
            value_type=relationship.value_type,
            validation_rules=relationship.validation_rules,
            has_validation_rules=relationship.has_validation_rules,
            validator=relationship.validator,
            field_object=relationship,
        )

    @staticmethod
    def _endpoint_to_definition(resource: str, endpoint: ResourceEndpoint) -> ResourceEndpointDefinition:
        return ResourceEndpointDefinition(
            resource=resource,
            endpoint=endpoint.name,
            module_id=endpoint.module_id,
            description=endpoint.description,
            operation="add",
            handler=endpoint.handler,
            methods=endpoint.methods,
            path=endpoint.path,
            absolute_path=endpoint.absolute_path,
            auth_required=endpoint.auth_required,
            permission=endpoint.permission,
            default_include=endpoint.default_include,
            eager_load=endpoint.eager_load,
            eager_load_when_included_rules=endpoint.eager_load_when_included_rules,
            eager_load_where_rules=endpoint.eager_load_where_rules,
            default_sort=endpoint.default_sort,
            paginate=endpoint.paginate,
            pagination_default_limit=endpoint.pagination_default_limit,
            pagination_max_limit=endpoint.pagination_max_limit,
            kind=endpoint.kind,
            ability=endpoint.ability,
            forum_permission=endpoint.forum_permission,
            before_hook=endpoint.before_hook,
            after_hook=endpoint.after_hook,
            meta_resolver=endpoint.meta_resolver,
            links_resolver=endpoint.links_resolver,
            query_callback=endpoint.query_callback,
            action_callback=endpoint.action_callback,
            before_serialization_callback=endpoint.before_serialization_callback,
            response_callback=endpoint.response_callback,
        )

    @staticmethod
    def _sort_to_definition(resource: str, sort: ResourceSort) -> ResourceSortDefinition:
        return ResourceSortDefinition(
            resource=resource,
            sort=sort.name,
            module_id=sort.module_id,
            handler=sort.handler,
            description=sort.description,
        )

    @staticmethod
    def _filter_to_definition(resource: str, filter_object: ResourceFilter) -> ResourceFilterDefinition:
        return ResourceFilterDefinition(
            resource=resource,
            filter=filter_object.name,
            module_id=filter_object.module_id,
            handler=lambda queryset, value, context, target=filter_object: target.apply(queryset, value, context),
            description=filter_object.description,
            visible=filter_object.visible,
        )

    @staticmethod
    def _field_mutator_result(definition: ResourceFieldMutatorDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except AttributeError:
            return target
        if mutated is None:
            return target
        if ResourceRegistry._is_field_definition_like(mutated):
            return mutated
        raise TypeError("The field mutator must return a ResourceFieldDefinition-compatible object")

    @staticmethod
    def _relationship_mutator_result(definition: ResourceFieldMutatorDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except AttributeError:
            return target
        if mutated is None:
            return target
        if ResourceRegistry._is_relationship_definition_like(mutated):
            return mutated
        raise TypeError("The relationship mutator must return a ResourceRelationshipDefinition-compatible object")

    @staticmethod
    def _sort_mutator_result(definition: ResourceSortDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except AttributeError:
            return target
        if mutated is None:
            return target
        if ResourceRegistry._is_sort_definition_like(mutated):
            return mutated
        raise TypeError("The sort mutator must return a ResourceSortDefinition-compatible object")

    @staticmethod
    def _filter_mutator_result(definition: ResourceFilterDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except AttributeError:
            return target
        if mutated is None:
            return target
        if ResourceRegistry._is_filter_definition_like(mutated):
            return mutated
        raise TypeError("The filter mutator must return a ResourceFilterDefinition-compatible object")

    @staticmethod
    def _mutator_kind(definition: Any) -> str:
        return str(getattr(definition, "kind", "") or "").strip().lower()

    @staticmethod
    def _external_sort_mutator_result(definition: ResourceSortDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except (AttributeError, TypeError):
            return target
        if ResourceRegistry._is_sort_definition_like(mutated):
            return target
        return mutated if mutated is not None else target

    @staticmethod
    def _is_resource_definition_mutation(value: Any) -> bool:
        return (
            ResourceRegistry._is_field_definition_like(value)
            or ResourceRegistry._is_relationship_definition_like(value)
        )

    @staticmethod
    def _is_field_definition_like(value: Any) -> bool:
        return (
            isinstance(value, ResourceFieldDefinition)
            or (
                hasattr(value, "resource")
                and hasattr(value, "field")
                and hasattr(value, "resolver")
            )
        )

    @staticmethod
    def _is_relationship_definition_like(value: Any) -> bool:
        return (
            isinstance(value, ResourceRelationshipDefinition)
            or (
                hasattr(value, "resource")
                and hasattr(value, "relationship")
                and hasattr(value, "resolver")
            )
        )

    @staticmethod
    def _is_sort_definition_like(value: Any) -> bool:
        return (
            isinstance(value, ResourceSortDefinition)
            or (
                hasattr(value, "resource")
                and hasattr(value, "sort")
                and hasattr(value, "handler")
            )
        )

    @staticmethod
    def _is_filter_definition_like(value: Any) -> bool:
        return (
            isinstance(value, ResourceFilterDefinition)
            or (
                hasattr(value, "resource")
                and hasattr(value, "filter")
                and hasattr(value, "handler")
            )
        )

    @staticmethod
    def _item_name(item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return str(item.get("name") or item.get("field") or item.get("relationship") or item.get("sort") or item.get("endpoint") or item.get("code") or "")
        return str(getattr(item, "name", "") or getattr(item, "field", "") or getattr(item, "relationship", "") or getattr(item, "sort", "") or getattr(item, "endpoint", "") or getattr(item, "code", "") or item)

    def _insert_before(self, items: list[Any], anchor: str, value: Any) -> None:
        index = self._find_item_index(items, anchor)
        if str(anchor or "").strip() in {"0", "before_all"}:
            items.insert(0, value)
        elif index is None:
            return
        else:
            items.insert(index, value)

    def _insert_after(self, items: list[Any], anchor: str, value: Any) -> None:
        index = self._find_item_index(items, anchor)
        if index is None:
            return
        else:
            items.insert(index + 1, value)

    def _find_item_index(self, items: list[Any], anchor: str) -> int | None:
        normalized = str(anchor or "").strip()
        if not normalized:
            return None
        for index, item in enumerate(items):
            if self._item_name(item) == normalized:
                return index
        return None

    def _endpoint_definition_matches(self, definition: ResourceEndpointDefinition, endpoint: str) -> bool:
        normalized = self._normalize_endpoint_path(endpoint)
        return normalized in {
            self._normalize_endpoint_path(definition.endpoint),
            self._normalize_endpoint_path(definition.path),
        }

    @staticmethod
    def _mutate_endpoint_definition(mutator_definition: ResourceEndpointDefinition, target: ResourceEndpointDefinition):
        if mutator_definition.mutator is None:
            return target
        mutated = mutator_definition.mutator(target)
        if mutated is None:
            return target
        if isinstance(mutated, ResourceEndpointDefinition):
            return mutated
        if ResourceRegistry._is_endpoint_definition_like(mutated):
            return ResourceRegistry._normalize_endpoint_definition(mutated)
        raise TypeError("The endpoint mutator must return a ResourceEndpointDefinition")

    @staticmethod
    def _is_endpoint_definition_like(value: Any) -> bool:
        return (
            hasattr(value, "resource")
            and hasattr(value, "endpoint")
            and (
                hasattr(value, "handler")
                or hasattr(value, "mutator")
                or hasattr(value, "kind")
            )
        )

    @staticmethod
    def _normalize_endpoint_definition(value: Any) -> ResourceEndpointDefinition:
        return ResourceEndpointDefinition(
            resource=getattr(value, "resource", ""),
            endpoint=getattr(value, "endpoint", ""),
            module_id=getattr(value, "module_id", ""),
            mutator=getattr(value, "mutator", None),
            description=getattr(value, "description", ""),
            operation=getattr(value, "operation", "mutate"),
            anchor=getattr(value, "anchor", ""),
            condition=getattr(value, "condition", None),
            handler=getattr(value, "handler", None),
            methods=getattr(value, "methods", ("GET",)),
            path=getattr(value, "path", ""),
            absolute_path=getattr(value, "absolute_path", False),
            auth_required=getattr(value, "auth_required", False),
            permission=getattr(value, "permission", ""),
            default_include=getattr(value, "default_include", ()),
            eager_load=getattr(value, "eager_load", ()),
            eager_load_when_included_rules=getattr(value, "eager_load_when_included_rules", ()),
            eager_load_where_rules=getattr(value, "eager_load_where_rules", ()),
            default_sort=getattr(value, "default_sort", ""),
            paginate=getattr(value, "paginate", False),
            pagination_default_limit=getattr(value, "pagination_default_limit", 20),
            pagination_max_limit=getattr(value, "pagination_max_limit", 50),
            kind=getattr(value, "kind", ""),
            ability=getattr(value, "ability", None),
            forum_permission=getattr(value, "forum_permission", ""),
            before_hook=getattr(value, "before_hook", None),
            after_hook=getattr(value, "after_hook", None),
            meta_resolver=getattr(value, "meta_resolver", None),
            links_resolver=getattr(value, "links_resolver", None),
            query_callback=getattr(value, "query_callback", None),
            action_callback=getattr(value, "action_callback", None),
            before_serialization_callback=getattr(value, "before_serialization_callback", None),
            response_callback=getattr(value, "response_callback", None),
        )

    @staticmethod
    def _endpoint_operation(definition: ResourceEndpointDefinition) -> str:
        operation = str(definition.operation or "mutate").strip().lower()
        if operation == "mutate" and definition.handler is not None and definition.mutator is None:
            return "add"
        return operation

    def _endpoint_registration_key(self, definition: ResourceEndpointDefinition) -> tuple[str, str, str]:
        return (
            str(definition.resource or "").strip(),
            self._normalize_endpoint_path(definition.path or definition.endpoint),
            ",".join(sorted(self._normalize_endpoint_methods(definition.methods))),
        )

    @staticmethod
    def _normalize_endpoint_path(value: str) -> str:
        return str(value or "").strip().strip("/")

    @staticmethod
    def _normalize_endpoint_methods(methods: Tuple[str, ...] | list[str] | str | None) -> set[str]:
        if methods is None:
            return {"GET"}
        if isinstance(methods, str):
            iterable = (methods,)
        else:
            iterable = methods
        normalized = {
            str(method or "").strip().upper()
            for method in iterable
            if str(method or "").strip()
        }
        return normalized or {"GET"}


_resource_registry: ResourceRegistry | None = None


def get_resource_registry() -> ResourceRegistry:
    from apps.core.extensions.bootstrap_state import is_extension_host_bootstrapped

    global _resource_registry
    if is_extension_host_bootstrapped():
        try:
            from apps.core.extensions.bootstrap import get_extension_host

            host = get_extension_host()
            if host is not None:
                return host.resources
        except Exception:
            pass
    if _resource_registry is None:
        _resource_registry = ResourceRegistry()
    return _resource_registry


class _DefinitionBackedResource(Resource):
    def __init__(self, definition: ResourceDefinition):
        self.definition = definition
        self.module_id = definition.module_id
        self.description = definition.description

    def type(self) -> str:
        return self.definition.resource

    def serialize(self, instance: Any, context: dict) -> dict[str, Any]:
        return self.definition.resolver(instance, context) or {}
