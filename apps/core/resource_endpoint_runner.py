from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from apps.core.resource_context import ResourceContext, ensure_resource_context
from apps.core.resource_objects import DatabaseResource


@dataclass(frozen=True)
class ResourceEndpointPipeline:
    query: Callable[[ResourceContext], ResourceContext] | None = None
    action: Callable[[ResourceContext], Any] | None = None
    before_serialization: Callable[[ResourceContext, Any], Any] | None = None
    response: Callable[[ResourceContext, Any], Any] | None = None


class ResourceEndpointRunner:
    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, definition: Any, context: dict):
        resolved_context = ensure_resource_context(context).with_resource(definition.resource)
        if definition.handler is not None:
            return definition.handler(resolved_context)

        resource_object = self.registry.get_resource_object(definition.resource)
        if resource_object is None:
            raise ValueError("资源不存在")
        if not isinstance(resource_object, DatabaseResource):
            raise ValueError("资源端点没有处理器")
        resolved_context = resolved_context.with_resource_object(resource_object).with_collection(resource_object)

        pipeline = self.pipeline_for(resource_object, definition)
        if pipeline.query is not None:
            resolved_context = pipeline.query(resolved_context)
        if callable(getattr(definition, "query_callback", None)):
            updated_context = definition.query_callback(resolved_context)
            if updated_context is not None:
                resolved_context = ensure_resource_context(updated_context)
        result = pipeline.action(resolved_context) if pipeline.action is not None else None
        resolved_context = resolved_context.with_result(result)
        if callable(getattr(definition, "action_callback", None)):
            updated_result = definition.action_callback(resolved_context)
            if updated_result is not None:
                result = updated_result
                resolved_context = resolved_context.with_result(result)
        if pipeline.before_serialization is not None:
            updated = pipeline.before_serialization(resolved_context, result)
            if updated is not None:
                result = updated
                resolved_context = resolved_context.with_result(result)
        if callable(getattr(definition, "before_serialization_callback", None)):
            updated = definition.before_serialization_callback(resolved_context, result)
            if updated is not None:
                result = updated
                resolved_context = resolved_context.with_result(result)
        if pipeline.response is not None:
            response = pipeline.response(resolved_context, result)
        else:
            response = result
        if isinstance(response, dict):
            resolved_context = resolved_context.with_document(response)
        if callable(getattr(definition, "response_callback", None)):
            updated_response = definition.response_callback(resolved_context, response)
            if updated_response is not None:
                response = updated_response
        return response

    def pipeline_for(self, resource_object: DatabaseResource, definition: Any) -> ResourceEndpointPipeline:
        build_pipeline = getattr(definition, "build_pipeline", None)
        if callable(build_pipeline):
            return build_pipeline(self.registry, resource_object)
        endpoint = DatabaseResourceEndpoint(self.registry, resource_object, definition)
        kind = str(definition.kind or definition.endpoint or "").strip().lower()
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

    def _resource_response(self, definition: Any, context: ResourceContext, instance: Any):
        document = self.registry.serialize_jsonapi_document(
            definition.resource,
            instance,
            context,
            include=self.registry._resolve_endpoint_include(definition, context),
        )
        self.registry._merge_endpoint_document_meta_links(document, definition, context, instance)
        return document


class EndpointListingParams:
    def listing_params(self, context: ResourceContext) -> dict[str, Any]:
        definition = self.definition
        return {
            "pagination": self.registry._resolve_endpoint_pagination(definition, context) if definition.paginate else None,
            "include": self.registry._resolve_endpoint_include(definition, context),
            "sort": self.registry._resolve_endpoint_sort(definition, context),
            "filters": self.registry._resolve_endpoint_filters(context),
        }


class EndpointHooks:
    def call_before_hook(self, context: ResourceContext) -> None:
        self.registry._call_endpoint_before(self.definition, context)

    def call_after_hook(self, context: ResourceContext, result: Any) -> Any:
        return self.registry._call_endpoint_after(self.definition, context, result)


class EndpointAuthorization:
    def ensure_ability(self, instance: Any | None, context: ResourceContext) -> None:
        self.registry._ensure_resource_ability(self.resource_object, self.definition, instance, context)


class EndpointIncludesData:
    def apply_query_preloads(self, queryset: Any, context: ResourceContext, include: Any) -> Any:
        return self.registry.apply_preload_plan(queryset, self.definition.resource, context, include=include)

    def before_serialize_includes(self, context: ResourceContext, results: Any) -> Any:
        method = context.get("method") or (getattr(self.definition, "methods", ("GET",)) or ("GET",))[0]
        endpoint_context = context.with_value("method", method)
        plan = self.registry.build_endpoint_definition_preload_plan(self.definition, endpoint_context)
        context["preload_plan"] = plan
        prefetches = list(plan.prefetch_related)
        if plan.prefetch_where:
            prefetches = self.apply_where_eager_loads(prefetches, plan.prefetch_where, results, context)
        if prefetches:
            try:
                from django.db.models import prefetch_related_objects

                prefetch_related_objects(list(results or ()), *prefetches)
            except Exception:
                pass
        return results

    def apply_where_eager_loads(
        self,
        prefetches: list[Any],
        prefetch_where: tuple[tuple[str, Callable[[Any, ResourceContext], Any]], ...],
        results: Any,
        context: ResourceContext,
    ) -> list[Any]:
        try:
            from django.db.models import Prefetch
        except Exception:
            return prefetches
        output = [item for item in prefetches if str(item) not in {relation for relation, _ in prefetch_where}]
        model = getattr(self.resource_object, "model", None)
        sample = next(iter(results or ()), None)
        for relation, callback in prefetch_where:
            queryset = self._relation_queryset_for_model(model, relation) or self._relation_queryset(sample, relation)
            if queryset is None:
                output.append(relation)
                continue
            updated = callback(queryset, context)
            output.append(Prefetch(relation, queryset=updated if updated is not None else queryset))
        return output

    @staticmethod
    def _relation_queryset(instance: Any, relation: str):
        if instance is None:
            return None
        current = instance
        for part in str(relation or "").split("__"):
            current = getattr(current, part, None)
            if current is None:
                return None
        all_method = getattr(current, "all", None)
        if callable(all_method):
            try:
                return all_method()
            except Exception:
                return None
        return None

    @staticmethod
    def _relation_queryset_for_model(model: Any, relation: str):
        if model is None:
            return None
        current_model = model
        field = None
        for part in str(relation or "").replace(".", "__").split("__"):
            if not part:
                return None
            meta = getattr(current_model, "_meta", None)
            get_field = getattr(meta, "get_field", None)
            if not callable(get_field):
                return None
            try:
                field = get_field(part)
            except Exception:
                return None
            related_model = getattr(field, "related_model", None)
            if related_model is None:
                return None
            current_model = related_model
        manager = getattr(current_model, "objects", None)
        all_method = getattr(manager, "all", None)
        if callable(all_method):
            try:
                return all_method()
            except Exception:
                return None
        return None


class EndpointSearchesData:
    def apply_listing_query(
        self,
        queryset: Any,
        context: ResourceContext,
        params: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        definition = self.definition
        search_results = self.registry._search_resource_index(
            self.resource_object,
            definition,
            queryset,
            context,
            filters=params["filters"],
            sort=params["sort"],
            pagination=params["pagination"],
        )
        total = None
        if search_results is not None:
            queryset = search_results.results
            total = search_results.total
            if params["sort"] and not search_results.sort_applied:
                queryset = self.registry.apply_named_sort(definition.resource, queryset, params["sort"], context)
            return queryset, search_results, total

        if params["sort"]:
            queryset = self.registry.apply_named_sort(definition.resource, queryset, params["sort"], context)
        total = self.resource_object.count(queryset, context) if definition.paginate else None
        return queryset, search_results, total


class EndpointPagination:
    def apply_pagination(self, queryset: Any, context: ResourceContext, pagination: Any, search_results: Any) -> Any:
        if pagination and not (search_results is not None and search_results.pagination_applied):
            return self.resource_object.paginate(queryset, context.with_value("pagination", pagination))
        return queryset


class EndpointMeta:
    def collection_meta(self, document: dict, results: Any, context: ResourceContext) -> dict:
        definition = self.definition
        resource_object = self.resource_object
        total = context.get("total")
        if total is None:
            total = resource_object.count(context.queryset, context)
        pagination = context.get("pagination")
        meta = dict(document.get("meta") or {})
        meta.update({
            "total": total,
            "count": len(document.get("data") or []),
            "limit": pagination["limit"] if pagination else None,
            "offset": pagination["offset"] if pagination else 0,
        })
        meta.update(self.registry._resolve_endpoint_meta(definition, context, {"results": results, "total": total}) or {})
        return meta

    def collection_links(self, results: Any, context: ResourceContext) -> dict:
        total = context.get("total")
        if total is None:
            total = self.resource_object.count(context.queryset, context)
        return self.registry._resolve_endpoint_links(self.definition, context, {"results": results, "total": total}) or {}


class EndpointSerialization:
    def resource_response(self, instance: Any, context: ResourceContext):
        definition = self.definition
        document = self.registry.serialize_jsonapi_document(
            definition.resource,
            instance,
            context,
            include=self.registry._resolve_endpoint_include(definition, context),
        )
        self.registry._merge_endpoint_document_meta_links(document, definition, context, instance)
        return document

    def collection_response(self, results: Any, context: ResourceContext):
        definition = self.definition
        document = self.registry.serialize_jsonapi_document(definition.resource, results, context, include=context.get("include"), many=True)
        if not definition.paginate:
            return document
        document["meta"] = self.collection_meta(document, results, context)
        links = self.collection_links(results, context)
        if links:
            document["links"] = links
        return document


class DatabaseResourceEndpoint(
    EndpointListingParams,
    EndpointHooks,
    EndpointAuthorization,
    EndpointIncludesData,
    EndpointSearchesData,
    EndpointPagination,
    EndpointMeta,
    EndpointSerialization,
):
    def __init__(self, registry, resource_object: DatabaseResource, definition: Any) -> None:
        self.registry = registry
        self.resource_object = resource_object
        self.definition = definition

    def index_pipeline(self) -> ResourceEndpointPipeline:
        resource_object = self.resource_object
        definition = self.definition

        def query(context: ResourceContext) -> ResourceContext:
            self.call_before_hook(context)
            queryset = resource_object.scope(resource_object.query(context), context)
            params = self.listing_params(context)
            pagination = params["pagination"]
            include = params["include"]
            filters = params["filters"]
            sort = params["sort"]
            queryset, search_results, total = self.apply_listing_query(queryset, context, params)
            queryset = self.apply_query_preloads(queryset, context, include)
            queryset = self.apply_pagination(queryset, context, pagination, search_results)
            return (
                context
                .with_query(queryset)
                .with_value("pagination", pagination)
                .with_value("include", include)
                .with_value("filters", filters)
                .with_value("sort", sort)
                .with_value("search_results", search_results)
                .with_value("total", total)
            )

        def action(context: ResourceContext):
            results = resource_object.results(context.queryset, context)
            return self.call_after_hook(context, results)

        def response(context: ResourceContext, results):
            return self.collection_response(results, context)

        return ResourceEndpointPipeline(
            query=query,
            action=action,
            before_serialization=lambda context, results: self.before_serialize_includes(context, results),
            response=response,
        )

    def show_pipeline(self) -> ResourceEndpointPipeline:
        resource_object = self.resource_object
        definition = self.definition

        def action(context: ResourceContext):
            self.call_before_hook(context)
            instance = resource_object.find(str(context.get("object_id") or ""), context)
            if instance is None:
                raise LookupError("资源不存在")
            self.ensure_ability(instance, context)
            return self.call_after_hook(context, instance)

        return ResourceEndpointPipeline(
            action=action,
            response=lambda context, instance: self.resource_response(instance, context),
        )

    def create_pipeline(self) -> ResourceEndpointPipeline:
        resource_object = self.resource_object
        definition = self.definition

        def action(context: ResourceContext):
            self.call_before_hook(context)
            self.ensure_ability(None, context)
            instance = resource_object.new_model(context)
            self.registry._parse_jsonapi_data(context, definition.resource, creating=True)
            self.registry.apply_resource_payload(definition.resource, instance, self.registry._extract_resource_payload(context), context, creating=True)
            instance = resource_object.create_action(instance, context)
            return self.call_after_hook(context, instance)

        return ResourceEndpointPipeline(
            action=action,
            response=lambda context, instance: (201, self.resource_response(instance, context)),
        )

    def update_pipeline(self) -> ResourceEndpointPipeline:
        resource_object = self.resource_object
        definition = self.definition

        def action(context: ResourceContext):
            self.call_before_hook(context)
            instance = resource_object.find(str(context.get("object_id") or ""), context)
            if instance is None:
                raise LookupError("资源不存在")
            self.ensure_ability(instance, context)
            self.registry._parse_jsonapi_data(context, definition.resource, creating=False, instance=instance, resource_object=resource_object)
            self.registry.apply_resource_payload(definition.resource, instance, self.registry._extract_resource_payload(context), context, creating=False)
            instance = resource_object.update_action(instance, context)
            return self.call_after_hook(context, instance)

        return ResourceEndpointPipeline(
            action=action,
            response=lambda context, instance: self.resource_response(instance, context),
        )

    def delete_pipeline(self) -> ResourceEndpointPipeline:
        resource_object = self.resource_object
        definition = self.definition

        def action(context: ResourceContext):
            self.call_before_hook(context)
            instance = resource_object.find(str(context.get("object_id") or ""), context)
            if instance is None:
                raise LookupError("资源不存在")
            self.ensure_ability(instance, context)
            resource_object.delete_action(instance, context)
            self.call_after_hook(context, None)
            return None

        return ResourceEndpointPipeline(action=action, response=lambda context, result: (204, None))
