from __future__ import annotations

from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.validation import resolve_bias_version_compatibility


def validate_bias_compatibility(extension, *, action: str) -> None:
    compatibility = resolve_bias_version_compatibility(extension.manifest)
    if compatibility["compatible"]:
        return

    action_label = "安装" if action == "install" else "启用"
    raise ExtensionStateError(
        f"无法{action_label}扩展 {extension.id}。{compatibility['message']}",
        code=f"extension_{action}_incompatible_bias_version",
        details={
            "extension_id": extension.id,
            "current_bias_version": compatibility["current_version"],
            "required_bias_version": compatibility["required_range"],
        },
    )
