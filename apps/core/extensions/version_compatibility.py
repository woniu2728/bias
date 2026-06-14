from __future__ import annotations

from apps.core.extensions.types import ExtensionManifest
from apps.core.extensions.validation_rules import SEMVER_PATTERN, VERSION_RANGE_PATTERN
from apps.core.version import APP_VERSION


def resolve_bias_version_compatibility(manifest: ExtensionManifest, *, current_version: str | None = None) -> dict[str, str | bool]:
    target_version = str(current_version or APP_VERSION or "").strip()
    version_range = str(manifest.compatibility.bias_version or "").strip()
    if not version_range:
        return {
            "compatible": True,
            "current_version": target_version,
            "required_range": "",
            "message": "",
        }

    if not target_version or not SEMVER_PATTERN.match(target_version):
        return {
            "compatible": False,
            "current_version": target_version,
            "required_range": version_range,
            "message": f"当前 Bias 版本 {target_version or '未知'} 无法用于校验扩展兼容范围 {version_range}。",
        }

    if not VERSION_RANGE_PATTERN.match(version_range):
        return {
            "compatible": False,
            "current_version": target_version,
            "required_range": version_range,
            "message": f"扩展声明的 Bias 兼容范围非法：{version_range}。",
        }

    compatible = matches_simple_version_range(target_version, version_range)
    if compatible:
        return {
            "compatible": True,
            "current_version": target_version,
            "required_range": version_range,
            "message": "",
        }
    return {
        "compatible": False,
        "current_version": target_version,
        "required_range": version_range,
        "message": f"当前 Bias 版本 {target_version} 不满足扩展声明的兼容范围 {version_range}。",
    }


def matches_simple_version_range(version: str, version_range: str) -> bool:
    normalized = version_range.strip()
    operator = ""
    for candidate in ("^", "~", ">=", "<=", ">", "<"):
        if normalized.startswith(candidate):
            operator = candidate
            normalized = normalized[len(candidate):]
            break

    current = parse_semver_tuple(version)
    target = parse_semver_tuple(normalized)

    if operator == "^":
        if current < target:
            return False
        upper_bound = (target[0] + 1, 0, 0)
        return current < upper_bound
    if operator == "~":
        if current < target:
            return False
        upper_bound = (target[0], target[1] + 1, 0)
        return current < upper_bound
    if operator == ">=":
        return current >= target
    if operator == "<=":
        return current <= target
    if operator == ">":
        return current > target
    if operator == "<":
        return current < target
    return current == target


def parse_semver_tuple(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.strip().split(".")
    return int(major), int(minor), int(patch)
