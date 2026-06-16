from __future__ import annotations

from typing import Any

from apps.core.extension_settings_service import get_extension_settings
from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.frontend_serialization import (
    serialize_frontend_routes,
    serialize_frontend_value,
    serialize_frontend_values,
)
from apps.core.extensions.product import is_product_visible_extension


_frontend_runtime_catalog: dict[str, dict[str, Any]] = {}
_frontend_runtime_bootstrapped = False


def clear_extension_frontend_runtime_cache() -> None:
    global _frontend_runtime_catalog
    global _frontend_runtime_bootstrapped
    _frontend_runtime_catalog = {}
    _frontend_runtime_bootstrapped = False


def bootstrap_extension_frontend_runtime() -> None:
    global _frontend_runtime_catalog
    global _frontend_runtime_bootstrapped
    if _frontend_runtime_bootstrapped:
        return

    catalog: dict[str, dict[str, Any]] = {}
    host = get_extension_host(force=True)
    if host is None:
        _frontend_runtime_catalog = {}
        _frontend_runtime_bootstrapped = True
        return

    extension_map = {
        item.id: item
        for item in host.get_runtime_extensions()
    }
    frontend_map = {
        item.extension_id: item
        for item in host.get_frontend_extensions()
    }
    frontend_outputs = _get_extension_frontend_outputs()
    for extension_id, extension in extension_map.items():
        runtime_view = host.get_extension_view(extension_id)
        frontend = frontend_map.get(extension_id)
        if extension is None:
            continue
        if runtime_view is None:
            continue
        admin_entry = str((frontend.admin_entry if frontend else runtime_view.frontend_admin_entry) or "").strip()
        forum_entry = str((frontend.forum_entry if frontend else runtime_view.frontend_forum_entry) or "").strip()
        common_entry = str((frontend.common_entry if frontend else runtime_view.frontend_common_entry) or "").strip()
        frontend_routes = tuple((frontend.routes if frontend else runtime_view.frontend_routes) or ())
        catalog[extension_id] = {
            "id": extension_id,
            "name": extension.name,
            "source": extension.source,
            "module_ids": list(runtime_view.module_ids),
            "frontend_admin_entry": admin_entry,
            "frontend_forum_entry": forum_entry,
            "frontend_common_entry": common_entry,
            "frontend_outputs": dict(frontend_outputs.get(extension_id) or {}),
            "frontend_routes": serialize_frontend_routes(frontend_routes),
            "frontend_document": _build_frontend_document_payload(runtime_view),
            "settings_pages": list((frontend.settings_pages if frontend else runtime_view.settings_pages) or ()),
            "permissions_pages": list((frontend.permissions_pages if frontend else runtime_view.permissions_pages) or ()),
            "operations_pages": list((frontend.operations_pages if frontend else runtime_view.operations_pages) or ()),
            "locale_paths": list(runtime_view.locale_paths),
            "formatter_pipeline": list(runtime_view.formatter_pipeline),
            "product_visible": _is_product_visible_frontend_extension(
                extension,
                admin_entry=admin_entry,
                forum_entry=forum_entry,
                common_entry=common_entry,
                frontend_routes=frontend_routes,
                runtime_view=runtime_view,
            ),
        }

    _frontend_runtime_catalog = catalog
    _frontend_runtime_bootstrapped = True


def get_enabled_extension_runtime_entries(*, product_visible_only: bool = False) -> list[dict[str, Any]]:
    bootstrap_extension_frontend_runtime()
    host = get_extension_host()
    if host is None:
        return []
    extension_map = {
        item.id: item
        for item in host.get_runtime_extensions()
    }

    entries = []
    for extension in host.get_runtime_extensions():
        runtime_view = host.get_extension_view(extension.id)
        if extension is None:
            continue
        if not getattr(extension.runtime, "enabled", False):
            continue
        if runtime_view is None:
            continue
        entry = _build_runtime_entry(host, runtime_view, extension)
        if product_visible_only and not entry["product_visible"]:
            continue
        entries.append(entry)
    return entries


def get_enabled_extension_locales() -> list[dict[str, Any]]:
    from apps.core.extensions.locale_service import get_enabled_extension_locales as load_enabled_extension_locales

    return load_enabled_extension_locales()


def apply_enabled_extension_formatters(html: str) -> str:
    from apps.core.extensions.formatter_service import apply_extension_formatters

    return apply_extension_formatters(html)


def _build_runtime_entry(
    host,
    runtime_view,
    extension,
) -> dict[str, Any]:
    static_entry = dict(_frontend_runtime_catalog.get(runtime_view.extension_id) or {})
    frontend = host.get_frontend_extension(runtime_view.extension_id)
    admin_entry = str((frontend.admin_entry if frontend else runtime_view.frontend_admin_entry) or "").strip()
    forum_entry = str((frontend.forum_entry if frontend else runtime_view.frontend_forum_entry) or "").strip()
    common_entry = str((frontend.common_entry if frontend else runtime_view.frontend_common_entry) or "").strip()
    frontend_routes = tuple((frontend.routes if frontend else runtime_view.frontend_routes) or ())
    frontend_outputs = _get_extension_frontend_outputs().get(runtime_view.extension_id) or {}
    settings_definition = {
        "forum_settings_keys": tuple(runtime_view.forum_settings_keys),
        "forum_serializations": tuple(runtime_view.settings_forum_serializations),
    } if _has_settings_contract(runtime_view) else None
    settings_values = get_extension_settings(runtime_view.extension_id) if settings_definition else {}
    forum_settings = _build_extension_forum_settings(settings_definition, settings_values)

    static_entry.update({
        "id": runtime_view.extension_id,
        "name": extension.name,
        "source": extension.source,
        "module_ids": list(runtime_view.module_ids),
        "frontend_admin_entry": admin_entry,
        "frontend_forum_entry": forum_entry,
        "frontend_common_entry": common_entry,
        "frontend_outputs": dict(frontend_outputs),
        "frontend_routes": serialize_frontend_routes(frontend_routes),
        "frontend_document": _build_frontend_document_payload(runtime_view, settings_values=settings_values),
        "settings_pages": list((frontend.settings_pages if frontend else runtime_view.settings_pages) or ()),
        "permissions_pages": list((frontend.permissions_pages if frontend else runtime_view.permissions_pages) or ()),
        "operations_pages": list((frontend.operations_pages if frontend else runtime_view.operations_pages) or ()),
        "settings_values": settings_values,
        "forum_settings": forum_settings,
        "locale_paths": list(runtime_view.locale_paths),
        "formatter_pipeline": list(runtime_view.formatter_pipeline),
        "product_visible": _is_product_visible_frontend_extension(
            extension,
            admin_entry=admin_entry,
            forum_entry=forum_entry,
            common_entry=common_entry,
            frontend_routes=frontend_routes,
            runtime_view=runtime_view,
        ),
    })
    return static_entry


def _get_extension_frontend_outputs() -> dict[str, dict[str, Any]]:
    from apps.core.extensions.frontend_compiler import inspect_extension_frontend_output_manifest

    output_manifest = inspect_extension_frontend_output_manifest()
    outputs: dict[str, dict[str, Any]] = {}
    for extension_id, payload in dict(output_manifest.get("extensions") or {}).items():
        outputs[str(extension_id)] = dict(dict(payload or {}).get("outputs") or {})
    return outputs


def _is_product_visible_frontend_extension(
    extension,
    *,
    admin_entry: str,
    forum_entry: str,
    common_entry: str,
    frontend_routes,
    runtime_view,
) -> bool:
    if not is_product_visible_extension(extension):
        return False
    return bool(admin_entry or forum_entry or common_entry or frontend_routes or _has_settings_contract(runtime_view))


def _has_settings_contract(runtime_view) -> bool:
    return bool(
        getattr(runtime_view, "settings_schema", None)
        or getattr(runtime_view, "settings_defaults", None)
        or getattr(runtime_view, "settings_forum_serializations", None)
        or getattr(runtime_view, "forum_settings_keys", None)
    )


def build_enabled_frontend_document_payload() -> dict[str, Any]:
    entries = get_enabled_extension_runtime_entries(product_visible_only=False)
    preloads = []
    document_attributes = {}
    title_drivers = []
    content_callbacks = []
    head_tags = []
    theme_variables = {}

    for entry in entries:
        document = dict(entry.get("frontend_document") or {})
        for preload in document.get("preloads") or []:
            if preload and preload not in preloads:
                preloads.append(preload)
        for attributes in document.get("document_attributes") or []:
            if isinstance(attributes, dict):
                document_attributes.update(attributes)
        for tag in document.get("head_tags") or []:
            if tag and tag not in head_tags:
                head_tags.append(tag)
        for variables in document.get("theme_variables") or []:
            if isinstance(variables, dict):
                theme_variables.update(variables)
        title_driver = document.get("title_driver")
        if title_driver:
            title_drivers.append({
                "extension_id": entry["id"],
                "driver": title_driver,
            })
        for callback in document.get("content_callbacks") or []:
            callback_payload = _normalize_content_callback_payload(callback)
            if callback_payload["callback"]:
                content_callbacks.append({
                    "extension_id": entry["id"],
                    **callback_payload,
                })

    content_callbacks.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)

    return {
        "preloads": preloads,
        "document_attributes": document_attributes,
        "head_tags": head_tags,
        "theme_variables": theme_variables,
        "title_drivers": title_drivers,
        "content_callbacks": content_callbacks,
    }


def build_frontend_document_payload(runtime_view, *, settings_values: dict[str, Any] | None = None) -> dict[str, Any]:
    theme_document = _build_theme_document_payload(runtime_view)
    return {
        "preloads": serialize_frontend_values(getattr(runtime_view, "frontend_preloads", ()) or ()),
        "document_attributes": serialize_frontend_values([
            *(getattr(runtime_view, "frontend_document_attributes", ()) or ()),
            *theme_document["document_attributes"],
        ]),
        "head_tags": serialize_frontend_values([
            *(getattr(runtime_view, "frontend_head_tags", ()) or ()),
            *theme_document["head_tags"],
        ]),
        "theme_variables": serialize_frontend_values([
            *(getattr(runtime_view, "frontend_theme_variables", ()) or ()),
            _build_settings_theme_variables(runtime_view, settings_values or {}),
            *theme_document["theme_variables"],
        ]),
        "title_driver": serialize_frontend_value(getattr(runtime_view, "frontend_title_driver", None)),
        "content_callbacks": serialize_frontend_values(getattr(runtime_view, "frontend_content_callbacks", ()) or ()),
    }


_build_frontend_document_payload = build_frontend_document_payload


def _build_settings_theme_variables(runtime_view, settings_values: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for definition in getattr(runtime_view, "settings_theme_variables", ()) or ():
        name = str(getattr(definition, "name", "") or "").strip()
        key = str(getattr(definition, "key", "") or "").strip()
        if not name or not key:
            continue
        value = settings_values.get(key)
        callback = getattr(definition, "callback", None)
        if callable(callback):
            try:
                value = callback(value)
            except TypeError:
                try:
                    value = callback(value, settings_values)
                except TypeError:
                    value = callback()
        if value is not None:
            output[name] = value
    return output


def _build_theme_document_payload(runtime_view) -> dict[str, list[Any]]:
    extension_id = str(getattr(runtime_view, "extension_id", "") or "").strip()
    output = {
        "document_attributes": [],
        "head_tags": [],
        "theme_variables": [],
    }
    if not extension_id:
        return output
    host = get_extension_host()
    service = host.make("theme", None) if host is not None else None
    if service is None:
        return output
    definitions = service.get_definitions(extension_id=extension_id)
    for definition in definitions:
        payload = definition.callback
        if callable(payload):
            payload = payload({}, {})
        if definition.key == "variables" and isinstance(payload, dict):
            output["theme_variables"].append(payload)
        elif definition.key == "document_attributes" and isinstance(payload, dict):
            output["document_attributes"].append(payload)
        elif definition.key == "head_tag" and isinstance(payload, dict):
            output["head_tags"].append(payload)
    return output


def _normalize_content_callback_payload(callback) -> dict[str, Any]:
    if isinstance(callback, dict):
        return {
            "callback": serialize_frontend_value(callback.get("callback")),
            "priority": int(callback.get("priority") or 0),
        }
    return {
        "callback": serialize_frontend_value(callback),
        "priority": 0,
    }


def _build_extension_forum_settings(
    settings_definition: dict[str, Any] | None,
    settings_values: dict[str, Any],
) -> dict[str, Any]:
    keys = tuple((settings_definition or {}).get("forum_settings_keys") or ())
    output = {
        key: settings_values.get(key)
        for key in keys
    }
    for definition in (settings_definition or {}).get("forum_serializations") or ():
        attribute = str(getattr(definition, "attribute", "") or "").strip()
        key = str(getattr(definition, "key", "") or "").strip()
        if not attribute or not key:
            continue
        value = settings_values.get(key)
        callback = getattr(definition, "callback", None)
        if callable(callback):
            try:
                value = callback(value)
            except TypeError:
                try:
                    value = callback(value, settings_values)
                except TypeError:
                    value = callback()
        output[attribute] = value
    return output
