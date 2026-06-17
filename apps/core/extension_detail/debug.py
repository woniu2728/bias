from __future__ import annotations

from apps.core.extension_detail.frontend import _build_extension_frontend_document
from apps.core.extension_detail.frontend import _build_runtime_surface_view
from apps.core.extension_detail.frontend import _resolve_extension_frontend_admin_entry
from apps.core.extension_detail.frontend import _resolve_extension_frontend_forum_entry
from apps.core.extension_detail.frontend import _resolve_extension_operations_pages
from apps.core.extension_detail.frontend import _resolve_extension_permissions_pages
from apps.core.extension_detail.frontend import _resolve_extension_settings_pages
from apps.core.extension_detail.models import _serialize_extension_migration_execution
from apps.core.extension_detail.models import _serialize_extension_migration_plan
from apps.core.extension_detail.settings_theme import _build_extension_settings_runtime
from apps.core.extension_detail.settings_theme import _build_extension_system_hooks
from apps.core.extension_detail.settings_theme import _build_extension_theme_runtime
from apps.core.extension_validation_context import resolve_available_extension_ids_for_validation
from apps.core.extensions.admin_manifest import manifest_attr
from apps.core.extensions.validation import validate_extension_manifests_with_available_ids
from apps.core.extensions.validation_inspection import (
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    resolve_admin_surface_implementation,
)
from pathlib import Path

def _build_extension_debug_info(extension):
    from apps.core.extension_detail.orchestrator import _resolve_extension_runtime_record
    runtime_record = _resolve_extension_runtime_record(extension)
    frontend_admin_entry = _resolve_extension_frontend_admin_entry(extension, runtime_record)
    frontend_forum_entry = _resolve_extension_frontend_forum_entry(extension, runtime_record)
    settings_pages = _resolve_extension_settings_pages(extension, runtime_record)
    permissions_pages = _resolve_extension_permissions_pages(extension, runtime_record)
    operations_pages = _resolve_extension_operations_pages(extension, runtime_record)
    runtime_surface_view = _build_runtime_surface_view(
        extension,
        runtime_record,
        frontend_admin_entry=frontend_admin_entry,
        frontend_forum_entry=frontend_forum_entry,
        settings_pages=settings_pages,
        permissions_pages=permissions_pages,
        operations_pages=operations_pages,
    )
    manifest_path = manifest_attr(extension, "path")
    extension_root_path = Path(manifest_path) if manifest_path else None
    extensions_base_path = extension_root_path.parent if extension_root_path is not None else None
    inspection = inspect_frontend_admin_entry(
        runtime_surface_view,
        extensions_base_path=extensions_base_path,
    )
    forum_inspection = inspect_frontend_forum_entry(
        runtime_surface_view,
        extensions_base_path=extensions_base_path,
    )
    backend_inspection = inspect_backend_entry(
        extension.manifest,
        extensions_base_path=extensions_base_path,
    )
    validation_issues = []
    if extension.source == "filesystem":
        validation_result = validate_extension_manifests_with_available_ids(
            [extension.manifest],
            available_extension_ids=resolve_available_extension_ids_for_validation(),
            extensions_base_path=extensions_base_path,
            strict_runtime_hooks=True,
        )
        validation_issues = [
            {
                "level": issue.level,
                "code": issue.code,
                "field": issue.field,
                "message": issue.message,
            }
            for issue in validation_result.issues
        ]

    expected_settings_path = f"/admin/extensions/{extension.id}/settings"
    expected_permissions_path = f"/admin/extensions/{extension.id}/permissions"
    expected_operations_path = f"/admin/extensions/{extension.id}/operations"
    expected_forum_entry = f"extensions/{extension.id}/frontend/forum/index.js"
    admin_surface_statuses = [
        {
            "key": "detail",
            "label": "详情页",
            **resolve_admin_surface_implementation(runtime_surface_view, "detail", inspection["available_exports"]),
        },
        {
            "key": "settings",
            "label": "设置页",
            **resolve_admin_surface_implementation(runtime_surface_view, "settings", inspection["available_exports"]),
        },
        {
            "key": "permissions",
            "label": "权限页",
            **resolve_admin_surface_implementation(runtime_surface_view, "permissions", inspection["available_exports"]),
        },
        {
            "key": "operations",
            "label": "操作页",
            **resolve_admin_surface_implementation(runtime_surface_view, "operations", inspection["available_exports"]),
        },
    ]

    return {
        "manifest_path": manifest_path,
        "frontend_admin_entry": {
            "entry": inspection["entry"],
            "entry_type": inspection["entry_type"],
            "exists": inspection["exists"],
            "resolved_path": inspection["resolved_path"],
            "required_exports": list(inspection["required_exports"]),
            "optional_exports": list(inspection["optional_exports"]),
            "available_exports": list(inspection["available_exports"]),
        },
        "frontend_forum_entry": {
            "entry": forum_inspection["entry"],
            "entry_type": forum_inspection["entry_type"],
            "exists": forum_inspection["exists"],
            "resolved_path": forum_inspection["resolved_path"],
            "required_exports": list(forum_inspection["required_exports"]),
            "optional_exports": list(forum_inspection["optional_exports"]),
            "available_exports": list(forum_inspection["available_exports"]),
        },
        "backend_entry": {
            "entry": backend_inspection["entry"],
            "entry_type": backend_inspection["entry_type"],
            "exists": backend_inspection["exists"],
            "resolved_path": backend_inspection["resolved_path"],
            "available_hooks": list(backend_inspection["available_hooks"]),
        },
        "system_hooks": _build_extension_system_hooks(runtime_record),
        "settings_runtime": _build_extension_settings_runtime(runtime_record),
        "frontend_document": _build_extension_frontend_document(runtime_record),
        "theme_runtime": _build_extension_theme_runtime(runtime_record),
        "migration_execution": _serialize_extension_migration_execution(extension),
        "migration_plan": _serialize_extension_migration_plan(extension),
        "admin_surface_statuses": admin_surface_statuses,
        "route_bindings": [
            {
                "key": "settings",
                "label": "设置页",
                "declared": next(iter(settings_pages), ""),
                "expected": expected_settings_path,
                "matches_expected": next(iter(settings_pages), "") == expected_settings_path if settings_pages else False,
            },
            {
                "key": "permissions",
                "label": "权限页",
                "declared": next(iter(permissions_pages), ""),
                "expected": expected_permissions_path,
                "matches_expected": next(iter(permissions_pages), "") == expected_permissions_path if permissions_pages else False,
            },
            {
                "key": "operations",
                "label": "操作页",
                "declared": next(iter(operations_pages), ""),
                "expected": expected_operations_path,
                "matches_expected": next(iter(operations_pages), "") == expected_operations_path if operations_pages else False,
            },
            {
                "key": "frontend_forum_entry",
                "label": "前台入口",
                "declared": frontend_forum_entry,
                "expected": expected_forum_entry,
                "matches_expected": str(frontend_forum_entry or "").strip() == expected_forum_entry,
            },
        ],
        "validation_issues": validation_issues,
    }

def _serialize_debug_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _serialize_debug_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_serialize_debug_value(item) for item in value]
    return getattr(value, "__name__", str(value))
