from __future__ import annotations

from apps.core.resource_registry import ResourceRegistry, get_resource_registry
from extensions.discussions.backend.handlers import register_discussion_core_resource_endpoints
from extensions.posts.backend.handlers import register_post_core_resource_endpoints
from extensions.users.backend.handlers import register_user_core_resource_endpoints


def bootstrap_core_resource_endpoints(registry: ResourceRegistry | None = None) -> ResourceRegistry:
    resolved_registry = registry or get_resource_registry()
    register_user_core_resource_endpoints(resolved_registry)
    register_discussion_core_resource_endpoints(resolved_registry)
    register_post_core_resource_endpoints(resolved_registry)
    return resolved_registry
