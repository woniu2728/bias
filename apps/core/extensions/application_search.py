from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from apps.core.extensions.types import (
    ExtensionSearchDriverDefinition,
    ExtensionSearchIndexDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost


class ApplicationSearchService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._drivers_by_extension: dict[str, tuple[ExtensionSearchDriverDefinition, ...]] = {}
        self._indexes_by_extension: dict[str, tuple[ExtensionSearchIndexDefinition, ...]] = {}
        from apps.core.resource_search import ResourceSearchManager

        self.manager = ResourceSearchManager(container=host)

    def register_driver(self, extension_id: str, definition: ExtensionSearchDriverDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        drivers = tuple([*self._drivers_by_extension.get(normalized, ()), definition])
        self._drivers_by_extension[normalized] = drivers
        view = self._host._get_or_create_runtime_view(normalized)
        view.search_drivers = drivers
        self._register_resource_search_driver(definition)

    def get_drivers(self, *, extension_id: str | None = None) -> list[ExtensionSearchDriverDefinition]:
        if extension_id is not None:
            return list(self._drivers_by_extension.get(str(extension_id or "").strip(), ()))
        drivers: list[ExtensionSearchDriverDefinition] = []
        for items in self._drivers_by_extension.values():
            drivers.extend(items)
        return drivers

    def get_drivers_for_target(self, target: str) -> list[ExtensionSearchDriverDefinition]:
        normalized = str(target or "").strip()
        return [
            driver
            for driver in self.get_drivers()
            if driver.target == normalized
        ]

    def register_index_definition(self, extension_id: str, definition: ExtensionSearchIndexDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definition = replace(definition, module_id=definition.module_id or normalized)
        indexes = tuple([*self._indexes_by_extension.get(normalized, ()), definition])
        self._indexes_by_extension[normalized] = indexes
        view = self._host._get_or_create_runtime_view(normalized)
        view.search_indexes = indexes

    def get_index_definitions(self, *, extension_id: str | None = None) -> list[ExtensionSearchIndexDefinition]:
        if extension_id is not None:
            return list(self._indexes_by_extension.get(str(extension_id or "").strip(), ()))
        indexes: list[ExtensionSearchIndexDefinition] = []
        for items in self._indexes_by_extension.values():
            indexes.extend(items)
        return indexes

    def apply_filters(self, target: str, queryset, query: str, context: dict | None = None):
        text_query, parsed_filters = self.extract_filter_tokens(query, targets=(target,))
        output = queryset
        resolved_context = {
            **dict(context or {}),
            "query": query,
            "text_query": text_query,
            "target": target,
        }
        for definition, parsed_value in parsed_filters.get(target, []):
            output = definition.applier(output, parsed_value, resolved_context)
        return output

    def extract_filter_tokens(
        self,
        query: str,
        targets: tuple[str, ...] | None = None,
    ) -> tuple[str, dict[str, list]]:
        text_tokens: list[str] = []
        filters: dict[str, list] = {}
        allowed_targets = set(targets or ())

        for raw_token in (query or "").split():
            matched = False
            for definition in self.get_available_filters(targets=targets):
                if allowed_targets and definition.target not in allowed_targets:
                    continue
                parsed_value = definition.parser(raw_token)
                if parsed_value is None:
                    continue
                filters.setdefault(definition.target, []).append((definition, parsed_value))
                matched = True
                break

            if not matched:
                text_tokens.append(raw_token)

        return " ".join(text_tokens).strip(), filters

    def get_available_filters(self, *, targets: tuple[str, ...] | None = None):
        allowed_targets = set(targets or ())
        definitions = list(self._host.forum_registry.get_search_filters())
        for driver in self.get_drivers():
            if allowed_targets and driver.target not in allowed_targets:
                continue
            definitions.extend(driver.filters)
        if targets is not None:
            definitions = [item for item in definitions if item.target in allowed_targets]
        return definitions

    def apply_mutators(self, target: str, queryset, context: dict | None = None):
        output = queryset
        resolved_context = dict(context or {})
        for driver in self.get_drivers_for_target(target):
            for mutator in driver.mutators:
                output = self._invoke_search_callable(mutator, output, resolved_context)
        return output

    def get_searchers(self, target: str) -> list[Any]:
        searchers: list[Any] = []
        for driver in self.get_drivers_for_target(target):
            searchers.extend(driver.searchers)
        return searchers

    def get_fulltext_handlers(self, target: str) -> list[Any]:
        return [
            driver.fulltext
            for driver in self.get_drivers_for_target(target)
            if driver.fulltext is not None
        ]

    def searchable(self, model: Any) -> bool:
        return self.manager.searchable(model)

    def query(self, model: Any, queryset, criteria, context: dict):
        return self.manager.query(model, queryset, criteria, context)

    def filters_for(self, model: Any, *, resource: str = ""):
        return self.manager.filters_for(model, resource=resource)

    def register_filter(self, resource: str, definition) -> None:
        self.manager.register_filter(resource, definition)

    def register_searcher(self, model: Any, searcher: Any, *, driver: str = "database") -> None:
        self.manager.register_searcher(model, searcher, driver=driver)

    def register_indexer(self, model: Any, indexer: Any) -> None:
        self.manager.register_indexer(model, indexer)

    def indexers(self, model: Any):
        return self.manager.indexers(model)

    def indexable(self, model: Any) -> bool:
        return self.manager.indexable(model)

    def index(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self.manager.index(model, instance, context or {})

    def unindex(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self.manager.unindex(model, instance, context or {})

    def reindex(self, model: Any, instances: Any = None, context: dict | None = None) -> None:
        self.manager.reindex(model, instances, context or {})

    def _invoke_search_callable(self, callback, queryset, context: dict):
        if callable(callback):
            return callback(queryset, context)
        return queryset

    def _register_resource_search_driver(self, definition: ExtensionSearchDriverDefinition) -> None:
        target = str(definition.target or "").strip()
        from apps.core.resource_search import ResourceSearchFilter

        for item in definition.filters or ():
            name = str(getattr(item, "code", "") or getattr(item, "name", "") or "").strip()
            applier = getattr(item, "applier", None)
            if target and name and callable(applier):
                self.manager.register_filter(
                    target,
                    ResourceSearchFilter(
                        name=name,
                        handler=lambda state, value, context, item=item: item.applier(state.queryset, value, context),
                        module_id=getattr(item, "module_id", "") or target,
                    ),
                )
        for searcher in definition.searchers or ():
            model = getattr(searcher, "model", None)
            if model is not None:
                self.manager.register_searcher(
                    model,
                    searcher,
                    driver=str(definition.driver or "database"),
                    searcher_key=searcher,
                )
        if definition.model is not None and definition.searcher is not None:
            self.manager.register_searcher(
                definition.model,
                definition.searcher,
                driver=str(definition.driver or "database"),
                searcher_key=definition.searcher,
            )
        for indexer in getattr(definition, "indexers", ()) or ():
            model = getattr(indexer, "model", None) or definition.model
            if model is not None:
                self.manager.register_indexer(model, indexer)
        driver_indexers = getattr(definition.driver, "indexers", None)
        if isinstance(driver_indexers, dict):
            for model, indexers in driver_indexers.items():
                for indexer in indexers if isinstance(indexers, (list, tuple, set)) else (indexers,):
                    self.manager.register_indexer(model, indexer)
        searcher_key = definition.searcher if definition.searcher is not None else definition.model
        if searcher_key is not None and definition.fulltext is not None:
            self.manager.set_driver_fulltext(str(definition.driver or "database"), searcher_key, definition.fulltext)
        for item in definition.driver_filters or ():
            if searcher_key is None:
                continue
            filter_definition = self._to_resource_search_filter(item, target=target)
            if filter_definition is not None:
                self.manager.register_driver_filter(str(definition.driver or "database"), searcher_key, filter_definition)
        for replace, item in definition.replace_filters or ():
            if searcher_key is None:
                continue
            filter_definition = self._to_resource_search_filter(item, target=target)
            if filter_definition is not None:
                self.manager.register_driver_filter(
                    str(definition.driver or "database"),
                    searcher_key,
                    filter_definition,
                    replace=str(replace or "").strip(),
                )
        for mutator in definition.driver_mutators or ():
            if searcher_key is not None:
                self.manager.add_driver_mutator(str(definition.driver or "database"), searcher_key, mutator)

    @staticmethod
    def _to_resource_search_filter(item: Any, *, target: str = ""):
        from apps.core.resource_search import ResourceSearchFilter

        if isinstance(item, ResourceSearchFilter):
            return item
        name = str(
            getattr(item, "name", "")
            or getattr(item, "code", "")
            or getattr(item, "filter", "")
            or ""
        ).strip()
        if not name and isinstance(item, tuple) and len(item) == 2:
            name = str(item[0] or "").strip()
            handler = item[1]
        else:
            handler = getattr(item, "handler", None) or getattr(item, "applier", None)
        if not name or not callable(handler):
            return None

        def apply(state, value, context, handler=handler):
            try:
                return handler(state, value, context)
            except TypeError:
                return handler(state.queryset, value, context)

        return ResourceSearchFilter(
            name=name,
            handler=apply,
            module_id=getattr(item, "module_id", "") or target or "extension",
        )
