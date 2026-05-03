from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


ResourceFieldResolver = Callable[[Any, dict], Any]


@dataclass(frozen=True)
class ResourceFieldDefinition:
    resource: str
    field: str
    module_id: str
    resolver: ResourceFieldResolver
    description: str = ""


class ResourceRegistry:
    def __init__(self):
        self._fields: Dict[str, List[ResourceFieldDefinition]] = {}

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

    def get_fields(self, resource: str) -> List[ResourceFieldDefinition]:
        return list(self._fields.get(resource, []))

    def get_all_fields(self) -> List[ResourceFieldDefinition]:
        definitions: List[ResourceFieldDefinition] = []
        for resource in sorted(self._fields.keys()):
            definitions.extend(self.get_fields(resource))
        return definitions

    def serialize(self, resource: str, instance: Any, context: dict | None = None) -> dict:
        payload = {}
        resolved_context = context or {}
        for definition in self.get_fields(resource):
            payload[definition.field] = definition.resolver(instance, resolved_context)
        return payload


_resource_registry: ResourceRegistry | None = None


def get_resource_registry() -> ResourceRegistry:
    global _resource_registry
    if _resource_registry is None:
        _resource_registry = ResourceRegistry()
    return _resource_registry
