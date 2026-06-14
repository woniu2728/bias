from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import get_extension_host_service, runtime_service_method


def get_runtime_search_service():
    return get_extension_host_service("search")


def get_runtime_search_extension_service(default: Any = None):
    return get_extension_host_service("search.service", default)


def apply_runtime_discussion_search(queryset, query: str, *, user: Any = None):
    service = get_runtime_search_extension_service()
    if service is None:
        return queryset
    return runtime_service_method(service, "apply_discussion_search")(queryset, query, user=user)
