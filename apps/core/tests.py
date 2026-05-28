import importlib
import json
import os
from pathlib import Path
import shutil
from subprocess import CompletedProcess
import sys
from types import SimpleNamespace
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.checks import run_checks
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from unittest.mock import Mock, patch

from apps.core.domain_events import DomainEventBus
from apps.core.extensions.builtin_adapter import adapt_builtin_module_to_extension
from apps.core.extensions.backend import run_extension_backend_hook
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.registry import ExtensionRegistry
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.validation import (
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    resolve_bias_version_compatibility,
    validate_extension_manifests,
    validate_extension_manifests_with_available_ids,
)
from apps.core.extension_service import ExtensionService
from apps.core.forum_events import (
    DiscussionCreatedEvent,
    DiscussionTagStatsRefreshEvent,
    TagStatsRefreshRequestedEvent,
    UserSuspendedEvent,
    UserUnsuspendedEvent,
)
from apps.core.forum_resources_post_events import resolve_post_event_data
from apps.core.forum_resources_users import serialize_user_payload, serialize_user_summary
from apps.core.forum_registry import get_forum_registry, get_registry_permission_codes_by_prefix
from apps.core.resource_registry import get_resource_registry
from apps.core.forum_resources_flags import register_forum_flag_resource_fields
from apps.core.resource_registry import (
    ResourceDefinition,
    ResourceFieldDefinition,
    ResourceRelationshipDefinition,
    ResourceRegistry,
)
from apps.core.bootstrap_config import load_site_bootstrap, read_site_config
from apps.core.models import AuditLog, ExtensionInstallation, Setting
from apps.core.file_service import FileUploadService
from apps.core.online_service import OnlineUserService
from apps.core.release import build_git_command, ensure_release_versions_aligned
from apps.core.search_index_service import SEARCH_INDEX_DEFINITIONS
from apps.core.settings_service import clear_runtime_setting_caches, get_setting_group
from apps.core.services import PaginationService, SearchService
from apps.core.test_runner import BiasDiscoverRunner
from apps.core.websocket_service import WebSocketService
from apps.core.websocket_auth import (
    REFRESH_TOKEN_COOKIE_NAME,
    _parse_cookie_header,
    resolve_user_from_refresh_token,
    resolve_user_from_token,
)
from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.notifications.models import Notification
from apps.posts.models import Post, PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


def make_workspace_temp_dir() -> Path:
    path = Path.cwd() / f"tmp-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class DomainEventBusTests(TestCase):
    def test_dispatches_registered_event_handlers(self):
        bus = DomainEventBus()
        received = []

        def handle_created(event):
            received.append((event.discussion_id, event.actor_user_id, event.tag_ids))

        bus.register(DiscussionCreatedEvent, handle_created)
        bus.dispatch(
            DiscussionCreatedEvent(
                discussion_id=7,
                actor_user_id=3,
                tag_ids=(11, 12),
                is_approved=True,
            )
        )

        self.assertEqual(received, [(7, 3, (11, 12))])

    def test_dispatches_handlers_for_additional_forum_events(self):
        bus = DomainEventBus()
        received = []

        def handle_suspended(event):
            received.append(("suspended", event.user_id, event.actor_user_id))

        def handle_unsuspended(event):
            received.append(("unsuspended", event.user_id, event.actor_user_id))

        bus.register(UserSuspendedEvent, handle_suspended)
        bus.register(UserUnsuspendedEvent, handle_unsuspended)
        bus.dispatch(UserSuspendedEvent(user_id=9, actor_user_id=2))
        bus.dispatch(UserUnsuspendedEvent(user_id=9, actor_user_id=2))

        self.assertEqual(
            received,
            [("suspended", 9, 2), ("unsuspended", 9, 2)],
        )


class ExtensionManifestLoaderTests(TestCase):
    def test_loader_reads_extension_manifest_from_extensions_directory(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            manifest_dir = base_dir / "extensions" / "sample-extension"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "sample-extension",
                "name": "Sample Extension",
                "version": "1.0.0",
                "description": "A sample extension.",
                "dependencies": ["core"],
                "settings_pages": ["/admin/extensions/sample"],
                "permissions_pages": ["/admin/extensions/sample/permissions"],
                "operations_pages": ["/admin/extensions/sample/operations"],
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/sample-extension",
                    }
                ],
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "run_rebuild_cache",
                        "requires_enabled": True,
                    }
                ],
                "settings_schema": [
                    {
                        "key": "theme",
                        "label": "主题",
                        "type": "select",
                        "default": "light",
                        "options": [
                            {"value": "light", "label": "浅色"},
                            {"value": "dark", "label": "深色"}
                        ]
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(base_dir / "extensions")
            results = loader.discover()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].manifest.id, "sample-extension")
            self.assertEqual(results[0].manifest.name, "Sample Extension")
            self.assertEqual(results[0].manifest.dependencies, ("core",))
            self.assertEqual(results[0].manifest.settings_pages, ("/admin/extensions/sample",))
            self.assertEqual(results[0].manifest.permissions_pages, ("/admin/extensions/sample/permissions",))
            self.assertEqual(results[0].manifest.operations_pages, ("/admin/extensions/sample/operations",))
            self.assertEqual(results[0].manifest.admin_actions[0].key, "details")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_schema[0].key, "theme")
            self.assertEqual(results[0].manifest.migration_namespace, "")
            self.assertEqual(results[0].manifest.compatibility.api_version, "1.0")
            self.assertEqual(results[0].manifest.compatibility.api_stability, "experimental")
            self.assertEqual(results[0].manifest.distribution.channel, "private")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_rejects_invalid_extension_id_and_version(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "Bad_Extension"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "Bad_Extension",
                "name": "Bad Extension",
                "version": "1.0",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            with self.assertRaisesMessage(Exception, f"扩展清单 id 非法: {manifest_dir / 'extension.json'}"):
                loader.discover()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ExtensionValidationTests(TestCase):
    def test_resolve_bias_version_compatibility_supports_simple_ranges(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.0.0")["compatible"])
        self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.2.3")["compatible"])
        self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="2.0.0")["compatible"])
        self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="0.9.9")["compatible"])

    def test_inspect_frontend_admin_entry_reports_available_exports(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        payload = inspect_frontend_admin_entry(
            extension.manifest,
            extensions_base_path=registry.extensions_path,
        )

        self.assertEqual(payload["entry_type"], "filesystem")
        self.assertTrue(payload["exists"])
        self.assertIn("resolveDetailPage", payload["available_exports"])
        self.assertIn("resolveSettingsPage", payload["available_exports"])
        self.assertIn("resolveOperationsPage", payload["available_exports"])

    def test_inspect_backend_entry_reports_available_hooks(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        payload = inspect_backend_entry(
            extension.manifest,
            extensions_base_path=registry.extensions_path,
        )

        self.assertEqual(payload["entry_type"], "filesystem")
        self.assertTrue(payload["exists"])
        self.assertIn("run_install", payload["available_hooks"])
        self.assertIn("run_migrations", payload["available_hooks"])

    def test_inspect_frontend_forum_entry_reports_available_exports(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        payload = inspect_frontend_forum_entry(
            extension.manifest,
            extensions_base_path=registry.extensions_path,
        )

        self.assertEqual(payload["entry_type"], "filesystem")
        self.assertTrue(payload["exists"])
        self.assertIn("available_exports", payload)
        self.assertEqual(payload["resolved_path"].endswith("extensions\\sample-hello\\frontend\\forum\\index.js") or payload["resolved_path"].endswith("extensions/sample-hello/frontend/forum/index.js"), True)

    def test_validate_extension_manifests_requires_frontend_admin_entry_for_admin_pages(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_admin_entry_declaration" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_dependency_and_missing_admin_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            manifest_path = manifest_dir / "extension.json"
            manifest_path.write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core", "missing-one"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_dependency" for item in result.issues))
            self.assertTrue(any(item.code == "missing_frontend_admin_entry" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_admin_exports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveSettingsPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "missing_frontend_admin_export"
                and "resolveOperationsPage" in item.message
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_generated_settings_surface(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "settings_schema": [
                    {
                        "key": "welcome_message",
                        "label": "欢迎语",
                        "type": "text",
                        "default": "hello",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(result.ok)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_generated_permissions_and_operations_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "permissions_pages": ["/admin/extensions/alpha-tools/permissions"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/alpha-tools",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(result.ok)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_forum_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_forum_entry" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_forum_export(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            forum_dir = manifest_dir / "frontend" / "forum"
            forum_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")
            (forum_dir / "index.js").write_text(
                "export const bootForumExtension = null\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_forum_export" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_mismatched_extension_admin_page(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/other-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_extension_admin_page" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_admin_actions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "admin_actions": [
                    {
                        "key": "broken",
                        "label": "坏动作",
                        "kind": "command",
                        "target": "/admin/extensions/alpha-tools",
                        "tone": "loud",
                    },
                    {
                        "key": "broken-route",
                        "label": "坏路由",
                        "kind": "route",
                        "target": "admin/extensions/alpha-tools",
                        "tone": "default",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_admin_action_kind" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_admin_action_tone" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_admin_action_target" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_runtime_actions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "",
                    },
                    {
                        "key": "rebuild-cache",
                        "label": "",
                        "hook": "run_rebuild_cache",
                        "tone": "loud",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertEqual(result.error_count, 5)
            self.assertTrue(any(item.code == "invalid_runtime_action" for item in result.issues))
            self.assertTrue(any(item.code == "duplicate_runtime_action_key" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_runtime_action_tone" for item in result.issues))
            self.assertTrue(any(item.code == "missing_backend_entry_declaration" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_strict_reports_missing_runtime_backend_hook(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "run_rebuild_cache",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                strict_runtime_hooks=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "missing_backend_hook" and "run_rebuild_cache" in item.message
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_strict_reports_missing_migration_backend_hook(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "migration_namespace": "extensions.alpha_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                strict_runtime_hooks=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "missing_backend_hook" and item.field == "migration_namespace"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_migration_files(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            migrations_dir = manifest_dir / "backend" / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "migration_namespace": "extensions.alpha_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text(
                "def run_migrations(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_extension_migration_files" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_migration_file_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            migrations_dir = manifest_dir / "backend" / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
            (migrations_dir / "initial.py").write_text(
                "VALUE = 'missing-entrypoint'\n",
                encoding="utf-8",
            )
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "migration_namespace": "extensions.alpha_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text(
                "def run_migrations(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_extension_migration_filename" for item in result.issues))
            self.assertTrue(any(item.code == "missing_extension_migration_entrypoint" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_settings_schema(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "settings_schema": [
                    {
                        "key": "mode",
                        "label": "",
                        "type": "select",
                        "options": [],
                    },
                    {
                        "key": "mode",
                        "label": "模式",
                        "type": "json",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "duplicate_extension_setting_key" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_extension_setting_type" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_extension_setting_options" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_ecosystem_metadata(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "compatibility": {
                    "bias_version": "latest",
                    "api_version": "v1",
                    "api_stability": "ga",
                },
                "distribution": {
                    "channel": "store",
                    "signature_url": "https://example.com/signature.txt",
                },
                "security": {
                    "support_email": "security-at-example.com",
                },
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_bias_version_range" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_api_version" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_api_stability" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_distribution_channel" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_security_support_email" for item in result.issues))
            self.assertTrue(any(item.code == "signature_url_without_key" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ExtensionManagementCommandTests(TestCase):
    def test_extension_management_commands_skip_django_system_checks(self):
        from apps.core.management.commands.create_extension import Command as CreateExtensionCommand
        from apps.core.management.commands.validate_extensions import Command as ValidateExtensionsCommand

        self.assertEqual(CreateExtensionCommand.requires_system_checks, [])
        self.assertEqual(ValidateExtensionsCommand.requires_system_checks, [])

    @patch("apps.core.management.commands.validate_extensions.get_builtin_module_ids", return_value=("core",))
    def test_validate_extensions_command_uses_builtin_module_snapshot(self, get_builtin_module_ids_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        get_builtin_module_ids_mock.assert_called_once_with()

    def test_create_extension_command_scaffolds_manifest_and_admin_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command(
                    "create_extension",
                    "alpha-tools",
                    "--name",
                    "Alpha Tools",
                    "--description",
                    "用于测试脚手架",
                )

                extension_dir = Path(temp_dir) / "extensions" / "alpha-tools"
                manifest = json.loads((extension_dir / "extension.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["id"], "alpha-tools")
                self.assertEqual(manifest["name"], "Alpha Tools")
                self.assertEqual(manifest["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
                self.assertEqual(manifest["frontend_forum_entry"], "extensions/alpha-tools/frontend/forum/index.js")
                self.assertEqual(manifest["admin_actions"][0]["key"], "details")
                self.assertEqual(manifest["settings_schema"][0]["key"], "welcome_message")
                self.assertEqual(manifest["migration_namespace"], "extensions.alpha_tools.backend.migrations")
                self.assertEqual(manifest["compatibility"]["bias_version"], "^1.0.0")
                self.assertEqual(manifest["compatibility"]["api_stability"], "experimental")
                self.assertEqual(manifest["distribution"]["channel"], "private")
                self.assertEqual(manifest["security"]["support_email"], "security@example.com")
                self.assertTrue((extension_dir / "frontend" / "admin" / "DetailPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "index.js").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "SettingsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "OperationsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "forum" / "index.js").exists())
                self.assertTrue((extension_dir / "backend" / "ext.py").exists())
                self.assertTrue((extension_dir / "backend" / "migrations" / "__init__.py").exists())
                self.assertTrue((extension_dir / "backend" / "migrations" / "0001_initial.py").exists())
                self.assertTrue((extension_dir / "docs" / "README.md").exists())
                self.assertTrue((extension_dir / "locale" / "zh-CN.json").exists())
                backend_source = (extension_dir / "backend" / "ext.py").read_text(encoding="utf-8")
                self.assertIn("def run_install(context):", backend_source)
                self.assertIn("def run_migrations(context):", backend_source)
                self.assertIn("def run_uninstall(context):", backend_source)
                migration_source = (extension_dir / "backend" / "migrations" / "0001_initial.py").read_text(encoding="utf-8")
                self.assertIn("def apply():", migration_source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_admin_entry_exports_detail_page(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")

                entry_source = (Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export function resolveDetailPage()", entry_source)
                self.assertIn("import DetailPage from './DetailPage.vue'", entry_source)
                forum_entry_source = (Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("registerForumNavItem", forum_entry_source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_rejects_existing_directory_without_force(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extension_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            extension_dir.mkdir(parents=True, exist_ok=False)
            with override_settings(BASE_DIR=Path(temp_dir)):
                with self.assertRaisesMessage(CommandError, f"扩展目录已存在: {extension_dir}。如需覆盖，请传 --force"):
                    call_command("create_extension", "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_manifest_errors(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["missing-one"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 2 个错误"):
                call_command("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_can_pass_in_strict_mode(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_missing_frontend_admin_exports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveSettingsPage() { return null }\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_allows_generated_permissions_and_operations_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "permissions_pages": ["/admin/extensions/alpha-tools/permissions"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/alpha-tools",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            call_command("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_missing_frontend_admin_entry_declaration(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_strict_reports_missing_backend_hook(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "migration_namespace": "extensions.alpha_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 2 个错误"):
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ExtensionRegistryTests(TestCase):
    def test_registry_exposes_builtin_modules_as_extensions(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extensions = registry.get_extensions()

        extension_ids = {item.id for item in extensions}
        self.assertIn("core", extension_ids)
        self.assertIn("posts", extension_ids)
        self.assertIn("sample-hello", extension_ids)
        self.assertTrue(any(item.source == "builtin-module" for item in extensions))
        self.assertTrue(any(item.source == "filesystem" for item in extensions))

        core_extension = next(item for item in extensions if item.id == "core")
        self.assertEqual(core_extension.manifest.category, "core")
        self.assertEqual(core_extension.manifest.frontend_admin_entry, "builtin:core")
        self.assertEqual(core_extension.manifest.settings_pages, ("/admin/extensions/core/settings",))
        self.assertEqual(core_extension.manifest.operations_pages, ("/admin/extensions/core/operations",))
        self.assertIn("/admin", core_extension.admin_pages)
        self.assertIn("basic", core_extension.settings_groups)
        self.assertEqual(core_extension.lifecycle.registration_mode, "static")

        sample_extension = next(item for item in extensions if item.id == "sample-hello")
        self.assertEqual(sample_extension.source, "filesystem")
        self.assertEqual(sample_extension.manifest.dependencies, ("core",))
        self.assertIn("/admin/extensions/sample-hello/settings", sample_extension.manifest.settings_pages)
        self.assertFalse(sample_extension.runtime.installed)
        self.assertFalse(sample_extension.runtime.enabled)
        self.assertEqual(sample_extension.runtime.status_key, "pending_install")
        self.assertTrue(any(item.key == "migrations" for item in sample_extension.runtime.delivery_checks))
        self.assertTrue(any("不会自动回滚数据库迁移" in item for item in sample_extension.runtime.uninstall_warnings))
        runtime_probe = inspect_extension_runtime(sample_extension)
        self.assertIn("0001_bootstrap.py", runtime_probe["migration_plan"]["pending_files"])

    def test_builtin_adapter_preserves_module_metadata(self):
        module = get_forum_registry().get_module("approval")
        extension = adapt_builtin_module_to_extension(module)

        self.assertEqual(extension.id, "approval")
        self.assertEqual(extension.name, module.name)
        self.assertEqual(extension.manifest.dependencies, module.dependencies)
        self.assertEqual(extension.runtime.enabled, module.enabled)
        self.assertEqual(extension.manifest.frontend_admin_entry, "builtin:approval")
        self.assertEqual(extension.manifest.permissions_pages, ("/admin/extensions/approval/permissions",))
        self.assertEqual(extension.manifest.operations_pages, ("/admin/extensions/approval/operations",))

    def test_builtin_adapter_can_map_tags_to_extension_settings_page(self):
        module = get_forum_registry().get_module("tags")
        extension = adapt_builtin_module_to_extension(module)

        self.assertEqual(extension.manifest.frontend_admin_entry, "builtin:tags")
        self.assertEqual(extension.manifest.settings_pages, ("/admin/extensions/tags/settings",))
        self.assertEqual(extension.manifest.operations_pages, ())

    def test_builtin_adapter_can_map_builtin_operations_pages_to_extension_host(self):
        users_module = get_forum_registry().get_module("users")
        users_extension = adapt_builtin_module_to_extension(users_module)
        self.assertEqual(users_extension.manifest.frontend_admin_entry, "builtin:users")
        self.assertEqual(users_extension.manifest.operations_pages, ("/admin/extensions/users/operations",))
        self.assertEqual(users_extension.manifest.permissions_pages, ("/admin/extensions/users/permissions",))

        flags_module = get_forum_registry().get_module("flags")
        flags_extension = adapt_builtin_module_to_extension(flags_module)
        self.assertEqual(flags_extension.manifest.frontend_admin_entry, "builtin:flags")
        self.assertEqual(flags_extension.manifest.operations_pages, ("/admin/extensions/flags/operations",))
        self.assertEqual(flags_extension.manifest.permissions_pages, ("/admin/extensions/flags/permissions",))

    def test_builtin_adapter_can_map_core_pages_to_extension_host(self):
        module = get_forum_registry().get_module("core")
        extension = adapt_builtin_module_to_extension(module)

        self.assertEqual(extension.manifest.frontend_admin_entry, "builtin:core")
        self.assertEqual(extension.manifest.settings_pages, ("/admin/extensions/core/settings",))
        self.assertEqual(extension.manifest.permissions_pages, ("/admin/extensions/core/permissions",))
        self.assertEqual(extension.manifest.operations_pages, ("/admin/extensions/core/operations",))

    def test_registry_applies_persisted_installation_state(self):
        ExtensionInstallation.objects.create(
            extension_id="sample-hello",
            version="0.1.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        self.assertFalse(extension.runtime.enabled)
        self.assertFalse(extension.runtime.booted)
        self.assertTrue(extension.runtime.installed)

    @patch("apps.core.extensions.runtime_probe.resolve_bias_version_compatibility")
    def test_registry_marks_extension_unhealthy_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("sample-hello")

        self.assertFalse(extension.runtime.healthy)
        self.assertIn("当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。", extension.runtime.runtime_issues)
        self.assertTrue(any(
            item.key == "bias-compatibility" and item.status == "attention"
            for item in extension.runtime.delivery_checks
        ))

    def test_registry_filters_module_capabilities_when_extension_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="approval",
            version="1.0.0",
            source="builtin-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        registry = get_forum_registry()
        approval_module = registry.get_module("approval")

        self.assertFalse(approval_module.enabled)
        self.assertFalse(any(item.module_id == "approval" for item in registry.get_admin_pages()))
        self.assertFalse(any(item.module_id == "approval" for item in registry.get_search_filters()))

    def test_registry_filters_resource_capabilities_when_extension_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="flags",
            version="1.0.0",
            source="builtin-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        resource_registry = get_resource_registry()

        self.assertFalse(any(item.module_id == "flags" for item in resource_registry.get_fields("post")))


class AdminExtensionsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-extensions",
            email="admin-extensions@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extensions_api_returns_builtin_extension_snapshot(self):
        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("extensions", payload)
        self.assertGreaterEqual(payload["summary"]["extension_count"], 1)
        self.assertGreaterEqual(payload["summary"]["builtin_count"], 1)
        self.assertGreaterEqual(payload["summary"]["filesystem_count"], 1)

        extension_ids = {item["id"] for item in payload["extensions"]}
        self.assertIn("core", extension_ids)
        self.assertIn("tags", extension_ids)
        self.assertIn("sample-hello", extension_ids)

        core_extension = next(item for item in payload["extensions"] if item["id"] == "core")
        self.assertEqual(core_extension["source"], "builtin-module")
        self.assertEqual(core_extension["category"], "core")
        self.assertEqual(core_extension["frontend_admin_entry"], "builtin:core")
        self.assertTrue(core_extension["installed"])
        self.assertTrue(core_extension["enabled"])
        self.assertIn("/admin", core_extension["admin_pages"])
        self.assertTrue(any(page["path"] == "/admin/basics" for page in core_extension["admin_page_details"]))
        self.assertTrue(any(page["path"] == "/admin/appearance" for page in core_extension["admin_page_details"]))
        self.assertTrue(any(page["path"] == "/admin/mail" for page in core_extension["admin_page_details"]))
        self.assertTrue(any(page["path"] == "/admin/advanced" for page in core_extension["admin_page_details"]))
        self.assertTrue(any(page["path"] == "/admin/audit-logs" for page in core_extension["admin_page_details"]))
        self.assertTrue(any(page["path"] == "/admin/docs" for page in core_extension["admin_page_details"]))
        self.assertIn("basic", core_extension["settings_groups"])
        self.assertIn("phases", core_extension["lifecycle"])
        self.assertTrue(any(phase["key"] == "register" for phase in core_extension["lifecycle"]["phases"]))
        self.assertEqual(core_extension["action_links"]["detail_page"], "/admin/extensions/core")
        self.assertEqual(core_extension["action_links"]["settings_page"], "/admin/extensions/core/settings")
        self.assertEqual(core_extension["action_links"]["permissions_page"], "/admin/extensions/core/permissions")
        self.assertEqual(core_extension["action_links"]["operations_page"], "/admin/extensions/core/operations")
        self.assertTrue(any(action["key"] == "details" for action in core_extension["admin_actions"]))

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "sample-hello")
        self.assertEqual(sample_extension["source"], "filesystem")
        self.assertEqual(sample_extension["frontend_admin_entry"], "extensions/sample-hello/frontend/admin/index.js")
        self.assertIn("/admin/extensions/sample-hello/settings", sample_extension["settings_pages"])
        self.assertIn("/admin/extensions/sample-hello/permissions", sample_extension["permissions_pages"])
        self.assertEqual(sample_extension["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(sample_extension["compatibility"]["api_stability"], "experimental")
        self.assertEqual(sample_extension["distribution"]["channel"], "private")
        self.assertEqual(sample_extension["action_links"]["settings_page"], "/admin/extensions/sample-hello/settings")
        self.assertEqual(sample_extension["action_links"]["permissions_page"], "/admin/extensions/sample-hello/permissions")
        self.assertTrue(any(item["key"] == "welcome_message" for item in sample_extension["settings_schema"]))
        self.assertEqual(sample_extension["admin_actions"][0]["key"], "details")
        self.assertTrue(any(action["key"] == "documentation" for action in sample_extension["admin_actions"]))
        self.assertFalse(any(action["action"] == "hook:run_rebuild_cache" for action in sample_extension["runtime_actions"]))

        tags_extension = next(item for item in payload["extensions"] if item["id"] == "tags")
        self.assertEqual(tags_extension["source"], "builtin-module")
        self.assertEqual(tags_extension["frontend_admin_entry"], "builtin:tags")
        self.assertEqual(tags_extension["action_links"]["settings_page"], "/admin/extensions/tags/settings")

        approval_extension = next(item for item in payload["extensions"] if item["id"] == "approval")
        self.assertEqual(approval_extension["frontend_admin_entry"], "builtin:approval")
        self.assertEqual(approval_extension["action_links"]["permissions_page"], "/admin/extensions/approval/permissions")
        self.assertEqual(approval_extension["action_links"]["operations_page"], "/admin/extensions/approval/operations")

        users_extension = next(item for item in payload["extensions"] if item["id"] == "users")
        self.assertEqual(users_extension["frontend_admin_entry"], "builtin:users")
        self.assertEqual(users_extension["action_links"]["permissions_page"], "/admin/extensions/users/permissions")
        self.assertEqual(users_extension["action_links"]["operations_page"], "/admin/extensions/users/operations")

        flags_extension = next(item for item in payload["extensions"] if item["id"] == "flags")
        self.assertEqual(flags_extension["frontend_admin_entry"], "builtin:flags")
        self.assertEqual(flags_extension["action_links"]["permissions_page"], "/admin/extensions/flags/permissions")
        self.assertEqual(flags_extension["action_links"]["operations_page"], "/admin/extensions/flags/operations")

    def test_extension_detail_api_returns_extension_actions(self):
        response = self.client.get(
            "/api/admin/extensions/sample-hello",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["id"], "sample-hello")
        self.assertEqual(payload["action_links"]["detail_page"], "/admin/extensions/sample-hello")
        self.assertEqual(payload["action_links"]["settings_page"], "/admin/extensions/sample-hello/settings")
        self.assertEqual(payload["action_links"]["permissions_page"], "/admin/extensions/sample-hello/permissions")
        self.assertEqual(payload["action_links"]["operations_page"], "/admin/extensions/sample-hello/operations")
        self.assertEqual(payload["frontend_admin_entry"], "extensions/sample-hello/frontend/admin/index.js")
        self.assertEqual(payload["admin_actions"][0]["key"], "details")
        self.assertEqual(payload["runtime_status"]["key"], "pending_install")
        self.assertEqual(payload["runtime_actions"][0]["action"], "install")
        self.assertEqual(payload["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(payload["compatibility"]["api_stability_label"], "实验性")
        self.assertEqual(payload["distribution"]["channel_label"], "私有分发")
        self.assertEqual(payload["security"]["support_email"], "security@bias.local")
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["settings_schema"]))
        self.assertEqual(payload["settings_values"]["welcome_message"], "欢迎使用 Sample Hello")
        self.assertTrue(any(item["key"] == "migrations" for item in payload["delivery_checks"]))
        self.assertTrue(any("不会自动回滚数据库迁移" in item for item in payload["uninstall_warnings"]))
        self.assertIsNone(payload["migration_execution"])
        self.assertEqual(payload["debug_info"]["manifest_path"], str(Path.cwd() / "extensions" / "sample-hello"))
        self.assertEqual(payload["debug_info"]["frontend_admin_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_admin_entry"]["exists"])
        self.assertIn("resolveDetailPage", payload["debug_info"]["frontend_admin_entry"]["available_exports"])
        self.assertEqual(payload["debug_info"]["frontend_forum_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_forum_entry"]["exists"])
        self.assertIn("0001_bootstrap.py", payload["migration_plan"]["pending_files"])
        self.assertTrue(any(
            item["key"] == "settings"
            and item["matches_expected"]
            and item["declared"] == "/admin/extensions/sample-hello/settings"
            for item in payload["debug_info"]["route_bindings"]
        ))
        self.assertTrue(any(
            item["key"] == "frontend_forum_entry"
            and item["matches_expected"]
            and item["declared"] == "extensions/sample-hello/frontend/forum/index.js"
            for item in payload["debug_info"]["route_bindings"]
        ))
        self.assertTrue(any(
            item["key"] == "settings"
            and item["mode"] == "custom"
            and item["mode_label"] == "自定义组件"
            for item in payload["debug_info"]["admin_surface_statuses"]
        ))
        self.assertEqual(payload["debug_info"]["validation_issues"], [])
        self.assertEqual(payload["backend_hooks"], [])
        self.assertEqual(payload["permission_summary"]["permission_count"], 0)
        self.assertEqual(payload["permission_summary"]["section_count"], 0)
        self.assertEqual(payload["permission_modules"], [])
        self.assertEqual(payload["permission_sections"], [])
        self.assertEqual(payload["admin_page_details"], [])

    def test_extension_detail_api_aggregates_builtin_extension_permissions(self):
        response = self.client.get(
            "/api/admin/extensions/approval",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertGreater(payload["permission_summary"]["permission_count"], 0)
        self.assertGreater(payload["permission_summary"]["section_count"], 0)
        self.assertTrue(any(item["module_id"] == "approval" for item in payload["permission_modules"]))
        self.assertTrue(any(
            permission["module_id"] == "approval"
            for section in payload["permission_sections"]
            for permission in section["permissions"]
        ))
        self.assertFalse(any(
            permission["module_id"] != "approval"
            for section in payload["permission_sections"]
            for permission in section["permissions"]
        ))

    def test_extension_settings_api_can_read_and_save_declared_schema(self):
        response = self.client.get(
            "/api/admin/extensions/sample-hello/settings",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["extension_id"], "sample-hello")
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["schema"]))
        self.assertEqual(payload["settings"]["card_tone"], "primary")

        save_response = self.client.post(
            "/api/admin/extensions/sample-hello/settings",
            data=json.dumps({
                "welcome_message": "新的欢迎语",
                "card_tone": "warm",
                "show_runtime_tips": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )
        self.assertEqual(save_response.status_code, 200, save_response.content)
        saved_payload = save_response.json()
        self.assertEqual(saved_payload["settings"]["welcome_message"], "新的欢迎语")
        self.assertEqual(saved_payload["settings"]["card_tone"], "warm")
        self.assertFalse(saved_payload["settings"]["show_runtime_tips"])
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.sample-hello.welcome_message").value),
            "新的欢迎语",
        )

    def test_extension_settings_api_rejects_unknown_key(self):
        response = self.client.post(
            "/api/admin/extensions/sample-hello/settings",
            data=json.dumps({"unknown_key": "x"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_settings_unknown_key")

    def test_extensions_api_can_install_disable_enable_and_uninstall_extension(self):
        install_response = self.client.post(
            "/api/admin/extensions/sample-hello/install",
            **self.auth_header(),
        )

        self.assertEqual(install_response.status_code, 200, install_response.content)
        installed_payload = install_response.json()
        installed_extension = next(item for item in installed_payload["extensions"] if item["id"] == "sample-hello")
        self.assertTrue(installed_extension["installed"])
        self.assertTrue(installed_extension["enabled"])
        self.assertEqual(installed_extension["runtime_status"]["key"], "active")
        self.assertEqual(installed_extension["migration_state"], "applied")
        self.assertEqual(installed_extension["migration_label"], "最近已执行")
        self.assertEqual(installed_extension["migration_execution"]["state"], "applied")
        self.assertEqual(installed_extension["migration_execution"]["status"], "ok")
        self.assertEqual(installed_extension["migration_plan"]["pending_files"], [])
        self.assertIn("0001_bootstrap.py", installed_extension["migration_plan"]["applied_files"])
        self.assertTrue(any(item["hook"] == "run_install" for item in installed_extension["backend_hooks"]))
        self.assertTrue(any(item["hook"] == "run_migrations" for item in installed_extension["backend_hooks"]))
        self.assertTrue(any(item["action"] == "migrations" for item in installed_extension["runtime_actions"]))
        self.assertTrue(any(item["action"] == "hook:run_rebuild_cache" for item in installed_extension["runtime_actions"]))

        disable_response = self.client.post(
            "/api/admin/extensions/sample-hello/disable",
            **self.auth_header(),
        )

        self.assertEqual(disable_response.status_code, 200, disable_response.content)
        disabled_payload = disable_response.json()
        disabled_extension = next(item for item in disabled_payload["extensions"] if item["id"] == "sample-hello")
        self.assertFalse(disabled_extension["enabled"])
        self.assertEqual(disabled_extension["runtime_status"]["key"], "disabled")
        self.assertTrue(any(item["action"] == "uninstall" for item in disabled_extension["runtime_actions"]))
        self.assertTrue(any(item["hook"] == "run_disable" for item in disabled_extension["backend_hooks"]))

        installation = ExtensionInstallation.objects.get(extension_id="sample-hello")
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)
        self.assertIn("run_install", installation.meta["backend_hooks"])
        self.assertIn("run_disable", installation.meta["backend_hooks"])

        enable_response = self.client.post(
            "/api/admin/extensions/sample-hello/enable",
            **self.auth_header(),
        )

        self.assertEqual(enable_response.status_code, 200, enable_response.content)
        enabled_payload = enable_response.json()
        enabled_extension = next(item for item in enabled_payload["extensions"] if item["id"] == "sample-hello")
        self.assertTrue(enabled_extension["enabled"])
        self.assertTrue(any(item["hook"] == "run_enable" for item in enabled_extension["backend_hooks"]))

        runtime_hook_response = self.client.post(
            "/api/admin/extensions/sample-hello/runtime-hooks/run_rebuild_cache",
            **self.auth_header(),
        )
        self.assertEqual(runtime_hook_response.status_code, 200, runtime_hook_response.content)
        runtime_hook_payload = runtime_hook_response.json()
        runtime_hook_extension = next(item for item in runtime_hook_payload["extensions"] if item["id"] == "sample-hello")
        self.assertTrue(any(item["hook"] == "run_rebuild_cache" for item in runtime_hook_extension["backend_hooks"]))

        migrations_response = self.client.post(
            "/api/admin/extensions/sample-hello/migrations",
            **self.auth_header(),
        )
        self.assertEqual(migrations_response.status_code, 200, migrations_response.content)
        migrations_payload = migrations_response.json()
        migrations_extension = next(item for item in migrations_payload["extensions"] if item["id"] == "sample-hello")
        self.assertTrue(any(item["hook"] == "run_migrations" for item in migrations_extension["backend_hooks"]))
        self.assertEqual(migrations_extension["migration_label"], "最近已执行")
        self.assertEqual(migrations_extension["migration_execution"]["state"], "applied")

        installation.refresh_from_db()
        self.assertTrue(installation.enabled)
        self.assertTrue(installation.booted)
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disable_response = self.client.post(
            "/api/admin/extensions/sample-hello/disable",
            **self.auth_header(),
        )
        self.assertEqual(disable_response.status_code, 200, disable_response.content)

        uninstall_response = self.client.post(
            "/api/admin/extensions/sample-hello/uninstall",
            **self.auth_header(),
        )
        self.assertEqual(uninstall_response.status_code, 200, uninstall_response.content)
        uninstalled_payload = uninstall_response.json()
        uninstalled_extension = next(item for item in uninstalled_payload["extensions"] if item["id"] == "sample-hello")
        self.assertFalse(uninstalled_extension["installed"])
        self.assertFalse(uninstalled_extension["enabled"])
        self.assertEqual(uninstalled_extension["runtime_status"]["key"], "pending_install")
        self.assertTrue(any(item["hook"] == "run_uninstall" for item in uninstalled_extension["backend_hooks"]))

        installation.refresh_from_db()
        self.assertFalse(installation.installed)
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)

    def test_extensions_api_blocks_enable_when_dependency_disabled(self):
        self.client.post(
            "/api/admin/extensions/sample-hello/install",
            **self.auth_header(),
        )
        self.client.post(
            "/api/admin/extensions/sample-hello/disable",
            **self.auth_header(),
        )

        ExtensionInstallation.objects.create(
            extension_id="core",
            version="1.0.0",
            source="builtin-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        response = self.client.post(
            "/api/admin/extensions/sample-hello/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_enable_blocked")
        self.assertIn("disabled_dependencies", payload["field_errors"])
        self.assertIn("core", payload["field_errors"]["disabled_dependencies"])

    def test_extensions_api_blocks_enable_when_extension_not_installed(self):
        response = self.client.post(
            "/api/admin/extensions/sample-hello/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_enable_not_installed")

    @patch("apps.core.extension_service.resolve_bias_version_compatibility")
    def test_extensions_api_blocks_install_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        response = self.client.post(
            "/api/admin/extensions/sample-hello/install",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_install_incompatible_bias_version")
        self.assertEqual(payload["field_errors"]["required_bias_version"], "^2.0.0")

    def test_extensions_api_blocks_disable_when_other_extensions_depend_on_it(self):
        response = self.client.post(
            "/api/admin/extensions/notifications/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_blocked")
        self.assertIn("blocking_dependents", payload["field_errors"])
        self.assertIn("approval", payload["field_errors"]["blocking_dependents"])

    def test_extensions_api_blocks_disable_for_core_extension(self):
        response = self.client.post(
            "/api/admin/extensions/core/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_core_blocked")

    def test_extensions_api_blocks_uninstall_when_extension_is_enabled(self):
        self.client.post(
            "/api/admin/extensions/sample-hello/install",
            **self.auth_header(),
        )

        response = self.client.post(
            "/api/admin/extensions/sample-hello/uninstall",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_uninstall_enabled_blocked")


class ExtensionServiceTests(TestCase):
    def test_install_and_uninstall_transition_filesystem_extension(self):
        installed = ExtensionService.install_extension("sample-hello")
        self.assertTrue(installed.runtime.installed)
        self.assertTrue(installed.runtime.enabled)
        self.assertEqual(installed.runtime.backend_hooks["run_install"]["status"], "ok")
        self.assertEqual(installed.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(installed.runtime.migration_state, "applied")
        self.assertEqual(installed.runtime.migration_label, "最近已执行")
        self.assertEqual(installed.runtime.migration_execution["state"], "applied")
        self.assertIn("0001_bootstrap.py", installed.runtime.migration_execution["details"]["migration_files"])
        self.assertIn("bootstrap", installed.runtime.migration_execution["details"]["applied_steps"])
        installation = ExtensionInstallation.objects.get(extension_id="sample-hello")
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disabled = ExtensionService.set_extension_enabled("sample-hello", False)
        self.assertFalse(disabled.runtime.enabled)
        self.assertEqual(disabled.runtime.backend_hooks["run_disable"]["status"], "ok")

        enabled = ExtensionService.set_extension_enabled("sample-hello", True)
        self.assertTrue(enabled.runtime.enabled)
        self.assertEqual(enabled.runtime.backend_hooks["run_enable"]["status"], "ok")

        disabled_again = ExtensionService.set_extension_enabled("sample-hello", False)
        self.assertFalse(disabled_again.runtime.enabled)

        uninstalled = ExtensionService.uninstall_extension("sample-hello")
        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")

    def test_run_extension_backend_hook_skips_builtin_extension(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        definition = registry.get_extension("core")

        result = run_extension_backend_hook(definition, "run_install")

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["hook"], "run_install")

    def test_run_extension_backend_hook_skips_when_hook_missing(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        definition = registry.get_extension("sample-hello")

        result = run_extension_backend_hook(definition, "run_reconcile")

        self.assertEqual(result["status"], "skipped")
        self.assertIn("run_reconcile", result["message"])

    def test_runtime_hook_executes_declared_extension_operation(self):
        installed = ExtensionService.install_extension("sample-hello")
        self.assertTrue(installed.runtime.enabled)

        updated = ExtensionService.run_extension_runtime_hook("sample-hello", "run_rebuild_cache")

        self.assertEqual(updated.runtime.backend_hooks["run_rebuild_cache"]["status"], "ok")

    def test_run_extension_migrations_executes_declared_migration_hook(self):
        installed = ExtensionService.install_extension("sample-hello")
        self.assertTrue(installed.runtime.installed)

        updated = ExtensionService.run_extension_migrations("sample-hello")

        self.assertEqual(updated.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(updated.runtime.migration_state, "applied")
        self.assertEqual(updated.runtime.migration_label, "最近已执行")
        self.assertEqual(updated.runtime.migration_execution["status"], "ok")
        self.assertEqual(updated.runtime.migration_execution["details"]["migration_files"], [])
        self.assertIn("0001_bootstrap.py", updated.runtime.migration_execution["details"]["skipped_migration_files"])

    def test_run_extension_migrations_requires_installation(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_migrations("sample-hello")

        self.assertEqual(context.exception.code, "extension_migrations_not_installed")

    def test_runtime_hook_requires_manifest_declaration(self):
        ExtensionService.install_extension("sample-hello")

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_runtime_hook("sample-hello", "run_unknown")

        self.assertEqual(context.exception.code, "extension_runtime_hook_not_declared")

    def test_enable_raises_when_required_dependency_missing_or_disabled(self):
        ExtensionService.install_extension("sample-hello")
        ExtensionInstallation.objects.update_or_create(
            extension_id="core",
            defaults={
                "version": "1.0.0",
                "source": "builtin-module",
                "enabled": False,
                "installed": True,
                "booted": False,
            },
        )

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("sample-hello", True)

        self.assertEqual(context.exception.code, "extension_enable_blocked")
        self.assertIn("core", context.exception.details["disabled_dependencies"])

    def test_disable_raises_when_enabled_dependents_exist(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("notifications", False)

        self.assertEqual(context.exception.code, "extension_disable_blocked")
        self.assertIn("approval", context.exception.details["blocking_dependents"])

    def test_uninstall_raises_when_extension_is_enabled(self):
        installed = ExtensionService.install_extension("sample-hello")
        self.assertTrue(installed.runtime.enabled)

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.uninstall_extension("sample-hello")

        self.assertEqual(context.exception.code, "extension_uninstall_enabled_blocked")

    @patch("apps.core.extension_service.resolve_bias_version_compatibility")
    def test_install_raises_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.install_extension("sample-hello")

        self.assertEqual(context.exception.code, "extension_install_incompatible_bias_version")
        self.assertEqual(context.exception.details["required_bias_version"], "^2.0.0")


class DomainEventRegistryTests(TestCase):
    def test_dispatches_handlers_for_tag_stats_events(self):
        bus = DomainEventBus()
        received = []

        def handle_discussion_refresh(event):
            received.append(("discussion", event.discussion_id))

        def handle_tag_refresh(event):
            received.append(("tags", event.tag_ids))

        bus.register(DiscussionTagStatsRefreshEvent, handle_discussion_refresh)
        bus.register(TagStatsRefreshRequestedEvent, handle_tag_refresh)
        bus.dispatch(DiscussionTagStatsRefreshEvent(discussion_id=12))
        bus.dispatch(TagStatsRefreshRequestedEvent(tag_ids=(3, 7)))

        self.assertEqual(received, [("discussion", 12), ("tags", (3, 7))])


class ResourceRegistryTests(TestCase):
    def test_serializes_registered_resource_fields(self):
        registry = ResourceRegistry()

        class Target:
            id = 3
            title = "hello"

        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="summary",
                module_id="test",
                resolver=lambda instance, context: f"{instance.id}:{context['suffix']}",
            )
        )

        payload = registry.serialize("discussion", Target(), {"suffix": "ok"})
        self.assertEqual(payload, {"summary": "3:ok"})

    def test_registers_forum_flag_resource_fields(self):
        register_forum_flag_resource_fields()
        field_names = [field.field for field in get_resource_registry().get_fields("post")]

        self.assertIn("viewer_has_open_flag", field_names)
        self.assertIn("open_flag_count", field_names)
        self.assertIn("open_flags", field_names)
        self.assertIn("can_moderate_flags", field_names)

    def test_serialize_user_payload_keeps_registered_primary_group_field(self):
        user = User.objects.create_user(
            username="resource-user",
            email="resource-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="ResourceGroup", color="#16a085", icon="fas fa-user")
        user.user_groups.add(group)

        summary_payload = serialize_user_summary(user)
        discussion_payload = serialize_user_payload(user, resource="discussion_user")

        self.assertEqual(summary_payload["username"], user.username)
        self.assertEqual(summary_payload["primary_group"]["name"], group.name)
        self.assertEqual(discussion_payload["primary_group"]["name"], group.name)

    def test_resolve_post_event_data_parses_post_hidden_payload(self):
        payload = resolve_post_event_data(
            SimpleNamespace(
                type="postHidden",
                content="state:hidden\ntarget_post_id:12\ntarget_post_number:5",
            ),
            {},
        )

        self.assertEqual(
            payload,
            {
                "kind": "postHidden",
                "is_hidden": True,
                "target_post_id": 12,
                "target_post_number": 5,
            },
        )

    def test_resolve_post_event_data_parses_approval_payload(self):
        payload = resolve_post_event_data(
            SimpleNamespace(
                type="postApproved",
                content="note:已通过\nprevious_status:pending\ntarget_post_id:9\ntarget_post_number:3",
            ),
            {},
        )

        self.assertEqual(
            payload,
            {
                "kind": "postApproved",
                "note": "已通过",
                "previous_status": "pending",
                "target_post_id": 9,
                "target_post_number": 3,
            },
        )

    def test_serializes_base_resource_and_relationship_includes(self):
        registry = ResourceRegistry()

        class Target:
            id = 8
            title = "hello"
            owner = type("Owner", (), {"username": "neo"})()

        registry.register_resource(
            ResourceDefinition(
                resource="discussion",
                module_id="test",
                resolver=lambda instance, context: {"id": instance.id, "title": instance.title},
            )
        )
        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="summary",
                module_id="test",
                resolver=lambda instance, context: f"{instance.id}:{context['suffix']}",
            )
        )
        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="discussion",
                relationship="owner",
                module_id="test",
                resolver=lambda instance, context: {"username": instance.owner.username},
            )
        )

        payload = registry.serialize(
            "discussion",
            Target(),
            {"suffix": "ok"},
            include=("owner",),
        )
        self.assertEqual(
            payload,
            {
                "id": 8,
                "title": "hello",
                "summary": "8:ok",
                "owner": {"username": "neo"},
            },
        )

    def test_can_select_only_specific_resource_fields(self):
        registry = ResourceRegistry()

        class Target:
            id = 2

        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="first",
                module_id="test",
                resolver=lambda instance, context: "a",
            )
        )
        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="second",
                module_id="test",
                resolver=lambda instance, context: "b",
            )
        )

        payload = registry.serialize("discussion", Target(), only=("second",))
        self.assertEqual(payload, {"second": "b"})


class ForumRegistryTests(TestCase):
    def test_builtin_registry_exposes_default_comment_post_type(self):
        registry = get_forum_registry()

        self.assertEqual(registry.get_default_post_type_code(), "comment")
        self.assertIn("comment", registry.get_stream_post_type_codes())
        self.assertIn("comment", registry.get_searchable_post_type_codes())
        self.assertIn("comment", registry.get_discussion_counted_post_type_codes())
        self.assertIn("comment", registry.get_user_counted_post_type_codes())

    def test_builtin_registry_exposes_discussion_sort_catalog(self):
        registry = get_forum_registry()

        sorts = registry.get_discussion_sorts()
        sort_codes = [item.code for item in sorts]
        self.assertIn("latest", sort_codes)
        self.assertIn("top", sort_codes)
        self.assertIn("unanswered", sort_codes)
        self.assertEqual(registry.get_default_discussion_sort_code(), "latest")
        newest_sort = next(item for item in sorts if item.code == "newest")
        unanswered_sort = next(item for item in sorts if item.code == "unanswered")
        oldest_sort = next(item for item in sorts if item.code == "oldest")
        self.assertEqual(newest_sort.icon, "fas fa-file-alt")
        self.assertTrue(newest_sort.toolbar_visible)
        self.assertFalse(unanswered_sort.toolbar_visible)
        self.assertFalse(oldest_sort.toolbar_visible)

    def test_builtin_registry_exposes_discussion_list_filter_catalog(self):
        registry = get_forum_registry()

        filters = registry.get_discussion_list_filters()
        filter_codes = [item.code for item in filters]
        self.assertIn("all", filter_codes)
        self.assertIn("following", filter_codes)
        self.assertIn("my", filter_codes)
        self.assertIn("unread", filter_codes)
        self.assertEqual(registry.get_default_discussion_list_filter_code(), "all")
        all_filter = next(item for item in filters if item.code == "all")
        following_filter = next(item for item in filters if item.code == "following")
        my_filter = next(item for item in filters if item.code == "my")
        unread_filter = next(item for item in filters if item.code == "unread")
        self.assertTrue(all_filter.sidebar_visible)
        self.assertEqual(all_filter.route_path, "/")
        self.assertEqual(following_filter.module_id, "subscriptions")
        self.assertTrue(following_filter.sidebar_visible)
        self.assertEqual(following_filter.route_path, "/following")
        self.assertFalse(my_filter.sidebar_visible)
        self.assertFalse(unread_filter.sidebar_visible)


class ChineseSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="searcher",
            email="searcher@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_chinese_query_matches_discussion_content(self):
        discussion = DiscussionService.create_discussion(
            title="无关标题",
            content="这里讨论中文分词搜索和数据库检索体验。",
            user=self.user,
        )

        discussions, total = SearchService.search_discussions("中文搜索")

        self.assertEqual(total, 1)
        self.assertEqual(discussions[0].id, discussion.id)

    def test_discussion_list_query_uses_chinese_content_search(self):
        discussion = DiscussionService.create_discussion(
            title="产品反馈",
            content="希望论坛原生支持中文搜索。",
            user=self.user,
        )

        discussions, total = DiscussionService.get_discussion_list(q="中文搜索")

        self.assertEqual(total, 1)
        self.assertEqual(discussions[0].id, discussion.id)

    def test_discussion_list_supports_registered_unanswered_sort(self):
        first_discussion = DiscussionService.create_discussion(
            title="零回复讨论",
            content="等待回复",
            user=self.user,
        )
        answered_discussion = DiscussionService.create_discussion(
            title="已有回复讨论",
            content="已经有回复",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=answered_discussion.id,
            content="我来回复一下",
            user=self.user,
        )

        discussions, total = DiscussionService.get_discussion_list(sort="unanswered", user=self.user)

        self.assertEqual(total, 2)
        self.assertEqual(discussions[0].id, first_discussion.id)
        self.assertEqual(discussions[1].id, answered_discussion.id)

    def test_discussions_api_returns_registered_sort_catalog(self):
        DiscussionService.create_discussion(
            title="排序目录讨论",
            content="用于测试排序元数据",
            user=self.user,
        )

        response = self.client.get("/api/discussions/", {"sort": "unanswered"})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["sort"], "unanswered")
        self.assertTrue(any(item["code"] == "latest" and item["is_default"] for item in payload["available_sorts"]))
        self.assertTrue(any(item["code"] == "unanswered" and item["toolbar_visible"] is False for item in payload["available_sorts"]))
        self.assertTrue(any(item["code"] == "newest" and item["icon"] == "fas fa-file-alt" for item in payload["available_sorts"]))

    def test_discussions_api_returns_registered_filter_catalog(self):
        DiscussionService.create_discussion(
            title="过滤目录讨论",
            content="用于测试过滤元数据",
            user=self.user,
        )

        response = self.client.get("/api/discussions/", {"filter": "my"}, **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["filter"], "my")
        self.assertTrue(any(item["code"] == "all" and item["is_default"] for item in payload["available_filters"]))
        self.assertTrue(any(item["code"] == "following" and item["requires_authenticated_user"] for item in payload["available_filters"]))
        self.assertTrue(any(item["code"] == "following" and item["route_path"] == "/following" for item in payload["available_filters"]))
        self.assertTrue(any(item["code"] == "my" and item["sidebar_visible"] is False for item in payload["available_filters"]))
        self.assertTrue(any(item["code"] == "unread" and item["sidebar_visible"] is False for item in payload["available_filters"]))

    def test_discussion_list_supports_registered_my_and_unread_filters(self):
        other_user = User.objects.create_user(
            username="other-filter-user",
            email="other-filter-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        my_discussion = DiscussionService.create_discussion(
            title="我的讨论",
            content="我发起的主题",
            user=self.user,
        )
        unread_discussion = DiscussionService.create_discussion(
            title="未读讨论",
            content="稍后会产生未读回复",
            user=other_user,
        )
        read_discussion = DiscussionService.create_discussion(
            title="已读讨论",
            content="稍后会被标记已读",
            user=other_user,
        )

        from apps.discussions.models import DiscussionUser
        DiscussionUser.objects.update_or_create(
            discussion=unread_discussion,
            user=self.user,
            defaults={"last_read_post_number": 1, "is_subscribed": False},
        )
        DiscussionUser.objects.update_or_create(
            discussion=read_discussion,
            user=self.user,
            defaults={"last_read_post_number": 1, "is_subscribed": False},
        )

        PostService.create_post(
            discussion_id=unread_discussion.id,
            content="生成未读回复",
            user=other_user,
        )

        my_discussions, my_total = DiscussionService.get_discussion_list(list_filter="my", user=self.user)
        unread_discussions, unread_total = DiscussionService.get_discussion_list(list_filter="unread", user=self.user)

        self.assertEqual(my_total, 1)
        self.assertEqual([item.id for item in my_discussions], [my_discussion.id])
        self.assertEqual(unread_total, 1)
        self.assertEqual([item.id for item in unread_discussions], [unread_discussion.id])

    def test_chinese_tokenizer_keeps_phrase_and_segments(self):
        tokens = SearchService.tokenize_query("中文搜索")

        self.assertIn("中文搜索", tokens)
        self.assertTrue({"中文", "搜索"}.intersection(tokens))

    def test_postgres_full_text_is_only_used_for_latin_queries_on_postgres(self):
        self.assertTrue(SearchService.should_use_postgres_full_text("postgres search", vendor="postgresql"))
        self.assertFalse(SearchService.should_use_postgres_full_text("中文搜索", vendor="postgresql"))
        self.assertFalse(SearchService.should_use_postgres_full_text("postgres search", vendor="sqlite"))

    def test_discussion_list_search_respects_post_approval_visibility(self):
        discussion = DiscussionService.create_discussion(
            title="普通讨论标题",
            content="首帖不包含目标词",
            user=self.user,
        )
        pending_author = User.objects.create_user(
            username="list-search-pending",
            email="list-search-pending@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        trusted_group = Group.objects.create(name="ListSearchTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        PostService.create_post(
            discussion_id=discussion.id,
            content="pendingreplyvisibilitykeyword",
            user=pending_author,
        )

        guest_discussions, guest_total = DiscussionService.get_discussion_list(q="pendingreplyvisibilitykeyword")
        author_discussions, author_total = DiscussionService.get_discussion_list(
            q="pendingreplyvisibilitykeyword",
            user=pending_author,
        )

        self.assertEqual(guest_total, 0)
        self.assertEqual(guest_discussions, [])
        self.assertEqual(author_total, 1)
        self.assertEqual(author_discussions[0].id, discussion.id)

    def test_search_api_all_returns_section_totals(self):
        DiscussionService.create_discussion(
            title="搜索讨论标题",
            content="这里有搜索内容",
            user=self.user,
        )
        discussion = DiscussionService.create_discussion(
            title="另一个搜索讨论",
            content="讨论里包含搜索关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="这是一条搜索帖子内容",
            user=self.user,
        )
        User.objects.create_user(
            username="search-keyword",
            email="search-keyword@example.com",
            password="password123",
            bio="搜索用户简介",
            is_email_confirmed=True,
        )

        response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "all"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertGreaterEqual(payload["discussion_total"], 2)
        self.assertGreaterEqual(payload["post_total"], 1)
        self.assertGreaterEqual(payload["user_total"], 1)

    def test_search_api_preview_mode_returns_capped_section_results_without_full_totals(self):
        for index in range(7):
            DiscussionService.create_discussion(
                title=f"预览标题专用词 {index}",
                content="这是一段不会命中标题预览查询的正文",
                user=self.user,
            )

        response = self.client.get(
            "/api/search",
            {"q": "预览标题专用词", "type": "all", "limit": 20, "preview": True},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type"], "all")
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 5)
        self.assertTrue(payload["is_preview"])
        self.assertEqual(payload["discussion_total"], 5)
        self.assertEqual(len(payload["discussions"]), 5)
        self.assertEqual(payload["discussion_total"], len(payload["discussions"]))
        self.assertEqual(payload["post_total"], len(payload["posts"]))
        self.assertEqual(payload["user_total"], len(payload["users"]))
        self.assertEqual(
            payload["total"],
            payload["discussion_total"] + payload["post_total"] + payload["user_total"],
        )


class UserPreferencesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="prefs-user",
            email="prefs-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_preferences_api_returns_ui_values_defaults(self):
        response = self.client.get("/api/users/me/preferences", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["ui_values"], {})
        self.assertIn("values", payload)
        self.assertIn("definitions", payload)

    def test_preferences_api_updates_ui_values(self):
        response = self.client.patch(
            "/api/users/me/preferences",
            data=json.dumps({
                "values": {
                    "notify_user_mentioned": False,
                },
                "ui_values": {},
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferences_ui, {})
        self.assertFalse(self.user.preferences["notify_user_mentioned"])
        self.assertEqual(response.json()["ui_values"], {})


class SearchApiTests(ChineseSearchTests):
    def test_search_api_posts_type_returns_pagination_metadata(self):
        discussion = DiscussionService.create_discussion(
            title="分页搜索讨论",
            content="讨论首帖包含分页搜索关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="第一页搜索帖子内容",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="第二页搜索帖子内容",
            user=self.user,
        )

        response = self.client.get("/api/search", {"q": "搜索", "type": "posts", "page": 1, "limit": 1})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type"], "posts")
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 1)
        self.assertGreaterEqual(payload["total"], 2)
        self.assertGreaterEqual(payload["post_total"], 2)
        self.assertEqual(len(payload["posts"]), 1)

    def test_search_api_users_type_returns_user_totals(self):
        unique_keyword = "独有用户搜索键12345"
        matched_user = User.objects.create_user(
            username="isolated-user",
            email="search-user-only@example.com",
            password="password123",
            bio=f"这是一个{unique_keyword}",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="SearchUserGroup", color="#16a085", icon="fas fa-user-tag")
        matched_user.user_groups.add(group)

        response = self.client.get(
            "/api/search",
            {"q": unique_keyword, "type": "users"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type"], "users")
        self.assertEqual(payload["user_total"], 1)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["users"]), 1)
        self.assertEqual(payload["users"][0]["username"], "isolated-user")
        self.assertEqual(payload["users"][0]["primary_group"]["name"], group.name)

    def test_search_api_users_type_supports_resource_field_selection(self):
        unique_keyword = "用户字段裁剪搜索键67890"
        matched_user = User.objects.create_user(
            username="isolated-user-fields",
            email="search-user-fields@example.com",
            password="password123",
            bio=f"这是一个{unique_keyword}",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="SearchUserFieldsGroup", color="#16a085", icon="fas fa-user-tag")
        matched_user.user_groups.add(group)

        response = self.client.get(
            "/api/search",
            {"q": unique_keyword, "type": "users", "fields[search_user]": "primary_group"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["users"][0]["primary_group"]["name"], group.name)
        self.assertIn("bio", payload["users"][0])

    def test_search_api_discussions_support_resource_include_for_author(self):
        keyword = "搜索讨论 include 作者"
        discussion = DiscussionService.create_discussion(
            title=keyword,
            content="作者 include 讨论内容",
            user=self.user,
        )

        response = self.client.get(
            "/api/search",
            {"q": keyword, "type": "discussions", "fields[search_discussion]": "unknown_field", "include": "user"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["discussion_total"], 1)
        self.assertEqual(payload["discussions"][0]["id"], discussion.id)
        self.assertIn("user", payload["discussions"][0])
        self.assertEqual(payload["discussions"][0]["user"]["username"], self.user.username)

    def test_search_api_posts_support_resource_include_for_author(self):
        keyword = "搜索回复 include 作者"
        discussion = DiscussionService.create_discussion(
            title="搜索回复 include 讨论",
            content="首帖内容",
            user=self.user,
        )
        post = PostService.create_post(
            discussion_id=discussion.id,
            content=keyword,
            user=self.user,
        )

        response = self.client.get(
            "/api/search",
            {"q": keyword, "type": "posts", "fields[search_post]": "unknown_field", "include": "user"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual(payload["posts"][0]["id"], post.id)
        self.assertIn("user", payload["posts"][0])
        self.assertEqual(payload["posts"][0]["user"]["username"], self.user.username)

    def test_search_api_user_results_avoid_n_plus_one_for_primary_group(self):
        keyword = "搜索预加载用户"
        for index in range(3):
            candidate = User.objects.create_user(
                username=f"search-preload-user-{index}",
                email=f"search-preload-user-{index}@example.com",
                password="password123",
                bio=keyword,
                is_email_confirmed=True,
            )
            group = Group.objects.create(name=f"SearchPreloadGroup{index}", color="#16a085")
            candidate.user_groups.add(group)

        with CaptureQueriesContext(connection) as context:
            response = self.client.get(
                "/api/search",
                {"q": keyword, "type": "users"},
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        select_group_queries = [
            query["sql"]
            for query in context.captured_queries
            if "user_groups" in query["sql"].lower()
        ]
        self.assertLessEqual(len(select_group_queries), 2)

    def test_search_api_users_type_requires_search_permission(self):
        restricted_user = User.objects.create_user(
            username="search-no-user-permission",
            email="search-no-user-permission@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        restricted_group = Group.objects.create(name="NoUserSearch", color="#95a5a6")
        restricted_user.user_groups.add(restricted_group)

        response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "users"},
            **self.auth_header(restricted_user),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限搜索用户")

    def test_search_api_hides_discussions_in_staff_only_tags(self):
        admin = User.objects.create_superuser(
            username="search-admin",
            email="search-admin@example.com",
            password="password123",
        )
        hidden_tag = Tag.objects.create(
            name="管理搜索区",
            slug="search-staff",
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )
        DiscussionService.create_discussion(
            title="搜索内网讨论",
            content="这里有搜索关键字",
            user=admin,
            tag_ids=[hidden_tag.id],
        )

        guest_response = self.client.get("/api/search", {"q": "搜索", "type": "discussions"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual(guest_response.json()["discussion_total"], 0)
        self.assertEqual(guest_response.json()["discussions"], [])

        admin_response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "discussions"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertGreaterEqual(admin_response.json()["discussion_total"], 1)

    def test_search_api_supports_registered_tag_filter_syntax(self):
        target_tag = Tag.objects.create(name="扩展搜索标签", slug="extension-search-tag")
        other_tag = Tag.objects.create(name="其他标签", slug="other-search-tag")
        matched = DiscussionService.create_discussion(
            title="模块搜索过滤命中",
            content="使用注册式过滤器检索标签。",
            user=self.user,
            tag_ids=[target_tag.id],
        )
        DiscussionService.create_discussion(
            title="模块搜索过滤未命中",
            content="同样包含搜索关键字，但标签不同。",
            user=self.user,
            tag_ids=[other_tag.id],
        )

        response = self.client.get(
            "/api/search",
            {"q": "搜索 tag:extension-search-tag", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["discussion_total"], 1)
        self.assertEqual([item["id"] for item in payload["discussions"]], [matched.id])

    def test_search_api_supports_registered_author_filter_syntax(self):
        other_user = User.objects.create_user(
            username="other-search-author",
            email="other-search-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        matched = DiscussionService.create_discussion(
            title="作者过滤命中",
            content="作者过滤扩展关键字",
            user=self.user,
        )
        DiscussionService.create_discussion(
            title="作者过滤未命中",
            content="作者过滤扩展关键字",
            user=other_user,
        )

        response = self.client.get(
            "/api/search",
            {"q": f"关键字 author:{self.user.username}", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["discussion_total"], 1)
        self.assertEqual([item["id"] for item in payload["discussions"]], [matched.id])

    def test_search_api_supports_registered_state_filter_syntax(self):
        sticky = DiscussionService.create_discussion(
            title="置顶过滤讨论",
            content="置顶过滤关键字",
            user=self.user,
        )
        locked = DiscussionService.create_discussion(
            title="锁定过滤讨论",
            content="锁定过滤关键字",
            user=self.user,
        )
        DiscussionService.create_discussion(
            title="普通过滤讨论",
            content="过滤关键字",
            user=self.user,
        )

        sticky.is_sticky = True
        sticky.save(update_fields=["is_sticky"])
        locked.is_locked = True
        locked.save(update_fields=["is_locked"])

        sticky_response = self.client.get(
            "/api/search",
            {"q": "过滤关键字 is:sticky", "type": "discussions"},
            **self.auth_header(),
        )
        locked_response = self.client.get(
            "/api/search",
            {"q": "过滤关键字 is:locked", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(sticky_response.status_code, 200, sticky_response.content)
        self.assertEqual(locked_response.status_code, 200, locked_response.content)
        self.assertEqual([item["id"] for item in sticky_response.json()["discussions"]], [sticky.id])
        self.assertEqual([item["id"] for item in locked_response.json()["discussions"]], [locked.id])

    def test_search_api_posts_support_registered_author_filter_syntax(self):
        other_user = User.objects.create_user(
            username="other-post-search-author",
            email="other-post-search-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = DiscussionService.create_discussion(
            title="帖子作者过滤讨论",
            content="首帖内容",
            user=self.user,
        )
        matched_post = PostService.create_post(
            discussion_id=discussion.id,
            content="帖子作者过滤关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="帖子作者过滤关键字",
            user=other_user,
        )

        response = self.client.get(
            "/api/search",
            {"q": f"关键字 author:{self.user.username}", "type": "posts"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual([item["id"] for item in payload["posts"]], [matched_post.id])

    def test_search_api_supports_registered_following_and_unread_filters(self):
        followed = DiscussionService.create_discussion(
            title="关注过滤命中讨论",
            content="关注过滤关键字",
            user=self.user,
        )
        read_discussion = DiscussionService.create_discussion(
            title="已读过滤讨论",
            content="关注过滤关键字",
            user=self.user,
        )
        unread_discussion = DiscussionService.create_discussion(
            title="未读过滤讨论",
            content="关注过滤关键字",
            user=self.user,
        )

        from apps.discussions.models import DiscussionUser
        DiscussionUser.objects.update_or_create(
            discussion=followed,
            user=self.user,
            defaults={"is_subscribed": True, "last_read_post_number": 1},
        )
        DiscussionUser.objects.update_or_create(
            discussion=read_discussion,
            user=self.user,
            defaults={"is_subscribed": False, "last_read_post_number": read_discussion.last_post_number or 1},
        )
        DiscussionUser.objects.update_or_create(
            discussion=unread_discussion,
            user=self.user,
            defaults={"is_subscribed": False, "last_read_post_number": 0},
        )

        following_response = self.client.get(
            "/api/search",
            {"q": "关注过滤关键字 is:following", "type": "discussions"},
            **self.auth_header(),
        )
        unread_response = self.client.get(
            "/api/search",
            {"q": "关注过滤关键字 is:unread", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(following_response.status_code, 200, following_response.content)
        self.assertEqual(unread_response.status_code, 200, unread_response.content)
        self.assertEqual([item["id"] for item in following_response.json()["discussions"]], [followed.id])
        self.assertEqual([item["id"] for item in unread_response.json()["discussions"]], [unread_discussion.id])

    def test_search_api_supports_registered_created_month_filter_for_discussions(self):
        current_month = timezone.now().strftime("%Y-%m")
        previous_month = (timezone.now() - timedelta(days=40)).strftime("%Y-%m")

        matched = DiscussionService.create_discussion(
            title="创建月份过滤命中讨论",
            content="创建月份过滤关键字",
            user=self.user,
        )
        other = DiscussionService.create_discussion(
            title="创建月份过滤未命中讨论",
            content="创建月份过滤关键字",
            user=self.user,
        )
        Discussion.objects.filter(id=other.id).update(
            created_at=timezone.now() - timedelta(days=40),
            last_posted_at=timezone.now() - timedelta(days=40),
        )

        response = self.client.get(
            "/api/search",
            {"q": f"创建月份过滤关键字 created:{current_month}", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["discussion_total"], 1)
        self.assertEqual([item["id"] for item in payload["discussions"]], [matched.id])
        self.assertNotEqual(current_month, previous_month)

    def test_search_api_supports_registered_created_month_filter_for_posts(self):
        current_month = timezone.now().strftime("%Y-%m")
        discussion = DiscussionService.create_discussion(
            title="帖子创建月份过滤讨论",
            content="首帖内容",
            user=self.user,
        )
        matched_post = PostService.create_post(
            discussion_id=discussion.id,
            content="帖子创建月份过滤关键字",
            user=self.user,
        )
        other_post = PostService.create_post(
            discussion_id=discussion.id,
            content="帖子创建月份过滤关键字",
            user=self.user,
        )
        Post.objects.filter(id=other_post.id).update(
            created_at=timezone.now() - timedelta(days=40),
        )

        response = self.client.get(
            "/api/search",
            {"q": f"帖子创建月份过滤关键字 created:{current_month}", "type": "posts"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual([item["id"] for item in payload["posts"]], [matched_post.id])

    def test_search_api_supports_registered_mentioned_me_filter_syntax(self):
        mentioned_user = User.objects.create_user(
            username="mentioned-me-user",
            email="mentioned-me-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        other_user = User.objects.create_user(
            username="mentioned-other-user",
            email="mentioned-other-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = DiscussionService.create_discussion(
            title="提及过滤讨论",
            content="首帖内容",
            user=self.user,
        )
        matched_post = PostService.create_post(
            discussion_id=discussion.id,
            content=f"Hello @{mentioned_user.username} 提及过滤关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content=f"Hello @{other_user.username} 提及过滤关键字",
            user=self.user,
        )

        response = self.client.get(
            "/api/search",
            {"q": "提及过滤关键字 mentioned:me", "type": "posts"},
            **self.auth_header(mentioned_user),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual([item["id"] for item in payload["posts"]], [matched_post.id])

    def test_search_filters_api_returns_registered_filter_catalog(self):
        response = self.client.get("/api/search/filters")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["target"], "all")
        syntaxes = {item["syntax"] for item in payload["filters"]}
        self.assertIn("tag:<slug>", syntaxes)
        self.assertIn("author:<username>", syntaxes)
        self.assertIn("is:following", syntaxes)
        self.assertIn("is:unread", syntaxes)
        self.assertIn("created:YYYY-MM", syntaxes)
        self.assertIn("mentioned:me", syntaxes)

    def test_search_filters_api_supports_target_scoping(self):
        discussions_response = self.client.get("/api/search/filters", {"target": "discussions"})
        posts_response = self.client.get("/api/search/filters", {"target": "posts"})

        self.assertEqual(discussions_response.status_code, 200, discussions_response.content)
        self.assertEqual(posts_response.status_code, 200, posts_response.content)

        discussions_payload = discussions_response.json()
        posts_payload = posts_response.json()

        self.assertEqual(discussions_payload["target"], "discussions")
        self.assertEqual(posts_payload["target"], "posts")
        self.assertTrue(all(item["target"] == "discussion" for item in discussions_payload["filters"]))
        self.assertTrue(all(item["target"] == "post" for item in posts_payload["filters"]))
        self.assertIn("is:following", {item["syntax"] for item in discussions_payload["filters"]})
        self.assertIn("created:YYYY-MM", {item["syntax"] for item in discussions_payload["filters"]})
        self.assertIn("created:YYYY-MM", {item["syntax"] for item in posts_payload["filters"]})
        self.assertIn("mentioned:me", {item["syntax"] for item in posts_payload["filters"]})

    def test_search_api_respects_discussion_approval_visibility(self):
        admin = User.objects.create_superuser(
            username="search-approval-admin",
            email="search-approval-admin@example.com",
            password="password123",
        )
        approved = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="公开讨论内容",
            user=self.user,
        )
        trusted_group = Group.objects.create(name="SearchApprovalTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")
        pending_author = User.objects.create_user(
            username="search-pending-author",
            email="search-pending-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        pending = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="待审核讨论内容",
            user=pending_author,
        )
        rejected = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="被拒绝讨论内容",
            user=pending_author,
        )
        DiscussionService.reject_discussion(rejected, admin, note="测试拒绝")

        guest_response = self.client.get("/api/search", {"q": "统一搜索可见性", "type": "discussions"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual({item["id"] for item in guest_response.json()["discussions"]}, {approved.id})

        author_response = self.client.get(
            "/api/search",
            {"q": "统一搜索可见性", "type": "discussions"},
            **self.auth_header(pending_author),
        )
        self.assertEqual(author_response.status_code, 200, author_response.content)
        self.assertEqual(
            {item["id"] for item in author_response.json()["discussions"]},
            {approved.id, pending.id, rejected.id},
        )

        admin_response = self.client.get(
            "/api/search",
            {"q": "统一搜索可见性", "type": "discussions"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertEqual(
            {item["id"] for item in admin_response.json()["discussions"]},
            {approved.id, pending.id, rejected.id},
        )

    def test_search_api_respects_post_approval_visibility(self):
        admin = User.objects.create_superuser(
            username="search-post-admin",
            email="search-post-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="搜索回复可见性",
            content="首帖公开",
            user=self.user,
        )
        approved_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索公开内容",
            user=self.user,
        )
        trusted_group = Group.objects.create(name="SearchPostTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        pending_author = User.objects.create_user(
            username="search-post-pending",
            email="search-post-pending@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        pending_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索待审核内容",
            user=pending_author,
        )
        rejected_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索被拒绝内容",
            user=pending_author,
        )
        PostService.reject_post(rejected_reply, admin, note="测试拒绝回复")

        guest_response = self.client.get("/api/search", {"q": "统一回复搜索", "type": "posts"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual({item["id"] for item in guest_response.json()["posts"]}, {approved_reply.id})

        author_response = self.client.get(
            "/api/search",
            {"q": "统一回复搜索", "type": "posts"},
            **self.auth_header(pending_author),
        )
        self.assertEqual(author_response.status_code, 200, author_response.content)
        self.assertEqual(
            {item["id"] for item in author_response.json()["posts"]},
            {approved_reply.id, pending_reply.id, rejected_reply.id},
        )

        admin_response = self.client.get(
            "/api/search",
            {"q": "统一回复搜索", "type": "posts"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertEqual(
            {item["id"] for item in admin_response.json()["posts"]},
            {approved_reply.id, pending_reply.id, rejected_reply.id},
        )

    def test_search_discussions_does_not_fetch_first_post_per_result(self):
        DiscussionService.create_discussion(
            title="搜索摘要优化一",
            content="第一条摘要内容",
            user=self.user,
        )
        DiscussionService.create_discussion(
            title="搜索摘要优化二",
            content="第二条摘要内容",
            user=self.user,
        )

        with patch("apps.core.services.Post.objects.get", side_effect=AssertionError("不应逐条 get 首帖")):
            discussions, total = SearchService.search_discussions("搜索摘要优化", user=self.user)

        self.assertEqual(total, 2)
        self.assertEqual(len(discussions), 2)
        self.assertTrue(all(discussion.excerpt for discussion in discussions))

    def test_search_discussions_uses_subquery_for_first_post_excerpt(self):
        DiscussionService.create_discussion(
            title="子查询摘要优化一",
            content="第一条子查询摘要内容",
            user=self.user,
        )
        DiscussionService.create_discussion(
            title="子查询摘要优化二",
            content="第二条子查询摘要内容",
            user=self.user,
        )

        with patch("apps.core.services.Post.objects.in_bulk", side_effect=AssertionError("不应额外批量查询首帖")):
            discussions, total = SearchService.search_discussions("子查询摘要优化", user=self.user)

        self.assertEqual(total, 2)
        self.assertEqual(len(discussions), 2)
        self.assertTrue(all(discussion.excerpt for discussion in discussions))

    def test_search_api_normalizes_page_and_limit(self):
        for index in range(3):
            DiscussionService.create_discussion(
                title=f"分页归一化搜索 {index}",
                content="分页归一化内容",
                user=self.user,
            )

        response = self.client.get(
            "/api/search",
            {"q": "分页归一化", "type": "discussions", "page": -5, "limit": 500},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 100)
        self.assertEqual(len(payload["discussions"]), 3)

    def test_pagination_service_normalizes_page_and_limit(self):
        page, limit = PaginationService.normalize(0, 999)

        self.assertEqual(page, 1)
        self.assertEqual(limit, 100)

    def test_search_api_all_reuses_single_search_context(self):
        DiscussionService.create_discussion(
            title="上下文复用搜索",
            content="上下文复用内容",
            user=self.user,
        )

        with patch("apps.core.api.SearchService.build_search_context", wraps=SearchService.build_search_context) as build_context:
            response = self.client.get(
                "/api/search",
                {"q": "上下文复用", "type": "all"},
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(build_context.call_count, 1)


class TestRunnerTests(TestCase):
    def test_default_runner_uses_app_test_modules_without_explicit_labels(self):
        runner = BiasDiscoverRunner()
        labels = [
            f"{app}.tests"
            for app in settings.INSTALLED_APPS
            if app.startswith("apps.")
        ]

        suite = runner.build_suite([])

        discovered = set()
        stack = [suite]
        while stack:
            item = stack.pop()
            if hasattr(item, "__iter__") and not hasattr(item, "_testMethodName"):
                stack.extend(list(item))
                continue
            module_name = item.__class__.__module__.split(".")[0:3]
            discovered.add(".".join(module_name[:2]) + ".tests")

        for label in labels:
            self.assertIn(label, discovered)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'bias-online-tests',
    }
})
class OnlineUserServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="online-user",
            email="online-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.other_user = User.objects.create_user(
            username="online-other",
            email="online-other@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_multiple_connections_only_go_offline_after_last_disconnect(self):
        self.assertTrue(OnlineUserService.mark_user_online(self.user.id))
        self.assertFalse(OnlineUserService.mark_user_online(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertFalse(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertTrue(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_touch_extends_presence_ttl(self):
        with patch.object(OnlineUserService, "_now_ts", return_value=100):
            OnlineUserService.mark_user_online(self.user.id)

        with patch.object(OnlineUserService, "_now_ts", return_value=150):
            self.assertTrue(OnlineUserService.touch_user_online(self.user.id))

        with patch.object(OnlineUserService, "_now_ts", return_value=200):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        with patch.object(OnlineUserService, "_now_ts", return_value=241):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_get_online_users_returns_only_marked_users(self):
        OnlineUserService.mark_user_online(self.other_user.id)
        OnlineUserService.mark_user_online(self.user.id)

        users = OnlineUserService.get_online_users(limit=10)

        self.assertEqual({item["id"] for item in users}, {self.user.id, self.other_user.id})
        self.assertTrue(all("username" in item for item in users))


class WebSocketJwtAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ws-user",
            email="ws-user@example.com",
            password="password123",
        )

    def test_valid_token_resolves_user_for_websocket(self):
        token = str(RefreshToken.for_user(self.user).access_token)

        resolved_user = resolve_user_from_token(token)

        self.assertEqual(resolved_user.id, self.user.id)

    def test_invalid_token_returns_anonymous_user(self):
        resolved_user = resolve_user_from_token("invalid-token")

        self.assertIsInstance(resolved_user, AnonymousUser)

    def test_valid_refresh_cookie_resolves_user_for_websocket(self):
        refresh = str(RefreshToken.for_user(self.user))

        resolved_user = resolve_user_from_refresh_token(refresh)

        self.assertEqual(resolved_user.id, self.user.id)

    def test_cookie_parser_extracts_refresh_token(self):
        scope = {
            "headers": [
                (b"cookie", f"theme=light; {REFRESH_TOKEN_COOKIE_NAME}=refresh-token-value".encode()),
            ]
        }

        cookies = _parse_cookie_header(scope)

        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE_NAME], "refresh-token-value")


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
)
class DiscussionRealtimeTests(TestCase):
    def setUp(self):
        trusted_group = Group.objects.create(
            name="RealtimeTrusted",
            name_singular="RealtimeTrusted",
            name_plural="RealtimeTrusted",
            color="#4d698e",
        )
        Permission.objects.create(group=trusted_group, permission="startDiscussion")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")
        Permission.objects.create(group=trusted_group, permission="viewForum")
        Permission.objects.create(group=trusted_group, permission="discussion.reply")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")

        self.author = User.objects.create_user(
            username="realtime-author",
            email="realtime-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.author.user_groups.add(trusted_group)
        self.admin = User.objects.create_superuser(
            username="realtime-admin",
            email="realtime-admin@example.com",
            password="password123",
        )
        self.tag = Tag.objects.create(
            name="实时标签",
            slug="realtime-tag",
            color="#4d698e",
        )
        self.discussion = DiscussionService.create_discussion(
            title="实时讨论",
            content="首帖内容",
            user=self.author,
            tag_ids=[self.tag.id],
        )

    def test_hidden_discussion_is_not_visible_to_anonymous_realtime_viewer(self):
        DiscussionService.set_hidden_state(self.discussion, self.admin, True)

        self.discussion.refresh_from_db()
        self.assertFalse(DiscussionService._can_view_discussion(self.discussion, None))

    def test_visible_discussion_is_accessible_to_authenticated_realtime_viewer(self):
        self.discussion.refresh_from_db()
        self.assertTrue(DiscussionService._can_view_discussion(self.discussion, self.author))

    @patch.object(WebSocketService, "broadcast_discussion_event")
    def test_visible_post_event_broadcasts_discussion_and_post_payload(self, broadcast_discussion_event):
        with self.captureOnCommitCallbacks(execute=True):
            post = PostService.create_post(
                discussion_id=self.discussion.id,
                content="新增回复",
                user=self.author,
            )

        self.assertTrue(broadcast_discussion_event.called)
        discussion_id, event_type, payload = broadcast_discussion_event.call_args.args
        self.assertEqual(discussion_id, self.discussion.id)
        self.assertEqual(event_type, "post.created")
        self.assertEqual(payload["discussion"]["id"], self.discussion.id)
        self.assertEqual(payload["discussion"]["last_post_number"], post.number)
        self.assertEqual(payload["post"]["id"], post.id)
        self.assertEqual(payload["post"]["discussion_id"], self.discussion.id)
        self.assertEqual([item["id"] for item in payload["users"]], [self.author.id])
        self.assertEqual([item["id"] for item in payload["tags"]], [self.tag.id])
        self.assertEqual(payload["tags"][0]["last_posted_discussion"]["id"], self.discussion.id)
        self.assertEqual(payload["tags"][0]["last_posted_discussion"]["last_post_number"], post.number)

    @patch.object(WebSocketService, "broadcast_discussion_event")
    def test_discussion_created_event_broadcasts_related_resources(self, broadcast_discussion_event):
        child_tag = Tag.objects.create(
            name="实时子标签",
            slug="realtime-child-tag",
            color="#e67e22",
            parent=self.tag,
        )

        with self.captureOnCommitCallbacks(execute=True):
            discussion = DiscussionService.create_discussion(
                title="第二个实时讨论",
                content="讨论内容",
                user=self.author,
                tag_ids=[self.tag.id, child_tag.id],
            )

        discussion_id, event_type, payload = broadcast_discussion_event.call_args.args
        self.assertEqual(discussion_id, discussion.id)
        self.assertEqual(event_type, "discussion.created")
        self.assertEqual(payload["discussion"]["id"], discussion.id)
        self.assertEqual(payload["post"]["discussion_id"], discussion.id)
        self.assertEqual([item["id"] for item in payload["users"]], [self.author.id])
        self.assertEqual(
            sorted(item["id"] for item in payload["tags"]),
            sorted([self.tag.id, child_tag.id]),
        )
        self.assertTrue(
            all(item["last_posted_discussion"]["id"] == discussion.id for item in payload["tags"])
        )

    @patch.object(WebSocketService, "broadcast_discussion_event")
    def test_hidden_post_event_broadcasts_minimal_signal_only(self, broadcast_discussion_event):
        with self.captureOnCommitCallbacks(execute=True):
            post = PostService.create_post(
                discussion_id=self.discussion.id,
                content="待隐藏回复",
                user=self.author,
            )
        broadcast_discussion_event.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            PostService.set_hidden_state(post, self.admin, True)

        discussion_id, event_type, payload = broadcast_discussion_event.call_args.args
        self.assertEqual(discussion_id, self.discussion.id)
        self.assertEqual(event_type, "post.hidden")
        self.assertEqual(payload, {})


class AdminSettingsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_settings_are_persisted(self):
        response = self.client.post(
            "/api/admin/settings",
            data=json.dumps({
                "forum_title": "中文社区",
                "seo_title": "中文社区 - 技术论坛",
                "seo_description": "这是一个专注 Django 与 Vue 的中文社区。",
                "seo_keywords": "Python, Django, Vue",
                "seo_robots_index": False,
                "seo_robots_follow": True,
                "announcement_enabled": True,
                "announcement_message": "今晚 23:00 进行维护。",
                "announcement_tone": "warning",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.forum_title").value),
            "中文社区",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_title").value),
            "中文社区 - 技术论坛",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_robots_index").value),
            False,
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.announcement_message").value),
            "今晚 23:00 进行维护。",
        )


    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_advanced_and_cache_endpoints_exist(self):
        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("cache_driver", payload)
        self.assertIn("storage_driver", payload)

        response = self.client.post(
            "/api/admin/cache/clear",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "缓存已清除")

    def test_advanced_settings_persist_storage_config(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "storage_driver": "r2",
                "storage_attachments_dir": "uploads/files",
                "storage_local_path": "custom-media",
                "upload_avatar_max_size_mb": 3,
                "upload_attachment_max_size_mb": 12,
                "upload_site_asset_max_size_mb": 4,
                "storage_r2_bucket": "forum-assets",
                "storage_r2_endpoint": "https://example.r2.cloudflarestorage.com",
                "storage_r2_public_url": "https://cdn.example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.storage_driver").value),
            "r2",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.upload_attachment_max_size_mb").value),
            12,
        )

        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["storage_driver"], "r2")
        self.assertEqual(payload["storage_attachments_dir"], "uploads/files")
        self.assertEqual(payload["upload_avatar_max_size_mb"], 3)
        self.assertEqual(payload["upload_attachment_max_size_mb"], 12)
        self.assertEqual(payload["upload_site_asset_max_size_mb"], 4)
        self.assertEqual(payload["storage_r2_bucket"], "forum-assets")
        self.assertEqual(payload["storage_r2_public_url"], "https://cdn.example.com")

    def test_appearance_settings_persist_head_and_footer_html(self):
        response = self.client.post(
            "/api/admin/appearance",
            data=json.dumps({
                "custom_head_html": "<script>window.testHead = true</script>",
                "custom_footer_html": "<p>备案号：蜀ICP备123456号</p>",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="appearance.custom_head_html").value),
            "<script>window.testHead = true</script>",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="appearance.custom_footer_html").value),
            "<p>备案号：蜀ICP备123456号</p>",
        )

        response = self.client.get(
            "/api/admin/appearance",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["custom_head_html"], "<script>window.testHead = true</script>")
        self.assertEqual(payload["custom_footer_html"], "<p>备案号：蜀ICP备123456号</p>")

    def test_appearance_settings_fall_back_to_legacy_custom_header(self):
        Setting.objects.update_or_create(
            key="appearance.custom_header",
            defaults={"value": json.dumps("<meta name=\"legacy-test\" content=\"1\">")},
        )

        response = self.client.get(
            "/api/admin/appearance",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["custom_head_html"],
            "<meta name=\"legacy-test\" content=\"1\">",
        )
        self.assertEqual(response.json()["custom_footer_html"], "")

    def test_advanced_settings_persist_human_verification_config(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "auth_human_verification_provider": "turnstile",
                "auth_turnstile_site_key": "site-key",
                "auth_turnstile_secret_key": "secret-key",
                "auth_human_verification_login_enabled": True,
                "auth_human_verification_register_enabled": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_human_verification_provider").value),
            "turnstile",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_turnstile_site_key").value),
            "site-key",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_human_verification_register_enabled").value),
            False,
        )

        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["auth_human_verification_provider"], "turnstile")
        self.assertEqual(payload["auth_turnstile_site_key"], "site-key")
        self.assertEqual(payload["auth_turnstile_secret_key"], "secret-key")
        self.assertTrue(payload["auth_human_verification_login_enabled"])
        self.assertFalse(payload["auth_human_verification_register_enabled"])

    def test_advanced_settings_persist_realtime_typing_toggle(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "realtime_typing_enabled": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.realtime_typing_enabled").value),
            False,
        )

        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["realtime_typing_enabled"])

    def test_debug_mode_setting_is_read_only_runtime_value(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "debug_mode": not settings.DEBUG,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["debug_mode"], settings.DEBUG)
        self.assertFalse(Setting.objects.filter(key="advanced.debug_mode").exists())

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
    )
    def test_advanced_settings_rejects_file_cache_in_postgres_runtime(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "cache_driver": "file",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_runtime_configuration")
        self.assertIn("PostgreSQL 生产形态下不允许将缓存驱动保存为文件缓存", payload["message"])

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    )
    def test_advanced_settings_rejects_nonredis_queue_in_postgres_runtime(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "queue_enabled": True,
                "queue_driver": "database",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_runtime_configuration")
        self.assertIn("当前仅允许使用 Redis 队列驱动", payload["message"])

    @patch("apps.core.admin_api.SearchIndexService.rebuild_postgres_indexes")
    def test_admin_can_rebuild_search_indexes(self, rebuild_indexes):
        rebuild_indexes.return_value = {
            "message": "搜索全文索引已重建",
            "indexes": ["discussions_title_slug_fts_idx", "posts_content_fts_idx"],
            "duration_ms": 42,
        }

        response = self.client.post(
            "/api/admin/search-indexes/rebuild",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        rebuild_indexes.assert_called_once_with()
        payload = response.json()
        self.assertEqual(payload["message"], "搜索全文索引已重建")
        self.assertEqual(payload["duration_ms"], 42)
        audit_log = AuditLog.objects.get(action="admin.search_indexes.rebuild")
        self.assertEqual(audit_log.target_type, "search_index")
        self.assertEqual(audit_log.data["indexes"], ["discussions_title_slug_fts_idx", "posts_content_fts_idx"])

    @patch("apps.core.admin_api.SearchIndexService.rebuild_postgres_indexes")
    def test_search_index_rebuild_reports_unsupported_database(self, rebuild_indexes):
        rebuild_indexes.side_effect = RuntimeError("当前数据库不是 PostgreSQL，全文索引无需重建")

        response = self.client.post(
            "/api/admin/search-indexes/rebuild",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "当前数据库不是 PostgreSQL，全文索引无需重建")
        self.assertFalse(AuditLog.objects.filter(action="admin.search_indexes.rebuild").exists())

    @patch("apps.core.admin_api.QueueService.get_worker_status")
    @patch("apps.core.admin_api.SearchIndexService.get_status")
    def test_search_index_status_returns_runtime_snapshot(self, get_status, get_worker_status):
        get_status.return_value = {
            "supported": True,
            "status": "missing",
            "label": "缺少 1 个索引",
            "message": "建议先补齐缺失索引，再继续依赖 PostgreSQL 全文搜索。",
            "expected_indexes": ["discussions_title_slug_fts_idx", "posts_content_fts_idx"],
            "existing_indexes": ["discussions_title_slug_fts_idx"],
            "missing_indexes": ["posts_content_fts_idx"],
        }
        get_worker_status.return_value = {
            "status": "available",
            "label": "2 个 worker 在线",
            "available": True,
            "worker_count": 2,
            "message": "Celery worker 可用。",
        }
        AuditLog.objects.create(
            user=self.admin,
            action="admin.search_indexes.rebuild",
            target_type="search_index",
            data={
                "indexes": ["discussions_title_slug_fts_idx", "posts_content_fts_idx"],
                "duration_ms": 42,
            },
        )

        response = self.client.get(
            "/api/admin/search-indexes/status",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        get_status.assert_called_once_with()
        get_worker_status.assert_called_once_with()
        payload = response.json()
        self.assertTrue(payload["supported"])
        self.assertEqual(payload["status"], "missing")
        self.assertEqual(payload["existing_indexes"], ["discussions_title_slug_fts_idx"])
        self.assertEqual(payload["missing_indexes"], ["posts_content_fts_idx"])
        self.assertEqual(payload["queueWorkerLabel"], "2 个 worker 在线")
        self.assertEqual(payload["lastRebuild"]["duration_ms"], 42)
        self.assertEqual(
            payload["lastRebuild"]["indexes"],
            ["discussions_title_slug_fts_idx", "posts_content_fts_idx"],
        )

    def test_search_index_status_reports_unsupported_database_by_default(self):
        response = self.client.get(
            "/api/admin/search-indexes/status",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["status"], "unsupported")
        self.assertIsNone(payload["lastRebuild"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_settings_affect_test_email_sender(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_driver": "smtp",
                "mail_from": "Bias Mailer <service@example.com>",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "Bias Mailer <service@example.com>")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_sends_to_current_admin_email(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_accepts_custom_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            data=json.dumps({"to_email": "real-recipient@example.com"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "real-recipient@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["real-recipient@example.com"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_uses_saved_test_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                "mail_test_recipient": "saved-recipient@example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "saved-recipient@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["saved-recipient@example.com"])

    def test_mail_settings_persist_mail_from_and_saved_test_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_driver": "smtp",
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_test_recipient": "saved-recipient@example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["mail_from"], "Bias Mailer <service@example.com>")

        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["mail_from"], "Bias Mailer <service@example.com>")
        self.assertEqual(response.json()["mail_test_recipient"], "saved-recipient@example.com")
        self.assertEqual(response.json()["test_to_email"], "saved-recipient@example.com")

    def test_mail_settings_expose_default_templates(self):
        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("{{ site_name }}", payload["mail_verification_subject"])
        self.assertIn("{{ verification_url }}", payload["mail_verification_text"])
        self.assertIn("{{ reset_url }}", payload["mail_password_reset_html"])
        self.assertTrue(payload["mail_from"])
        self.assertEqual(list(payload["drivers"].keys()), ["smtp"])
        self.assertEqual(payload["driver_options"], [{"value": "smtp", "label": "SMTP"}])
        self.assertEqual(payload["mail_host"], "smtp.gmail.com")
        self.assertEqual(payload["mail_encryption"], "tls")
        self.assertIn("sending", payload)

    def test_smtp_driver_requires_host_before_sending(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                "mail_host": "",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertFalse(payload["sending"])
        self.assertIn("mail_host", payload["errors"])

    def test_public_forum_settings_include_basic_and_appearance(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("运行时论坛名称")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_title",
            defaults={"value": json.dumps("运行时 SEO 标题")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_description",
            defaults={"value": json.dumps("运行时 SEO 描述")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_keywords",
            defaults={"value": json.dumps("Python, Django, Vue")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_index",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_follow",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_message",
            defaults={"value": json.dumps("运行时公告")},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_tone",
            defaults={"value": json.dumps("warning")},
        )
        Setting.objects.update_or_create(
            key="appearance.primary_color",
            defaults={"value": json.dumps("#123456")},
        )
        Setting.objects.update_or_create(
            key="appearance.logo_url",
            defaults={"value": json.dumps("/media/runtime-logo.png")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_provider",
            defaults={"value": json.dumps("turnstile")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_site_key",
            defaults={"value": json.dumps("public-site-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_secret_key",
            defaults={"value": json.dumps("private-secret-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_login_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_register_enabled",
            defaults={"value": json.dumps(False)},
        )
        ExtensionInstallation.objects.create(
            extension_id="sample-hello",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["forum_title"], "运行时论坛名称")
        self.assertEqual(payload["seo_title"], "运行时 SEO 标题")
        self.assertEqual(payload["seo_description"], "运行时 SEO 描述")
        self.assertEqual(payload["seo_keywords"], "Python, Django, Vue")
        self.assertFalse(payload["seo_robots_index"])
        self.assertTrue(payload["seo_robots_follow"])
        self.assertTrue(payload["announcement_enabled"])
        self.assertEqual(payload["announcement_message"], "运行时公告")
        self.assertEqual(payload["announcement_tone"], "warning")
        self.assertEqual(payload["primary_color"], "#123456")
        self.assertEqual(payload["logo_url"], "/media/runtime-logo.png")
        self.assertTrue(payload["realtime_typing_enabled"])
        self.assertIn("notification_types", payload)
        self.assertIn("enabled_modules", payload)
        self.assertIn("enabled_extensions", payload)
        self.assertTrue(
            any(
                item["code"] == "discussionReply"
                and item["icon"] == "fas fa-reply"
                and item["navigation_scope"] == "post"
                and item["preference_key"] == "notify_new_post"
                for item in payload["notification_types"]
            )
        )
        self.assertIn("user_preferences", payload)
        self.assertTrue(
            any(
                item["key"] == "notify_user_mentioned"
                and item["category"] == "notification"
                and item["default_value"] is True
                for item in payload["user_preferences"]
            )
        )
        self.assertTrue(
            any(
                item["key"] == "follow_after_reply"
                and item["category"] == "behavior"
                for item in payload["user_preferences"]
            )
        )
        self.assertTrue(
            any(
                item["code"] == "userSuspended"
                and item["navigation_scope"] == "profile"
                for item in payload["notification_types"]
            )
        )
        self.assertEqual(payload["auth_human_verification_provider"], "turnstile")
        self.assertEqual(payload["auth_turnstile_site_key"], "public-site-key")
        self.assertTrue(payload["auth_human_verification_login_enabled"])
        self.assertFalse(payload["auth_human_verification_register_enabled"])
        self.assertTrue(any(item["code"] == "comment" and item["is_default"] for item in payload["post_types"]))
        self.assertTrue(any(item["code"] == "discussionRenamed" for item in payload["post_types"]))
        self.assertIn("core", payload["enabled_modules"])
        self.assertIn("users", payload["enabled_modules"])
        self.assertTrue(
            any(
                item["id"] == "sample-hello"
                and item["frontend_forum_entry"] == "extensions/sample-hello/frontend/forum/index.js"
                and item["settings_values"]["welcome_message"] == "欢迎使用 Sample Hello"
                for item in payload["enabled_extensions"]
            )
        )
        self.assertNotIn("auth_turnstile_secret_key", payload)

    def test_public_forum_settings_expose_realtime_typing_toggle(self):
        Setting.objects.update_or_create(
            key="advanced.realtime_typing_enabled",
            defaults={"value": json.dumps(False)},
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["realtime_typing_enabled"])

    def test_public_forum_settings_fall_back_to_legacy_custom_header(self):
        Setting.objects.update_or_create(
            key="appearance.custom_header",
            defaults={"value": json.dumps("<script>window.legacyHead = true</script>")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["custom_head_html"],
            "<script>window.legacyHead = true</script>",
        )

    def test_public_forum_settings_filters_disabled_extension_runtime_capabilities(self):
        ExtensionInstallation.objects.create(
            extension_id="approval",
            version="1.0.0",
            source="builtin-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertNotIn("approval", payload["enabled_modules"])
        self.assertFalse(any(item["id"] == "approval" for item in payload["enabled_extensions"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["notification_types"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["user_preferences"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["post_types"]))

    @patch("apps.core.admin_api.FileUploadService.upload_site_asset")
    def test_admin_can_upload_appearance_logo(self, upload_site_asset):
        upload_site_asset.return_value = (
            "/media/appearance/logo/site-logo.png",
            {
                "original_name": "site-logo.png",
                "size": 1234,
                "mime_type": "image/png",
            },
        )
        file = SimpleUploadedFile("site-logo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/admin/appearance/upload?target=logo",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["target"], "logo")
        self.assertEqual(payload["url"], "/media/appearance/logo/site-logo.png")
        upload_site_asset.assert_called_once()

    def test_admin_appearance_upload_rejects_invalid_target(self):
        file = SimpleUploadedFile("site-logo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/admin/appearance/upload?target=avatar",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "仅支持上传 logo 或 favicon")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_cache_lifetime_controls_public_forum_settings_cache(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 A")},
        )
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(60)},
        )
        clear_runtime_setting_caches()

        first_response = self.client.get("/api/forum")
        self.assertEqual(first_response.status_code, 200, first_response.content)
        self.assertEqual(first_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 B")},
        )

        cached_response = self.client.get("/api/forum")
        self.assertEqual(cached_response.status_code, 200, cached_response.content)
        self.assertEqual(cached_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        clear_runtime_setting_caches()

        uncached_response = self.client.get("/api/forum")
        self.assertEqual(uncached_response.status_code, 200, uncached_response.content)
        self.assertEqual(uncached_response.json()["forum_title"], "缓存标题 B")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 C")},
        )
        direct_response = self.client.get("/api/forum")
        self.assertEqual(direct_response.status_code, 200, direct_response.content)
        self.assertEqual(direct_response.json()["forum_title"], "缓存标题 C")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_maintenance_mode_blocks_public_api_but_keeps_admin_paths_available(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.maintenance_message",
            defaults={"value": json.dumps("站点维护中，请稍后回来。")},
        )
        clear_runtime_setting_caches()

        public_settings_response = self.client.get("/api/forum")
        self.assertEqual(public_settings_response.status_code, 200, public_settings_response.content)
        self.assertTrue(public_settings_response.json()["maintenance_mode"])
        self.assertEqual(public_settings_response.json()["maintenance_message"], "站点维护中，请稍后回来。")

        blocked_response = self.client.get("/api/search", {"q": "维护"})
        self.assertEqual(blocked_response.status_code, 503, blocked_response.content)
        self.assertEqual(blocked_response.json()["error"], "站点维护中，请稍后回来。")
        self.assertTrue(blocked_response.json()["maintenance"])

        admin_response = self.client.get("/api/admin/advanced", **self.auth_header())
        self.assertEqual(admin_response.status_code, 200, admin_response.content)

        me_response = self.client.get("/api/users/me", **self.auth_header())
        self.assertEqual(me_response.status_code, 200, me_response.content)
        self.assertTrue(me_response.json()["is_staff"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_log_queries_setting_logs_sql_statements(self):
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        Setting.objects.update_or_create(
            key="advanced.log_queries",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with self.assertLogs("bias.sql", level="INFO") as captured:
            response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        joined_output = "\n".join(captured.output)
        self.assertIn("/api/forum", joined_output)
        self.assertIn("total_queries=", joined_output)
        self.assertIn("SELECT", joined_output.upper())

    def test_markdown_preview_endpoint_returns_rendered_html(self):
        alice = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "# 标题\n\n你好 @alice\n\n[官网](https://example.com)"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        html = response.json()["html"]
        self.assertIn("<h1", html)
        self.assertIn(f'href="/u/{alice.id}"', html)
        self.assertIn(">官网</a>", html)
        self.assertIn('target="_blank"', html)

    def test_markdown_preview_keeps_username_route_for_unknown_mentions(self):
        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "你好 @ghost"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('href="/u/ghost"', response.json()["html"])


class AdminUserManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-user-mgr",
            email="admin-user-mgr@example.com",
            password="password123",
        )
        self.member_group = Group.objects.create(
            name="Member",
            name_singular="Member",
            name_plural="Members",
            color="#4d698e",
        )
        self.moderator_group = Group.objects.create(
            name="Moderator",
            name_singular="Moderator",
            name_plural="Moderators",
            color="#80349E",
        )
        self.user = User.objects.create_user(
            username="managed-user",
            email="managed@example.com",
            password="password123",
        )
        self.user.user_groups.add(self.member_group)

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_get_and_update_user(self):
        response = self.client.get(
            f"/api/admin/users/{self.user.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "managed-user")
        self.assertEqual(len(response.json()["groups"]), 1)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                f"/api/admin/users/{self.user.id}",
                data=json.dumps({
                    "username": "managed-user-updated",
                    "email": "managed-updated@example.com",
                    "display_name": "运营同学",
                    "bio": "负责社区运营",
                    "is_staff": True,
                    "is_email_confirmed": True,
                    "group_ids": [self.member_group.id, self.moderator_group.id],
                    "suspended_until": "2030-01-02T03:04:05Z",
                    "suspend_reason": "spam",
                    "suspend_message": "请联系管理员处理",
                }),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["username"], "managed-user-updated")
        self.assertTrue(payload["is_staff"])
        self.assertTrue(payload["is_email_confirmed"])
        self.assertEqual(len(payload["groups"]), 2)

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "managed-user-updated")
        self.assertEqual(self.user.email, "managed-updated@example.com")
        self.assertEqual(self.user.display_name, "运营同学")
        self.assertEqual(self.user.bio, "负责社区运营")
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.is_email_confirmed)
        self.assertEqual(self.user.suspend_reason, "spam")
        self.assertEqual(self.user.suspend_message, "请联系管理员处理")
        self.assertIsNotNone(self.user.suspended_until)
        self.assertGreater(self.user.suspended_until, timezone.now())
        self.assertEqual(
            set(self.user.user_groups.values_list("id", flat=True)),
            {self.member_group.id, self.moderator_group.id},
        )

        suspended_notification = Notification.objects.get(
            user=self.user,
            type="userSuspended",
            subject_id=self.user.id,
        )
        self.assertEqual(suspended_notification.from_user_id, self.admin.id)
        self.assertEqual(suspended_notification.data["suspend_reason"], "spam")
        self.assertEqual(suspended_notification.data["suspend_message"], "请联系管理员处理")

        audit_log = AuditLog.objects.get(action="admin.user.update", target_id=self.user.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "user")
        self.assertIn("is_staff", audit_log.data["changed_fields"])
        self.assertTrue(audit_log.data["groups_changed"])

    def test_admin_unsuspending_user_creates_recovery_notification(self):
        self.user.suspended_until = timezone.now() + timedelta(days=2)
        self.user.suspend_reason = "temporary"
        self.user.suspend_message = "请等待处理"
        self.user.save(update_fields=["suspended_until", "suspend_reason", "suspend_message"])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                f"/api/admin/users/{self.user.id}",
                data=json.dumps({
                    "suspended_until": None,
                    "suspend_reason": "",
                    "suspend_message": "",
                }),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_suspended)

        unsuspended_notification = Notification.objects.get(
            user=self.user,
            type="userUnsuspended",
            subject_id=self.user.id,
        )
        self.assertEqual(unsuspended_notification.from_user_id, self.admin.id)

    def test_admin_suspension_event_dispatches_after_commit(self):
        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                response = self.client.put(
                    f"/api/admin/users/{self.user.id}",
                    data=json.dumps({
                        "suspended_until": "2030-01-02T03:04:05Z",
                        "suspend_reason": "spam",
                        "suspend_message": "请联系管理员处理",
                    }),
                    content_type="application/json",
                    **self.auth_header(),
                )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, UserSuspendedEvent)
        self.assertEqual(event.user_id, self.user.id)
        self.assertEqual(event.actor_user_id, self.admin.id)

    def test_admin_unsuspension_event_dispatches_after_commit(self):
        self.user.suspended_until = timezone.now() + timedelta(days=2)
        self.user.suspend_reason = "temporary"
        self.user.suspend_message = "请等待处理"
        self.user.save(update_fields=["suspended_until", "suspend_reason", "suspend_message"])

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                response = self.client.put(
                    f"/api/admin/users/{self.user.id}",
                    data=json.dumps({
                        "suspended_until": None,
                        "suspend_reason": "",
                        "suspend_message": "",
                    }),
                    content_type="application/json",
                    **self.auth_header(),
                )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, UserUnsuspendedEvent)
        self.assertEqual(event.user_id, self.user.id)
        self.assertEqual(event.actor_user_id, self.admin.id)

    def test_admin_can_delete_user(self):
        response = self.client.delete(
            f"/api/admin/users/{self.user.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        audit_log = AuditLog.objects.get(action="admin.user.delete", target_id=self.user.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.data["username"], "managed-user")

    def test_admin_cannot_delete_self(self):
        response = self.client.delete(
            f"/api/admin/users/{self.admin.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能删除当前登录的管理员账号")
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())


class AdminDashboardStatsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_returns_python_runtime_status(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["runtimeName"], "Python")
        self.assertTrue(payload["pythonVersion"])
        self.assertTrue(payload["djangoVersion"])
        self.assertIn("SQLite", payload["databaseLabel"])
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueMetrics"]["enqueued_count"], 0)
        self.assertEqual(payload["queueMetrics"]["sync_count"], 0)
        self.assertEqual(payload["queueMetrics"]["fallback_count"], 0)
        self.assertFalse(payload["redisEnabled"])
        self.assertEqual(payload["cacheConnectionStatus"], "disabled")
        self.assertIsNone(payload["cacheConnectionAvailable"])
        self.assertEqual(payload["realtimeConnectionStatus"], "disabled")
        self.assertIsNone(payload["realtimeConnectionAvailable"])
        self.assertEqual(payload["queueBrokerStatus"], "disabled")
        self.assertIsNone(payload["queueBrokerAvailable"])
        self.assertEqual(payload["authSecretStatus"], "healthy")
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://localhost:6379/0"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    @patch("apps.core.admin_api._probe_redis_ping")
    @patch("apps.core.admin_api.cache.get", return_value="ok")
    @patch("apps.core.admin_api.cache.set", return_value=None)
    @patch("apps.core.admin_api.QueueService.get_worker_status")
    def test_admin_stats_marks_redis_and_queue_status(self, get_worker_status, _cache_set, _cache_get, probe_redis_ping):
        probe_redis_ping.return_value = {
            "available": True,
            "status": "available",
            "label": "可用",
            "message": "Redis 返回 PONG",
        }
        get_worker_status.return_value = {
            "status": "available",
            "label": "2 个 worker 在线",
            "available": True,
            "worker_count": 2,
            "message": "Celery worker 可用。",
        }
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "Redis")
        self.assertEqual(payload["realtimeDriver"], "Redis")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "Redis")
        self.assertTrue(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "available")
        self.assertEqual(payload["queueWorkerLabel"], "2 个 worker 在线")
        self.assertTrue(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueWorkerCount"], 2)
        self.assertTrue(payload["redisEnabled"])
        self.assertEqual(payload["cacheConnectionStatus"], "available")
        self.assertTrue(payload["cacheConnectionAvailable"])
        self.assertEqual(payload["realtimeConnectionStatus"], "available")
        self.assertTrue(payload["realtimeConnectionAvailable"])
        self.assertEqual(payload["queueBrokerStatus"], "available")
        self.assertTrue(payload["queueBrokerAvailable"])
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    def test_admin_stats_does_not_mark_redis_enabled_from_idle_broker_config(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": json.dumps("redis")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertFalse(payload["redisEnabled"])
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    def test_admin_stats_reports_production_runtime_risks(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": json.dumps("redis")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertIn("locmem-cache-production", risk_codes)
        self.assertIn("realtime-inmemory-production", risk_codes)
        self.assertIn("queue-worker-unavailable", risk_codes)

    @override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://localhost:6379/0"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    @patch("apps.core.admin_api.cache.get", side_effect=RuntimeError("cache offline"))
    @patch("apps.core.admin_api.cache.set", side_effect=RuntimeError("cache offline"))
    def test_admin_stats_reports_cache_backend_unavailable(self, _cache_set, _cache_get):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["cacheConnectionStatus"], "unavailable")
        self.assertFalse(payload["cacheConnectionAvailable"])
        self.assertIn("cache-backend-unavailable", risk_codes)
        self.assertIn("缓存服务在线", dependency_checks["cache"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {}}},
        CELERY_BROKER_URL="memory://",
    )
    @patch("apps.core.admin_api._probe_redis_ping")
    def test_admin_stats_reports_realtime_backend_misconfigured(self, _probe_redis_ping):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["realtimeConnectionStatus"], "misconfigured")
        self.assertFalse(payload["realtimeConnectionAvailable"])
        self.assertIn("realtime-backend-unavailable", risk_codes)
        self.assertIn("CHANNEL_LAYERS.default.CONFIG.hosts", dependency_checks["realtime"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    @patch("apps.core.admin_api.QueueService.get_worker_status")
    @patch("apps.core.admin_api.get_runtime_advanced_settings")
    def test_admin_stats_reports_queue_broker_misconfigured(self, get_runtime_advanced_settings, get_worker_status):
        get_runtime_advanced_settings.return_value = {
            "queue_enabled": True,
            "queue_driver": "redis",
            "maintenance_mode": False,
        }
        get_worker_status.return_value = {
            "status": "unavailable",
            "label": "无 worker 响应",
            "available": False,
            "worker_count": 0,
            "message": "队列已启用，但没有检测到在线 worker。",
        }

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["queueBrokerStatus"], "misconfigured")
        self.assertFalse(payload["queueBrokerAvailable"])
        self.assertIn("queue-broker-unavailable", risk_codes)
        self.assertIn("CELERY_BROKER_URL", dependency_checks["queue-broker"]["recommended_action"])
        self.assertIn("启动 Celery worker", dependency_checks["queue-worker"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis.internal", 6379)]}}},
        CELERY_BROKER_URL="redis://redis.internal:6379/1",
    )
    @patch("apps.core.admin_api.cache.get", return_value="ok")
    @patch("apps.core.admin_api.cache.set", return_value=None)
    @patch("apps.core.admin_api._probe_redis_ping")
    @patch("apps.core.admin_api.QueueService.get_worker_status")
    def test_admin_stats_reports_unreachable_realtime_and_queue_broker(
        self,
        get_worker_status,
        probe_redis_ping,
        _cache_set,
        _cache_get,
    ):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        get_worker_status.return_value = {
            "status": "unavailable",
            "label": "无 worker 响应",
            "available": False,
            "worker_count": 0,
            "message": "队列已启用，但没有检测到在线 worker。",
        }
        probe_redis_ping.side_effect = [
            {
                "available": False,
                "status": "unreachable",
                "label": "不可达",
                "message": "Redis Channel Layer 主机 redis.internal:6379 无法连通：timeout",
            },
            {
                "available": False,
                "status": "unreachable",
                "label": "不可达",
                "message": "Redis broker 主机 redis.internal:6379 无法连通：timeout",
            },
        ]

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertEqual(payload["realtimeConnectionStatus"], "unreachable")
        self.assertEqual(payload["queueBrokerStatus"], "unreachable")
        self.assertIn("realtime-backend-unavailable", risk_codes)
        self.assertIn("queue-broker-unavailable", risk_codes)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis.internal", 6379)]}}},
        CELERY_BROKER_URL="redis://redis.internal:6379/1",
    )
    @patch("apps.core.admin_api.cache.get", return_value="ok")
    @patch("apps.core.admin_api.cache.set", return_value=None)
    @patch("apps.core.admin_api._probe_redis_ping")
    @patch("apps.core.admin_api.QueueService.get_worker_status")
    def test_admin_stats_reports_protocol_error_for_realtime_and_queue_broker(
        self,
        get_worker_status,
        probe_redis_ping,
        _cache_set,
        _cache_get,
    ):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        get_worker_status.return_value = {
            "status": "available",
            "label": "1 个 worker 在线",
            "available": True,
            "worker_count": 1,
            "message": "Celery worker 可用。",
        }
        probe_redis_ping.side_effect = [
            {
                "available": False,
                "status": "protocol-error",
                "label": "协议异常",
                "message": "Redis Channel Layer 已建立连接，但未返回 Redis PONG。",
            },
            {
                "available": False,
                "status": "protocol-error",
                "label": "协议异常",
                "message": "Redis broker 已建立连接，但未返回 Redis PONG。",
            },
        ]

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["realtimeConnectionStatus"], "protocol-error")
        self.assertEqual(payload["queueBrokerStatus"], "protocol-error")

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_reports_missing_redis_in_postgres_runtime(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertIn("redis-disabled-production", risk_codes)

    @override_settings(
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={
            "ALGORITHM": "HS256",
            "SIGNING_KEY": "short-jwt-secret",
        },
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "auth-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_reports_auth_secret_risks(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertEqual(payload["authSecretStatus"], "danger")
        self.assertEqual(payload["authSecretLabel"], "存在风险")
        self.assertIn("django-secret-placeholder", risk_codes)
        self.assertIn("jwt-secret-too-short", risk_codes)
        self.assertIn("JWT 签名密钥长度不足", payload["authSecretMessage"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "queue-reset-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_can_reset_queue_metrics(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.reset_metric_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        self.assertEqual(QueueService.get_metrics()["sync_count"], 1)

        response = self.client.post("/api/admin/queue/metrics/reset", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["message"], "队列运行指标已重置")
        self.assertEqual(payload["metrics"]["sync_count"], 0)
        self.assertEqual(payload["metrics"]["enqueued_count"], 0)
        self.assertEqual(payload["metrics"]["fallback_count"], 0)
        audit_log = AuditLog.objects.get(action="admin.queue_metrics.reset")
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "")

    def test_non_staff_cannot_reset_queue_metrics(self):
        member = User.objects.create_user(
            username="queue-reset-member",
            email="queue-reset-member@example.com",
            password="password123",
        )
        token = RefreshToken.for_user(member).access_token

        response = self.client.post(
            "/api/admin/queue/metrics/reset",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403, response.content)


class AdminAuditLogApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="audit-admin",
            email="audit-admin@example.com",
            password="password123",
        )
        self.member = User.objects.create_user(
            username="audit-member",
            email="audit-member@example.com",
            password="password123",
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_list_audit_logs(self):
        AuditLog.objects.create(
            user=self.admin,
            action="admin.cache.clear",
            target_type="cache",
            ip_address="127.0.0.1",
            data={"source": "test"},
        )
        AuditLog.objects.create(
            user=self.admin,
            action="admin.user.delete",
            target_type="user",
            target_id=self.member.id,
            data={"username": self.member.username},
        )
        AuditLog.objects.create(
            user=self.member,
            action="password_reset",
            target_type="user",
            target_id=self.member.id,
            data={"source": "public"},
        )

        response = self.client.get(
            "/api/admin/audit-logs",
            {"target_type": "user"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["action"], "admin.user.delete")
        self.assertEqual(payload["data"][0]["target_id"], self.member.id)
        self.assertEqual(payload["data"][0]["user"]["username"], self.admin.username)
        self.assertNotIn("password_reset", {item["action"] for item in payload["data"]})

    def test_non_staff_cannot_list_audit_logs(self):
        response = self.client.get(
            "/api/admin/audit-logs",
            **self.auth_header(self.member),
        )

        self.assertEqual(response.status_code, 403, response.content)


class HealthCheckApiTests(TestCase):
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "health-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="health-check-secret-key-1234567890123456",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "health-check-jwt-secret-key-1234567890"},
    )
    def test_health_check_exposes_runtime_readiness_summary(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["state"], "ready")
        self.assertIn("readiness", payload)
        self.assertEqual(payload["readiness"]["cache_driver"], "内存")
        self.assertEqual(payload["readiness"]["realtime_driver"], "In-memory")
        self.assertEqual(payload["readiness"]["queue_driver"], "sync")
        self.assertFalse(payload["readiness"]["queue_enabled"])
        self.assertEqual(payload["readiness"]["queue_worker_status"]["status"], "disabled")
        self.assertEqual(payload["readiness"]["auth_secret_status"]["status"], "healthy")
        self.assertEqual(payload["readiness"]["runtime_risks"], [])

    @override_settings(
        DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "health-prod-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "short-jwt-secret"},
        FRONTEND_URL="",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    def test_health_check_reports_production_runtime_risks(self, _is_test_process):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["readiness"]["runtime_risks"]}
        self.assertIn("django-secret-placeholder", risk_codes)
        self.assertIn("jwt-secret-too-short", risk_codes)
        self.assertIn("redis-disabled-production", risk_codes)
        self.assertIn("frontend-url-missing-production", risk_codes)
        self.assertIn("email-backend-development-production", risk_codes)


class QueueServiceTests(TestCase):
    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_queue_worker_status_reports_disabled_when_queue_is_off(self):
        from apps.core.queue_service import QueueService

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "disabled")
        self.assertFalse(status["available"])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    @patch("apps.core.queue_service.QueueService._should_skip_live_worker_check", return_value=False)
    def test_queue_worker_status_reports_available_workers(self, _skip_live_worker_check, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = {
            "celery@worker-a": {"ok": "pong"},
            "celery@worker-b": {"ok": "pong"},
        }

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "available")
        self.assertTrue(status["available"])
        self.assertEqual(status["worker_count"], 2)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    @patch("apps.core.queue_service.QueueService._should_skip_live_worker_check", return_value=False)
    def test_queue_worker_status_reports_unavailable_without_ping_response(self, _skip_live_worker_check, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = None

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "unavailable")
        self.assertFalse(status["available"])
        self.assertEqual(status["worker_count"], 0)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    def test_queue_worker_status_skips_live_probe_during_tests(self, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "unavailable")
        self.assertEqual(status["label"], "测试环境跳过")
        self.assertFalse(status["available"])
        inspect.assert_not_called()

    def test_queue_metrics_record_sync_dispatch(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.sync_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        result = QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        metrics = QueueService.get_metrics()

        self.assertEqual(result, "done")
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["enqueued_count"], 0)
        self.assertEqual(metrics["fallback_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.sync_task")

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_queue_metrics_record_enqueue_and_fallback(self):
        from apps.core.queue_service import QueueService

        class SuccessfulTask:
            name = "tests.successful_task"

            def delay(self):
                return "queued"

        class FailingTask:
            name = "tests.failing_task"

            def delay(self):
                raise RuntimeError("queue down")

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        QueueService.reset_metrics()

        self.assertEqual(
            QueueService.dispatch_celery_task(SuccessfulTask(), fallback=lambda: "sync"),
            "queued",
        )
        self.assertEqual(
            QueueService.dispatch_celery_task(FailingTask(), fallback=lambda: "fallback"),
            "fallback",
        )
        metrics = QueueService.get_metrics()

        self.assertEqual(metrics["enqueued_count"], 1)
        self.assertEqual(metrics["fallback_count"], 1)
        self.assertEqual(metrics["sync_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.failing_task")
        self.assertEqual(metrics["last_error"], "queue down")

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_queue_dispatch_skips_live_enqueue_for_app_tasks_during_tests(self):
        from apps.core.queue_service import QueueService

        class AppTask:
            __module__ = "apps.notifications.tasks"
            name = "apps.notifications.tasks.dispatch_notification_batch"

            def delay(self):
                raise AssertionError("live queue should be skipped in tests")

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        QueueService.reset_metrics()

        result = QueueService.dispatch_celery_task(AppTask(), fallback=lambda: "sync")
        metrics = QueueService.get_metrics()

        self.assertEqual(result, "sync")
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["enqueued_count"], 0)
        self.assertEqual(metrics["fallback_count"], 0)


class ComposerUploadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="composer-user",
            email="composer@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_authenticated_user_can_upload_attachment(self, upload_attachment):
        upload_attachment.return_value = (
            f"/media/attachments/{self.user.id}/guide.pdf",
            {
                "original_name": "guide.pdf",
                "size": 128,
                "mime_type": "application/pdf",
                "hash": "abc123",
            },
        )
        file = SimpleUploadedFile("guide.pdf", b"dummy-pdf", content_type="application/pdf")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["url"], f"/media/attachments/{self.user.id}/guide.pdf")
        self.assertEqual(payload["original_name"], "guide.pdf")
        self.assertEqual(payload["mime_type"], "application/pdf")
        self.assertFalse(payload["is_image"])
        upload_attachment.assert_called_once()

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_upload_image_marks_response_as_image(self, upload_attachment):
        upload_attachment.return_value = (
            f"/media/attachments/{self.user.id}/photo.png",
            {
                "original_name": "photo.png",
                "size": 256,
                "mime_type": "image/png",
                "hash": "def456",
            },
        )
        file = SimpleUploadedFile("photo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_image"])

    def test_upload_requires_file(self):
        response = self.client.post(
            "/api/uploads",
            {},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "请选择要上传的文件")

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_upload_validation_error_returns_400(self, upload_attachment):
        upload_attachment.side_effect = ValueError("不支持的文件格式")
        file = SimpleUploadedFile("virus.exe", b"bad", content_type="application/octet-stream")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不支持的文件格式")


class InstallForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_site_config_and_invokes_manage_steps(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--admin-username",
                        "forum-admin",
                        "--admin-email",
                        "forum-admin@example.com",
                        "--admin-password",
                        "password123",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "sqlite")
            self.assertEqual(config.sqlite_name, "db.sqlite3")
            self.assertFalse(config.use_redis)
            self.assertEqual(config.resolved_frontend_url(), "http://localhost:5173")
            self.assertTrue(config.secret_key)
            self.assertTrue(config.jwt_secret_key)

            self.assertEqual(mock_run_manage_py.call_count, 4)
            invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
            self.assertEqual(
                invoked_steps,
                [
                    ["init_groups"],
                    ["sync_forum_version"],
                    ["collectstatic", "--noinput"],
                    [
                        "ensure_admin",
                        "--username",
                        "forum-admin",
                        "--email",
                        "forum-admin@example.com",
                        "--password",
                        "password123",
                    ],
                ],
            )

            first_args, first_env = mock_run_manage_py.call_args_list[0].args
            self.assertEqual(first_args, ["init_groups"])
            self.assertEqual(
                first_env["BIAS_SITE_CONFIG"],
                str(config_path),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_postgres_site_config_values(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--db-name",
                        "community",
                        "--db-user",
                        "community_user",
                        "--db-password",
                        "community_pass",
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5433",
                        "--frontend-url",
                        "http://forum.example.com",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "postgres")
            self.assertFalse(config.debug)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.db_name, "community")
            self.assertEqual(config.db_user, "community_user")
            self.assertEqual(config.db_password, "community_pass")
            self.assertEqual(config.db_host, "db.internal")
            self.assertEqual(config.db_port, "5433")
            self.assertEqual(config.resolved_frontend_url(), "http://forum.example.com")

            self.assertEqual(mock_run_manage_py.call_count, 3)
            group_args, group_env = mock_run_manage_py.call_args_list[0].args
            self.assertEqual(group_args, ["init_groups"])
            self.assertEqual(group_env["BIAS_SITE_CONFIG"], str(config_path))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_allows_explicit_redis_override(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--redis",
                        "on",
                        "--redis-host",
                        "cache.internal",
                        "--redis-port",
                        "6380",
                        "--redis-db",
                        "5",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            config = read_site_config(config_path)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.redis_host, "cache.internal")
            self.assertEqual(config.redis_port, "6380")
            self.assertEqual(config.redis_db, "5")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_overwrite_preserves_existing_secrets(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "secret_key": "secret-1",
                        "jwt_secret_key": "jwt-secret-1",
                        "database_mode": "postgres",
                        "db_name": "bias",
                        "db_user": "postgres",
                        "db_password": "postgres",
                        "db_host": "db",
                        "db_port": "5432",
                        "use_redis": True,
                        "redis_host": "redis",
                        "redis_port": "6379",
                        "redis_db": "0",
                        "site_domains": ["old.example.com"],
                        "site_scheme": "https",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command(
                    "install_forum",
                    "--config",
                    str(config_path),
                    "--site-domains",
                    "bias.chat,www.bias.chat",
                    "--skip-migrate",
                    "--skip-admin",
                    "--overwrite",
                    "--non-interactive",
                )

            config = read_site_config(config_path)
            self.assertEqual(config.secret_key, "secret-1")
            self.assertEqual(config.jwt_secret_key, "jwt-secret-1")
            self.assertEqual(config.site_domains, ["bias.chat", "www.bias.chat"])
            self.assertEqual(config.db_host, "db")
            self.assertEqual(config.resolved_frontend_url(), "https://bias.chat")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_install_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(
                CommandError,
                "PostgreSQL 模式缺少必要配置: db_name, db_user, db_password",
            ):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_role_missing(self, mock_running_in_docker, mock_connect):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "woniu" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaisesMessage(CommandError, "Docker 复用了旧的 postgres_data 卷"):
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=False)
    def test_install_forum_surfaces_native_postgres_hint_when_role_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "bias_user" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaises(CommandError) as captured:
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-name",
                        "bias",
                        "--db-user",
                        "bias_user",
                        "--db-password",
                        "secret",
                        "--db-host",
                        "127.0.0.1",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            message = str(captured.exception)
            self.assertIn("请先在 PostgreSQL 中创建对应用户", message)
            self.assertNotIn("postgres_data", message)
            self.assertNotIn(".env", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_database_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  database "bias" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaises(CommandError) as captured:
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )

            message = str(captured.exception)
            self.assertIn("postgres_data 卷", message)
            self.assertIn("旧数据库名", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class BootstrapConfigFallbackTests(TestCase):
    def test_load_site_bootstrap_prefers_database_env_when_site_config_missing(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with patch("apps.core.bootstrap_config._is_test_process", return_value=False):
                with patch.dict(
                    os.environ,
                    {
                        "DB_NAME": "bias",
                        "DB_USER": "postgres",
                        "DB_PASSWORD": "postgres",
                        "DB_HOST": "db",
                        "DB_PORT": "5432",
                        "REDIS_HOST": "redis",
                        "REDIS_PORT": "6379",
                        "REDIS_DB": "0",
                    },
                    clear=False,
                ):
                    config = load_site_bootstrap(temp_dir)

            self.assertTrue(config.installed)
            self.assertEqual(config.source, "env")
            self.assertEqual(config.database_mode, "postgres")
            self.assertEqual(config.db_name, "bias")
            self.assertEqual(config.db_user, "postgres")
            self.assertEqual(config.db_host, "db")
            self.assertTrue(config.use_redis)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class SettingsServiceFallbackTests(TestCase):
    def test_get_setting_group_returns_defaults_when_settings_table_is_unavailable(self):
        defaults = {"log_queries": False, "maintenance_mode": False}

        with patch("apps.core.settings_service.Setting.objects.filter", side_effect=OperationalError("no such table")):
            values = get_setting_group("advanced", defaults)

        self.assertEqual(values, defaults)


class EnsureAdminCommandTests(TestCase):
    def test_ensure_admin_command_creates_admin_user_and_group_membership(self):
        call_command("init_groups")

        call_command(
            "ensure_admin",
            "--username",
            "forum-admin",
            "--email",
            "forum-admin@example.com",
            "--password",
            "password123",
        )

        admin = User.objects.get(username="forum-admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_email_confirmed)
        self.assertTrue(admin.user_groups.filter(name="Admin").exists())
        self.assertTrue(admin.check_password("password123"))

    def test_init_groups_syncs_registry_managed_admin_permissions(self):
        call_command("init_groups")

        admin_group = Group.objects.get(id=1)
        permissions = set(
            Permission.objects.filter(group=admin_group).values_list("permission", flat=True)
        )

        self.assertTrue(
            set(get_registry_permission_codes_by_prefix("admin.approval.")).issubset(permissions)
        )
        self.assertTrue(
            set(get_registry_permission_codes_by_prefix("admin.flag.")).issubset(permissions)
        )


class UpgradeForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned")
    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_runs_default_upgrade_steps(self, mock_run_manage_py, mock_ensure_versions):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_ensure_versions.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(mock_run_manage_py.call_count, 6)
        invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
        self.assertEqual(
            invoked_steps,
            [
                ["check"],
                ["migrate", "--noinput"],
                ["init_groups"],
                ["sync_forum_version"],
                ["clear_runtime_cache"],
                ["collectstatic", "--noinput"],
            ],
        )
        self.assertEqual(mock_run_manage_py.call_args_list[0].args[1]["BIAS_SITE_CONFIG"], str(config_path))

    @patch(
        "apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned",
        side_effect=ValueError("版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致"),
    )
    def test_upgrade_forum_requires_aligned_release_versions(self, mock_ensure_versions):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                CommandError,
                "版本校验失败: 版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_dry_run_does_not_execute_steps(self, mock_run_manage_py):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--dry-run",
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run_manage_py.assert_not_called()

    def test_upgrade_forum_requires_existing_site_config(self):
        temp_dir = make_workspace_temp_dir()
        try:
            missing_config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(CommandError, f"站点配置不存在: {missing_config_path}。请先执行 python manage.py install_forum"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(missing_config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_upgrade_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "postgres",
                        "db_name": "",
                        "db_user": "",
                        "db_host": "",
                        "db_port": "",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "PostgreSQL 模式缺少必要配置: db_name, db_user, db_host, db_port"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ReleaseVersionControlTests(TestCase):
    def test_ensure_release_versions_aligned_raises_when_version_mismatch(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                ValueError,
                "版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                ensure_release_versions_aligned(base_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_syncs_version_and_frontend_package_files(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout="",
            stderr="",
        )

        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "bias-frontend",
                        "version": "1.0.0",
                        "packages": {
                            "": {
                                "name": "bias-frontend",
                                "version": "1.0.0",
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                call_command("prepare_release", "--tag", "v1.2.3")

            self.assertEqual((base_dir / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")
            package_json = json.loads((base_dir / "frontend" / "package.json").read_text(encoding="utf-8"))
            package_lock = json.loads((base_dir / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(package_json["version"], "1.2.3")
            self.assertEqual(package_lock["version"], "1.2.3")
            self.assertEqual(package_lock["packages"][""]["version"], "1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_prepare_release_rejects_mismatched_version_and_tag(self):
        with self.assertRaisesMessage(CommandError, "--set-version 与 --tag 不一致"):
            call_command("prepare_release", "--set-version", "1.0.1", "--tag", "v1.0.2", "--allow-dirty")

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M README.md\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("prepare_release", "--set-version", "1.0.1")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_creates_git_tag_when_versions_match(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_mismatched_tag_and_version(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git tag 与代码版本不一致：tag=v1.2.4，VERSION=1.2.3",
                ):
                    call_command("finalize_release", "--tag", "v1.2.4", "--allow-dirty")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run.assert_not_called()

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M VERSION\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_existing_git_tag(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "--list", "v1.2.3"),
                returncode=0,
                stdout="v1.2.3\n",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(CommandError, "Git tag 已存在: v1.2.3"):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_runs_prepare_then_finalize_in_dry_run(self, mock_call_command, mock_subprocess_run):
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--dry-run",
            "--allow-dirty",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3", "--allow-dirty", "--dry-run"),
                ("finalize_release", "--tag", "v1.2.3", "--dry-run"),
            ],
        )
        mock_subprocess_run.assert_not_called()

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_commits_then_tags_and_pushes(self, mock_call_command, mock_subprocess_run):
        base_dir = settings.BASE_DIR
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--push",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3"),
                ("finalize_release", "--tag", "v1.2.3"),
            ],
        )
        self.assertEqual(
            [call.args[0] for call in mock_subprocess_run.call_args_list],
            [
                build_git_command(base_dir, "add", "VERSION", "frontend/package.json", "frontend/package-lock.json"),
                build_git_command(base_dir, "commit", "-m", "发布 1.2.3"),
                build_git_command(base_dir, "push", "origin", "main", "--tags"),
            ],
        )

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_uses_safe_directory_git_commands(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )
            mock_run.side_effect = [
                CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"), returncode=0, stdout="", stderr=""),
            ]

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(mock_run.call_args_list[0].args[0], build_git_command(base_dir, "status", "--short"))
            self.assertEqual(mock_run.call_args_list[1].args[0], build_git_command(base_dir, "tag", "--list", "v1.2.3"))
            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class SystemStatusApiTests(TestCase):
    def test_system_status_endpoint_returns_ready_state(self):
        response = self.client.get("/api/system/status")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["state"], "ready")
        self.assertIn("current_version", payload)


class LocalStorageSettingsTests(TestCase):
    def test_attachment_upload_respects_custom_local_storage_settings(self):
        tmpdir = Path.cwd() / "media" / f"storage-test-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            Setting.objects.update_or_create(
                key="advanced.storage_driver",
                defaults={"value": json.dumps("local")},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_local_path",
                defaults={"value": json.dumps(str(tmpdir))},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_local_base_url",
                defaults={"value": json.dumps("/uploads/")},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_attachments_dir",
                defaults={"value": json.dumps("forum-files")},
            )

            file = SimpleUploadedFile("guide.txt", b"hello storage", content_type="text/plain")

            file_url, file_info = FileUploadService.upload_attachment(file, 9)

            self.assertTrue(file_url.startswith("/uploads/forum-files/9/"))
            self.assertEqual(file_info["original_name"], "guide.txt")

            relative_key = file_url.removeprefix("/uploads/")
            stored_path = Path(tmpdir).joinpath(*relative_key.split("/"))
            self.assertTrue(stored_path.exists())
            self.assertEqual(stored_path.read_bytes(), b"hello storage")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_attachment_upload_respects_runtime_size_limit(self):
        Setting.objects.update_or_create(
            key="advanced.upload_attachment_max_size_mb",
            defaults={"value": json.dumps(1)},
        )
        file = SimpleUploadedFile("too-large.txt", b"x" * (1024 * 1024 + 1), content_type="text/plain")

        with self.assertRaisesMessage(ValueError, "文件大小超过限制"):
            FileUploadService.upload_attachment(file, 9)

    def test_upload_policy_exposes_runtime_limits(self):
        user = User.objects.create_user(
            username="upload-policy-user",
            email="upload-policy-user@example.com",
            password="password123",
        )
        Setting.objects.update_or_create(
            key="advanced.upload_attachment_max_size_mb",
            defaults={"value": json.dumps(7)},
        )
        token = RefreshToken.for_user(user).access_token

        response = self.client.get(
            "/api/uploads/policy",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["attachment_max_size_mb"], 7)
        self.assertIn(".pdf", response.json()["allowed_attachment_extensions"])


class AdminGroupManagementApiTests(TestCase):
    def setUp(self):
        call_command("init_groups")
        self.admin = User.objects.create_superuser(
            username="admin-group-mgr",
            email="admin-group-mgr@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_create_and_update_group(self):
        response = self.client.post(
            "/api/admin/groups",
            data=json.dumps({
                "name": "Helpers",
                "color": "#27ae60",
                "icon": "fas fa-life-ring",
                "is_hidden": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        group_id = response.json()["id"]
        self.assertTrue(Group.objects.filter(id=group_id, name="Helpers").exists())

        response = self.client.put(
            f"/api/admin/groups/{group_id}",
            data=json.dumps({
                "name": "Support",
                "color": "#8e44ad",
                "icon": "fas fa-headset",
                "is_hidden": True,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["name"], "Support")
        self.assertTrue(payload["is_hidden"])

        group = Group.objects.get(id=group_id)
        self.assertEqual(group.name, "Support")
        self.assertEqual(group.name_singular, "Support")
        self.assertEqual(group.name_plural, "Support")
        self.assertEqual(group.color, "#8e44ad")
        self.assertEqual(group.icon, "fas fa-headset")
        self.assertTrue(group.is_hidden)

    def test_admin_can_delete_custom_group(self):
        group = Group.objects.create(
            name="Helpers",
            name_singular="Helper",
            name_plural="Helpers",
            color="#27ae60",
        )
        Permission.objects.create(group=group, permission="discussion.reply")

        response = self.client.delete(
            f"/api/admin/groups/{group.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Group.objects.filter(id=group.id).exists())
        self.assertFalse(Permission.objects.filter(group_id=group.id).exists())
        audit_log = AuditLog.objects.get(action="admin.group.delete", target_id=group.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "group")
        self.assertEqual(audit_log.data["name"], "Helpers")

    def test_admin_cannot_delete_builtin_group(self):
        response = self.client.delete(
            "/api/admin/groups/1",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "系统默认用户组不允许删除")
        self.assertTrue(Group.objects.filter(id=1, name="Admin").exists())


class AdminPermissionsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-permission-mgr",
            email="admin-permission-mgr@example.com",
            password="password123",
        )
        Group.objects.get_or_create(
            id=1,
            defaults={
                "name": "Admin",
                "name_singular": "Admin",
                "name_plural": "Admins",
                "color": "#B72A2A",
            },
        )
        self.group = Group.objects.create(
            name="Editors",
            name_singular="Editor",
            name_plural="Editors",
            color="#4d698e",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_permissions_api_normalizes_legacy_codes_on_read(self):
        Permission.objects.create(group=self.group, permission="reply")
        Permission.objects.create(group=self.group, permission="editPosts")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        group_permissions = payload.get(str(self.group.id), payload.get(self.group.id, []))
        self.assertEqual(set(group_permissions), {"discussion.reply", "discussion.edit"})

    def test_permissions_api_includes_staff_runtime_baseline_for_admin_group(self):
        admin_group = Group.objects.get(id=1)
        Permission.objects.create(group=admin_group, permission="discussion.edit")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        admin_permissions = set(payload.get("1", payload.get(1, [])))
        self.assertIn("discussion.edit", admin_permissions)
        self.assertIn("discussion.editOwn", admin_permissions)
        self.assertIn("discussion.deleteOwn", admin_permissions)

    def test_permissions_api_preserves_staff_runtime_baseline_when_saving_admin_group(self):
        admin_group = Group.objects.get(id=1)

        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(admin_group.id): ["discussion.edit"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        saved_permissions = set(
            Permission.objects.filter(group=admin_group).values_list("permission", flat=True)
        )
        self.assertIn("discussion.edit", saved_permissions)
        self.assertIn("discussion.editOwn", saved_permissions)
        self.assertIn("discussion.deleteOwn", saved_permissions)

    def test_permissions_api_normalizes_legacy_codes_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["reply", "editPosts", "reply"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(Permission.objects.filter(group=self.group).values_list("permission", flat=True)),
            {"discussion.reply", "discussion.edit", "viewForum"},
        )

    def test_permissions_api_expands_required_permissions_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["replyWithoutApproval"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(Permission.objects.filter(group=self.group).values_list("permission", flat=True)),
            {"replyWithoutApproval", "discussion.reply", "viewForum"},
        )

    def test_permissions_api_rejects_unknown_permission(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["unknown.permission"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("未知权限", response.json()["error"])

    def test_permissions_meta_api_returns_registry_sections(self):
        response = self.client.get(
            "/api/admin/permissions/meta",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("sections", payload)
        self.assertIn("aliases", payload)
        self.assertIn("modules", payload)
        section_names = {section["name"] for section in payload["sections"]}
        self.assertIn("view", section_names)
        self.assertIn("moderate", section_names)
        all_permission_codes = {
            permission["name"]
            for section in payload["sections"]
            for permission in section["permissions"]
        }
        self.assertIn("discussion.reply", all_permission_codes)
        self.assertEqual(payload["aliases"]["reply"], "discussion.reply")
        self.assertTrue(any(module["id"] == "core" for module in payload["modules"]))

    @patch("apps.core.admin_api.build_runtime_dependency_summary")
    def test_modules_api_returns_builtin_registry_snapshot(self, build_runtime_dependency_summary):
        build_runtime_dependency_summary.return_value = {
            "status": "healthy",
            "label": "健康",
            "issues": [],
            "checks": [],
        }
        response = self.client.get(
            "/api/admin/modules",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("modules", payload)
        self.assertIn("category_summaries", payload)
        self.assertIn("dependency_attention", payload)
        self.assertIn("admin_pages", payload)
        self.assertIn("notification_types", payload)
        self.assertIn("user_preferences", payload)
        self.assertIn("language_packs", payload)
        self.assertIn("event_listeners", payload)
        self.assertIn("post_types", payload)
        self.assertIn("search_filters", payload)
        self.assertIn("discussion_sorts", payload)
        self.assertIn("discussion_list_filters", payload)
        self.assertIn("resource_definitions", payload)
        self.assertIn("resource_relationships", payload)
        self.assertIn("resource_fields", payload)
        module_ids = {module["id"] for module in payload["modules"]}
        self.assertIn("core", module_ids)
        self.assertIn("posts", module_ids)
        self.assertIn("tags", module_ids)
        self.assertIn("approval", module_ids)
        self.assertIn("notifications", module_ids)
        self.assertGreaterEqual(payload["summary"]["module_count"], len(module_ids))
        self.assertGreaterEqual(payload["summary"]["enabled_count"], 1)
        self.assertGreaterEqual(payload["summary"]["user_preference_count"], 1)
        self.assertGreaterEqual(payload["summary"]["language_pack_count"], 1)

        core_module = next(module for module in payload["modules"] if module["id"] == "core")
        posts_module = next(module for module in payload["modules"] if module["id"] == "posts")
        notifications_module = next(module for module in payload["modules"] if module["id"] == "notifications")
        approval_module = next(module for module in payload["modules"] if module["id"] == "approval")
        flags_module = next(module for module in payload["modules"] if module["id"] == "flags")
        tags_module = next(module for module in payload["modules"] if module["id"] == "tags")
        admin_page_paths = {page["path"] for page in payload["admin_pages"]}
        self.assertIn("/admin/modules", admin_page_paths)
        self.assertIn("/admin/docs", admin_page_paths)
        self.assertTrue(core_module["is_core"])
        self.assertEqual(core_module["category_label"], "核心")
        self.assertIn("dependency_status", core_module)
        self.assertIn("health_status", core_module)
        self.assertIn("settings", core_module)
        self.assertIn("runtime", core_module)
        self.assertIn("lifecycle", core_module)
        self.assertIn("registration_counts", core_module)
        self.assertIn("permissions", core_module)
        self.assertIn("documentation_url", core_module)
        self.assertIn("extension", core_module)
        self.assertEqual(
            core_module["documentation_url"],
            "/admin.html#/admin/docs?guide=module-development&module=core",
        )
        self.assertEqual(core_module["extension"]["id"], "core")
        self.assertEqual(core_module["extension"]["source"], "builtin-module")
        self.assertTrue(core_module["extension"]["runtime"]["installed"])
        self.assertIn("debug_items", core_module["runtime"])
        self.assertIn("lifecycle_phases", core_module["runtime"])
        self.assertIn("permissions_entry_path", core_module["runtime"])
        self.assertIn("module_center_path", core_module["runtime"])
        self.assertEqual(core_module["lifecycle"]["registration_mode"], "static")
        self.assertEqual(core_module["lifecycle"]["registration_mode_label"], "启动时静态注册")
        self.assertEqual(core_module["lifecycle"]["supports_disable"], False)
        self.assertEqual(core_module["lifecycle"]["supports_teardown"], False)
        self.assertEqual(
            [item["key"] for item in core_module["lifecycle"]["phases"]],
            ["register", "bootstrap", "ready", "disable", "teardown"],
        )
        self.assertTrue(any(item["optional"] for item in core_module["lifecycle"]["phases"] if item["key"] == "disable"))
        self.assertIn("resource_definitions", posts_module)
        self.assertIn("resource_relationships", posts_module)
        self.assertIn("resource_fields", tags_module)
        self.assertIn("search_filters", tags_module)
        self.assertEqual(core_module["dependency_status"], "healthy")
        self.assertEqual(core_module["health_status"], "healthy")
        self.assertIn("basic", core_module["settings"]["groups"])
        self.assertEqual(core_module["runtime"]["boot_mode"], "static")
        self.assertEqual(core_module["runtime"]["module_center_path"], "/admin/modules?module=core")
        self.assertTrue(any(item["key"] == "module_id" and item["value"] == "core" for item in core_module["runtime"]["debug_items"]))
        self.assertEqual(approval_module["runtime"]["permissions_entry_path"], "/admin/permissions")
        discussions_module = next(module for module in payload["modules"] if module["id"] == "discussions")
        self.assertIn("discussion_sorts", discussions_module)
        self.assertIn("discussion_list_filters", discussions_module)
        self.assertTrue(any(item["code"] == "author" and item["syntax"] == "author:<username>" for item in discussions_module["search_filters"]))
        self.assertTrue(any(item["code"] == "is_sticky" and item["syntax"] == "is:sticky" for item in discussions_module["search_filters"]))
        self.assertTrue(any(item["code"] == "is_locked" and item["syntax"] == "is:locked" for item in discussions_module["search_filters"]))
        self.assertTrue(any(item["code"] == "tag" and item["syntax"] == "tag:<slug>" for item in tags_module["search_filters"]))
        self.assertTrue(any(item["module_id"] == "tags" and item["code"] == "tag" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "discussions" and item["code"] == "author" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "discussions" and item["target"] == "post" and item["code"] == "author" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "subscriptions" and item["code"] == "is_following" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "discussions" and item["code"] == "unanswered" for item in payload["discussion_sorts"]))
        self.assertTrue(any(item["code"] == "unanswered" and item["toolbar_visible"] is False for item in payload["discussion_sorts"]))
        self.assertTrue(any(item["code"] == "newest" and item["icon"] == "fas fa-file-alt" for item in payload["discussion_sorts"]))
        self.assertTrue(any(item["module_id"] == "discussions" and item["code"] == "unread" for item in payload["discussion_list_filters"]))
        self.assertTrue(any(item["module_id"] == "subscriptions" and item["code"] == "following" for item in payload["discussion_list_filters"]))
        self.assertTrue(any(item["code"] == "following" and item["route_path"] == "/following" for item in payload["discussion_list_filters"]))
        self.assertTrue(any(item["code"] == "my" and item["sidebar_visible"] is False for item in payload["discussion_list_filters"]))
        self.assertTrue(any(item["field"] == "can_start_discussion" for item in tags_module["resource_fields"]))
        self.assertTrue(any(item["resource"] == "tag" for item in payload["resource_definitions"]))
        self.assertTrue(any(item["resource"] == "search_discussion" for item in payload["resource_definitions"]))
        self.assertTrue(any(item["relationship"] == "user" and item["resource"] == "post" for item in payload["resource_relationships"]))
        self.assertTrue(any(item["resource"] == "search_post" and item["field"] == "user" for item in payload["resource_fields"]))

    @patch("apps.core.admin_api.build_runtime_dependency_summary")
    def test_modules_api_surfaces_runtime_dependency_attention_on_core_module(self, build_runtime_dependency_summary):
        build_runtime_dependency_summary.return_value = {
            "status": "attention",
            "label": "需关注",
            "issues": ["缓存后端：不可达", "队列 Broker：不可达"],
            "checks": [
                {
                    "key": "cache",
                    "label": "缓存后端",
                    "status": "unreachable",
                    "status_label": "不可达",
                    "available": False,
                    "message": "缓存后端主机不可达",
                    "recommended_action": "检查 Redis 缓存服务。",
                }
            ],
        }

        response = self.client.get(
            "/api/admin/modules",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        core_module = next(module for module in payload["modules"] if module["id"] == "core")
        self.assertEqual(core_module["health_status"], "attention")
        self.assertIn("缓存后端：不可达", core_module["health_issues"])
        self.assertEqual(core_module["runtime_dependency_summary"]["status"], "attention")
        self.assertGreaterEqual(payload["summary"]["runtime_dependency_attention_count"], 1)
        self.assertTrue(any(item["module_id"] == "notifications" for item in payload["user_preferences"]))
        self.assertTrue(any(item["module_id"] == "core" and item["code"] == "zh-CN" for item in payload["language_packs"]))

    @patch("apps.core.admin_api.build_runtime_dependency_summary")
    def test_modules_api_filters_disabled_extension_runtime_capabilities(self, build_runtime_dependency_summary):
        build_runtime_dependency_summary.return_value = {
            "status": "healthy",
            "label": "健康",
            "issues": [],
            "checks": [],
        }
        ExtensionInstallation.objects.create(
            extension_id="approval",
            version="1.0.0",
            source="builtin-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        response = self.client.get(
            "/api/admin/modules",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        approval_module = next(module for module in payload["modules"] if module["id"] == "approval")

        self.assertFalse(approval_module["enabled"])
        self.assertFalse(any(page["module_id"] == "approval" for page in payload["admin_pages"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["search_filters"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["user_preferences"]))

    def test_registry_permission_prefix_helper_returns_admin_moderation_codes(self):
        self.assertEqual(
            set(get_registry_permission_codes_by_prefix("admin.approval.")),
            {
                "admin.approval.view",
                "admin.approval.approve",
                "admin.approval.reject",
            },
        )
        self.assertEqual(
            set(get_registry_permission_codes_by_prefix("admin.flag.")),
            {
                "admin.flag.view",
                "admin.flag.resolve",
            },
        )

    def test_search_index_definition_limits_post_index_to_registered_searchable_types(self):
        post_index = next(definition for definition in SEARCH_INDEX_DEFINITIONS if definition["name"] == "posts_content_fts_idx")
        self.assertIn("WHERE type IN ('comment')", post_index["create"])


class AdminFlagManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-flag-mgr",
            email="admin-flag-mgr@example.com",
            password="password123",
        )
        self.author = User.objects.create_user(
            username="flag-author",
            email="flag-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reporter = User.objects.create_user(
            username="flag-reporter",
            email="flag-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = DiscussionService.create_discussion(
            title="Flag target",
            content="First",
            user=self.author,
        )
        post = PostService.create_post(
            discussion_id=discussion.id,
            content="这是一条被举报的帖子",
            user=self.author,
        )
        self.flag = PostFlag.objects.create(
            post=post,
            user=self.reporter,
            reason="违规内容",
            message="请管理员处理",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_list_and_resolve_flags(self):
        response = self.client.get(
            "/api/admin/flags",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["data"][0]["reason"], "违规内容")

        response = self.client.post(
            f"/api/admin/flags/{self.flag.id}/resolve",
            data=json.dumps({
                "status": "resolved",
                "resolution_note": "已联系发帖人并隐藏内容",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, "resolved")
        self.assertEqual(self.flag.resolution_note, "已联系发帖人并隐藏内容")
        self.assertEqual(self.flag.resolved_by_id, self.admin.id)
        audit_log = AuditLog.objects.get(action="admin.flag.resolve", target_id=self.flag.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "post_flag")
        self.assertEqual(audit_log.data["status"], "resolved")

    def test_admin_without_flag_permission_is_denied(self):
        with patch("apps.core.admin_api.UserService.has_forum_permission", return_value=False):
            list_response = self.client.get(
                "/api/admin/flags",
                **self.auth_header(),
            )
            self.assertEqual(list_response.status_code, 403, list_response.content)

            resolve_response = self.client.post(
                f"/api/admin/flags/{self.flag.id}/resolve",
                data=json.dumps({
                    "status": "resolved",
                    "resolution_note": "尝试越权处理举报",
                }),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(resolve_response.status_code, 403, resolve_response.content)


class AdminTagManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-tag-mgr",
            email="admin-tag@example.com",
            password="password123",
        )
        self.other_root_tag = Tag.objects.create(
            name="产品",
            slug="product",
            color="#e67e22",
            position=2,
        )
        self.parent_tag = Tag.objects.create(
            name="开发",
            slug="development",
            color="#4d698e",
            position=0,
        )
        self.child_tag = Tag.objects.create(
            name="后端",
            slug="backend",
            color="#0f766e",
            position=1,
            parent=self.parent_tag,
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_create_update_and_clear_tag_parent(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "接口设计",
                "slug": "api-design",
                "description": "讨论接口约定",
                "color": "#3c78d8",
                "icon": "fas fa-code",
                "parent_id": self.parent_tag.id,
                "position": 3,
                "is_hidden": True,
                "is_restricted": True,
                "view_scope": "members",
                "start_discussion_scope": "staff",
                "reply_scope": "members",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["slug"], "api-design")
        self.assertEqual(payload["parent_id"], self.parent_tag.id)
        self.assertEqual(payload["parent_name"], self.parent_tag.name)
        self.assertTrue(payload["is_hidden"])
        self.assertTrue(payload["is_restricted"])
        self.assertEqual(payload["view_scope"], "members")
        self.assertEqual(payload["start_discussion_scope"], "staff")
        self.assertEqual(payload["reply_scope"], "members")

        created_tag = Tag.objects.get(id=payload["id"])
        self.assertEqual(created_tag.parent_id, self.parent_tag.id)
        self.assertEqual(created_tag.view_scope, "members")

        response = self.client.put(
            f"/api/admin/tags/{created_tag.id}",
            data=json.dumps({
                "name": "接口规范",
                "slug": "api-guidelines",
                "parent_id": None,
                "position": 6,
                "is_hidden": False,
                "is_restricted": False,
                "view_scope": "public",
                "start_discussion_scope": "members",
                "reply_scope": "staff",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["name"], "接口规范")
        self.assertEqual(payload["slug"], "api-guidelines")
        self.assertIsNone(payload["parent_id"])
        self.assertIsNone(payload["parent_name"])
        self.assertFalse(payload["is_hidden"])
        self.assertFalse(payload["is_restricted"])
        self.assertEqual(payload["view_scope"], "public")
        self.assertEqual(payload["start_discussion_scope"], "members")
        self.assertEqual(payload["reply_scope"], "staff")

        created_tag.refresh_from_db()
        self.assertIsNone(created_tag.parent_id)
        self.assertEqual(created_tag.position, 6)
        self.assertEqual(created_tag.reply_scope, "staff")

    def test_admin_cannot_delete_tag_with_children(self):
        response = self.client.delete(
            f"/api/admin/tags/{self.parent_tag.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("子标签", response.json()["error"])

    def test_admin_cannot_create_grandchild_tag(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "Django ORM",
                "slug": "django-orm",
                "parent_id": self.child_tag.id,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("顶级标签", response.json()["error"])

    def test_admin_cannot_turn_parent_tag_with_children_into_child(self):
        response = self.client.put(
            f"/api/admin/tags/{self.parent_tag.id}",
            data=json.dumps({
                "parent_id": self.other_root_tag.id,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("已有子标签", response.json()["error"])

    def test_admin_cannot_set_posting_scopes_wider_than_view_scope(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "内部运营",
                "slug": "internal-ops",
                "view_scope": "staff",
                "start_discussion_scope": "members",
                "reply_scope": "staff",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("发帖权限不能比查看权限更宽松", response.json()["error"])

        response = self.client.put(
            f"/api/admin/tags/{self.parent_tag.id}",
            data=json.dumps({
                "view_scope": "members",
                "reply_scope": "public",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("回帖权限不能比查看权限更宽松", response.json()["error"])

    def test_admin_can_move_root_tag_up(self):
        response = self.client.post(
            f"/api/admin/tags/{self.other_root_tag.id}/move",
            data=json.dumps({"direction": "up"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["moved"])

        self.other_root_tag.refresh_from_db()
        self.parent_tag.refresh_from_db()
        self.assertEqual(self.other_root_tag.position, 0)
        self.assertEqual(self.parent_tag.position, 1)

    def test_admin_can_move_child_tag_within_same_parent(self):
        sibling_child = Tag.objects.create(
            name="前端",
            slug="frontend",
            color="#3c78d8",
            position=2,
            parent=self.parent_tag,
        )

        response = self.client.post(
            f"/api/admin/tags/{sibling_child.id}/move",
            data=json.dumps({"direction": "up"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["moved"])

        sibling_child.refresh_from_db()
        self.child_tag.refresh_from_db()
        self.parent_tag.refresh_from_db()

        self.assertEqual(sibling_child.position, 0)
        self.assertEqual(self.child_tag.position, 1)
        self.assertEqual(self.parent_tag.position, 0)

    @patch("apps.core.admin_api.TagService.dispatch_refresh_tag_stats")
    def test_admin_can_refresh_tag_stats(self, dispatch_refresh_tag_stats):
        dispatch_refresh_tag_stats.return_value = {
            "mode": "sync",
            "tag_ids": None,
            "message": "标签统计已同步刷新",
        }

        response = self.client.post(
            "/api/admin/tags/stats/refresh",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        dispatch_refresh_tag_stats.assert_called_once_with()
        self.assertEqual(response.json()["message"], "标签统计已同步刷新")
        audit_log = AuditLog.objects.get(action="admin.tag.refresh_stats")
        self.assertEqual(audit_log.target_type, "tag")
        self.assertEqual(audit_log.data["mode"], "sync")


class AdminApprovalQueueApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-approval-mgr",
            email="admin-approval@example.com",
            password="password123",
        )
        self.trusted_group = Group.objects.create(
            name="Trusted",
            name_singular="Trusted",
            name_plural="Trusted",
            color="#4d698e",
        )
        Permission.objects.create(group=self.trusted_group, permission="startDiscussion")
        Permission.objects.create(group=self.trusted_group, permission="startDiscussionWithoutApproval")
        Permission.objects.create(group=self.trusted_group, permission="replyWithoutApproval")

        self.author = User.objects.create_user(
            username="approval-author",
            email="approval-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.author.user_groups.add(self.trusted_group)
        self.pending_author = User.objects.create_user(
            username="approval-pending-author",
            email="approval-pending-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.replier = User.objects.create_user(
            username="approval-replier",
            email="approval-replier@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        self.pending_discussion = DiscussionService.create_discussion(
            title="待审核讨论",
            content="首帖需要审核",
            user=self.pending_author,
        )
        self.discussion = DiscussionService.create_discussion(
            title="已通过讨论",
            content="已发布首帖",
            user=self.author,
        )
        self.post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="这是一条待审核回复",
            user=self.replier,
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_list_and_approve_queue(self):
        response = self.client.get(
            "/api/admin/approval-queue",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 2)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
                data=json.dumps({"note": "讨论符合规范"}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.pending_discussion.refresh_from_db()
        self.assertEqual(self.pending_discussion.approval_status, "approved")
        approved_notification = Notification.objects.get(
            user=self.pending_author,
            type="discussionApproved",
            subject_id=self.pending_discussion.id,
        )
        self.assertEqual(approved_notification.from_user_id, self.admin.id)
        self.assertEqual(approved_notification.data["approval_note"], "讨论符合规范")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/admin/approval-queue/post/{self.post.id}/reject",
                data=json.dumps({"note": "回复质量不足"}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.post.refresh_from_db()
        self.assertEqual(self.post.approval_status, "rejected")
        self.assertIsNotNone(self.post.hidden_at)
        rejected_notification = Notification.objects.get(
            user=self.replier,
            type="postRejected",
            subject_id=self.post.id,
        )
        self.assertEqual(rejected_notification.from_user_id, self.admin.id)
        self.assertEqual(rejected_notification.data["approval_note"], "回复质量不足")

    def test_admin_can_bulk_process_approval_queue(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/admin/approval-queue/bulk/approve",
                data=json.dumps({
                    "note": "批量审核通过",
                    "items": [
                        {"type": "discussion", "id": self.pending_discussion.id},
                        {"type": "post", "id": self.post.id},
                    ],
                }),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["processed_count"], 2)
        self.assertEqual(payload["action"], "approve")
        self.assertEqual(len(payload["data"]), 2)

        self.pending_discussion.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.pending_discussion.approval_status, "approved")
        self.assertEqual(self.post.approval_status, "approved")

        discussion_notification = Notification.objects.get(
            user=self.pending_author,
            type="discussionApproved",
            subject_id=self.pending_discussion.id,
        )
        post_notification = Notification.objects.get(
            user=self.replier,
            type="postApproved",
            subject_id=self.post.id,
        )
        self.assertEqual(discussion_notification.data["approval_note"], "批量审核通过")
        self.assertEqual(post_notification.data["approval_note"], "批量审核通过")

    def test_bulk_approval_queue_rejects_invalid_payload(self):
        response = self.client.post(
            "/api/admin/approval-queue/bulk/reject",
            data=json.dumps({"note": "批量拒绝", "items": []}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("请至少选择一条待审核内容", response.json()["error"])

    def test_admin_without_approval_permissions_is_denied_for_bulk_processing(self):
        with patch("apps.core.admin_api.UserService.has_forum_permission", return_value=False):
            response = self.client.post(
                "/api/admin/approval-queue/bulk/approve",
                data=json.dumps({
                    "note": "尝试越权批量审核",
                    "items": [{"type": "discussion", "id": self.pending_discussion.id}],
                }),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(response.status_code, 403, response.content)

    def test_non_staff_cannot_access_or_process_approval_queue(self):
        member_token = RefreshToken.for_user(self.pending_author).access_token
        auth = {"HTTP_AUTHORIZATION": f"Bearer {member_token}"}

        list_response = self.client.get(
            "/api/admin/approval-queue",
            **auth,
        )
        self.assertEqual(list_response.status_code, 403, list_response.content)

        approve_response = self.client.post(
            f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
            data=json.dumps({"note": "尝试越权审核"}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(approve_response.status_code, 403, approve_response.content)

        reject_post_response = self.client.post(
            f"/api/admin/approval-queue/post/{self.post.id}/reject",
            data=json.dumps({"note": "尝试越权拒绝回复"}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(reject_post_response.status_code, 403, reject_post_response.content)

        bulk_response = self.client.post(
            "/api/admin/approval-queue/bulk/approve",
            data=json.dumps({
                "note": "尝试越权批量审核",
                "items": [{"type": "discussion", "id": self.pending_discussion.id}],
            }),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(bulk_response.status_code, 403, bulk_response.content)

    def test_admin_without_approval_permissions_is_denied(self):
        with patch("apps.core.admin_api.UserService.has_forum_permission", return_value=False):
            list_response = self.client.get(
                "/api/admin/approval-queue",
                **self.auth_header(),
            )
            self.assertEqual(list_response.status_code, 403, list_response.content)

            approve_response = self.client.post(
                f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
                data=json.dumps({"note": "尝试越权审核"}),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(approve_response.status_code, 403, approve_response.content)

            reject_post_response = self.client.post(
                f"/api/admin/approval-queue/post/{self.post.id}/reject",
                data=json.dumps({"note": "尝试越权拒绝回复"}),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(reject_post_response.status_code, 403, reject_post_response.content)


class ProductionRuntimeCheckTests(TestCase):
    @override_settings(
        DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-runtime-check-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "short-jwt-secret"},
        FRONTEND_URL="",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    def test_production_runtime_checks_report_critical_risks(self, _is_test_process):
        messages = run_checks(tags=["bias_runtime"])
        message_ids = {message.id for message in messages}

        self.assertIn("bias.django-secret-placeholder", message_ids)
        self.assertIn("bias.jwt-secret-too-short", message_ids)
        self.assertIn("bias.redis-disabled-production", message_ids)
        self.assertIn("bias.frontend-url-missing-production", message_ids)
        self.assertIn("bias.email-backend-development-production", message_ids)

    @override_settings(DEBUG=False)
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    @patch("apps.core.startup_guard.run_checks")
    def test_startup_guard_blocks_production_startup_when_critical_checks_exist(
        self,
        run_checks_mock,
        _is_test_process,
    ):
        from django.core.checks import Critical, Warning
        from apps.core.startup_guard import enforce_production_runtime_checks

        run_checks_mock.return_value = [
            Warning("warning", id="bias.warning-example"),
            Critical("critical failure", hint="fix it", id="bias.critical-example"),
        ]

        with self.assertRaises(ImproperlyConfigured) as captured:
            enforce_production_runtime_checks()

        message = str(captured.exception)
        self.assertIn("bias.critical-example", message)
        self.assertIn("critical failure", message)
        self.assertIn("fix it", message)

    @override_settings(DEBUG=True)
    @patch("apps.core.startup_guard.run_checks")
    def test_startup_guard_skips_non_production_runtime(self, run_checks_mock):
        from apps.core.startup_guard import enforce_production_runtime_checks

        enforce_production_runtime_checks()

        run_checks_mock.assert_not_called()

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_enforces_production_runtime_checks(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        manage.main()

        enforce_runtime_checks_mock.assert_called_once_with()
        execute_from_command_line_mock.assert_called_once_with(sys.argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_validate_extensions(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "validate_extensions"]
        with patch.object(sys, "argv", argv):
            manage.main()

        enforce_runtime_checks_mock.assert_not_called()
        execute_from_command_line_mock.assert_called_once_with(argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_create_extension(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "create_extension", "demo-tools"]
        with patch.object(sys, "argv", argv):
            manage.main()

        enforce_runtime_checks_mock.assert_not_called()
        execute_from_command_line_mock.assert_called_once_with(argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    def test_celery_module_enforces_production_runtime_checks(self, enforce_runtime_checks_mock):
        import config.celery as celery_module

        importlib.reload(celery_module)
        celery_module._enforce_celery_runtime_checks()

        enforce_runtime_checks_mock.assert_called_once_with()
