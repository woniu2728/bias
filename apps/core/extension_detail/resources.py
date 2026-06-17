from __future__ import annotations

from apps.core.extensions.runtime import get_runtime_resource_registry
from apps.core.forum_registry import get_forum_registry

def _build_extension_resource_definitions(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "module_id": item.module_id,
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_resources()
        if item.module_id in module_ids
    ]

def _build_extension_resource_relationships(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "relationship": item.relationship,
            "module_id": item.module_id,
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_relationships()
        if item.module_id in module_ids
    ]

def _build_extension_resource_endpoints(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "endpoint": item.endpoint,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "mutate"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_endpoints()
        if item.module_id in module_ids
    ]

def _build_extension_resource_sorts(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "sort": item.sort,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "add"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_sorts()
        if item.module_id in module_ids
    ]

def _build_extension_resource_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "resource": item.resource,
            "filter": item.filter,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "add"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_filters()
        if item.module_id in module_ids
    ]

def _build_extension_resource_fields(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    fields = [
        {
            "resource": item.resource,
            "field": item.field,
            "module_id": item.module_id,
            "operation": "add",
            "anchor": "",
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_fields()
        if item.module_id in module_ids
    ]
    fields.extend([
        {
            "resource": item.resource,
            "field": item.field,
            "module_id": item.module_id,
            "operation": getattr(item, "operation", "mutate"),
            "anchor": getattr(item, "anchor", ""),
            "description": item.description,
        }
        for item in get_runtime_resource_registry().get_all_field_mutators()
        if item.module_id in module_ids
    ])
    return fields

def _build_extension_search_drivers(runtime_view):
    if runtime_view is None:
        return []
    return [
        {
            "target": item.target,
            "driver": getattr(item.driver, "__name__", str(item.driver)),
            "filter_count": len(item.filters),
            "description": item.description,
        }
        for item in getattr(runtime_view, "search_drivers", ()) or ()
    ]

def _build_extension_search_filters(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    return [
        {
            "code": item.code,
            "label": item.label,
            "module_id": item.module_id,
            "target": item.target,
            "syntax": item.syntax,
            "description": item.description,
        }
        for item in get_forum_registry().get_search_filters()
        if item.module_id in module_ids
    ]
