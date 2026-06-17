"""
Extension detail serialization.

This file is a re-export shim migrated to apps/core/extension_detail/.
Import from apps.core.extension_detail directly.
"""
from __future__ import annotations

from apps.core.extension_detail.orchestrator import (
    serialize_admin_extension,
    serialize_admin_extensions_payload,
)
from apps.core.extension_detail.orchestrator import (  # noqa: F401
    _serialize_admin_extension,
    _serialize_admin_extension_summary,
    _serialize_admin_extensions_payload,
    _serialize_admin_extension_action_payload,
    _build_default_extension_admin_actions,
    _serialize_extension_admin_actions,
    _resolve_extension_runtime_record,
    _serialize_extension_recovery_status,
    _resolve_api_stability_label,
    _resolve_distribution_channel_label,
    _build_extension_capability_summary,
    _serialize_extension_backend_hooks,
)

from apps.core.extension_detail.models import (  # noqa: F401
    _build_extension_model_definitions,
    _build_extension_owned_models,
    _build_extension_model_ownership_audit,
    _build_extension_model_relations,
    _build_extension_model_visibility,
    _resolve_display_model,
    _model_name,
    _model_label,
    _model_module,
    _model_app_label,
    _extension_app_label,
    _extension_app_label_source,
    _model_db_table,
    _model_storage_origin,
    _model_package_migration_required,
    _model_app_label_migration_required,
    _model_migration_risk,
    _model_migration_recommended_steps,
    _build_model_app_label_migration_item,
    _serialize_extension_migration_execution,
    _serialize_extension_migration_plan,
)

from apps.core.extension_detail.resources import (  # noqa: F401
    _build_extension_resource_definitions,
    _build_extension_resource_relationships,
    _build_extension_resource_endpoints,
    _build_extension_resource_sorts,
    _build_extension_resource_filters,
    _build_extension_resource_fields,
    _build_extension_search_drivers,
    _build_extension_search_filters,
)

from apps.core.extension_detail.forum_domain import (  # noqa: F401
    _build_extension_discussion_list_filters,
    _build_extension_discussion_sorts,
    _build_extension_post_types,
    _build_extension_post_lifecycle,
    _build_extension_notification_types,
    _build_extension_user_preferences,
    _build_extension_event_listeners,
    _build_extension_realtime_broadcasts,
    _build_extension_language_packs,
    _build_extension_delivery_assets,
)

from apps.core.extension_detail.permissions import (  # noqa: F401
    _build_extension_permission_sections,
    _build_extension_permission_summary,
    _flatten_extension_permissions,
    _build_extension_permission_modules,
    _build_extension_admin_page_details,
)

from apps.core.extension_detail.frontend import (  # noqa: F401
    _build_extension_frontend_routes,
    _build_extension_frontend_document,
    _resolve_extension_frontend_admin_entry,
    _resolve_extension_frontend_forum_entry,
    _resolve_extension_frontend_outputs,
    _resolve_extension_settings_pages,
    _resolve_extension_permissions_pages,
    _resolve_extension_operations_pages,
    _build_runtime_surface_view,
    _serialize_extension_runtime_rebuild_state,
    _serialize_extension_frontend_asset_state_for_extension,
)

from apps.core.extension_detail.settings_theme import (  # noqa: F401
    _build_extension_settings_runtime,
    _build_extension_theme_runtime,
    _build_extension_system_hooks,
)

from apps.core.extension_detail.debug import (  # noqa: F401
    _build_extension_debug_info,
    _serialize_debug_value,
)

from apps.core.extension_detail._shared import (  # noqa: F401
    _serialize_callable_or_value,
)
