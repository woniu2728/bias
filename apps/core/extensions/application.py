from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from apps.core.domain_events import DomainEventBus
from apps.core.extensions.application_services import (
    ApplicationMailService,
    ApplicationPostEventDataService,
    ApplicationSignalService,
    ApplicationSystemHookService,
    ApplicationValidatorService,
    ApplicationViewService,
)
from apps.core.extensions.container import import_string, resolve_container_value
from apps.core.extensions.application_frontend import (
    ApplicationFrontendExtension,
    ApplicationFrontendService,
    ApplicationRouteService,
    ApplicationServiceProvider,
    ApplicationServiceProviderRegistry,
    ApplicationWebSocketRouteService,
)
from apps.core.extensions.application_events import (
    ApplicationEventService,
    ApplicationRealtimeService,
)
from apps.core.extensions.application_formatting import (
    ApplicationFormatterService,
    ApplicationLocaleService,
)
from apps.core.extensions.application_forum import (
    ApplicationDiscussionLifecycleService,
    ApplicationForumPermissionService,
    ApplicationForumService,
    ApplicationPostLifecycleService,
    ApplicationResourceService,
)
from apps.core.extensions.application_types import (
    ApplicationMiddlewareMount,
    ApplicationNamedRoute,
    ApplicationPolicyMount,
    ApplicationRouteMount,
    ApplicationWebSocketRoute,
)
from apps.core.extensions.application_models import (
    ApplicationModelService,
    ApplicationModelUrlService,
)
from apps.core.extensions.application_admin import (
    ApplicationAdminActionService,
    ApplicationSettingsService,
)
from apps.core.extensions.application_policy import (
    ApplicationMiddlewareService,
    ApplicationPolicyService,
)
from apps.core.extensions.application_runtime import (
    ExtensionApplicationRecord,
    ExtensionRuntimeView,
)
from apps.core.extensions.application_search import ApplicationSearchService
from apps.core.extensions.exceptions import ExtensionBootError


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.core.extensions.extension_runtime import Extension
    from apps.core.forum_registry import ForumRegistry
    from apps.core.resource_registry import ResourceRegistry


UNSET = object()
ContainerResolver = Callable[["ExtensionHost"], Any]
ContainerExtender = Callable[["ExtensionHost", Any], Any]
ResolvingCallback = Callable[[Any, "ExtensionHost"], Any]
LifecycleCallback = Callable[["ExtensionHost"], None]
PolicyCallback = Callable[..., bool]

class ExtensionApplication:
    def __init__(
        self,
        *,
        extensions_to_boot: tuple["Extension", ...] | list["Extension"] = (),
        extensions_to_catalog: tuple["Extension", ...] | list["Extension"] = (),
        forum_registry: "ForumRegistry | None" = None,
        resource_registry: "ResourceRegistry | None" = None,
        event_bus: DomainEventBus | None = None,
    ) -> None:
        if forum_registry is None:
            from apps.core.forum_registry import ForumRegistry

            forum_registry = ForumRegistry()
        if resource_registry is None:
            from apps.core.resource_registry import ResourceRegistry

            resource_registry = ResourceRegistry()

        self.extensions_to_boot = tuple(extensions_to_boot or ())
        self.extensions_to_catalog = tuple(extensions_to_catalog or self.extensions_to_boot)
        self.forum_registry = forum_registry
        self.resource_registry = resource_registry
        self.event_bus = event_bus or DomainEventBus()

        self._runtime_views: dict[str, ExtensionRuntimeView] = {}
        self._booted_extensions: dict[str, Extension] = {
            extension.id: extension
            for extension in self.extensions_to_boot
        }
        self._bindings: dict[str, ContainerResolver] = {}
        self._singletons: dict[str, ContainerResolver] = {}
        self._instances: dict[str, Any] = {}
        self._aliases: dict[str, str] = {}
        self._tags: dict[str, list[str]] = {}
        self._service_extenders: dict[str, list[ContainerExtender]] = {}
        self._resolving_callbacks: dict[str, list[ResolvingCallback]] = {}
        self._lifecycle_extenders: dict[str, list[Any]] = {}
        self._booting_callbacks: list[LifecycleCallback] = []
        self._booted_callbacks: list[LifecycleCallback] = []
        self._booted = False
        self._booting = False
        self.forum = ApplicationForumService(self, self.forum_registry)
        self.resources = ApplicationResourceService(self, self.resource_registry)
        self.models = ApplicationModelService(self)
        self.model_urls = ApplicationModelUrlService(self)
        self.search = ApplicationSearchService(self)
        self.validators = ApplicationValidatorService(self)
        self.mail = ApplicationMailService(self)
        self.views = ApplicationViewService(self)
        self.error_handling = ApplicationSystemHookService(self, "error_handlers")
        self.auth = ApplicationSystemHookService(self, "auth_handlers")
        self.csrf = ApplicationSystemHookService(self, "csrf_handlers")
        self.filesystem = ApplicationSystemHookService(self, "filesystem_drivers")
        self.console = ApplicationSystemHookService(self, "console_commands")
        self.sessions = ApplicationSystemHookService(self, "session_handlers")
        self.theme = ApplicationSystemHookService(self, "theme_handlers")
        self.throttle_api = ApplicationSystemHookService(self, "throttle_api_handlers")
        self.user = ApplicationSystemHookService(self, "user_handlers")
        self.signals = ApplicationSignalService(self)
        self.routes = ApplicationRouteService(self)
        self.websocket_routes = ApplicationWebSocketRouteService(self)
        self.frontend = ApplicationFrontendService(self)
        self.providers = ApplicationServiceProviderRegistry(self)
        self.locales = ApplicationLocaleService(self)
        self.formatters = ApplicationFormatterService(self)
        self.settings = ApplicationSettingsService(self)
        self.actions = ApplicationAdminActionService(self)
        self.middleware = ApplicationMiddlewareService(self)
        self.policies = ApplicationPolicyService(self)
        self.events = ApplicationEventService(self, self.event_bus)
        self.realtime = ApplicationRealtimeService(self)
        self.forum_permissions = ApplicationForumPermissionService(self)
        self.discussion_lifecycle = ApplicationDiscussionLifecycleService(self)
        self.post_lifecycle = ApplicationPostLifecycleService(self)
        self.post_events = ApplicationPostEventDataService(self)

        self.instance("app", self)
        self.instance("host", self)
        self.instance("extensions.app", self)
        self.instance("extensions.host", self)
        self.instance("forum", self.forum)
        self.instance("extensions.forum", self.forum)
        self.instance("routes", self.routes)
        self.instance("extensions.routes", self.routes)
        self.instance("websocket.routes", self.websocket_routes)
        self.instance("extensions.websocket.routes", self.websocket_routes)
        self.instance("frontend", self.frontend)
        self.instance("extensions.frontend", self.frontend)
        self.instance("resources", self.resources)
        self.instance("extensions.resources", self.resources)
        self.instance("models", self.models)
        self.instance("extensions.models", self.models)
        self.instance("model.urls", self.model_urls)
        self.instance("extensions.model.urls", self.model_urls)
        self.instance("search", self.search)
        self.instance("extensions.search", self.search)
        self.instance("validators", self.validators)
        self.instance("extensions.validators", self.validators)
        self.instance("mail", self.mail)
        self.instance("extensions.mail", self.mail)
        self.instance("views", self.views)
        self.instance("extensions.views", self.views)
        self.instance("error.handling", self.error_handling)
        self.instance("extensions.error.handling", self.error_handling)
        self.instance("auth", self.auth)
        self.instance("extensions.auth", self.auth)
        self.instance("csrf", self.csrf)
        self.instance("extensions.csrf", self.csrf)
        self.instance("filesystem", self.filesystem)
        self.instance("extensions.filesystem", self.filesystem)
        self.instance("console", self.console)
        self.instance("extensions.console", self.console)
        self.instance("session", self.sessions)
        self.instance("extensions.session", self.sessions)
        self.instance("theme", self.theme)
        self.instance("extensions.theme", self.theme)
        self.instance("throttle.api", self.throttle_api)
        self.instance("extensions.throttle.api", self.throttle_api)
        self.instance("user", self.user)
        self.instance("extensions.user", self.user)
        self.instance("signals", self.signals)
        self.instance("extensions.signals", self.signals)
        self.instance("providers", self.providers)
        self.instance("extensions.providers", self.providers)
        self.instance("locales", self.locales)
        self.instance("extensions.locales", self.locales)
        self.instance("formatters", self.formatters)
        self.instance("extensions.formatters", self.formatters)
        self.instance("settings", self.settings)
        self.instance("extensions.settings", self.settings)
        self.instance("actions", self.actions)
        self.instance("extensions.actions", self.actions)
        self.instance("middleware", self.middleware)
        self.instance("extensions.middleware", self.middleware)
        self.instance("policies", self.policies)
        self.instance("extensions.policies", self.policies)
        self.instance("events", self.events)
        self.instance("extensions.events", self.events)
        self.instance("realtime", self.realtime)
        self.instance("extensions.realtime", self.realtime)
        self.instance("forum.permissions", self.forum_permissions)
        self.instance("extensions.forum.permissions", self.forum_permissions)
        self.instance("discussion.lifecycle", self.discussion_lifecycle)
        self.instance("extensions.discussion.lifecycle", self.discussion_lifecycle)
        self.instance("post.lifecycle", self.post_lifecycle)
        self.instance("extensions.post.lifecycle", self.post_lifecycle)
        self.instance("post.events", self.post_events)
        self.instance("extensions.post.events", self.post_events)
        self.instance("forum.registry", self.forum_registry)
        self.instance("resource.registry", self.resource_registry)
        self.instance("event.bus", self.event_bus)
        self.instance("bias.api.resources", [])
        self.singleton("api.application", lambda host: _build_api_application_from_host(host))
        try:
            from apps.core.forum_runtime import set_realtime_service

            set_realtime_service(self.realtime)
        except Exception:
            logger.warning("Failed to bind extension realtime service to forum runtime.", exc_info=True)

    def booting(self, callback: LifecycleCallback) -> None:
        if callable(callback):
            self._booting_callbacks.append(callback)

    def booted(self, callback: LifecycleCallback) -> None:
        if callable(callback):
            self._booted_callbacks.append(callback)

    def is_booted(self) -> bool:
        return self._booted

    def boot(self) -> "ExtensionApplication":
        if self._booted or self._booting:
            return self

        self._booting = True
        try:
            self._run_booting_callbacks()
            self._register_extensions()
            self._boot_extension_providers()
            self._mark_extensions_ready()
        finally:
            self._booting = False

        return self

    def _run_booting_callbacks(self) -> None:
        for callback in list(self._booting_callbacks):
            callback(self)

    def _register_extensions(self) -> None:
        for extension in self.extensions_to_catalog:
            if extension.source != "site":
                self.forum.register_extension_module(extension)
        for extension in self.extensions_to_boot:
            if extension.source != "site":
                self.forum.register_external_module_id(extension.id)
            self._mark_extension_lifecycle_phase(extension.id, "register")
            extension.register(self)

    def _boot_extension_providers(self) -> None:
        self.providers.boot()
        self.make("validators")
        self.make("mail")
        self.make("error.handling")
        self.make("auth")
        self.make("csrf")
        self.make("filesystem")
        self.make("console")
        self.make("session")
        self.make("theme")
        self.make("throttle.api")
        self.make("signals")
        for extension in self.extensions_to_boot:
            self._mark_extension_lifecycle_phase(extension.id, "boot")

    def _mark_extensions_ready(self) -> None:
        self._booted = True
        for callback in list(self._booted_callbacks):
            callback(self)
        for extension in self.extensions_to_boot:
            self._mark_extension_lifecycle_phase(extension.id, "ready")

    def apply_extension_extenders(
        self,
        extension,
        extenders,
    ) -> ExtensionRuntimeView:
        from apps.core.extensions.extender_values import flatten_extenders

        runtime_view = self.get_or_create_runtime_view(
            extension.id,
            name=extension.name,
            source=extension.source,
            path=getattr(getattr(extension, "manifest", None), "path", ""),
            module_ids=extension.module_ids or (extension.id,),
        )
        normalized_extenders = flatten_extenders(extenders)
        for extender in normalized_extenders:
            extend_fn = getattr(extender, "extend", None)
            if not callable(extend_fn):
                continue
            self._mark_extension_extender(extension.id, extender)
            try:
                extend_fn(self, runtime_view)
            except Exception as exc:
                raise ExtensionBootError(extension.id, extender, exc) from exc
        return runtime_view

    def register_lifecycle_extender(self, extension_id: str, extender: Any) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or extender is None:
            return

        current = self._lifecycle_extenders.setdefault(normalized_extension_id, [])
        if extender not in current:
            current.append(extender)

        extender_key = extender.__class__.__name__
        view = self._get_or_create_runtime_view(normalized_extension_id)
        if extender_key and extender_key not in view.lifecycle_extender_keys:
            view.lifecycle_extender_keys = tuple([*view.lifecycle_extender_keys, extender_key])

    def get_lifecycle_extenders(self, extension_id: str) -> list[Any]:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return []
        return list(self._lifecycle_extenders.get(normalized_extension_id, ()))

    def register(self, provider: Any, *, key: str = "", extension_id: str = "core", singleton: bool = True) -> str:
        resolved_key = str(key or "").strip()
        if not resolved_key:
            if isinstance(provider, str):
                resolved_key = provider
            else:
                provider_class = provider if isinstance(provider, type) else type(provider)
                resolved_key = f"{provider_class.__module__}.{provider_class.__name__}"
        return self.providers.register_provider(
            extension_id,
            resolved_key,
            provider,
            singleton=singleton,
        )

    def bind(self, key: str, resolver: ContainerResolver) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        self._bindings[normalized] = resolver
        self._instances.pop(normalized, None)

    def singleton(self, key: str, resolver: ContainerResolver) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        self._singletons[normalized] = resolver
        self._instances.pop(normalized, None)

    def instance(self, key: str, value: Any) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        resolved = self._apply_service_extenders(normalized, value)
        self._instances[normalized] = self._apply_resolving_callbacks(normalized, resolved)

    def extend(self, key: str, extender: ContainerExtender) -> None:
        normalized = self._container_key(key)
        if not normalized or not callable(extender):
            return
        normalized = self._resolve_alias(normalized)
        self._service_extenders.setdefault(normalized, []).append(extender)
        if normalized in self._instances:
            self._instances[normalized] = self._apply_service_extenders(normalized, self._instances[normalized])
            self._instances[normalized] = self._apply_resolving_callbacks(normalized, self._instances[normalized])

    def resolving(self, key: str, callback: ResolvingCallback) -> None:
        normalized = self._container_key(key)
        if not normalized or not callable(callback):
            return
        normalized = self._resolve_alias(normalized)
        self._resolving_callbacks.setdefault(normalized, []).append(callback)
        if normalized in self._instances:
            self._instances[normalized] = callback(self._instances[normalized], self)

    def alias(self, abstract: Any, alias: str) -> None:
        target = self._container_key(abstract)
        normalized_alias = self._container_key(alias)
        if target and normalized_alias and target != normalized_alias:
            self._aliases[normalized_alias] = self._resolve_alias(target)

    def tag(self, keys, tag: str) -> None:
        normalized_tag = self._container_key(tag)
        if not normalized_tag:
            return
        current = self._tags.setdefault(normalized_tag, [])
        iterable = keys if isinstance(keys, (list, tuple, set)) else (keys,)
        for key in iterable:
            normalized = self._resolve_alias(self._container_key(key))
            if normalized and normalized not in current:
                current.append(normalized)

    def tagged(self, tag: str) -> list[Any]:
        normalized_tag = self._container_key(tag)
        return [self.make(key) for key in self._tags.get(normalized_tag, ())]

    def has(self, key: str) -> bool:
        normalized = self._resolve_alias(self._container_key(key))
        return (
            normalized in self._instances
            or normalized in self._singletons
            or normalized in self._bindings
            or self._is_class_key(normalized)
        )

    def make(self, key: str, default: Any = UNSET) -> Any:
        normalized = self._resolve_alias(self._container_key(key))
        if normalized in self._instances:
            return self._instances[normalized]

        if normalized in self._singletons:
            resolved = self._resolve_service(self._singletons[normalized])
            resolved = self._apply_service_extenders(normalized, resolved)
            self._instances[normalized] = self._apply_resolving_callbacks(normalized, resolved)
            return self._instances[normalized]

        if normalized in self._bindings:
            resolved = self._resolve_service(self._bindings[normalized])
            resolved = self._apply_service_extenders(normalized, resolved)
            return self._apply_resolving_callbacks(normalized, resolved)

        if default is not UNSET:
            return default

        if self._is_class_key(normalized):
            return self._make_class(normalized)

        raise KeyError(f"服务未注册: {normalized}")

    def get(self, key: str, default: Any = UNSET) -> Any:
        return self.make(key, default)

    def register_service(self, key: str, value: Any) -> None:
        self.instance(key, value)

    def get_service(self, key: str, default: Any = None) -> Any:
        return self.make(key, default)

    def get_or_create_runtime_view(
        self,
        extension_id: str,
        *,
        name: str = "",
        source: str = "",
        path: str = "",
        module_ids: tuple[str, ...] | list[str] = (),
    ) -> ExtensionRuntimeView:
        normalized = str(extension_id or "").strip()
        return self._get_or_create_runtime_view(
            normalized,
            name=name,
            source=source,
            path=path,
            module_ids=module_ids,
        )

    def get_records(self) -> list[ExtensionApplicationRecord]:
        return [
            self._build_application_record(view)
            for view in self.get_runtime_views()
        ]

    def get_runtime_views(self) -> list[ExtensionRuntimeView]:
        return list(self._runtime_views.values())

    def get_runtime_view(self, extension_id: str) -> ExtensionRuntimeView | None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._runtime_views.get(normalized)

    def get_extension_views(self) -> list[ExtensionRuntimeView]:
        return self.get_runtime_views()

    def get_extension_view(self, extension_id: str) -> ExtensionRuntimeView | None:
        return self.get_runtime_view(extension_id)

    def get_booted_extensions(self) -> list["Extension"]:
        return list(self._booted_extensions.values())

    def get_booted_extension(self, extension_id: str) -> "Extension | None":
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._booted_extensions.get(normalized)

    def get_runtime_extensions(self) -> list["Extension"]:
        return self.get_booted_extensions()

    def get_runtime_extension(self, extension_id: str) -> "Extension | None":
        return self.get_booted_extension(extension_id)

    def register_frontend_entry(
        self,
        extension: ExtensionRuntimeView,
        *,
        admin_entry: str = "",
        forum_entry: str = "",
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        frontend = self.frontend.register_entries(
            extension.extension_id,
            admin_entry=admin_entry,
            forum_entry=forum_entry,
        )
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry

    def register_admin_surface_pages(
        self,
        extension: ExtensionRuntimeView,
        *,
        settings_pages=(),
        permissions_pages=(),
        operations_pages=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        frontend = self.frontend.register_pages(
            extension.extension_id,
            settings_pages=settings_pages,
            permissions_pages=permissions_pages,
            operations_pages=operations_pages,
        )
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages

    def register_locale_path(self, extension: ExtensionRuntimeView, path: str) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(path or "").strip()
        if normalized and normalized not in view.locale_paths:
            view.locale_paths = tuple([*view.locale_paths, normalized])

    def register_formatter(self, extension: ExtensionRuntimeView, callback) -> None:
        self.formatters.register_render(extension.extension_id, callback)

    def register_settings_fields(
        self,
        extension: ExtensionRuntimeView,
        fields,
        *,
        expose_to_forum=(),
        generated_page: bool = True,
        defaults=(),
        reset_when=(),
        reset_frontend_cache_for=(),
        theme_variables=(),
        forum_serializations=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        fields_collection = list(view.settings_schema)
        for field in fields or ():
            fields_collection.append(field)
        view.settings_schema = tuple(fields_collection)
        view.settings_defaults = tuple([*view.settings_defaults, *(defaults or ())])
        view.settings_reset_rules = tuple([*view.settings_reset_rules, *(reset_when or ())])
        cache_keys = list(view.settings_frontend_cache_keys)
        for key in reset_frontend_cache_for or ():
            normalized = str(key or "").strip()
            if normalized and normalized not in cache_keys:
                cache_keys.append(normalized)
        view.settings_frontend_cache_keys = tuple(cache_keys)
        view.settings_theme_variables = tuple([*view.settings_theme_variables, *(theme_variables or ())])
        view.settings_forum_serializations = tuple([
            *view.settings_forum_serializations,
            *(forum_serializations or ()),
        ])
        forum_keys = list(view.forum_settings_keys)
        for key in expose_to_forum or ():
            normalized = str(key or "").strip()
            if normalized and normalized not in forum_keys:
                forum_keys.append(normalized)
        view.forum_settings_keys = tuple(forum_keys)
        if generated_page:
            view.use_generated_settings_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/settings"
            self.register_admin_surface_pages(extension, settings_pages=(generated_path,))

    def register_runtime_actions(
        self,
        extension: ExtensionRuntimeView,
        actions,
        *,
        generated_page: bool = False,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        collection = list(view.runtime_actions)
        for action in actions or ():
            collection.append(action)
        view.runtime_actions = tuple(collection)
        if generated_page:
            view.use_generated_operations_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/operations"
            self.register_admin_surface_pages(extension, operations_pages=(generated_path,))

    def register_admin_actions(
        self,
        extension: ExtensionRuntimeView,
        actions,
        *,
        generated_permissions_page: bool = False,
        generated_operations_page: bool = False,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        collection = list(view.admin_actions)
        for action in actions or ():
            collection.append(action)
        view.admin_actions = tuple(collection)
        if generated_permissions_page:
            view.use_generated_permissions_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/permissions"
            self.register_admin_surface_pages(extension, permissions_pages=(generated_path,))
        if generated_operations_page:
            view.use_generated_operations_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/operations"
            self.register_admin_surface_pages(extension, operations_pages=(generated_path,))

    def mark_generated_permissions_page(self, extension: ExtensionRuntimeView) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.use_generated_permissions_page = True
        generated_path = f"/admin/extensions/{extension.extension_id}/permissions"
        self.register_admin_surface_pages(extension, permissions_pages=(generated_path,))

    def register_forum_module_id(self, extension: ExtensionRuntimeView, module_id: str) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(module_id or "").strip()
        if normalized:
            self.forum_registry.register_external_module_id(normalized)
            if normalized not in view.module_ids:
                view.module_ids = tuple([*view.module_ids, normalized])

    def register_permission(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.permissions = tuple([*view.permissions, definition])
        self.forum.register_permission(definition)

    def register_admin_page(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.admin_pages = tuple([*view.admin_pages, definition])
        self.forum.register_admin_page(definition)

    def register_notification_type(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.notification_types = tuple([*view.notification_types, definition])
        self.forum.register_notification_type(definition)

    def register_user_preference(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.user_preferences = tuple([*view.user_preferences, definition])
        self.forum.register_user_preference(definition)

    def register_language_pack(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.language_packs = tuple([*view.language_packs, definition])
        self.forum.register_language_pack(definition)

    def register_post_type(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.post_types = tuple([*view.post_types, definition])
        self.forum.register_post_type(definition)

    def register_search_filter(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.search_filters = tuple([*view.search_filters, definition])
        self.forum.register_search_filter(definition)

    def register_discussion_list_query(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_list_queries = tuple([*view.discussion_list_queries, definition])
        self.forum.register_discussion_list_query(definition)

    def register_discussion_sort(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_sorts = tuple([*view.discussion_sorts, definition])
        self.forum.register_discussion_sort(definition)

    def register_discussion_list_filter(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_list_filters = tuple([*view.discussion_list_filters, definition])
        self.forum.register_discussion_list_filter(definition)

    def register_resource(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_definitions = tuple([*view.resource_definitions, definition])
        self.resources.register_resource(definition)

    def register_resource_field(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_fields = tuple([*view.resource_fields, definition])
        self.resources.register_field(definition)

    def register_resource_relationship(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_relationships = tuple([*view.resource_relationships, definition])
        self.resources.register_relationship(definition)

    def register_event_listener(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.event_listeners = tuple([*view.event_listeners, definition])
        self.event_bus.register(definition.event_type, definition.handler)

    def register_route_mount(
        self,
        extension: ExtensionRuntimeView,
        prefix: str,
        router,
        *,
        tags=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        mount = self.routes.mount(extension.extension_id, prefix, router, tags=tags)
        if mount is None:
            return
        view.route_mounts = tuple(self.routes.get_mounts(extension_id=extension.extension_id))

    def register_service_provider(
        self,
        extension: ExtensionRuntimeView,
        provider_name: str,
        provider: Any | None = None,
        *,
        singleton: bool = True,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(provider_name or "").strip()
        if not normalized or provider is None:
            return
        registered_key = self.providers.register(
            extension.extension_id,
            ApplicationServiceProvider(
                key=normalized,
                target=provider,
                singleton=singleton,
            ),
        )
        if registered_key:
            view.service_providers = tuple(self.providers.get_provider_keys(extension_id=extension.extension_id))

    def register_middleware_mount(
        self,
        extension: ExtensionRuntimeView,
        target: str,
        middleware,
        *,
        order: int = 100,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.middleware_mounts = tuple([*view.middleware_mounts, ApplicationMiddlewareMount(
            target=str(target or "").strip() or "api",
            middleware=middleware,
            order=int(order),
        )])

    def register_policy_mount(self, extension: ExtensionRuntimeView, key: str, handler) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(key or "").strip()
        if normalized and callable(handler):
            view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
                key=normalized,
                handler=handler,
            )])

    def get_route_mounts(self) -> list[ApplicationRouteMount]:
        return self.routes.get_mounts()

    def get_named_routes(self, *, app_name: str | None = None) -> list[ApplicationNamedRoute]:
        return self.routes.get_routes(app_name=app_name)

    def get_websocket_routes(self) -> list[ApplicationWebSocketRoute]:
        return self.websocket_routes.get_routes()

    def get_frontend_extension(self, extension_id: str) -> ApplicationFrontendExtension | None:
        return self.frontend.get_extension(extension_id)

    def get_frontend_extensions(self) -> list[ApplicationFrontendExtension]:
        return self.frontend.get_extensions()

    def get_service_provider_keys(self, *, extension_id: str | None = None) -> list[str]:
        return self.providers.get_provider_keys(extension_id=extension_id)

    def get_middleware_mounts(self, *, target: str | None = None) -> list[ApplicationMiddlewareMount]:
        mounts: list[ApplicationMiddlewareMount] = []
        for view in self.get_runtime_views():
            mounts.extend(view.middleware_mounts)
        if target is not None:
            mounts = [item for item in mounts if item.target == target]
        return sorted(mounts, key=lambda item: (item.target, item.order))

    def get_policy_mounts(self) -> list[ApplicationPolicyMount]:
        mounts: list[ApplicationPolicyMount] = []
        for view in self.get_runtime_views():
            mounts.extend(view.policy_mounts)
        return mounts

    @staticmethod
    def _container_key(key: Any) -> str:
        if isinstance(key, type):
            return f"{key.__module__}.{key.__name__}"
        return str(key or "").strip()

    def _resolve_alias(self, key: str) -> str:
        normalized = str(key or "").strip()
        seen = set()
        while normalized in self._aliases and normalized not in seen:
            seen.add(normalized)
            normalized = self._aliases[normalized]
        return normalized

    @staticmethod
    def _is_class_key(key: str) -> bool:
        return "." in str(key or "").strip()

    def _make_class(self, key: str) -> Any:
        try:
            cls = import_string(key)
        except (ImportError, AttributeError):
            short = key.rsplit(".", 1)[-1]
            if short and short in self._instances:
                return self._instances[short]
            raise KeyError(f"服务未注册: {key}")
        resolved = resolve_container_value(cls, self)
        resolved = self._apply_service_extenders(key, resolved)
        return self._apply_resolving_callbacks(key, resolved)

    def _resolve_service(self, resolver: ContainerResolver | Any) -> Any:
        resolver = resolve_container_value(resolver, self, _skip_container_lookup=True)
        if callable(resolver):
            try:
                return resolver(self)
            except TypeError:
                return resolver()
        return resolver

    def _get_or_create_runtime_view(
        self,
        extension_id: str,
        *,
        name: str = "",
        source: str = "",
        path: str = "",
        module_ids: tuple[str, ...] | list[str] = (),
    ) -> ExtensionRuntimeView:
        normalized = str(extension_id or "").strip()
        if normalized not in self._runtime_views:
            self._runtime_views[normalized] = ExtensionRuntimeView(
                extension_id=normalized,
                name=str(name or "").strip(),
                source=str(source or "").strip(),
                path=str(path or "").strip(),
                module_ids=tuple(
                    item for item in dict.fromkeys(str(item).strip() for item in module_ids)
                    if item
                ),
            )
        view = self._runtime_views[normalized]
        if name:
            view.name = str(name).strip()
        if source:
            view.source = str(source).strip()
        if path:
            view.path = str(path).strip()
        if module_ids:
            view.module_ids = tuple(
                item for item in dict.fromkeys(str(item).strip() for item in module_ids)
                if item
            )
        return view

    def _mark_extension_lifecycle_phase(self, extension_id: str, phase_key: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_phase_key = str(phase_key or "").strip()
        if not normalized_extension_id or not normalized_phase_key:
            return

        view = self._get_or_create_runtime_view(normalized_extension_id)
        if normalized_phase_key in view.lifecycle_phase_keys:
            return
        view.lifecycle_phase_keys = tuple([*view.lifecycle_phase_keys, normalized_phase_key])

    def _mark_extension_extender(self, extension_id: str, extender: Any) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return
        extender_key = extender.__class__.__name__
        if not extender_key:
            return
        view = self._get_or_create_runtime_view(normalized_extension_id)
        if extender_key in view.extender_keys:
            return
        view.extender_keys = tuple([*view.extender_keys, extender_key])

    def _build_application_record(self, view: ExtensionRuntimeView) -> ExtensionApplicationRecord:
        return ExtensionApplicationRecord(
            extension_id=view.extension_id,
            name=view.name,
            source=view.source,
            module_ids=list(view.module_ids),
            frontend_admin_entry=view.frontend_admin_entry,
            frontend_forum_entry=view.frontend_forum_entry,
            frontend_common_entry=view.frontend_common_entry,
            frontend_css=list(view.frontend_css),
            frontend_js_directories=list(view.frontend_js_directories),
            frontend_preloads=list(view.frontend_preloads),
            frontend_content_callbacks=list(view.frontend_content_callbacks),
            frontend_document_attributes=list(view.frontend_document_attributes),
            frontend_head_tags=list(view.frontend_head_tags),
            frontend_theme_variables=list(view.frontend_theme_variables),
            frontend_title_driver=view.frontend_title_driver,
            frontend_routes=list(view.frontend_routes),
            settings_pages=list(view.settings_pages),
            permissions_pages=list(view.permissions_pages),
            operations_pages=list(view.operations_pages),
            settings_schema=list(view.settings_schema),
            settings_defaults=list(view.settings_defaults),
            settings_reset_rules=list(view.settings_reset_rules),
            settings_frontend_cache_keys=list(view.settings_frontend_cache_keys),
            settings_theme_variables=list(view.settings_theme_variables),
            settings_forum_serializations=list(view.settings_forum_serializations),
            forum_settings_keys=list(view.forum_settings_keys),
            permissions=list(view.permissions),
            admin_pages=list(view.admin_pages),
            notification_types=list(view.notification_types),
            user_preferences=list(view.user_preferences),
            language_packs=list(view.language_packs),
            post_types=list(view.post_types),
            search_filters=list(view.search_filters),
            discussion_list_queries=list(view.discussion_list_queries),
            discussion_sorts=list(view.discussion_sorts),
            discussion_list_filters=list(view.discussion_list_filters),
            locale_paths=list(view.locale_paths),
            view_namespaces=list(view.view_namespaces),
            formatter_pipeline=list(view.formatter_pipeline),
            formatter_callbacks=list(view.formatter_callbacks),
            resource_definitions=list(view.resource_definitions),
            resource_fields=list(view.resource_fields),
            resource_field_mutators=list(view.resource_field_mutators),
            resource_relationships=list(view.resource_relationships),
            resource_endpoints=list(view.resource_endpoints),
            resource_sorts=list(view.resource_sorts),
            resource_filters=list(view.resource_filters),
            model_definitions=list(view.model_definitions),
            model_visibility=list(view.model_visibility),
            model_relations=list(view.model_relations),
            model_casts=list(view.model_casts),
            model_defaults=list(view.model_defaults),
            model_slug_drivers=list(view.model_slug_drivers),
            search_drivers=list(view.search_drivers),
            search_indexes=list(view.search_indexes),
            validators=list(view.validators),
            mailers=list(view.mailers),
            error_handlers=list(view.error_handlers),
            auth_handlers=list(view.auth_handlers),
            csrf_handlers=list(view.csrf_handlers),
            filesystem_drivers=list(view.filesystem_drivers),
            console_commands=list(view.console_commands),
            session_handlers=list(view.session_handlers),
            theme_handlers=list(view.theme_handlers),
            throttle_api_handlers=list(view.throttle_api_handlers),
            user_handlers=list(view.user_handlers),
            signal_handlers=list(view.signal_handlers),
            event_listeners=list(view.event_listeners),
            realtime_included=list(view.realtime_included),
            realtime_discussion_visibility=list(view.realtime_discussion_visibility),
            realtime_discussion_transports=list(view.realtime_discussion_transports),
            realtime_discussion_broadcasts=list(view.realtime_discussion_broadcasts),
            forum_permission_checkers=list(view.forum_permission_checkers),
            discussion_lifecycle=list(view.discussion_lifecycle),
            post_lifecycle=list(view.post_lifecycle),
            runtime_actions=list(view.runtime_actions),
            admin_actions=list(view.admin_actions),
            route_mounts=list(view.route_mounts),
            named_routes=list(view.named_routes),
            websocket_routes=list(view.websocket_routes),
            middleware_mounts=list(view.middleware_mounts),
            policy_mounts=list(view.policy_mounts),
            service_providers=list(view.service_providers),
            extender_keys=list(view.extender_keys),
            lifecycle_extender_keys=list(view.lifecycle_extender_keys),
            lifecycle_phase_keys=list(view.lifecycle_phase_keys),
            use_generated_settings_page=view.use_generated_settings_page,
            use_generated_permissions_page=view.use_generated_permissions_page,
            use_generated_operations_page=view.use_generated_operations_page,
        )

    def _apply_service_extenders(self, key: str, value: Any) -> Any:
        output = value
        for extender in self._service_extenders.get(key, []):
            output = extender(self, output)
        return output

    def _apply_resolving_callbacks(self, key: str, value: Any) -> Any:
        output = value
        for callback in self._resolving_callbacks.get(key, []):
            output = callback(output, self)
        return output


ExtensionHost = ExtensionApplication


def _build_api_application_from_host(host: ExtensionApplication):
    from apps.core.api_runtime import build_api_application

    return build_api_application(extension_host=host)
