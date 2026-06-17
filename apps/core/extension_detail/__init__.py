"""
Extension detail package — admin extension serialization.

Each submodule owns a cohesive subset of the original
apps/core/admin_extension_detail.py functions.
Import from this package directly.
"""
from __future__ import annotations

from apps.core.extension_detail.orchestrator import (
    _build_extension_capability_summary,
    _resolve_extension_runtime_record,
    _serialize_admin_extension,
    _serialize_admin_extension_action_payload,
    _serialize_admin_extension_summary,
    _serialize_admin_extensions_payload,
    _serialize_extension_backend_hooks,
    _serialize_extension_recovery_status,
    serialize_admin_extension,
    serialize_admin_extensions_payload,
)
