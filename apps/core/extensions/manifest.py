from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

from django.conf import settings

from apps.core.extensions.definition_assembler import resolve_extension_discovery_result
from apps.core.extensions.exceptions import ExtensionManifestError
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionCompatibilityDefinition,
    ExtensionDiscoveryResult,
    ExtensionDistributionDefinition,
    ExtensionManifest,
    ExtensionManifestSettingFieldDefinition,
    ExtensionManifestSettingOptionDefinition,
    ExtensionSecurityDefinition,
    ExtensionManifestRuntimeActionDefinition,
)
from apps.core.extensions.validation import EXTENSION_ID_PATTERN, SEMVER_PATTERN


_distribution_manifest_cache: list[ExtensionManifest] | None = None


class ExtensionManifestLoader:
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)

    def discover(self) -> list[ExtensionDiscoveryResult]:
        return [
            resolve_extension_discovery_result(manifest)
            for manifest in self.discover_manifests()
        ]

    def discover_manifests(self) -> list[ExtensionManifest]:
        results: list[ExtensionManifest] = []

        if not self.base_path.exists():
            results.extend(self.discover_distribution_manifests())
            return self._deduplicate_manifests(results)

        for manifest_path in sorted(self.base_path.glob("*/extension.json")):
            results.append(self.load_manifest_only(manifest_path))
        results.extend(self.discover_distribution_manifests())
        return self._deduplicate_manifests(results)

    def discover_distribution_manifests(self) -> list[ExtensionManifest]:
        global _distribution_manifest_cache
        if not getattr(settings, "BIAS_EXTENSION_PACKAGE_DISCOVERY", True):
            return []
        if _distribution_manifest_cache is not None:
            return list(_distribution_manifest_cache)

        manifests: list[ExtensionManifest] = []
        for distribution in sorted(metadata.distributions(), key=lambda item: (item.metadata.get("Name") or "").lower()):
            extension_files = [
                file
                for file in (distribution.files or ())
                if self._is_distribution_manifest_file(str(file).replace("\\", "/"))
            ]
            for file in extension_files:
                manifest_path = Path(str(distribution.locate_file(file)))
                if not manifest_path.exists():
                    continue
                try:
                    manifest = self.load_manifest_only(manifest_path)
                except ExtensionManifestError:
                    continue
                package_name = distribution.metadata.get("Name") or ""
                manifest = self._with_distribution_source(
                    manifest,
                    package_name=str(package_name or "").strip(),
                    package_version=str(distribution.version or "").strip(),
                )
                manifests.append(manifest)
        _distribution_manifest_cache = list(manifests)
        return manifests

    def load_manifest(self, manifest_path: Path) -> tuple[ExtensionManifest, ExtensionDiscoveryResult]:
        result = resolve_extension_discovery_result(self.load_manifest_only(manifest_path))
        return result.manifest, result

    def load_manifest_only(self, manifest_path: Path) -> ExtensionManifest:
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

        manifest = ExtensionManifest(
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
            operations_profile=dict(payload.get("operations_profile") or {}) if isinstance(payload.get("operations_profile"), dict) else {},
            compatibility=self._build_compatibility(payload.get("compatibility")),
            security=self._build_security(payload.get("security")),
            distribution=self._build_distribution(payload.get("distribution")),
            runtime_actions=tuple(self._build_runtime_action(item) for item in payload.get("runtime_actions", []) if isinstance(item, dict)),
            settings_schema=tuple(self._build_settings_field(item) for item in payload.get("settings_schema", []) if isinstance(item, dict)),
            migration_namespace=str(payload.get("migration_namespace") or "").strip(),
            django_app_config=str(payload.get("django_app_config") or "").strip(),
            source="filesystem",
            path=str(manifest_path.parent),
            extra=dict(payload.get("extra") or {}),
        )
        return manifest

    def _with_distribution_source(
        self,
        manifest: ExtensionManifest,
        *,
        package_name: str,
        package_version: str,
    ) -> ExtensionManifest:
        extra = {
            **dict(manifest.extra or {}),
            "python_distribution": {
                "name": package_name,
                "version": package_version,
            },
        }
        return ExtensionManifest(
            **{
                **manifest.__dict__,
                "source": "python-package",
                "extra": extra,
            }
        )

    def _deduplicate_manifests(self, manifests: list[ExtensionManifest]) -> list[ExtensionManifest]:
        by_id: dict[str, ExtensionManifest] = {}
        for manifest in manifests:
            existing = by_id.get(manifest.id)
            if existing is not None and existing.source == "filesystem":
                continue
            by_id[manifest.id] = manifest
        return [by_id[key] for key in sorted(by_id.keys())]

    def _is_distribution_manifest_file(self, filename: str) -> bool:
        return (
            filename == "bias_extension.json"
            or filename.endswith("/bias_extension.json")
            or filename == "bias_extension/extension.json"
            or filename.endswith("/bias_extension/extension.json")
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

    def _build_settings_field(self, payload: dict) -> ExtensionManifestSettingFieldDefinition:
        return ExtensionManifestSettingFieldDefinition(
            key=str(payload.get("key") or "").strip(),
            label=str(payload.get("label") or "").strip(),
            type=str(payload.get("type") or "text").strip() or "text",
            default=payload.get("default", ""),
            help_text=str(payload.get("help_text") or "").strip(),
            placeholder=str(payload.get("placeholder") or "").strip(),
            required=bool(payload.get("required", False)),
            options=tuple(
                ExtensionManifestSettingOptionDefinition(
                    value=str(item.get("value") or "").strip(),
                    label=str(item.get("label") or "").strip(),
                )
                for item in payload.get("options", [])
                if isinstance(item, dict)
            ),
            multiline=bool(payload.get("multiline", False)),
            order=int(payload.get("order", 100) or 100),
        )
