from __future__ import annotations

from typing import Any

from apps.core.extensions.backend import (
    _build_admin_action_definition,
    _build_runtime_action_definition,
    _build_setting_field_definition,
)
from apps.core.extensions.contracts import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionListQueryDefinition,
    DiscussionSortDefinition,
    ExtensionAdminActionDefinition,
    ExtensionEventListenerDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionModelDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionResourceDefinition,
    ExtensionResourceEndpointDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceFieldMutatorDefinition,
    ExtensionResourceFilterDefinition,
    ExtensionResourceObjectDefinition,
    ExtensionResourceRelationshipDefinition,
    ExtensionResourceSortDefinition,
    ExtensionRuntimeActionDefinition,
    ExtensionSearchDriverDefinition,
    ExtensionSearchIndexDefinition,
    ExtensionSignalDefinition,
    LanguagePackDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    ResourceDefinition,
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourceFieldMutatorDefinition,
    ResourceFilterDefinition,
    ResourceRelationshipDefinition,
    ResourceSortDefinition,
    DatabaseResource,
    ResourceEndpoint,
    ResourceField,
    ResourceFilter,
    ResourceRelationship,
    ResourceSort,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)


def _merge_payload(payload: dict[str, Any] | None, overrides: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    data.update(overrides)
    return data


def setting_field(payload: dict[str, Any] | None = None, **overrides):
    return _build_setting_field_definition(_merge_payload(payload, overrides))


def runtime_action(payload: dict[str, Any] | None = None, **overrides):
    return _build_runtime_action_definition(_merge_payload(payload, overrides))


def admin_action(payload: dict[str, Any] | None = None, **overrides):
    return _build_admin_action_definition(_merge_payload(payload, overrides))


def event_listener(*, event_type, handler, description: str = "") -> ExtensionEventListenerDefinition:
    return ExtensionEventListenerDefinition(
        event_type=event_type,
        handler=handler,
        description=description,
    )


__all__ = [
    "AdminPageDefinition",
    "DiscussionListFilterDefinition",
    "DiscussionListQueryDefinition",
    "DiscussionSortDefinition",
    "ExtensionAdminActionDefinition",
    "ExtensionEventListenerDefinition",
    "ExtensionManifestRuntimeActionDefinition",
    "ExtensionManifestSettingFieldDefinition",
    "ExtensionModelCastDefinition",
    "ExtensionModelDefaultDefinition",
    "ExtensionModelDefinition",
    "ExtensionModelRelationDefinition",
    "ExtensionModelSlugDriverDefinition",
    "ExtensionModelVisibilityDefinition",
    "ExtensionResourceDefinition",
    "ExtensionResourceEndpointDefinition",
    "ExtensionResourceFieldDefinition",
    "ExtensionResourceFieldMutatorDefinition",
    "ExtensionResourceFilterDefinition",
    "ExtensionResourceObjectDefinition",
    "ExtensionResourceRelationshipDefinition",
    "ExtensionResourceSortDefinition",
    "ExtensionRuntimeActionDefinition",
    "ExtensionSearchDriverDefinition",
    "ExtensionSearchIndexDefinition",
    "ExtensionSignalDefinition",
    "LanguagePackDefinition",
    "NotificationTypeDefinition",
    "PermissionDefinition",
    "PostTypeDefinition",
    "ResourceDefinition",
    "DatabaseResource",
    "ResourceEndpoint",
    "ResourceEndpointDefinition",
    "ResourceField",
    "ResourceFieldDefinition",
    "ResourceFieldMutatorDefinition",
    "ResourceFilter",
    "ResourceFilterDefinition",
    "ResourceRelationship",
    "ResourceRelationshipDefinition",
    "ResourceSort",
    "ResourceSortDefinition",
    "SearchFilterDefinition",
    "UserPreferenceDefinition",
    "admin_action",
    "event_listener",
    "runtime_action",
    "setting_field",
]
