from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from typing import Protocol, TYPE_CHECKING

from apps.core.extensions.extenders_frontend import (
    FormatterExtender,
    FrontendExtender,
    LanguagePackExtender,
    LinkExtender,
    LocalesExtender,
)
from apps.core.extensions.extenders_forum_admin import (
    AdminNavigationExtender,
    AdminSurfaceExtender,
    DiscussionLifecycleExtender,
    ForumCapabilitiesExtender,
    ForumPermissionExtender,
    NotificationsExtender,
    PostExtender,
    PostLifecycleExtender,
    RuntimeActionsExtender,
    SettingsExtender,
    UserExtender,
)
from apps.core.extensions.extenders_model_search import (
    ModelExtender,
    ModelPrivateExtender,
    ModelUrlExtender,
    ModelVisibilityExtender,
    RuntimeModel,
    SearchDriverExtender,
    SearchIndexExtender,
)
from apps.core.extensions.extenders_runtime import (
    EventListenersExtender,
    MailExtender,
    RealtimeExtender,
    SignalExtender,
    ValidatorExtender,
    ViewExtender,
)
from apps.core.extensions.extenders_system import (
    AuthExtender,
    ConsoleExtender,
    CsrfExtender,
    ErrorHandlingExtender,
    FilesystemExtender,
    PostEventExtender,
    ServiceProviderExtender,
    SessionExtender,
    SystemHookExtender,
    ThemeExtender,
    ThrottleApiExtender,
)
from apps.core.extensions.extenders_routes_policy import (
    ApiRoutesExtender,
    ConditionalExtender,
    MiddlewareExtender,
    PolicyExtender,
    RoutesExtender,
    WebSocketRoutesExtender,
)
from apps.core.extensions.extenders_resources import (
    ApiResourceExtender,
    ResourceExtender,
)

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
