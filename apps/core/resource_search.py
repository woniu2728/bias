from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from apps.core.extensions.container import resolve_container_value, wrap_callback
from apps.core.resource_errors import BadJsonApiRequest
from apps.core.resource_objects import ResourceSearchCriteria, ResourceSearchResults


ResourceSearcher = Callable[[Any, ResourceSearchCriteria, dict], Any]
ResourceFilterHandler = Callable[[Any, Any, dict], Any]


@dataclass
class ResourceSearchState:
    queryset: Any
    criteria: ResourceSearchCriteria
    context: dict
    active_filters: list[Any] = field(default_factory=list)

    def add_active_filter(self, definition: Any) -> None:
        self.active_filters.append(definition)

    def filter(self, *args, **kwargs) -> "ResourceSearchState":
        filter_method = getattr(self.queryset, "filter", None)
        if callable(filter_method):
            self.queryset = filter_method(*args, **kwargs)
        return self

    def order_by(self, *fields) -> "ResourceSearchState":
        order_by = getattr(self.queryset, "order_by", None)
        if callable(order_by):
            self.queryset = order_by(*fields)
        return self


@dataclass(frozen=True)
class ResourceSearchFilter:
    name: str
    handler: ResourceFilterHandler
    visible: Callable[[dict], bool] | bool = True
    module_id: str = "core"

    def is_visible(self, context: dict) -> bool:
        if callable(self.visible):
            return bool(self.visible(context))
        return bool(self.visible)

    def apply(self, state: ResourceSearchState, value: Any, negate: bool = False):
        state.add_active_filter(self)
        result = self.handler(state, value, {**state.context, "filter": self.name, "negate": negate})
        if isinstance(result, ResourceSearchState):
            return result
        if result is not None:
            state.queryset = result
        return state


@dataclass(frozen=True)
class ResourceFulltextFilter:
    handler: Callable[[ResourceSearchState, str, dict], Any]

    def search(self, state: ResourceSearchState, query: str):
        state.add_active_filter(self)
        result = self.handler(state, query, {**state.context, "filter": "q"})
        if isinstance(result, ResourceSearchState):
            return result
        if result is not None:
            state.queryset = result
        return state


class ResourceFilterManager:
    def __init__(self, fulltext: ResourceFulltextFilter | Callable | None = None, *, strict: bool = False) -> None:
        self.fulltext = self._normalize_fulltext(fulltext)
        self.strict = bool(strict)
        self._filters: dict[str, list[ResourceSearchFilter]] = {}

    def add(self, definition: ResourceSearchFilter) -> None:
        self._filters.setdefault(definition.name, []).append(definition)

    def replace(self, name: str, definition: ResourceSearchFilter) -> None:
        self._filters[name] = [definition]

    def apply(self, state: ResourceSearchState, filters: dict[str, Any]) -> ResourceSearchState:
        query = (filters or {}).get("q")
        if self.fulltext is not None and query:
            state = self.fulltext.search(state, str(query))
        for raw_name, value in (filters or {}).items():
            normalized = str(raw_name or "").strip()
            if normalized == "q":
                continue
            negate = normalized.startswith("-")
            name = normalized[1:] if negate else normalized
            definitions = [item for item in self._filters.get(name, ()) if item.is_visible(state.context)]
            if not definitions:
                if self.strict:
                    raise BadJsonApiRequest(f"Invalid filter: {name}", parameter=f"filter[{name}]")
                continue
            for definition in definitions:
                state = definition.apply(state, value, negate)
        return state

    @staticmethod
    def _normalize_fulltext(fulltext):
        if fulltext is None:
            return None
        if isinstance(fulltext, ResourceFulltextFilter):
            return fulltext
        if hasattr(fulltext, "search") and callable(fulltext.search):
            return ResourceFulltextFilter(lambda state, query, context: fulltext.search(state, query))
        if callable(fulltext):
            return ResourceFulltextFilter(lambda state, query, context: fulltext(state, query, context))
        return None



@dataclass(frozen=True)
class ResourceSearchDriver:
    name: str
    searchers: dict[Any, Any] = field(default_factory=dict)
    searcher_keys_by_model: dict[Any, Any] = field(default_factory=dict)
    filters: dict[Any, tuple[ResourceSearchFilter, ...]] = field(default_factory=dict)
    fulltext: dict[Any, ResourceFulltextFilter | Callable] = field(default_factory=dict)
    mutators: dict[Any, tuple[Any, ...]] = field(default_factory=dict)
    indexers: dict[Any, tuple[Any, ...]] = field(default_factory=dict)
    default: bool = False

    def supports(self, model: Any) -> bool:
        return self.searcher_key_for(model) is not None

    def searcher_key_for(self, model: Any):
        mapped_key = self._find_model_key(model, self.searcher_keys_by_model)
        if mapped_key is not None:
            return self.searcher_keys_by_model[mapped_key]
        return self._find_model_key(model, self.searchers)

    def searcher(self, model: Any):
        key = self.searcher_key_for(model)
        if key is None:
            return None
        return self.searchers[key]

    def filters_for(self, model: Any) -> tuple[ResourceSearchFilter, ...]:
        key = self._filter_key_for(model, self.filters)
        if key is None:
            return ()
        return self.filters[key]

    def filter_manager_for(self, model: Any) -> ResourceFilterManager:
        key = self._filter_key_for(model, self.filters)
        fulltext_key = self._filter_key_for(model, self.fulltext)
        manager = ResourceFilterManager(self.fulltext.get(fulltext_key) if fulltext_key is not None else None)
        if key is not None:
            for definition in self.filters[key]:
                manager.add(definition)
        return manager

    def mutators_for(self, model: Any) -> tuple[Any, ...]:
        key = self._filter_key_for(model, self.mutators)
        if key is None:
            return ()
        return self.mutators[key]

    def indexers_for(self, model: Any) -> tuple[Any, ...]:
        key = self._find_model_key(model, self.indexers)
        if key is None:
            return ()
        return self.indexers[key]

    @staticmethod
    def _find_model_key(model: Any, values: dict[Any, Any]):
        if model in values:
            return model
        if isinstance(model, type):
            for key in values:
                try:
                    if isinstance(key, type) and issubclass(model, key):
                        return key
                except TypeError:
                    continue
                if isinstance(key, str) and key in {model.__name__, f"{model.__module__}.{model.__name__}"}:
                    return key
        return None

    def _filter_key_for(self, model: Any, values: dict[Any, Any]):
        searcher_key = self.searcher_key_for(model)
        if searcher_key in values:
            return searcher_key
        return self._find_model_key(model, values)


class DatabaseResourceSearchDriver:
    name = "database"

    def __init__(self, manager: "ResourceSearchManager") -> None:
        self.manager = manager

    def supports(self, model: Any) -> bool:
        return False

    def searcher(self, model: Any):
        def search(queryset, criteria: ResourceSearchCriteria, context: dict):
            resource = str(criteria.resource or "")
            state = ResourceSearchState(queryset=queryset, criteria=criteria, context=context)
            manager = ResourceFilterManager()
            for definition in self.manager.filters_for(model, resource=resource):
                manager.add(definition)
            state = manager.apply(state, criteria.filters or {})
            return ResourceSearchResults(
                results=state.queryset,
                sort_applied=False,
                pagination_applied=False,
                active_filters=tuple(state.active_filters),
            )

        return search


class ResourceSearchManager:
    def __init__(self, settings: Any | None = None, container: Any | None = None) -> None:
        self._drivers: dict[str, Any] = {}
        self._driver_classes: dict[str, Any] = {}
        self._driver_names_by_model: dict[Any, str] = {}
        self._indexers: dict[Any, list[Any]] = {}
        self._filters_by_resource: dict[str, list[ResourceSearchFilter]] = {}
        self.settings = settings
        self.container = container
        self.register_driver("database", DatabaseResourceSearchDriver(self), default=True)

    def set_container(self, container: Any) -> None:
        self.container = container

    def register_driver(self, name: str, driver: Any, *, default: bool = False) -> None:
        normalized = str(name or "").strip() or "database"
        self._driver_classes[normalized] = driver
        self._drivers[normalized] = self._resolve_component(driver)
        if default:
            self._drivers[""] = self._drivers[normalized]
            self._driver_classes[""] = driver

    def register_driver_class(self, driver: Any, *, name: str = "", default: bool = False) -> None:
        resolved_name = str(name or "").strip() or self._driver_name_from_class(driver)
        self.register_driver(resolved_name, driver, default=default)

    def driver_classes(self) -> tuple[Any, ...]:
        output = []
        for name, driver in self._driver_classes.items():
            if name == "":
                continue
            if driver not in output:
                output.append(driver)
        return tuple(output)

    def use_driver_for(self, model: Any, driver: str) -> None:
        if model is not None:
            self._driver_names_by_model[model] = str(driver or "").strip()

    def set_settings(self, settings: Any) -> None:
        self.settings = settings

    def register_searcher(self, model: Any, searcher: Any, *, driver: str = "database", searcher_key: Any = None) -> None:
        normalized = str(driver or "").strip() or "database"
        key = searcher_key if searcher_key is not None else model
        searchers = {key: self._resolve_component(searcher)}
        model_map = {model: key} if model is not None else {}
        current = self._drivers.get(normalized)
        if isinstance(current, DatabaseResourceSearchDriver):
            self.register_driver(
                normalized,
                ResourceSearchDriver(
                    name=normalized,
                    searchers=searchers,
                    searcher_keys_by_model=model_map,
                    default=normalized == "database",
                ),
                default=normalized == "database",
            )
        elif isinstance(current, ResourceSearchDriver):
            next_searchers = dict(current.searchers)
            next_searchers[key] = self._resolve_component(searcher)
            next_model_map = dict(current.searcher_keys_by_model)
            if model is not None:
                next_model_map[model] = key
            self._replace_resource_driver(current, searchers=next_searchers, searcher_keys_by_model=next_model_map)
        else:
            self.register_driver(
                normalized,
                ResourceSearchDriver(name=normalized, searchers=searchers, searcher_keys_by_model=model_map),
            )

    def register_indexer(self, model: Any, indexer: Any) -> None:
        if model is None:
            return
        self._indexers.setdefault(model, []).append(self._resolve_component(indexer))

    def register_driver_filter(
        self,
        driver: str,
        searcher_key: Any,
        definition: ResourceSearchFilter,
        *,
        replace: str | None = None,
    ) -> None:
        current = self._ensure_resource_driver(driver)
        filters = {key: list(values) for key, values in current.filters.items()}
        values = filters.setdefault(searcher_key, [])
        if replace:
            values[:] = [item for item in values if item.name != replace]
        values.append(self._resolve_filter(definition))
        self._replace_resource_driver(current, filters={key: tuple(items) for key, items in filters.items()})

    def _replace_resource_driver(
        self,
        current: ResourceSearchDriver,
        *,
        searchers: dict[Any, Any] | None = None,
        searcher_keys_by_model: dict[Any, Any] | None = None,
        filters: dict[Any, tuple[ResourceSearchFilter, ...]] | None = None,
        fulltext: dict[Any, Any] | None = None,
        mutators: dict[Any, tuple[Any, ...]] | None = None,
        indexers: dict[Any, tuple[Any, ...]] | None = None,
    ) -> None:
        replacement = ResourceSearchDriver(
            name=current.name,
            searchers=searchers if searchers is not None else current.searchers,
            searcher_keys_by_model=searcher_keys_by_model if searcher_keys_by_model is not None else current.searcher_keys_by_model,
            filters=filters if filters is not None else current.filters,
            fulltext=fulltext if fulltext is not None else current.fulltext,
            mutators=mutators if mutators is not None else current.mutators,
            indexers=indexers if indexers is not None else current.indexers,
            default=current.default,
        )
        self._drivers[current.name] = replacement
        if current.default or current.name == "database":
            self._drivers[""] = replacement

    def set_driver_fulltext(self, driver: str, searcher_key: Any, fulltext: Any) -> None:
        current = self._ensure_resource_driver(driver)
        fulltext_map = dict(current.fulltext)
        fulltext_map[searcher_key] = self._resolve_component(fulltext)
        self._replace_resource_driver(current, fulltext=fulltext_map)

    def add_driver_mutator(self, driver: str, searcher_key: Any, mutator: Any) -> None:
        current = self._ensure_resource_driver(driver)
        mutators = {key: list(values) for key, values in current.mutators.items()}
        mutators.setdefault(searcher_key, []).append(self._resolve_callback(mutator))
        self._replace_resource_driver(current, mutators={key: tuple(items) for key, items in mutators.items()})

    def register_filter(self, resource: str, definition: ResourceSearchFilter) -> None:
        normalized = str(resource or "").strip()
        if not normalized:
            return
        filters = self._filters_by_resource.setdefault(normalized, [])
        resolved = self._resolve_filter(definition)
        filters[:] = [item for item in filters if item.name != resolved.name or item.module_id != resolved.module_id]
        filters.append(resolved)

    def driver(self, name: str | None = None):
        normalized = str(name or "").strip()
        return self._drivers.get(normalized) or self._drivers.get("database")

    def driver_for(self, model: Any, *, resource: str = ""):
        return self.driver(self.driver_name_for(model, resource=resource))

    def driver_name_for(self, model: Any, *, resource: str = "") -> str:
        configured = self._setting_driver_name(model, resource=resource)
        if configured:
            return configured
        mapped_key = self._find_model_key(model, self._driver_names_by_model)
        if mapped_key is not None:
            return self._driver_names_by_model[mapped_key]
        return ""

    def default_driver(self):
        return self.driver("database")

    def query_driver_for(self, model: Any, criteria: ResourceSearchCriteria):
        configured = self.driver_for(model, resource=criteria.resource)
        default = self.default_driver()
        if getattr(criteria, "is_fulltext", False) or not self._driver_supports(default, model):
            return configured
        return default

    def searchable(self, model: Any) -> bool:
        driver = self.driver_for(model)
        default = self.default_driver()
        return self._driver_supports(driver, model) or self._driver_supports(default, model)

    def indexers(self, model: Any) -> tuple[Any, ...]:
        output = list(self._indexers.get(model, ()))
        seen_drivers = []
        for driver in (self.driver_for(model), self.default_driver()):
            if driver in seen_drivers:
                continue
            seen_drivers.append(driver)
            driver_indexers = getattr(driver, "indexers_for", None)
            if callable(driver_indexers):
                output.extend(driver_indexers(model))
        return tuple(output)

    def indexable(self, model: Any) -> bool:
        return bool(self.indexers(model))

    def index(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self._run_indexers("index", model, instance, context or {})

    def unindex(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self._run_indexers("unindex", model, instance, context or {})

    def reindex(self, model: Any, instances: Any = None, context: dict | None = None) -> None:
        for indexer in self.indexers(model):
            if hasattr(indexer, "reindex") and callable(indexer.reindex):
                indexer.reindex(instances, context or {})
            elif instances is not None:
                for instance in self._iter_instances(instances):
                    self._invoke_indexer(indexer, "index", instance, context or {})

    def filters_for(self, model: Any, *, resource: str = "") -> tuple[ResourceSearchFilter, ...]:
        output = list(self._filters_by_resource.get(str(resource or "").strip(), ()))
        driver = self.query_driver_for(model, ResourceSearchCriteria(resource=resource))
        driver_filters = getattr(driver, "filters_for", None)
        if callable(driver_filters):
            output.extend(driver_filters(model))
        return tuple(output)

    def query(self, model: Any, queryset, criteria: ResourceSearchCriteria, context: dict) -> ResourceSearchResults:
        driver = self.query_driver_for(model, criteria)
        searcher = None
        get_searcher = getattr(driver, "searcher", None)
        if callable(get_searcher):
            searcher = get_searcher(model)
        if searcher is None:
            return ResourceSearchResults(results=queryset)
        state = ResourceSearchState(queryset=queryset, criteria=criteria, context=context)
        driver_filter_manager = getattr(driver, "filter_manager_for", None)
        if callable(driver_filter_manager):
            filter_manager = driver_filter_manager(model)
            extra_filters = self._filters_by_resource.get(str(criteria.resource or "").strip(), ())
        else:
            filter_manager = ResourceFilterManager()
            extra_filters = self.filters_for(model, resource=criteria.resource)
        for definition in extra_filters:
            filter_manager.add(definition)
        state = filter_manager.apply(state, criteria.filters or {})
        for mutator in getattr(driver, "mutators_for", lambda target: ())(model):
            maybe_state = self._invoke_mutator(mutator, state, criteria, context)
            if isinstance(maybe_state, ResourceSearchState):
                state = maybe_state
            elif maybe_state is not None:
                state.queryset = maybe_state
        result = self._invoke_searcher(searcher, state.queryset, criteria, {**context, "search_state": state})
        return self.normalize_results(result)

    @staticmethod
    def normalize_results(result: Any) -> ResourceSearchResults:
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
        return ResourceSearchResults(results=result)

    @staticmethod
    def _invoke_searcher(searcher: Any, queryset, criteria: ResourceSearchCriteria, context: dict):
        if hasattr(searcher, "search") and callable(searcher.search):
            return searcher.search(queryset, criteria, context)
        if callable(searcher):
            return searcher(queryset, criteria, context)
        return queryset

    @staticmethod
    def _invoke_mutator(mutator: Any, state: ResourceSearchState, criteria: ResourceSearchCriteria, context: dict):
        if callable(mutator):
            try:
                return mutator(state, criteria)
            except TypeError:
                return mutator(state.queryset, context)
        return None

    @staticmethod
    def _driver_supports(driver: Any, model: Any) -> bool:
        supports = getattr(driver, "supports", None)
        return bool(callable(supports) and supports(model))

    def _ensure_resource_driver(self, driver: str) -> ResourceSearchDriver:
        normalized = str(driver or "").strip() or "database"
        current = self._drivers.get(normalized)
        if isinstance(current, ResourceSearchDriver):
            return current
        replacement = ResourceSearchDriver(name=normalized, default=normalized == "database")
        self._drivers[normalized] = replacement
        if replacement.default:
            self._drivers[""] = replacement
        return replacement

    def _run_indexers(self, action: str, model: Any, instance: Any, context: dict) -> None:
        for indexer in self.indexers(model):
            self._invoke_indexer(indexer, action, instance, context)

    @staticmethod
    def _invoke_indexer(indexer: Any, action: str, instance: Any, context: dict) -> None:
        handler = getattr(indexer, action, None)
        if callable(handler):
            try:
                handler(instance, context)
            except TypeError:
                handler(instance)
            return
        if callable(indexer):
            indexer(action, instance, context)

    def _resolve_component(self, value: Any) -> Any:
        return resolve_container_value(value, self.container) if isinstance(value, (str, type)) else value

    def _resolve_callback(self, value: Any) -> Any:
        return wrap_callback(value, self.container) if isinstance(value, (str, type)) else value

    def _resolve_filter(self, definition: Any) -> ResourceSearchFilter:
        resolved = self._resolve_component(definition)
        if isinstance(resolved, ResourceSearchFilter):
            handler = self._resolve_callback(resolved.handler)
            visible = self._resolve_callback(resolved.visible)
            return ResourceSearchFilter(
                name=resolved.name,
                handler=handler,
                visible=visible,
                module_id=resolved.module_id,
            )
        if hasattr(resolved, "apply") and callable(resolved.apply):
            name = str(getattr(resolved, "name", "") or getattr(resolved, "filter", "") or resolved.__class__.__name__)
            module_id = str(getattr(resolved, "module_id", "core") or "core")
            visible = getattr(resolved, "visible", True)
            return ResourceSearchFilter(
                name=name,
                handler=lambda state, value, context, target=resolved: target.apply(state, value, context),
                visible=visible,
                module_id=module_id,
            )
        raise TypeError("Search filter must be a ResourceSearchFilter-compatible object")

    @staticmethod
    def _iter_instances(instances: Any):
        if isinstance(instances, (list, tuple, set)):
            return instances
        if hasattr(instances, "__iter__") and not isinstance(instances, (str, bytes, dict)):
            return instances
        return (instances,)

    def _setting_driver_name(self, model: Any, *, resource: str = "") -> str:
        settings = self.settings
        if settings is None:
            return ""
        keys = [
            f"search_driver_{resource}" if resource else "",
            f"search_driver_{self._model_name(model)}" if model is not None else "",
        ]
        for key in keys:
            if not key:
                continue
            value = self._settings_get(settings, key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _settings_get(settings: Any, key: str) -> Any:
        if isinstance(settings, dict):
            return settings.get(key)
        getter = getattr(settings, "get", None)
        if callable(getter):
            return getter(key)
        return getattr(settings, key, "")

    @staticmethod
    def _model_name(model: Any) -> str:
        if isinstance(model, type):
            return f"{model.__module__}.{model.__name__}"
        return str(model or "")

    @staticmethod
    def _find_model_key(model: Any, values: dict[Any, Any]):
        return ResourceSearchDriver._find_model_key(model, values)

    def _driver_name_from_class(self, driver: Any) -> str:
        resolved = self._resolve_component(driver)
        name_attr = getattr(resolved, "name", "")
        if callable(name_attr):
            try:
                return str(name_attr() or "").strip() or "database"
            except TypeError:
                pass
        if name_attr:
            return str(name_attr).strip()
        if isinstance(driver, str):
            return driver.rsplit(".", 1)[-1]
        return getattr(driver, "__name__", "") or resolved.__class__.__name__


_default_search_manager = ResourceSearchManager()


def get_resource_search_manager() -> ResourceSearchManager:
    return _default_search_manager
