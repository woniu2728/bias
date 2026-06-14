from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable

from apps.core.extensions.container import resolve_container_value, wrap_callback
from apps.core.extensions.types import (
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionModelDefinition,
    ExtensionModelReference,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionSearchDriverDefinition,
    ExtensionSearchIndexDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


@dataclass(frozen=True)
class ModelExtender:
    definitions: tuple[ExtensionModelDefinition, ...] = ()
    visibility: tuple[ExtensionModelVisibilityDefinition, ...] = ()
    relations: tuple[ExtensionModelRelationDefinition, ...] = ()
    casts: tuple[ExtensionModelCastDefinition, ...] = ()
    defaults: tuple[ExtensionModelDefaultDefinition, ...] = ()
    model: Any = None

    def owns(
        self,
        model: Any = None,
        *,
        key: str = "",
        description: str = "",
    ) -> "ModelExtender":
        resolved_model = model or self.model
        if resolved_model is None:
            raise ValueError("ModelExtender ownership requires a model")
        owner_key = str(key or "").strip() or _model_definition_key(resolved_model)
        return ModelExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionModelDefinition(
                    model=resolved_model,
                    key=owner_key,
                    handler=resolved_model,
                    kind="owner",
                    description=str(description or "").strip(),
                ),
            ]),
            visibility=self.visibility,
            relations=self.relations,
            casts=self.casts,
            defaults=self.defaults,
            model=self.model,
        )

    def relationship(self, *definitions: ExtensionModelRelationDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=tuple([*self.relations, *definitions]),
            casts=self.casts,
            defaults=self.defaults,
            model=self.model,
        )

    def belongs_to(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "belongsTo",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=owner_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def belongs_to_many(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "belongsToMany",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=owner_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def has_one(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        local_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "hasOne",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=local_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def has_many(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        local_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "hasMany",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=local_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def cast(self, *definitions: ExtensionModelCastDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=self.relations,
            casts=tuple([*self.casts, *definitions]),
            defaults=self.defaults,
            model=self.model,
        )

    def default(self, *definitions: ExtensionModelDefaultDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=self.relations,
            casts=self.casts,
            defaults=tuple([*self.defaults, *definitions]),
            model=self.model,
        )

    def _simple_relation(
        self,
        relation_type: str,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        source_model = model or self.model
        if source_model is None:
            raise ValueError("ModelExtender simple relations require a source model")
        relation_resolver = resolver or (lambda instance: getattr(instance, name, None))
        return self.relationship(
            ExtensionModelRelationDefinition(
                model=source_model,
                name=name,
                resolver=relation_resolver,
                relation_type=relation_type,
                related_model=related_model,
                foreign_key=foreign_key,
                owner_key=owner_key,
                description=description,
                inject_attribute=inject_attribute,
            )
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.definitions or self.visibility or self.relations or self.casts or self.defaults):
            return

        extension_id = extension.extension_id

        def apply(models, host: "ExtensionHost"):
            for definition in self.definitions:
                models.register(extension_id, definition)
            for definition in self.visibility:
                models.register_visibility(extension_id, definition)
            for definition in self.relations:
                models.register_relation(extension_id, definition)
            for definition in self.casts:
                models.register_cast(extension_id, definition)
            for definition in self.defaults:
                models.register_default(extension_id, definition)
            return models

        app.resolving("models", apply)


def RuntimeModel(service_key: str, attribute: str = "model", *, description: str = "") -> ExtensionModelReference:
    return ExtensionModelReference(
        service_key=str(service_key or "").strip(),
        attribute=str(attribute or "model").strip() or "model",
        description=str(description or "").strip(),
    )


@dataclass(frozen=True)
class ModelVisibilityExtender:
    definitions: tuple[ExtensionModelVisibilityDefinition, ...] = ()

    def scope(
        self,
        model: Any,
        callback: Callable[[Any, dict], Any],
        *,
        ability: str = "view",
        description: str = "",
        order: int = 100,
    ) -> "ModelVisibilityExtender":
        if model is None or callback is None:
            return self
        return ModelVisibilityExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionModelVisibilityDefinition(
                    model=model,
                    scope=callback,
                    ability=str(ability or "view"),
                    description=str(description or "").strip(),
                    order=int(order or 100),
                ),
            ])
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        ModelExtender(visibility=self.definitions).extend(app, extension)


@dataclass(frozen=True)
class ModelPrivateExtender:
    model: Any
    checkers: tuple[Any, ...] = ()

    def checker(self, callback: Any) -> "ModelPrivateExtender":
        if callback is None:
            return self
        return ModelPrivateExtender(
            model=self.model,
            checkers=tuple([*self.checkers, callback]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if self.model is None or not self.checkers:
            return
        extension_id = extension.extension_id

        def apply(models, host: "ExtensionHost"):
            for index, checker in enumerate(self.checkers):
                models.register_private_checker(extension_id, ExtensionModelDefinition(
                    model=self.model,
                    key=f"private_checker:{index}",
                    handler=wrap_callback(checker, host),
                    kind="private_checker",
                    description="Model privacy checker",
                ))
            return models

        app.resolving("models", apply)


def _model_definition_key(model: Any) -> str:
    meta = getattr(model, "_meta", None)
    label = str(getattr(meta, "label_lower", "") or "").strip()
    if label:
        return label
    module = str(getattr(model, "__module__", "") or "").strip()
    name = str(getattr(model, "__name__", "") or getattr(model, "__qualname__", "") or "").strip()
    return ".".join(item for item in (module, name) if item) or str(model)


@dataclass(frozen=True)
class ModelUrlExtender:
    model: Any
    slug_drivers: tuple[ExtensionModelSlugDriverDefinition, ...] = ()

    def add_slug_driver(
        self,
        identifier: str,
        driver: Any,
        *,
        field: str = "slug",
        source_field: str = "name",
        max_length: int | None = None,
        description: str = "",
    ) -> "ModelUrlExtender":
        return ModelUrlExtender(
            model=self.model,
            slug_drivers=tuple([
                *self.slug_drivers,
                ExtensionModelSlugDriverDefinition(
                    model=self.model,
                    identifier=str(identifier or "").strip() or "default",
                    driver=driver,
                    field=str(field or "slug").strip() or "slug",
                    source_field=str(source_field or "name").strip() or "name",
                    max_length=max_length,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.slug_drivers:
            return

        extension_id = extension.extension_id

        def apply(model_urls, host: "ExtensionHost"):
            for definition in self.slug_drivers:
                model_urls.register_slug_driver(extension_id, definition)
            return model_urls

        app.resolving("model.urls", apply)


@dataclass(frozen=True)
class SearchDriverExtender:
    driver: Any = "database"
    drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()

    def __init__(self, driver: Any = "database", drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()) -> None:
        object.__setattr__(self, "driver", driver)
        object.__setattr__(self, "drivers", tuple(drivers or ()))

    def add_searcher(self, model: Any, searcher: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(model),
            driver=self.driver,
            model=model,
            searcher=searcher,
        ))

    def add_filter(self, searcher: Any, filter_definition: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            driver_filters=(filter_definition,),
        ))

    def replace_filter(self, searcher: Any, replace: str, filter_definition: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            replace_filters=((replace, filter_definition),),
        ))

    def set_fulltext(self, searcher: Any, fulltext: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            fulltext=fulltext,
        ))

    def add_mutator(self, searcher: Any, callback: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            driver_mutators=(callback,),
        ))

    def add_indexer(self, model: Any, indexer: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(model),
            driver=self.driver,
            model=model,
            indexers=(indexer,),
        ))

    def _append_definition(self, definition: ExtensionSearchDriverDefinition) -> "SearchDriverExtender":
        return SearchDriverExtender(driver=self.driver, drivers=tuple([*self.drivers, definition]))

    @staticmethod
    def _target_from_model(model: Any) -> str:
        name = getattr(model, "__name__", "") if model is not None else ""
        return str(name or "").strip()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.drivers:
            return

        extension_id = extension.extension_id

        def apply(search, host: "ExtensionHost"):
            for definition in self.drivers:
                search.register_driver(extension_id, definition)
            return search

        app.resolving("search", apply)


@dataclass(frozen=True)
class SearchIndexExtender:
    indexers: tuple[tuple[Any, Any], ...] = ()
    indexes: tuple[ExtensionSearchIndexDefinition, ...] = ()

    def indexer(self, model: Any, indexer: Any) -> "SearchIndexExtender":
        if model is None or indexer is None:
            return self
        return SearchIndexExtender(
            indexers=tuple([*self.indexers, (model, indexer)]),
            indexes=self.indexes,
        )

    def postgres_index(
        self,
        name: str,
        *,
        drop: str,
        create: str | Callable[[], str],
        description: str = "",
    ) -> "SearchIndexExtender":
        normalized = str(name or "").strip()
        if not normalized:
            return self
        return SearchIndexExtender(
            indexers=self.indexers,
            indexes=tuple([*self.indexes, ExtensionSearchIndexDefinition(
                name=normalized,
                drop=str(drop or "").strip(),
                create=create,
                description=str(description or "").strip(),
            )]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.indexers and not self.indexes:
            return
        extension_id = extension.extension_id

        def apply(search, host: "ExtensionHost"):
            view = host._get_or_create_runtime_view(extension_id)
            for model, indexer in self.indexers:
                search.register_indexer(model, indexer)
                view.search_drivers = tuple([*view.search_drivers, ExtensionSearchDriverDefinition(
                    target=str(getattr(model, "__name__", "") or "").strip(),
                    driver="database",
                    model=model,
                    indexers=(indexer,),
                )])
            for definition in self.indexes:
                search.register_index_definition(extension_id, definition)
            return search

        app.resolving("search", apply)
