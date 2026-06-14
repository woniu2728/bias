from __future__ import annotations

import json
from pathlib import Path

from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.runtime import get_runtime_locale_service


_extension_locale_cache: list[dict] | None = None


def clear_extension_locale_cache() -> None:
    global _extension_locale_cache
    _extension_locale_cache = None


def get_enabled_extension_locales() -> list[dict]:
    global _extension_locale_cache
    if _extension_locale_cache is not None:
        return list(_extension_locale_cache)

    locales: list[dict] = []
    host = get_extension_host()
    if host is None:
        return locales
    locale_service = get_runtime_locale_service()
    paths_by_extension = {
        extension.extension_id: list(extension.locale_paths)
        for extension in host.get_extension_views()
    }
    if locale_service is not None:
        paths_by_extension = {
            extension.extension_id: locale_service.get_paths(extension_id=extension.extension_id)
            for extension in host.get_extension_views()
        }
    for extension_id, paths in paths_by_extension.items():
        for path in paths:
            locale_dir = Path(path)
            if not locale_dir.exists() or not locale_dir.is_dir():
                continue
            for locale_file in sorted(locale_dir.glob("*.json")):
                try:
                    messages = json.loads(locale_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(messages, dict):
                    continue
                locales.append({
                    "extension_id": extension_id,
                    "locale": locale_file.stem,
                    "messages": messages,
                })
    _extension_locale_cache = list(locales)
    return locales

__all__ = ["clear_extension_locale_cache", "get_enabled_extension_locales"]
