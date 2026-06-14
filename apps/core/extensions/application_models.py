from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apps.core.extensions.container import resolve_container_value
from apps.core.extensions.model_references import model_class, model_matches, resolve_model_reference
from apps.core.extensions.types import (
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionModelDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost


@dataclass
class ApplicationModelExtension:
    extension_id: str
    definition: ExtensionModelDefinition


class ApplicationModelRelationDescriptor:
    def __init__(self, definition: ExtensionModelRelationDefinition) -> None:
        self.definition = definition

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return self.definition.resolver(instance)


class ApplicationModelService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionModelDefinition, ...]] = {}
        self._visibility_by_extension: dict[str, tuple[ExtensionModelVisibilityDefinition, ...]] = {}
        self._relations_by_extension: dict[str, tuple[ExtensionModelRelationDefinition, ...]] = {}
        self._casts_by_extension: dict[str, tuple[ExtensionModelCastDefinition, ...]] = {}
        self._defaults_by_extension: dict[str, tuple[ExtensionModelDefaultDefinition, ...]] = {}
        self._private_checkers_by_extension: dict[str, tuple[ExtensionModelDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionModelDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_definitions = definitions

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        if extension_id is not None:
            return list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelDefinition] = []
        for items in self._definitions_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_definitions_for_model(self, model: Any, *, kind: str | None = None) -> list[ExtensionModelDefinition]:
        definitions = [
            definition
            for definition in self.get_definitions()
            if self._model_matches(definition.model, model)
        ]
        if kind is not None:
            definitions = [definition for definition in definitions if definition.kind == kind]
        return definitions

    def get_owned_models(self, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        return [
            definition
            for definition in self.get_definitions(extension_id=extension_id)
            if definition.kind == "owner"
        ]

    def get_model_owner(self, model: Any) -> str:
        owners = [
            extension_id
            for extension_id, definitions in self._definitions_by_extension.items()
            for definition in definitions
            if definition.kind == "owner" and self._model_matches(definition.model, model)
        ]
        return owners[-1] if owners else ""

    def register_visibility(self, extension_id: str, definition: ExtensionModelVisibilityDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._visibility_by_extension.get(normalized, ()), definition])
        self._visibility_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_visibility = definitions

    def get_visibility(self, *, extension_id: str | None = None) -> list[ExtensionModelVisibilityDefinition]:
        if extension_id is not None:
            return list(self._visibility_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelVisibilityDefinition] = []
        for items in self._visibility_by_extension.values():
            definitions.extend(items)
        return definitions

    def has_visibility(self, model: Any, *, ability: str | None = None) -> bool:
        return any(
            True
            for _definition in self._get_visibility_for_model(model, ability=ability)
        )

    def apply_visibility(self, model: Any, queryset, context: dict | None = None):
        output = queryset
        resolved_context = dict(context or {})
        requested_ability = str(resolved_context.get("ability") or "view")
        for definition in self._get_visibility_for_model(model, ability=requested_ability):
            output = definition.scope(output, resolved_context)
        return output

    def _get_visibility_for_model(self, model: Any, *, ability: str | None = None) -> list[ExtensionModelVisibilityDefinition]:
        requested_ability = str(ability or "view")
        definitions = []
        for sequence, definition in enumerate(self.get_visibility()):
            if not self._model_matches(definition.model, model):
                continue
            definition_ability = str(definition.ability or "*")
            if definition_ability not in {"*", requested_ability}:
                continue
            definitions.append((self._visibility_sort_key(definition, model, requested_ability, sequence), definition))
        return [definition for _key, definition in sorted(definitions, key=lambda item: item[0])]

    def _visibility_sort_key(
        self,
        definition: ExtensionModelVisibilityDefinition,
        model: Any,
        requested_ability: str,
        sequence: int,
    ) -> tuple[int, int, int, int]:
        lineage = self._model_lineage(model)
        registered_class = self._model_class(definition.model)
        try:
            lineage_index = lineage.index(registered_class) if registered_class in lineage else len(lineage)
        except ValueError:
            lineage_index = len(lineage)
        ability = str(definition.ability or "*")
        ability_index = 0 if ability == "*" else 1
        return (lineage_index, ability_index, int(getattr(definition, "order", 100) or 100), sequence)

    def _model_matches(self, registered_model: Any, model: Any) -> bool:
        return model_matches(registered_model, model, self._host)

    def _model_class(self, model: Any) -> type | None:
        return model_class(model, self._host)

    def _model_lineage(self, model: Any) -> list[type]:
        resolved_model_class = self._model_class(model)
        if resolved_model_class is None:
            return []
        return [item for item in reversed(resolved_model_class.__mro__) if item is not object]

    def register_relation(self, extension_id: str, definition: ExtensionModelRelationDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._relations_by_extension.get(normalized, ()), definition])
        self._relations_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_relations = definitions
        self._install_relation_descriptor(definition)

    def get_relations(self, *, extension_id: str | None = None) -> list[ExtensionModelRelationDefinition]:
        if extension_id is not None:
            return list(self._relations_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelRelationDefinition] = []
        for items in self._relations_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_relations_for_model(self, model: Any) -> list[ExtensionModelRelationDefinition]:
        return [
            definition
            for definition in self.get_relations()
            if self._model_matches(definition.model, model)
        ]

    def get_relation(self, model: Any, name: str) -> ExtensionModelRelationDefinition | None:
        normalized = str(name or "").strip()
        if not normalized:
            return None
        for definition in self.get_relations_for_model(model):
            if definition.name == normalized:
                return definition
        return None

    def resolve_relation(self, model: Any, name: str, instance: Any):
        definition = self.get_relation(model, name)
        if definition is None:
            return None
        return definition.resolver(instance)

    def _install_relation_descriptor(self, definition: ExtensionModelRelationDefinition) -> None:
        if not bool(getattr(definition, "inject_attribute", True)):
            return
        model_class = self._model_class(definition.model)
        relation_name = str(definition.name or "").strip()
        if model_class is None or not relation_name:
            return
        existing = getattr(model_class, relation_name, None)
        if existing is not None and not isinstance(existing, ApplicationModelRelationDescriptor):
            return
        setattr(model_class, relation_name, ApplicationModelRelationDescriptor(definition))

    def register_cast(self, extension_id: str, definition: ExtensionModelCastDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._casts_by_extension.get(normalized, ()), definition])
        self._casts_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_casts = definitions

    def get_casts(self, *, extension_id: str | None = None) -> list[ExtensionModelCastDefinition]:
        if extension_id is not None:
            return list(self._casts_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelCastDefinition] = []
        for items in self._casts_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_casts_for_model(self, model: Any) -> dict[str, Any]:
        casts: dict[str, Any] = {}
        for definition in self.get_casts():
            if self._model_matches(definition.model, model):
                casts[definition.attribute] = definition.cast
        return casts

    def register_default(self, extension_id: str, definition: ExtensionModelDefaultDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._defaults_by_extension.get(normalized, ()), definition])
        self._defaults_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_defaults = definitions

    def get_defaults(self, *, extension_id: str | None = None) -> list[ExtensionModelDefaultDefinition]:
        if extension_id is not None:
            return list(self._defaults_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelDefaultDefinition] = []
        for items in self._defaults_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_defaults_for_model(self, model: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for definition in self.get_defaults():
            if not self._model_matches(definition.model, model):
                continue
            value = definition.value
            defaults[definition.attribute] = value() if callable(value) else value
        return defaults

    def register_private_checker(self, extension_id: str, definition: ExtensionModelDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._private_checkers_by_extension.get(normalized, ()), definition])
        self._private_checkers_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_definitions = tuple([*view.model_definitions, definition])
        self._ensure_private_save_hook(definition.model)

    def get_private_checkers(self, model: Any | None = None, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        if extension_id is not None:
            definitions = list(self._private_checkers_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._private_checkers_by_extension.values():
                definitions.extend(items)
        if model is not None:
            definitions = [definition for definition in definitions if self._model_matches(definition.model, model)]
        return definitions

    def is_private(self, model: Any, instance: Any, *, default: bool = False) -> bool:
        result = bool(default)
        for definition in self.get_private_checkers(model):
            checker = definition.handler
            if not callable(checker):
                continue
            checked = checker(instance)
            if checked is True:
                return True
            if checked is False:
                result = False
        return result

    def _ensure_private_save_hook(self, model: Any) -> None:
        resolved_model = resolve_model_reference(model, self._host)
        if resolved_model is None or not hasattr(resolved_model, "_meta"):
            return
        from django.db.models.signals import pre_save

        model_label = f"{getattr(resolved_model, '__module__', '')}.{getattr(resolved_model, '__qualname__', getattr(resolved_model, '__name__', ''))}"

        def refresh_private_flag(sender, instance, **kwargs):
            if instance is None or not hasattr(instance, "is_private"):
                return
            from apps.core.extensions.runtime import is_runtime_model_private

            instance.is_private = is_runtime_model_private(instance, model=sender, default=False)

        pre_save.connect(
            refresh_private_flag,
            sender=resolved_model,
            weak=False,
            dispatch_uid=f"bias.model_private.pre_save.{model_label}",
        )


class ApplicationModelUrlService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._slug_drivers_by_extension: dict[str, tuple[ExtensionModelSlugDriverDefinition, ...]] = {}

    def register_slug_driver(self, extension_id: str, definition: ExtensionModelSlugDriverDefinition) -> None:
        normalized = str(extension_id or "").strip()
        identifier = str(getattr(definition, "identifier", "") or "").strip()
        if not normalized or not identifier or getattr(definition, "model", None) is None:
            return
        definitions = tuple([
            *(
                item
                for item in self._slug_drivers_by_extension.get(normalized, ())
                if not (
                    item.model == definition.model
                    and str(item.identifier or "").strip() == identifier
                )
            ),
            definition,
        ])
        self._slug_drivers_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_slug_drivers = definitions

    def get_slug_drivers(self, model: Any | None = None, *, extension_id: str | None = None) -> list[ExtensionModelSlugDriverDefinition]:
        if extension_id is not None:
            definitions = list(self._slug_drivers_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._slug_drivers_by_extension.values():
                definitions.extend(items)
        if model is not None:
            definitions = [definition for definition in definitions if definition.model == model]
        return definitions

    def get_slug_driver(self, model: Any, identifier: str = "default") -> ExtensionModelSlugDriverDefinition | None:
        normalized_identifier = str(identifier or "default").strip() or "default"
        for definition in reversed(self.get_slug_drivers(model)):
            if str(definition.identifier or "").strip() == normalized_identifier:
                return definition
        return None

    def generate_slug(
        self,
        model: Any,
        source: Any,
        *,
        identifier: str = "default",
        explicit_slug: str = "",
        exclude_id: int | None = None,
        context: dict | None = None,
    ) -> str:
        definition = self.get_slug_driver(model, identifier)
        if definition is None:
            raise KeyError(f"slug driver not registered: {model}.{identifier}")

        resolved_context = {
            **dict(context or {}),
            "model": model,
            "identifier": str(identifier or "default").strip() or "default",
            "field": definition.field,
            "source_field": definition.source_field,
            "exclude_id": exclude_id,
        }
        driver = resolve_container_value(definition.driver, self._host)
        base_slug = self._invoke_slug_driver(driver, source, explicit_slug, resolved_context)
        return self._unique_slug(
            model,
            base_slug,
            field=definition.field,
            exclude_id=exclude_id,
            max_length=definition.max_length,
        )

    @staticmethod
    def _invoke_slug_driver(driver: Any, source: Any, explicit_slug: str, context: dict) -> str:
        if hasattr(driver, "generate"):
            return str(driver.generate(source, explicit_slug=explicit_slug, context=context) or "").strip()
        if callable(driver):
            try:
                return str(driver(source, explicit_slug=explicit_slug, context=context) or "").strip()
            except TypeError:
                try:
                    return str(driver(source, explicit_slug) or "").strip()
                except TypeError:
                    return str(driver(source) or "").strip()
        return str(explicit_slug or source or "").strip()

    @staticmethod
    def _unique_slug(
        model: Any,
        slug: str,
        *,
        field: str = "slug",
        exclude_id: int | None = None,
        max_length: int | None = None,
    ) -> str:
        import uuid

        normalized = str(slug or "").strip() or str(uuid.uuid4())[:8]
        if max_length is not None and max_length > 0:
            normalized = normalized[:max_length].strip("-_ ") or str(uuid.uuid4())[:8]

        original = normalized
        counter = 1
        manager = getattr(model, "objects", None)
        if manager is None:
            return normalized

        while True:
            queryset = manager.filter(**{field: normalized})
            if exclude_id is not None:
                queryset = queryset.exclude(id=exclude_id)
            if not queryset.exists():
                return normalized
            counter += 1
            suffix = f"-{counter}"
            if max_length is not None and max_length > 0:
                base = original[: max(1, max_length - len(suffix))].rstrip("-_ ")
                normalized = f"{base}{suffix}"
            else:
                normalized = f"{original}{suffix}"
