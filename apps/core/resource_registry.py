from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Tuple

from django.db import OperationalError, ProgrammingError

from apps.core.models import ExtensionInstallation
from apps.core.resource_definitions import (
    ResourceAnnotateResolver,
    ResourceBaseFieldResolver,
    ResourceDefinition,
    ResourceEndpointDefinition,
    ResourceEndpointHandler,
    ResourceFieldDefinition,
    ResourceFieldMutatorDefinition,
    ResourceFieldResolver,
    ResourceFilterDefinition,
    ResourcePreloadPlan,
    ResourcePreloadResolver,
    ResourceRelationshipDefinition,
    ResourceRelationshipResolver,
    ResourceSortDefinition,
)
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
from apps.core.resource_conversion import (
    endpoint_to_definition,
    field_to_definition,
    filter_to_definition,
    relationship_to_definition,
    sort_to_definition,
)



_JSONAPI_SKIP = object()
_NOT_CACHED = object()
logger = logging.getLogger(__name__)

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
        self._enabled_module_ids_cache: set[str] | None = _NOT_CACHED

        from apps.core.registry.preload_planner import PreloadPlanner
        from apps.core.registry.search_bridge import SearchBridge
        from apps.core.registry.definition_mutator import DefinitionMutator
        from apps.core.registry.endpoint_context import EndpointContextResolver
        from apps.core.registry.jsonapi_serializer import JsonApiSerializer
        from apps.core.registry.resource_validator import ResourceValidator

        self._preload_planner: PreloadPlanner = PreloadPlanner(self)
        self._search_bridge: SearchBridge = SearchBridge(self)
        self._definition_mutator: DefinitionMutator = DefinitionMutator(self)
        self._endpoint_context: EndpointContextResolver = EndpointContextResolver(self)
        self._jsonapi_serializer: JsonApiSerializer = JsonApiSerializer(self)
        self._resource_validator: ResourceValidator = ResourceValidator(self)

    def _get_enabled_module_ids(self) -> set[str] | None:
        if self._enabled_module_ids_cache is not _NOT_CACHED:
            return self._enabled_module_ids_cache
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
        result = enabled_ids - disabled_ids
        self._enabled_module_ids_cache = result
        return result

    def _invalidate_enabled_module_ids_cache(self) -> None:
        self._enabled_module_ids_cache = _NOT_CACHED

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
            elif operation == "before_all":
                added = self._field_mutator_result(definition, None)
                if added is not None:
                    output.insert(0, added)
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
            elif operation == "before_all":
                added = self._relationship_mutator_result(definition, None)
                if added is not None:
                    output.insert(0, added)
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
        return self._definition_mutator.apply_endpoint_mutators(resource, endpoint, endpoint_object, context)

    def apply_endpoint_definitions(self, resource: str, endpoints: List[Any], context: dict | None = None) -> List[Any]:
        return self._definition_mutator.apply_endpoint_definitions(resource, endpoints, context)

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
        return self._definition_mutator.apply_field_definitions(resource, fields, context)

    def apply_sort_definitions(self, resource: str, sorts: List[Any], context: dict | None = None) -> List[Any]:
        return self._definition_mutator.apply_sort_definitions(resource, sorts, context)

    def build_preload_plan(
        self,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> ResourcePreloadPlan:
        return self._preload_planner.build_preload_plan(resource, context, only=only, include=include)

    def apply_preload_plan(
        self,
        queryset,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ):
        return self._preload_planner.apply_preload_plan(queryset, resource, context, only=only, include=include)

    def build_endpoint_preload_plan(
        self,
        resource: str,
        endpoint: str,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        return self._preload_planner.build_endpoint_preload_plan(resource, endpoint, context)

    def build_endpoint_definition_preload_plan(
        self,
        definition: ResourceEndpointDefinition,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        return self._preload_planner.build_endpoint_definition_preload_plan(definition, context)

    def apply_resource_payload(
        self,
        resource: str,
        instance: Any,
        payload: dict,
        context: dict | None = None,
        *,
        creating: bool = False,
    ) -> Any:
        return self._endpoint_context.apply_resource_payload(resource, instance, payload, context, creating=creating)

    def _run_extension_validators(self, resource: str, instance: Any, payload: dict, context: dict) -> None:
        self._endpoint_context._run_extension_validators(resource, instance, payload, context)

    def dispatch_resource_endpoint(self, definition: ResourceEndpointDefinition, context: dict):
        return self._endpoint_context.dispatch_resource_endpoint(definition, context)

    @staticmethod
    def _extract_resource_payload(context: dict) -> dict:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._extract_resource_payload(context)

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
        self._resource_validator._run_validation_factory(resource_object, context, data)

    def _build_validation_payload(self, resource_object: Resource, context: dict, data: dict) -> dict:
        return self._resource_validator._build_validation_payload(resource_object, context, data)

    def _collect_validation_rules(self, resource_object: Resource, context: dict) -> dict:
        return self._resource_validator._collect_validation_rules(resource_object, context)

    def _collect_validation_state(self, resource_object: Resource, context: dict) -> dict:
        return self._resource_validator._collect_validation_state(resource_object, context)

    @staticmethod
    def _merge_definition_validation_state(
        rules: dict,
        messages: dict,
        attributes: dict,
        definition: Any,
        name: str,
        context: dict,
    ) -> None:
        from apps.core.registry.resource_validator import ResourceValidator
        ResourceValidator._merge_definition_validation_state(rules, messages, attributes, definition, name, context)

    @staticmethod
    def _invoke_validation_factory_object(factory: Any, validation_payload: dict, data: dict, context: dict):
        from apps.core.registry.resource_validator import ResourceValidator
        return ResourceValidator._invoke_validation_factory_object(factory, validation_payload, data, context)

    @staticmethod
    def _validator_errors(section: str, validator: Any) -> list[dict]:
        from apps.core.registry.resource_validator import ResourceValidator
        return ResourceValidator._validator_errors(section, validator)

    def _collect_payload_validation_errors(self, resource_object: Resource, context: dict, data: dict) -> list[dict]:
        return self._resource_validator._collect_payload_validation_errors(resource_object, context, data)

    @staticmethod
    def _validation_error_to_document(exc: JsonApiValidationError, definition: Any, messages: dict, attributes: dict) -> dict:
        from apps.core.registry.resource_validator import ResourceValidator
        return ResourceValidator._validation_error_to_document(exc, definition, messages, attributes)

    @staticmethod
    def _normalize_validation_factory_errors(result: Any) -> list[dict]:
        from apps.core.registry.resource_validator import ResourceValidator
        return ResourceValidator._normalize_validation_factory_errors(result)

    @staticmethod
    def _call_endpoint_before(definition: ResourceEndpointDefinition, context: dict) -> None:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        EndpointContextResolver._call_endpoint_before(definition, context)

    @staticmethod
    def _call_endpoint_after(definition: ResourceEndpointDefinition, context: dict, value: Any):
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._call_endpoint_after(definition, context, value)

    @staticmethod
    def _resolve_endpoint_meta(definition: ResourceEndpointDefinition, context: dict, value: Any) -> dict:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._resolve_endpoint_meta(definition, context, value)

    @staticmethod
    def _resolve_endpoint_links(definition: ResourceEndpointDefinition, context: dict, value: Any) -> dict:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._resolve_endpoint_links(definition, context, value)

    def _merge_endpoint_document_meta_links(
        self,
        document: dict,
        definition: ResourceEndpointDefinition,
        context: dict,
        value: Any,
    ) -> None:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        EndpointContextResolver._merge_endpoint_document_meta_links(document, definition, context, value)

    @staticmethod
    @staticmethod
    def _extract_relationship_payload(context: dict) -> dict:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._extract_relationship_payload(context)

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
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._resolve_endpoint_include(definition, context)

    @staticmethod
    def _resolve_endpoint_sort(definition: ResourceEndpointDefinition, context: dict) -> str:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._resolve_endpoint_sort(definition, context)

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
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._resolve_endpoint_pagination(definition, context)

    @staticmethod
    def _parse_non_negative_int(value: Any, name: str) -> int:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._parse_non_negative_int(value, name)

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
        from apps.core.registry.resource_validator import ResourceValidator
        ResourceValidator._validate_resource_value(definition, value, context)

    @staticmethod
    def _validate_resource_rule(name: str, rule: Any, value: Any, context: dict, definition: Any = None) -> None:
        from apps.core.registry.resource_validator import ResourceValidator
        ResourceValidator._validate_resource_rule(name, rule, value, context, definition)

    @staticmethod
    def _validate_named_resource_rule(name: str, rule_name: str, value: Any, argument: Any = None, definition: Any = None) -> None:
        from apps.core.registry.resource_validator import ResourceValidator
        ResourceValidator._validate_named_resource_rule(name, rule_name, value, argument, definition)

    @staticmethod
    def _validation_pointer(definition: Any) -> str:
        from apps.core.registry.resource_validator import ResourceValidator
        return ResourceValidator._validation_pointer(definition)

    def serialize(
        self,
        resource: str,
        instance: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> dict:
        return self._jsonapi_serializer.serialize(resource, instance, context, only=only, include=include)

    def _serialize_plain_relationship(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
    ):
        return self._jsonapi_serializer._serialize_plain_relationship(definition, value, context)

    def _serialize_plain_related_item(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
    ):
        return self._jsonapi_serializer._serialize_plain_related_item(definition, value, context)

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
        return self._jsonapi_serializer.serialize_jsonapi_document(resource, data, context, only=only, include=include, many=many)

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
        return self._jsonapi_serializer.serialize_jsonapi_resource(resource, instance, context, only=only,
                                                                     include_tree=include_tree, included=included, deferred=deferred)

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
        return self._jsonapi_serializer._serialize_jsonapi_resource_internal(resource, instance, context, only=only,
                                                                               include_tree=include_tree, included=included, deferred=deferred)

    def apply_payload_field_mutators(self, resource: str, payload: dict, context: dict | None = None) -> dict:
        return self._jsonapi_serializer.apply_payload_field_mutators(resource, payload, context)

    @staticmethod
    def _build_include_tree(include: Tuple[str, ...] | List[str]) -> dict[str, dict]:
        from apps.core.registry.preload_planner import PreloadPlanner
        return PreloadPlanner._build_include_tree(include)

    @staticmethod
    def _flatten_include_tree(tree: dict[str, dict], prefix: str = "") -> list[str]:
        from apps.core.registry.preload_planner import PreloadPlanner
        return PreloadPlanner._flatten_include_tree(tree, prefix)

    @staticmethod
    def _prefix_prefetch(prefix: str, item: Any) -> Any:
        from apps.core.registry.preload_planner import PreloadPlanner
        return PreloadPlanner._prefix_prefetch(prefix, item)

    def _add_jsonapi_included(
        self,
        definition: ResourceRelationshipDefinition,
        value: Any,
        context: dict,
        include_tree: dict,
        included: dict[tuple[str, str], tuple[tuple[str, str], dict]] | None,
        deferred: list[Callable[[], None]] | None = None,
    ) -> None:
        return self._jsonapi_serializer._add_jsonapi_included(definition, value, context, include_tree, included, deferred)

    def _set_jsonapi_value(
        self,
        payload: dict,
        key: str,
        value: Any,
        deferred: list[Callable[[], None]] | None,
    ) -> None:
        return self._jsonapi_serializer._set_jsonapi_value(payload, key, value, deferred)

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
        return self._jsonapi_serializer._set_jsonapi_relationship(relationship_payload, definition, value, context, include_tree, included, deferred)

    @staticmethod
    def _resolve_jsonapi_deferred(deferred: list[Callable[[], None]]) -> None:
        from apps.core.registry.jsonapi_serializer import JsonApiSerializer
        JsonApiSerializer._resolve_jsonapi_deferred(deferred)

    def _relationship_linkage(self, definition: ResourceRelationshipDefinition, value: Any, context: dict):
        return self._jsonapi_serializer._relationship_linkage(definition, value, context)

    def _resource_identifier_payload(self, resource: str, value: Any, context: dict) -> dict | None:
        return self._jsonapi_serializer._resource_identifier_payload(resource, value, context)

    def _resolve_related_resource_type(self, definition: ResourceRelationshipDefinition, value: Any, context: dict) -> str:
        return self._jsonapi_serializer._resolve_related_resource_type(definition, value, context)

    @staticmethod
    def _resource_self_link(resource: str, resource_id: str, context: dict) -> str:
        from apps.core.registry.jsonapi_serializer import JsonApiSerializer
        return JsonApiSerializer._resource_self_link(resource, resource_id, context)

    def _resource_identifier(self, resource: str, instance: Any, context: dict, resource_object: Resource | None = None) -> str | None:
        return self._jsonapi_serializer._resource_identifier(resource, instance, context, resource_object)

    @staticmethod
    def _relationship_values(value: Any, *, many: bool) -> list[Any]:
        from apps.core.registry.jsonapi_serializer import JsonApiSerializer
        return JsonApiSerializer._relationship_values(value, many=many)

    @staticmethod
    def _is_jsonapi_identifier(value: Any) -> bool:
        from apps.core.registry.jsonapi_serializer import JsonApiSerializer
        return JsonApiSerializer._is_jsonapi_identifier(value)

    def apply_named_sort(self, resource: str, queryset, sort: str, context: dict | None = None):
        return self._endpoint_context.apply_named_sort(resource, queryset, sort, context)

    def has_named_sort(self, resource: str, sort: str, context: dict | None = None) -> bool:
        return self._endpoint_context.has_named_sort(resource, sort, context)

    def apply_resource_filters(self, resource: str, queryset, filters: dict[str, Any], context: dict | None = None):
        return self._endpoint_context.apply_resource_filters(resource, queryset, filters, context)

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
        return self._search_bridge.search_resource_index(
            resource_object, definition, queryset, context,
            filters=filters, sort=sort, pagination=pagination,
        )

    def _runtime_search_manager(self):
        return self._search_bridge.runtime_search_manager()

    def _sync_resource_filters_to_search_manager(self, manager) -> None:
        self._search_bridge._sync_resource_filters_to_search_manager(manager)

    def _register_search_filter(self, definition: ResourceFilterDefinition, *, manager=None) -> None:
        self._search_bridge._register_search_filter(definition, manager=manager)

    @staticmethod
    def _normalize_search_result(result: Any) -> ResourceSearchResults | None:
        from apps.core.registry.search_bridge import SearchBridge
        return SearchBridge._normalize_search_result(result)

    @staticmethod
    def _invoke_resource_searcher(searcher: Any, queryset, criteria: ResourceSearchCriteria, context: dict):
        from apps.core.registry.search_bridge import SearchBridge
        return SearchBridge._invoke_resource_searcher(searcher, queryset, criteria, context)

    @staticmethod
    def _sort_order_fields(fields: tuple | list, descending: bool) -> list[str]:
        from apps.core.registry.endpoint_context import EndpointContextResolver
        return EndpointContextResolver._sort_order_fields(fields, descending)

    def _apply_default_fulltext_filter(self, resource: str, queryset, value: Any, context: dict):
        return self._search_bridge.apply_default_fulltext_filter(resource, queryset, value, context)

    def _merge_preload_definition(
        self,
        definition,
        context: dict,
        select_related: list[str],
        prefetch_related: list[Any],
        seen_select: set[str],
        seen_prefetch: set[str],
        prefetch_where: list[tuple[str, Callable[[Any, dict], Any]]] | None = None,
        annotations: list[tuple[str, Any]] | None = None,
        seen_annotations: set[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> None:
        self._preload_planner._merge_preload_definition(
            definition, context,
            select_related, prefetch_related,
            seen_select, seen_prefetch,
            prefetch_where, annotations,
            seen_annotations, include,
        )

    @staticmethod
    def _prefetch_key(item: Any) -> str:
        from apps.core.registry.preload_planner import PreloadPlanner
        return PreloadPlanner._prefetch_key(item)

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
        return field_to_definition(resource, field)

    @staticmethod
    def _relationship_to_definition(resource: str, relationship: ResourceRelationship) -> ResourceRelationshipDefinition:
        return relationship_to_definition(resource, relationship)

    @staticmethod
    def _endpoint_to_definition(resource: str, endpoint: ResourceEndpoint) -> ResourceEndpointDefinition:
        return endpoint_to_definition(resource, endpoint)

    @staticmethod
    def _sort_to_definition(resource: str, sort: ResourceSort) -> ResourceSortDefinition:
        return sort_to_definition(resource, sort)

    @staticmethod
    def _filter_to_definition(resource: str, filter_object: ResourceFilter) -> ResourceFilterDefinition:
        return filter_to_definition(resource, filter_object)

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
    def _sort_definition_value(definition: ResourceSortDefinition):
        handler = getattr(definition, "handler", None)
        return definition if handler is None else handler

    @staticmethod
    def _external_sort_mutator_result(definition: ResourceSortDefinition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except (AttributeError, TypeError):
            try:
                mutated = definition.mutator(definition)
            except (AttributeError, TypeError):
                return target
        if ResourceRegistry._is_sort_definition_like(mutated):
            return ResourceRegistry._sort_definition_value(mutated)
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
            return str(item.get("name") or item.get("field") or item.get("relationship") or item.get("sort") or item.get("filter") or item.get("endpoint") or item.get("code") or "")
        return str(getattr(item, "name", "") or getattr(item, "field", "") or getattr(item, "relationship", "") or getattr(item, "sort", "") or getattr(item, "filter", "") or getattr(item, "endpoint", "") or getattr(item, "code", "") or item)

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


def reset_resource_registry_state() -> None:
    global _resource_registry

    if _resource_registry is not None:
        _resource_registry._invalidate_enabled_module_ids_cache()
    _resource_registry = None


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
            logger.warning("Failed to resolve extension-backed resource registry.", exc_info=True)
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
