from __future__ import annotations


def is_product_visible_extension(definition) -> bool:
    if definition is None:
        return False
    if definition.source != "filesystem":
        return False

    extra = dict(getattr(definition.manifest, "extra", {}) or {})
    if bool(extra.get("product_hidden", False)):
        return False
    return True


def is_extension_auto_installed(definition) -> bool:
    if definition is None or definition.source != "filesystem":
        return False
    extra = dict(getattr(definition.manifest, "extra", {}) or {})
    return bool(extra.get("auto_install", False))


def is_extension_auto_enabled(definition) -> bool:
    if not is_extension_auto_installed(definition):
        return False
    extra = dict(getattr(definition.manifest, "extra", {}) or {})
    if "auto_enable" in extra:
        return bool(extra.get("auto_enable"))
    return True


def is_extension_protected(definition) -> bool:
    if definition is None:
        return False
    extra = dict(getattr(definition.manifest, "extra", {}) or {})
    return bool(extra.get("protected", False))


def get_extension_protected_reason(definition) -> str:
    if not is_extension_protected(definition):
        return ""
    extra = dict(getattr(definition.manifest, "extra", {}) or {})
    return str(extra.get("protected_reason") or "该扩展承载 Bias 基础能力，不能停用或卸载。").strip()
