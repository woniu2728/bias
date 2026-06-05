from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from django.conf import settings

from apps.core.extensions.application import ExtensionHost
from apps.core.extensions.container import wrap_callback
from apps.core.extensions.exceptions import ExtensionBootError, ExtensionManifestError
from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.extenders import SignalExtender
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.product import is_extension_auto_enabled
from apps.core.extensions.signal_runtime import connect_runtime_signal_proxy


_signal_proxy_bootstrapped = False


def reset_extension_signal_proxy_bootstrap() -> None:
    from apps.core.extensions.signal_runtime import disconnect_runtime_signal_receivers

    global _signal_proxy_bootstrapped
    disconnect_runtime_signal_receivers(include_proxies=True, proxy_only=True)
    _signal_proxy_bootstrapped = False


def bootstrap_extension_signal_proxies(*, force: bool = False) -> None:
    global _signal_proxy_bootstrapped
    if _signal_proxy_bootstrapped and not force:
        return

    loader = ExtensionManifestLoader(Path(settings.BASE_DIR) / "extensions")
    host = ExtensionHost()
    for manifest in loader.discover_manifests():
        try:
            extension = Extension.from_manifest(manifest)
            _connect_signal_extenders(host, extension)
        except (ExtensionBootError, ExtensionManifestError, ImportError, RuntimeError):
            continue

    _signal_proxy_bootstrapped = True


def _connect_signal_extenders(host: ExtensionHost, extension: Extension) -> None:
    enabled_by_default = is_extension_auto_enabled(extension)
    for extender in extension.get_extenders():
        if not isinstance(extender, SignalExtender):
            continue
        for definition in extender.definitions:
            receiver = definition.receiver
            if isinstance(receiver, str) or isinstance(receiver, type):
                receiver = wrap_callback(receiver, host)
                definition = replace(definition, receiver=receiver)
            connect_runtime_signal_proxy(
                extension.id,
                replace(definition, module_id=definition.module_id or extension.id),
                enabled_by_default=enabled_by_default,
            )
