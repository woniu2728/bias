from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass
from typing import Any, Callable
from typing import Protocol, TYPE_CHECKING

from apps.core.extensions.container import resolve_container_value, wrap_callback
from apps.core.extensions.extender_values import flatten_extenders
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionDiscussionLifecycleDefinition,
    ExtensionEventListenerDefinition,
    ExtensionFrontendRouteDefinition,
    ExtensionFormatterCallback,
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionSettingDefaultDefinition,
    ExtensionSettingForumSerializationDefinition,
    ExtensionSettingResetDefinition,
    ExtensionSettingThemeVariableDefinition,
    ExtensionModelDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionPostLifecycleDefinition,
    ExtensionResourceDefinition,
    ExtensionResourceEndpointDefinition,
    ExtensionResourceFieldMutatorDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceObjectDefinition,
    ExtensionResourceRelationshipDefinition,
    ExtensionResourceSortDefinition,
    ExtensionRealtimeIncludedDefinition,
    ExtensionSearchDriverDefinition,
    ExtensionSignalDefinition,
    ExtensionSystemHookDefinition,
    ExtensionValidatorDefinition,
    ExtensionViewNamespaceDefinition,
    ExtensionMailDefinition,
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
from apps.core.resource_objects import ResourceEndpoint, ResourceField, ResourceRelationship, ResourceSort
from apps.core.resource_registry import ResourceRegistry

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView
    from apps.core.extensions.backend import ExtensionBackendContext


class ExtenderInterface(Protocol):
    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        ...


class LifecycleInterface(Protocol):
    def on_install(self, context: "ExtensionBackendContext") -> Any:
        ...

    def on_enable(self, context: "ExtensionBackendContext") -> Any:
        ...

    def on_disable(self, context: "ExtensionBackendContext") -> Any:
        ...

    def on_uninstall(self, context: "ExtensionBackendContext") -> Any:
        ...


@dataclass(frozen=True)
class LifecycleExtender:
    install: Callable[["ExtensionBackendContext"], Any] | None = None
    enable: Callable[["ExtensionBackendContext"], Any] | None = None
    disable: Callable[["ExtensionBackendContext"], Any] | None = None
    uninstall: Callable[["ExtensionBackendContext"], Any] | None = None

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        app.register_lifecycle_extender(extension.extension_id, self)

    def on_install(self, context: "ExtensionBackendContext") -> Any:
        if self.install is None:
            return None
        return self.install(context)

    def on_enable(self, context: "ExtensionBackendContext") -> Any:
        if self.enable is None:
            return None
        return self.enable(context)

    def on_disable(self, context: "ExtensionBackendContext") -> Any:
        if self.disable is None:
            return None
        return self.disable(context)

    def on_uninstall(self, context: "ExtensionBackendContext") -> Any:
        if self.uninstall is None:
            return None
        return self.uninstall(context)


@dataclass(frozen=True)
class FrontendExtender:
    admin_entry: str = ""
    forum_entry: str = ""
    common_entry: str = ""
    css_files: tuple[str, ...] = ()
    js_directories: tuple[str, ...] = ()
    preloads: tuple[Any, ...] = ()
    content_callbacks: tuple[Any, ...] = ()
    document_attributes: tuple[Any, ...] = ()
    title_driver: Any = None
    routes: tuple[ExtensionFrontendRouteDefinition, ...] = ()

    def css(self, path: str) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=tuple([*self.css_files, path]),
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=self.routes,
        )

    def js_directory(self, path: str) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=tuple([*self.js_directories, path]),
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=self.routes,
        )

    def preload(self, *items: Any) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=tuple([*self.preloads, *items]),
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=self.routes,
        )

    def content(self, callback: Any, priority: int = 0) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=tuple([
                *self.content_callbacks,
                {
                    "callback": callback,
                    "priority": int(priority),
                },
            ]),
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=self.routes,
        )

    def extra_document_attributes(self, attributes: Any) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=tuple([*self.document_attributes, attributes]),
            title_driver=self.title_driver,
            routes=self.routes,
        )

    def extra_document_classes(self, classes: Any) -> "FrontendExtender":
        return self.extra_document_attributes({"class": classes})

    def title(self, driver: Any) -> "FrontendExtender":
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=driver,
            routes=self.routes,
        )

    def remove_route(self, name: str, *, frontend: str = "forum") -> "FrontendExtender":
        normalized = str(name or "").strip()
        if not normalized:
            return self
        route = ExtensionFrontendRouteDefinition(
            path="",
            name=normalized,
            component="",
            frontend=str(frontend or "forum").strip() or "forum",
            removed=True,
        )
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=tuple([*self.routes, route]),
        )

    def route(
        self,
        path: str,
        name: str,
        component: str,
        *,
        frontend: str = "forum",
        title: str = "",
        description: str = "",
        preloads: tuple[Any, ...] = (),
        document_attributes: tuple[Any, ...] = (),
        head_tags: tuple[Any, ...] = (),
        requires_auth: bool = False,
        order: int = 100,
    ) -> "FrontendExtender":
        route = ExtensionFrontendRouteDefinition(
            path=str(path or "").strip(),
            name=str(name or "").strip(),
            component=str(component or "").strip(),
            frontend=str(frontend or "forum").strip() or "forum",
            title=str(title or "").strip(),
            description=str(description or "").strip(),
            preloads=tuple(preloads or ()),
            document_attributes=tuple(document_attributes or ()),
            head_tags=tuple(head_tags or ()),
            requires_auth=bool(requires_auth),
            order=int(order),
        )
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=self.preloads,
            content_callbacks=self.content_callbacks,
            document_attributes=self.document_attributes,
            title_driver=self.title_driver,
            routes=tuple([*self.routes, route]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(frontend, host: "ExtensionHost"):
            frontend.set_extension(
                extension_id,
                admin_entry=self.admin_entry or None,
                forum_entry=self.forum_entry or None,
                common_entry=self.common_entry or None,
                css=self.css_files,
                js_directories=self.js_directories,
                preloads=self.preloads,
                content_callbacks=self.content_callbacks,
                document_attributes=self.document_attributes,
                title_driver=self.title_driver,
            routes=tuple(
                    route if route.module_id else replace(route, module_id=extension_id)
                    for route in self.routes
                    if route.name and (route.removed or (route.path and route.component))
                ),
            )
            return frontend

        app.resolving("frontend", apply)


@dataclass(frozen=True)
class LocalesExtender:
    paths: tuple[str, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.paths:
            return

        extension_id = extension.extension_id

        def apply(locales, host: "ExtensionHost"):
            for path in self.paths:
                locales.register_path(extension_id, path)
            return locales

        app.resolving("locales", apply)


@dataclass(frozen=True)
class LanguagePackExtender:
    code: str = ""
    label: str = ""
    native_label: str = ""
    description: str = ""
    path: str = "locale"
    is_default: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        code = str(self.code or "").strip()
        label = str(self.label or "").strip()
        path = str(self.path or "").strip()
        if not code or not label:
            return

        extension_id = extension.extension_id
        definition = LanguagePackDefinition(
            code=code,
            label=label,
            native_label=str(self.native_label or label).strip(),
            module_id=extension_id,
            description=str(self.description or "").strip(),
            is_default=bool(self.is_default),
        )

        def apply_forum(forum, host: "ExtensionHost"):
            forum.register_external_module_id(extension_id)
            forum.register_language_pack(definition, extension_id=extension_id)
            return forum

        def apply_locales(locales, host: "ExtensionHost"):
            if path:
                locales.register_path(extension_id, path)
            return locales

        app.resolving("forum", apply_forum)
        if path:
            app.resolving("locales", apply_locales)


@dataclass(frozen=True)
class FormatterExtender:
    transforms: tuple[ExtensionFormatterCallback, ...] = ()
    configure_callbacks: tuple[Any, ...] = ()
    parse_callbacks: tuple[Any, ...] = ()
    render_callbacks: tuple[Any, ...] = ()
    unparse_callbacks: tuple[Any, ...] = ()

    def configure(self, callback: Any) -> "FormatterExtender":
        return FormatterExtender(
            transforms=self.transforms,
            configure_callbacks=tuple([*self.configure_callbacks, callback]),
            parse_callbacks=self.parse_callbacks,
            render_callbacks=self.render_callbacks,
            unparse_callbacks=self.unparse_callbacks,
        )

    def parse(self, callback: Any) -> "FormatterExtender":
        return FormatterExtender(
            transforms=self.transforms,
            configure_callbacks=self.configure_callbacks,
            parse_callbacks=tuple([*self.parse_callbacks, callback]),
            render_callbacks=self.render_callbacks,
            unparse_callbacks=self.unparse_callbacks,
        )

    def render(self, callback: Any) -> "FormatterExtender":
        return FormatterExtender(
            transforms=self.transforms,
            configure_callbacks=self.configure_callbacks,
            parse_callbacks=self.parse_callbacks,
            render_callbacks=tuple([*self.render_callbacks, callback]),
            unparse_callbacks=self.unparse_callbacks,
        )

    def unparse(self, callback: Any) -> "FormatterExtender":
        return FormatterExtender(
            transforms=self.transforms,
            configure_callbacks=self.configure_callbacks,
            parse_callbacks=self.parse_callbacks,
            render_callbacks=self.render_callbacks,
            unparse_callbacks=tuple([*self.unparse_callbacks, callback]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (
            self.transforms
            or self.configure_callbacks
            or self.parse_callbacks
            or self.render_callbacks
            or self.unparse_callbacks
        ):
            return

        extension_id = extension.extension_id

        def apply(formatters, host: "ExtensionHost"):
            for callback in self.configure_callbacks:
                formatters.register_configure(extension_id, self._resolve_callback(callback, host))
            for callback in self.parse_callbacks:
                formatters.register_parse(extension_id, self._resolve_callback(callback, host))
            for callback in (*self.transforms, *self.render_callbacks):
                formatters.register_render(extension_id, self._resolve_callback(callback, host))
            for callback in self.unparse_callbacks:
                formatters.register_unparse(extension_id, self._resolve_callback(callback, host))
            return formatters

        app.resolving("formatters", apply)

    @staticmethod
    def _resolve_callback(callback: Any, host: "ExtensionHost") -> Any:
        if isinstance(callback, str) or isinstance(callback, type):
            return wrap_callback(callback, host)
        return callback


@dataclass(frozen=True)
class LinkExtender:
    rel_callback: Any = None
    target_callback: Any = None

    def set_rel(self, callback: Any) -> "LinkExtender":
        return LinkExtender(
            rel_callback=callback,
            target_callback=self.target_callback,
        )

    def set_target(self, callback: Any) -> "LinkExtender":
        return LinkExtender(
            rel_callback=self.rel_callback,
            target_callback=callback,
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.rel_callback and not self.target_callback:
            return

        extension_id = extension.extension_id
        rel_callback = wrap_callback(self.rel_callback, app) if self.rel_callback else None
        target_callback = wrap_callback(self.target_callback, app) if self.target_callback else None

        def transform(html: str) -> str:
            from django.conf import settings
            from apps.core.link_formatter import apply_link_attribute_callbacks

            return apply_link_attribute_callbacks(
                html,
                site_url=getattr(settings, "FRONTEND_URL", ""),
                set_rel=rel_callback,
                set_target=target_callback,
            )

        def apply(formatters, host: "ExtensionHost"):
            formatters.register_transform(extension_id, transform)
            return formatters

        app.resolving("formatters", apply)


@dataclass(frozen=True)
class ResourceExtender:
    resources: tuple[Any, ...] = ()
    fields: tuple[ExtensionResourceFieldDefinition, ...] = ()
    field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    relationships: tuple[ExtensionResourceRelationshipDefinition, ...] = ()
    endpoints: tuple[ExtensionResourceEndpointDefinition, ...] = ()
    sorts: tuple[ExtensionResourceSortDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.resources or self.fields or self.field_mutators or self.relationships or self.endpoints or self.sorts):
            return

        extension_id = extension.extension_id

        def apply(resources, host: "ExtensionHost"):
            for definition in self.resources:
                resolved = resolve_container_value(definition, host)
                resources.register_resource(self._with_module_id(resolved, extension_id), extension_id=extension_id)
                self._register_api_resource_contract(host, resolved)
            for definition in self.fields:
                resources.register_field(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.field_mutators:
                resources.register_field_mutator(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.relationships:
                resources.register_relationship(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.endpoints:
                resources.register_endpoint(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            for definition in self.sorts:
                resources.register_sort(self._with_module_id(self._resolve_definition_callbacks(definition, host), extension_id), extension_id=extension_id)
            return resources

        app.resolving("resources", apply)

    @staticmethod
    def _register_api_resource_contract(host, resource: Any) -> None:
        resource_class = resource if isinstance(resource, type) else type(resource)
        if resource_class is type(None):
            return

        def add_resource(app, resources):
            output = list(resources or [])
            if resource_class not in output:
                output.append(resource_class)
            return output

        host.extend("bias.api.resources", add_resource)

    @staticmethod
    def _with_module_id(definition, extension_id: str):
        if isinstance(definition, type):
            return definition
        if not hasattr(definition, "module_id"):
            return definition
        if getattr(definition, "module_id", ""):
            return definition
        return replace(definition, module_id=extension_id)

    @staticmethod
    def _resolve_definition_callbacks(definition, host):
        replacements = {}
        for attr in (
            "resolver",
            "handler",
            "mutator",
            "setter",
            "validator",
            "condition",
            "before_hook",
            "after_hook",
            "meta_resolver",
            "links_resolver",
            "query_callback",
            "action_callback",
            "before_serialization_callback",
            "response_callback",
        ):
            if hasattr(definition, attr):
                value = getattr(definition, attr)
                if isinstance(value, str) or isinstance(value, type):
                    replacements[attr] = wrap_callback(value, host)
        return replace(definition, **replacements) if replacements else definition


@dataclass(frozen=True, init=False)
class ApiResourceExtender:
    resource: Any = None
    _fields: tuple[Any, ...] = ()
    _field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    _relationships: tuple[Any, ...] = ()
    _endpoints: tuple[Any, ...] = ()
    _sorts: tuple[Any, ...] = ()

    def __init__(
        self,
        resource: Any = None,
        fields: tuple[Any, ...] = (),
        field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = (),
        relationships: tuple[Any, ...] = (),
        endpoints: tuple[Any, ...] = (),
        sorts: tuple[Any, ...] = (),
    ) -> None:
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "_fields", tuple(fields or ()))
        object.__setattr__(self, "_field_mutators", tuple(field_mutators or ()))
        object.__setattr__(self, "_relationships", tuple(relationships or ()))
        object.__setattr__(self, "_endpoints", tuple(endpoints or ()))
        object.__setattr__(self, "_sorts", tuple(sorts or ()))

    @property
    def resource_name(self) -> str:
        if self.resource is not None:
            if isinstance(self.resource, str):
                return self.resource.strip()
            if isinstance(self.resource, ExtensionResourceObjectDefinition):
                return self._resource_object_name(self.resource.resource)
            return getattr(self.resource, "resource", "") or self._resource_object_name(self.resource)
        for definitions in (
            self._fields,
            self._relationships,
            self._endpoints,
            self._sorts,
            self._field_mutators,
        ):
            for definition in definitions:
                resource = getattr(definition, "resource", "")
                if resource:
                    return resource
        return ""

    @staticmethod
    def from_resource(resource) -> "ApiResourceExtender":
        return ApiResourceExtender(resource=resource)

    def fields(self, fields: Any = None, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        if fields is None:
            items = definitions
        else:
            items = (fields, *definitions)
        return self.fields_with(*items)

    def fields_with(self, *definitions: Any) -> "ApiResourceExtender":
        return ApiResourceExtender(
            resource=self.resource,
            fields=tuple([*self._fields, *definitions]),
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=self._sorts,
        )

    def fields_before(self, anchor: str, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        return self._field_mutators_with_operation("before", anchor, *definitions)

    def fields_after(self, anchor: str, *definitions: ExtensionResourceFieldDefinition) -> "ApiResourceExtender":
        return self._field_mutators_with_operation("after", anchor, *definitions)

    def remove_fields(self, *fields: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=field,
                module_id="",
                operation="remove",
                mutator=lambda current: current,
                condition=condition,
                kind="field",
            )
            for field in fields
        )
        return self.field(*definitions)

    def field(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_field_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=tuple([*self._field_mutators, *definitions]),
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=self._sorts,
        )

    def relationships(self, relationships: Any = None, *definitions: ExtensionResourceRelationshipDefinition) -> "ApiResourceExtender":
        if relationships is None:
            items = definitions
        else:
            items = (relationships, *definitions)
        return self.relationships_with(*items)

    def relationships_with(self, *definitions: Any) -> "ApiResourceExtender":
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=tuple([*self._relationships, *definitions]),
            endpoints=self._endpoints,
            sorts=self._sorts,
        )

    def model_relationship(
        self,
        name: str,
        *,
        resource_type: str = "",
        many: bool = False,
        description: str = "",
        select_related: tuple[str, ...] = (),
        prefetch_related: tuple[Any, ...] = (),
        preload_resolver: Callable[[dict], tuple[tuple[str, ...], tuple[Any, ...]]] | None = None,
        visible: Callable[[Any, dict], bool] | bool = True,
        includable: Callable[[dict], bool] | bool = True,
    ) -> "ApiResourceExtender":
        relationship_name = str(name or "").strip()
        if not relationship_name:
            return self

        def resolver(instance, context):
            from apps.core.extensions.runtime_access import resolve_runtime_model_relation

            return resolve_runtime_model_relation(
                instance,
                relationship_name,
                default=[] if many else None,
            )

        return self.relationships_with(
            ExtensionResourceRelationshipDefinition(
                resource=self.resource_name,
                relationship=relationship_name,
                module_id="",
                resolver=resolver,
                description=description,
                select_related=select_related,
                prefetch_related=prefetch_related,
                preload_resolver=preload_resolver,
                visible=visible,
                includable=includable,
                resource_type=resource_type,
                many=many,
            )
        )

    def relationships_before(
        self,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        return self._relationship_mutators_with_operation("before", anchor, *definitions)

    def relationships_after(
        self,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        return self._relationship_mutators_with_operation("after", anchor, *definitions)

    def endpoints(self, endpoints: Any = None, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        if endpoints is None:
            items = definitions
        else:
            items = (endpoints, *definitions)
        return self.endpoints_with(*items)

    def endpoints_with(self, *definitions: Any) -> "ApiResourceExtender":
        return self.endpoint(*definitions)

    def endpoints_before(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("before", anchor, *definitions)

    def endpoints_after(self, anchor: str, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("after", anchor, *definitions)

    def endpoints_before_all(self, *definitions: ExtensionResourceEndpointDefinition) -> "ApiResourceExtender":
        return self._endpoints_with_operation("before_all", "", *definitions)

    def remove_endpoints(self, *endpoints: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceEndpointDefinition(
                resource=self.resource_name,
                endpoint=endpoint,
                module_id="",
                operation="remove",
                condition=condition,
            )
            for endpoint in endpoints
        )
        return self.endpoint(*definitions)

    def endpoint(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_endpoint_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=tuple([*self._endpoints, *definitions]),
            sorts=self._sorts,
        )

    def add_default_include(self, endpoints, includes) -> "ApiResourceExtender":
        normalized_includes = tuple(self._normalize_names(includes))

        def mutate(endpoint):
            current = list(getattr(endpoint, "default_include", ()) or ())
            seen = set(current)
            for include in normalized_includes:
                if include and include not in seen:
                    seen.add(include)
                    current.append(include)
            return replace(endpoint, default_include=tuple(current))

        return self.endpoint(endpoints, mutate)

    def eager_load(self, endpoints, *items: Any) -> "ApiResourceExtender":
        def mutate(endpoint):
            return replace(endpoint, eager_load=tuple([
                *(getattr(endpoint, "eager_load", ()) or ()),
                *items,
            ]))

        return self.endpoint(endpoints, mutate)

    def eager_load_when_included(self, endpoints, include: str, *items: Any) -> "ApiResourceExtender":
        normalized_include = str(include or "").strip()
        if not normalized_include:
            return self

        def mutate(endpoint):
            return replace(endpoint, eager_load_when_included_rules=tuple([
                *(getattr(endpoint, "eager_load_when_included_rules", ()) or ()),
                (normalized_include, tuple(items or ())),
            ]))

        return self.endpoint(endpoints, mutate)

    def eager_load_where(self, endpoints, relation: str, callback: Callable[[Any, dict], Any]) -> "ApiResourceExtender":
        normalized_relation = str(relation or "").strip()
        if not normalized_relation or not callable(callback):
            return self

        def mutate(endpoint):
            return replace(endpoint, eager_load_where_rules=tuple([
                *(getattr(endpoint, "eager_load_where_rules", ()) or ()),
                (normalized_relation, callback),
            ]))

        return self.endpoint(endpoints, mutate)

    def default_sort(self, endpoints, sort: str) -> "ApiResourceExtender":
        normalized_sort = str(sort or "").strip()

        def mutate(endpoint):
            return replace(endpoint, default_sort=normalized_sort)

        return self.endpoint(endpoints, mutate)

    def sorts(self, sorts: Any = None, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        if sorts is None:
            items = definitions
        else:
            items = (sorts, *definitions)
        return self.sort(*items)

    def sorts_with(self, *definitions: Any) -> "ApiResourceExtender":
        return self.sort(*definitions)

    def sorts_before(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("before", anchor, *definitions)

    def sorts_after(self, anchor: str, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("after", anchor, *definitions)

    def sorts_before_all(self, *definitions: ExtensionResourceSortDefinition) -> "ApiResourceExtender":
        return self._sorts_with_operation("before_all", "", *definitions)

    def remove_sorts(self, *sorts: str, condition: Callable[[dict], bool] | None = None) -> "ApiResourceExtender":
        definitions = tuple(
            ExtensionResourceSortDefinition(
                resource=self.resource_name,
                sort=sort,
                module_id="",
                operation="remove",
                condition=condition,
            )
            for sort in sorts
        )
        return self.sort(*definitions)

    def sort(self, *definitions) -> "ApiResourceExtender":
        if self._is_named_mutator_call(definitions):
            definitions = self._named_sort_mutators(definitions[0], definitions[1])
        return ApiResourceExtender(
            resource=self.resource,
            fields=self._fields,
            field_mutators=self._field_mutators,
            relationships=self._relationships,
            endpoints=self._endpoints,
            sorts=tuple([*self._sorts, *definitions]),
        )

    def _field_mutators_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceFieldDefinition,
    ) -> "ApiResourceExtender":
        mutators = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=definition.resource,
                field=definition.field,
                module_id=definition.module_id,
                operation=operation,
                anchor=anchor,
                mutator=lambda current, value=definition: value,
                kind="field",
            )
            for definition in definitions
        )
        return self.field(*mutators)

    def _named_field_mutators(self, fields, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=self.resource_name,
                field=field,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for field in self._normalize_names(fields)
        )

    def _named_endpoint_mutators(self, endpoints, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceEndpointDefinition(
                resource=self.resource_name,
                endpoint=endpoint,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for endpoint in self._normalize_names(endpoints)
        )

    def _named_sort_mutators(self, sorts, mutator: Callable[[Any], Any]):
        return tuple(
            ExtensionResourceSortDefinition(
                resource=self.resource_name,
                sort=sort,
                module_id="",
                operation="mutate",
                mutator=mutator,
            )
            for sort in self._normalize_names(sorts)
        )

    def _relationship_mutators_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceRelationshipDefinition,
    ) -> "ApiResourceExtender":
        mutators = tuple(
            ExtensionResourceFieldMutatorDefinition(
                resource=definition.resource,
                field=definition.relationship,
                module_id=definition.module_id,
                operation=operation,
                anchor=anchor,
                mutator=lambda current, value=definition: value,
                kind="relationship",
            )
            for definition in definitions
        )
        return self.field(*mutators)

    def _endpoints_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceEndpointDefinition,
    ) -> "ApiResourceExtender":
        endpoints = tuple(
            replace(definition, operation=operation, anchor=anchor)
            for definition in definitions
        )
        return self.endpoint(*endpoints)

    def _sorts_with_operation(
        self,
        operation: str,
        anchor: str,
        *definitions: ExtensionResourceSortDefinition,
    ) -> "ApiResourceExtender":
        sorts = tuple(
            replace(definition, operation=operation, anchor=anchor)
            for definition in definitions
        )
        return self.sort(*sorts)

    @staticmethod
    def _is_named_mutator_call(definitions) -> bool:
        if len(definitions) != 2 or not callable(definitions[1]):
            return False
        names = definitions[0]
        if isinstance(names, str):
            return True
        if isinstance(names, (tuple, list, set)):
            return all(isinstance(name, str) for name in names)
        return False

    @staticmethod
    def _normalize_names(names) -> tuple[str, ...]:
        if isinstance(names, str):
            return (names,)
        return tuple(names)

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        resources = () if isinstance(self.resource, str) else ((self.resource,) if self.resource is not None else ())
        fields = self._normalize_resource_fields(self._resolve_definition_groups(self._fields, app))
        relationships = self._normalize_resource_relationships(self._resolve_definition_groups(self._relationships, app))
        endpoints = self._normalize_resource_endpoints(self._resolve_definition_groups(self._endpoints, app))
        sorts = self._normalize_resource_sorts(self._resolve_definition_groups(self._sorts, app))
        ResourceExtender(
            resources=resources,
            fields=fields,
            field_mutators=self._field_mutators,
            relationships=relationships,
            endpoints=endpoints,
            sorts=sorts,
        ).extend(app, extension)

    @staticmethod
    def _resolve_definition_groups(items: tuple[Any, ...], host) -> tuple[Any, ...]:
        output = []
        for item in items:
            if isinstance(item, str) or isinstance(item, type):
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

    def _normalize_resource_fields(self, items: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(
            ResourceRegistry._field_to_definition(self.resource_name, item)
            if isinstance(item, ResourceField) and not isinstance(item, ResourceRelationship)
            else item
            for item in items
        )

    def _normalize_resource_relationships(self, items: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(
            ResourceRegistry._relationship_to_definition(self.resource_name, item)
            if isinstance(item, ResourceRelationship)
            else item
            for item in items
        )

    def _normalize_resource_endpoints(self, items: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(
            ResourceRegistry._endpoint_to_definition(self.resource_name, item)
            if isinstance(item, ResourceEndpoint)
            else item
            for item in items
        )

    def _normalize_resource_sorts(self, items: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(
            ResourceRegistry._sort_to_definition(self.resource_name, item)
            if isinstance(item, ResourceSort)
            else item
            for item in items
        )

    @staticmethod
    def _resource_object_name(resource) -> str:
        if resource is None:
            return ""
        resource_object = resource
        if isinstance(resource, type):
            try:
                resource_object = resource()
            except TypeError:
                return ""
        type_method = getattr(resource_object, "type", None)
        if callable(type_method):
            return str(type_method() or "").strip()
        return ""


@dataclass(frozen=True)
class ModelExtender:
    definitions: tuple[ExtensionModelDefinition, ...] = ()
    visibility: tuple[ExtensionModelVisibilityDefinition, ...] = ()
    relations: tuple[ExtensionModelRelationDefinition, ...] = ()
    casts: tuple[ExtensionModelCastDefinition, ...] = ()
    defaults: tuple[ExtensionModelDefaultDefinition, ...] = ()
    model: Any = None

    def owns(
        self,
        model: Any = None,
        *,
        key: str = "",
        description: str = "",
    ) -> "ModelExtender":
        resolved_model = model or self.model
        if resolved_model is None:
            raise ValueError("ModelExtender ownership requires a model")
        owner_key = str(key or "").strip() or _model_definition_key(resolved_model)
        return ModelExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionModelDefinition(
                    model=resolved_model,
                    key=owner_key,
                    handler=resolved_model,
                    kind="owner",
                    description=str(description or "").strip(),
                ),
            ]),
            visibility=self.visibility,
            relations=self.relations,
            casts=self.casts,
            defaults=self.defaults,
            model=self.model,
        )

    def relationship(self, *definitions: ExtensionModelRelationDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=tuple([*self.relations, *definitions]),
            casts=self.casts,
            defaults=self.defaults,
            model=self.model,
        )

    def belongs_to(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "belongsTo",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=owner_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def belongs_to_many(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "belongsToMany",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=owner_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def has_one(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        local_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "hasOne",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=local_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def has_many(
        self,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        local_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        return self._simple_relation(
            "hasMany",
            name,
            related_model,
            model=model,
            foreign_key=foreign_key,
            owner_key=local_key,
            resolver=resolver,
            description=description,
            inject_attribute=inject_attribute,
        )

    def cast(self, *definitions: ExtensionModelCastDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=self.relations,
            casts=tuple([*self.casts, *definitions]),
            defaults=self.defaults,
            model=self.model,
        )

    def default(self, *definitions: ExtensionModelDefaultDefinition) -> "ModelExtender":
        return ModelExtender(
            definitions=self.definitions,
            visibility=self.visibility,
            relations=self.relations,
            casts=self.casts,
            defaults=tuple([*self.defaults, *definitions]),
            model=self.model,
        )

    def _simple_relation(
        self,
        relation_type: str,
        name: str,
        related_model: Any,
        *,
        model: Any = None,
        foreign_key: str = "",
        owner_key: str = "",
        resolver: Callable[[Any], Any] | None = None,
        description: str = "",
        inject_attribute: bool = True,
    ) -> "ModelExtender":
        source_model = model or self.model
        if source_model is None:
            raise ValueError("ModelExtender simple relations require a source model")
        relation_resolver = resolver or (lambda instance: getattr(instance, name, None))
        return self.relationship(
            ExtensionModelRelationDefinition(
                model=source_model,
                name=name,
                resolver=relation_resolver,
                relation_type=relation_type,
                related_model=related_model,
                foreign_key=foreign_key,
                owner_key=owner_key,
                description=description,
                inject_attribute=inject_attribute,
            )
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.definitions or self.visibility or self.relations or self.casts or self.defaults):
            return

        extension_id = extension.extension_id

        def apply(models, host: "ExtensionHost"):
            for definition in self.definitions:
                models.register(extension_id, definition)
            for definition in self.visibility:
                models.register_visibility(extension_id, definition)
            for definition in self.relations:
                models.register_relation(extension_id, definition)
            for definition in self.casts:
                models.register_cast(extension_id, definition)
            for definition in self.defaults:
                models.register_default(extension_id, definition)
            return models

        app.resolving("models", apply)


@dataclass(frozen=True)
class ModelVisibilityExtender:
    definitions: tuple[ExtensionModelVisibilityDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        ModelExtender(visibility=self.definitions).extend(app, extension)


@dataclass(frozen=True)
class ModelPrivateExtender:
    model: Any
    checkers: tuple[Any, ...] = ()

    def checker(self, callback: Any) -> "ModelPrivateExtender":
        if callback is None:
            return self
        return ModelPrivateExtender(
            model=self.model,
            checkers=tuple([*self.checkers, callback]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if self.model is None or not self.checkers:
            return
        extension_id = extension.extension_id

        def apply(models, host: "ExtensionHost"):
            for index, checker in enumerate(self.checkers):
                models.register_private_checker(extension_id, ExtensionModelDefinition(
                    model=self.model,
                    key=f"private_checker:{index}",
                    handler=wrap_callback(checker, host),
                    kind="private_checker",
                    description="Model privacy checker",
                ))
            return models

        app.resolving("models", apply)


def _model_definition_key(model: Any) -> str:
    meta = getattr(model, "_meta", None)
    label = str(getattr(meta, "label_lower", "") or "").strip()
    if label:
        return label
    module = str(getattr(model, "__module__", "") or "").strip()
    name = str(getattr(model, "__name__", "") or getattr(model, "__qualname__", "") or "").strip()
    return ".".join(item for item in (module, name) if item) or str(model)


@dataclass(frozen=True)
class ModelUrlExtender:
    model: Any
    slug_drivers: tuple[ExtensionModelSlugDriverDefinition, ...] = ()

    def add_slug_driver(
        self,
        identifier: str,
        driver: Any,
        *,
        field: str = "slug",
        source_field: str = "name",
        max_length: int | None = None,
        description: str = "",
    ) -> "ModelUrlExtender":
        return ModelUrlExtender(
            model=self.model,
            slug_drivers=tuple([
                *self.slug_drivers,
                ExtensionModelSlugDriverDefinition(
                    model=self.model,
                    identifier=str(identifier or "").strip() or "default",
                    driver=driver,
                    field=str(field or "slug").strip() or "slug",
                    source_field=str(source_field or "name").strip() or "name",
                    max_length=max_length,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.slug_drivers:
            return

        extension_id = extension.extension_id

        def apply(model_urls, host: "ExtensionHost"):
            for definition in self.slug_drivers:
                model_urls.register_slug_driver(extension_id, definition)
            return model_urls

        app.resolving("model.urls", apply)


@dataclass(frozen=True)
class SearchDriverExtender:
    driver: Any = "database"
    drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()

    def __init__(self, driver: Any = "database", drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()) -> None:
        object.__setattr__(self, "driver", driver)
        object.__setattr__(self, "drivers", tuple(drivers or ()))

    def add_searcher(self, model: Any, searcher: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(model),
            driver=self.driver,
            model=model,
            searcher=searcher,
        ))

    def add_filter(self, searcher: Any, filter_definition: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            driver_filters=(filter_definition,),
        ))

    def replace_filter(self, searcher: Any, replace: str, filter_definition: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            replace_filters=((replace, filter_definition),),
        ))

    def set_fulltext(self, searcher: Any, fulltext: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            fulltext=fulltext,
        ))

    def add_mutator(self, searcher: Any, callback: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(searcher),
            driver=self.driver,
            searcher=searcher,
            driver_mutators=(callback,),
        ))

    def add_indexer(self, model: Any, indexer: Any, *, target: str = "") -> "SearchDriverExtender":
        return self._append_definition(ExtensionSearchDriverDefinition(
            target=target or self._target_from_model(model),
            driver=self.driver,
            model=model,
            indexers=(indexer,),
        ))

    def _append_definition(self, definition: ExtensionSearchDriverDefinition) -> "SearchDriverExtender":
        return SearchDriverExtender(driver=self.driver, drivers=tuple([*self.drivers, definition]))

    @staticmethod
    def _target_from_model(model: Any) -> str:
        name = getattr(model, "__name__", "") if model is not None else ""
        return str(name or "").strip()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.drivers:
            return

        extension_id = extension.extension_id

        def apply(search, host: "ExtensionHost"):
            for definition in self.drivers:
                search.register_driver(extension_id, definition)
            return search

        app.resolving("search", apply)


@dataclass(frozen=True)
class SearchIndexExtender:
    indexers: tuple[tuple[Any, Any], ...] = ()

    def indexer(self, model: Any, indexer: Any) -> "SearchIndexExtender":
        if model is None or indexer is None:
            return self
        return SearchIndexExtender(indexers=tuple([*self.indexers, (model, indexer)]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.indexers:
            return
        extension_id = extension.extension_id

        def apply(search, host: "ExtensionHost"):
            view = host._get_or_create_runtime_view(extension_id)
            for model, indexer in self.indexers:
                search.register_indexer(model, indexer)
                view.search_drivers = tuple([*view.search_drivers, ExtensionSearchDriverDefinition(
                    target=str(getattr(model, "__name__", "") or "").strip(),
                    driver="database",
                    model=model,
                    indexers=(indexer,),
                )])
            return search

        app.resolving("search", apply)


@dataclass(frozen=True)
class ValidatorExtender:
    definitions: tuple[ExtensionValidatorDefinition, ...] = ()

    def validator(
        self,
        key: str,
        target: str,
        callback: Callable[[Any, dict], Any],
        *,
        description: str = "",
    ) -> "ValidatorExtender":
        definition = ExtensionValidatorDefinition(
            key=str(key or "").strip(),
            target=str(target or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
        )
        return ValidatorExtender(definitions=tuple([*self.definitions, definition]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return
        extension_id = extension.extension_id

        def apply(validators, host: "ExtensionHost"):
            for definition in self.definitions:
                if not definition.key or not definition.target:
                    continue
                validators.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return validators

        app.resolving("validators", apply)


@dataclass(frozen=True)
class MailExtender:
    definitions: tuple[ExtensionMailDefinition, ...] = ()

    def driver(
        self,
        key: str,
        callback: Callable[[Any, dict], Any],
        *,
        description: str = "",
    ) -> "MailExtender":
        definition = ExtensionMailDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
        )
        return MailExtender(definitions=tuple([*self.definitions, definition]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return
        extension_id = extension.extension_id

        def apply(mail, host: "ExtensionHost"):
            for definition in self.definitions:
                if not definition.key:
                    continue
                mail.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return mail

        app.resolving("mail", apply)


@dataclass(frozen=True)
class ViewExtender:
    namespaces: tuple[ExtensionViewNamespaceDefinition, ...] = ()

    def namespace(
        self,
        namespace: str,
        *hints: str,
        description: str = "",
        order: int = 100,
    ) -> "ViewExtender":
        normalized_hints = tuple(str(item or "").strip() for item in hints if str(item or "").strip())
        return ViewExtender(namespaces=tuple([*self.namespaces, ExtensionViewNamespaceDefinition(
            namespace=str(namespace or "").strip(),
            hints=normalized_hints,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def extend_namespace(
        self,
        namespace: str,
        *hints: str,
        description: str = "",
        order: int = 100,
    ) -> "ViewExtender":
        normalized_hints = tuple(str(item or "").strip() for item in hints if str(item or "").strip())
        return ViewExtender(namespaces=tuple([*self.namespaces, ExtensionViewNamespaceDefinition(
            namespace=str(namespace or "").strip(),
            hints=normalized_hints,
            description=str(description or "").strip(),
            order=int(order),
            prepend=True,
        )]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.namespaces:
            return
        extension_id = extension.extension_id

        def apply(views, host: "ExtensionHost"):
            for definition in self.namespaces:
                views.namespace(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return views

        app.resolving("views", apply)


@dataclass(frozen=True)
class EventListenersExtender:
    listeners: tuple[ExtensionEventListenerDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.listeners:
            return

        extension_id = extension.extension_id

        def apply(events, host: "ExtensionHost"):
            for listener in self.listeners:
                events.register_listener(extension_id, listener)
            return events

        app.resolving("events", apply)


@dataclass(frozen=True)
class SignalExtender:
    definitions: tuple[ExtensionSignalDefinition, ...] = ()

    def connect(
        self,
        signal: Any,
        receiver: Any,
        *,
        sender: Any = None,
        dispatch_uid: str = "",
        weak: bool = False,
        description: str = "",
        order: int = 100,
    ) -> "SignalExtender":
        return SignalExtender(tuple([
            *self.definitions,
            ExtensionSignalDefinition(
                signal=signal,
                receiver=receiver,
                sender=sender,
                dispatch_uid=str(dispatch_uid or "").strip(),
                weak=bool(weak),
                description=str(description or "").strip(),
                order=int(order),
            ),
        ]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return

        extension_id = extension.extension_id

        def apply(signals, host: "ExtensionHost"):
            for definition in self.definitions:
                receiver = definition.receiver
                if isinstance(receiver, str) or isinstance(receiver, type):
                    receiver = wrap_callback(receiver, host)
                    definition = replace(definition, receiver=receiver)
                signals.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return signals

        app.resolving("signals", apply)


@dataclass(frozen=True)
class RealtimeExtender:
    included: tuple[ExtensionRealtimeIncludedDefinition, ...] = ()

    def included_payload(self, key: str, handler: Any, *, description: str = "") -> "RealtimeExtender":
        return RealtimeExtender(
            included=tuple([
                *self.included,
                ExtensionRealtimeIncludedDefinition(
                    key=str(key or "").strip(),
                    handler=handler,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.included:
            return

        extension_id = extension.extension_id

        def apply(realtime, host: "ExtensionHost"):
            for definition in self.included:
                handler = definition.handler
                if isinstance(handler, str) or isinstance(handler, type):
                    handler = wrap_callback(handler, host)
                    definition = replace(definition, handler=handler)
                realtime.register_included_enricher(extension_id, definition)
            return realtime

        app.resolving("realtime", apply)


@dataclass(frozen=True)
class DiscussionLifecycleExtender:
    definitions: tuple[ExtensionDiscussionLifecycleDefinition, ...] = ()

    def handler(
        self,
        key: str,
        *,
        prepare_create: Any = None,
        apply_create: Any = None,
        prepare_update: Any = None,
        apply_update: Any = None,
        prepare_delete: Any = None,
        apply_delete: Any = None,
        apply_hidden: Any = None,
        apply_approved: Any = None,
        apply_rejected: Any = None,
        description: str = "",
    ) -> "DiscussionLifecycleExtender":
        return DiscussionLifecycleExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionDiscussionLifecycleDefinition(
                    key=str(key or "").strip(),
                    prepare_create=prepare_create,
                    apply_create=apply_create,
                    prepare_update=prepare_update,
                    apply_update=apply_update,
                    prepare_delete=prepare_delete,
                    apply_delete=apply_delete,
                    apply_hidden=apply_hidden,
                    apply_approved=apply_approved,
                    apply_rejected=apply_rejected,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return

        extension_id = extension.extension_id

        def apply(discussion_lifecycle, host: "ExtensionHost"):
            for definition in self.definitions:
                replacements = {}
                for attr in (
                    "prepare_create",
                    "apply_create",
                    "prepare_update",
                    "apply_update",
                    "prepare_delete",
                    "apply_delete",
                    "apply_hidden",
                    "apply_approved",
                    "apply_rejected",
                ):
                    value = getattr(definition, attr)
                    if isinstance(value, str) or isinstance(value, type):
                        replacements[attr] = wrap_callback(value, host)
                if replacements:
                    definition = replace(definition, **replacements)
                discussion_lifecycle.register(extension_id, definition)
            return discussion_lifecycle

        app.resolving("discussion.lifecycle", apply)


@dataclass(frozen=True)
class PostLifecycleExtender:
    definitions: tuple[ExtensionPostLifecycleDefinition, ...] = ()

    def handler(
        self,
        key: str,
        *,
        apply_created: Any = None,
        apply_updated: Any = None,
        apply_approved: Any = None,
        apply_hidden: Any = None,
        prepare_delete: Any = None,
        apply_deleted: Any = None,
        description: str = "",
    ) -> "PostLifecycleExtender":
        return PostLifecycleExtender(
            definitions=tuple([
                *self.definitions,
                ExtensionPostLifecycleDefinition(
                    key=str(key or "").strip(),
                    apply_created=apply_created,
                    apply_updated=apply_updated,
                    apply_approved=apply_approved,
                    apply_hidden=apply_hidden,
                    prepare_delete=prepare_delete,
                    apply_deleted=apply_deleted,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return

        extension_id = extension.extension_id

        def apply(post_lifecycle, host: "ExtensionHost"):
            for definition in self.definitions:
                replacements = {}
                for attr in (
                    "apply_created",
                    "apply_updated",
                    "apply_approved",
                    "apply_hidden",
                    "prepare_delete",
                    "apply_deleted",
                ):
                    value = getattr(definition, attr)
                    if isinstance(value, str) or isinstance(value, type):
                        replacements[attr] = wrap_callback(value, host)
                if replacements:
                    definition = replace(definition, **replacements)
                post_lifecycle.register(extension_id, definition)
            return post_lifecycle

        app.resolving("post.lifecycle", apply)


@dataclass(frozen=True)
class SettingsExtender:
    fields: tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    expose_to_forum: tuple[str, ...] = ()
    generated_page: bool = True
    defaults: tuple[ExtensionSettingDefaultDefinition, ...] = ()
    reset_rules: tuple[ExtensionSettingResetDefinition, ...] = ()
    frontend_cache_keys: tuple[str, ...] = ()
    theme_variables: tuple[ExtensionSettingThemeVariableDefinition, ...] = ()
    forum_serializations: tuple[ExtensionSettingForumSerializationDefinition, ...] = ()

    def default(self, key: str, value: Any) -> "SettingsExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=tuple([*self.defaults, ExtensionSettingDefaultDefinition(normalized_key, value)]),
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def reset_when(self, key: str, callback: Any) -> "SettingsExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=tuple([*self.reset_rules, ExtensionSettingResetDefinition(normalized_key, callback)]),
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def reset_frontend_cache_for(self, *keys: str) -> "SettingsExtender":
        normalized_keys = tuple(
            key
            for key in (str(item or "").strip() for item in keys)
            if key
        )
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=tuple(dict.fromkeys([*self.frontend_cache_keys, *normalized_keys])),
            theme_variables=self.theme_variables,
            forum_serializations=self.forum_serializations,
        )

    def theme_variable(self, name: str, key: str, callback: Any = None) -> "SettingsExtender":
        normalized_name = str(name or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_name or not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=tuple([
                *self.theme_variables,
                ExtensionSettingThemeVariableDefinition(normalized_name, normalized_key, callback),
            ]),
            forum_serializations=self.forum_serializations,
        )

    def serialize_to_forum(self, attribute: str, key: str, callback: Any = None) -> "SettingsExtender":
        normalized_attribute = str(attribute or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_attribute or not normalized_key:
            return self
        return SettingsExtender(
            fields=self.fields,
            expose_to_forum=self.expose_to_forum,
            generated_page=self.generated_page,
            defaults=self.defaults,
            reset_rules=self.reset_rules,
            frontend_cache_keys=self.frontend_cache_keys,
            theme_variables=self.theme_variables,
            forum_serializations=tuple([
                *self.forum_serializations,
                ExtensionSettingForumSerializationDefinition(normalized_attribute, normalized_key, callback),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(settings, host: "ExtensionHost"):
            reset_rules = tuple(
                replace(definition, callback=wrap_callback(definition.callback, host))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.reset_rules
            )
            theme_variables = tuple(
                replace(definition, callback=wrap_callback(definition.callback, host))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.theme_variables
            )
            forum_serializations = tuple(
                replace(definition, callback=wrap_callback(definition.callback, host))
                if isinstance(definition.callback, (str, type))
                else definition
                for definition in self.forum_serializations
            )
            settings.register_fields(
                extension_id,
                self.fields,
                expose_to_forum=self.expose_to_forum,
                generated_page=self.generated_page,
                defaults=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in self.defaults
                ),
                reset_when=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in reset_rules
                ),
                reset_frontend_cache_for=self.frontend_cache_keys,
                theme_variables=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in theme_variables
                ),
                forum_serializations=tuple(
                    replace(definition, module_id=definition.module_id or extension_id)
                    for definition in forum_serializations
                ),
            )
            return settings

        app.resolving("settings", apply)


@dataclass(frozen=True)
class AdminSurfaceExtender:
    permissions: tuple[PermissionDefinition, ...] = ()
    admin_pages: tuple[AdminPageDefinition, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()
    generated_permissions_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.permissions:
                forum.register_permission(definition, extension_id=extension_id)
            for definition in self.admin_pages:
                forum.register_admin_page(definition, extension_id=extension_id)
            return forum

        if self.permissions or self.admin_pages:
            app.resolving("forum", apply)
        if self.permissions_pages or self.operations_pages:
            def apply_pages(frontend, host: "ExtensionHost"):
                host.register_admin_surface_pages(
                    extension,
                    permissions_pages=self.permissions_pages,
                    operations_pages=self.operations_pages,
                )
                return frontend

            app.resolving("frontend", apply_pages)
        if self.generated_permissions_page:
            def apply_actions(actions, host: "ExtensionHost"):
                actions.mark_generated_permissions_page(extension_id)
                return actions

            app.resolving("actions", apply_actions)


@dataclass(frozen=True)
class NotificationsExtender:
    notification_types: tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.notification_types or self.user_preferences):
            return

        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.notification_types:
                forum.register_notification_type(definition, extension_id=extension_id)
            for definition in self.user_preferences:
                forum.register_user_preference(definition, extension_id=extension_id)
            return forum

        app.resolving("forum", apply)


@dataclass(frozen=True)
class PostExtender:
    post_types: tuple[PostTypeDefinition, ...] = ()

    def type(
        self,
        post_type: Any,
        *,
        code: str = "",
        label: str = "",
        description: str = "",
        icon: str = "far fa-comment",
        is_default: bool = False,
        is_stream_visible: bool = True,
        counts_toward_discussion: bool = True,
        counts_toward_user: bool = True,
        searchable: bool = True,
    ) -> "PostExtender":
        definition = post_type if isinstance(post_type, PostTypeDefinition) else PostTypeDefinition(
            code=code or self._post_type_code(post_type),
            label=label or self._post_type_label(post_type),
            module_id="",
            description=description or str(getattr(post_type, "description", "") or ""),
            icon=icon or str(getattr(post_type, "icon", "") or "far fa-comment"),
            is_default=bool(is_default or getattr(post_type, "is_default", False)),
            is_stream_visible=bool(is_stream_visible),
            counts_toward_discussion=bool(counts_toward_discussion),
            counts_toward_user=bool(counts_toward_user),
            searchable=bool(searchable),
        )
        if not definition.code:
            return self
        return PostExtender(post_types=tuple([*self.post_types, definition]))

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.post_types:
            return
        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            forum.register_external_module_id(extension_id)
            for definition in self.post_types:
                forum.register_post_type(replace(definition, module_id=definition.module_id or extension_id), extension_id=extension_id)
            return forum

        app.resolving("forum", apply)

    @staticmethod
    def _post_type_code(post_type: Any) -> str:
        return str(
            getattr(post_type, "code", "")
            or getattr(post_type, "type", "")
            or getattr(post_type, "post_type", "")
            or getattr(post_type, "__name__", "")
        ).strip()

    @staticmethod
    def _post_type_label(post_type: Any) -> str:
        return str(
            getattr(post_type, "label", "")
            or getattr(post_type, "name", "")
            or PostExtender._post_type_code(post_type)
        ).strip()


@dataclass(frozen=True)
class UserExtender:
    definitions: tuple[ExtensionSystemHookDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()

    def display_name_driver(self, identifier: str, driver: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("display_name_driver", {
            "identifier": str(identifier or "").strip(),
            "driver": driver,
            "description": str(description or "").strip(),
        }, order=order)

    def avatar_driver(self, identifier: str, driver: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("avatar_driver", {
            "identifier": str(identifier or "").strip(),
            "driver": driver,
            "description": str(description or "").strip(),
        }, order=order)

    def permission_groups(self, callback: Any, *, description: str = "", order: int = 100) -> "UserExtender":
        return self._with_definition("permission_groups", {
            "callback": callback,
            "description": str(description or "").strip(),
        }, order=order)

    def register_preference(
        self,
        key: str,
        transformer: Any = None,
        default: Any = None,
        *,
        label: str = "",
        description: str = "",
        category: str = "notification",
    ) -> "UserExtender":
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self
        preference = UserPreferenceDefinition(
            key=normalized_key,
            label=str(label or normalized_key).strip(),
            module_id="",
            description=str(description or "").strip(),
            category=str(category or "notification").strip() or "notification",
            default_value=bool(default),
        )
        extender = UserExtender(
            definitions=self.definitions,
            user_preferences=tuple([*self.user_preferences, preference]),
        )
        if transformer is None:
            return extender
        return extender._with_definition("preference_transformer", {
            "key": normalized_key,
            "transformer": transformer,
            "default": default,
        })

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (self.definitions or self.user_preferences):
            return
        extension_id = extension.extension_id

        def apply_forum(forum, host: "ExtensionHost"):
            forum.register_external_module_id(extension_id)
            for definition in self.user_preferences:
                forum.register_user_preference(replace(definition, module_id=definition.module_id or extension_id), extension_id=extension_id)
            return forum

        def apply_user(user, host: "ExtensionHost"):
            for definition in self.definitions:
                user.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return user

        if self.user_preferences:
            app.resolving("forum", apply_forum)
        if self.definitions:
            app.resolving("user", apply_user)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "UserExtender":
        return UserExtender(
            definitions=tuple([*self.definitions, ExtensionSystemHookDefinition(
                key=key,
                callback=payload,
                order=int(order),
            )]),
            user_preferences=self.user_preferences,
        )


@dataclass(frozen=True)
class ForumCapabilitiesExtender:
    post_types: tuple[PostTypeDefinition, ...] = ()
    search_filters: tuple[SearchFilterDefinition, ...] = ()
    discussion_list_queries: tuple[DiscussionListQueryDefinition, ...] = ()
    discussion_sorts: tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: tuple[DiscussionListFilterDefinition, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not (
            self.post_types
            or self.search_filters
            or self.discussion_list_queries
            or self.discussion_sorts
            or self.discussion_list_filters
        ):
            return

        extension_id = extension.extension_id

        def apply(forum, host: "ExtensionHost"):
            for definition in self.post_types:
                forum.register_post_type(definition, extension_id=extension_id)
            for definition in self.search_filters:
                forum.register_search_filter(definition, extension_id=extension_id)
            for definition in self.discussion_list_queries:
                forum.register_discussion_list_query(definition, extension_id=extension_id)
            for definition in self.discussion_sorts:
                forum.register_discussion_sort(definition, extension_id=extension_id)
            for definition in self.discussion_list_filters:
                forum.register_discussion_list_filter(definition, extension_id=extension_id)
            return forum

        app.resolving("forum", apply)


@dataclass(frozen=True)
class RuntimeActionsExtender:
    actions: tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    generated_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(actions, host: "ExtensionHost"):
            actions.register_runtime_actions(
                extension_id,
                self.actions,
                generated_page=self.generated_page,
            )
            return actions

        app.resolving("actions", apply)


@dataclass(frozen=True)
class AdminNavigationExtender:
    actions: tuple[ExtensionAdminActionDefinition, ...] = ()
    generated_permissions_page: bool = False
    generated_operations_page: bool = False

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        extension_id = extension.extension_id

        def apply(actions, host: "ExtensionHost"):
            actions.register_admin_actions(
                extension_id,
                self.actions,
                generated_permissions_page=self.generated_permissions_page,
                generated_operations_page=self.generated_operations_page,
            )
            return actions

        app.resolving("actions", apply)


@dataclass(frozen=True)
class ServiceProviderExtender:
    key: str
    provider: Any
    singleton: bool = True

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if self.provider is None:
            return
        extension_id = extension.extension_id

        def apply(providers, host: "ExtensionHost"):
            host.register(
                self.provider,
                key=self.key,
                extension_id=extension_id,
                singleton=self.singleton,
            )
            return providers

        app.resolving("providers", apply)


@dataclass(frozen=True)
class SystemHookExtender:
    service_key: str
    definitions: tuple[ExtensionSystemHookDefinition, ...] = ()

    def hook(
        self,
        key: str,
        callback: Any,
        *,
        description: str = "",
        order: int = 100,
    ) -> "SystemHookExtender":
        return SystemHookExtender(
            service_key=self.service_key,
            definitions=tuple([*self.definitions, ExtensionSystemHookDefinition(
                key=str(key or "").strip(),
                callback=callback,
                description=str(description or "").strip(),
                order=int(order),
            )]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.definitions:
            return
        extension_id = extension.extension_id
        service_key = str(self.service_key or "").strip()
        if not service_key:
            return

        def apply(service, host: "ExtensionHost"):
            for definition in self.definitions:
                if not definition.key:
                    continue
                service.register(extension_id, replace(definition, module_id=definition.module_id or extension_id))
            return service

        app.resolving(service_key, apply)


@dataclass(frozen=True)
class PostEventExtender:
    event_data_resolvers: tuple[ExtensionSystemHookDefinition, ...] = ()

    def type(
        self,
        post_type: str,
        resolver: Any,
        *,
        description: str = "",
        order: int = 100,
    ) -> "PostEventExtender":
        normalized = str(post_type or "").strip()
        if not normalized:
            return self
        return PostEventExtender(tuple([
            *self.event_data_resolvers,
            ExtensionSystemHookDefinition(
                key=normalized,
                callback=resolver,
                description=str(description or "").strip(),
                order=int(order),
            ),
        ]))

    def types(
        self,
        post_types: tuple[str, ...] | list[str] | set[str],
        resolver: Any,
        *,
        description: str = "",
        order: int = 100,
    ) -> "PostEventExtender":
        extender = self
        for post_type in post_types:
            extender = extender.type(
                post_type,
                resolver,
                description=description,
                order=order,
            )
        return extender

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.event_data_resolvers:
            return
        extension_id = extension.extension_id

        def apply(service, host: "ExtensionHost"):
            for definition in self.event_data_resolvers:
                resolver = definition.callback
                if isinstance(resolver, str) or isinstance(resolver, type):
                    resolver = wrap_callback(resolver, host)
                service.register(
                    extension_id,
                    replace(
                        definition,
                        callback=resolver,
                        module_id=definition.module_id or extension_id,
                    ),
                )
            return service

        app.resolving("post.events", apply)


class ErrorHandlingExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("error.handling", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "ErrorHandlingExtender":
        return ErrorHandlingExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def status(self, error_type: str, http_status: int) -> "ErrorHandlingExtender":
        return self._with_definition("status", {
            "error_type": str(error_type or "").strip(),
            "http_status": int(http_status),
        })

    def type(self, exception_class: Any, error_type: str) -> "ErrorHandlingExtender":
        return self._with_definition("type", {
            "exception_class": exception_class,
            "error_type": str(error_type or "").strip(),
        })

    def handler(self, exception_class: Any, handler: Any) -> "ErrorHandlingExtender":
        return self._with_definition("handler", {
            "exception_class": exception_class,
            "handler": handler,
        })

    def reporter(self, reporter: Any) -> "ErrorHandlingExtender":
        return self._with_definition("reporter", {"reporter": reporter})

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "ErrorHandlingExtender":
        return ErrorHandlingExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class AuthExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("auth", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "AuthExtender":
        return AuthExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def add_password_checker(self, identifier: str, checker: Any, *, description: str = "", order: int = 100) -> "AuthExtender":
        return self._with_definition("password_checker", {
            "identifier": str(identifier or "").strip(),
            "checker": checker,
            "description": str(description or "").strip(),
        }, order=order)

    def remove_password_checker(self, identifier: str, *, order: int = 100) -> "AuthExtender":
        return self._with_definition("remove_password_checker", {
            "identifier": str(identifier or "").strip(),
        }, order=order)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "AuthExtender":
        return AuthExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class FilesystemExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("filesystem", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "FilesystemExtender":
        return FilesystemExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def driver(self, name: str, driver: Any, *, description: str = "") -> "FilesystemExtender":
        return self._with_definition("driver", {
            "name": str(name or "").strip().lower(),
            "driver": driver,
            "description": str(description or "").strip(),
        })

    def disk(self, name: str, config: Any, *, driver: str = "local", description: str = "") -> "FilesystemExtender":
        return self._with_definition("disk", {
            "name": str(name or "").strip().lower(),
            "driver": str(driver or "local").strip().lower() or "local",
            "config": config,
            "description": str(description or "").strip(),
        })

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "FilesystemExtender":
        return FilesystemExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class ConsoleExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("console", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "ConsoleExtender":
        return ConsoleExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def command(self, name: str, handler: Any, *, description: str = "", order: int = 100) -> "ConsoleExtender":
        return self._with_definition("command", {
            "name": str(name or "").strip(),
            "description": str(description or "").strip(),
            "handler": handler,
        }, order=order)

    def schedule(self, name: str, schedule: Any, *, args: Any = None, description: str = "", order: int = 100) -> "ConsoleExtender":
        return self._with_definition("schedule", {
            "name": str(name or "").strip(),
            "description": str(description or "").strip(),
            "schedule": schedule,
            "args": args or {},
        }, order=order)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "ConsoleExtender":
        return ConsoleExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class SessionExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("session", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "SessionExtender":
        return SessionExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def driver(self, name: str, driver: Any, *, description: str = "", order: int = 100) -> "SessionExtender":
        return self._with_definition("driver", {
            "name": str(name or "").strip().lower(),
            "driver": driver,
            "description": str(description or "").strip(),
        }, order=order)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "SessionExtender":
        return SessionExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class ThemeExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("theme", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "ThemeExtender":
        return ThemeExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def variable(self, name: str, value: Any) -> "ThemeExtender":
        return self.variables({name: value})

    def variables(self, values: dict[str, Any]) -> "ThemeExtender":
        return self._with_definition("variables", dict(values or {}))

    def document_attributes(self, attributes: dict[str, Any]) -> "ThemeExtender":
        return self._with_definition("document_attributes", dict(attributes or {}))

    def document_classes(self, classes: Any) -> "ThemeExtender":
        return self.document_attributes({"class": classes})

    def head_tag(self, tag: str, attributes: dict[str, Any] | None = None, *, text: str = "") -> "ThemeExtender":
        return self._with_definition("head_tag", {
            "tag": str(tag or "").strip().lower(),
            "attributes": dict(attributes or {}),
            "text": str(text or ""),
        })

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "ThemeExtender":
        return ThemeExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class CsrfExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("csrf", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "CsrfExtender":
        return CsrfExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def exempt_route(self, route_name: str, *, description: str = "", order: int = 100) -> "CsrfExtender":
        return self._with_definition("exempt_route", {
            "route_name": str(route_name or "").strip(),
            "description": str(description or "").strip(),
        }, order=order)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "CsrfExtender":
        return CsrfExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


class ThrottleApiExtender(SystemHookExtender):
    def __init__(self, definitions: tuple[ExtensionSystemHookDefinition, ...] = ()) -> None:
        super().__init__("throttle.api", definitions)

    def hook(self, key: str, callback: Any, *, description: str = "", order: int = 100) -> "ThrottleApiExtender":
        return ThrottleApiExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=str(key or "").strip(),
            callback=callback,
            description=str(description or "").strip(),
            order=int(order),
        )]))

    def set(self, name: str, throttler: Any, *, description: str = "", order: int = 100) -> "ThrottleApiExtender":
        return self._with_definition("throttler", {
            "name": str(name or "").strip(),
            "throttler": throttler,
            "description": str(description or "").strip(),
        }, order=order)

    def remove(self, name: str, *, order: int = 100) -> "ThrottleApiExtender":
        return self._with_definition("remove_throttler", {
            "name": str(name or "").strip(),
        }, order=order)

    def _with_definition(self, key: str, payload: Any, *, order: int = 100) -> "ThrottleApiExtender":
        return ThrottleApiExtender(tuple([*self.definitions, ExtensionSystemHookDefinition(
            key=key,
            callback=payload,
            order=order,
        )]))


@dataclass(frozen=True)
class RoutesExtender:
    app_name: str = "api"
    routes: tuple[tuple[str, str, str, Any], ...] = ()
    removed_routes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized_app = str(self.app_name or "api").strip() or "api"
        if normalized_app != "api":
            raise ValueError("RoutesExtender 目前只注册后端 API 命名路由；前台/后台页面路由请使用 FrontendExtender.route()")
        object.__setattr__(self, "app_name", normalized_app)

    def get(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("GET", path, name, handler)

    def post(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("POST", path, name, handler)

    def put(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("PUT", path, name, handler)

    def patch(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("PATCH", path, name, handler)

    def delete(self, path: str, name: str, handler: Any) -> "RoutesExtender":
        return self.route("DELETE", path, name, handler)

    def route(self, method: str, path: str, name: str, handler: Any) -> "RoutesExtender":
        return RoutesExtender(
            app_name=self.app_name,
            routes=tuple([*self.routes, (str(method or "GET").strip().upper(), path, name, handler)]),
            removed_routes=self.removed_routes,
            tags=self.tags,
        )

    def remove(self, name: str) -> "RoutesExtender":
        normalized = str(name or "").strip()
        if not normalized:
            return self
        return RoutesExtender(
            app_name=self.app_name,
            routes=self.routes,
            removed_routes=tuple([*self.removed_routes, normalized]),
            tags=self.tags,
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.routes and not self.removed_routes:
            return

        extension_id = extension.extension_id

        def apply(routes, host: "ExtensionHost"):
            for name in self.removed_routes:
                routes.remove_route(extension_id, self.app_name, name)
            for method, path, name, handler in self.routes:
                resolved_handler = handler
                if isinstance(resolved_handler, str) or isinstance(resolved_handler, type):
                    resolved_handler = wrap_callback(resolved_handler, host)
                routes.add_route(
                    extension_id,
                    self.app_name,
                    method,
                    path,
                    name,
                    resolved_handler,
                    tags=self.tags,
                )
            return routes

        app.resolving("routes", apply)


@dataclass(frozen=True)
class ApiRoutesExtender:
    mounts: tuple[tuple[str, Any], ...] = ()
    tags: tuple[str, ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        mounts = tuple(
            (str(prefix or "").strip(), router)
            for prefix, router in self.mounts
            if router is not None
        )
        if not mounts:
            return

        extension_id = extension.extension_id

        def apply(routes, host: "ExtensionHost"):
            routes.remove_mounts(extension_id)
            for prefix, router in mounts:
                routes.mount(extension_id, prefix, router, tags=self.tags)
            return routes

        app.resolving("routes", apply)


@dataclass(frozen=True)
class MiddlewareExtender:
    mounts: tuple[tuple[str, Any, int], ...] = ()

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.mounts:
            return

        extension_id = extension.extension_id

        def apply(middleware_service, host: "ExtensionHost"):
            for target, middleware, order in self.mounts:
                if middleware is None:
                    continue
                middleware_service.mount(extension_id, target, middleware, order=order)
            return middleware_service

        app.resolving("middleware", apply)


@dataclass(frozen=True)
class PolicyExtender:
    mounts: tuple[tuple[str, Callable[..., bool]], ...] = ()
    global_policies: tuple[Callable[..., bool], ...] = ()
    model_policies: tuple[tuple[Any, Callable[..., bool]], ...] = ()
    query_model_policies: tuple[tuple[Any, Callable[..., bool]], ...] = ()

    def global_policy(self, handler: Callable[..., bool]) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=tuple([*self.global_policies, handler]),
            model_policies=self.model_policies,
            query_model_policies=self.query_model_policies,
        )

    def model_policy(self, model: Any, handler: Callable[..., bool]) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=self.global_policies,
            model_policies=tuple([*self.model_policies, (model, handler)]),
            query_model_policies=self.query_model_policies,
        )

    def query_model_policy(self, model: Any, handler: Callable[..., bool]) -> "PolicyExtender":
        return PolicyExtender(
            mounts=self.mounts,
            global_policies=self.global_policies,
            model_policies=self.model_policies,
            query_model_policies=tuple([*self.query_model_policies, (model, handler)]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if not self.mounts and not self.global_policies and not self.model_policies and not self.query_model_policies:
            return

        extension_id = extension.extension_id

        def apply(policies, host: "ExtensionHost"):
            for key, handler in self.mounts:
                policies.mount(extension_id, key, handler)
            for handler in self.global_policies:
                policies.global_policy(extension_id, handler)
            for model, handler in self.model_policies:
                policies.model_policy(extension_id, model, handler)
            for model, handler in self.query_model_policies:
                policies.query_model_policy(extension_id, model, handler)
            return policies

        app.resolving("policies", apply)


@dataclass(frozen=True)
class ConditionalExtender:
    callbacks: tuple[Callable[["ExtensionHost"], Any], ...] = ()

    def when(self, condition: Callable[["ExtensionHost"], bool] | bool, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        def resolver(host: "ExtensionHost"):
            if not self._evaluate_condition(condition, host):
                return []
            return self._resolve_extenders(callback, host)

        return ConditionalExtender(callbacks=tuple([*self.callbacks, resolver]))

    def when_extension_enabled(self, extension_id: str, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        normalized = str(extension_id or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            extension = host.get_runtime_extension(normalized)
            return bool(extension and extension.runtime.enabled)

        return self.when(condition, callback)

    def when_extension_disabled(self, extension_id: str, callback: Callable[[], Any] | str | type) -> "ConditionalExtender":
        normalized = str(extension_id or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            extension = host.get_runtime_extension(normalized)
            return not bool(extension and extension.runtime.enabled)

        return self.when(condition, callback)

    def when_setting(
        self,
        key: str,
        expected: Any,
        callback: Callable[[], Any] | str | type,
        *,
        strict: bool = False,
    ) -> "ConditionalExtender":
        normalized_key = str(key or "").strip()

        def condition(host: "ExtensionHost") -> bool:
            try:
                from apps.core.models import Setting

                record = Setting.objects.filter(key=normalized_key).first()
                value = record.value if record is not None else None
            except Exception:
                value = None
            if strict:
                return value == expected and type(value) is type(expected)
            return value == expected

        return self.when(condition, callback)

    @staticmethod
    def _evaluate_condition(condition: Callable[["ExtensionHost"], bool] | bool | str | type, host: "ExtensionHost") -> bool:
        if isinstance(condition, bool):
            return condition
        resolved = wrap_callback(condition, host) if isinstance(condition, (str, type)) else condition
        if not callable(resolved):
            return bool(resolved)
        try:
            return bool(resolved(host))
        except TypeError:
            return bool(resolved())

    @staticmethod
    def _resolve_extenders(callback: Callable[[], Any] | str | type, host: "ExtensionHost"):
        resolved = wrap_callback(callback, host) if isinstance(callback, (str, type)) else callback
        if not callable(resolved):
            return resolved
        try:
            return resolved()
        except TypeError:
            return resolved(host)

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        for resolver in self.callbacks:
            extenders = resolver(app)
            for extender in flatten_extenders(extenders):
                extend_fn = getattr(extender, "extend", None)
                if callable(extend_fn):
                    app._mark_extension_extender(extension.extension_id, extender)
                    extend_fn(app, extension)
