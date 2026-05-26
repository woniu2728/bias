from __future__ import annotations

import json
from pathlib import Path

from apps.core.extensions.exceptions import ExtensionManifestError
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionCompatibilityDefinition,
    ExtensionDiscoveryResult,
    ExtensionDistributionDefinition,
    ExtensionManifest,
    ExtensionSecurityDefinition,
    ExtensionManifestRuntimeActionDefinition,
)
from apps.core.extensions.validation import EXTENSION_ID_PATTERN, SEMVER_PATTERN


class ExtensionManifestLoader:
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)

    def discover(self) -> list[ExtensionDiscoveryResult]:
        if not self.base_path.exists():
            return []

        results: list[ExtensionDiscoveryResult] = []
        for manifest_path in sorted(self.base_path.glob("*/extension.json")):
            manifest = self.load_manifest(manifest_path)
            results.append(ExtensionDiscoveryResult(
                manifest=manifest,
                path=manifest_path.parent,
            ))
        return results

    def load_manifest(self, manifest_path: Path) -> ExtensionManifest:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ExtensionManifestError(f"扩展清单不存在: {manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise ExtensionManifestError(f"扩展清单 JSON 非法: {manifest_path}") from exc

        extension_id = str(payload.get("id") or "").strip()
        name = str(payload.get("name") or "").strip()
        version = str(payload.get("version") or "").strip()

        if not extension_id:
            raise ExtensionManifestError(f"扩展清单缺少 id: {manifest_path}")
        if not name:
            raise ExtensionManifestError(f"扩展清单缺少 name: {manifest_path}")
        if not version:
            raise ExtensionManifestError(f"扩展清单缺少 version: {manifest_path}")

        if not EXTENSION_ID_PATTERN.match(extension_id):
            raise ExtensionManifestError(f"扩展清单 id 非法: {manifest_path}")
        if not SEMVER_PATTERN.match(version):
            raise ExtensionManifestError(f"扩展清单 version 非法: {manifest_path}")

        return ExtensionManifest(
            id=extension_id,
            name=name,
            version=version,
            description=str(payload.get("description") or "").strip(),
            icon=str(payload.get("icon") or "fas fa-puzzle-piece").strip(),
            category=str(payload.get("category") or "feature").strip(),
            authors=tuple(str(item).strip() for item in payload.get("authors", []) if str(item).strip()),
            homepage=str(payload.get("homepage") or "").strip(),
            documentation_url=str(payload.get("documentation_url") or "").strip(),
            dependencies=tuple(str(item).strip() for item in payload.get("dependencies", []) if str(item).strip()),
            optional_dependencies=tuple(str(item).strip() for item in payload.get("optional_dependencies", []) if str(item).strip()),
            conflicts=tuple(str(item).strip() for item in payload.get("conflicts", []) if str(item).strip()),
            provides=tuple(str(item).strip() for item in payload.get("provides", []) if str(item).strip()),
            backend_entry=str(payload.get("backend_entry") or "").strip(),
            frontend_admin_entry=str(payload.get("frontend_admin_entry") or "").strip(),
            frontend_forum_entry=str(payload.get("frontend_forum_entry") or "").strip(),
            settings_pages=tuple(str(item).strip() for item in payload.get("settings_pages", []) if str(item).strip()),
            permissions_pages=tuple(str(item).strip() for item in payload.get("permissions_pages", []) if str(item).strip()),
            operations_pages=tuple(str(item).strip() for item in payload.get("operations_pages", []) if str(item).strip()),
            admin_actions=tuple(self._build_admin_action(item) for item in payload.get("admin_actions", []) if isinstance(item, dict)),
            compatibility=self._build_compatibility(payload.get("compatibility")),
            security=self._build_security(payload.get("security")),
            distribution=self._build_distribution(payload.get("distribution")),
            runtime_actions=tuple(self._build_runtime_action(item) for item in payload.get("runtime_actions", []) if isinstance(item, dict)),
            migration_namespace=str(payload.get("migration_namespace") or "").strip(),
            source="filesystem",
            path=str(manifest_path.parent),
            extra=dict(payload.get("extra") or {}),
        )

    def _build_admin_action(self, payload: dict) -> ExtensionAdminActionDefinition:
        return ExtensionAdminActionDefinition(
            key=str(payload.get("key") or "").strip(),
            label=str(payload.get("label") or "").strip(),
            kind=str(payload.get("kind") or "route").strip() or "route",
            target=str(payload.get("target") or "").strip(),
            icon=str(payload.get("icon") or "").strip(),
            tone=str(payload.get("tone") or "default").strip() or "default",
            opens_in_new_tab=bool(payload.get("opens_in_new_tab", False)),
            requires_enabled=bool(payload.get("requires_enabled", False)),
            description=str(payload.get("description") or "").strip(),
            order=int(payload.get("order", 100) or 100),
        )

    def _build_compatibility(self, payload: dict | None) -> ExtensionCompatibilityDefinition:
        data = payload if isinstance(payload, dict) else {}
        return ExtensionCompatibilityDefinition(
            bias_version=str(data.get("bias_version") or "").strip(),
            api_version=str(data.get("api_version") or "1.0").strip() or "1.0",
            api_stability=str(data.get("api_stability") or "experimental").strip() or "experimental",
            api_stability_label=str(data.get("api_stability_label") or "").strip(),
            breaking_change_policy=str(data.get("breaking_change_policy") or "").strip(),
        )

    def _build_security(self, payload: dict | None) -> ExtensionSecurityDefinition:
        data = payload if isinstance(payload, dict) else {}
        return ExtensionSecurityDefinition(
            policy_url=str(data.get("policy_url") or "").strip(),
            support_email=str(data.get("support_email") or "").strip(),
            capabilities_notice=str(data.get("capabilities_notice") or "").strip(),
        )

    def _build_distribution(self, payload: dict | None) -> ExtensionDistributionDefinition:
        data = payload if isinstance(payload, dict) else {}
        return ExtensionDistributionDefinition(
            channel=str(data.get("channel") or "private").strip() or "private",
            channel_label=str(data.get("channel_label") or "").strip(),
            signing_key_id=str(data.get("signing_key_id") or "").strip(),
            signature_url=str(data.get("signature_url") or "").strip(),
        )

    def _build_runtime_action(self, payload: dict) -> ExtensionManifestRuntimeActionDefinition:
        return ExtensionManifestRuntimeActionDefinition(
            key=str(payload.get("key") or "").strip(),
            label=str(payload.get("label") or "").strip(),
            hook=str(payload.get("hook") or "").strip(),
            tone=str(payload.get("tone") or "default").strip() or "default",
            confirm_title=str(payload.get("confirm_title") or "").strip(),
            confirm_message=str(payload.get("confirm_message") or "").strip(),
            confirm_text=str(payload.get("confirm_text") or "").strip(),
            success_message=str(payload.get("success_message") or "").strip(),
            requires_enabled=bool(payload.get("requires_enabled", False)),
            requires_installed=bool(payload.get("requires_installed", False)),
            description=str(payload.get("description") or "").strip(),
            order=int(payload.get("order", 100) or 100),
        )
