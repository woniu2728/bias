from __future__ import annotations

from apps.core.resource_registry import (
    ResourceDefinition,
    get_resource_registry,
)


_bootstrapped_registry_ids: set[int] = set()


def reset_forum_resource_bootstrap_state() -> None:
    _bootstrapped_registry_ids.clear()


def bootstrap_forum_resource_fields(registry=None) -> None:
    registry = registry or get_resource_registry()
    registry_id = id(registry)
    if registry_id in _bootstrapped_registry_ids:
        return

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
    _bootstrapped_registry_ids.add(registry_id)


def _serialize_forum_base(forum, context: dict) -> dict:
    return {}


def _serialize_admin_stats_base(stats, context: dict) -> dict:
    return dict(stats or {})
