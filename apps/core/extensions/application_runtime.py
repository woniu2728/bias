from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.core.extensions.application_types import (
    ApplicationForumPermissionChecker,
    ApplicationMiddlewareMount,
    ApplicationNamedRoute,
    ApplicationPolicyMount,
    ApplicationRouteMount,
    ApplicationWebSocketRoute,
)
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionDiscussionLifecycleDefinition,
    ExtensionEventListenerDefinition,
    ExtensionFrontendRouteDefinition,
    ExtensionFormatterCallback,
    ExtensionFormatterDefinition,
    ExtensionMailDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionModelDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionPostLifecycleDefinition,
    ExtensionRealtimeDiscussionBroadcastDefinition,
    ExtensionRealtimeDiscussionTransportDefinition,
    ExtensionRealtimeIncludedDefinition,
    ExtensionResourceDefinition,
    ExtensionResourceEndpointDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceFieldMutatorDefinition,
    ExtensionResourceFilterDefinition,
    ExtensionResourceRelationshipDefinition,
    ExtensionResourceSortDefinition,
    ExtensionSearchDriverDefinition,
    ExtensionSearchIndexDefinition,
    ExtensionSettingDefaultDefinition,
    ExtensionSettingForumSerializationDefinition,
    ExtensionSettingResetDefinition,
    ExtensionSettingThemeVariableDefinition,
    ExtensionSignalDefinition,
    ExtensionSystemHookDefinition,
    ExtensionValidatorDefinition,
    ExtensionViewNamespaceDefinition,
)
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionListQueryDefinition,
    DiscussionSortDefinition,
    LanguagePackDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)


@dataclass
class ExtensionApplicationRecord:
    extension_id: str
    name: str = ""
    source: str = ""
    module_ids: list[str] = field(default_factory=list)
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    frontend_common_entry: str = ""
    frontend_css: list[str] = field(default_factory=list)
    frontend_js_directories: list[str] = field(default_factory=list)
    frontend_preloads: list[Any] = field(default_factory=list)
    frontend_content_callbacks: list[Any] = field(default_factory=list)
    frontend_document_attributes: list[Any] = field(default_factory=list)
    frontend_head_tags: list[Any] = field(default_factory=list)
    frontend_theme_variables: list[Any] = field(default_factory=list)
    frontend_title_driver: Any = None
    frontend_routes: list[ExtensionFrontendRouteDefinition] = field(default_factory=list)
    settings_pages: list[str] = field(default_factory=list)
    permissions_pages: list[str] = field(default_factory=list)
    operations_pages: list[str] = field(default_factory=list)
    settings_schema: list[ExtensionManifestSettingFieldDefinition] = field(default_factory=list)
    settings_defaults: list[ExtensionSettingDefaultDefinition] = field(default_factory=list)
    settings_reset_rules: list[ExtensionSettingResetDefinition] = field(default_factory=list)
    settings_frontend_cache_keys: list[str] = field(default_factory=list)
    settings_theme_variables: list[ExtensionSettingThemeVariableDefinition] = field(default_factory=list)
    settings_forum_serializations: list[ExtensionSettingForumSerializationDefinition] = field(default_factory=list)
    forum_settings_keys: list[str] = field(default_factory=list)
    permissions: list[PermissionDefinition] = field(default_factory=list)
    admin_pages: list[AdminPageDefinition] = field(default_factory=list)
    notification_types: list[NotificationTypeDefinition] = field(default_factory=list)
    user_preferences: list[UserPreferenceDefinition] = field(default_factory=list)
    language_packs: list[LanguagePackDefinition] = field(default_factory=list)
    post_types: list[PostTypeDefinition] = field(default_factory=list)
    search_filters: list[SearchFilterDefinition] = field(default_factory=list)
    discussion_list_queries: list[DiscussionListQueryDefinition] = field(default_factory=list)
    discussion_sorts: list[DiscussionSortDefinition] = field(default_factory=list)
    discussion_list_filters: list[DiscussionListFilterDefinition] = field(default_factory=list)
    locale_paths: list[str] = field(default_factory=list)
    view_namespaces: list[ExtensionViewNamespaceDefinition] = field(default_factory=list)
    formatter_pipeline: list[ExtensionFormatterCallback] = field(default_factory=list)
    formatter_callbacks: list[ExtensionFormatterDefinition] = field(default_factory=list)
    resource_definitions: list[ExtensionResourceDefinition] = field(default_factory=list)
    resource_fields: list[ExtensionResourceFieldDefinition] = field(default_factory=list)
    resource_field_mutators: list[ExtensionResourceFieldMutatorDefinition] = field(default_factory=list)
    resource_relationships: list[ExtensionResourceRelationshipDefinition] = field(default_factory=list)
    resource_endpoints: list[ExtensionResourceEndpointDefinition] = field(default_factory=list)
    resource_sorts: list[ExtensionResourceSortDefinition] = field(default_factory=list)
    resource_filters: list[ExtensionResourceFilterDefinition] = field(default_factory=list)
    model_definitions: list[ExtensionModelDefinition] = field(default_factory=list)
    model_visibility: list[ExtensionModelVisibilityDefinition] = field(default_factory=list)
    model_relations: list[ExtensionModelRelationDefinition] = field(default_factory=list)
    model_casts: list[ExtensionModelCastDefinition] = field(default_factory=list)
    model_defaults: list[ExtensionModelDefaultDefinition] = field(default_factory=list)
    model_slug_drivers: list[ExtensionModelSlugDriverDefinition] = field(default_factory=list)
    search_drivers: list[ExtensionSearchDriverDefinition] = field(default_factory=list)
    search_indexes: list[ExtensionSearchIndexDefinition] = field(default_factory=list)
    validators: list[ExtensionValidatorDefinition] = field(default_factory=list)
    mailers: list[ExtensionMailDefinition] = field(default_factory=list)
    error_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    auth_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    csrf_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    filesystem_drivers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    console_commands: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    session_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    theme_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    throttle_api_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    user_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    signal_handlers: list[ExtensionSignalDefinition] = field(default_factory=list)
    event_listeners: list[ExtensionEventListenerDefinition] = field(default_factory=list)
    realtime_included: list[ExtensionRealtimeIncludedDefinition] = field(default_factory=list)
    realtime_discussion_visibility: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    realtime_discussion_transports: list[ExtensionRealtimeDiscussionTransportDefinition] = field(default_factory=list)
    realtime_discussion_broadcasts: list[ExtensionRealtimeDiscussionBroadcastDefinition] = field(default_factory=list)
    forum_permission_checkers: list[ApplicationForumPermissionChecker] = field(default_factory=list)
    discussion_lifecycle: list[ExtensionDiscussionLifecycleDefinition] = field(default_factory=list)
    post_lifecycle: list[ExtensionPostLifecycleDefinition] = field(default_factory=list)
    runtime_actions: list[ExtensionManifestRuntimeActionDefinition] = field(default_factory=list)
    admin_actions: list[ExtensionAdminActionDefinition] = field(default_factory=list)
    route_mounts: list[ApplicationRouteMount] = field(default_factory=list)
    named_routes: list[ApplicationNamedRoute] = field(default_factory=list)
    websocket_routes: list[ApplicationWebSocketRoute] = field(default_factory=list)
    middleware_mounts: list[ApplicationMiddlewareMount] = field(default_factory=list)
    policy_mounts: list[ApplicationPolicyMount] = field(default_factory=list)
    service_providers: list[str] = field(default_factory=list)
    extender_keys: list[str] = field(default_factory=list)
    lifecycle_extender_keys: list[str] = field(default_factory=list)
    lifecycle_phase_keys: list[str] = field(default_factory=list)
    use_generated_settings_page: bool = False
    use_generated_permissions_page: bool = False
    use_generated_operations_page: bool = False

    @property
    def id(self) -> str:
        return self.extension_id


@dataclass
class ExtensionRuntimeView:
    extension_id: str
    name: str = ""
    source: str = ""
    path: str = ""
    module_ids: tuple[str, ...] = ()
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    frontend_common_entry: str = ""
    frontend_css: tuple[str, ...] = ()
    frontend_js_directories: tuple[str, ...] = ()
    frontend_preloads: tuple[Any, ...] = ()
    frontend_content_callbacks: tuple[Any, ...] = ()
    frontend_document_attributes: tuple[Any, ...] = ()
    frontend_head_tags: tuple[Any, ...] = ()
    frontend_theme_variables: tuple[Any, ...] = ()
    frontend_title_driver: Any = None
    frontend_routes: tuple[ExtensionFrontendRouteDefinition, ...] = ()
    settings_pages: tuple[str, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()
    settings_schema: tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    settings_defaults: tuple[ExtensionSettingDefaultDefinition, ...] = ()
    settings_reset_rules: tuple[ExtensionSettingResetDefinition, ...] = ()
    settings_frontend_cache_keys: tuple[str, ...] = ()
    settings_theme_variables: tuple[ExtensionSettingThemeVariableDefinition, ...] = ()
    settings_forum_serializations: tuple[ExtensionSettingForumSerializationDefinition, ...] = ()
    forum_settings_keys: tuple[str, ...] = ()
    permissions: tuple[PermissionDefinition, ...] = ()
    admin_pages: tuple[AdminPageDefinition, ...] = ()
    notification_types: tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()
    language_packs: tuple[LanguagePackDefinition, ...] = ()
    post_types: tuple[PostTypeDefinition, ...] = ()
    search_filters: tuple[SearchFilterDefinition, ...] = ()
    discussion_list_queries: tuple[DiscussionListQueryDefinition, ...] = ()
    discussion_sorts: tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: tuple[DiscussionListFilterDefinition, ...] = ()
    locale_paths: tuple[str, ...] = ()
    view_namespaces: tuple[ExtensionViewNamespaceDefinition, ...] = ()
    formatter_pipeline: tuple[ExtensionFormatterCallback, ...] = ()
    formatter_callbacks: tuple[ExtensionFormatterDefinition, ...] = ()
    resource_definitions: tuple[ExtensionResourceDefinition, ...] = ()
    resource_fields: tuple[ExtensionResourceFieldDefinition, ...] = ()
    resource_field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    resource_relationships: tuple[ExtensionResourceRelationshipDefinition, ...] = ()
    resource_endpoints: tuple[ExtensionResourceEndpointDefinition, ...] = ()
    resource_sorts: tuple[ExtensionResourceSortDefinition, ...] = ()
    resource_filters: tuple[ExtensionResourceFilterDefinition, ...] = ()
    model_definitions: tuple[ExtensionModelDefinition, ...] = ()
    model_visibility: tuple[ExtensionModelVisibilityDefinition, ...] = ()
    model_relations: tuple[ExtensionModelRelationDefinition, ...] = ()
    model_casts: tuple[ExtensionModelCastDefinition, ...] = ()
    model_defaults: tuple[ExtensionModelDefaultDefinition, ...] = ()
    model_slug_drivers: tuple[ExtensionModelSlugDriverDefinition, ...] = ()
    search_drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()
    search_indexes: tuple[ExtensionSearchIndexDefinition, ...] = ()
    validators: tuple[ExtensionValidatorDefinition, ...] = ()
    mailers: tuple[ExtensionMailDefinition, ...] = ()
    error_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    auth_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    csrf_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    filesystem_drivers: tuple[ExtensionSystemHookDefinition, ...] = ()
    console_commands: tuple[ExtensionSystemHookDefinition, ...] = ()
    session_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    theme_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    throttle_api_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    user_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    signal_handlers: tuple[ExtensionSignalDefinition, ...] = ()
    event_listeners: tuple[ExtensionEventListenerDefinition, ...] = ()
    realtime_included: tuple[ExtensionRealtimeIncludedDefinition, ...] = ()
    realtime_discussion_visibility: tuple[ExtensionSystemHookDefinition, ...] = ()
    realtime_discussion_transports: tuple[ExtensionRealtimeDiscussionTransportDefinition, ...] = ()
    realtime_discussion_broadcasts: tuple[ExtensionRealtimeDiscussionBroadcastDefinition, ...] = ()
    forum_permission_checkers: tuple[ApplicationForumPermissionChecker, ...] = ()
    discussion_lifecycle: tuple[ExtensionDiscussionLifecycleDefinition, ...] = ()
    post_lifecycle: tuple[ExtensionPostLifecycleDefinition, ...] = ()
    runtime_actions: tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    admin_actions: tuple[ExtensionAdminActionDefinition, ...] = ()
    route_mounts: tuple[ApplicationRouteMount, ...] = ()
    named_routes: tuple[ApplicationNamedRoute, ...] = ()
    websocket_routes: tuple[ApplicationWebSocketRoute, ...] = ()
    middleware_mounts: tuple[ApplicationMiddlewareMount, ...] = ()
    policy_mounts: tuple[ApplicationPolicyMount, ...] = ()
    service_providers: tuple[str, ...] = ()
    extender_keys: tuple[str, ...] = ()
    lifecycle_extender_keys: tuple[str, ...] = ()
    lifecycle_phase_keys: tuple[str, ...] = ()
    use_generated_settings_page: bool = False
    use_generated_permissions_page: bool = False
    use_generated_operations_page: bool = False

    @property
    def id(self) -> str:
        return self.extension_id
