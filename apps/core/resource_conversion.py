"""
Resource → Definition 转换函数。

将资源对象（Field/Relationship/Endpoint/Sort/Filter）转换为其对应的
定义对象（Definition），供 ResourceRegistry 使用。
"""

from __future__ import annotations

from apps.core.resource_definitions import (
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourceFilterDefinition,
    ResourceRelationshipDefinition,
    ResourceSortDefinition,
)
from apps.core.resource_objects import (
    ResourceEndpoint,
    ResourceField,
    ResourceFilter,
    ResourceRelationship,
    ResourceSort,
)


def field_to_definition(resource: str, field: ResourceField) -> ResourceFieldDefinition:
    """将 ResourceField 转换为 ResourceFieldDefinition。"""
    return ResourceFieldDefinition(
        resource=resource,
        field=field.name,
        module_id=field.module_id,
        resolver=lambda instance, context, field_object=field: field_object.resolve(instance, context),
        description=field.description,
        select_related=field.select_related,
        prefetch_related=field.prefetch_related,
        preload_resolver=field.preload_resolver,
        annotate_resolver=getattr(field, "annotate_resolver", None),
        visible=field.visible,
        writable=field.writable,
        required_on_create=field.required_on_create,
        required_on_update=field.required_on_update,
        nullable=field.nullable,
        value_type=field.value_type,
        validation_rules=field.validation_rules,
        has_validation_rules=field.has_validation_rules,
        setter=field.setter,
        validator=field.validator,
        field_object=field,
    )


def relationship_to_definition(resource: str, relationship: ResourceRelationship) -> ResourceRelationshipDefinition:
    """将 ResourceRelationship 转换为 ResourceRelationshipDefinition。"""
    return ResourceRelationshipDefinition(
        resource=resource,
        relationship=relationship.name,
        module_id=relationship.module_id,
        resolver=lambda instance, context, relationship_object=relationship: relationship_object.resolve(instance, context),
        description=relationship.description,
        select_related=relationship.select_related,
        prefetch_related=relationship.prefetch_related,
        preload_resolver=relationship.preload_resolver,
        visible=relationship.visible,
        includable=relationship.includable,
        resource_type=relationship.resource_type,
        many=relationship.many,
        inverse=relationship.inverse,
        setter=relationship.relationship_setter or relationship.setter,
        writable=relationship.writable,
        linkage=relationship.linkage,
        required_on_create=relationship.required_on_create,
        required_on_update=relationship.required_on_update,
        nullable=relationship.nullable,
        value_type=relationship.value_type,
        validation_rules=relationship.validation_rules,
        has_validation_rules=relationship.has_validation_rules,
        validator=relationship.validator,
        field_object=relationship,
    )


def endpoint_to_definition(resource: str, endpoint: ResourceEndpoint) -> ResourceEndpointDefinition:
    """将 ResourceEndpoint 转换为 ResourceEndpointDefinition。"""
    return ResourceEndpointDefinition(
        resource=resource,
        endpoint=endpoint.name,
        module_id=endpoint.module_id,
        description=endpoint.description,
        operation="add",
        handler=endpoint.handler,
        methods=endpoint.methods,
        path=endpoint.path,
        absolute_path=endpoint.absolute_path,
        auth_required=endpoint.auth_required,
        permission=endpoint.permission,
        default_include=endpoint.default_include,
        eager_load=endpoint.eager_load,
        eager_load_when_included_rules=endpoint.eager_load_when_included_rules,
        eager_load_where_rules=endpoint.eager_load_where_rules,
        default_sort=endpoint.default_sort,
        paginate=endpoint.paginate,
        pagination_default_limit=endpoint.pagination_default_limit,
        pagination_max_limit=endpoint.pagination_max_limit,
        kind=endpoint.kind,
        ability=endpoint.ability,
        forum_permission=endpoint.forum_permission,
        before_hook=endpoint.before_hook,
        after_hook=endpoint.after_hook,
        meta_resolver=endpoint.meta_resolver,
        links_resolver=endpoint.links_resolver,
        query_callback=endpoint.query_callback,
        action_callback=endpoint.action_callback,
        before_serialization_callback=endpoint.before_serialization_callback,
        response_callback=endpoint.response_callback,
    )


def sort_to_definition(resource: str, sort: ResourceSort) -> ResourceSortDefinition:
    """将 ResourceSort 转换为 ResourceSortDefinition。"""
    return ResourceSortDefinition(
        resource=resource,
        sort=sort.name,
        module_id=sort.module_id,
        handler=sort.handler,
        description=sort.description,
    )


def filter_to_definition(resource: str, filter_object: ResourceFilter) -> ResourceFilterDefinition:
    """将 ResourceFilter 转换为 ResourceFilterDefinition。"""
    return ResourceFilterDefinition(
        resource=resource,
        filter=filter_object.name,
        module_id=filter_object.module_id,
        handler=lambda queryset, value, context, target=filter_object: target.apply(queryset, value, context),
        description=filter_object.description,
        visible=filter_object.visible,
    )
