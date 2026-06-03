from __future__ import annotations

from typing import Any


class ResourceContext(dict):
    def __init__(self, values: dict | None = None, **kwargs) -> None:
        super().__init__(values or {})
        if kwargs:
            self.update(kwargs)

    def with_value(self, key: str, value: Any) -> "ResourceContext":
        output = ResourceContext(self)
        output[key] = value
        return output

    def with_resource(self, resource: str) -> "ResourceContext":
        return self.with_value("resource", resource)

    def with_collection(self, collection: Any) -> "ResourceContext":
        return self.with_value("collection", collection)

    def with_resource_object(self, resource_object: Any) -> "ResourceContext":
        return self.with_value("resource_object", resource_object)

    def with_model(self, model: Any) -> "ResourceContext":
        return self.with_value("model", model)

    def with_field(self, field: Any) -> "ResourceContext":
        return self.with_value("field", field)

    def with_include(self, include: Any) -> "ResourceContext":
        return self.with_value("include", include)

    def with_query(self, query: Any) -> "ResourceContext":
        return self.with_value("queryset", query)

    def with_query_params(self, query_params: dict | None) -> "ResourceContext":
        return self.with_value("query", dict(query_params or {})).with_value("query_params", dict(query_params or {}))

    def with_search_results(self, results: Any) -> "ResourceContext":
        return self.with_value("search_results", results)

    def with_result(self, result: Any) -> "ResourceContext":
        return self.with_value("result", result)

    def with_document(self, document: dict) -> "ResourceContext":
        return self.with_value("document", document)

    def with_serializer(self, serializer: Any) -> "ResourceContext":
        return self.with_value("serializer", serializer)

    def with_api(self, api: Any) -> "ResourceContext":
        return self.with_value("api", api)

    def with_body(self, body: Any) -> "ResourceContext":
        return self.with_value("body", body).with_value("payload", body)

    def body(self) -> Any:
        return self.get("body") if "body" in self else self.get("payload", {})

    def data(self) -> dict:
        body = self.body()
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            return body["data"]
        return {}

    def attributes(self) -> dict:
        data = self.data()
        return dict(data.get("attributes") or {}) if isinstance(data.get("attributes"), dict) else {}

    def relationship_data(self) -> dict:
        data = self.data()
        return dict(data.get("relationships") or {}) if isinstance(data.get("relationships"), dict) else {}

    def path(self) -> str:
        return str(self.get("path") or self.get("endpoint") or "")

    def query_param(self, key: str, default: Any = None) -> Any:
        query = self.get("query") or self.get("query_params") or {}
        if not isinstance(query, dict):
            return default
        return query.get(key, default)

    def fields(self, resource: Any = None) -> list[Any]:
        registry = self.registry
        resource_name = self._resource_name(resource or self.resource)
        if registry is not None and resource_name:
            getter = getattr(registry, "get_effective_fields", None)
            if callable(getter):
                return list(getter(resource_name, self))
        resource_object = resource or self.resource_object
        resolver = getattr(resource_object, "resolve_fields", None)
        if callable(resolver):
            return list(resolver())
        return []

    def relationships(self, resource: Any = None) -> list[Any]:
        registry = self.registry
        resource_name = self._resource_name(resource or self.resource)
        if registry is not None and resource_name:
            getter = getattr(registry, "get_effective_relationships", None)
            if callable(getter):
                return list(getter(resource_name, self))
        return []

    def sparse_fields(self, resource: Any = None) -> list[Any]:
        resource_name = self._resource_name(resource or self.resource)
        requested = self.query_param("fields") or {}
        allowed = None
        if isinstance(requested, dict) and resource_name:
            raw = requested.get(resource_name)
            if isinstance(raw, str):
                allowed = {item.strip() for item in raw.split(",") if item.strip()}
            elif isinstance(raw, (list, tuple, set)):
                allowed = {str(item).strip() for item in raw if str(item).strip()}
        fields = [*self.fields(resource), *self.relationships(resource)]
        if allowed is None:
            return fields
        return [
            field
            for field in fields
            if self._item_name(field) in allowed
        ]

    def resource_for(self, value: Any) -> str:
        registry = self.registry
        if registry is None:
            return ""
        for definition in getattr(registry, "get_resources", lambda: [])():
            resource_name = getattr(definition, "resource", "")
            resource_object = registry.get_resource_object(resource_name)
            resource_for = getattr(resource_object, "resource_for", None)
            if callable(resource_for):
                matched = resource_for(value, self)
                if matched:
                    return str(matched)
        return ""

    def resource_object_for(self, resource: Any = None) -> Any:
        registry = self.registry
        resource_name = self._resource_name(resource or self.resource)
        if registry is not None and resource_name:
            getter = getattr(registry, "get_resource_object", None)
            if callable(getter):
                return getter(resource_name)
        return self.resource_object

    def collection_resources(self) -> tuple[str, ...]:
        collection = self.collection or self.resource_object
        resources = getattr(collection, "resources", None)
        if callable(resources):
            return tuple(resources())
        resource = self._resource_name(collection or self.resource)
        return (resource,) if resource else ()

    @property
    def actor(self):
        return self.get("user") or self.get("actor")

    @property
    def resource(self):
        return self.get("resource")

    @property
    def collection(self):
        return self.get("collection")

    @property
    def resource_object(self):
        return self.get("resource_object")

    @property
    def model(self):
        return self.get("model")

    @property
    def queryset(self):
        return self.get("queryset")

    @property
    def result(self):
        return self.get("result")

    @property
    def document(self):
        return self.get("document")

    @property
    def serializer(self):
        return self.get("serializer")

    @property
    def api(self):
        return self.get("api") or self.get("registry")

    @property
    def registry(self):
        return self.get("registry") or self.get("api")

    @property
    def base_path(self):
        return str(self.get("api_base_path") or self.get("base_path") or "/api")

    @staticmethod
    def _item_name(item: Any) -> str:
        return str(
            getattr(item, "field", "")
            or getattr(item, "relationship", "")
            or getattr(item, "name", "")
            or ""
        )

    @staticmethod
    def _resource_name(resource: Any) -> str:
        if isinstance(resource, str):
            return resource
        type_method = getattr(resource, "type", None)
        if callable(type_method):
            return str(type_method() or "").strip()
        return str(getattr(resource, "resource", "") or "")


def ensure_resource_context(context: dict | ResourceContext | None = None) -> ResourceContext:
    if isinstance(context, ResourceContext):
        return context
    return ResourceContext(context or {})
