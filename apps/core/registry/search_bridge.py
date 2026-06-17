"""
SearchBridge — 资源搜索桥接

职责：封装资源搜索逻辑，桥接 DatabaseResource.search / RuntimeSearchManager / 扩展 searcher。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.core.resource_definitions import (
    ResourceEndpointDefinition,
    ResourceFilterDefinition,
)
from apps.core.resource_objects import (
    DatabaseResource,
    ResourceSearchCriteria,
    ResourceSearchResults,
)
from apps.core.resource_search import ResourceSearchFilter, get_resource_search_manager


logger = logging.getLogger(__name__)


class SearchBridge:
    """搜索桥接"""

    def __init__(self, store: Any):
        self._store = store

    def search_resource_index(
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

        manager = self.runtime_search_manager()
        if manager is not None:
            model = getattr(resource_object, "model", None)
            if manager.searchable(model) or manager.filters_for(model, resource=definition.resource):
                return manager.query(model, queryset, criteria, context_with_search)

        try:
            from apps.core.extensions.bootstrap_state import is_extension_host_bootstrapped

            if not is_extension_host_bootstrapped():
                search_service = None
            else:
                from apps.core.extensions.runtime import get_runtime_search_service

                search_service = get_runtime_search_service()
        except Exception:
            logger.warning("Failed to resolve runtime search service for resource dispatch.", exc_info=True)
            search_service = None
        if search_service is not None:
            searchers = getattr(search_service, "get_searchers", lambda target: [])(definition.resource)
            for searcher in searchers:
                result = self._invoke_resource_searcher(searcher, queryset, criteria, context_with_search)
                normalized = self._normalize_search_result(result)
                if normalized is not None:
                    return normalized
        return None

    def runtime_search_manager(self):
        try:
            from apps.core.extensions.bootstrap_state import is_extension_host_bootstrapped

            if not is_extension_host_bootstrapped():
                raise RuntimeError("extension host is not bootstrapped")
            from apps.core.extensions.runtime import get_runtime_search_service

            service = get_runtime_search_service()
            manager = getattr(service, "manager", None)
            if manager is not None:
                self._sync_resource_filters_to_search_manager(manager)
                return manager
        except RuntimeError:
            pass
        except Exception:
            logger.warning("Failed to resolve extension runtime search manager.", exc_info=True)
        manager = get_resource_search_manager()
        self._sync_resource_filters_to_search_manager(manager)
        return manager

    def _sync_resource_filters_to_search_manager(self, manager) -> None:
        for resource in (
            set(self._store._definitions.keys())
            | set(self._store._resource_objects.keys())
            | set(self._store._filters.keys())
        ):
            for definition in self._store.get_effective_filters(resource):
                self._register_search_filter(definition, manager=manager)

    def _register_search_filter(self, definition: ResourceFilterDefinition, *, manager=None) -> None:
        target_manager = manager or self.runtime_search_manager()
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
        if hasattr(searcher, "search"):
            try:
                return searcher.search(queryset, criteria, context)
            except Exception:
                logger.warning("Searcher.search raised, falling through", exc_info=True)
                return None
        if callable(searcher):
            try:
                return searcher(queryset, criteria, context)
            except Exception:
                logger.warning("Callable searcher raised, falling through", exc_info=True)
                return None
        return None

    def apply_default_fulltext_filter(self, resource: str, queryset, value: Any, context: dict):
        query = str(value or "").strip()
        if not query:
            return queryset
        resource_object = self._store.get_resource_object(resource)
        fields = [
            definition.field
            for definition in self._store.get_effective_fields(resource, context)
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
