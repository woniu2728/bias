from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.core.extensions.application_types import (
    ApplicationNamedRoute,
    ApplicationRouteMount,
    ApplicationWebSocketRoute,
)
from apps.core.extensions.container import resolve_container_value
from apps.core.extensions.types import ExtensionFrontendRouteDefinition


FRONTEND_UNSET = object()

@dataclass
class ApplicationFrontendExtension:
    extension_id: str
    admin_entry: str = ""
    forum_entry: str = ""
    common_entry: str = ""
    css: tuple[str, ...] = ()
    js_directories: tuple[str, ...] = ()
    preloads: tuple[Any, ...] = ()
    content_callbacks: tuple[Any, ...] = ()
    document_attributes: tuple[Any, ...] = ()
    head_tags: tuple[Any, ...] = ()
    theme_variables: tuple[Any, ...] = ()
    title_driver: Any = None
    routes: tuple[ExtensionFrontendRouteDefinition, ...] = ()
    settings_pages: tuple[str, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()


@dataclass
class ApplicationServiceProvider:
    key: str
    target: Any
    singleton: bool = True
    _resolved_target: Any = field(default=None, init=False, repr=False)

    def register(self, host: "ExtensionHost") -> None:
        target = self._resolve_target()
        register = getattr(target, "register", None)
        if callable(register):
            register(host)
            return
        if callable(target):
            if self.singleton:
                host.singleton(self.key, target)
            else:
                host.bind(self.key, target)

    def boot(self, host: "ExtensionHost") -> None:
        target = self._resolve_target()
        boot = getattr(target, "boot", None)
        if callable(boot):
            boot(host)

    def _resolve_target(self) -> Any:
        if self._resolved_target is not None:
            return self._resolved_target

        target = resolve_container_value(self.target, None, _skip_container_lookup=True)
        if isinstance(target, type):
            target = target()
        self._resolved_target = target
        return target


class ApplicationRouteService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._mounts_by_extension: dict[str, tuple[ApplicationRouteMount, ...]] = {}
        self._routes_by_app: dict[str, tuple[ApplicationNamedRoute, ...]] = {}
        self._route_names_by_extension: dict[str, tuple[tuple[str, str], ...]] = {}
        self._removed_by_app: dict[str, tuple[str, ...]] = {}

    def mount(
        self,
        extension_id: str,
        prefix: str,
        router: Any,
        *,
        tags=(),
    ) -> ApplicationRouteMount | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_prefix = str(prefix or "").strip()
        if not normalized_extension_id or router is None:
            return None

        mount = ApplicationRouteMount(
            prefix=normalized_prefix,
            router=router,
            tags=tuple(tags or ()),
        )
        mounts = list(self._mounts_by_extension.get(normalized_extension_id, ()))
        mounts.append(mount)
        self._mounts_by_extension[normalized_extension_id] = tuple(mounts)
        self._host._get_or_create_runtime_view(normalized_extension_id).route_mounts = tuple(
            self.get_mounts(extension_id=normalized_extension_id)
        )
        return mount

    def get_mounts(self, *, extension_id: str | None = None) -> list[ApplicationRouteMount]:
        if extension_id is not None:
            return list(self._mounts_by_extension.get(str(extension_id or "").strip(), ()))

        mounts: list[ApplicationRouteMount] = []
        for items in self._mounts_by_extension.values():
            mounts.extend(items)
        return mounts

    def remove_mounts(self, extension_id: str) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        self._mounts_by_extension.pop(normalized, None)
        self._host._get_or_create_runtime_view(normalized).route_mounts = ()

    def add_route(
        self,
        extension_id: str,
        app_name: str,
        method: str,
        path: str,
        name: str,
        handler: Any,
        *,
        tags=(),
    ) -> ApplicationNamedRoute | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_app = str(app_name or "api").strip() or "api"
        normalized_method = str(method or "GET").strip().upper() or "GET"
        normalized_path = "/" + str(path or "").strip().strip("/")
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_name or handler is None:
            return None

        route = ApplicationNamedRoute(
            app_name=normalized_app,
            method=normalized_method,
            path=normalized_path,
            name=normalized_name,
            handler=handler,
            module_id=normalized_extension_id,
            tags=tuple(tags or ()),
        )
        routes = [
            item
            for item in self._routes_by_app.get(normalized_app, ())
            if item.name != normalized_name
        ]
        routes.append(route)
        self._routes_by_app[normalized_app] = tuple(routes)
        removed = [
            item
            for item in self._removed_by_app.get(normalized_app, ())
            if item != normalized_name
        ]
        self._removed_by_app[normalized_app] = tuple(removed)
        route_keys = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != (normalized_app, normalized_name)
        ]
        route_keys.append((normalized_app, normalized_name))
        self._route_names_by_extension[normalized_extension_id] = tuple(route_keys)
        self._sync_route_view(normalized_extension_id)
        return route

    def remove_route(self, extension_id: str, app_name: str, name: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_app = str(app_name or "api").strip() or "api"
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_name:
            return

        self._routes_by_app[normalized_app] = tuple(
            item
            for item in self._routes_by_app.get(normalized_app, ())
            if item.name != normalized_name
        )
        removed = list(self._removed_by_app.get(normalized_app, ()))
        if normalized_name not in removed:
            removed.append(normalized_name)
        self._removed_by_app[normalized_app] = tuple(removed)
        route_keys = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != (normalized_app, normalized_name)
        ]
        route_keys.append((normalized_app, normalized_name))
        self._route_names_by_extension[normalized_extension_id] = tuple(route_keys)
        self._sync_route_view(normalized_extension_id)

    def get_routes(self, *, app_name: str | None = None) -> list[ApplicationNamedRoute]:
        if app_name is not None:
            normalized_app = str(app_name or "").strip()
            removed = set(self._removed_by_app.get(normalized_app, ()))
            return [
                route
                for route in self._routes_by_app.get(normalized_app, ())
                if route.name not in removed
            ]

        routes: list[ApplicationNamedRoute] = []
        for normalized_app in sorted(self._routes_by_app.keys()):
            routes.extend(self.get_routes(app_name=normalized_app))
        return routes

    def get_removed_route_names(self, app_name: str) -> tuple[str, ...]:
        return tuple(self._removed_by_app.get(str(app_name or "").strip(), ()))

    def _sync_route_view(self, extension_id: str) -> None:
        view = self._host._get_or_create_runtime_view(extension_id)
        route_keys = set(self._route_names_by_extension.get(extension_id, ()))
        view.named_routes = tuple(
            route
            for route in self.get_routes()
            if (route.app_name, route.name) in route_keys
        )


class ApplicationWebSocketRouteService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._routes: dict[str, ApplicationWebSocketRoute] = {}
        self._route_names_by_extension: dict[str, tuple[str, ...]] = {}

    def add_route(
        self,
        extension_id: str,
        path: str,
        name: str,
        consumer: Any,
    ) -> ApplicationWebSocketRoute | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_path = str(path or "").strip()
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_path or not normalized_name or consumer is None:
            return None

        route = ApplicationWebSocketRoute(
            path=normalized_path,
            name=normalized_name,
            consumer=consumer,
            module_id=normalized_extension_id,
        )
        self._routes[normalized_name] = route
        route_names = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != normalized_name
        ]
        route_names.append(normalized_name)
        self._route_names_by_extension[normalized_extension_id] = tuple(route_names)
        self._sync_route_view(normalized_extension_id)
        return route

    def remove_routes(self, extension_id: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return
        for name in self._route_names_by_extension.pop(normalized_extension_id, ()):
            self._routes.pop(name, None)
        self._sync_route_view(normalized_extension_id)

    def get_routes(self, *, extension_id: str | None = None) -> list[ApplicationWebSocketRoute]:
        if extension_id is not None:
            route_names = self._route_names_by_extension.get(str(extension_id or "").strip(), ())
            return [
                self._routes[name]
                for name in route_names
                if name in self._routes
            ]
        return [
            self._routes[name]
            for name in sorted(self._routes.keys())
        ]

    def _sync_route_view(self, extension_id: str) -> None:
        view = self._host._get_or_create_runtime_view(extension_id)
        view.websocket_routes = tuple(self.get_routes(extension_id=extension_id))


class ApplicationFrontendService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._extensions: dict[str, ApplicationFrontendExtension] = {}

    def register_entries(
        self,
        extension_id: str,
        *,
        admin_entry: str = "",
        forum_entry: str = "",
        common_entry: str = "",
        css=(),
        js_directories=(),
        preloads=(),
        content_callbacks=(),
        document_attributes=(),
        head_tags=(),
        theme_variables=(),
        title_driver=None,
        routes=(),
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        if admin_entry:
            frontend.admin_entry = str(admin_entry).strip()
        if forum_entry:
            frontend.forum_entry = str(forum_entry).strip()
        if common_entry:
            frontend.common_entry = str(common_entry).strip()
        frontend.css = self._merge_pages(frontend.css, css)
        frontend.js_directories = self._merge_pages(frontend.js_directories, js_directories)
        frontend.preloads = tuple([*frontend.preloads, *(preloads or ())])
        frontend.content_callbacks = tuple([*frontend.content_callbacks, *(content_callbacks or ())])
        frontend.document_attributes = tuple([*frontend.document_attributes, *(document_attributes or ())])
        frontend.head_tags = tuple([*frontend.head_tags, *(head_tags or ())])
        frontend.theme_variables = tuple([*frontend.theme_variables, *(theme_variables or ())])
        if title_driver is not None:
            frontend.title_driver = title_driver
        frontend.routes = self._merge_routes(frontend.routes, routes)
        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry
        view.frontend_css = frontend.css
        view.frontend_js_directories = frontend.js_directories
        view.frontend_preloads = frontend.preloads
        view.frontend_content_callbacks = frontend.content_callbacks
        view.frontend_document_attributes = frontend.document_attributes
        view.frontend_head_tags = frontend.head_tags
        view.frontend_theme_variables = frontend.theme_variables
        view.frontend_title_driver = frontend.title_driver
        view.frontend_routes = frontend.routes
        return frontend

    def register_pages(
        self,
        extension_id: str,
        *,
        settings_pages=(),
        permissions_pages=(),
        operations_pages=(),
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        frontend.settings_pages = self._merge_pages(frontend.settings_pages, settings_pages)
        frontend.permissions_pages = self._merge_pages(frontend.permissions_pages, permissions_pages)
        frontend.operations_pages = self._merge_pages(frontend.operations_pages, operations_pages)
        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages
        return frontend

    def get_extension(self, extension_id: str) -> ApplicationFrontendExtension | None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._extensions.get(normalized)

    def get_extensions(self) -> list[ApplicationFrontendExtension]:
        return list(self._extensions.values())

    def set_extension(
        self,
        extension_id: str,
        *,
        admin_entry: str | None = None,
        forum_entry: str | None = None,
        common_entry: str | None = None,
        css=None,
        js_directories=None,
        preloads=None,
        content_callbacks=None,
        document_attributes=None,
        head_tags=None,
        theme_variables=None,
        title_driver=FRONTEND_UNSET,
        routes=None,
        settings_pages=None,
        permissions_pages=None,
        operations_pages=None,
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        if admin_entry is not None:
            frontend.admin_entry = str(admin_entry or "").strip()
        if forum_entry is not None:
            frontend.forum_entry = str(forum_entry or "").strip()
        if common_entry is not None:
            frontend.common_entry = str(common_entry or "").strip()
        if css is not None:
            frontend.css = tuple(css or ())
        if js_directories is not None:
            frontend.js_directories = tuple(js_directories or ())
        if preloads is not None:
            frontend.preloads = tuple(preloads or ())
        if content_callbacks is not None:
            frontend.content_callbacks = tuple(content_callbacks or ())
        if document_attributes is not None:
            frontend.document_attributes = tuple(document_attributes or ())
        if head_tags is not None:
            frontend.head_tags = tuple(head_tags or ())
        if theme_variables is not None:
            frontend.theme_variables = tuple(theme_variables or ())
        if title_driver is not FRONTEND_UNSET:
            frontend.title_driver = title_driver
        if routes is not None:
            frontend.routes = tuple(routes or ())
        if settings_pages is not None:
            frontend.settings_pages = tuple(settings_pages or ())
        if permissions_pages is not None:
            frontend.permissions_pages = tuple(permissions_pages or ())
        if operations_pages is not None:
            frontend.operations_pages = tuple(operations_pages or ())

        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry
        view.frontend_css = frontend.css
        view.frontend_js_directories = frontend.js_directories
        view.frontend_preloads = frontend.preloads
        view.frontend_content_callbacks = frontend.content_callbacks
        view.frontend_document_attributes = frontend.document_attributes
        view.frontend_head_tags = frontend.head_tags
        view.frontend_theme_variables = frontend.theme_variables
        view.frontend_title_driver = frontend.title_driver
        view.frontend_routes = frontend.routes
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages
        return frontend

    def _get_or_create_extension(self, extension_id: str) -> ApplicationFrontendExtension:
        normalized = str(extension_id or "").strip()
        if normalized not in self._extensions:
            self._extensions[normalized] = ApplicationFrontendExtension(extension_id=normalized)
        return self._extensions[normalized]

    def _merge_pages(self, current: tuple[str, ...], additions) -> tuple[str, ...]:
        merged = list(current)
        for value in additions or ():
            normalized = str(value or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        return tuple(merged)

    def _merge_routes(
        self,
        current: tuple[ExtensionFrontendRouteDefinition, ...],
        additions,
    ) -> tuple[ExtensionFrontendRouteDefinition, ...]:
        merged = list(current)
        seen = {(item.frontend, item.name, item.path) for item in merged}
        for route in additions or ():
            if route is None:
                continue
            key = (route.frontend, route.name, route.path)
            if key in seen:
                continue
            merged.append(route)
            seen.add(key)
        return tuple(sorted(merged, key=lambda item: (item.frontend, item.order, item.name)))


class ApplicationServiceProviderRegistry:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._providers_by_extension: dict[str, tuple[ApplicationServiceProvider, ...]] = {}
        self._registered_provider_keys: set[str] = set()
        self._booted_provider_keys: set[str] = set()

    def register(
        self,
        extension_id: str,
        provider: ApplicationServiceProvider,
    ) -> str:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(provider, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return ""

        providers = list(self._providers_by_extension.get(normalized_extension_id, ()))
        if any(item.key == normalized_key for item in providers):
            return normalized_key

        providers.append(provider)
        self._providers_by_extension[normalized_extension_id] = tuple(providers)
        if normalized_key not in self._registered_provider_keys:
            provider.register(self._host)
            self._registered_provider_keys.add(normalized_key)
        self._host._get_or_create_runtime_view(normalized_extension_id).service_providers = tuple(
            self.get_provider_keys(extension_id=normalized_extension_id)
        )
        return normalized_key

    def register_provider(
        self,
        extension_id: str,
        key: str,
        provider: Any,
        *,
        singleton: bool = True,
    ) -> str:
        return self.register(
            extension_id,
            ApplicationServiceProvider(
                key=key,
                target=provider,
                singleton=singleton,
            ),
        )

    def boot(self) -> None:
        for provider in self.get_providers():
            if provider.key in self._booted_provider_keys:
                continue
            provider.boot(self._host)
            self._booted_provider_keys.add(provider.key)

    def get_providers(self, *, extension_id: str | None = None) -> list[ApplicationServiceProvider]:
        if extension_id is not None:
            return list(self._providers_by_extension.get(str(extension_id or "").strip(), ()))

        providers: list[ApplicationServiceProvider] = []
        for items in self._providers_by_extension.values():
            providers.extend(items)
        return providers

    def get_provider_keys(self, *, extension_id: str | None = None) -> list[str]:
        return [provider.key for provider in self.get_providers(extension_id=extension_id)]
