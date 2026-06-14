from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, TYPE_CHECKING

from apps.core.extensions.container import wrap_callback
from apps.core.extensions.types import ExtensionSystemHookDefinition

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


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

    def human_verification(self, identifier: str, verifier: Any, *, description: str = "", order: int = 100) -> "AuthExtender":
        return self._with_definition("human_verification", {
            "identifier": str(identifier or "").strip(),
            "verifier": verifier,
            "description": str(description or "").strip(),
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
