from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, TYPE_CHECKING

from apps.core.extensions.container import wrap_callback
from apps.core.extensions.types import (
    ExtensionEventListenerDefinition,
    ExtensionMailDefinition,
    ExtensionRealtimeDiscussionBroadcastDefinition,
    ExtensionRealtimeDiscussionTransportDefinition,
    ExtensionRealtimeIncludedDefinition,
    ExtensionSignalDefinition,
    ExtensionSystemHookDefinition,
    ExtensionValidatorDefinition,
    ExtensionViewNamespaceDefinition,
)

if TYPE_CHECKING:
    from apps.core.extensions.application import ExtensionHost, ExtensionRuntimeView


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
    discussion_visibility_resolvers: tuple[ExtensionSystemHookDefinition, ...] = ()
    discussion_transports: tuple[ExtensionRealtimeDiscussionTransportDefinition, ...] = ()
    discussion_broadcasts: tuple[ExtensionRealtimeDiscussionBroadcastDefinition, ...] = ()

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
            discussion_visibility_resolvers=self.discussion_visibility_resolvers,
            discussion_transports=self.discussion_transports,
            discussion_broadcasts=self.discussion_broadcasts,
        )

    def discussion_visibility(
        self,
        handler: Any,
        *,
        key: str = "discussion.visibility",
        description: str = "",
        order: int = 100,
    ) -> "RealtimeExtender":
        return RealtimeExtender(
            included=self.included,
            discussion_visibility_resolvers=tuple([
                *self.discussion_visibility_resolvers,
                ExtensionSystemHookDefinition(
                    key=str(key or "").strip(),
                    callback=handler,
                    description=str(description or "").strip(),
                    order=int(order),
                ),
            ]),
            discussion_transports=self.discussion_transports,
            discussion_broadcasts=self.discussion_broadcasts,
        )

    def discussion_transport(self, key: str, handler: Any, *, description: str = "") -> "RealtimeExtender":
        return RealtimeExtender(
            included=self.included,
            discussion_visibility_resolvers=self.discussion_visibility_resolvers,
            discussion_transports=tuple([
                *self.discussion_transports,
                ExtensionRealtimeDiscussionTransportDefinition(
                    key=str(key or "").strip(),
                    handler=handler,
                    description=str(description or "").strip(),
                ),
            ]),
            discussion_broadcasts=self.discussion_broadcasts,
        )

    def broadcast_discussion_event(
        self,
        event_type: Any,
        event_name: Any,
        *,
        discussion_id: Any = "discussion_id",
        include_discussion: bool = False,
        include_post: bool = False,
        post_id: Any = None,
        post_id_getter: Any = None,
        extension_context: Any = None,
        condition: Any = None,
        description: str = "",
    ) -> "RealtimeExtender":
        return RealtimeExtender(
            included=self.included,
            discussion_visibility_resolvers=self.discussion_visibility_resolvers,
            discussion_transports=self.discussion_transports,
            discussion_broadcasts=tuple([
                *self.discussion_broadcasts,
                ExtensionRealtimeDiscussionBroadcastDefinition(
                    event_type=event_type,
                    event_name=event_name,
                    discussion_id=discussion_id,
                    include_discussion=bool(include_discussion),
                    include_post=bool(include_post),
                    post_id=post_id,
                    post_id_getter=post_id_getter,
                    extension_context=extension_context,
                    condition=condition,
                    description=str(description or "").strip(),
                ),
            ]),
        )

    def extend(self, app: "ExtensionHost", extension: "ExtensionRuntimeView") -> None:
        if (
            not self.included
            and not self.discussion_visibility_resolvers
            and not self.discussion_transports
            and not self.discussion_broadcasts
        ):
            return

        extension_id = extension.extension_id

        def apply(realtime, host: "ExtensionHost"):
            for definition in self.included:
                handler = definition.handler
                if isinstance(handler, str) or isinstance(handler, type):
                    handler = wrap_callback(handler, host)
                    definition = replace(definition, handler=handler)
                realtime.register_included_enricher(extension_id, definition)
            for definition in sorted(self.discussion_visibility_resolvers, key=lambda item: int(item.order or 100)):
                handler = definition.callback
                if isinstance(handler, str) or isinstance(handler, type):
                    handler = wrap_callback(handler, host)
                    definition = replace(definition, callback=handler)
                realtime.register_discussion_visibility_resolver(extension_id, definition)
            for definition in self.discussion_transports:
                handler = definition.handler
                if isinstance(handler, str) or isinstance(handler, type):
                    handler = wrap_callback(handler, host)
                    definition = replace(definition, handler=handler)
                realtime.register_discussion_transport(extension_id, definition)
            for definition in self.discussion_broadcasts:
                realtime.register_discussion_broadcast(extension_id, definition)
            return realtime

        app.resolving("realtime", apply)
