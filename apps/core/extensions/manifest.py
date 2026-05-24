from __future__ import annotations

import json
from pathlib import Path

from apps.core.extensions.exceptions import ExtensionManifestError
from apps.core.extensions.types import ExtensionDiscoveryResult, ExtensionManifest


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
            migration_namespace=str(payload.get("migration_namespace") or "").strip(),
            source="filesystem",
            path=str(manifest_path.parent),
            extra=dict(payload.get("extra") or {}),
        )
