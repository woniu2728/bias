from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from apps.core.extensions.application import ExtensionApplication, ExtensionHost, ExtensionRuntimeView
from apps.core.extensions.extender_values import flatten_extenders
from apps.core.extensions.module_loader import load_extension_backend_module
from apps.core.extensions.types import (
    ExtensionLifecycleDefinition,
    ExtensionManifest,
    ExtensionRuntimeState,
)


ExtensionBootstrapper = Callable[["Extension", ExtensionHost], ExtensionRuntimeView]


@dataclass
class Extension:
    manifest: ExtensionManifest
    module: Any | None = None
    runtime: ExtensionRuntimeState = field(default_factory=ExtensionRuntimeState)
    lifecycle: ExtensionLifecycleDefinition = field(default_factory=ExtensionLifecycleDefinition)
    capabilities: tuple[str, ...] = ()
    module_ids: tuple[str, ...] = ()
    source: str = "filesystem"
    admin_pages: tuple[str, ...] = ()
    settings_groups: tuple[str, ...] = ()
    bootstrapper: ExtensionBootstrapper | None = None
    _discovery_view: ExtensionRuntimeView | None = field(default=None, init=False, repr=False)
    _extenders: tuple[Any, ...] | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_manifest(cls, manifest: ExtensionManifest) -> "Extension":
        extension = cls(
            manifest=manifest,
            module=load_extension_backend_module(
                type(
                    "_ManifestDefinition",
                    (),
                    {
                        "manifest": manifest,
                        "source": manifest.source,
                        "id": manifest.id,
                    },
                )()
            ),
            capabilities=tuple(manifest.provides),
            module_ids=(manifest.id,),
            source=manifest.source,
        )
        return extension

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def description(self) -> str:
        return self.manifest.description

    def discover(self, *, force: bool = False) -> ExtensionRuntimeView:
        if self._discovery_view is not None and not force:
            return self._discovery_view

        host = ExtensionHost()
        self._discovery_view = self.extend(host)
        return self._discovery_view

    def invalidate_discovery(self) -> None:
        self._discovery_view = None
        self._extenders = None

    def extend(self, host: ExtensionHost) -> ExtensionRuntimeView:
        return self.register(host)

    def register(self, host: ExtensionHost) -> ExtensionRuntimeView:
        if self.bootstrapper is not None:
            return self.bootstrapper(self, host)
        return self._extend_filesystem(host)

    def _extend_filesystem(self, host: ExtensionHost) -> ExtensionRuntimeView:
        module = self.module
        if module is None:
            return host.get_or_create_runtime_view(
                self.id,
                name=self.name,
                source=self.source,
                module_ids=self.module_ids or (self.id,),
            )

        if not callable(getattr(module, "extend", None)):
            return host.get_or_create_runtime_view(
                self.id,
                name=self.name,
                source=self.source,
                module_ids=self.module_ids or (self.id,),
            )

        extenders = self.get_extenders()
        return host.apply_extension_extenders(self, extenders)

    def get_extenders(self) -> tuple[Any, ...]:
        if self._extenders is not None:
            return self._extenders

        module = self.module
        if module is None:
            self._extenders = ()
            return self._extenders

        extenders_factory = getattr(module, "extend", None)
        extenders: Any = []
        if callable(extenders_factory):
            extenders = extenders_factory() or []

        self._extenders = flatten_extenders(extenders)
        return self._extenders

    def get_runtime_view(self, host: ExtensionHost | None = None) -> ExtensionRuntimeView:
        if host is not None:
            runtime_view = host.get_extension_view(self.id)
            if runtime_view is not None:
                return runtime_view
        return self.discover()

    @property
    def frontend_admin_entry(self) -> str:
        runtime_view = self.discover()
        return str(runtime_view.frontend_admin_entry or self.manifest.frontend_admin_entry or "").strip()

    @property
    def frontend_forum_entry(self) -> str:
        runtime_view = self.discover()
        return str(runtime_view.frontend_forum_entry or self.manifest.frontend_forum_entry or "").strip()

    @property
    def settings_pages(self) -> tuple[str, ...]:
        runtime_view = self.discover()
        if runtime_view.settings_pages:
            return tuple(runtime_view.settings_pages)
        return tuple(self.manifest.settings_pages)

    @property
    def permissions_pages(self) -> tuple[str, ...]:
        runtime_view = self.discover()
        if runtime_view.permissions_pages:
            return tuple(runtime_view.permissions_pages)
        return tuple(self.manifest.permissions_pages)

    @property
    def operations_pages(self) -> tuple[str, ...]:
        runtime_view = self.discover()
        if runtime_view.operations_pages:
            return tuple(runtime_view.operations_pages)
        return tuple(self.manifest.operations_pages)

    @property
    def settings_schema(self):
        return tuple(self.discover().settings_schema)

    @property
    def settings_defaults(self):
        return tuple(self.discover().settings_defaults)

    @property
    def settings_reset_rules(self):
        return tuple(self.discover().settings_reset_rules)

    @property
    def settings_frontend_cache_keys(self) -> tuple[str, ...]:
        return tuple(self.discover().settings_frontend_cache_keys)

    @property
    def settings_theme_variables(self):
        return tuple(self.discover().settings_theme_variables)

    @property
    def settings_forum_serializations(self):
        return tuple(self.discover().settings_forum_serializations)

    @property
    def forum_settings_keys(self) -> tuple[str, ...]:
        return tuple(self.discover().forum_settings_keys)

    @property
    def permissions(self):
        return tuple(self.discover().permissions)

    @property
    def admin_page_definitions(self):
        return tuple(self.discover().admin_pages)

    @property
    def notification_types(self):
        return tuple(self.discover().notification_types)

    @property
    def user_preferences(self):
        return tuple(self.discover().user_preferences)

    @property
    def language_packs(self):
        return tuple(self.discover().language_packs)

    @property
    def post_types(self):
        return tuple(self.discover().post_types)

    @property
    def search_filters(self):
        return tuple(self.discover().search_filters)

    @property
    def discussion_list_queries(self):
        return tuple(self.discover().discussion_list_queries)

    @property
    def discussion_sorts(self):
        return tuple(self.discover().discussion_sorts)

    @property
    def discussion_list_filters(self):
        return tuple(self.discover().discussion_list_filters)

    @property
    def locale_paths(self) -> tuple[str, ...]:
        return tuple(self.discover().locale_paths)

    @property
    def view_namespaces(self):
        return tuple(self.discover().view_namespaces)

    @property
    def formatter_pipeline(self):
        return tuple(self.discover().formatter_pipeline)

    @property
    def formatter_callbacks(self):
        return tuple(self.discover().formatter_callbacks)

    @property
    def resource_definitions(self):
        return tuple(self.discover().resource_definitions)

    @property
    def resource_fields(self):
        return tuple(self.discover().resource_fields)

    @property
    def resource_field_mutators(self):
        return tuple(self.discover().resource_field_mutators)

    @property
    def resource_relationships(self):
        return tuple(self.discover().resource_relationships)

    @property
    def resource_endpoints(self):
        return tuple(self.discover().resource_endpoints)

    @property
    def resource_sorts(self):
        return tuple(self.discover().resource_sorts)

    @property
    def model_definitions(self):
        return tuple(self.discover().model_definitions)

    @property
    def model_visibility(self):
        return tuple(self.discover().model_visibility)

    @property
    def model_relations(self):
        return tuple(self.discover().model_relations)

    @property
    def model_casts(self):
        return tuple(self.discover().model_casts)

    @property
    def model_defaults(self):
        return tuple(self.discover().model_defaults)

    @property
    def model_slug_drivers(self):
        return tuple(self.discover().model_slug_drivers)

    @property
    def search_drivers(self):
        return tuple(self.discover().search_drivers)

    @property
    def event_listeners(self):
        return tuple(self.discover().event_listeners)

    @property
    def realtime_included(self):
        return tuple(self.discover().realtime_included)

    @property
    def discussion_lifecycle(self):
        return tuple(self.discover().discussion_lifecycle)

    @property
    def post_lifecycle(self):
        return tuple(self.discover().post_lifecycle)

    @property
    def manifest_runtime_actions(self):
        runtime_view = self.discover()
        if runtime_view.runtime_actions:
            return tuple(runtime_view.runtime_actions)
        return tuple(self.manifest.runtime_actions)

    @property
    def admin_actions(self):
        runtime_view = self.discover()
        if runtime_view.admin_actions:
            return tuple(runtime_view.admin_actions)
        return tuple(self.manifest.admin_actions)

    @property
    def path(self) -> Path | None:
        root = str(self.manifest.path or "").strip()
        if not root:
            return None
        return Path(root)
