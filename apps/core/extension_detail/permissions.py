from __future__ import annotations

from apps.core.forum_registry import get_forum_registry

def _build_extension_permission_sections(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    sections = []
    for section in get_forum_registry().get_permission_sections():
        permissions = [
            permission
            for permission in section.get("permissions", [])
            if permission.get("module_id") in module_ids
        ]
        if not permissions:
            continue
        sections.append({
            "name": section.get("name", ""),
            "label": section.get("label", ""),
            "permission_count": len(permissions),
            "permissions": permissions,
        })
    return sections

def _build_extension_permission_summary(sections):
    permission_count = sum(len(section["permissions"]) for section in sections)
    module_ids = {
        permission["module_id"]
        for section in sections
        for permission in section["permissions"]
    }
    return {
        "section_count": len(sections),
        "permission_count": permission_count,
        "module_count": len(module_ids),
    }

def _flatten_extension_permissions(sections):
    return [
        permission
        for section in sections
        for permission in section.get("permissions", [])
    ]

def _build_extension_permission_modules(sections):
    counts = {}
    for section in sections:
        for permission in section["permissions"]:
            module_id = permission["module_id"]
            counts[module_id] = counts.get(module_id, 0) + 1
    return [
        {
            "module_id": module_id,
            "permission_count": counts[module_id],
        }
        for module_id in sorted(counts.keys())
    ]

def _build_extension_admin_page_details(extension):
    module_ids = set(extension.module_ids or ())
    if not module_ids:
        return []

    pages = []
    seen_paths = set()
    for page in get_forum_registry().get_admin_pages():
        if page.module_id not in module_ids:
            continue
        if page.path in seen_paths:
            continue
        seen_paths.add(page.path)
        pages.append({
            "path": page.path,
            "label": page.label,
            "icon": page.icon,
            "module_id": page.module_id,
            "nav_section": page.nav_section,
            "description": page.description,
            "settings_group": page.settings_group,
        })
    return pages
