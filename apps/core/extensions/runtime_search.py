from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import RuntimeServiceProxy, get_extension_host_service

_search = RuntimeServiceProxy("search.service")


def get_runtime_search_service():
    return get_extension_host_service("search")


def get_runtime_search_extension_service(default: Any = None):
    return get_extension_host_service("search.service", default)


def apply_runtime_discussion_search(queryset, query: str, *, user: Any = None):
    try:
        return _search.apply_discussion_search(queryset, query, user=user)
    except RuntimeError:
        return queryset
