from __future__ import annotations

from apps.core.extensions import (
    ResourceDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
)
from apps.core.extensions.runtime import serialize_runtime_user


EXTENSION_ID = "notifications"


def notification_resource_definitions():
    return (notification_resource_definition(),)


def notification_resource_definition():
    return ResourceDefinition(
        resource="notification",
        module_id=EXTENSION_ID,
        resolver=serialize_notification_base,
        description="论坛通知主资源。",
    )


def notification_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="notification",
            field="from_user",
            module_id=EXTENSION_ID,
            resolver=resolve_notification_from_user,
            description="通知来源用户摘要。",
            select_related=("from_user",),
            prefetch_related=("from_user__user_groups",),
        ),
    )


def notification_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="notification",
            relationship="from_user",
            module_id=EXTENSION_ID,
            resolver=resolve_notification_from_user,
            description="通知来源用户摘要。",
            select_related=("from_user",),
            prefetch_related=("from_user__user_groups",),
        ),
    )


def serialize_notification_base(notification, context: dict) -> dict:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": notification.type,
        "subject_type": notification.subject_type,
        "subject_id": notification.subject_id,
        "data": notification.data,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }


def resolve_notification_from_user(notification, context: dict) -> dict | None:
    return serialize_runtime_user(getattr(notification, "from_user", None), resource="user_summary", context=context)

