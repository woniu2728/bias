from __future__ import annotations

from apps.core.resource_registry import (
    ResourceDefinition,
    get_resource_registry,
)


_resources_bootstrapped = False


def bootstrap_forum_resource_fields() -> None:
    global _resources_bootstrapped
    if _resources_bootstrapped:
        return

    registry = get_resource_registry()

    registry.register_resource(
        ResourceDefinition(
            resource="forum",
            module_id="core",
            resolver=_serialize_forum_base,
            description="论坛公开运行时资源。",
        )
    )
    registry.register_resource(
        ResourceDefinition(
            resource="admin_stats",
            module_id="core",
            resolver=_serialize_admin_stats_base,
            description="后台运行状态与统计资源。",
        )
    )
    _resources_bootstrapped = True


def _serialize_forum_base(forum, context: dict) -> dict:
    return {}


def _serialize_admin_stats_base(stats, context: dict) -> dict:
    return dict(stats or {})
