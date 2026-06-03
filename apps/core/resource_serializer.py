from __future__ import annotations

from typing import Any, Callable

from apps.core.resource_context import ResourceContext, ensure_resource_context

ResourceSerializationContext = ResourceContext


class ResourceSerializer:
    def __init__(self, registry, context: dict | None = None) -> None:
        self.registry = registry
        self.context = ensure_resource_context(context).with_value("registry", registry)
        self.deferred: list[Callable[[], None]] = []
        self.included: dict[tuple[str, str], tuple[tuple[str, str], dict]] = {}
        self.map: dict[tuple[str, str], dict] = {}
        self.primary_keys: list[tuple[str, str]] = []
        self.context = self.context.with_serializer(self)

    def document(
        self,
        resource: str,
        data: Any,
        *,
        only=None,
        include=None,
        many: bool = False,
    ) -> dict:
        include_tree = self.registry._build_include_tree(include or ())
        if many:
            for item in data or []:
                self.add_primary(resource, item, include_tree=include_tree, only=only)
        else:
            self.add_primary(resource, data, include_tree=include_tree, only=only)
        data_items, included_items = self.serialize()
        return {
            "data": data_items if many else (data_items[0] if data_items else None),
            **({"included": included_items} if included_items else {}),
        }

    def add_primary(self, resource: str, instance: Any, *, include_tree=None, only=None) -> dict:
        data = self.resource(resource, instance, only=only, include_tree=include_tree or {})
        key = self._resource_key(data)
        if key is not None and key not in self.primary_keys:
            self.primary_keys.append(key)
        return data

    def add_included(self, resource: str, instance: Any, *, include_tree=None, only=None) -> dict:
        data = self.resource(resource, instance, only=only, include_tree=include_tree or {})
        return {"type": data.get("type"), "id": data.get("id")}

    def serialize(self) -> tuple[list[dict], list[dict]]:
        self.resolve_deferred()
        for key in list(self.map.keys()):
            self.map[key] = self._refresh_resource_from_map(self.map[key])
        for included_key, included_data in self.included.values():
            self.map[included_key] = included_data
        primary_key_set = set(self.primary_keys)
        primary = [self.map[key] for key in self.primary_keys if key in self.map]
        included = [
            item
            for key, item in self.map.items()
            if key not in primary_key_set
        ]
        return primary, included

    def resource(self, resource: str, instance: Any, *, only=None, include_tree=None) -> dict:
        data = self._build_resource(resource, instance, only=only, include_tree=include_tree or {})
        key = self._resource_key(data)
        if key is not None:
            self.map[key] = data
        for included_key, included_data in self.included.values():
            self.map[included_key] = included_data
        return data

    def _build_resource(self, resource: str, instance: Any, *, only=None, include_tree=None) -> dict:
        context = self.context.with_resource(resource).with_model(instance)
        resource_object = self.registry.get_resource_object(resource)
        resource_id = self.resource_identifier(resource, instance, context, resource_object)
        output = {"type": resource}
        if resource_id is not None:
            output["id"] = resource_id
            output["links"] = {"self": self.resource_self_link(resource, resource_id, context)}

        attributes = {}
        resource_definition = self.registry.get_resource(resource)
        if resource_definition:
            attributes.update(resource_definition.resolver(instance, context) or {})
        attributes.pop("id", None)

        selected_fields = set(only or [])
        for definition in self._fields_for(resource, context):
            if selected_fields and definition.field not in selected_fields:
                continue
            if not self.field_is_visible(definition, context):
                continue
            value = self.field_value(definition, context)
            self.set_value(attributes, definition.field, value)

        self.resolve_deferred()
        attributes = self.registry.apply_payload_field_mutators(resource, attributes, context)
        if attributes:
            output["attributes"] = attributes

        relationship_payload = {}
        include_tree = include_tree or {}
        for definition in self._relationships_for(resource, context):
            if selected_fields and definition.relationship not in selected_fields:
                continue
            if not self.field_is_visible(definition, context):
                continue
            value = self.field_value(definition, context)
            self.set_relationship(
                relationship_payload,
                definition,
                value,
                context,
                include_tree,
            )
        if relationship_payload:
            output["relationships"] = relationship_payload
        return output

    def _fields_for(self, resource: str, context: ResourceContext) -> list[Any]:
        sparse = context.sparse_fields(resource)
        if sparse:
            return [
                item for item in sparse
                if getattr(item, "field", "") and not getattr(item, "relationship", "")
            ]
        return self.registry.get_effective_fields(resource, context)

    def _relationships_for(self, resource: str, context: ResourceContext) -> list[Any]:
        sparse = context.sparse_fields(resource)
        if sparse:
            return [item for item in sparse if getattr(item, "relationship", "")]
        return self.registry.get_effective_relationships(resource, context)

    def resolve_deferred(self) -> None:
        self.resolve_deferred_callbacks(self.deferred)

    @staticmethod
    def resolve_deferred_callbacks(deferred: list[Callable[[], None]]) -> None:
        depth = 0
        while deferred:
            callbacks = list(deferred)
            deferred.clear()
            for callback in callbacks:
                callback()
            depth += 1
            if depth > 10:
                raise RuntimeError("Too many levels of deferred JSON:API values")

    def set_value(self, payload: dict, key: str, value: Any) -> None:
        if callable(value):
            payload.setdefault(key, None)
            self.deferred.append(lambda: self.set_value(payload, key, value()))
            return
        payload[key] = value

    def field_value(self, definition: Any, context: ResourceContext) -> Any:
        field_object = getattr(definition, "field_object", None)
        get_value = getattr(field_object, "get_value", None)
        if callable(get_value):
            return get_value(context)
        return definition.resolver(context.get("model"), context)

    def field_is_visible(self, definition: Any, context: ResourceContext) -> bool:
        field_object = getattr(definition, "field_object", None)
        is_visible_for = getattr(field_object, "is_visible_for", None)
        if callable(is_visible_for):
            return bool(is_visible_for(context))
        visible = getattr(definition, "visible", True)
        if callable(visible):
            return bool(visible(context.get("model"), context))
        return bool(visible)

    def set_relationship(
        self,
        relationship_payload: dict,
        definition: Any,
        value: Any,
        context: ResourceContext,
        include_tree: dict,
    ) -> None:
        if callable(value):
            relationship_payload.setdefault(definition.relationship, {"data": None})
            self.deferred.insert(0, lambda: self.set_relationship(
                relationship_payload,
                definition,
                value(),
                context,
                include_tree,
            ))
            return
        linkage = self.relationship_linkage(definition, value, context)
        if linkage is not _JSONAPI_SKIP:
            relationship_payload[definition.relationship] = {"data": linkage}
        if definition.relationship in include_tree and self.registry._is_relationship_includable(definition, context):
            self.add_relationship_included(
                definition,
                value,
                context,
                include_tree[definition.relationship],
            )

    def add_relationship_included(self, definition: Any, value: Any, context: ResourceContext, include_tree: dict) -> None:
        for item in self.relationship_values(value, many=definition.many):
            if item is None or self.is_jsonapi_identifier(item):
                continue
            related_resource = self.related_resource_type(definition, item, context)
            if not related_resource:
                continue
            related_object = self.registry.get_resource_object(related_resource)
            related_id = self.resource_identifier(related_resource, item, context, related_object)
            if related_id is None:
                continue
            key = (related_resource, related_id)
            if key not in self.included:
                self.included[key] = (
                    key,
                    self._build_resource(related_resource, item, include_tree=include_tree),
                )

    def relationship_linkage(self, definition: Any, value: Any, context: ResourceContext):
        linkage = getattr(definition, "linkage", True)
        field_object = getattr(definition, "field_object", None)
        linkage_value = getattr(field_object, "linkage_value", None)
        if callable(linkage_value):
            value = linkage_value(value, context)
        elif callable(linkage):
            value = linkage(value, context)
        elif linkage is False:
            return _JSONAPI_SKIP
        if definition.many:
            return [
                item
                for item in (
                    self.resource_identifier_payload(self.related_resource_type(definition, item, context), item, context)
                    for item in self.relationship_values(value, many=True)
                )
                if item is not None
            ]
        return self.resource_identifier_payload(self.related_resource_type(definition, value, context), value, context)

    def resource_identifier_payload(self, resource: str, value: Any, context: ResourceContext) -> dict | None:
        if value is None:
            return None
        if self.is_jsonapi_identifier(value):
            return {"type": str(value["type"]), "id": str(value["id"])}
        resource_type = str(resource or "").strip()
        if not resource_type:
            return None
        if isinstance(value, dict) and "id" in value:
            return {"type": resource_type, "id": str(value["id"])}
        resource_object = self.registry.get_resource_object(resource_type)
        identifier = self.resource_identifier(resource_type, value, context, resource_object)
        if identifier is None:
            return None
        return {"type": resource_type, "id": identifier}

    def related_resource_type(self, definition: Any, value: Any, context: ResourceContext) -> str:
        resource_type = str(definition.resource_type or "").strip()
        if resource_type:
            return resource_type
        if value is None or self.is_jsonapi_identifier(value):
            return ""
        for resource in self.registry.get_resources():
            resource_object = self.registry.get_resource_object(resource.resource)
            if resource_object is None:
                continue
            model = getattr(resource_object, "model", None)
            if model is not None:
                try:
                    if isinstance(value, model):
                        return resource.resource
                except TypeError:
                    pass
            resource_for = getattr(resource_object, "resource_for", None)
            if callable(resource_for):
                matched = resource_for(value, context)
                if matched:
                    return str(matched)
        return ""

    @staticmethod
    def resource_self_link(resource: str, resource_id: str, context: dict) -> str:
        base_path = str(context.get("api_base_path") or context.get("base_path") or "/api").rstrip("/")
        return f"{base_path}/{resource}/{resource_id}"

    @staticmethod
    def resource_identifier(resource: str, instance: Any, context: dict, resource_object: Any | None = None) -> str | None:
        if instance is None:
            return None
        if resource_object is not None:
            value = resource_object.get_id(instance, context)
        else:
            value = getattr(instance, "id", None)
            if value is None:
                value = getattr(instance, "pk", None)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def relationship_values(value: Any, *, many: bool) -> list[Any]:
        if value is None:
            return []
        if many:
            all_method = getattr(value, "all", None)
            if callable(all_method):
                value = all_method()
            if isinstance(value, (list, tuple, set)):
                return list(value)
            return list(value) if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict)) else [value]
        return [value]

    @staticmethod
    def is_jsonapi_identifier(value: Any) -> bool:
        return isinstance(value, dict) and "type" in value and "id" in value

    def _refresh_resource_from_map(self, data: dict) -> dict:
        key = self._resource_key(data)
        if key is None:
            return data
        current = self.map.get(key)
        return current or data

    @staticmethod
    def _resource_key(data: dict) -> tuple[str, str] | None:
        resource_type = data.get("type")
        resource_id = data.get("id")
        if resource_type is None or resource_id is None:
            return None
        return str(resource_type), str(resource_id)


_JSONAPI_SKIP = object()
