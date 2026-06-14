from __future__ import annotations

from typing import Any, Callable

from apps.core.extensions.container import wrap_callback
from apps.core.resource_objects import ResourceEndpoint, ResourceField, ResourceFilter, ResourceRelationship, ResourceSort
from apps.core.resource_registry import ResourceRegistry


def normalize_names(names) -> tuple[str, ...]:
    if isinstance(names, str):
        return (names,)
    return tuple(names)


def resolve_definition_groups(items: tuple[Any, ...], host) -> tuple[Any, ...]:
    output = []
    for item in items:
        if isinstance(item, (str, type)):
            item = wrap_callback(item, host)
        if callable(item) and not hasattr(item, "resource"):
            item = item()
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            output.extend(item)
        else:
            output.append(item)
    return tuple(output)


def normalize_resource_fields(resource_name: str, items: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        ResourceRegistry._field_to_definition(resource_name, item)
        if isinstance(item, ResourceField) and not isinstance(item, ResourceRelationship)
        else item
        for item in items
    )


def normalize_resource_relationships(resource_name: str, items: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        ResourceRegistry._relationship_to_definition(resource_name, item)
        if isinstance(item, ResourceRelationship)
        else item
        for item in items
    )


def normalize_resource_endpoints(resource_name: str, items: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        ResourceRegistry._endpoint_to_definition(resource_name, item)
        if isinstance(item, ResourceEndpoint)
        else item
        for item in items
    )


def normalize_resource_sorts(resource_name: str, items: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        ResourceRegistry._sort_to_definition(resource_name, item)
        if isinstance(item, ResourceSort)
        else item
        for item in items
    )


def normalize_resource_filters(resource_name: str, items: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        ResourceRegistry._filter_to_definition(resource_name, item)
        if isinstance(item, ResourceFilter)
        else item
        for item in items
    )


def evaluate_conditional_extender_condition(
    condition: Callable[[Any], bool] | bool | str | type,
    host,
) -> bool:
    if isinstance(condition, bool):
        return condition
    resolved = wrap_callback(condition, host) if isinstance(condition, (str, type)) else condition
    if not callable(resolved):
        return bool(resolved)
    try:
        return bool(resolved(host))
    except TypeError:
        return bool(resolved())


def resolve_conditional_extenders(callback: Callable[[], Any] | str | type, host):
    resolved = wrap_callback(callback, host) if isinstance(callback, (str, type)) else callback
    if not callable(resolved):
        return resolved
    try:
        return resolved()
    except TypeError:
        return resolved(host)
