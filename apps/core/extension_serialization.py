from __future__ import annotations

from apps.core.admin_content_api import _serialize_admin_extension, _serialize_admin_extensions_payload


def serialize_admin_extension(extension, *, include_permission_details: bool = False) -> dict:
    return _serialize_admin_extension(
        extension,
        include_permission_details=include_permission_details,
    )


def serialize_admin_extensions_payload(extensions) -> dict:
    return _serialize_admin_extensions_payload(extensions)
