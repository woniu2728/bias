from __future__ import annotations

from typing import Callable


def serialize_extension_admin_actions(
    extension,
    *,
    runtime_record=None,
    resolve_settings_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_permissions_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_operations_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_documentation_url: Callable[[object], str],
):
    declared_actions = (
        tuple(getattr(runtime_record, "admin_actions", ()) or ())
        or extension.admin_actions
        or tuple(build_default_extension_admin_actions(
            extension,
            runtime_record=runtime_record,
            resolve_settings_pages=resolve_settings_pages,
            resolve_permissions_pages=resolve_permissions_pages,
            resolve_operations_pages=resolve_operations_pages,
            resolve_documentation_url=resolve_documentation_url,
        ))
    )
    actions = []
    for action in sorted(declared_actions, key=lambda item: (item.order, item.key)):
        if action.requires_enabled and not extension.runtime.enabled:
            continue
        actions.append({
            "key": action.key,
            "label": action.label,
            "kind": action.kind,
            "target": action.target,
            "icon": action.icon,
            "tone": action.tone,
            "opens_in_new_tab": action.opens_in_new_tab,
            "requires_enabled": action.requires_enabled,
            "description": action.description,
            "order": action.order,
        })
    return actions


def build_default_extension_admin_actions(
    extension,
    *,
    runtime_record=None,
    resolve_settings_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_permissions_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_operations_pages: Callable[[object, object | None], tuple[str, ...]],
    resolve_documentation_url: Callable[[object], str],
):
    settings_pages = resolve_settings_pages(extension, runtime_record)
    permissions_pages = resolve_permissions_pages(extension, runtime_record)
    operations_pages = resolve_operations_pages(extension, runtime_record)
    generated = [
        {
            "key": "details",
            "label": "查看详情",
            "kind": "route",
            "target": f"/admin/extensions/{extension.id}",
            "icon": "fas fa-arrow-right",
            "tone": "primary",
            "opens_in_new_tab": False,
            "requires_enabled": False,
            "description": "",
            "order": 10,
        },
    ]

    if settings_pages:
        generated.append({
            "key": "settings",
            "label": "设置",
            "kind": "route",
            "target": next(iter(settings_pages), ""),
            "icon": "fas fa-sliders-h",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 20,
        })
    if permissions_pages:
        generated.append({
            "key": "permissions",
            "label": "权限",
            "kind": "route",
            "target": next(iter(permissions_pages), ""),
            "icon": "fas fa-user-shield",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 30,
        })
    if operations_pages:
        generated.append({
            "key": "operations",
            "label": "操作",
            "kind": "route",
            "target": next(iter(operations_pages), ""),
            "icon": "fas fa-screwdriver-wrench",
            "tone": "default",
            "opens_in_new_tab": False,
            "requires_enabled": True,
            "description": "",
            "order": 40,
        })
    documentation_url = resolve_documentation_url(extension)
    if documentation_url:
        generated.append({
            "key": "documentation",
            "label": "文档",
            "kind": "link",
            "target": documentation_url,
            "icon": "fas fa-book",
            "tone": "subtle",
            "opens_in_new_tab": False,
            "requires_enabled": False,
            "description": "",
            "order": 50,
        })

    return tuple(type("_GeneratedAdminAction", (), item)() for item in generated if item.get("target"))
