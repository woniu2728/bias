from __future__ import annotations

from dataclasses import dataclass

from apps.core.domain_events import DomainEvent


@dataclass(frozen=True)
class ExtensionLifecycleEvent(DomainEvent):
    extension_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ExtensionInstalledEvent(ExtensionLifecycleEvent):
    reason: str = "extension_installed"


@dataclass(frozen=True)
class ExtensionEnablingEvent(ExtensionLifecycleEvent):
    reason: str = "extension_enabling"


@dataclass(frozen=True)
class ExtensionEnabledEvent(ExtensionLifecycleEvent):
    reason: str = "extension_enabled"


@dataclass(frozen=True)
class ExtensionDisablingEvent(ExtensionLifecycleEvent):
    reason: str = "extension_disabling"


@dataclass(frozen=True)
class ExtensionDisabledEvent(ExtensionLifecycleEvent):
    reason: str = "extension_disabled"


@dataclass(frozen=True)
class ExtensionUninstalledEvent(ExtensionLifecycleEvent):
    reason: str = "extension_uninstalled"


@dataclass(frozen=True)
class ExtensionPackagesSyncedEvent(DomainEvent):
    created: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()
    pruned: tuple[str, ...] = ()
    reason: str = "extension_packages_synced"


@dataclass(frozen=True)
class RuntimeCacheClearedEvent(DomainEvent):
    reason: str = "runtime_cache_cleared"
