from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.utils import timezone

from apps.core.extensions.module_loader import (
    inspect_extension_backend_module,
    load_extension_backend_module,
)
from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionManifestSettingOptionDefinition,
)


@dataclass(frozen=True)
class ExtensionBackendContext:
    extension_id: str
    extension_name: str
    version: str
    source: str
    extension_path: str
    manifest_path: str
    backend_entry: str
    migration_namespace: str
    installed: bool
    enabled: bool
    booted: bool
    meta: dict[str, Any]


def build_backend_context(
    definition: Extension,
    *,
    meta: dict[str, Any] | None = None,
) -> ExtensionBackendContext:
    extension_path = str(definition.manifest.path or "").strip()
    manifest_path = str(Path(extension_path) / "extension.json") if extension_path else ""
    return ExtensionBackendContext(
        extension_id=definition.id,
        extension_name=definition.name,
        version=definition.version,
        source=definition.source,
        extension_path=extension_path,
        manifest_path=manifest_path,
        backend_entry=str(definition.manifest.backend_entry or "").strip(),
        migration_namespace=str(definition.manifest.migration_namespace or "").strip(),
        installed=bool(definition.runtime.installed),
        enabled=bool(definition.runtime.enabled),
        booted=bool(definition.runtime.booted),
        meta=dict(meta or {}),
    )


def inspect_extension_backend_entry(definition: Extension) -> dict[str, Any]:
    return inspect_extension_backend_module(definition)


def run_extension_backend_hook(
    definition: Extension,
    hook_name: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    module = load_extension_backend_module(definition)
    if module is None:
        return {
            "hook": hook_name,
            "status": "skipped",
            "status_label": "已跳过",
            "message": "当前扩展没有可执行的后端入口。",
        }

    hook = getattr(module, hook_name, None)
    if not callable(hook):
        return {
            "hook": hook_name,
            "status": "skipped",
            "status_label": "已跳过",
            "message": f"后端入口未声明 {hook_name}。",
        }

    context = build_backend_context(definition, meta=meta)
    result = hook(context)
    timestamp = timezone.now().isoformat()

    if result is None:
        return {
            "hook": hook_name,
            "status": "ok",
            "status_label": "已完成",
            "message": f"{hook_name} 已执行。",
            "executed_at": timestamp,
        }

    if isinstance(result, dict):
        payload = dict(result)
        payload.setdefault("hook", hook_name)
        payload.setdefault("status", "ok")
        payload.setdefault("status_label", "已完成")
        payload.setdefault("executed_at", timestamp)
        return payload

    return {
        "hook": hook_name,
        "status": "ok",
        "status_label": "已完成",
        "message": str(result),
        "executed_at": timestamp,
    }


def _build_setting_field_definition(payload: dict[str, Any]) -> ExtensionManifestSettingFieldDefinition:
    return ExtensionManifestSettingFieldDefinition(
        key=str(payload.get("key") or "").strip(),
        label=str(payload.get("label") or "").strip(),
        type=str(payload.get("type") or "text").strip() or "text",
        default=payload.get("default", ""),
        help_text=str(payload.get("help_text") or "").strip(),
        placeholder=str(payload.get("placeholder") or "").strip(),
        required=bool(payload.get("required", False)),
        options=tuple(
            ExtensionManifestSettingOptionDefinition(
                value=str(item.get("value") or "").strip(),
                label=str(item.get("label") or "").strip(),
            )
            for item in payload.get("options", [])
            if isinstance(item, dict)
        ),
        multiline=bool(payload.get("multiline", False)),
        order=int(payload.get("order", 100) or 100),
    )


def _build_runtime_action_definition(payload: dict[str, Any]) -> ExtensionManifestRuntimeActionDefinition:
    return ExtensionManifestRuntimeActionDefinition(
        key=str(payload.get("key") or "").strip(),
        label=str(payload.get("label") or "").strip(),
        hook=str(payload.get("hook") or "").strip(),
        tone=str(payload.get("tone") or "default").strip() or "default",
        confirm_title=str(payload.get("confirm_title") or "").strip(),
        confirm_message=str(payload.get("confirm_message") or "").strip(),
        confirm_text=str(payload.get("confirm_text") or "").strip(),
        success_message=str(payload.get("success_message") or "").strip(),
        requires_enabled=bool(payload.get("requires_enabled", False)),
        requires_installed=bool(payload.get("requires_installed", False)),
        description=str(payload.get("description") or "").strip(),
        order=int(payload.get("order", 100) or 100),
    )


def _build_admin_action_definition(payload: dict[str, Any]) -> ExtensionAdminActionDefinition:
    return ExtensionAdminActionDefinition(
        key=str(payload.get("key") or "").strip(),
        label=str(payload.get("label") or "").strip(),
        kind=str(payload.get("kind") or "route").strip() or "route",
        target=str(payload.get("target") or "").strip(),
        icon=str(payload.get("icon") or "").strip(),
        tone=str(payload.get("tone") or "default").strip() or "default",
        opens_in_new_tab=bool(payload.get("opens_in_new_tab", False)),
        requires_enabled=bool(payload.get("requires_enabled", False)),
        description=str(payload.get("description") or "").strip(),
        order=int(payload.get("order", 100) or 100),
    )
