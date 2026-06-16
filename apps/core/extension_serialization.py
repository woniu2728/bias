from __future__ import annotations

from apps.core import admin_content_api


def serialize_admin_extension(extension, *, include_permission_details: bool = False) -> dict:
    return admin_content_api.serialize_admin_extension(
        extension,
        include_permission_details=include_permission_details,
    )


def serialize_admin_extensions_payload(extensions) -> dict:
    return admin_content_api.serialize_admin_extensions_payload(extensions)
