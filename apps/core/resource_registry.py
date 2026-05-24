from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from django.db import OperationalError, ProgrammingError

from apps.core.models import ExtensionInstallation


ResourceFieldResolver = Callable[[Any, dict], Any]
ResourceBaseFieldResolver = Callable[[Any, dict], dict]
ResourceRelationshipResolver = Callable[[Any, dict], Any]
ResourcePreloadResolver = Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]]


@dataclass(frozen=True)
class ResourceFieldDefinition:
    resource: str
    field: str
    module_id: str
    resolver: ResourceFieldResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: ResourcePreloadResolver | None = None


@dataclass(frozen=True)
class ResourceDefinition:
    resource: str
    module_id: str
    resolver: ResourceBaseFieldResolver
    description: str = ""


@dataclass(frozen=True)
class ResourceRelationshipDefinition:
    resource: str
    relationship: str
    module_id: str
    resolver: ResourceRelationshipResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: ResourcePreloadResolver | None = None


@dataclass(frozen=True)
class ResourcePreloadPlan:
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[Any, ...] = ()


class ResourceRegistry:
    def __init__(self):
        self._definitions: Dict[str, ResourceDefinition] = {}
        self._fields: Dict[str, List[ResourceFieldDefinition]] = {}
        self._relationships: Dict[str, List[ResourceRelationshipDefinition]] = {}

    def _get_enabled_module_ids(self) -> set[str] | None:
        try:
            overrides = {
                item["extension_id"]: bool(item["enabled"])
                for item in ExtensionInstallation.objects.values("extension_id", "enabled")
            }
        except (OperationalError, ProgrammingError, RuntimeError):
            return None

        if not overrides:
            return None

        disabled_ids = {
            extension_id
            for extension_id, enabled in overrides.items()
            if not enabled
        }
        if not disabled_ids:
            return None

        enabled_ids = set(self._definitions.keys())
        enabled_ids.update(definition.module_id for definitions in self._fields.values() for definition in definitions)
        enabled_ids.update(
            definition.module_id
            for definitions in self._relationships.values()
            for definition in definitions
        )
        return enabled_ids - disabled_ids

    def _is_module_enabled(self, module_id: str, enabled_module_ids: set[str] | None) -> bool:
        if enabled_module_ids is None:
            return True
        return module_id in enabled_module_ids

    def register_resource(self, definition: ResourceDefinition) -> ResourceDefinition:
        self._definitions[definition.resource] = definition
        return definition

    def register_field(self, definition: ResourceFieldDefinition) -> ResourceFieldDefinition:
        fields = self._fields.setdefault(definition.resource, [])
        existing_index = next(
            (index for index, field in enumerate(fields) if field.field == definition.field),
            None,
        )
        if existing_index is not None:
            fields[existing_index] = definition
        else:
            fields.append(definition)
        fields.sort(key=lambda item: (item.module_id, item.field))
        return definition

    def register_relationship(self, definition: ResourceRelationshipDefinition) -> ResourceRelationshipDefinition:
        relationships = self._relationships.setdefault(definition.resource, [])
        existing_index = next(
            (
                index
                for index, relationship in enumerate(relationships)
                if relationship.relationship == definition.relationship
            ),
            None,
        )
        if existing_index is not None:
            relationships[existing_index] = definition
        else:
            relationships.append(definition)
        relationships.sort(key=lambda item: (item.module_id, item.relationship))
        return definition

    def get_resource(self, resource: str) -> ResourceDefinition | None:
        enabled_module_ids = self._get_enabled_module_ids()
        definition = self._definitions.get(resource)
        if definition is None:
            return None
        if not self._is_module_enabled(definition.module_id, enabled_module_ids):
            return None
        return definition

    def get_resources(self) -> List[ResourceDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            self._definitions[key]
            for key in sorted(self._definitions.keys())
            if self._is_module_enabled(self._definitions[key].module_id, enabled_module_ids)
        ]

    def get_fields(self, resource: str) -> List[ResourceFieldDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            definition
            for definition in self._fields.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ]

    def get_relationships(self, resource: str) -> List[ResourceRelationshipDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            definition
            for definition in self._relationships.get(resource, [])
            if self._is_module_enabled(definition.module_id, enabled_module_ids)
        ]

    def get_all_fields(self) -> List[ResourceFieldDefinition]:
        definitions: List[ResourceFieldDefinition] = []
        for resource in sorted(set(self._fields.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_fields(resource))
        return definitions

    def get_all_relationships(self) -> List[ResourceRelationshipDefinition]:
        definitions: List[ResourceRelationshipDefinition] = []
        for resource in sorted(set(self._relationships.keys()) | set(self._definitions.keys())):
            definitions.extend(self.get_relationships(resource))
        return definitions

    def build_preload_plan(
        self,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = context or {}
        select_related: list[str] = []
        prefetch_related: list[Any] = []
        seen_select: set[str] = set()
        seen_prefetch: set[str] = set()

        selected_fields = set(only or [])
        for definition in self.get_fields(resource):
            if selected_fields and definition.field not in selected_fields:
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
            )

        include_set = set(include or [])
        for definition in self.get_relationships(resource):
            if include_set and definition.relationship not in include_set:
                continue
            if not include_set and definition.relationship not in set():
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
            )

        return ResourcePreloadPlan(
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
        )

    def apply_preload_plan(
        self,
        queryset,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ):
        plan = self.build_preload_plan(
            resource,
            context,
            only=only,
            include=include,
        )
        if plan.select_related:
            queryset = queryset.select_related(*plan.select_related)
        if plan.prefetch_related:
            queryset = queryset.prefetch_related(*plan.prefetch_related)
        return queryset

    def serialize(
        self,
        resource: str,
        instance: Any,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> dict:
        resolved_context = context or {}
        payload = {}

        resource_definition = self.get_resource(resource)
        if resource_definition:
            payload.update(resource_definition.resolver(instance, resolved_context) or {})

        selected_fields = set(only or [])
        for definition in self.get_fields(resource):
            if selected_fields and definition.field not in selected_fields:
                continue
            payload[definition.field] = definition.resolver(instance, resolved_context)

        include_set = set(include or [])
        if include_set:
            for definition in self.get_relationships(resource):
                if definition.relationship not in include_set:
                    continue
                payload[definition.relationship] = definition.resolver(instance, resolved_context)
        return payload

    def _merge_preload_definition(
        self,
        definition,
        context: dict,
        select_related: list[str],
        prefetch_related: list[Any],
        seen_select: set[str],
        seen_prefetch: set[str],
    ) -> None:
        for item in getattr(definition, "select_related", ()) or ():
            if item and item not in seen_select:
                seen_select.add(item)
                select_related.append(item)

        for item in getattr(definition, "prefetch_related", ()) or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

        preload_resolver = getattr(definition, "preload_resolver", None)
        if preload_resolver is None:
            return

        extra_select, extra_prefetch = preload_resolver(context)
        for item in extra_select or ():
            if item and item not in seen_select:
                seen_select.add(item)
                select_related.append(item)

        for item in extra_prefetch or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

    @staticmethod
    def _prefetch_key(item: Any) -> str:
        if isinstance(item, str):
            return item
        lookup = getattr(item, "prefetch_to", None) or getattr(item, "lookup", None)
        if lookup:
            return str(lookup)
        return repr(item)


_resource_registry: ResourceRegistry | None = None


def get_resource_registry() -> ResourceRegistry:
    global _resource_registry
    if _resource_registry is None:
        _resource_registry = ResourceRegistry()
    return _resource_registry
