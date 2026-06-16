from __future__ import annotations

import logging

from apps.core.extensions.registry import get_extension_registry
from apps.core.forum_registry import get_core_module_ids


logger = logging.getLogger(__name__)


def resolve_available_extension_ids_for_validation() -> set[str]:
    extension_ids = set(get_core_module_ids())
    try:
        extension_ids.update(item.id for item in get_extension_registry().get_extensions())
    except Exception:
        logger.warning("Failed to resolve installed extension ids for extension validation.", exc_info=True)
    return extension_ids
