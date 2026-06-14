from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from apps.core.extensions.container import wrap_callback
from apps.core.extensions.types import ExtensionFormatterCallback, ExtensionFrontendRouteDefinition
from apps.core.forum_registry_types import LanguagePackDefinition

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


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

    def admin(self, path: str) -> "FrontendExtender":
        return replace(self, admin_entry=str(path or "").strip())

    def forum(self, path: str) -> "FrontendExtender":
        return replace(self, forum_entry=str(path or "").strip())

    def common(self, path: str) -> "FrontendExtender":
        return replace(self, common_entry=str(path or "").strip())

    def js(self, path: str, *, frontend: str = "forum") -> "FrontendExtender":
        target = str(frontend or "forum").strip().lower() or "forum"
        if target == "admin":
            return self.admin(path)
        if target == "common":
            return self.common(path)
        return self.forum(path)

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

    def jsDirectory(self, path: str) -> "FrontendExtender":
        return self.js_directory(path)

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
        normalized_items = items
        if len(items) == 1 and isinstance(items[0], (list, tuple)):
            normalized_items = tuple(items[0])
        return FrontendExtender(
            admin_entry=self.admin_entry,
            forum_entry=self.forum_entry,
            common_entry=self.common_entry,
            css_files=self.css_files,
            js_directories=self.js_directories,
            preloads=tuple([*self.preloads, *normalized_items]),
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

    def extraDocumentAttributes(self, attributes: Any) -> "FrontendExtender":
        return self.extra_document_attributes(attributes)

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

    def extraDocumentClasses(self, classes: Any) -> "FrontendExtender":
        return self.extra_document_classes(classes)

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

    def removeRoute(self, name: str, *, frontend: str = "forum") -> "FrontendExtender":
        return self.remove_route(name, frontend=frontend)

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
