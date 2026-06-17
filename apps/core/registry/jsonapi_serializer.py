"""
JsonApiSerializer — JSON:API 序列化

职责：处理资源的序列化、JSON:API 文档拼装。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from apps.core.resource_context import ensure_resource_context
from apps.core.resource_definitions import ResourceRelationshipDefinition
from apps.core.resource_objects import Resource
from apps.core.resource_serializer import ResourceSerializer


class JsonApiSerializer:
    def __init__(self, store: Any):
        self._store = store

    def serialize(self, resource, instance, context=None, *, only=None, include=None):
        ctx = context or {}
        payload = {}
        rd = self._store.get_resource(resource)
        if rd:
            payload.update(rd.resolver(instance, ctx) or {})
        selected = set(only or [])
        for d in self._store.get_effective_fields(resource, ctx):
            if selected and d.field not in selected:
                continue
            if not self._store._is_field_visible(d, instance, ctx):
                continue
            payload[d.field] = d.resolver(instance, ctx)
        payload = self.apply_payload_field_mutators(resource, payload, ctx)
        include_set = set(include or [])
        if include_set:
            for d in self._store.get_effective_relationships(resource, ctx):
                if d.relationship not in include_set:
                    continue
                if not self._store._is_relationship_visible(d, instance, ctx):
                    continue
                if not self._store._is_relationship_includable(d, ctx):
                    continue
                payload[d.relationship] = self._serialize_plain_relationship(d, d.resolver(instance, ctx), ctx)
        return payload

    def _serialize_plain_relationship(self, definition, value, context):
        if definition.many:
            return [self._serialize_plain_related_item(definition, item, context)
                    for item in ResourceSerializer.relationship_values(value, many=True) if item is not None]
        return self._serialize_plain_related_item(definition, value, context)

    def _serialize_plain_related_item(self, definition, value, context):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return value
        rt = ResourceSerializer(self._store, context).related_resource_type(definition, value, ensure_resource_context(context))
        if not rt or self._store.get_resource(rt) is None:
            return value
        return self.serialize(rt, value, context)

    def serialize_jsonapi_document(self, resource, data, context=None, *, only=None, include=None, many=False):
        serializer = ResourceSerializer(self._store, context)
        return serializer.document(resource, data, only=only, include=include, many=many)

    def serialize_jsonapi_resource(self, resource, instance, context=None, *, only=None, include_tree=None, included=None, deferred=None):
        return self._serialize_jsonapi_resource_internal(resource, instance, context, only=only,
                                                         include_tree=include_tree, included=included, deferred=deferred)

    def _serialize_jsonapi_resource_internal(self, resource, instance, context=None, *, only=None,
                                              include_tree=None, included=None, deferred=None):
        serializer = ResourceSerializer(self._store, context)
        if included is not None:
            serializer.included = included
        if deferred is not None:
            serializer.deferred = deferred
        return serializer._build_resource(resource, instance, only=only, include_tree=include_tree or {})

    def apply_payload_field_mutators(self, resource, payload, context=None):
        output = dict(payload or {})
        ctx = dict(context or {})
        for definition in self._store.get_field_mutators(resource):
            if not self._store._is_applicable(definition.condition, ctx):
                continue
            operation = str(definition.operation or "mutate").strip().lower()
            if operation == "add":
                try:
                    mutated = definition.mutator(output.get(definition.field))
                except (AttributeError, TypeError):
                    continue
                if not self._store._is_resource_definition_mutation(mutated):
                    output[definition.field] = mutated
            elif operation == "remove":
                output.pop(definition.field, None)
            elif operation == "mutate" and definition.field in output:
                try:
                    mutated = definition.mutator(output[definition.field])
                except (AttributeError, TypeError):
                    continue
                if not self._store._is_resource_definition_mutation(mutated):
                    output[definition.field] = mutated
        return output

    @staticmethod
    def _add_jsonapi_included(definition, value, context, include_tree, included=None, deferred=None):
        serializer = ResourceSerializer(None, context)
        if included is not None:
            serializer.included = included
        if deferred is not None:
            serializer.deferred = deferred
        serializer.add_relationship_included(definition, value, ensure_resource_context(context), include_tree)

    @staticmethod
    def _set_jsonapi_value(payload, key, value, deferred=None):
        serializer = ResourceSerializer(None)
        if deferred is not None:
            serializer.deferred = deferred
        serializer.set_value(payload, key, value)
        if deferred is None:
            serializer.resolve_deferred()

    @staticmethod
    def _set_jsonapi_relationship(relationship_payload, definition, value, context, include_tree, included=None, deferred=None):
        serializer = ResourceSerializer(None, context)
        if included is not None:
            serializer.included = included
        if deferred is not None:
            serializer.deferred = deferred
        serializer.set_relationship(relationship_payload, definition, value, ensure_resource_context(context), include_tree)
        if deferred is None:
            serializer.resolve_deferred()

    @staticmethod
    def _resolve_jsonapi_deferred(deferred):
        ResourceSerializer.resolve_deferred_callbacks(deferred)

    def _relationship_linkage(self, definition, value, context):
        serializer = ResourceSerializer(self._store, context)
        return serializer.relationship_linkage(definition, value, context)

    def _resource_identifier_payload(self, resource, value, context):
        serializer = ResourceSerializer(self._store, context)
        return serializer.resource_identifier_payload(resource, value, context)

    def _resolve_related_resource_type(self, definition, value, context):
        serializer = ResourceSerializer(self._store, context)
        return serializer.related_resource_type(definition, value, ensure_resource_context(context))

    @staticmethod
    def _resource_self_link(resource, resource_id, context):
        return ResourceSerializer.resource_self_link(resource, resource_id, context)

    def _resource_identifier(self, resource, instance, context, resource_object=None):
        serializer = ResourceSerializer(self._store, context)
        return serializer.resource_identifier(resource, instance, context, resource_object=resource_object)

    @staticmethod
    def _relationship_values(value, *, many):
        return ResourceSerializer.relationship_values(value, many=many)

    @staticmethod
    def _is_jsonapi_identifier(value):
        return ResourceSerializer.is_jsonapi_identifier(value)
