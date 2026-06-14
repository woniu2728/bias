from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable

from apps.core.extensions.container import resolve_container_value, wrap_callback
from apps.core.extensions.extender_helpers import (
    normalize_names,
    normalize_resource_endpoints,
    normalize_resource_fields,
    normalize_resource_filters,
    normalize_resource_relationships,
    normalize_resource_sorts,
    resolve_definition_groups,
)
from apps.core.extensions.types import (
    ExtensionResourceEndpointDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceFieldMutatorDefinition,
    ExtensionResourceFilterDefinition,
    ExtensionResourceObjectDefinition,
    ExtensionResourceRelationshipDefinition,
    ExtensionResourceSortDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView

@dataclass(frozen=True)
class ResourceExtender:
    resources: tuple[Any, ...] = ()
    fields: tuple[ExtensionResourceFieldDefinition, ...] = ()
    field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    relationships: tuple[ExtensionResourceRelationshipDefinition, ...] = ()
    endpoints: tuple[ExtensionResourceEndpointDefinition, ...] = ()
    sorts: tuple[ExtensionResourceSortDefinition, ...] = ()
    filters: tuple[ExtensionResourceFilterDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.resources or self.fields or self.field_mutators or self.relationships or self.endpoints or self.sorts or self.filters):
            return

        extension_id = extension.extension_id

        def apply(resources, host: "ExtensionHost"):
            for definition in self.resources:
                resolved = resolve_container_value(definition, host)
                resources.register_resource(self._with_module_id(resolved, extension_id), extension_id=extension_id)
                self._register_api_resource_contract(host, resolved)
            for definition in self.fields:
                resources.register_field(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.field_mutators:
                resources.register_field_mutator(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.relationships:
                resources.register_relationship(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.endpoints:
                resources.register_endpoint(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.sorts:
                resources.register_sort(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.filters:
                resources.register_filter(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            return resources

        app.resolving("resources", apply)

    @staticmethod
    def _register_api_resource_contract(host, resource: Any) -> None:
        resource_class = resource if isinstance(resource, type) else type(resource)
        if resource_class is type(None):
            return

        def add_resource(app, resources):
            output = list(resources or [])
            if resource_class not in output:
                output.append(resource_class)
            return output

        host.extend("bias.api.resources", add_resource)

    @staticmethod
    def _with_module_id(definition, extension_id: str):
        if isinstance(definition, type):
            return definition
        if not hasattr(definition, "module_id"):
            return definition
        if getattr(definition, "module_id", ""):
            return definition
        return replace(definition, module_id=extension_id)

    @staticmethod
    def _resolve_definition_callbacks(definition, host):
        replacements = {}
        for attr in (
            "resolver",
            "handler",
            "mutator",
            "setter",
            "validator",
            "condition",
            "before_hook",
            "after_hook",
            "meta_resolver",
            "links_resolver",
            "query_callback",
            "action_callback",
            "before_serialization_callback",
            "response_callback",
        ):
            if hasattr(definition, attr):
                value = getattr(definition, attr)
                if isinstance(value, str) or isinstance(value, type):
                    replacements[attr] = wrap_callback(value, host)
        return replace(definition, **replacements) if replacements else definition


@dataclass(frozen=True, init=False)
class ApiResourceExtender:
    resource: Any = None
    _fields: tuple[Any, ...] = ()
    _field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    _relationships: tuple[Any, ...] = ()
    _endpoints: tuple[Any, ...] = ()
    _sorts: tuple[Any, ...] = ()
    _filters: tuple[Any, ...] = ()

    def __init__(
        self,
        resource: Any = None,
        fields: tuple[Any, ...] = (),
        field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = (),
        relationships: tuple[Any, ...] = (),
        endpoints: tuple[Any, ...] = (),
        sorts: tuple[Any, ...] = (),
        filters: tuple[Any, ...] = (),
    ) -> None:
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "_fields", tuple(fields or ()))
        object.__setattr__(self, "_field_mutators", tuple(field_mutators or ()))
        object.__setattr__(self, "_relationships", tuple(relationships or ()))
        object.__setattr__(self, "_endpoints", tuple(endpoints or ()))
        object.__setattr__(self, "_sorts", tuple(sorts or ()))
        object.__setattr__(self, "_filters", tuple(filters or ()))

    @property
    def resource_name(self) -> str:
        if self.resource is not None:
            if isinstance(self.resource, str):
                return self.resource.strip()
            if isinstance(self.resource, ExtensionResourceObjectDefinition):
                return self._resource_object_name(self.resource.resource)
            return getattr(self.resource, "resource", "") or self._resource_object_name(self.resource)
        for definitions in (
            self._fields,
            self._relationships,
            self._endpoints,
            self._sorts,
            self._field_mutators,
            self._filters,
        ):
            for definition in definitions:
                resource = getattr(definition, "resource", "")
                if resource:
                    return resource
        return ""

    @staticmethod
    def from_resource(resource) -> "ApiResourceExtender":
        return ApiResourceExtender(resource=resource)

    def fields(self, fields: Any = None, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        if fields is None:
            items = definitions
        else:
            items = (fields, *definitions)
        return self.fields_with(*items)

    def fields_with(self, *definitions: Any) -> "ApiResourceExtender":
        return ApiResourceExtender(
            resource=self.resource,
            fields=tuple([*self._fields, *definitions]),
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=self._sorts,
            filters=self._filters,
        )

    def fields_before(self, anchor: str, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        return self._field_mutators_with_operation("before", anchor, *definitions)

    def fields_after(self, anchor: str, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        return self._field_mutators_with_operation("after", anchor, *definitions)

    def fields_before_all(self, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        return self._field_mutators_with_operation("before_all", "", *definitions)

    def remove_fields(self, *fields: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=field,
                module_id="",
                operation="remove",
                mutator=lambda current: current,
                condition=condition,
                kind="field",
            )
            for field in fields
        )
        return self.field(*definitions)

    def remove_field(self, field: str, *, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        return self.remove_fields(field, condition=condition)

    def mutate_field(self, fields, mutator: Callable[[Any], Any]) -> "ApiResourceExtender":
        return self.field(fields, mutator)

    def field(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_field_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=tuple([*self._field_mutators, *definitions]),
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=self._sorts,
            filters=self._filters,
        )

    def relationships(self, relationships: Any = None, *definitions: ExtensionResourceRelationshipDefinition) -> "ApiResourceExtender":
        if relationships is None:
            items = definitions
        else:
            items = (relationships, *definitions)
        return self.relationships_with(*items)

    def relationships_with(self, *definitions: Any) -> "ApiResourceExtender":
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=tuple([*self._relationships, *definitions]),
            endpoints=self._endpoints,
            sorts=self._sorts,
            filters=self._filters,
        )

    def model_relationship(
        self,
        name: str,
        *,
        resource_type: str = "",
        many: bool = False,
        description: str = "",
        select_related: tuple[str, ...] = (),
        prefetch_related: tuple[Any, ...] = (),
        preload_resolver: Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]] | None = None,
        visible: Callable[[Any, dict], bool] | bool = True,
        includable: Callable[[dict], bool] | bool = True,
    ) -> "ApiResourceExtender":
        relationship_name = str(name or "").strip()
        if not relationship_name:
            return self

        def resolver(instance, context):
            from apps.core.extensions.runtime import resolve_runtime_model_relation

            return resolve_runtime_model_relation(
                instance,
                relationship_name,
                default=[] if many else None,
            )

        return self.relationships_with(
            ExtensionResourceRelationshipDefinition(
                resource=self.resource_name,
                relationship=relationship_name,
                module_id="",
                resolver=resolver,
                description=description,
                select_related=select_related,
                prefetch_related=prefetch_related,
                preload_resolver=preload_resolver,
                visible=visible,
                includable=includable,
                resource_type=resource_type,
                many=many,
            )
        )

    def relationships_before(
        self,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        return self._relationship_mutators_with_operation("before", anchor, *definitions)

    def relationships_after(
        self,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        return self._relationship_mutators_with_operation("after", anchor, *definitions)

    def relationships_before_all(
        self,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        return self._relationship_mutators_with_operation("before_all", "", *definitions)

    def remove_relationships(
        self,
        *relationships: str,
        condition: Callable[[dict], bool] | None = None,
    ) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=relationship,
                module_id="",
                operation="remove",
                mutator=lambda current: current,
                condition=condition,
                kind="relationship",
            )
            for relationship in relationships
        )
        return self.field(*definitions)

    def remove_relationship(
        self,
        relationship: str,
        *,
        condition: Callable[[dict], bool] | None = None,
    ) -> "ApiResourceExtender":
        return self.remove_relationships(relationship, condition=condition)

    def mutate_relationship(self, relationships, mutator: Callable[[Any], Any]) -> "ApiResourceExtender":
        return self.relationship(relationships, mutator)

    def relationship(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_relationship_mutators(definitions[0], definitions[1])
        return self.field(*definitions)

    def endpoints(self, endpoints: Any = None, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        if endpoints is None:
            items = definitions
        else:
            items = (endpoints, *definitions)
        return self.endpoints_with(*items)

    def endpoints_with(self, *definitions: Any) -> "ApiResourceExtender":
        return self.endpoint(*definitions)

    def endpoints_before(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("before", anchor, *definitions)

    def endpoint_before(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self.endpoints_before(anchor, *definitions)

    def endpoints_after(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("after", anchor, *definitions)

    def endpoint_after(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self.endpoints_after(anchor, *definitions)

    def endpoints_before_all(self, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("before_all", "", *definitions)

    def endpoint_before_all(self, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self.endpoints_before_all(*definitions)

    def remove_endpoints(self, *endpoints: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceEndpointDefinition(
                resource=self.resource_name,
                endpoint=endpoint,
                module_id="",
                operation="remove",
                condition=condition,
            )
            for endpoint in endpoints
        )
        return self.endpoint(*definitions)

    def remove_endpoint(self, endpoint: str, *, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        return self.remove_endpoints(endpoint, condition=condition)

    def mutate_endpoint(self, endpoints, mutator: Callable[[Any], Any]) -> "ApiResourceExtender":
        return self.endpoint(endpoints, mutator)

    def endpoint(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_endpoint_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=tuple([*self._endpoints, *definitions]),
            sorts=self._sorts,
            filters=self._filters,
        )

    def add_default_include(self, endpoints, includes) -> "ApiResourceExtender":
        normalized_includes = tuple(normalize_names(includes))

        def mutate(endpoint):
            current = list(getattr(endpoint, "default_include", ()) or ())
            seen = set(current)
            for include in normalized_includes:
                if include and include not in seen:
                    seen.add(include)
                    current.append(include)
            return replace(endpoint, default_include=tuple(current))

        return self.endpoint(endpoints, mutate)

    def eager_load(self, endpoints, *items: Any) -> "ApiResourceExtender":
        def mutate(endpoint):
            return replace(endpoint, eager_load=tuple([
                *(getattr(endpoint, "eager_load", ()) or ()),
                *items,
            ]))

        return self.endpoint(endpoints, mutate)

    def eager_load_when_included(self, endpoints, include: str, *items: Any) -> "ApiResourceExtender":
        normalized_include = str(include or "").strip()
        if not normalized_include:
            return self

        def mutate(endpoint):
            return replace(endpoint, eager_load_when_included_rules=tuple([
                *(getattr(endpoint, "eager_load_when_included_rules", ()) or ()),
                (normalized_include, tuple(items or ())),
            ]))

        return self.endpoint(endpoints, mutate)

    def eager_load_where(self, endpoints, relation: str, callback: Callable[[Any, dict], Any]) -> "ApiResourceExtender":
        normalized_relation = str(relation or "").strip()
        if not normalized_relation or not callable(callback):
            return self

        def mutate(endpoint):
            return replace(endpoint, eager_load_where_rules=tuple([
                *(getattr(endpoint, "eager_load_where_rules", ()) or ()),
                (normalized_relation, callback),
            ]))

        return self.endpoint(endpoints, mutate)

    def default_sort(self, endpoints, sort: str) -> "ApiResourceExtender":
        normalized_sort = str(sort or "").strip()

        def mutate(endpoint):
            return replace(endpoint, default_sort=normalized_sort)

        return self.endpoint(endpoints, mutate)

    def sorts(self, sorts: Any = None, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        if sorts is None:
            items = definitions
        else:
            items = (sorts, *definitions)
        return self.sort(*items)

    def sorts_with(self, *definitions: Any) -> "ApiResourceExtender":
        return self.sort(*definitions)

    def sorts_before(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("before", anchor, *definitions)

    def sort_before(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self.sorts_before(anchor, *definitions)

    def sorts_after(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("after", anchor, *definitions)

    def sort_after(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self.sorts_after(anchor, *definitions)

    def sorts_before_all(self, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("before_all", "", *definitions)

    def sort_before_all(self, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self.sorts_before_all(*definitions)

    def remove_sorts(self, *sorts: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceSortDefinition(
                resource=self.resource_name,
                sort=sort,
                module_id="",
                operation="remove",
                condition=condition,
            )
            for sort in sorts
        )
        return self.sort(*definitions)

    def remove_sort(self, sort: str, *, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        return self.remove_sorts(sort, condition=condition)

    def mutate_sort(self, sorts, mutator: Callable[[Any], Any]) -> "ApiResourceExtender":
        return self.sort(sorts, mutator)

    def sort(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_sort_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=tuple([*self._sorts, *definitions]),
            filters=self._filters,
        )

    def filters(self, filters: Any = None, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        if filters is None:
            items = definitions
        else:
            items = (filters, *definitions)
        return self.filter(*items)

    def filters_with(self, *definitions: Any) -> "ApiResourceExtender":
        return self.filter(*definitions)

    def filters_before(self, anchor: str, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self._filters_with_operation("before", anchor, *definitions)

    def filter_before(self, anchor: str, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self.filters_before(anchor, *definitions)

    def filters_after(self, anchor: str, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self._filters_with_operation("after", anchor, *definitions)

    def filter_after(self, anchor: str, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self.filters_after(anchor, *definitions)

    def filters_before_all(self, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self._filters_with_operation("before_all", "", *definitions)

    def filter_before_all(self, *definitions: ExtensionResourceFilterDefinition) -> "ApiResourceExtender":
        return self.filters_before_all(*definitions)

    def remove_filters(self, *filters: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceFilterDefinition(
                resource=self.resource_name,
                filter=item,
                module_id="",
                handler=lambda queryset, value, context: queryset,
                operation="remove",
                condition=condition,
            )
            for item in filters
        )
        return self.filter(*definitions)

    def remove_filter(self, filter_name: str, *, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        return self.remove_filters(filter_name, condition=condition)

    def mutate_filter(self, filters, mutator: Callable[[Any], Any]) -> "ApiResourceExtender":
        return self.filter(filters, mutator)

    def filter(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_filter_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=self._sorts,
            filters=tuple([*self._filters, *definitions]),
        )

    def _field_mutators_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceFieldDefinition,
    ) -> "ApiResourceExtender":
        mutators = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=definition.resource,
                field=definition.field,
                module_id=definition.module_id,
                operation=operation,
                anchor=anchor,
                mutator=lambda current, value=definition: value,
                kind="field",
            )
            for definition in definitions
        )
        return self.field(*mutators)

    def _named_field_mutators(self, fields, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=field,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for field in normalize_names(fields)
        )

    def _named_endpoint_mutators(self, endpoints, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceEndpointDefinition(
                resource=self.resource_name,
                endpoint=endpoint,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for endpoint in normalize_names(endpoints)
        )

    def _named_sort_mutators(self, sorts, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceSortDefinition(
                resource=self.resource_name,
                sort=sort,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for sort in normalize_names(sorts)
        )

    def _named_filter_mutators(self, filters, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceFilterDefinition(
                resource=self.resource_name,
                filter=filter_name,
                module_id="",
                handler=lambda queryset, value, context: queryset,
                operation="mutate",
                mutator=mutator,
            )
            for filter_name in normalize_names(filters)
        )

    def _named_relationship_mutators(self, relationships, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=relationship,
                module_id="",
                operation="mutate",
                mutator=mutator,
                kind="relationship",
            )
            for relationship in normalize_names(relationships)
        )

    def _relationship_mutators_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        mutators = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=definition.resource,
                field=definition.relationship,
                module_id=definition.module_id,
                operation=operation,
                anchor=anchor,
                mutator=lambda current, value=definition: value,
                kind="relationship",
            )
            for definition in definitions
        )
        return self.field(*mutators)

    def _endpoints_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceEndpointDefinition,
    ) -> "ApiResourceExtender":
        endpoints = tuple(
            replace(definition, operation=operation, anchor=anchor)
            for definition in definitions
        )
        return self.endpoint(*endpoints)

    def _sorts_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceSortDefinition,
    ) -> "ApiResourceExtender":
        sorts = tuple(
            replace(definition, operation=operation, anchor=anchor)
            for definition in definitions
        )
        return self.sort(*sorts)

    def _filters_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceFilterDefinition,
    ) -> "ApiResourceExtender":
        filters = tuple(
            replace(definition, operation=operation, anchor=anchor)
            for definition in definitions
        )
        return self.filter(*filters)

    @staticmethod
    def _is_named_mutator_call(definitions) -> bool:
        if len(definitions) != 2 or not callable(definitions[1]):
            return False
        names = definitions[0]
        if isinstance(names, str):
            return True
        if isinstance(names, (tuple, list, set)):
            return all(isinstance(name, str) for name in names)
        return False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        resources = () if isinstance(self.resource, str) else ((self.resource,) if self.resource is not None else ())
        fields = normalize_resource_fields(self.resource_name, resolve_definition_groups(self._fields, app))
        relationships = normalize_resource_relationships(self.resource_name, resolve_definition_groups(self._relationships, app))
        endpoints = normalize_resource_endpoints(self.resource_name, resolve_definition_groups(self._endpoints, app))
        sorts = normalize_resource_sorts(self.resource_name, resolve_definition_groups(self._sorts, app))
        filters = normalize_resource_filters(self.resource_name, resolve_definition_groups(self._filters, app))
        ResourceExtender(
            resources=resources,
            fields=fields,
            field_mutators=self._field_mutators,
            relationships=relationships,
            endpoints=endpoints,
            sorts=sorts,
            filters=filters,
        ).extend(app, extension)

    @staticmethod
    def _resource_object_name(resource) -> str:
        if resource is None:
            return ""
        resource_object = resource
        if isinstance(resource, type):
            try:
                resource_object = resource()
            except TypeError:
                return ""
        type_method = getattr(resource_object, "type", None)
        if callable(type_method):
            return str(type_method() or "").strip()
        return ""
