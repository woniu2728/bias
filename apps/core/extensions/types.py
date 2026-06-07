from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Type, Tuple

from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionSortDefinition,
    LanguagePackDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)


@dataclass(frozen=True)
class ExtensionAdminActionDefinition:
    key: str
    label: str
    kind: str = "route"
    target: str = ""
    icon: str = ""
    tone: str = "default"
    opens_in_new_tab: bool = False
    requires_enabled: bool = False
    description: str = ""
    order: int = 100


@dataclass(frozen=True)
class ExtensionRuntimeActionDefinition:
    key: str
    label: str
    action: str
    tone: str = "default"
    confirm_title: str = ""
    confirm_message: str = ""
    confirm_text: str = ""
    success_message: str = ""
    requires_enabled: bool = False
    requires_installed: bool = False
    order: int = 100


@dataclass(frozen=True)
class ExtensionFrontendRouteDefinition:
    path: str
    name: str
    component: str
    frontend: str = "forum"
    module_id: str = ""
    title: str = ""
    description: str = ""
    preloads: Tuple[Any, ...] = ()
    document_attributes: Tuple[Any, ...] = ()
    head_tags: Tuple[Any, ...] = ()
    requires_auth: bool = False
    order: int = 100
    removed: bool = False


@dataclass(frozen=True)
class ExtensionManifestRuntimeActionDefinition:
    key: str
    label: str
    hook: str
    tone: str = "default"
    confirm_title: str = ""
    confirm_message: str = ""
    confirm_text: str = ""
    success_message: str = ""
    requires_enabled: bool = False
    requires_installed: bool = False
    description: str = ""
    order: int = 100


@dataclass(frozen=True)
class ExtensionManifestSettingOptionDefinition:
    value: str
    label: str


@dataclass(frozen=True)
class ExtensionManifestSettingFieldDefinition:
    key: str
    label: str
    type: str = "text"
    default: Any = ""
    help_text: str = ""
    placeholder: str = ""
    required: bool = False
    options: Tuple[ExtensionManifestSettingOptionDefinition, ...] = ()
    multiline: bool = False
    order: int = 100


ExtensionFormatterCallback = Callable[[str], str]


@dataclass(frozen=True)
class ExtensionFormatterDefinition:
    phase: str
    callback: Callable[..., Any]
    module_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class ExtensionSettingDefaultDefinition:
    key: str
    value: Any
    module_id: str = ""


@dataclass(frozen=True)
class ExtensionSettingResetDefinition:
    key: str
    callback: Callable[[Any], bool]
    module_id: str = ""


@dataclass(frozen=True)
class ExtensionSettingThemeVariableDefinition:
    name: str
    key: str
    callback: Callable[[Any], Any] | None = None
    module_id: str = ""


@dataclass(frozen=True)
class ExtensionSettingForumSerializationDefinition:
    attribute: str
    key: str
    callback: Callable[[Any], Any] | None = None
    module_id: str = ""


ExtensionResourceBaseResolver = Callable[[Any, dict], dict]
ExtensionResourceFieldResolver = Callable[[Any, dict], Any]
ExtensionResourceRelationshipResolver = Callable[[Any, dict], Any]
ExtensionDomainEventHandler = Callable[[Any], None]


@dataclass(frozen=True)
class ExtensionValidatorDefinition:
    key: str
    target: str
    callback: Callable[[Any, dict], Any]
    module_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class ExtensionMailDefinition:
    key: str
    callback: Callable[[Any, dict], Any]
    module_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class ExtensionViewNamespaceDefinition:
    namespace: str
    hints: Tuple[str, ...]
    module_id: str = ""
    description: str = ""
    order: int = 100
    prepend: bool = False


@dataclass(frozen=True)
class ExtensionSystemHookDefinition:
    key: str
    callback: Callable[[Any, dict], Any] | Any
    module_id: str = ""
    description: str = ""
    order: int = 100


@dataclass(frozen=True)
class ExtensionSignalDefinition:
    signal: Any
    receiver: Callable[..., Any]
    sender: Any = None
    dispatch_uid: str = ""
    weak: bool = False
    module_id: str = ""
    description: str = ""
    order: int = 100


@dataclass(frozen=True)
class ExtensionResourceDefinition:
    resource: str
    module_id: str
    resolver: ExtensionResourceBaseResolver
    description: str = ""


@dataclass(frozen=True)
class ExtensionResourceObjectDefinition:
    resource: Any
    module_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class ExtensionResourceFieldDefinition:
    resource: str
    field: str
    module_id: str
    resolver: ExtensionResourceFieldResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]] | None = None
    visible: Callable[[Any, dict], bool] | bool = True
    writable: Callable[[Any, dict], bool] | bool = False
    required_on_create: bool = False
    required_on_update: bool = False
    nullable: bool = False
    value_type: str = ""
    validation_rules: Tuple[Any, ...] = ()
    setter: Callable[[Any, Any, dict], None] | None = None
    validator: Callable[[Any, dict], None] | None = None


@dataclass(frozen=True)
class ExtensionResourceRelationshipDefinition:
    resource: str
    relationship: str
    module_id: str
    resolver: ExtensionResourceRelationshipResolver
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]] | None = None
    visible: Callable[[Any, dict], bool] | bool = True
    includable: Callable[[dict], bool] | bool = True
    resource_type: str = ""
    many: bool = False
    inverse: str = ""
    setter: Callable[[Any, Any, dict], None] | None = None
    writable: Callable[[Any, dict], bool] | bool = False
    linkage: Callable[[Any, dict], Any] | bool = True
    required_on_create: bool = False
    required_on_update: bool = False
    nullable: bool = False
    value_type: str = ""
    validation_rules: Tuple[Any, ...] = ()
    validator: Callable[[Any, dict], None] | None = None


@dataclass(frozen=True)
class ExtensionResourceEndpointDefinition:
    resource: str
    endpoint: str
    module_id: str
    mutator: Callable[[Any], Any] | None = None
    description: str = ""
    operation: str = "mutate"
    anchor: str = ""
    condition: Callable[[dict], bool] | None = None
    handler: Callable[[dict], Any] | None = None
    methods: Tuple[str, ...] = ("GET",)
    path: str = ""
    absolute_path: bool = False
    auth_required: bool = False
    ability: Any = None
    forum_permission: str = ""
    pagination_default_limit: int = 20
    pagination_max_limit: int = 50


@dataclass(frozen=True)
class ExtensionResourceFieldMutatorDefinition:
    resource: str
    field: str
    module_id: str
    mutator: Callable[[Any], Any]
    description: str = ""
    operation: str = "mutate"
    anchor: str = ""
    condition: Callable[[dict], bool] | None = None
    kind: str = ""


@dataclass(frozen=True)
class ExtensionResourceSortDefinition:
    resource: str
    sort: str
    module_id: str
    handler: Any = None
    description: str = ""
    operation: str = "add"
    anchor: str = ""
    mutator: Callable[[Any], Any] | None = None
    condition: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class ExtensionResourceFilterDefinition:
    resource: str
    filter: str
    module_id: str
    handler: Callable[[Any, Any, dict], Any]
    description: str = ""
    visible: Callable[[dict], bool] | bool = True
    operation: str = "add"
    anchor: str = ""
    mutator: Callable[[Any], Any] | None = None
    condition: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class ExtensionModelDefinition:
    model: Any
    key: str
    handler: Any
    kind: str = "metadata"
    description: str = ""


@dataclass(frozen=True)
class ExtensionModelVisibilityDefinition:
    model: Any
    scope: Callable[[Any, dict], Any]
    ability: str = "view"
    description: str = ""
    order: int = 100


@dataclass(frozen=True)
class ExtensionModelRelationDefinition:
    model: Any
    name: str
    resolver: Callable[[Any], Any]
    relation_type: str = "relationship"
    related_model: Any = None
    foreign_key: str = ""
    owner_key: str = ""
    description: str = ""
    inject_attribute: bool = True


@dataclass(frozen=True)
class ExtensionModelCastDefinition:
    model: Any
    attribute: str
    cast: Any
    description: str = ""


@dataclass(frozen=True)
class ExtensionModelDefaultDefinition:
    model: Any
    attribute: str
    value: Any
    description: str = ""


@dataclass(frozen=True)
class ExtensionModelSlugDriverDefinition:
    model: Any
    identifier: str
    driver: Any
    field: str = "slug"
    source_field: str = "name"
    max_length: int | None = None
    description: str = ""


@dataclass(frozen=True)
class ExtensionSearchDriverDefinition:
    target: str
    driver: Any
    filters: Tuple[SearchFilterDefinition, ...] = ()
    mutators: Tuple[Any, ...] = ()
    searchers: Tuple[Any, ...] = ()
    fulltext: Any | None = None
    model: Any = None
    searcher: Any = None
    driver_filters: Tuple[Any, ...] = ()
    replace_filters: Tuple[tuple[str, Any], ...] = ()
    driver_mutators: Tuple[Any, ...] = ()
    indexers: Tuple[Any, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class ExtensionEventListenerDefinition:
    event_type: Type[Any]
    handler: ExtensionDomainEventHandler
    description: str = ""


@dataclass(frozen=True)
class ExtensionRealtimeIncludedDefinition:
    key: str
    handler: Any
    description: str = ""


@dataclass(frozen=True)
class ExtensionDiscussionLifecycleDefinition:
    key: str
    prepare_create: Any = None
    apply_create: Any = None
    prepare_update: Any = None
    apply_update: Any = None
    prepare_delete: Any = None
    apply_delete: Any = None
    apply_hidden: Any = None
    apply_approved: Any = None
    apply_rejected: Any = None
    description: str = ""


@dataclass(frozen=True)
class ExtensionPostLifecycleDefinition:
    key: str
    apply_created: Any = None
    apply_updated: Any = None
    apply_approved: Any = None
    apply_hidden: Any = None
    prepare_delete: Any = None
    apply_deleted: Any = None
    description: str = ""


@dataclass(frozen=True)
class ExtensionDeliveryCheckDefinition:
    key: str
    label: str
    status: str
    status_label: str
    message: str = ""
    path: str = ""
    optional: bool = False


@dataclass(frozen=True)
class ExtensionLifecyclePhaseDefinition:
    key: str
    label: str
    description: str = ""
    optional: bool = False


DEFAULT_EXTENSION_LIFECYCLE_PHASES: Tuple[ExtensionLifecyclePhaseDefinition, ...] = (
    ExtensionLifecyclePhaseDefinition(
        key="discover",
        label="discover",
        description="发现扩展清单并解析扩展元数据。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="register",
        label="register",
        description="注册扩展元数据与能力声明。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="boot",
        label="boot",
        description="接入运行时依赖、监听器、前端资源和后台入口。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="ready",
        label="ready",
        description="依赖与健康检查通过后，对外提供稳定能力。",
    ),
    ExtensionLifecyclePhaseDefinition(
        key="disable",
        label="disable",
        description="停用扩展并撤销可撤销能力。",
        optional=True,
    ),
    ExtensionLifecyclePhaseDefinition(
        key="teardown",
        label="teardown",
        description="卸载、迁移或重建时回收扩展运行时资源。",
        optional=True,
    ),
)


@dataclass(frozen=True)
class ExtensionLifecycleDefinition:
    registration_mode: str = "static"
    registration_mode_label: str = "启动时静态注册"
    readiness_probe: str = "扩展依赖校验与运行时健康摘要"
    supports_disable: bool = False
    supports_teardown: bool = False
    phases: Tuple[ExtensionLifecyclePhaseDefinition, ...] = DEFAULT_EXTENSION_LIFECYCLE_PHASES


@dataclass(frozen=True)
class ExtensionCompatibilityDefinition:
    bias_version: str = ""
    api_version: str = "1.0"
    api_stability: str = "experimental"
    api_stability_label: str = "实验性"
    breaking_change_policy: str = ""


@dataclass(frozen=True)
class ExtensionSecurityDefinition:
    policy_url: str = ""
    support_email: str = ""
    capabilities_notice: str = ""


@dataclass(frozen=True)
class ExtensionDistributionDefinition:
    channel: str = "private"
    channel_label: str = "私有分发"
    signing_key_id: str = ""
    signature_url: str = ""


@dataclass(frozen=True)
class ExtensionManifest:
    id: str
    name: str
    version: str
    description: str = ""
    icon: str = "fas fa-puzzle-piece"
    category: str = "feature"
    authors: Tuple[str, ...] = ()
    homepage: str = ""
    documentation_url: str = ""
    dependencies: Tuple[str, ...] = ()
    optional_dependencies: Tuple[str, ...] = ()
    conflicts: Tuple[str, ...] = ()
    provides: Tuple[str, ...] = ()
    backend_entry: str = ""
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    settings_pages: Tuple[str, ...] = ()
    permissions_pages: Tuple[str, ...] = ()
    operations_pages: Tuple[str, ...] = ()
    admin_actions: Tuple[ExtensionAdminActionDefinition, ...] = ()
    operations_profile: dict[str, Any] = field(default_factory=dict)
    compatibility: ExtensionCompatibilityDefinition = ExtensionCompatibilityDefinition()
    security: ExtensionSecurityDefinition = ExtensionSecurityDefinition()
    distribution: ExtensionDistributionDefinition = ExtensionDistributionDefinition()
    runtime_actions: Tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    settings_schema: Tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    migration_namespace: str = ""
    django_app_config: str = ""
    django_migration_module: str = ""
    source: str = "filesystem"
    path: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtensionRuntimeState:
    installed: bool = True
    enabled: bool = True
    booted: bool = True
    healthy: bool = True
    status_key: str = "active"
    status_label: str = "已启用"
    migration_state: str = "pending"
    migration_label: str = "未声明迁移"
    dependency_state: str = "healthy"
    dependency_state_label: str = "依赖正常"
    runtime_issues: Tuple[str, ...] = ()
    runtime_actions: Tuple[ExtensionRuntimeActionDefinition, ...] = ()
    delivery_checks: Tuple[ExtensionDeliveryCheckDefinition, ...] = ()
    uninstall_warnings: Tuple[str, ...] = ()
    backend_hooks: dict[str, Any] = field(default_factory=dict)
    migration_execution: dict[str, Any] = field(default_factory=dict)
    applied_migration_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionDiscoveryResult:
    manifest: ExtensionManifest
    path: Path
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    frontend_routes: Tuple[ExtensionFrontendRouteDefinition, ...] = ()
    settings_pages: Tuple[str, ...] = ()
    permissions_pages: Tuple[str, ...] = ()
    operations_pages: Tuple[str, ...] = ()
    settings_schema: Tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    settings_defaults: Tuple[ExtensionSettingDefaultDefinition, ...] = ()
    settings_reset_rules: Tuple[ExtensionSettingResetDefinition, ...] = ()
    settings_frontend_cache_keys: Tuple[str, ...] = ()
    settings_theme_variables: Tuple[ExtensionSettingThemeVariableDefinition, ...] = ()
    settings_forum_serializations: Tuple[ExtensionSettingForumSerializationDefinition, ...] = ()
    forum_settings_keys: Tuple[str, ...] = ()
    permissions: Tuple[PermissionDefinition, ...] = ()
    admin_pages: Tuple[AdminPageDefinition, ...] = ()
    notification_types: Tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: Tuple[UserPreferenceDefinition, ...] = ()
    language_packs: Tuple[LanguagePackDefinition, ...] = ()
    post_types: Tuple[PostTypeDefinition, ...] = ()
    search_filters: Tuple[SearchFilterDefinition, ...] = ()
    discussion_list_queries: Tuple[Any, ...] = ()
    discussion_sorts: Tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: Tuple[DiscussionListFilterDefinition, ...] = ()
    locale_paths: Tuple[str, ...] = ()
    view_namespaces: Tuple[ExtensionViewNamespaceDefinition, ...] = ()
    formatter_pipeline: Tuple[ExtensionFormatterCallback, ...] = ()
    formatter_callbacks: Tuple[ExtensionFormatterDefinition, ...] = ()
    resource_definitions: Tuple[ExtensionResourceDefinition, ...] = ()
    resource_fields: Tuple[ExtensionResourceFieldDefinition, ...] = ()
    resource_field_mutators: Tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    resource_relationships: Tuple[ExtensionResourceRelationshipDefinition, ...] = ()
    resource_endpoints: Tuple[ExtensionResourceEndpointDefinition, ...] = ()
    resource_sorts: Tuple[ExtensionResourceSortDefinition, ...] = ()
    resource_filters: Tuple[ExtensionResourceFilterDefinition, ...] = ()
    model_definitions: Tuple[ExtensionModelDefinition, ...] = ()
    model_visibility: Tuple[ExtensionModelVisibilityDefinition, ...] = ()
    model_relations: Tuple[ExtensionModelRelationDefinition, ...] = ()
    model_casts: Tuple[ExtensionModelCastDefinition, ...] = ()
    model_defaults: Tuple[ExtensionModelDefaultDefinition, ...] = ()
    model_slug_drivers: Tuple[ExtensionModelSlugDriverDefinition, ...] = ()
    search_drivers: Tuple[ExtensionSearchDriverDefinition, ...] = ()
    event_listeners: Tuple[ExtensionEventListenerDefinition, ...] = ()
    realtime_included: Tuple[ExtensionRealtimeIncludedDefinition, ...] = ()
    discussion_lifecycle: Tuple[ExtensionDiscussionLifecycleDefinition, ...] = ()
    post_lifecycle: Tuple[ExtensionPostLifecycleDefinition, ...] = ()
    runtime_actions: Tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    admin_actions: Tuple[ExtensionAdminActionDefinition, ...] = ()


@dataclass(frozen=True)
class ExtensionAssembly:
    extension_id: str
    name: str
    source: str
    module_ids: Tuple[str, ...]
    product_visible: bool
    frontend_admin_entry: str
    frontend_forum_entry: str
    frontend_common_entry: str
    frontend_routes: Tuple[Any, ...]
    settings_schema: Tuple[Any, ...]
    settings_defaults: Tuple[Any, ...]
    settings_reset_rules: Tuple[Any, ...]
    settings_frontend_cache_keys: Tuple[str, ...]
    settings_theme_variables: Tuple[Any, ...]
    settings_forum_serializations: Tuple[Any, ...]
    forum_settings_keys: Tuple[str, ...]
    permissions: Tuple[Any, ...]
    admin_pages: Tuple[Any, ...]
    notification_types: Tuple[Any, ...]
    user_preferences: Tuple[Any, ...]
    language_packs: Tuple[Any, ...]
    post_types: Tuple[Any, ...]
    search_filters: Tuple[Any, ...]
    discussion_list_queries: Tuple[Any, ...]
    discussion_sorts: Tuple[Any, ...]
    discussion_list_filters: Tuple[Any, ...]
    locale_paths: Tuple[str, ...]
    view_namespaces: Tuple[Any, ...]
    formatter_pipeline: Tuple[Any, ...]
    formatter_callbacks: Tuple[Any, ...]
    resource_definitions: Tuple[Any, ...]
    resource_fields: Tuple[Any, ...]
    resource_field_mutators: Tuple[Any, ...]
    resource_relationships: Tuple[Any, ...]
    resource_endpoints: Tuple[Any, ...]
    resource_sorts: Tuple[Any, ...]
    resource_filters: Tuple[Any, ...]
    model_definitions: Tuple[Any, ...]
    model_visibility: Tuple[Any, ...]
    model_relations: Tuple[Any, ...]
    model_casts: Tuple[Any, ...]
    model_defaults: Tuple[Any, ...]
    model_slug_drivers: Tuple[Any, ...]
    search_drivers: Tuple[Any, ...]
    event_listeners: Tuple[Any, ...]
    realtime_included: Tuple[Any, ...]
    discussion_lifecycle: Tuple[Any, ...]
    post_lifecycle: Tuple[Any, ...]
    runtime_actions: Tuple[Any, ...]
    admin_actions: Tuple[Any, ...]
    settings_pages: Tuple[str, ...]
    permissions_pages: Tuple[str, ...]
    operations_pages: Tuple[str, ...]


@dataclass(frozen=True)
class ExtensionBootPlan:
    forum_extensions: Tuple[ExtensionAssembly, ...] = ()
    event_extensions: Tuple[ExtensionAssembly, ...] = ()
    resource_extensions: Tuple[ExtensionAssembly, ...] = ()
    frontend_extensions: Tuple[ExtensionAssembly, ...] = ()
    locale_extensions: Tuple[ExtensionAssembly, ...] = ()
    formatter_extensions: Tuple[ExtensionAssembly, ...] = ()
