from __future__ import annotations

from pathlib import Path

from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.types import ExtensionDiscoveryResult, ExtensionManifest


def resolve_extension_discovery_result(manifest: ExtensionManifest) -> ExtensionDiscoveryResult:
    extension = Extension.from_manifest(manifest)
    record = extension.discover()
    merged_manifest = ExtensionManifest(
        id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        icon=manifest.icon,
        category=manifest.category,
        authors=manifest.authors,
        homepage=manifest.homepage,
        documentation_url=manifest.documentation_url,
        dependencies=manifest.dependencies,
        optional_dependencies=manifest.optional_dependencies,
        conflicts=manifest.conflicts,
        provides=manifest.provides,
        backend_entry=manifest.backend_entry,
        frontend_admin_entry=extension.frontend_admin_entry,
        frontend_forum_entry=extension.frontend_forum_entry,
        settings_pages=extension.settings_pages,
        permissions_pages=extension.permissions_pages,
        operations_pages=extension.operations_pages,
        admin_actions=tuple(record.admin_actions) or manifest.admin_actions,
        operations_profile=manifest.operations_profile,
        compatibility=manifest.compatibility,
        security=manifest.security,
        distribution=manifest.distribution,
        runtime_actions=tuple(record.runtime_actions) or manifest.runtime_actions,
        settings_schema=tuple(record.settings_schema) or manifest.settings_schema,
        migration_namespace=manifest.migration_namespace,
        django_app_config=manifest.django_app_config,
        django_app_label=manifest.django_app_label,
        source=manifest.source,
        path=manifest.path,
        extra=manifest.extra,
    )
    return ExtensionDiscoveryResult(
        manifest=merged_manifest,
        path=extension.path or Path(manifest.path),
        frontend_admin_entry=extension.frontend_admin_entry,
        frontend_forum_entry=extension.frontend_forum_entry,
        frontend_routes=tuple(record.frontend_routes),
        settings_pages=extension.settings_pages,
        permissions_pages=extension.permissions_pages,
        operations_pages=extension.operations_pages,
        settings_schema=tuple(record.settings_schema),
        settings_defaults=tuple(record.settings_defaults),
        settings_reset_rules=tuple(record.settings_reset_rules),
        settings_frontend_cache_keys=tuple(record.settings_frontend_cache_keys),
        settings_theme_variables=tuple(record.settings_theme_variables),
        settings_forum_serializations=tuple(record.settings_forum_serializations),
        forum_settings_keys=tuple(record.forum_settings_keys),
        permissions=tuple(record.permissions),
        admin_pages=tuple(record.admin_pages),
        notification_types=tuple(record.notification_types),
        user_preferences=tuple(record.user_preferences),
        language_packs=tuple(record.language_packs),
        post_types=tuple(record.post_types),
        search_filters=tuple(record.search_filters),
        discussion_list_queries=tuple(record.discussion_list_queries),
        discussion_sorts=tuple(record.discussion_sorts),
        discussion_list_filters=tuple(record.discussion_list_filters),
        locale_paths=tuple(record.locale_paths),
        formatter_pipeline=tuple(record.formatter_pipeline),
        formatter_callbacks=tuple(record.formatter_callbacks),
        resource_definitions=tuple(record.resource_definitions),
        resource_fields=tuple(record.resource_fields),
        resource_field_mutators=tuple(record.resource_field_mutators),
        resource_relationships=tuple(record.resource_relationships),
        resource_endpoints=tuple(record.resource_endpoints),
        resource_sorts=tuple(record.resource_sorts),
        resource_filters=tuple(record.resource_filters),
        model_definitions=tuple(record.model_definitions),
        model_visibility=tuple(record.model_visibility),
        model_relations=tuple(record.model_relations),
        model_casts=tuple(record.model_casts),
        model_defaults=tuple(record.model_defaults),
        model_slug_drivers=tuple(record.model_slug_drivers),
        search_drivers=tuple(record.search_drivers),
        search_indexes=tuple(record.search_indexes),
        event_listeners=tuple(record.event_listeners),
        realtime_included=tuple(record.realtime_included),
        realtime_discussion_visibility=tuple(record.realtime_discussion_visibility),
        realtime_discussion_transports=tuple(record.realtime_discussion_transports),
        realtime_discussion_broadcasts=tuple(record.realtime_discussion_broadcasts),
        discussion_lifecycle=tuple(record.discussion_lifecycle),
        post_lifecycle=tuple(record.post_lifecycle),
        runtime_actions=tuple(record.runtime_actions),
        admin_actions=tuple(record.admin_actions),
    )


def resolve_extension_manifest_contract(
    manifest: ExtensionManifest,
) -> tuple[ExtensionManifest, object]:
    result = resolve_extension_discovery_result(manifest)
    return result.manifest, result
