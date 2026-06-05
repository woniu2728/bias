from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.core.extensions.types import ExtensionSignalDefinition


@dataclass(frozen=True)
class RuntimeSignalConnection:
    extension_id: str
    signal: Any
    sender: Any
    dispatch_uid: str
    receiver: Any
    lazy_proxy: bool = False
    enabled_by_default: bool = False


_runtime_signal_connections: dict[str, RuntimeSignalConnection] = {}


def connect_runtime_signal(extension_id: str, definition: ExtensionSignalDefinition) -> str:
    return _connect_runtime_signal(
        extension_id,
        definition,
        lazy_proxy=False,
        enabled_by_default=True,
    )


def connect_runtime_signal_proxy(
    extension_id: str,
    definition: ExtensionSignalDefinition,
    *,
    enabled_by_default: bool = False,
) -> str:
    return _connect_runtime_signal(
        extension_id,
        definition,
        lazy_proxy=True,
        enabled_by_default=enabled_by_default,
    )


def _connect_runtime_signal(
    extension_id: str,
    definition: ExtensionSignalDefinition,
    *,
    lazy_proxy: bool,
    enabled_by_default: bool,
) -> str:
    normalized_extension_id = str(extension_id or "").strip()
    if not normalized_extension_id:
        return ""
    if definition.signal is None or not callable(definition.receiver):
        return ""

    dispatch_uid = str(definition.dispatch_uid or "").strip()
    if not dispatch_uid:
        dispatch_uid = _build_dispatch_uid(normalized_extension_id, definition)

    existing = _runtime_signal_connections.get(dispatch_uid)
    if existing is not None:
        _disconnect_signal(existing)

    receiver = (
        _build_lazy_receiver(normalized_extension_id, definition, enabled_by_default=enabled_by_default)
        if lazy_proxy else
        definition.receiver
    )
    definition.signal.connect(
        receiver,
        sender=definition.sender,
        weak=bool(definition.weak),
        dispatch_uid=dispatch_uid,
    )
    _runtime_signal_connections[dispatch_uid] = RuntimeSignalConnection(
        extension_id=normalized_extension_id,
        signal=definition.signal,
        sender=definition.sender,
        dispatch_uid=dispatch_uid,
        receiver=receiver,
        lazy_proxy=lazy_proxy,
        enabled_by_default=bool(enabled_by_default),
    )
    return dispatch_uid


def disconnect_runtime_signal_receivers(
    *,
    extension_id: str | None = None,
    include_proxies: bool = False,
    proxy_only: bool = False,
) -> None:
    normalized_extension_id = None if extension_id is None else str(extension_id or "").strip()
    for dispatch_uid, connection in list(_runtime_signal_connections.items()):
        if normalized_extension_id is not None and connection.extension_id != normalized_extension_id:
            continue
        if connection.lazy_proxy and not include_proxies:
            continue
        if proxy_only and not connection.lazy_proxy:
            continue
        _disconnect_signal(connection)
        _runtime_signal_connections.pop(dispatch_uid, None)


def get_runtime_signal_connections(
    *,
    extension_id: str | None = None,
    include_proxies: bool = True,
) -> list[RuntimeSignalConnection]:
    normalized_extension_id = None if extension_id is None else str(extension_id or "").strip()
    return [
        connection
        for connection in _runtime_signal_connections.values()
        if normalized_extension_id is None or connection.extension_id == normalized_extension_id
        if include_proxies or not connection.lazy_proxy
    ]


def _disconnect_signal(connection: RuntimeSignalConnection) -> None:
    disconnect = getattr(connection.signal, "disconnect", None)
    if not callable(disconnect):
        return
    disconnect(dispatch_uid=connection.dispatch_uid, sender=connection.sender)


def _build_lazy_receiver(extension_id: str, definition: ExtensionSignalDefinition, *, enabled_by_default: bool):
    def receiver(sender=None, **kwargs):
        if not _is_extension_signal_enabled(extension_id, enabled_by_default=enabled_by_default):
            return None
        return definition.receiver(sender=sender, **kwargs)

    receiver.__name__ = f"bias_lazy_signal_{extension_id}".replace("-", "_").replace(".", "_")
    return receiver


def _is_extension_signal_enabled(extension_id: str, *, enabled_by_default: bool) -> bool:
    try:
        from django.db import OperationalError, ProgrammingError
        from apps.core.models import ExtensionInstallation

        installation = ExtensionInstallation.objects.filter(extension_id=extension_id).first()
    except (OperationalError, ProgrammingError, RuntimeError):
        return False

    if installation is None:
        return bool(enabled_by_default)
    return bool(installation.installed and installation.enabled)


def _build_dispatch_uid(extension_id: str, definition: ExtensionSignalDefinition) -> str:
    signal_label = _label_for(definition.signal, fallback="signal")
    sender_label = _label_for(definition.sender, fallback="any")
    receiver_label = _label_for(definition.receiver, fallback="receiver")
    return f"bias.extension.{extension_id}.{signal_label}.{sender_label}.{receiver_label}"


def _label_for(value: Any, *, fallback: str) -> str:
    if value is None:
        return fallback
    module = str(getattr(value, "__module__", "") or "").strip()
    qualname = str(getattr(value, "__qualname__", "") or getattr(value, "__name__", "") or "").strip()
    if module or qualname:
        return ".".join(item for item in (module, qualname) if item)
    return str(value.__class__.__name__ or fallback)
