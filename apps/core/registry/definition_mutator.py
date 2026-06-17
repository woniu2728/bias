"""
DefinitionMutator — 扩展驱动的定义改写/合并
"""
from __future__ import annotations

from typing import Any, List, Tuple

from apps.core.resource_definitions import (
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourceFieldMutatorDefinition,
    ResourceFilterDefinition,
    ResourceRelationshipDefinition,
    ResourceSortDefinition,
)
from apps.core.resource_objects import (
    Resource,
    ResourceEndpoint,
    ResourceField,
    ResourceFilter,
    ResourceRelationship,
    ResourceSort,
)
from apps.core.resource_conversion import (
    endpoint_to_definition,
    field_to_definition,
    filter_to_definition,
    relationship_to_definition,
    sort_to_definition,
)


class DefinitionMutator:
    """定义改写器"""

    def __init__(self, store: Any):
        self._store = store

    def apply_endpoint_mutators(self, resource, endpoint, endpoint_object, context=None):
        output = endpoint_object
        resolved_context = dict(context or {})
        for definition in self._store.get_endpoints(resource):
            if definition.endpoint != endpoint:
                continue
            if not self._store._is_applicable(definition.condition, resolved_context):
                continue
            if definition.mutator is None:
                continue
            output = definition.mutator(output)
        return output

    def apply_endpoint_definitions(self, resource, endpoints, context=None):
        output = list(endpoints or [])
        resolved_context = dict(context or {})
        for definition in self._store.get_endpoints(resource):
            if not self._store._is_applicable(definition.condition, resolved_context):
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

    def apply_field_definitions(self, resource, fields, context=None):
        output = list(fields or [])
        resolved_context = dict(context or {})
        for definition in self._store.get_field_mutators(resource):
            if self._mutator_kind(definition) == "relationship":
                continue
            if not self._store._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                output.append(definition.mutator(None))
            elif operation == "before_all":
                output.insert(0, definition.mutator(None))
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

    def apply_sort_definitions(self, resource, sorts, context=None):
        output = list(sorts or [])
        resolved_context = dict(context or {})
        for definition in self._store.get_sorts(resource):
            if not self._store._is_applicable(definition.condition, resolved_context):
                continue
            operation = str(definition.operation or "add").strip().lower()
            value = self._sort_definition_value(definition)
            if operation == "add":
                output.append(value)
            elif operation == "before_all":
                output.insert(0, value)
            elif operation == "before":
                self._insert_before(output, definition.anchor, value)
            elif operation == "after":
                self._insert_after(output, definition.anchor, value)
            elif operation == "remove":
                output = [item for item in output if self._item_name(item) != definition.sort]
            elif operation == "mutate" and definition.mutator is not None:
                output = [
                    self._external_sort_mutator_result(definition, item)
                    if self._item_name(item) == definition.sort
                    else item
                    for item in output
                ]
        return output

    @staticmethod
    def _item_name(item):
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return str(item.get("name") or item.get("field") or item.get("relationship") or item.get("sort") or item.get("filter") or item.get("endpoint") or item.get("code") or "")
        return str(getattr(item, "name", "") or getattr(item, "field", "") or getattr(item, "relationship", "") or getattr(item, "sort", "") or getattr(item, "filter", "") or getattr(item, "endpoint", "") or getattr(item, "code", "") or item)

    @staticmethod
    def _insert_before(items, anchor, value):
        index = DefinitionMutator._find_item_index(items, anchor)
        if str(anchor or "").strip() in {"0", "before_all"}:
            items.insert(0, value)
        elif index is not None:
            items.insert(index, value)

    @staticmethod
    def _insert_after(items, anchor, value):
        index = DefinitionMutator._find_item_index(items, anchor)
        if index is not None:
            items.insert(index + 1, value)

    @staticmethod
    def _find_item_index(items, anchor):
        normalized = str(anchor or "").strip()
        if not normalized:
            return None
        for index, item in enumerate(items):
            if DefinitionMutator._item_name(item) == normalized:
                return index
        return None

    @staticmethod
    def _is_field_definition_like(value):
        return (
            isinstance(value, ResourceFieldDefinition)
            or (hasattr(value, "resource") and hasattr(value, "field") and hasattr(value, "resolver"))
        )

    @staticmethod
    def _is_relationship_definition_like(value):
        return (
            isinstance(value, ResourceRelationshipDefinition)
            or (hasattr(value, "resource") and hasattr(value, "relationship") and hasattr(value, "resolver"))
        )

    @staticmethod
    def _is_sort_definition_like(value):
        return (
            isinstance(value, ResourceSortDefinition)
            or (hasattr(value, "resource") and hasattr(value, "sort") and hasattr(value, "handler"))
        )

    @staticmethod
    def _is_filter_definition_like(value):
        return (
            isinstance(value, ResourceFilterDefinition)
            or (hasattr(value, "resource") and hasattr(value, "filter") and hasattr(value, "handler"))
        )

    @staticmethod
    def _mutator_kind(definition):
        return str(getattr(definition, "kind", "") or "").strip().lower()

    @staticmethod
    def _sort_definition_value(definition):
        handler = getattr(definition, "handler", None)
        return definition if handler is None else handler

    @staticmethod
    def _external_sort_mutator_result(definition, target):
        if definition.mutator is None:
            return target
        try:
            mutated = definition.mutator(target)
        except (AttributeError, TypeError):
            return target
        if mutated is None:
            return target
        if DefinitionMutator._is_sort_definition_like(mutated):
            return DefinitionMutator._sort_definition_value(mutated)
        return mutated if mutated is not None else target

    @staticmethod
    def _endpoint_definition_matches(definition, endpoint):
        normalized = DefinitionMutator._normalize_endpoint_path(endpoint)
        return normalized in {
            DefinitionMutator._normalize_endpoint_path(definition.endpoint),
            DefinitionMutator._normalize_endpoint_path(definition.path),
        }

    @staticmethod
    def _mutate_endpoint_definition(mutator_definition, target):
        mutator = mutator_definition.mutator
        if mutator is not None:
            return mutator(target)
        return target

    @staticmethod
    def _is_endpoint_definition_like(value):
        return (
            hasattr(value, "resource")
            and hasattr(value, "endpoint")
            and (hasattr(value, "handler") or hasattr(value, "mutator") or hasattr(value, "kind"))
        )

    @staticmethod
    def _normalize_endpoint_definition(value):
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
    def _endpoint_operation(definition):
        operation = str(definition.operation or "mutate").strip().lower()
        if operation == "mutate" and definition.handler is not None and definition.mutator is None:
            return "add"
        return operation

    @staticmethod
    def _normalize_endpoint_path(value):
        return str(value or "").strip().strip("/")

    @staticmethod
    def _normalize_endpoint_methods(methods):
        if methods is None:
            return {"GET"}
        if isinstance(methods, str):
            return {str(methods).strip().upper()}
        return {str(m or "").strip().upper() for m in methods if str(m or "").strip()}
