import importlib
import json
import os
from pathlib import Path
import shutil
from io import StringIO
from subprocess import CompletedProcess
import sys
from types import ModuleType, SimpleNamespace
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
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import clear_url_caches, path
from django.db import connection
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from unittest.mock import Mock, patch

from apps.core.domain_events import DomainEventBus, get_forum_event_bus
from apps.core.extensions.backend import run_extension_backend_hook
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.registry import ExtensionRegistry
from apps.core.extensions import ApiResourceExtender, ConditionalExtender, PostEventExtender, ResourceExtender, SearchDriverExtender, get_extension_registry
from apps.core.extensions.extenders import ValidatorExtender, MailExtender
from apps.core.extensions.bootstrap import (
    bootstrap_extension_application,
    build_extension_application,
    get_extension_application,
    reset_extension_application_bootstrap_state,
)
from apps.core.extensions.application import ExtensionApplication
from apps.core.extensions.assembly_service import get_enabled_extension_assemblies
from apps.core.extensions.runtime_probe import inspect_extension_runtime
from apps.core.extensions.extension_runtime import Extension
from apps.core.extensions.frontend_runtime_service import (
    bootstrap_extension_frontend_runtime,
)
from apps.core.extensions.frontend_compiler import (
    build_extension_frontend_output_manifest,
    copy_frontend_dist_to_static,
    get_extension_frontend_import_map_path,
    get_extension_frontend_output_manifest_path,
    get_frontend_vite_manifest_path,
    get_published_frontend_root,
    write_extension_frontend_import_map,
)
from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners
from apps.core.extensions.lifecycle import reset_extension_runtime_state
from apps.core.extensions.settings_runtime_service import (
    get_enabled_extension_settings_definitions,
    get_extension_settings_definition,
)
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionEventListenerDefinition,
    ExtensionManifest,
    ExtensionResourceDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceRelationshipDefinition,
)
from apps.core.extensions.runtime_service import get_enabled_extension_runtime_entries
from apps.core.extensions.recovery import serialize_extension_recovery_state
from apps.core.extensions.validation import (
    inspect_backend_entry,
    inspect_frontend_admin_entry,
    inspect_frontend_forum_entry,
    resolve_bias_version_compatibility,
    validate_extension_manifests,
    validate_extension_manifests_with_available_ids,
)
from apps.core.extension_diagnostics import classify_extension_diagnostics, summarize_extension_delivery
from apps.core.extension_service import ExtensionService
from apps.core.middleware import ExtensionRequestMiddleware
from apps.core.api_runtime import build_api_application
from apps.core.forum_events import (
    DiscussionCreatedEvent,
    UserSuspendedEvent,
    UserUnsuspendedEvent,
)
from apps.core.forum_resources_post_events import resolve_post_event_data
from apps.core.forum_resources_users import serialize_user_payload, serialize_user_summary
from apps.core.forum_registry import (
    ForumRegistry,
    get_forum_registry,
    get_registry_permission_codes_by_prefix,
    get_registry_staff_managed_admin_permission_codes,
)
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionSortDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)
from apps.core.resource_registry import get_resource_registry
from apps.core.resource_registry import (
    ResourceEndpointDefinition,
    ResourceDefinition,
    ResourceFilterDefinition,
    ResourceFieldDefinition,
    ResourceFieldMutatorDefinition,
    ResourceRelationshipDefinition,
    ResourceRegistry,
    ResourceSortDefinition,
)
from apps.core.resource_objects import (
    DatabaseResource,
    Resource,
    ResourceEndpoint,
    ResourceFilter,
    ResourceField,
    ResourceSearchCriteria,
    ResourceRelationship,
    ResourceSearchResults,
    ResourceSort,
)
from apps.core.resource_dispatcher import dispatch_resource_endpoint
from apps.core.resource_routes import build_resource_route_definitions
from apps.core.resource_search import ResourceSearchFilter, ResourceSearchManager, ResourceSearchState
from apps.core.resource_serializer import ResourceSerializer
from apps.core.resource_context import ResourceContext
from apps.core.resource_validation import ResourceValidationError, ResourceValidator, ResourceValidatorFactory
from apps.core.bootstrap_config import load_site_bootstrap, read_site_config
from apps.core.models import AuditLog, ExtensionInstallation, Setting
from apps.core.file_service import FileUploadService
from apps.core.online_service import OnlineUserService
from apps.core.release import build_git_command, ensure_release_versions_aligned
from apps.core.search_index_service import get_search_index_definitions
from apps.core.settings_service import clear_runtime_setting_caches, get_public_forum_settings, get_setting_group
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
from apps.posts.models import Post
from apps.posts.services import PostService
from extensions.likes.backend.services import can_like_post
from extensions.notifications.backend.models import Notification
from extensions.tags.backend.events import DiscussionTagStatsRefreshEvent, TagStatsRefreshRequestedEvent
from extensions.tags.backend.models import Tag
from apps.users.models import Group, Permission, User
from apps.users.services import UserService


def discussion_tags_payload(tag_ids):
    return {
        "data": {
            "relationships": {
                "tags": {
                    "data": [
                        {"type": "tag", "id": str(tag_id)}
                        for tag_id in tag_ids
                    ],
                },
            },
        },
    }


def resolve_test_username(instance, context):
    return instance.username


def make_workspace_temp_dir() -> Path:
    path = Path.cwd() / f"tmp-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class DomainEventBusTests(TestCase):
    def test_dispatches_registered_event_handlers(self):
        bus = DomainEventBus()
        received = []

        def handle_created(event):
            received.append((event.discussion_id, event.actor_user_id, event.is_approved))

        bus.register(DiscussionCreatedEvent, handle_created)
        bus.dispatch(
            DiscussionCreatedEvent(
                discussion_id=7,
                actor_user_id=3,
                is_approved=True,
            )
        )

        self.assertEqual(received, [(7, 3, True)])

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


@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
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
                "operations_profile": {
                    "kicker": "Sample Runtime",
                    "title": "Sample Operations",
                    "highlights": ["示例能力"],
                    "focus_panels": [
                        {
                            "key": "notification_types",
                            "title": "示例通知",
                        }
                    ],
                    "recommended_action_keys": ["details"],
                    "next_steps": ["继续补齐示例操作页。"],
                },
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
            self.assertEqual(results[0].manifest.operations_profile["kicker"], "Sample Runtime")
            self.assertEqual(results[0].manifest.operations_profile["focus_panels"][0]["key"], "notification_types")
            self.assertEqual(results[0].manifest.admin_actions[0].key, "details")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_schema[0].key, "theme")
            self.assertEqual(results[0].manifest.migration_namespace, "")
            self.assertEqual(results[0].manifest.compatibility.api_version, "1.0")
            self.assertEqual(results[0].manifest.compatibility.api_stability, "experimental")
            self.assertEqual(results[0].manifest.distribution.channel, "private")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


    def test_loader_merges_forum_setting_exposure_from_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import SettingsExtender\n"
                "from apps.core.extensions.backend import _build_setting_field_definition\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        SettingsExtender(\n"
                "            fields=(\n"
                "                _build_setting_field_definition({'key': 'cdn_url', 'label': 'CDN', 'type': 'text', 'default': ''}),\n"
                "            ),\n"
                "            expose_to_forum=('cdn_url',),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.forum_settings_keys, ("cdn_url",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_forum_capabilities_from_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ForumCapabilitiesExtender, NotificationsExtender\n"
                "from apps.core.forum_registry_types import NotificationTypeDefinition, UserPreferenceDefinition, SearchFilterDefinition\n"
                "\n"
                "def _parse_author(token):\n"
                "    if token.startswith('author:'):\n"
                "        return token.split(':', 1)[1]\n"
                "    return None\n"
                "\n"
                "def _apply(queryset, value, context):\n"
                "    return queryset\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        NotificationsExtender(\n"
                "            notification_types=(\n"
                "                NotificationTypeDefinition(code='alphaPing', label='Alpha Ping', module_id='alpha-tools'),\n"
                "            ),\n"
                "            user_preferences=(\n"
                "                UserPreferenceDefinition(key='notify_alpha_ping', label='Alpha Ping', module_id='alpha-tools', default_value=True),\n"
                "            ),\n"
                "        ),\n"
                "        ForumCapabilitiesExtender(\n"
                "            search_filters=(\n"
                "                SearchFilterDefinition(code='author', label='作者', module_id='alpha-tools', target='discussion', parser=_parse_author, applier=_apply, syntax='author:<username>'),\n"
                "            ),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.notification_types[0].code, "alphaPing")
            self.assertEqual(result.user_preferences[0].key, "notify_alpha_ping")
            self.assertEqual(result.search_filters[0].syntax, "author:<username>")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_language_pack_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-lang"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-lang",
                "name": "Alpha Language",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_lang.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LanguagePackExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        LanguagePackExtender(\n"
                "            code='en-US',\n"
                "            label='English',\n"
                "            native_label='English',\n"
                "            path='extensions/alpha-lang/locale',\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.language_packs[0].code, "en-US")
            self.assertEqual(result.language_packs[0].module_id, "alpha-lang")
            self.assertEqual(result.locale_paths, ("extensions/alpha-lang/locale",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_admin_surface_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AdminSurfaceExtender\n"
                "from apps.core.forum_registry_types import PermissionDefinition, AdminPageDefinition\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        AdminSurfaceExtender(\n"
                "            permissions=(\n"
                "                PermissionDefinition(code='alpha.manage', label='管理 Alpha', section='admin', section_label='后台', module_id='alpha-tools'),\n"
                "            ),\n"
                "            admin_pages=(\n"
                "                AdminPageDefinition(path='/admin/alpha-tools', label='Alpha Tools', icon='fas fa-toolbox', module_id='alpha-tools'),\n"
                "            ),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.permissions[0].code, "alpha.manage")
            self.assertEqual(result.admin_pages[0].path, "/admin/alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_extenders_into_manifest(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import SettingsExtender, RuntimeActionsExtender\n"
                "from apps.core.extensions.backend import _build_setting_field_definition, _build_runtime_action_definition\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        SettingsExtender(fields=(\n"
                "            _build_setting_field_definition({'key': 'cdn_url', 'label': 'CDN', 'type': 'text', 'default': ''}),\n"
                "        )),\n"
                "        RuntimeActionsExtender(actions=(\n"
                "            _build_runtime_action_definition({'key': 'rebuild', 'label': '刷新', 'hook': 'run_rebuild_cache'}),\n"
                "        )),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            results = loader.discover()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].manifest.settings_schema[0].key, "cdn_url")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_pages, ("/admin/extensions/alpha-tools/settings",))
            self.assertEqual(results[0].settings_pages, ("/admin/extensions/alpha-tools/settings",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_frontend_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(\n"
                "            admin_entry='extensions/alpha-tools/frontend/admin/index.js',\n"
                "            forum_entry='extensions/alpha-tools/frontend/forum/index.js',\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.frontend_admin_entry, "extensions/alpha-tools/frontend/admin/index.js")
            self.assertEqual(result.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/index.js")
            self.assertEqual(result.manifest.frontend_admin_entry, "extensions/alpha-tools/frontend/admin/index.js")
            self.assertEqual(result.manifest.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/index.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_api_route_mounts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from ninja import Router\n"
                "from apps.core.extensions import ApiRoutesExtender\n"
                "\n"
                "router = Router()\n"
                "\n"
                "@router.get('/ping')\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ApiRoutesExtender(mounts=(('/ext/alpha-tools', router),), tags=('Alpha',)),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            mounts = application.get_route_mounts()

            self.assertEqual(len(mounts), 1)
            self.assertEqual(mounts[0].prefix, "/ext/alpha-tools")
            self.assertEqual(tuple(mounts[0].tags), ("Alpha",))
            runtime_view = application.get_runtime_view("alpha-tools")
            self.assertEqual(runtime_view.lifecycle_phase_keys, ("register", "boot", "ready"))
            self.assertEqual(runtime_view.extender_keys, ("ApiRoutesExtender",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_extenders_are_flattened_from_nested_extend_files(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(admin_entry='extensions/alpha/admin.js'),\n"
                "        [None, FrontendExtender(forum_entry='extensions/alpha/forum.js')],\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(runtime_view.frontend_admin_entry, "extensions/alpha/admin.js")
            self.assertEqual(runtime_view.frontend_forum_entry, "extensions/alpha/forum.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_named_api_routes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import RoutesExtender\n"
                "\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "\n"
                "def replacement(request):\n"
                "    return {'ok': 'replacement'}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RoutesExtender('api', tags=('Alpha',)).get('/ext/alpha-tools/ping', 'alpha.ping', ping),\n"
                "        RoutesExtender('api').remove('alpha.old').get('/ext/alpha-tools/replacement', 'alpha.old', replacement),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            named_routes = application.get_named_routes(app_name="api")

            self.assertEqual([route.name for route in named_routes], ["alpha.ping", "alpha.old"])
            self.assertEqual(named_routes[0].method, "GET")
            self.assertEqual(named_routes[0].tags, ("Alpha",))
            self.assertEqual(application.get_runtime_view("alpha-tools").named_routes[0].name, "alpha.ping")

            api = application.make("api.application")
            paths = {item[0] for item in api._routers}
            self.assertIn("/ext/alpha-tools/ping", paths)
            self.assertIn("/ext/alpha-tools/replacement", paths)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_forum_settings_exposes_extension_document_runtime(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(forum_entry='forum.js')\n"
                "            .preload({'href': '/static/alpha.css', 'as': 'style'})\n"
                "            .extra_document_attributes({'data-alpha': '1'})\n"
                "            .title('AlphaTitle')\n"
                "            .content('alpha.content', priority=120)\n"
                "            .content('alpha.late_content', priority=20),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            with patch("apps.core.extensions.frontend_runtime_service.get_extension_host", return_value=application):
                clear_runtime_setting_caches()
                payload = get_public_forum_settings()

            document = payload["extension_document"]
            self.assertEqual(document["preloads"], [{"href": "/static/alpha.css", "as": "style"}])
            self.assertEqual(document["document_attributes"], {"data-alpha": "1"})
            self.assertEqual(document["title_drivers"], [{"extension_id": "alpha-tools", "driver": "AlphaTitle"}])
            self.assertEqual(document["content_callbacks"], [
                {"extension_id": "alpha-tools", "callback": "alpha.content", "priority": 120},
                {"extension_id": "alpha-tools", "callback": "alpha.late_content", "priority": 20},
            ])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            clear_runtime_setting_caches()

    def test_extension_sources_do_not_import_replaced_private_runtime_helpers(self):
        forbidden_helpers = (
            "_broadcast_discussion_event",
            "_build_realtime_included_payload",
            "_create_timeline_from_builder",
            "_make_timeline_context",
        )
        extension_root = Path.cwd() / "extensions"
        offenders = []
        for path in extension_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for helper in forbidden_helpers:
                if helper in content:
                    offenders.append(f"{path.relative_to(Path.cwd())}: {helper}")

        self.assertEqual(offenders, [])

    def test_backend_entry_namespace_controls_loaded_file(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            alternate_dir = manifest_dir / "alternate"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            alternate_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.alternate.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/wrong.js')]\n",
                encoding="utf-8",
            )
            (alternate_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/right.js')]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(extensions_dir)
            result = loader.discover()[0]

            self.assertEqual(result.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/right.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.extensions.manifest.metadata.distributions")
    def test_manifest_loader_discovers_python_distribution_extensions(self, distributions_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=True):
                from apps.core.extensions import manifest as manifest_module

                manifest_module._distribution_manifest_cache = None
                package_dir = Path(temp_dir) / "site-packages" / "alpha_tools" / "bias_extension"
                package_dir.mkdir(parents=True, exist_ok=False)
                manifest_path = package_dir / "extension.json"
                manifest_path.write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.2.3",
                    "backend_entry": "alpha_tools.ext",
                }, ensure_ascii=False), encoding="utf-8")

                class DemoDistribution:
                    version = "1.2.3"
                    files = ("alpha_tools/bias_extension/extension.json",)
                    metadata = {"Name": "alpha-tools"}

                    def locate_file(self, file):
                        return Path(temp_dir) / "site-packages" / str(file)

                distributions_mock.return_value = [DemoDistribution()]
                loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
                manifests = loader.discover_manifests()

            self.assertEqual(len(manifests), 1)
            self.assertEqual(manifests[0].id, "alpha-tools")
            self.assertEqual(manifests[0].source, "python-package")
            self.assertEqual(manifests[0].extra["python_distribution"]["name"], "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_runs_extension_service_provider(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ServiceProviderExtender\n"
                "\n"
                "def provide(app):\n"
                "    return {'has_app': app.has('app'), 'ready': True}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ServiceProviderExtender(key='alpha.provider', provider=provide),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)

            self.assertEqual(application.get_service("alpha.provider"), {
                "has_app": True,
                "ready": True,
            })
            runtime_view = application.get_runtime_view("alpha-tools")
            self.assertIsNotNone(runtime_view)
            self.assertIn("alpha.provider", runtime_view.service_providers)
            compatibility_record = next(item for item in application.get_records() if item.extension_id == "alpha-tools")
            self.assertIn("alpha.provider", compatibility_record.service_providers)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_runs_host_service_provider_class(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ServiceProviderExtender\n"
                "\n"
                "class DemoProvider:\n"
                "    def register(self, app):\n"
                "        app.instance('alpha.provider', {'registered': app.has('app')})\n"
                "\n"
                "    def boot(self, app):\n"
                "        app.instance('alpha.provider.booted', {'booted': True})\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ServiceProviderExtender(key='alpha.provider', provider=DemoProvider),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)

            self.assertEqual(application.get_service("alpha.provider"), {
                "registered": True,
            })
            self.assertEqual(application.get_service("alpha.provider.booted"), {
                "booted": True,
            })
            self.assertEqual(application.get_service_provider_keys(extension_id="alpha-tools"), ["alpha.provider"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_supports_aliases_tags_and_bias_resource_contract(self):
        app = ExtensionApplication()
        app.instance("alpha.service", {"ready": True})
        app.alias("alpha.service", "alpha.alias")
        app.tag(["alpha.alias"], "alpha.services")

        self.assertEqual(app.make("alpha.alias"), {"ready": True})
        self.assertEqual(app.tagged("alpha.services"), [{"ready": True}])
        self.assertEqual(app.make("bias.api.resources"), [])

    def test_view_extender_registers_template_namespaces(self):
        from django.template.loader import render_to_string

        from apps.core.extensions import ViewExtender
        from apps.core.extensions.template_loader import clear_extension_template_caches

        temp_dir = make_workspace_temp_dir()
        extension_dir = Path(temp_dir) / "extensions" / "alpha-tools"
        templates_dir = extension_dir / "templates"
        overrides_dir = extension_dir / "overrides"
        prepend_dir = extension_dir / "prepend"
        templates_dir.mkdir(parents=True)
        overrides_dir.mkdir(parents=True)
        prepend_dir.mkdir(parents=True)
        (templates_dir / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
        (prepend_dir / "hello.html").write_text("Override {{ name }}", encoding="utf-8")

        app = ExtensionApplication()
        app.get_or_create_runtime_view("alpha-tools", path=str(extension_dir))
        extension = SimpleNamespace(extension_id="alpha-tools")

        try:
            ViewExtender() \
                .namespace("alpha", "templates", "overrides", description="Alpha views") \
                .extend_namespace("alpha", "prepend") \
                .extend(app, extension)
            app.make("views")

            namespaces = app.views.get_namespaces(extension_id="alpha-tools")
            runtime_view = app.get_runtime_view("alpha-tools")

            self.assertEqual(len(namespaces), 2)
            self.assertEqual(namespaces[0].namespace, "alpha")
            self.assertEqual(namespaces[0].hints, (str(prepend_dir.resolve()),))
            self.assertEqual(namespaces[0].module_id, "alpha-tools")
            self.assertTrue(namespaces[0].prepend)
            self.assertEqual(namespaces[1].hints, (str(templates_dir.resolve()), str(overrides_dir.resolve())))
            self.assertEqual(runtime_view.view_namespaces, tuple(namespaces))
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                clear_extension_template_caches()
                self.assertEqual(app.views.render("alpha::hello.html", {"name": "Bias"}), "Override Bias")
                self.assertEqual(render_to_string("alpha::hello.html", {"name": "Bias"}), "Override Bias")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_registers_provider_through_app_register(self):
        app = ExtensionApplication()

        class DemoProvider:
            def register(self, host):
                host.instance("demo.provider.value", {"registered": True})

            def boot(self, host):
                host.instance("demo.provider.booted", {"booted": True})

        key = app.register(DemoProvider, key="demo.provider", extension_id="alpha-tools")
        app.providers.boot()

        self.assertEqual(key, "demo.provider")
        self.assertEqual(app.make("demo.provider.value"), {"registered": True})
        self.assertEqual(app.make("demo.provider.booted"), {"booted": True})

    def test_validator_and_mail_extenders_register_runtime_definitions(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def validate_title(value, context):
            return value

        def build_mail(message, context):
            return message

        ValidatorExtender().validator("title", "discussion", validate_title).extend(app, extension)
        MailExtender().driver("digest", build_mail).extend(app, extension)

        validators = app.make("validators").get_definitions(extension_id="alpha-tools")
        mailers = app.make("mail").get_definitions(extension_id="alpha-tools")
        runtime_view = app.get_runtime_view("alpha-tools")

        self.assertEqual(validators[0].key, "title")
        self.assertEqual(validators[0].target, "discussion")
        self.assertEqual(validators[0].module_id, "alpha-tools")
        self.assertEqual(mailers[0].key, "digest")
        self.assertEqual(mailers[0].module_id, "alpha-tools")
        self.assertEqual(runtime_view.validators, tuple(validators))
        self.assertEqual(runtime_view.mailers, tuple(mailers))

    def test_mail_extender_contributes_runtime_driver_definitions(self):
        from apps.core.mail_drivers import get_driver_definitions, normalize_mail_driver

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        MailExtender().driver(
            "custom",
            lambda definition, context: {
                "label": "Custom",
                "description": "Runtime mail driver",
                "fields": [{"key": "mail_custom_token", "label": "Token"}],
            },
        ).extend(app, extension)
        app.make("mail")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            definitions = get_driver_definitions()
            self.assertEqual(normalize_mail_driver("custom"), "custom")

        self.assertEqual(definitions["custom"]["label"], "Custom")
        self.assertEqual(definitions["custom"]["fields"][0]["key"], "mail_custom_token")

    def test_mail_extender_driver_can_send_runtime_message(self):
        from apps.core.mail_drivers import send_with_extension_mail_driver

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        sent = []

        def send_digest(message, context):
            sent.append((message["subject"], context["source"]))
            return True

        MailExtender().driver("digest", send_digest).extend(app, extension)
        app.make("mail")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            result = send_with_extension_mail_driver("digest", {"subject": "Digest"}, {"source": "test"})

        self.assertEqual(result, True)
        self.assertEqual(sent, [("Digest", "test")])

    def test_system_hook_extenders_register_runtime_hooks(self):
        from apps.core.extensions import (
            AuthExtender,
            ConsoleExtender,
            ErrorHandlingExtender,
            FilesystemExtender,
            SessionExtender,
            ThemeExtender,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        ErrorHandlingExtender().hook("report", lambda payload, context: "error").extend(app, extension)
        AuthExtender().hook("provider", lambda payload, context: "auth").extend(app, extension)
        FilesystemExtender().hook("driver", lambda payload, context: "fs").extend(app, extension)
        ConsoleExtender().hook("command", lambda payload, context: "console").extend(app, extension)
        SessionExtender().hook("session", lambda payload, context: "session").extend(app, extension)
        ThemeExtender().hook("theme", lambda payload, context: "theme").extend(app, extension)

        self.assertEqual(app.make("error.handling").run("report")[0], "error")
        self.assertEqual(app.make("auth").run("provider")[0], "auth")
        self.assertEqual(app.make("filesystem").run("driver")[0], "fs")
        self.assertEqual(app.make("console").run("command")[0], "console")
        self.assertEqual(app.make("session").run("session")[0], "session")
        self.assertEqual(app.make("theme").run("theme")[0], "theme")
        runtime_view = app.get_runtime_view("alpha-tools")
        self.assertEqual(runtime_view.error_handlers[0].module_id, "alpha-tools")

    def test_signal_extender_registers_and_clears_runtime_receivers(self):
        from django.dispatch import Signal
        from apps.core.extensions import SignalExtender
        from apps.core.extensions.signal_runtime import (
            disconnect_runtime_signal_receivers,
            get_runtime_signal_connections,
        )

        signal = Signal()
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs["value"])

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        try:
            SignalExtender().connect(
                signal,
                receiver,
                sender=ExtensionApplication,
                dispatch_uid="alpha.signal.receiver",
            ).extend(app, extension)
            app.make("signals")

            signal.send(sender=ExtensionApplication, value=1)

            runtime_view = app.get_runtime_view("alpha-tools")
            self.assertEqual(received, [1])
            self.assertEqual(runtime_view.signal_handlers[0].module_id, "alpha-tools")
            self.assertEqual(get_runtime_signal_connections(extension_id="alpha-tools")[0].dispatch_uid, "alpha.signal.receiver")

            disconnect_runtime_signal_receivers()
            signal.send(sender=ExtensionApplication, value=2)
            self.assertEqual(received, [1])
        finally:
            disconnect_runtime_signal_receivers()

    def test_signal_proxy_reset_disconnects_only_lazy_proxy_receivers(self):
        from django.dispatch import Signal
        from apps.core.extensions.signal_bootstrap import reset_extension_signal_proxy_bootstrap
        from apps.core.extensions.signal_runtime import (
            connect_runtime_signal,
            connect_runtime_signal_proxy,
            disconnect_runtime_signal_receivers,
            get_runtime_signal_connections,
        )
        from apps.core.extensions.types import ExtensionSignalDefinition

        proxy_signal = Signal()
        runtime_signal = Signal()
        received = []

        def proxy_receiver(sender=None, **kwargs):
            received.append(("proxy", kwargs["value"]))

        def runtime_receiver(sender=None, **kwargs):
            received.append(("runtime", kwargs["value"]))

        try:
            connect_runtime_signal_proxy(
                "alpha-tools",
                ExtensionSignalDefinition(
                    signal=proxy_signal,
                    receiver=proxy_receiver,
                    dispatch_uid="alpha.proxy.receiver",
                ),
                enabled_by_default=True,
            )
            connect_runtime_signal(
                "alpha-tools",
                ExtensionSignalDefinition(
                    signal=runtime_signal,
                    receiver=runtime_receiver,
                    dispatch_uid="alpha.runtime.receiver",
                ),
            )

            self.assertEqual(len(get_runtime_signal_connections(extension_id="alpha-tools")), 2)

            reset_extension_signal_proxy_bootstrap()
            proxy_signal.send(sender=ExtensionApplication, value=1)
            runtime_signal.send(sender=ExtensionApplication, value=2)

            self.assertEqual(received, [("runtime", 2)])
            remaining = get_runtime_signal_connections(extension_id="alpha-tools")
            self.assertEqual([item.dispatch_uid for item in remaining], ["alpha.runtime.receiver"])
        finally:
            disconnect_runtime_signal_receivers()

    def test_model_extender_declares_owned_models(self):
        from apps.core.extensions import ModelExtender

        class DemoOwnedModel:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        ModelExtender().owns(
            DemoOwnedModel,
            description="Alpha owns this model.",
        ).extend(app, extension)
        app.make("models")

        runtime_view = app.get_runtime_view("alpha-tools")
        owned = app.models.get_owned_models(extension_id="alpha-tools")

        self.assertEqual(runtime_view.model_definitions[0].kind, "owner")
        self.assertEqual(runtime_view.model_definitions[0].model, DemoOwnedModel)
        self.assertEqual(owned[0].description, "Alpha owns this model.")
        self.assertEqual(app.models.get_model_owner(DemoOwnedModel), "alpha-tools")

    def test_post_event_extender_registers_event_data_resolver(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def resolve_alpha_event(post, context):
            return {
                "kind": post.type,
                "actor": context["user"],
            }

        PostEventExtender().type(
            "alphaEvent",
            resolve_alpha_event,
            description="Alpha event data.",
        ).types(
            ("betaEvent",),
            resolve_alpha_event,
            description="Beta event data.",
        ).extend(app, extension)

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            event_data = resolve_post_event_data(
                SimpleNamespace(type="alphaEvent", content=""),
                {"user": "tester"},
            )

        self.assertEqual(event_data, {"kind": "alphaEvent", "actor": "tester"})
        self.assertEqual(app.make("post.events").get_definitions(post_type="alphaEvent")[0].module_id, "alpha-tools")
        self.assertEqual(app.make("post.events").get_definitions(post_type="betaEvent")[0].module_id, "alpha-tools")

    def test_conditional_extender_supports_disabled_setting_and_class_callbacks(self):
        app = ExtensionApplication()
        app._booted_extensions["beta-tools"] = SimpleNamespace(runtime=SimpleNamespace(enabled=False))
        extension = SimpleNamespace(extension_id="alpha-tools")
        Setting.objects.create(key="alpha.enabled", value="1")

        class ConditionalFields:
            def __call__(self):
                return ResourceExtender(fields=(
                    ResourceFieldDefinition(
                        resource="forum",
                        field="class_conditional",
                        module_id="",
                        resolver=lambda model, context: True,
                    ),
                ))

        ConditionalExtender() \
            .when_extension_disabled("beta-tools", lambda: [
                ResourceExtender(fields=(
                    ResourceFieldDefinition(
                        resource="forum",
                        field="disabled_conditional",
                        module_id="",
                        resolver=lambda model, context: True,
                    ),
                )),
                [
                    None,
                    ResourceExtender(fields=(
                        ResourceFieldDefinition(
                            resource="forum",
                            field="nested_conditional",
                            module_id="",
                            resolver=lambda model, context: True,
                        ),
                    )),
                ],
            ]) \
            .when_setting("alpha.enabled", "1", ConditionalFields) \
            .extend(app, extension)

        fields = {item.field: item for item in app.make("resources").get_fields("forum")}

        self.assertIn("disabled_conditional", fields)
        self.assertIn("nested_conditional", fields)
        self.assertIn("class_conditional", fields)
        self.assertEqual(fields["disabled_conditional"].module_id, "alpha-tools")
        self.assertEqual(fields["nested_conditional"].module_id, "alpha-tools")
        self.assertEqual(fields["class_conditional"].module_id, "alpha-tools")

    def test_system_hook_runtime_services_drive_error_filesystem_and_console(self):
        from apps.core.extensions import ConsoleExtender, ErrorHandlingExtender, FilesystemExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_error_statuses,
            list_runtime_console_commands,
            list_runtime_console_schedules,
            list_runtime_filesystem_disks,
            report_runtime_error,
            resolve_runtime_filesystem_driver,
            run_runtime_console_command,
        )
        from apps.core.storage_service import get_storage_backend

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        reports = []

        class CustomStorage:
            pass

        def report(payload, context):
            reports.append((payload["error_type"], payload["operation"]))
            return True

        def filesystem(payload, context):
            if payload["driver"] == "custom":
                return CustomStorage()
            return None

        def console(payload, context):
            return {
                "name": "alpha:refresh",
                "description": "Refresh alpha",
                "handler": lambda options: {"ok": True, "scope": options.get("scope")},
            }

        ErrorHandlingExtender().hook("report", report).status("alpha_error", 409).extend(app, extension)
        FilesystemExtender().hook("driver", filesystem).disk("alpha", {"root": "/tmp/alpha"}).extend(app, extension)
        ConsoleExtender().hook("command", console).schedule("alpha:refresh", "hourly").extend(app, extension)
        app.make("error.handling")
        app.make("filesystem")
        app.make("console")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            report_runtime_error(ValueError("broken"), operation="unit-test")
            storage = resolve_runtime_filesystem_driver("custom", {"storage_driver": "custom"})
            storage_from_service = get_storage_backend({"storage_driver": "custom"})
            commands = list_runtime_console_commands()
            schedules = list_runtime_console_schedules()
            disks = list_runtime_filesystem_disks()
            statuses = get_runtime_error_statuses()
            result = run_runtime_console_command("alpha:refresh", options={"scope": "all"})

        self.assertEqual(reports, [("ValueError", "unit-test")])
        self.assertIsInstance(storage, CustomStorage)
        self.assertIsInstance(storage_from_service, CustomStorage)
        self.assertEqual(commands[0]["name"], "alpha:refresh")
        self.assertEqual(schedules[0]["name"], "alpha:refresh")
        self.assertEqual(disks[0]["name"], "alpha")
        self.assertEqual(statuses["alpha_error"], 409)
        self.assertEqual(result, {"ok": True, "scope": "all"})

    def test_auth_and_session_extenders_register_typed_runtime_services(self):
        from apps.core.extensions import AuthExtender, SessionExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_password_checkers,
            list_runtime_session_drivers,
            resolve_runtime_session_driver,
            verify_runtime_user_password,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class CustomSessionDriver:
            def __init__(self, config):
                self.config = config

        user = SimpleNamespace(username="alpha", password="unused")

        AuthExtender() \
            .remove_password_checker("django") \
            .add_password_checker("alpha", lambda current_user, raw_password: current_user.username == raw_password) \
            .extend(app, extension)
        SessionExtender().driver("alpha", CustomSessionDriver, description="Alpha session").extend(app, extension)
        app.make("auth")
        app.make("session")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            checkers = get_runtime_password_checkers(default_checker=lambda current_user, raw_password: False)
            accepted = verify_runtime_user_password(user, "alpha", default_checker=lambda current_user, raw_password: False)
            rejected = verify_runtime_user_password(user, "wrong", default_checker=lambda current_user, raw_password: True)
            drivers = list_runtime_session_drivers()
            resolved_driver = resolve_runtime_session_driver("alpha", {"ttl": 60})

        self.assertEqual(list(checkers.keys()), ["alpha"])
        self.assertTrue(accepted)
        self.assertFalse(rejected)
        self.assertEqual(drivers[0]["name"], "alpha")
        self.assertEqual(drivers[0]["extension_id"], "alpha-tools")
        self.assertIsInstance(resolved_driver, CustomSessionDriver)
        self.assertEqual(resolved_driver.config["ttl"], 60)

    def test_csrf_throttle_and_search_index_extenders_register_runtime_services(self):
        from apps.core.extensions import CsrfExtender, SearchIndexExtender, ThrottleApiExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_api_throttlers,
            get_runtime_csrf_exempt_routes,
            should_throttle_runtime_api_request,
        )

        class Item:
            pass

        class Indexer:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        indexer = Indexer()
        request = RequestFactory().get("/api/demo")

        CsrfExtender().exempt_route("alpha-webhook").extend(app, extension)
        ThrottleApiExtender().set("alpha", lambda current_request: current_request.path == "/api/demo").extend(app, extension)
        SearchIndexExtender().indexer(Item, indexer).extend(app, extension)
        app.make("csrf")
        app.make("throttle.api")
        app.make("search")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            routes = get_runtime_csrf_exempt_routes()
            throttlers = get_runtime_api_throttlers()
            throttled = should_throttle_runtime_api_request(request)

        self.assertEqual(routes, {"alpha-webhook"})
        self.assertEqual(list(throttlers.keys()), ["alpha"])
        self.assertTrue(throttled)
        self.assertEqual(app.search.indexers(Item), (indexer,))

    @override_settings(FRONTEND_URL="https://bias.test")
    def test_link_extender_registers_formatter_link_attribute_callbacks(self):
        from apps.core.extensions import LinkExtender
        from apps.core.extensions.formatter_service import apply_extension_formatters, clear_extension_formatter_cache

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        seen = []

        def rel(uri, site_url, attributes):
            seen.append((uri.netloc, site_url, attributes.get("href", "")))
            if uri.netloc == "external.test":
                return "nofollow sponsored"
            return ""

        def target(uri, site_url, attributes):
            if uri.netloc == "bias.test":
                return "_self"
            return "_blank"

        LinkExtender().set_rel(rel).set_target(target).extend(app, extension)
        app.make("formatters")

        clear_extension_formatter_cache()
        try:
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                html = apply_extension_formatters(
                    '<p><a href="https://external.test/page">外部</a> '
                    '<a href="https://bias.test/d/1">内部</a></p>'
                )
        finally:
            clear_extension_formatter_cache()

        self.assertIn('href="https://external.test/page" rel="nofollow sponsored" target="_blank"', html)
        self.assertIn('href="https://bias.test/d/1" target="_self"', html)
        self.assertEqual(seen[0], ("external.test", "https://bias.test", "https://external.test/page"))

    def test_formatter_extender_registers_formatter_phases(self):
        from apps.core.extensions import FormatterExtender
        from apps.core.extensions.formatter_service import (
            apply_extension_formatter_config,
            apply_extension_formatter_parse,
            apply_extension_formatter_render,
            apply_extension_formatter_unparse,
            clear_extension_formatter_cache,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        FormatterExtender() \
            .configure(lambda config: {**config, "alpha": True}) \
            .parse(lambda text, context: text.replace(":alpha:", "alpha")) \
            .render(lambda html, context: html.replace("alpha", "<strong>alpha</strong>")) \
            .unparse(lambda text: text.replace("alpha", ":alpha:")) \
            .extend(app, extension)
        app.make("formatters")

        clear_extension_formatter_cache()
        try:
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                self.assertTrue(apply_extension_formatter_config({})["alpha"])
                parsed = apply_extension_formatter_parse("hello :alpha:")
                rendered = apply_extension_formatter_render(parsed)
                unparsed = apply_extension_formatter_unparse("hello alpha")
        finally:
            clear_extension_formatter_cache()

        self.assertEqual(parsed, "hello alpha")
        self.assertEqual(rendered, "hello <strong>alpha</strong>")
        self.assertEqual(unparsed, "hello :alpha:")

    def test_language_pack_extender_registers_runtime_locale_metadata(self):
        from apps.core.extensions import LanguagePackExtender

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-lang")

        LanguagePackExtender(
            code="en-US",
            label="English",
            native_label="English",
            path="extensions/alpha-lang/locale",
        ).extend(app, extension)
        app.make("forum")
        app.make("locales")

        packs = app.forum_registry.get_language_packs(module_id="alpha-lang")

        self.assertEqual(packs[0].code, "en-US")
        self.assertEqual(packs[0].label, "English")
        self.assertEqual(app.locales.get_paths(extension_id="alpha-lang"), ["extensions/alpha-lang/locale"])

    def test_post_user_and_model_private_extenders_register_core_runtime(self):
        from apps.core.extensions import ModelPrivateExtender, PostExtender, UserExtender
        from apps.core.extensions.system_runtime import (
            apply_runtime_user_group_processors,
            get_runtime_user_avatar_drivers,
            get_runtime_user_display_name_drivers,
            get_runtime_user_preference_transformers,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class DemoPost:
            type = "alphaEvent"
            label = "Alpha Event"

        class DemoModel:
            pass

        def group_processor(user, group_ids):
            return [*group_ids, user.extra_group_id]

        def preference_transformer(value):
            return value == "yes"

        PostExtender().type(DemoPost, description="Alpha post event").extend(app, extension)
        UserExtender() \
            .display_name_driver("alpha", "alpha.display") \
            .avatar_driver("alpha", "alpha.avatar") \
            .permission_groups(group_processor) \
            .register_preference("alpha_pref", preference_transformer, False, label="Alpha Pref") \
            .extend(app, extension)
        ModelPrivateExtender(DemoModel).checker(lambda instance: instance.is_private).extend(app, extension)

        app.make("forum")
        app.make("user")
        app.make("models")

        with patch("apps.core.extensions.system_runtime.get_runtime_system_service", side_effect=lambda key: app.make(key)):
            self.assertEqual(get_runtime_user_display_name_drivers()["alpha"], "alpha.display")
            self.assertEqual(get_runtime_user_avatar_drivers()["alpha"], "alpha.avatar")
            self.assertEqual(apply_runtime_user_group_processors(SimpleNamespace(extra_group_id=9), [1, 2]), [1, 2, 9])
            self.assertTrue(get_runtime_user_preference_transformers()["alpha_pref"]["transformer"]("yes"))

        post_type = app.forum.get_post_type("alphaEvent")
        runtime_view = app.get_runtime_view("alpha-tools")

        self.assertEqual(post_type.label, "Alpha Event")
        self.assertEqual(post_type.module_id, "alpha-tools")
        self.assertEqual(runtime_view.user_preferences[0].key, "alpha_pref")
        self.assertEqual(runtime_view.user_handlers[0].key, "display_name_driver")
        self.assertEqual(runtime_view.model_definitions[-1].kind, "private_checker")
        self.assertTrue(app.models.is_private(DemoModel, SimpleNamespace(is_private=True)))

    def test_model_visibility_scoper_matches_subclasses(self):
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        app = ExtensionApplication()
        app.models.register_visibility(
            "alpha-tools",
            ExtensionModelVisibilityDefinition(
                model=BaseModel,
                ability="view",
                scope=lambda queryset, context: (*queryset, context["ability"]),
            ),
        )

        self.assertTrue(app.models.has_visibility(ChildModel, ability="view"))
        self.assertEqual(
            app.models.apply_visibility(ChildModel, ("base",), {"ability": "view"}),
            ("base", "view"),
        )

    def test_model_visibility_scopers_follow_parent_wildcard_ability_order(self):
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        def append(name):
            return lambda queryset, context: (*queryset, name)

        app = ExtensionApplication()
        for name, model, ability in (
            ("child-view", ChildModel, "view"),
            ("base-view", BaseModel, "view"),
            ("child-any", ChildModel, "*"),
            ("base-any", BaseModel, "*"),
        ):
            app.models.register_visibility(
                "alpha-tools",
                ExtensionModelVisibilityDefinition(
                    model=model,
                    ability=ability,
                    scope=append(name),
                ),
            )

        self.assertEqual(
            app.models.apply_visibility(ChildModel, (), {"ability": "view"}),
            ("base-any", "base-view", "child-any", "child-view"),
        )

    def test_core_model_visibility_scopers_follow_parent_wildcard_ability_order(self):
        from apps.core.visibility import get_core_model_visibility_scopers, register_core_model_visibility_scoper

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        calls = []
        for name, model, ability in (
            ("child-view", ChildModel, "view"),
            ("base-view", BaseModel, "view"),
            ("child-any", ChildModel, "*"),
            ("base-any", BaseModel, "*"),
        ):
            register_core_model_visibility_scoper(
                model,
                lambda queryset, context, marker=name: calls.append(marker) or queryset,
                ability=ability,
            )

        for scoper in get_core_model_visibility_scopers(ChildModel, ability="view"):
            scoper([], {"ability": "view"})

        self.assertEqual(calls, ["base-any", "base-view", "child-any", "child-view"])

    def test_model_visibility_query_policy_deny_returns_empty_queryset(self):
        from apps.core.visibility import apply_model_visibility_scope
        from apps.discussions.models import Discussion

        app = ExtensionApplication()
        app.policies.query_model_policy(
            "alpha-tools",
            Discussion,
            lambda **context: False if context["ability"] == "view" else None,
        )

        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            queryset = apply_model_visibility_scope(
                Discussion,
                Discussion.objects.all(),
                user=AnonymousUser(),
                ability="view",
            )

        self.assertFalse(queryset.exists())

    def test_theme_extender_contributes_frontend_document_payload(self):
        from apps.core.extensions import SettingsExtender, ThemeExtender
        from apps.core.extensions.backend import _build_setting_field_definition
        from apps.core.extensions.frontend_runtime_service import build_enabled_frontend_document_payload

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        runtime_view = app.get_or_create_runtime_view("alpha-tools", name="Alpha Tools")

        ThemeExtender() \
            .variable("bias-alpha-color", "#123456") \
            .document_classes(["theme-alpha"]) \
            .head_tag("meta", {"name": "theme-alpha", "content": "1"}) \
            .extend(app, extension)
        SettingsExtender(fields=(
            _build_setting_field_definition({
                "key": "accent_color",
                "label": "Accent",
                "type": "text",
                "default": "#224466",
            }),
        )) \
            .theme_variable("bias-alpha-accent", "accent_color") \
            .extend(app, extension)
        app.make("theme")
        app.make("settings")

        from apps.core.extensions.frontend_runtime_service import _build_frontend_document_payload

        with patch("apps.core.extensions.frontend_runtime_service.get_extension_host", return_value=app):
            entry = {
                "id": "alpha-tools",
                "frontend_document": _build_frontend_document_payload(
                    runtime_view,
                    settings_values={"accent_color": "#335577"},
                ),
            }

        with patch("apps.core.extensions.frontend_runtime_service.get_enabled_extension_runtime_entries", return_value=[entry]):
            payload = build_enabled_frontend_document_payload()

        self.assertEqual(payload["theme_variables"]["bias-alpha-color"], "#123456")
        self.assertEqual(payload["theme_variables"]["bias-alpha-accent"], "#335577")
        self.assertEqual(payload["document_attributes"]["class"], ["theme-alpha"])
        self.assertEqual(payload["head_tags"][0]["attributes"]["name"], "theme-alpha")

    def test_settings_extender_serializes_forum_settings_with_alias_and_transform(self):
        from apps.core.extensions import SettingsExtender
        from apps.core.extensions.backend import _build_setting_field_definition
        from apps.core.extensions.frontend_runtime_service import _build_extension_forum_settings

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        SettingsExtender(fields=(
            _build_setting_field_definition({
                "key": "allow_username_format",
                "label": "Allow username format",
                "type": "boolean",
                "default": False,
            }),
        ), expose_to_forum=("allow_username_format",)) \
            .serialize_to_forum("allowUsernameMentionFormat", "allow_username_format", bool) \
            .extend(app, extension)
        app.make("settings")

        runtime_view = app.get_runtime_view("alpha-tools")
        payload = _build_extension_forum_settings(
            {
                "forum_settings_keys": tuple(runtime_view.forum_settings_keys),
                "forum_serializations": tuple(runtime_view.settings_forum_serializations),
            },
            {"allow_username_format": "1"},
        )

        self.assertEqual(payload["allow_username_format"], "1")
        self.assertTrue(payload["allowUsernameMentionFormat"])

    def test_validator_extender_runs_during_resource_payload_application(self):
        from apps.core.resource_registry import ResourceRegistry
        from apps.core.resource_objects import Resource, ResourceField
        from apps.core.resource_errors import JsonApiValidationError

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def reject_bad_title(payload, context):
            if payload["payload"].get("title") == "bad":
                raise ValueError("title rejected")

        ValidatorExtender().validator("title", "validated", reject_bad_title).extend(app, extension)
        app.make("validators")

        class Target:
            title = "old"

        class ValidatedResource(Resource):
            def type(self):
                return "validated"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).writable_when()]

        registry = ResourceRegistry()
        registry.register_resource(ValidatedResource())

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            with self.assertRaises(JsonApiValidationError):
                registry.apply_resource_payload("validated", Target(), {"title": "bad"})

    def test_validator_extender_matches_instance_class_targets(self):
        from apps.core.resource_registry import ResourceRegistry
        from apps.core.resource_objects import Resource, ResourceField
        from apps.core.resource_errors import JsonApiValidationError

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class Target:
            title = "old"

        def reject_by_class(payload, context):
            if payload["payload"].get("title") == "bad":
                raise ValueError("class rejected")

        ValidatorExtender().validator("target", Target.__name__, reject_by_class).extend(app, extension)
        app.make("validators")

        class ValidatedResource(Resource):
            def type(self):
                return "validated-class"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).writable_when()]

        registry = ResourceRegistry()
        registry.register_resource(ValidatedResource())

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            with self.assertRaises(JsonApiValidationError):
                registry.apply_resource_payload("validated-class", Target(), {"title": "bad"})

    def test_extension_lifecycle_extender_runs_on_state_changes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LifecycleExtender\n"
                "from apps.core.models import ExtensionInstallation\n"
                "\n"
                "def state():\n"
                "    item = ExtensionInstallation.objects.get(extension_id='alpha-tools')\n"
                "    return item.installed, item.enabled, item.booted\n"
                "\n"
                "def install(context):\n"
                "    label = 'installed-target' if context.installed and not context.enabled and state() == (True, False, False) else 'installed-old-state'\n"
                "    return {'status': 'ok', 'status_label': label, 'message': context.extension_id}\n"
                "\n"
                "def enable(context):\n"
                "    label = 'enabled-target' if context.installed and context.enabled and context.booted and state() == (True, True, True) else 'enabled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def disable(context):\n"
                "    label = 'disabled-target' if context.installed and not context.enabled and not context.booted and state() == (True, False, False) else 'disabled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def uninstall(context):\n"
                "    label = 'uninstalled-target' if not context.installed and not context.enabled and not context.booted and state() == (False, False, False) else 'uninstalled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def extend():\n"
                "    return [LifecycleExtender(install=install, enable=enable, disable=disable, uninstall=uninstall)]\n",
                encoding="utf-8",
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            installed = registry.install_extension("alpha-tools")
            self.assertEqual(installed.runtime.backend_hooks["run_install"]["status_label"], "installed-target")
            self.assertIn("lifecycle_results", installed.runtime.backend_hooks["run_install"]["details"])

            disabled = registry.set_extension_enabled("alpha-tools", False)
            self.assertEqual(disabled.runtime.backend_hooks["run_disable"]["status_label"], "disabled-target")
            enabled = registry.set_extension_enabled("alpha-tools", True)
            self.assertEqual(enabled.runtime.backend_hooks["run_enable"]["status_label"], "enabled-target")
            registry.set_extension_enabled("alpha-tools", False)
            uninstalled = registry.uninstall_extension("alpha-tools")
            self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status_label"], "uninstalled-target")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_lifecycle_error_blocks_state_transition(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LifecycleExtender\n"
                "\n"
                "def enable(context):\n"
                "    return {'status': 'error', 'message': 'enable failed'}\n"
                "\n"
                "def extend():\n"
                "    return [LifecycleExtender(enable=enable)]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=False,
                installed=True,
                booted=False,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            with self.assertRaises(ExtensionStateError) as raised:
                registry.set_extension_enabled("alpha-tools", True)

            self.assertEqual(raised.exception.code, "extension_lifecycle_failed")
            installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
            self.assertFalse(installation.enabled)
            self.assertFalse(installation.booted)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_asset_publish_and_runtime_rebuild_marker(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                assets_dir = manifest_dir / "assets"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                assets_dir.mkdir(parents=True, exist_ok=False)
                (assets_dir / "logo.txt").write_text("asset", encoding="utf-8")
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")

                bootstrap_extension_runtime_event_listeners()
                registry = ExtensionRegistry(extensions_path=extensions_dir)
                with self.captureOnCommitCallbacks(execute=True):
                    installed = registry.install_extension("alpha-tools")

                published_file = Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt"
                self.assertTrue(published_file.exists())
                self.assertEqual(installed.runtime.backend_hooks["publish_assets"]["status"], "ok")
                self.assertIn("run_enable", installed.runtime.backend_hooks)
                published_details = installed.runtime.backend_hooks["publish_assets"]["details"]
                self.assertEqual(published_details["files"][0]["path"], "logo.txt")
                self.assertIn("sha256", published_details["files"][0])
                self.assertIn("/static/extensions/alpha-tools/logo.txt", published_details["files"][0]["url"])
                self.assertTrue(published_details["cache_key"])

                rebuild_marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_enabled", rebuild_marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                import_map_source = import_map.read_text(encoding="utf-8")
                self.assertIn("generatedAdminExtensionModules", import_map_source)
                self.assertNotIn("staleExtensionModules", import_map_source)

                with self.captureOnCommitCallbacks(execute=True):
                    registry.set_extension_enabled("alpha-tools", False)
                self.assertFalse(published_file.exists())
                disabled_marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_disabled", disabled_marker.value)
                self.assertNotIn("alpha-tools", build_manifest.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_runtime_version_survives_rebuild_marker_clear(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            RUNTIME_VERSION_KEY,
            clear_extension_runtime_rebuild_marker,
            mark_extension_runtime_requires_rebuild,
        )

        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")

        marker = Setting.objects.get(key=RUNTIME_REBUILD_MARKER_KEY)
        version = Setting.objects.get(key=RUNTIME_VERSION_KEY)
        self.assertIn("extension_enabled", marker.value)
        self.assertIn("alpha-tools", version.value)

        clear_extension_runtime_rebuild_marker()

        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        self.assertEqual(Setting.objects.get(key=RUNTIME_VERSION_KEY).value, version.value)

    def test_extension_runtime_invalidation_middleware_rebuilds_from_persistent_version(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            clear_extension_runtime_rebuild_marker,
            mark_extension_runtime_requires_rebuild,
            reset_extension_runtime_version_seen,
        )
        from apps.core.middleware import ExtensionRuntimeInvalidationMiddleware

        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")
        clear_extension_runtime_rebuild_marker()
        reset_extension_runtime_version_seen()

        request = RequestFactory().get("/api/forum")
        middleware = ExtensionRuntimeInvalidationMiddleware(lambda current_request: HttpResponse("ok"))
        with patch("apps.core.extensions.lifecycle.rebuild_extension_runtime_state") as rebuild_runtime:
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        rebuild_runtime.assert_called_once_with()

    def test_build_extension_frontend_command_writes_manifest(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                    "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="alpha-tools",
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                call_command("build_extension_frontend", stdout=StringIO())
                manifest = json.loads((Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json").read_text(encoding="utf-8"))
                self.assertIn("alpha-tools", manifest["extensions"])
                self.assertEqual(
                    manifest["extensions"]["alpha-tools"]["inputs"]["forum"],
                    "extensions/alpha-tools/frontend/forum/index.js",
                )
                self.assertTrue(manifest["extensions"]["alpha-tools"]["cache_key"])
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                self.assertTrue(import_map.exists())
                self.assertTrue(output_manifest.exists())
                import_map_source = import_map.read_text(encoding="utf-8")
                self.assertIn("generatedForumExtensionModules", import_map_source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/index.js", import_map_source)
                output_payload = json.loads(output_manifest.read_text(encoding="utf-8"))
                self.assertIn("alpha-tools", output_payload["extensions"])
                self.assertFalse(output_payload["build"]["ran"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_output_manifest_maps_vite_chunks(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                vite_manifest = get_frontend_vite_manifest_path()
                vite_manifest.parent.mkdir(parents=True, exist_ok=True)
                vite_manifest.write_text(json.dumps({
                    "extensions/alpha-tools/frontend/forum/index.js": {
                        "file": "assets/alpha-forum.js",
                        "css": ["assets/alpha-forum.css"],
                        "imports": ["assets/vendor.js"],
                        "dynamicImports": ["../../../extensions/alpha-tools/frontend/forum/lazy.js"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/lazy.js": {
                        "file": "assets/chunk.js",
                        "css": ["assets/chunk.css"],
                        "imports": ["assets/vendor.js"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/Page.vue": {
                        "file": "assets/page.js",
                        "css": ["assets/page.css"],
                        "imports": ["assets/vendor.js"],
                    }
                }, ensure_ascii=False), encoding="utf-8")
                output = build_extension_frontend_output_manifest({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                            "admin_entry": "",
                            "routes": [{
                                "path": "/alpha",
                                "name": "alpha.page",
                                "component": "./Page.vue",
                                "frontend": "forum",
                            }],
                        }
                    }
                })

                forum_output = output["extensions"]["alpha-tools"]["outputs"]["forum"]
                self.assertTrue(output["revision"])
                self.assertEqual(output["extensions"]["alpha-tools"]["revision"], output["revision"])
                self.assertEqual(forum_output["revision"], output["revision"])
                self.assertEqual(forum_output["file"], "assets/alpha-forum.js")
                self.assertEqual(forum_output["css"], ["assets/alpha-forum.css"])
                self.assertEqual(forum_output["imports"], ["assets/vendor.js"])
                self.assertEqual(forum_output["dynamic_imports"], ["../../../extensions/alpha-tools/frontend/forum/lazy.js"])
                self.assertEqual(forum_output["chunks"][0]["module_id"], "frontend/forum/lazy.js")
                self.assertEqual(forum_output["chunks"][0]["file"], "assets/chunk.js")
                self.assertEqual(forum_output["chunks"][0]["css"], ["assets/chunk.css"])
                self.assertEqual(forum_output["chunks"][0]["revision"], output["revision"])
                self.assertEqual(forum_output["chunks"][1]["module_id"], "frontend/forum/Page.vue")
                self.assertEqual(forum_output["chunks"][1]["file"], "assets/page.js")
                self.assertEqual(forum_output["chunks"][1]["css"], ["assets/page.css"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_output_manifest_maps_route_only_components(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                vite_manifest = get_frontend_vite_manifest_path()
                vite_manifest.parent.mkdir(parents=True, exist_ok=True)
                vite_manifest.write_text(json.dumps({
                    "../../../extensions/alpha-tools/frontend/admin/Page.vue": {
                        "file": "assets/admin-page.js",
                        "css": ["assets/admin-page.css"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/Page.vue": {
                        "file": "assets/forum-page.js",
                        "css": ["assets/forum-page.css"],
                    },
                }, ensure_ascii=False), encoding="utf-8")

                output = build_extension_frontend_output_manifest({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "admin_entry": "",
                            "forum_entry": "",
                            "routes": [
                                {
                                    "path": "/admin/alpha",
                                    "name": "alpha.admin",
                                    "component": "./Page.vue",
                                    "frontend": "admin",
                                },
                                {
                                    "path": "/alpha",
                                    "name": "alpha.page",
                                    "component": "./Page.vue",
                                    "frontend": "forum",
                                },
                            ],
                        }
                    }
                })

                outputs = output["extensions"]["alpha-tools"]["outputs"]
                self.assertEqual(outputs["admin"]["chunks"][0]["module_id"], "frontend/admin/Page.vue")
                self.assertEqual(outputs["admin"]["chunks"][0]["file"], "assets/admin-page.js")
                self.assertEqual(outputs["forum"]["chunks"][0]["module_id"], "frontend/forum/Page.vue")
                self.assertEqual(outputs["forum"]["chunks"][0]["file"], "assets/forum-page.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_import_map_uses_inputs_fallback(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                path = write_extension_frontend_import_map({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "inputs": {
                                "admin": "extensions/alpha-tools/frontend/admin/index.js",
                                "forum": "extensions/alpha-tools/frontend/forum/index.js",
                            },
                        }
                    }
                })

                source = path.read_text(encoding="utf-8")
                self.assertIn("../../../extensions/alpha-tools/frontend/admin/index.js", source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/index.js", source)
                self.assertIn('"alpha-tools": () =>', source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_import_map_includes_css_and_route_components(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                path = write_extension_frontend_import_map({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                            "css": ["frontend/forum/style.css"],
                            "routes": [
                                {
                                    "path": "/admin/alpha",
                                    "name": "alpha.admin",
                                    "component": "./AdminPage.vue",
                                    "frontend": "admin",
                                },
                                {
                                    "path": "/alpha",
                                    "name": "alpha.page",
                                    "component": "./Page.vue",
                                    "frontend": "forum",
                                },
                            ],
                        }
                    }
                })

                source = path.read_text(encoding="utf-8")
                self.assertIn("loadExtensionModule", source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/style.css", source)
                self.assertNotIn('"./AdminPage.vue": () => import(', source)
                self.assertIn('"extensions/alpha-tools/frontend/admin/AdminPage.vue": () => import("../../../extensions/alpha-tools/frontend/admin/AdminPage.vue")', source)
                self.assertIn('"alpha-tools:./AdminPage.vue": () => import("../../../extensions/alpha-tools/frontend/admin/AdminPage.vue")', source)
                self.assertNotIn('"./Page.vue": () => import(', source)
                self.assertIn('"extensions/alpha-tools/frontend/forum/Page.vue": () => import("../../../extensions/alpha-tools/frontend/forum/Page.vue")', source)
                self.assertIn('"alpha-tools:./Page.vue": () => import("../../../extensions/alpha-tools/frontend/forum/Page.vue")', source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_copy_frontend_dist_to_static_publishes_dist(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                dist_file = Path(temp_dir) / "frontend" / "dist" / "assets" / "main.js"
                dist_file.parent.mkdir(parents=True, exist_ok=True)
                dist_file.write_text("console.log('ok')", encoding="utf-8")

                result = copy_frontend_dist_to_static()

                published = get_published_frontend_root() / "assets" / "main.js"
                self.assertEqual(result["status"], "ok")
                self.assertTrue(published.exists())
                self.assertEqual(published.read_text(encoding="utf-8"), "console.log('ok')")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_build_extension_frontend_command_flushes_generated_assets(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const generatedAdminExtensionModules = {}\nexport const generatedForumExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text("{}", encoding="utf-8")
                build_manifest.write_text("{}", encoding="utf-8")

                published_root = get_published_frontend_root()
                published_root.mkdir(parents=True, exist_ok=True)
                (published_root / "index.html").write_text("", encoding="utf-8")

                call_command("build_extension_frontend", "--flush", "--flush-published", stdout=StringIO())

                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
                self.assertFalse(output_manifest.exists())
                self.assertFalse(build_manifest.exists())
                self.assertFalse(published_root.exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extensions_command_prunes_missing_installations(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING

                ExtensionInstallation.objects.create(
                    extension_id="missing-package",
                    version="1.0.0",
                    source="python-package",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                stdout = StringIO()
                call_command("sync_extensions", stdout=stdout)
                installation = ExtensionInstallation.objects.get(extension_id="missing-package")
                self.assertFalse(installation.enabled)
                self.assertFalse(installation.booted)
                self.assertTrue(installation.meta["sync"]["missing"])
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)
                self.assertEqual(lock["schema"], 1)
                self.assertEqual(lock["packages"][0]["id"], "missing-package")
                self.assertTrue(lock["packages"][0]["missing"])
                self.assertIn("包锁定:", stdout.getvalue())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.extensions.manifest.metadata.distributions")
    def test_sync_extension_packages_persists_distribution_package_lock(self, distributions_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir), BIAS_EXTENSION_PACKAGE_DISCOVERY=True):
                from apps.core.extensions import manifest as manifest_module
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING, ExtensionManager

                manifest_module._distribution_manifest_cache = None
                package_dir = Path(temp_dir) / "site-packages" / "alpha_tools" / "bias_extension"
                package_dir.mkdir(parents=True, exist_ok=False)
                (package_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.2.3",
                }, ensure_ascii=False), encoding="utf-8")

                class DemoDistribution:
                    version = "1.2.3"
                    files = ("alpha_tools/bias_extension/extension.json",)
                    metadata = {"Name": "alpha-tools"}

                    def locate_file(self, file):
                        return Path(temp_dir) / "site-packages" / str(file)

                distributions_mock.return_value = [DemoDistribution()]
                ExtensionInstallation.objects.create(
                    extension_id="alpha-tools",
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                result = ExtensionManager(extensions_path=Path(temp_dir) / "extensions").sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)

            self.assertEqual(result["discovered"], ["alpha-tools"])
            self.assertEqual(result["updated"], ["alpha-tools"])
            self.assertEqual(result["locked"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["locked_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["missing_count"], 0)
            self.assertEqual(installation.version, "1.2.3")
            self.assertEqual(installation.source, "python-package")
            self.assertEqual(lock["packages"][0]["id"], "alpha-tools")
            self.assertEqual(lock["packages"][0]["source"], "python-package")
            self.assertEqual(lock["packages"][0]["distribution"]["name"], "alpha-tools")
            self.assertEqual(lock["packages"][0]["distribution"]["version"], "1.2.3")
            self.assertFalse(lock["packages"][0]["missing"])
            self.assertTrue(lock["packages"][0]["discovered"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_middleware_and_policy_mounts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import MiddlewareExtender, PolicyExtender\n"
                "\n"
                "def demo_middleware(request):\n"
                "    return request\n"
                "\n"
                "def can_use_demo(user=None, **kwargs):\n"
                "    return True\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        MiddlewareExtender(mounts=(('api', demo_middleware, 30),)),\n"
                "        PolicyExtender(mounts=(('demo.use', can_use_demo),)),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.middleware_mounts), 1)
            self.assertEqual(runtime_view.middleware_mounts[0].target, "api")
            self.assertEqual(runtime_view.middleware_mounts[0].order, 30)
            self.assertEqual(len(runtime_view.policy_mounts), 1)
            self.assertEqual(runtime_view.policy_mounts[0].key, "demo.use")
            self.assertTrue(runtime_view.policy_mounts[0].handler())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_realtime_included_enrichers(self):
        from apps.core.forum_runtime import (
            build_realtime_included_payload,
            clear_realtime_included_enrichers,
        )

        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import RealtimeExtender\n"
                "\n"
                "def enrich_alpha(**kwargs):\n"
                "    return {'alpha': [{'id': '1', 'value': 'ok'}]}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RealtimeExtender().included_payload('alpha', enrich_alpha, description='Alpha included payload'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            clear_realtime_included_enrichers()
            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.realtime_included), 1)
            self.assertEqual(runtime_view.realtime_included[0].key, "alpha")
            self.assertEqual(application.realtime.get_included_enrichers(extension_id="alpha-tools")[0].description, "Alpha included payload")
            self.assertEqual(build_realtime_included_payload()["alpha"][0]["value"], "ok")
        finally:
            clear_realtime_included_enrichers()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_discussion_lifecycle_handlers(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import DiscussionLifecycleExtender\n"
                "\n"
                "def prepare_create(**kwargs):\n"
                "    return {'prepared': kwargs['payload']['alpha']}\n"
                "\n"
                "def apply_create(state=None, **kwargs):\n"
                "    return {'applied': state['prepared']}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        DiscussionLifecycleExtender().handler('alpha', prepare_create=prepare_create, apply_create=apply_create, description='Alpha discussion lifecycle'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.discussion_lifecycle), 1)
            self.assertEqual(runtime_view.discussion_lifecycle[0].key, "alpha")
            states = application.discussion_lifecycle.prepare_create(
                user=None,
                payload={"alpha": "ok"},
            )
            self.assertEqual(states["alpha"]["prepared"], "ok")
            results = application.discussion_lifecycle.apply_create(
                discussion=SimpleNamespace(id=1),
                states=states,
            )
            self.assertEqual(results["alpha"]["applied"], "ok")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_post_lifecycle_handlers(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import PostLifecycleExtender\n"
                "\n"
                "def apply_created(**kwargs):\n"
                "    return {'post_id': kwargs['post'].id, 'value': kwargs['context']['alpha']}\n"
                "\n"
                "def apply_hidden(**kwargs):\n"
                "    return {'post_id': kwargs['post'].id, 'hidden': kwargs['context']['is_hidden']}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        PostLifecycleExtender().handler('alpha', apply_created=apply_created, apply_hidden=apply_hidden, description='Alpha post lifecycle'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.post_lifecycle), 1)
            self.assertEqual(runtime_view.post_lifecycle[0].key, "alpha")
            results = application.post_lifecycle.apply_created(
                post=SimpleNamespace(id=7),
                context={"alpha": "ok"},
            )
            self.assertEqual(results["alpha"]["post_id"], 7)
            self.assertEqual(results["alpha"]["value"], "ok")
            hidden_results = application.post_lifecycle.apply_hidden(
                post=SimpleNamespace(id=8),
                context={"is_hidden": True},
            )
            self.assertEqual(hidden_results["alpha"]["post_id"], 8)
            self.assertTrue(hidden_results["alpha"]["hidden"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_api_application_is_built_from_extension_host_routes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from ninja import Router\n"
                "from apps.core.extensions import ApiRoutesExtender\n"
                "router = Router()\n"
                "@router.get('/ping')\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "def extend():\n"
                "    return [ApiRoutesExtender(mounts=(('/ext/alpha-tools', router),), tags=('Alpha',))]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            api = application.make("api.application")

            paths = {item[0] for item in api._routers}
            self.assertIn("/ext/alpha-tools", paths)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_bias_style_conditional_model_search_and_api_resource_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ApiResourceExtender, ConditionalExtender, FrontendExtender, ModelExtender, ModelVisibilityExtender, SearchDriverExtender\n"
                "from apps.core.extensions.types import ExtensionModelCastDefinition, ExtensionModelDefaultDefinition, ExtensionModelDefinition, ExtensionModelRelationDefinition, ExtensionModelVisibilityDefinition, ExtensionResourceEndpointDefinition, ExtensionResourceFieldDefinition, ExtensionResourceFieldMutatorDefinition, ExtensionResourceRelationshipDefinition, ExtensionResourceSortDefinition, ExtensionSearchDriverDefinition\n"
                "from apps.core.forum_registry_types import SearchFilterDefinition\n"
                "from apps.core.resource_objects import Resource, ResourceEndpoint, ResourceField, ResourceSort\n"
                "\n"
                "class DemoModel:\n"
                "    pass\n"
                "\n"
                "class ChildDemoModel(DemoModel):\n"
                "    pass\n"
                "\n"
                "class AlphaResource(Resource):\n"
                "    module_id = 'alpha-tools'\n"
                "    def type(self):\n"
                "        return 'alpha_resource'\n"
                "    def base(self, model, context):\n"
                "        return {'id': 'alpha'}\n"
                "    def fields(self):\n"
                "        return [ResourceField('title', resolver=lambda model, context: 'alpha')]\n"
                "    def endpoints(self):\n"
                "        return [ResourceEndpoint('show', handler=lambda context: {'version': 1})]\n"
                "    def sorts(self):\n"
                "        return [ResourceSort('hot', handler=('hot',))]\n"
                "\n"
                "def visibility(queryset, context):\n"
                "    return ('visible', queryset, context['ability'])\n"
                "\n"
                "def parse(value):\n"
                "    return value.split(':', 1)[1] if value.startswith('alpha:') else None\n"
                "\n"
                "def apply(queryset, value, context):\n"
                "    return queryset\n"
                "\n"
                "def mutate(queryset, context):\n"
                "    return ('mutated', queryset, context['target'])\n"
                "\n"
                "def mutate_endpoint(endpoint):\n"
                "    return ('endpoint', endpoint)\n"
                "\n"
                "def mutate_owner_relationship(relationship):\n"
                "    return mutated_owner_relationship\n"
                "\n"
                "def mutate_sort(sort):\n"
                "    return ExtensionResourceSortDefinition(resource=sort.resource, sort=sort.sort, module_id=sort.module_id, handler={'name': 'newest-mutated'}, operation='add')\n"
                "\n"
                "def mutate_alpha_field(field):\n"
                "    return ExtensionResourceFieldDefinition(resource='alpha_resource', field=field.field, module_id='', resolver=lambda model, context: 'ALPHA')\n"
                "\n"
                "def mutate_alpha_endpoint(endpoint):\n"
                "    return ExtensionResourceEndpointDefinition(resource='alpha_resource', endpoint=endpoint.endpoint, module_id='', handler=lambda context: {'version': 2})\n"
                "\n"
                "def mutate_alpha_sort(sort):\n"
                "    return ExtensionResourceSortDefinition(resource='alpha_resource', sort=sort.sort, module_id='', handler=('-hot',))\n"
                "\n"
                "field = ExtensionResourceFieldDefinition(resource='forum', field='alpha', module_id='alpha-tools', resolver=lambda model, context: True)\n"
                "before_field = ExtensionResourceFieldDefinition(resource='forum', field='before_title', module_id='', resolver=lambda model, context: True)\n"
                "owner_relationship = ExtensionResourceRelationshipDefinition(resource='forum', relationship='owner', module_id='alpha-tools', resolver=lambda model, context: {'name': 'owner'}, select_related=('owner',))\n"
                "mutated_owner_relationship = ExtensionResourceRelationshipDefinition(resource='forum', relationship='owner', module_id='', resolver=lambda model, context: {'name': 'mutated'}, select_related=('owner_profile',))\n"
                "search_filter = SearchFilterDefinition(code='alpha', label='Alpha', module_id='alpha-tools', target='discussion', parser=parse, applier=apply)\n"
                "endpoint_add = ExtensionResourceEndpointDefinition(resource='forum', endpoint='store', module_id='alpha-tools', operation='add', mutator=lambda endpoint: {'name': 'store'})\n"
                "endpoint_before = ExtensionResourceEndpointDefinition(resource='forum', endpoint='before_store', module_id='', operation='add', mutator=lambda endpoint: {'name': 'before_store'})\n"
                "endpoint_first = ExtensionResourceEndpointDefinition(resource='forum', endpoint='first', module_id='', operation='add', mutator=lambda endpoint: {'name': 'first'})\n"
                "field_mutator = ExtensionResourceFieldMutatorDefinition(resource='forum', field='title', module_id='alpha-tools', mutator=lambda field: {'name': 'title', 'mutated': True})\n"
                "sort = ExtensionResourceSortDefinition(resource='forum', sort='newest', module_id='alpha-tools', handler={'name': 'newest'}, operation='add')\n"
                "old_sort = ExtensionResourceSortDefinition(resource='forum', sort='old', module_id='', handler={'name': 'old'}, operation='add')\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(forum_entry='forum.js').css('forum.css').js_directory('chunks').preload({'href': '/x.js', 'as': 'script'}).extra_document_attributes({'data-alpha': '1'}).extra_document_classes(['alpha-page', {'beta-page': True}]).title('AlphaTitle').route('/alpha', 'alpha', 'AlphaView', title='Alpha').remove_route('old-alpha'),\n"
                "        ApiResourceExtender(fields=(field,)).fields_before('title', before_field).relationships_with(owner_relationship).field(field_mutator).field(\n"
                "            'owner', mutate_owner_relationship\n"
                "        ).remove_fields('hidden').endpoint('show', mutate_endpoint).endpoint(endpoint_add).endpoints_before('store', endpoint_before).endpoints_before_all(endpoint_first).sort(sort, old_sort).sort('newest', mutate_sort).remove_sorts('old'),\n"
                "        ApiResourceExtender.from_resource(AlphaResource).field('title', mutate_alpha_field).endpoint('show', mutate_alpha_endpoint).sort('hot', mutate_alpha_sort),\n"
                "        ModelExtender(definitions=(ExtensionModelDefinition(model=DemoModel, key='alpha', handler='belongsToMany'),)).relationship(\n"
                "            ExtensionModelRelationDefinition(model=DemoModel, name='owner', resolver=lambda model: ('owner', model), relation_type='belongsTo')\n"
                "        ).has_one(\n"
                "            'owner_profile', DemoModel, model=DemoModel, foreign_key='owner_id', local_key='id'\n"
                "        ).has_many(\n"
                "            'children', DemoModel, model=DemoModel, foreign_key='parent_id', local_key='id'\n"
                "        ).cast(\n"
                "            ExtensionModelCastDefinition(model=DemoModel, attribute='meta', cast='json')\n"
                "        ).default(\n"
                "            ExtensionModelDefaultDefinition(model=DemoModel, attribute='enabled', value=True)\n"
                "        ),\n"
                "        ModelVisibilityExtender(definitions=(ExtensionModelVisibilityDefinition(model=DemoModel, ability='view', scope=visibility),)),\n"
                "        SearchDriverExtender(drivers=(ExtensionSearchDriverDefinition(target='discussion', driver='database', filters=(search_filter,), mutators=(mutate,), searchers=('tag-searcher',), fulltext='fulltext'),)),\n"
                "        ConditionalExtender().when_extension_enabled('alpha-tools', lambda: ApiResourceExtender(fields=(\n"
                "            ExtensionResourceFieldDefinition(resource='forum', field='conditional', module_id='alpha-tools', resolver=lambda model, context: True),\n"
                "        ))),\n"
                "    ]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual([item.field for item in runtime_view.resource_fields], ["alpha", "conditional"])
            self.assertEqual([item.module_id for item in runtime_view.resource_field_mutators if item.field in {"before_title", "owner", "hidden"}], ["alpha-tools", "alpha-tools", "alpha-tools"])
            self.assertEqual(runtime_view.resource_endpoints[0].endpoint, "show")
            self.assertEqual(runtime_view.resource_sorts[0].sort, "newest")
            self.assertEqual(runtime_view.model_definitions[0].key, "alpha")
            self.assertEqual(runtime_view.model_relations[0].name, "owner")
            self.assertEqual([item.relation_type for item in runtime_view.model_relations], ["belongsTo", "hasOne", "hasMany"])
            self.assertEqual(runtime_view.model_relations[1].foreign_key, "owner_id")
            self.assertEqual(runtime_view.model_relations[2].owner_key, "id")
            self.assertEqual(runtime_view.model_casts[0].attribute, "meta")
            self.assertEqual(runtime_view.model_defaults[0].attribute, "enabled")
            self.assertEqual(runtime_view.frontend_forum_entry, "forum.js")
            self.assertEqual(runtime_view.frontend_css, ("forum.css",))
            self.assertEqual(runtime_view.frontend_js_directories, ("chunks",))
            self.assertEqual(runtime_view.frontend_preloads[0]["as"], "script")
            self.assertEqual(runtime_view.frontend_document_attributes[0]["data-alpha"], "1")
            self.assertEqual(runtime_view.frontend_title_driver, "AlphaTitle")
            self.assertEqual(runtime_view.frontend_routes[0].path, "/alpha")
            self.assertEqual(runtime_view.frontend_routes[0].module_id, "alpha-tools")
            self.assertEqual(runtime_view.frontend_routes[1].name, "old-alpha")
            self.assertTrue(runtime_view.frontend_routes[1].removed)
            self.assertIn({"class": ["alpha-page", {"beta-page": True}]}, runtime_view.frontend_document_attributes)
            self.assertEqual(runtime_view.search_drivers[0].target, "discussion")
            self.assertEqual(runtime_view.search_drivers[0].mutators[0].__name__, "mutate")
            self.assertEqual(runtime_view.search_drivers[0].searchers, ("tag-searcher",))
            self.assertEqual(runtime_view.search_drivers[0].fulltext, "fulltext")
            self.assertFalse(any(item.code == "alpha" for item in application.forum.get_search_filters("discussion")))
            self.assertEqual(
                application.models.get_definitions_for_model(runtime_view.model_definitions[0].model)[0].key,
                "alpha",
            )
            child_model = runtime_view.model_relations[0].resolver.__globals__["ChildDemoModel"]
            self.assertEqual(application.models.get_definitions_for_model(child_model)[0].key, "alpha")
            self.assertEqual(
                application.models.apply_visibility(runtime_view.model_definitions[0].model, "base", {"ability": "view"}),
                ("visible", "base", "view"),
            )
            self.assertEqual(
                application.models.apply_visibility(runtime_view.model_definitions[0].model, "base", {"ability": "edit"}),
                "base",
            )
            self.assertEqual(application.search.get_searchers("discussion"), ["tag-searcher"])
            self.assertEqual(application.search.get_fulltext_handlers("discussion"), ["fulltext"])
            self.assertEqual(application.search.apply_mutators("discussion", "base", {"target": "discussion"}), ("mutated", "base", "discussion"))
            self.assertEqual(application.resources.apply_endpoint_mutators("forum", "show", "base"), ("endpoint", "base"))
            self.assertEqual(
                application.resources.apply_endpoint_definitions("forum", [{"name": "index"}]),
                [{"name": "first"}, {"name": "index"}, {"name": "before_store"}, {"name": "store"}],
            )
            self.assertEqual(
                application.resources.apply_endpoint_definitions("forum", [{"name": "store"}]),
                [{"name": "first"}, {"name": "before_store"}, {"name": "store"}, {"name": "store"}],
            )
            field_definitions = application.resources.apply_field_definitions("forum", [{"name": "title"}, {"name": "hidden"}])
            self.assertEqual(getattr(field_definitions[0], "field", ""), "before_title")
            self.assertEqual(field_definitions[1], {"name": "title", "mutated": True})
            self.assertEqual(len(field_definitions), 2)
            self.assertEqual(
                application.resources.apply_payload_field_mutators("forum", {"title": {"name": "title"}}),
                {"title": {"name": "title", "mutated": True}},
            )
            resource_payload = application.resources.serialize("forum", SimpleNamespace(), include=("owner",))
            resource_plan = application.resources.build_preload_plan("forum", include=("owner",))
            self.assertEqual(resource_payload["owner"], {"name": "mutated"})
            self.assertEqual(resource_plan.select_related, ("owner_profile",))
            self.assertEqual(application.resources.apply_sort_definitions("forum", []), [{"name": "newest-mutated"}])
            alpha_payload = application.resources.serialize("alpha_resource", SimpleNamespace())
            alpha_endpoint = application.resources.get_dispatch_endpoint("alpha_resource", "show", "GET")
            alpha_queryset = Mock()
            alpha_ordered_queryset = Mock()
            alpha_queryset.order_by.return_value = alpha_ordered_queryset
            self.assertEqual(alpha_payload, {"id": "alpha", "title": "ALPHA"})
            self.assertEqual(alpha_endpoint.handler({}), {"version": 2})
            self.assertIs(application.resources.apply_named_sort("alpha_resource", alpha_queryset, "hot"), alpha_ordered_queryset)
            alpha_queryset.order_by.assert_called_once_with("-hot")
            self.assertEqual(application.models.resolve_relation(runtime_view.model_definitions[0].model, "owner", "demo"), ("owner", "demo"))
            self.assertEqual(application.models.resolve_relation(child_model, "owner", "child"), ("owner", "child"))
            child_instance = child_model()
            self.assertEqual(child_instance.owner, ("owner", child_instance))
            self.assertEqual(application.models.get_casts_for_model(runtime_view.model_definitions[0].model), {"meta": "json"})
            self.assertEqual(application.models.get_casts_for_model(child_model), {"meta": "json"})
            self.assertEqual(application.models.get_defaults_for_model(runtime_view.model_definitions[0].model), {"enabled": True})
            self.assertEqual(application.models.get_defaults_for_model(child_model), {"enabled": True})
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=application):
                text_query, parsed_filters = SearchService.extract_filter_tokens(
                    "alpha:1 body",
                    targets=("discussion",),
                )
                self.assertEqual(text_query, "body")
                self.assertEqual(parsed_filters["discussion"][0][0].code, "alpha")
                self.assertTrue(any(item.code == "alpha" for item in SearchService.get_public_search_filters(targets=("discussion",))))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_dependency_sort_detects_cycles_and_persists_enabled_order(self):
        alpha = Extension.from_manifest(ExtensionManifest(
            id="alpha",
            name="Alpha",
            version="1.0.0",
            dependencies=("beta",),
            source="filesystem",
        ))
        beta = Extension.from_manifest(ExtensionManifest(
            id="beta",
            name="Beta",
            version="1.0.0",
            dependencies=("alpha",),
            source="filesystem",
        ))
        manager = ExtensionRegistry()
        with self.assertRaises(ExtensionStateError) as raised:
            manager.sort_extensions_for_boot([alpha, beta])
        self.assertEqual(raised.exception.code, "extension_dependency_cycle")

        core = Extension.from_manifest(ExtensionManifest(
            id="core",
            name="Core",
            version="1.0.0",
            source="filesystem",
        ))
        tags = Extension.from_manifest(ExtensionManifest(
            id="tags",
            name="Tags",
            version="1.0.0",
            dependencies=("core",),
            source="filesystem",
        ))
        ordered = manager.sort_extensions_for_boot([tags, core])
        self.assertEqual([item.id for item in ordered], ["core", "tags"])

        notifications = Extension.from_manifest(ExtensionManifest(
            id="notifications",
            name="Notifications",
            version="1.0.0",
            dependencies=("core",),
            source="filesystem",
        ))
        likes = Extension.from_manifest(ExtensionManifest(
            id="likes",
            name="Likes",
            version="1.0.0",
            dependencies=("notifications",),
            source="filesystem",
        ))
        ordered = manager.sort_extensions_for_boot([likes, tags, notifications, core])
        self.assertEqual([item.id for item in ordered], ["core", "notifications", "tags", "likes"])

    def test_site_extend_file_contributes_runtime_extenders_without_module_registration(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                extensions_dir.mkdir(parents=True, exist_ok=False)
                (Path(temp_dir) / "extend.py").write_text(
                    "from apps.core.extensions import SettingsExtender\n"
                    "\n"
                    "def extend():\n"
                    "    return [SettingsExtender().default('site.local_enabled', True)]\n",
                    encoding="utf-8",
                )

                application = build_extension_application(
                    manager=ExtensionRegistry(extensions_path=extensions_dir),
                    forum_registry=ForumRegistry(),
                    event_bus=DomainEventBus(),
                    force=True,
                )
                application.make("settings")

                site_view = application.get_runtime_view("site")
                self.assertIsNotNone(site_view)
                self.assertEqual(site_view.source, "site")
                self.assertTrue(any(
                    item.key == "site.local_enabled"
                    and item.value is True
                    and item.module_id == "site"
                    for item in site_view.settings_defaults
                ))
                self.assertNotIn(
                    "site",
                    {module.module_id for module in application.forum.get_modules()},
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_bootstrap_populates_shared_registries_at_startup(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AdminSurfaceExtender, EventListenersExtender, ResourceExtender\n"
                "from apps.core.extensions.types import ExtensionEventListenerDefinition, ExtensionResourceDefinition\n"
                "from apps.core.forum_registry_types import PermissionDefinition\n"
                "\n"
                "def _serialize(instance, context):\n"
                "    return {'ok': True}\n"
                "\n"
                "def _handle(event):\n"
                "    return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        AdminSurfaceExtender(permissions=(\n"
                "            PermissionDefinition(code='alpha.manage', label='管理 Alpha', section='admin', section_label='后台', module_id='alpha-tools'),\n"
                "        )),\n"
                "        ResourceExtender(resources=(\n"
                "            ExtensionResourceDefinition(resource='alpha', module_id='alpha-tools', resolver=_serialize),\n"
                "        )),\n"
                "        EventListenersExtender(listeners=(\n"
                "            ExtensionEventListenerDefinition(event_type=object, handler=_handle),\n"
                "        )),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            manager = ExtensionRegistry(extensions_path=extensions_dir)
            forum_registry = ForumRegistry()
            event_bus = DomainEventBus()
            resource_registry = ResourceRegistry()

            with patch("apps.core.extensions.bootstrap.get_extension_registry", return_value=manager), patch(
                "apps.core.forum_registry.get_forum_registry",
                return_value=forum_registry,
            ), patch(
                "apps.core.domain_events.get_forum_event_bus",
                return_value=event_bus,
            ), patch(
                "apps.core.resource_registry.get_resource_registry",
                return_value=resource_registry,
            ):
                application = bootstrap_extension_application(force=True)

            self.assertIsNotNone(application)
            self.assertTrue(any(item.code == "alpha.manage" for item in forum_registry.get_all_permissions()))
            self.assertIsNotNone(resource_registry.get_resource("alpha"))
            self.assertIn(object, event_bus._listeners)
        finally:
            reset_extension_application_bootstrap_state()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_resolving_callbacks_do_not_reapply_previous_callbacks(self):
        application = ExtensionApplication()
        application.instance("actions", [])

        application.resolving("actions", lambda actions, host: [*actions, "first"])
        application.resolving("actions", lambda actions, host: [*actions, "second"])

        self.assertEqual(application.get("actions"), ["first", "second"])


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
        self.assertIn("install", payload["available_hooks"])
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


class ExtensionPolicyIntegrationTests(TestCase):
    def _build_policy_extension_registry(self) -> tuple[Path, ExtensionRegistry]:
        temp_dir = make_workspace_temp_dir()
        extensions_dir = temp_dir / "extensions"
        manifest_dir = extensions_dir / "alpha-policy"
        backend_dir = manifest_dir / "backend"
        manifest_dir.mkdir(parents=True, exist_ok=False)
        backend_dir.mkdir(parents=True, exist_ok=False)
        (manifest_dir / "extension.json").write_text(json.dumps({
            "id": "alpha-policy",
            "name": "Alpha Policy",
            "version": "1.0.0",
            "backend_entry": "extensions.alpha_policy.backend.ext",
        }, ensure_ascii=False), encoding="utf-8")
        (backend_dir / "ext.py").write_text(
            "from apps.core.extensions import PolicyExtender\n"
            "\n"
            "def grant_search_users(user=None, permission_name=None, **kwargs):\n"
            "    if permission_name == 'searchUsers' and user and user.username == 'policy-user':\n"
            "        return True\n"
            "    return None\n"
            "\n"
            "def deny_delete_own_discussion(user=None, discussion=None, **kwargs):\n"
            "    if user and discussion and discussion.user_id == user.id:\n"
            "        return False\n"
            "    return None\n"
            "\n"
            "def deny_post_like(user=None, post=None, **kwargs):\n"
            "    if user and post and user.username == 'blocked-liker':\n"
            "        return False\n"
            "    return None\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        PolicyExtender(mounts=(\n"
            "            ('forum.permission.searchUsers', grant_search_users),\n"
            "            ('discussion.delete', deny_delete_own_discussion),\n"
            "            ('post.like', deny_post_like),\n"
            "        )),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.create(
            extension_id="alpha-policy",
            version="1.0.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )
        return temp_dir, ExtensionRegistry(extensions_path=extensions_dir)

    def test_extension_policy_can_grant_forum_permission(self):
        temp_dir, registry = self._build_policy_extension_registry()
        try:
            user = User.objects.create_user(
                username="policy-user",
                email="policy-user@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            group = Group.objects.create(name="PolicySearchViewer", color="#27ae60")
            Permission.objects.create(group=group, permission="viewUserList")
            user.user_groups.add(group)

            self.assertFalse("searchUsers" in UserService.get_forum_permission_set(user))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertTrue(UserService.has_forum_permission(user, "searchUsers"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_policy_can_deny_delete_own_discussion(self):
        temp_dir, registry = self._build_policy_extension_registry()
        try:
            author = User.objects.create_user(
                username="policy-discussion-author",
                email="policy-discussion-author@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            discussion = DiscussionService.create_discussion(
                title="Policy delete discussion",
                content="Delete should be denied by extension policy",
                user=author,
            )

            self.assertTrue(DiscussionService.can_delete_discussion(discussion, author))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertFalse(DiscussionService.can_delete_discussion(discussion, author))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_policy_can_deny_like_post(self):
        temp_dir, registry = self._build_policy_extension_registry()
        try:
            author = User.objects.create_user(
                username="policy-post-author",
                email="policy-post-author@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            liker = User.objects.create_user(
                username="blocked-liker",
                email="blocked-liker@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            discussion = DiscussionService.create_discussion(
                title="Policy like discussion",
                content="Initial content",
                user=author,
            )
            post = PostService.create_post(
                discussion_id=discussion.id,
                content="Reply to be liked",
                user=author,
            )

            self.assertTrue(can_like_post(post, liker))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertFalse(can_like_post(post, liker))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ExtensionMiddlewareIntegrationTests(TestCase):
    def _build_middleware_extension_registry(self) -> tuple[Path, ExtensionRegistry]:
        temp_dir = make_workspace_temp_dir()
        extensions_dir = temp_dir / "extensions"
        manifest_dir = extensions_dir / "alpha-middleware"
        backend_dir = manifest_dir / "backend"
        manifest_dir.mkdir(parents=True, exist_ok=False)
        backend_dir.mkdir(parents=True, exist_ok=False)
        (manifest_dir / "extension.json").write_text(json.dumps({
            "id": "alpha-middleware",
            "name": "Alpha Middleware",
            "version": "1.0.0",
            "backend_entry": "extensions.alpha_middleware.backend.ext",
        }, ensure_ascii=False), encoding="utf-8")
        (backend_dir / "ext.py").write_text(
            "from django.http import JsonResponse\n"
            "from apps.core.extensions import MiddlewareExtender\n"
            "\n"
            "def annotate_request(request, next_handler):\n"
            "    request.alpha_trace = ['global']\n"
            "    response = next_handler(request)\n"
            "    response['X-Alpha-Global'] = '1'\n"
            "    return response\n"
            "\n"
            "def annotate_api_request(request, next_handler):\n"
            "    request.alpha_trace.append('api')\n"
            "    response = next_handler(request)\n"
            "    response['X-Alpha-Api'] = ','.join(request.alpha_trace)\n"
            "    return response\n"
            "\n"
            "def block_admin(request):\n"
            "    return JsonResponse({'blocked': True, 'target': 'admin'}, status=418)\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        MiddlewareExtender(mounts=(\n"
            "            ('global', annotate_request, 10),\n"
            "            ('api', annotate_api_request, 20),\n"
            "            ('admin', block_admin, 5),\n"
            "        )),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.create(
            extension_id="alpha-middleware",
            version="1.0.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )
        return temp_dir, ExtensionRegistry(extensions_path=extensions_dir)

    def test_extension_request_middleware_runs_global_and_api_targets(self):
        temp_dir, registry = self._build_middleware_extension_registry()
        try:
            request = RequestFactory().get("/api/demo")

            def get_response(inner_request):
                trace = list(getattr(inner_request, "alpha_trace", []))
                return JsonResponse({"trace": trace})

            middleware = ExtensionRequestMiddleware(get_response)

            with patch("apps.core.middleware.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content), {"trace": ["global", "api"]})
            self.assertEqual(response["X-Alpha-Global"], "1")
            self.assertEqual(response["X-Alpha-Api"], "global,api")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_request_middleware_can_short_circuit_admin_target(self):
        temp_dir, registry = self._build_middleware_extension_registry()
        try:
            request = RequestFactory().get("/api/admin/extensions")

            def get_response(_request):
                return HttpResponse("should not execute", status=200)

            middleware = ExtensionRequestMiddleware(get_response)

            with patch("apps.core.middleware.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                response = middleware(request)

            self.assertEqual(response.status_code, 418)
            self.assertEqual(json.loads(response.content), {"blocked": True, "target": "admin"})
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_error_handling_middleware_reports_and_reraises(self):
        from apps.core.middleware import ExtensionErrorHandlingMiddleware

        request = RequestFactory().get("/api/fail")
        reported = []

        def get_response(_request):
            raise ValueError("broken")

        middleware = ExtensionErrorHandlingMiddleware(get_response)

        with patch(
            "apps.core.extensions.system_runtime.report_runtime_error",
            side_effect=lambda exc, **kwargs: reported.append((exc, kwargs)),
        ):
            with self.assertRaises(ValueError):
                middleware(request)

        self.assertEqual(reported[0][0].args, ("broken",))
        self.assertEqual(reported[0][1]["request"], request)
        self.assertEqual(reported[0][1]["operation"], "request")

    def test_extension_error_handling_middleware_uses_typed_handler_response(self):
        from apps.core.extensions import ErrorHandlingExtender
        from apps.core.middleware import ExtensionErrorHandlingMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def handle_value_error(payload, context):
            return JsonResponse({"handled": payload["message"], "status": payload["http_status"]}, status=409)

        ErrorHandlingExtender() \
            .type(ValueError, "alpha_value_error") \
            .status("alpha_value_error", 409) \
            .handler(ValueError, handle_value_error) \
            .extend(app, extension)
        app.make("error.handling")

        request = RequestFactory().get("/api/fail")

        def get_response(_request):
            raise ValueError("broken")

        middleware = ExtensionErrorHandlingMiddleware(get_response)

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            response = middleware(request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content), {"handled": "broken", "status": 409})

    def test_extension_csrf_middleware_marks_exempt_runtime_route(self):
        from apps.core.extensions import CsrfExtender
        from apps.core.middleware import ExtensionCsrfMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        CsrfExtender().exempt_route("alpha-webhook").extend(app, extension)
        app.make("csrf")

        request = RequestFactory().post("/api/webhook")
        request.resolver_match = SimpleNamespace(url_name="alpha-webhook")
        middleware = ExtensionCsrfMiddleware(lambda current_request: HttpResponse("ok"))

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            result = middleware.process_view(request, None, (), {})

        self.assertIsNone(result)
        self.assertTrue(request._dont_enforce_csrf_checks)

    def test_extension_throttle_api_middleware_short_circuits_api_request(self):
        from apps.core.extensions import ThrottleApiExtender
        from apps.core.middleware import ExtensionThrottleApiMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        ThrottleApiExtender().set("alpha", lambda request: request.path == "/api/demo").extend(app, extension)
        app.make("throttle.api")

        request = RequestFactory().get("/api/demo")
        middleware = ExtensionThrottleApiMiddleware(lambda current_request: HttpResponse("ok"))

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            response = middleware.process_view(request, None, (), {})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.content), {"error": "请求过于频繁", "code": "rate_limit_exceeded"})


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

    def test_validate_extension_manifests_reports_mismatched_frontend_entry_paths(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/other-tools/frontend/admin/index.js",
                "frontend_forum_entry": "extensions/other-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_frontend_admin_entry_path" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_frontend_forum_entry_path" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_core_owned_frontend_contributions(self):
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
                "import { registerForumNavItem } from '@/forum/registry'\n"
                "export const extend = [{\n"
                "  extend() {\n"
                "    registerForumNavItem({ key: 'alpha', moduleId: 'core' })\n"
                "  },\n"
                "}]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_core_module_frontend_contribution"
                and item.field == "extensions/alpha-tools/frontend/forum/index.js"
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
                "export const setup = null\n",
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

    def test_validate_extension_manifests_reports_invalid_backend_and_migration_namespace(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            migrations_dir = backend_dir / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.other_tools.backend.ext",
                "migration_namespace": "extensions.other_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            (migrations_dir / "0001_initial.py").write_text(
                "def apply():\n"
                "    return 'ok'\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_backend_entry_namespace" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_migration_namespace" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_django_app_entry_imports(self):
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
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.posts import signals\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_django_app_entry_import" for item in result.issues))
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
        from apps.core.management.commands.extension_console import Command as ExtensionConsoleCommand
        from apps.core.management.commands.inspect_extensions import Command as InspectExtensionsCommand
        from apps.core.management.commands.validate_extensions import Command as ValidateExtensionsCommand

        self.assertEqual(CreateExtensionCommand.requires_system_checks, [])
        self.assertEqual(ExtensionConsoleCommand.requires_system_checks, [])
        self.assertEqual(InspectExtensionsCommand.requires_system_checks, [])
        self.assertEqual(ValidateExtensionsCommand.requires_system_checks, [])

    def test_extension_console_command_lists_and_runs_runtime_commands(self):
        commands = [{
            "name": "alpha:refresh",
            "description": "Refresh alpha",
            "handler": lambda options: {"ok": True, "scope": options.get("scope")},
        }]

        with patch("apps.core.management.commands.extension_console.list_runtime_console_commands", return_value=commands):
            stdout = StringIO()
            call_command("extension_console", "--list", "--format", "json", stdout=stdout)
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["commands"][0]["name"], "alpha:refresh")

        with patch("apps.core.management.commands.extension_console.list_runtime_console_schedules", return_value=[{
            "name": "alpha:refresh",
            "description": "Refresh alpha",
            "schedule": "hourly",
            "args": {"scope": "all"},
        }]):
            stdout = StringIO()
            call_command("extension_console", "--scheduled", "--format", "json", stdout=stdout)
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["schedules"][0]["schedule"], "hourly")

        with patch(
            "apps.core.management.commands.extension_console.run_runtime_console_command",
            return_value={"ok": True, "scope": "all"},
        ):
            stdout = StringIO()
            call_command(
                "extension_console",
                "alpha:refresh",
                "--payload",
                '{"scope":"all"}',
                "--format",
                "json",
                stdout=stdout,
            )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["result"], {"ok": True, "scope": "all"})

    @patch("apps.core.management.commands.validate_extensions.get_core_module_ids", return_value=("core",))
    def test_validate_extensions_command_uses_core_and_filesystem_extension_ids(self, get_core_module_ids_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                call_command("create_extension", "beta-tools")
                beta_manifest_path = Path(temp_dir) / "extensions" / "beta-tools" / "extension.json"
                beta_manifest = json.loads(beta_manifest_path.read_text(encoding="utf-8"))
                beta_manifest["dependencies"] = ["alpha-tools"]
                beta_manifest_path.write_text(json.dumps(beta_manifest, ensure_ascii=False), encoding="utf-8")
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        get_core_module_ids_mock.assert_called_once_with()

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
                self.assertNotIn("frontend_admin_entry", manifest)
                self.assertNotIn("frontend_forum_entry", manifest)
                self.assertEqual(manifest["migration_namespace"], "extensions.alpha_tools.backend.migrations")
                self.assertEqual(manifest["compatibility"]["bias_version"], "^1.0.0")
                self.assertEqual(manifest["compatibility"]["api_stability"], "experimental")
                self.assertEqual(manifest["distribution"]["channel"], "private")
                self.assertEqual(manifest["security"]["support_email"], "security@example.com")
                self.assertTrue((extension_dir / "frontend" / "admin" / "DetailPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "index.js").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "SettingsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "PermissionsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "admin" / "OperationsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "forum" / "index.js").exists())
                self.assertTrue((extension_dir / "backend" / "ext.py").exists())
                self.assertTrue((extension_dir / "backend" / "migrations" / "__init__.py").exists())
                self.assertTrue((extension_dir / "backend" / "migrations" / "0001_initial.py").exists())
                self.assertTrue((extension_dir / "docs" / "README.md").exists())
                self.assertTrue((extension_dir / "locale" / "zh-CN.json").exists())
                backend_source = (extension_dir / "backend" / "ext.py").read_text(encoding="utf-8")
                self.assertIn("def extend():", backend_source)
                self.assertIn("FrontendExtender(", backend_source)
                self.assertIn("SettingsExtender(fields=(", backend_source)
                self.assertIn("ApiResourceExtender('forum').fields(forum_resource_field_definitions)", backend_source)
                self.assertIn("ResourceFieldDefinition(", backend_source)
                self.assertIn("def resolve_forum_scaffold_status(forum, context):", backend_source)
                self.assertIn("RuntimeActionsExtender(actions=(", backend_source)
                self.assertIn("AdminNavigationExtender(generated_permissions_page=True)", backend_source)
                self.assertIn("LifecycleExtender(", backend_source)
                self.assertIn("def install(context):", backend_source)
                self.assertIn("def run_migrations(context):", backend_source)
                self.assertIn("def uninstall(context):", backend_source)
                admin_source = (extension_dir / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                forum_source = (extension_dir / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("from '@bias/admin'", admin_source)
                self.assertIn("export const extend", admin_source)
                self.assertIn("extendAdmin(admin => admin", admin_source)
                self.assertIn(".page({", admin_source)
                self.assertIn("from '@bias/forum'", forum_source)
                self.assertIn("extendForum(forum => forum", forum_source)
                self.assertIn(".navItem({", forum_source)
                migration_source = (extension_dir / "backend" / "migrations" / "0001_initial.py").read_text(encoding="utf-8")
                self.assertIn("def apply():", migration_source)
                readme_source = (extension_dir / "docs" / "README.md").read_text(encoding="utf-8")
                self.assertIn('ApiResourceExtender("forum")', readme_source)
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
                self.assertIn("import PermissionsPage from './PermissionsPage.vue'", entry_source)
                self.assertIn("export function resolvePermissionsPage()", entry_source)
                self.assertIn("extendAdmin(admin => admin", entry_source)
                self.assertIn(".page({", entry_source)
                forum_entry_source = (Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export const extend", forum_entry_source)
                self.assertIn("extendForum(forum => forum", forum_entry_source)
                self.assertIn(".navItem({", forum_entry_source)
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

    def test_validate_extensions_command_rejects_low_level_resource_extender_in_extension_source(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                backend_path = Path(temp_dir) / "extensions" / "alpha-tools" / "backend" / "ext.py"
                backend_path.write_text(
                    backend_path.read_text(encoding="utf-8")
                    + "\nfrom apps.core.extensions import ResourceExtender\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_external_project_name_residue_in_extension_source(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                backend_path = Path(temp_dir) / "extensions" / "alpha-tools" / "backend" / "ext.py"
                external_project_name = "fla" + "rum"
                backend_path.write_text(
                    backend_path.read_text(encoding="utf-8")
                    + f"\n# {external_project_name} naming residue must not enter Bias extensions\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_legacy_forum_frontend_extender(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                forum_path = Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "forum" / "index.js"
                forum_path.write_text(
                    "import { Forum } from '@bias/forum'\n\n"
                    "export const extend = [\n"
                    "  new Forum().navItem({ key: 'legacy-entry' }),\n"
                    "]\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_legacy_admin_frontend_extender(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                admin_path = Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "admin" / "index.js"
                admin_path.write_text(
                    "export const extend = [\n"
                    "  new Admin().page({ path: '/admin/legacy' }),\n"
                    "]\n"
                    "export function resolveDetailPage() { return null }\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_direct_admin_frontend_extender(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                admin_path = Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "admin" / "index.js"
                admin_path.write_text(
                    "export const extend = [\n"
                    "  new AdminExtender().page({ path: '/admin/direct' }),\n"
                    "]\n"
                    "export function resolveDetailPage() { return null }\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_legacy_admin_frontend_import(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                admin_path = Path(temp_dir) / "extensions" / "alpha-tools" / "frontend" / "admin" / "index.js"
                admin_path.write_text(
                    "import { AdminPage } from '@bias/admin'\n"
                    "import { extendAdmin } from '@bias/admin'\n\n"
                    "export const extend = [\n"
                    "  extendAdmin(admin => admin.page({ path: '/admin/current' })),\n"
                    "]\n"
                    "export function resolveDetailPage() { return null }\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
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

    def test_validate_extensions_command_can_emit_json_payload(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                stdout = StringIO()
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--format",
                    "json",
                    stdout=stdout,
                )

                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["summary"]["manifest_count"], 1)
                self.assertEqual(payload["summary"]["error_count"], 0)
                self.assertEqual(payload["summary"]["warning_count"], 0)
                self.assertTrue(payload["summary"]["ok"])
                self.assertEqual(payload["manifests"][0]["id"], "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_json_payload_still_fails_on_errors(self):
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

            stdout = StringIO()
            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 2 个错误"):
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--format",
                    "json",
                    stdout=stdout,
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["summary"]["error_count"], 2)
            self.assertFalse(payload["summary"]["ok"])
            self.assertTrue(any(item["code"] == "missing_dependency" for item in payload["issues"]))
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

    def test_inspect_extensions_command_outputs_extension_snapshot(self):
        stdout = StringIO()
        call_command("inspect_extensions", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertIn("summary", payload)
        self.assertIn("extensions", payload)
        self.assertIn("meta", payload)
        self.assertGreaterEqual(payload["summary"]["extension_count"], 1)
        self.assertIn("attention_count", payload["summary"])
        self.assertIn("blocking_count", payload["summary"])
        self.assertIn("warning_count", payload["summary"])
        self.assertIn("frontend_bundle_count", payload["summary"])
        self.assertIn("migration_bundle_count", payload["summary"])
        self.assertIn("diagnostics", payload["extensions"][0])
        self.assertTrue(any(item["id"] == "core" for item in payload["extensions"]))
        self.assertTrue(any(item["id"] == "sample-hello" for item in payload["extensions"]))

    def test_inspect_extensions_command_can_focus_single_extension_with_permissions(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "sample-hello",
            "--include-permissions",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["summary"]["extension_count"], 1)
        self.assertEqual(payload["meta"]["extension_id"], "sample-hello")
        self.assertEqual(payload["extensions"][0]["id"], "sample-hello")
        self.assertIn("permission_sections", payload["extensions"][0])
        self.assertIn("package_lock", payload)
        self.assertIn("summary", payload["package_lock"])
        self.assertIn("packages", payload["package_lock"])

    def test_inspect_extensions_command_reports_model_ownership_audit(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "tags",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]

        self.assertEqual(extension["id"], "tags")
        self.assertGreaterEqual(audit["owned_model_count"], 1)
        self.assertEqual(audit["django_app_count"], 0)
        self.assertTrue(any(item["storage_origin"] == "extension" for item in audit["items"]))
        self.assertTrue(any(item["model_module"].startswith("extensions.tags") for item in audit["items"]))
        self.assertIn("model_package_migration_required_count", extension["capability_summary"])

    def test_inspect_extensions_reports_notifications_as_extension_native_model(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "notifications",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]
        item = audit["items"][0]

        self.assertEqual(extension["id"], "notifications")
        self.assertIn("0001_record_model_ownership.py", extension["migration_plan"]["pending_files"])
        self.assertEqual(audit["owned_model_count"], 1)
        self.assertEqual(audit["extension_native_count"], 1)
        self.assertEqual(audit["django_app_count"], 0)
        self.assertEqual(audit["package_migration_required_count"], 0)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(item["model"], "Notification")
        self.assertEqual(item["model_module"], "extensions.notifications.backend.models")
        self.assertEqual(item["current_app_label"], "notifications")
        self.assertEqual(item["target_app_label"], "notifications")
        self.assertEqual(item["migration_risk"], "none")

    def test_inspect_extensions_reports_extension_model_app_label_gap(self):
        for extension_id in ("likes", "flags", "mentions"):
            stdout = StringIO()
            call_command(
                "inspect_extensions",
                "--extension-id",
                extension_id,
                stdout=stdout,
            )
            payload = json.loads(stdout.getvalue())
            extension = payload["extensions"][0]
            audit = extension["model_ownership_audit"]
            manifest = ExtensionRegistry(extensions_path=Path.cwd() / "extensions").get_extension(extension_id).manifest

            self.assertEqual(manifest.migration_namespace, f"extensions.{extension_id}.backend.migrations")
            self.assertIn("0001_record_model_ownership.py", extension["migration_plan"]["pending_files"])
            self.assertEqual(audit["extension_native_count"], 1)
            self.assertEqual(audit["app_label_migration_required_count"], 1)
            self.assertEqual(audit["app_label_migration_plan_required_count"], 1)
            self.assertTrue(all(item["storage_origin"] == "extension" for item in audit["items"]))
            self.assertTrue(all(item["model_module"].startswith(f"extensions.{extension_id}") for item in audit["items"]))
            self.assertEqual(len(audit["app_label_migration_items"]), 1)
            migration_item = audit["app_label_migration_items"][0]
            owned_item = audit["items"][0]
            self.assertEqual(owned_item["current_app_label"], "posts")
            self.assertEqual(owned_item["target_app_label"], extension_id)
            self.assertEqual(owned_item["migration_risk"], "high")
            self.assertEqual(migration_item["current_app_label"], "posts")
            self.assertEqual(migration_item["target_app_label"], extension_id)
            self.assertEqual(migration_item["db_table"], owned_item["db_table"])
            self.assertEqual(migration_item["migration_risk"], "high")
            self.assertTrue(migration_item["recommended_steps"])

    def test_inspect_extensions_reports_approval_migration_marker(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "approval",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        manifest = ExtensionRegistry(extensions_path=Path.cwd() / "extensions").get_extension("approval").manifest

        self.assertEqual(manifest.migration_namespace, "extensions.approval.backend.migrations")
        self.assertIn(
            "0001_record_core_hosted_approval_storage.py",
            extension["migration_plan"]["pending_files"],
        )

    def test_inspect_extensions_command_can_filter_attention_only(self):
        ExtensionInstallation.objects.create(
            extension_id="sample-hello",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={
                "migration_execution": {
                    "status": "error",
                    "status_label": "失败",
                    "message": "迁移执行失败",
                },
            },
        )

        stdout = StringIO()
        call_command("inspect_extensions", "--only-attention", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertGreaterEqual(payload["summary"]["attention_count"], 1)
        self.assertTrue(any(item["id"] == "sample-hello" for item in payload["extensions"]))

    def test_inspect_extensions_command_can_filter_blocking_only(self):
        ExtensionInstallation.objects.create(
            extension_id="sample-hello",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={
                "migration_execution": {
                    "status": "error",
                    "status_label": "失败",
                    "message": "迁移执行失败",
                },
            },
        )

        stdout = StringIO()
        call_command("inspect_extensions", "--only-blocking", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertGreaterEqual(payload["summary"]["blocking_count"], 1)
        self.assertTrue(all(item["diagnostics"]["blocking"] for item in payload["extensions"]))

    def test_inspect_extensions_command_reports_missing_extension(self):
        with self.assertRaisesMessage(CommandError, "扩展不存在: missing-extension"):
            call_command("inspect_extensions", "--extension-id", "missing-extension")


class ExtensionDiagnosticsTests(TestCase):
    def test_classify_extension_diagnostics_marks_pending_migration_plan_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "migration_plan": {
                "pending_files": ["0001_bootstrap.py"],
            },
            "delivery_checks": [],
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("迁移状态待完善", diagnostics["warning_reasons"])

    def test_classify_extension_diagnostics_marks_model_ownership_audit_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "model_ownership_audit": {
                "package_migration_required_count": 2,
                "app_label_migration_required_count": 1,
            },
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("扩展模型仍依赖 Django app 模块壳", diagnostics["warning_reasons"])
        self.assertIn("扩展模型 app label 尚未完全归属扩展", diagnostics["warning_reasons"])

    def test_summarize_extension_delivery_counts_frontend_migration_and_signed_assets(self):
        summary = summarize_extension_delivery([
            {
                "delivery_assets": {
                    "asset_count": 4,
                    "assets": [
                        {"key": "frontend_admin_entry", "exists": True},
                        {"key": "migrations", "exists": True},
                        {"key": "locale", "exists": False},
                    ],
                },
            },
            {
                "delivery_assets": {
                    "asset_count": 3,
                    "assets": [
                        {"key": "frontend_forum_entry", "exists": True},
                        {"key": "locale", "exists": True},
                        {"key": "signature", "exists": True},
                    ],
                },
            },
        ])

        self.assertEqual(summary["asset_count"], 7)
        self.assertEqual(summary["frontend_bundle_count"], 2)
        self.assertEqual(summary["migration_bundle_count"], 1)
        self.assertEqual(summary["locale_bundle_count"], 1)
        self.assertEqual(summary["signed_extension_count"], 1)


@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class ExtensionRegistryTests(TestCase):
    def test_safe_mode_filters_enabled_filesystem_extensions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id in ("alpha-tools", "beta-tools"):
                manifest_dir = extensions_dir / extension_id
                manifest_dir.mkdir(parents=True, exist_ok=True)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id,
                    "version": "1.0.0",
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id=extension_id,
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode",
                defaults={"value": json.dumps(True)},
            )
            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode_extensions",
                defaults={"value": json.dumps(["alpha-tools"])},
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            enabled_ids = [extension.id for extension in registry.get_enabled_extensions()]

            self.assertEqual(enabled_ids, ["alpha-tools"])
            recovery_state = serialize_extension_recovery_state()
            self.assertEqual(recovery_state["safe_mode"], True)
            self.assertEqual(recovery_state["safe_mode_extensions"], ["alpha-tools"])
            self.assertEqual(recovery_state["bisect"]["active"], False)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_safe_mode_filters_all_extension_runtime_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id in ("alpha-tools", "beta-tools"):
                manifest_dir = extensions_dir / extension_id
                backend_dir = manifest_dir / "backend"
                backend_dir.mkdir(parents=True, exist_ok=True)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id,
                    "version": "1.0.0",
                    "backend_entry": f"extensions.{extension_id.replace('-', '_')}.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text(
                    "from apps.core.extensions import ApiResourceExtender, EventListenersExtender, FrontendExtender, MiddlewareExtender\n"
                    "from apps.core.extensions.types import ExtensionEventListenerDefinition\n"
                    "from apps.core.resource_registry import ResourceEndpointDefinition\n"
                    "\n"
                    "class RuntimeEvent:\n"
                    "    pass\n"
                    "\n"
                    "def handle_event(event):\n"
                    "    return None\n"
                    "\n"
                    "def handle_endpoint(context):\n"
                    "    return {'ok': True}\n"
                    "\n"
                    "def demo_middleware(request):\n"
                    "    return request\n"
                    "\n"
                    "def extend():\n"
                    "    return [\n"
                    f"        FrontendExtender(forum_entry='extensions/{extension_id}/frontend/forum/index.js').route('/{extension_id}', '{extension_id}.route', './Page.vue'),\n"
                    f"        ApiResourceExtender('forum').endpoint(ResourceEndpointDefinition(resource='forum', endpoint='{extension_id}.endpoint', module_id='', handler=handle_endpoint)),\n"
                    "        EventListenersExtender((ExtensionEventListenerDefinition(RuntimeEvent, handle_event),)),\n"
                    "        MiddlewareExtender(mounts=(('api', demo_middleware, 30),)),\n"
                    "    ]\n",
                    encoding="utf-8",
                )
                ExtensionInstallation.objects.create(
                    extension_id=extension_id,
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode",
                defaults={"value": json.dumps(True)},
            )
            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode_extensions",
                defaults={"value": json.dumps(["alpha-tools"])},
            )

            app = build_extension_application(
                manager=ExtensionRegistry(extensions_path=extensions_dir),
                forum_registry=ForumRegistry(),
                resource_registry=ResourceRegistry(),
                event_bus=DomainEventBus(),
                force=True,
            )

            self.assertEqual([view.extension_id for view in app.get_runtime_views()], ["alpha-tools"])
            self.assertIsNotNone(app.get_frontend_extension("alpha-tools"))
            self.assertIsNone(app.get_frontend_extension("beta-tools"))
            self.assertEqual(
                [endpoint.endpoint for endpoint in app.resources.get_endpoints("forum")],
                ["alpha-tools.endpoint"],
            )
            self.assertEqual(len(app.events.get_listeners(extension_id="alpha-tools")), 1)
            self.assertEqual(app.events.get_listeners(extension_id="beta-tools"), [])
            self.assertEqual(len(app.get_middleware_mounts(target="api")), 1)
            self.assertEqual(app.get_middleware_mounts(target="api")[0].middleware.__name__, "demo_middleware")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_bisect_state_advances_to_candidate(self):
        from apps.core.extensions.recovery import (
            advance_extension_bisect,
            start_extension_bisect,
            stop_extension_bisect,
        )

        try:
            state = start_extension_bisect(["alpha", "beta", "gamma", "delta"])
            self.assertEqual(state["active"], True)
            self.assertEqual(state["current"], ["alpha", "beta"])

            state = advance_extension_bisect(issue_present=True)
            self.assertEqual(state["active"], True)
            self.assertEqual(state["current"], ["alpha"])

            state = advance_extension_bisect(issue_present=False)
            self.assertEqual(state["active"], False)
            self.assertEqual(state["culprit"], "beta")
        finally:
            stop_extension_bisect()

    def test_extension_bisect_rotates_enabled_extensions_and_restores_original_state(self):
        from apps.core.extensions.recovery import (
            advance_extension_bisect,
            start_extension_bisect,
            stop_extension_bisect,
        )

        for extension_id in ["alpha", "beta", "gamma", "delta"]:
            ExtensionInstallation.objects.create(
                extension_id=extension_id,
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

        try:
            state = start_extension_bisect(["alpha", "beta", "gamma", "delta"])
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["current"], ["alpha", "beta"])
            self.assertEqual(enabled_ids, ["alpha", "beta"])
            self.assertEqual(Setting.objects.get(key="advanced.maintenance_mode_key").value, '"low"')

            state = advance_extension_bisect(issue_present=True)
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["current"], ["alpha"])
            self.assertEqual(enabled_ids, ["alpha"])

            state = advance_extension_bisect(issue_present=False)
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["culprit"], "beta")
            self.assertEqual(enabled_ids, ["alpha", "beta", "delta", "gamma"])
            self.assertEqual(Setting.objects.get(key="advanced.maintenance_mode_key").value, '"none"')
        finally:
            stop_extension_bisect()

    def test_routes_extender_rejects_frontend_route_apps(self):
        from apps.core.extensions import RoutesExtender

        with self.assertRaisesMessage(ValueError, "FrontendExtender.route"):
            RoutesExtender("forum")

        with self.assertRaisesMessage(ValueError, "FrontendExtender.route"):
            RoutesExtender("admin")

    def test_runtime_invalidation_resets_runtime_and_url_caches(self):
        from apps.core.extensions.events import ExtensionDisabledEvent
        from apps.core.extensions.runtime_event_listeners import handle_extension_runtime_invalidation

        with patch("apps.core.extensions.frontend_runtime_service.clear_extension_frontend_runtime_cache") as clear_frontend, patch(
            "apps.core.extensions.locale_service.clear_extension_locale_cache"
        ) as clear_locale, patch(
            "apps.core.extensions.formatter_service.clear_extension_formatter_cache"
        ) as clear_formatter, patch(
            "apps.core.extensions.template_loader.clear_extension_template_caches"
        ) as clear_templates, patch(
            "apps.core.extensions.runtime_event_listeners.invalidate_extension_frontend_assets"
        ) as invalidate_assets, patch(
            "apps.core.extensions.lifecycle.reset_extension_runtime_state"
        ) as reset_runtime, patch(
            "apps.core.extensions.lifecycle.rebuild_runtime_urlconf"
        ) as rebuild_urlconf:
            handle_extension_runtime_invalidation(ExtensionDisabledEvent(extension_id="alpha-tools"))

        clear_frontend.assert_called_once_with()
        clear_locale.assert_called_once_with()
        clear_formatter.assert_called_once_with()
        clear_templates.assert_called_once_with()
        invalidate_assets.assert_called_once_with("extension_disabled", extension_id="alpha-tools")
        reset_runtime.assert_called_once_with()
        rebuild_urlconf.assert_called_once_with()

    def test_extension_frontend_listener_invalidates_assets_from_lifecycle_event(self):
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import ExtensionEnabledEvent
        from apps.core.extensions import formatter_service, frontend_runtime_service, locale_service

        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")
                frontend_runtime_service._frontend_runtime_catalog = {"stale": {}}
                frontend_runtime_service._frontend_runtime_bootstrapped = True
                locale_service._extension_locale_cache = [{"stale": True}]
                formatter_service._extension_formatter_pipeline_cache = {"render": [lambda value: value]}

                bootstrap_extension_runtime_event_listeners()
                get_extension_event_bus().dispatch(ExtensionEnabledEvent(extension_id="alpha-tools"))

                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_enabled", marker.value)
                self.assertIn("alpha-tools", marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
                self.assertEqual(frontend_runtime_service._frontend_runtime_catalog, {})
                self.assertFalse(frontend_runtime_service._frontend_runtime_bootstrapped)
                self.assertIsNone(locale_service._extension_locale_cache)
                self.assertEqual(formatter_service._extension_formatter_pipeline_cache, {})
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_runtime_cache_clear_event_refreshes_extension_frontend_assets(self):
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import RuntimeCacheClearedEvent

        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")

                bootstrap_extension_runtime_event_listeners()
                get_extension_event_bus().dispatch(RuntimeCacheClearedEvent())

                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("runtime_cache_cleared", marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_clear_runtime_cache_command_refreshes_extension_frontend_assets(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")

                stdout = StringIO()
                call_command("clear_runtime_cache", stdout=stdout)

                self.assertIn("[OK] 已清理运行时缓存", stdout.getvalue())
                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("runtime_cache_cleared", marker.value)
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_enabling_event_can_block_install_before_side_effects(self):
        from apps.core.domain_events import DomainEventBus
        from apps.core.extensions import event_bus as extension_event_bus_module
        from apps.core.extensions.events import ExtensionEnablingEvent

        previous_bus = extension_event_bus_module._extension_event_bus
        extension_event_bus_module._extension_event_bus = DomainEventBus()
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                assets_dir = manifest_dir / "assets"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                assets_dir.mkdir(parents=True, exist_ok=False)
                (assets_dir / "logo.txt").write_text("asset", encoding="utf-8")
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

                def block_enable(event):
                    if event.extension_id == "alpha-tools":
                        raise ExtensionStateError(
                            "blocked by pre-enable listener",
                            code="extension_enable_blocked_by_listener",
                        )

                extension_event_bus_module.get_extension_event_bus().register(ExtensionEnablingEvent, block_enable)
                registry = ExtensionRegistry(extensions_path=extensions_dir)

                with self.assertRaises(ExtensionStateError):
                    registry.install_extension("alpha-tools")

                self.assertFalse(ExtensionInstallation.objects.filter(extension_id="alpha-tools").exists())
                self.assertFalse((Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt").exists())
                self.assertFalse(Setting.objects.filter(key="extensions_runtime_rebuild_required").exists())
        finally:
            extension_event_bus_module._extension_event_bus = previous_bus
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_disabling_event_can_block_disable_before_side_effects(self):
        from apps.core.domain_events import DomainEventBus
        from apps.core.extensions import event_bus as extension_event_bus_module
        from apps.core.extensions.events import ExtensionDisablingEvent

        previous_bus = extension_event_bus_module._extension_event_bus
        extension_event_bus_module._extension_event_bus = DomainEventBus()
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                assets_dir = manifest_dir / "assets"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                assets_dir.mkdir(parents=True, exist_ok=False)
                (assets_dir / "logo.txt").write_text("asset", encoding="utf-8")
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

                registry = ExtensionRegistry(extensions_path=extensions_dir)
                registry.install_extension("alpha-tools")
                published_file = Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt"
                self.assertTrue(published_file.exists())

                def block_disable(event):
                    if event.extension_id == "alpha-tools":
                        raise ExtensionStateError(
                            "blocked by pre-disable listener",
                            code="extension_disable_blocked_by_listener",
                        )

                extension_event_bus_module.get_extension_event_bus().register(ExtensionDisablingEvent, block_disable)

                with self.assertRaises(ExtensionStateError):
                    registry.set_extension_enabled("alpha-tools", False)

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                self.assertTrue(installation.enabled)
                self.assertTrue(installation.booted)
                self.assertTrue(published_file.exists())
        finally:
            extension_event_bus_module._extension_event_bus = previous_bus
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_uninstall_runs_declared_migration_rollback(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                migrations_dir = backend_dir / "migrations"
                migrations_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                    "migration_namespace": "extensions.alpha_tools.backend.migrations",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")
                (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
                (migrations_dir / "0001_bootstrap.py").write_text(
                    "from pathlib import Path\n"
                    "\n"
                    "def apply():\n"
                    "    Path('migration-up.txt').write_text('up', encoding='utf-8')\n"
                    "    return 'up'\n"
                    "\n"
                    "def rollback():\n"
                    "    Path('migration-down.txt').write_text('down', encoding='utf-8')\n"
                    "    return 'down'\n",
                    encoding="utf-8",
                )

                registry = ExtensionRegistry(extensions_path=extensions_dir)
                installed = registry.install_extension("alpha-tools")
                self.assertEqual(installed.runtime.backend_hooks["run_migrations"]["details"]["direction"], "up")

                registry.set_extension_enabled("alpha-tools", False)
                reenabled = registry.set_extension_enabled("alpha-tools", True)
                self.assertEqual(reenabled.runtime.backend_hooks["run_migrations"]["details"]["direction"], "up")
                self.assertEqual(
                    reenabled.runtime.backend_hooks["run_migrations"]["details"]["skipped_migration_files"],
                    ["0001_bootstrap.py"],
                )

                uninstalled = registry.uninstall_extension("alpha-tools")

                self.assertFalse(uninstalled.runtime.installed)
                self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "skipped")
                self.assertEqual(uninstalled.runtime.backend_hooks["rollback_migrations"]["details"]["direction"], "down")
                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                self.assertEqual(installation.meta["applied_migration_files"], [])
                self.assertTrue((Path.cwd() / "migration-up.txt").exists())
                self.assertTrue((Path.cwd() / "migration-down.txt").exists())
        finally:
            for path in (Path.cwd() / "migration-up.txt", Path.cwd() / "migration-down.txt"):
                if path.exists():
                    path.unlink()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_registry_exposes_filesystem_extensions_only(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extensions = registry.get_extensions()

        extension_ids = {item.id for item in extensions}
        self.assertNotIn("core", extension_ids)
        self.assertNotIn("posts", extension_ids)
        self.assertIn("sample-hello", extension_ids)
        self.assertTrue(all(item.source == "filesystem" for item in extensions))

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

        emoji_extension = next(item for item in extensions if item.id == "emoji")
        self.assertEqual(emoji_extension.source, "filesystem")
        self.assertTrue(emoji_extension.runtime.installed)
        self.assertTrue(emoji_extension.runtime.enabled)
        self.assertEqual(emoji_extension.runtime.status_key, "active")

    def test_filesystem_tags_extension_registers_extension_settings_page(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("tags")

        self.assertEqual(extension.source, "filesystem")
        self.assertEqual(extension.manifest.frontend_admin_entry, "")
        self.assertEqual(extension.frontend_admin_entry, "extensions/tags/frontend/admin/index.js")
        self.assertEqual(extension.settings_pages, ("/admin/extensions/tags/settings",))

    def test_runtime_probe_prefers_contract_frontend_entries(self):
        manifest = ExtensionManifest(
            id="contract-first",
            name="Contract First",
            version="1.0.0",
            frontend_admin_entry="",
            frontend_forum_entry="",
            path=str(Path.cwd() / "extensions" / "sample-hello"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/contract-first/frontend/admin/index.js",
                frontend_forum_entry="extensions/contract-first/frontend/forum/index.js",
                path=str(Path.cwd() / "extensions" / "sample-hello"),
            ),
            source="filesystem",
        )

        payload = inspect_extension_runtime(extension)

        checks = {item.key: item for item in payload["delivery_checks"]}
        self.assertEqual(checks["frontend-admin-entry"].status, "ready")
        self.assertEqual(checks["frontend-forum-entry"].status, "ready")

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

    def test_registry_merges_filesystem_extension_contract_capabilities(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

        self.assertEqual(extension.module_ids, ("emoji",))
        self.assertEqual(extension.settings_schema[0].key, "cdn_url")

    def test_runtime_service_exposes_enabled_extension_runtime_entries(self):
        entries = get_enabled_extension_runtime_entries(product_visible_only=True)

        emoji = next(item for item in entries if item["id"] == "emoji")
        self.assertEqual(emoji["frontend_forum_entry"], "extensions/emoji/frontend/forum/index.js")
        self.assertEqual(emoji["module_ids"], ["emoji"])
        self.assertEqual(emoji["forum_settings"], {"cdn_url": "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"})
        self.assertIn("extensions/emoji/locale", emoji["locale_paths"])
        self.assertFalse(any(item["id"] == "sample-hello" for item in entries))

    def test_frontend_runtime_bootstrap_builds_enabled_extension_entries(self):
        from apps.core.extensions import frontend_runtime_service

        frontend_runtime_service._frontend_runtime_catalog = {}
        frontend_runtime_service._frontend_runtime_bootstrapped = False
        bootstrap_extension_frontend_runtime()

        entries = frontend_runtime_service.get_enabled_extension_runtime_entries(product_visible_only=True)
        emoji = next(item for item in entries if item["id"] == "emoji")
        self.assertEqual(emoji["frontend_forum_entry"], "extensions/emoji/frontend/forum/index.js")
        self.assertEqual(emoji["forum_settings"], {"cdn_url": "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"})

    def test_frontend_runtime_bootstrap_registers_static_catalog_without_settings_query(self):
        from apps.core.extensions import frontend_runtime_service

        frontend_runtime_service._frontend_runtime_catalog = {}
        frontend_runtime_service._frontend_runtime_bootstrapped = False

        with patch("apps.core.extensions.frontend_runtime_service.get_extension_settings") as get_extension_settings_mock:
            bootstrap_extension_frontend_runtime()

        get_extension_settings_mock.assert_not_called()
        self.assertIn("emoji", frontend_runtime_service._frontend_runtime_catalog)

    def test_extension_runtime_state_refreshes_after_enable_toggle(self):
        reset_extension_runtime_state()
        entries = get_enabled_extension_runtime_entries(product_visible_only=True)
        self.assertTrue(any(item["id"] == "emoji" for item in entries))

        with patch("apps.core.extension_service.reset_extension_runtime_state") as reset_runtime_mock:
            ExtensionService.set_extension_enabled("emoji", False)

        reset_runtime_mock.assert_called_once()

    def test_extension_assembly_service_orders_enabled_extensions_by_dependency(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"

            alpha_dir = extensions_dir / "alpha-base"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-base",
                "name": "Alpha Base",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_base.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            beta_dir = extensions_dir / "beta-addon"
            beta_backend_dir = beta_dir / "backend"
            beta_backend_dir.mkdir(parents=True, exist_ok=False)
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-addon",
                "name": "Beta Addon",
                "version": "1.0.0",
                "dependencies": ["alpha-base"],
                "backend_entry": "extensions.beta_addon.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (beta_backend_dir / "ext.py").write_text(
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-base",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            ExtensionInstallation.objects.create(
                extension_id="beta-addon",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            ordered = get_enabled_extension_assemblies(force=True, registry=registry)

            ordered_ids = [item.extension_id for item in ordered if item.extension_id in {"alpha-base", "beta-addon"}]
            self.assertEqual(ordered_ids, ["alpha-base", "beta-addon"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_settings_runtime_service_exposes_extension_settings_definition(self):
        definitions = get_enabled_extension_settings_definitions()
        emoji = get_extension_settings_definition("emoji")

        self.assertIn("emoji", definitions)
        self.assertEqual(emoji["defaults"]["cdn_url"], "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/")
        self.assertEqual(emoji["forum_settings_keys"], ("cdn_url",))
        self.assertEqual(emoji["fields"][0].key, "cdn_url")

    @patch("apps.core.extensions.lifecycle.invalidate_extension_frontend_assets")
    @patch("apps.core.extensions.frontend_runtime_service.clear_extension_frontend_runtime_cache")
    def test_extension_settings_default_reset_and_frontend_cache_invalidation(
        self,
        clear_frontend_runtime_cache,
        invalidate_frontend_assets,
    ):
        from apps.core.extension_settings_service import get_extension_settings, save_extension_settings

        default_cdn = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"

        self.assertEqual(get_extension_settings("emoji")["cdn_url"], default_cdn)

        saved = save_extension_settings("emoji", {"cdn_url": "https://cdn.example.com/twemoji/"})

        self.assertEqual(saved["cdn_url"], "https://cdn.example.com/twemoji/")
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.emoji.cdn_url").value),
            "https://cdn.example.com/twemoji/",
        )
        clear_frontend_runtime_cache.assert_called()
        invalidate_frontend_assets.assert_called_with(
            "extension_settings_changed",
            extension_id="emoji",
        )

        clear_frontend_runtime_cache.reset_mock()
        invalidate_frontend_assets.reset_mock()

        reset = save_extension_settings("emoji", {"cdn_url": ""})

        self.assertEqual(reset["cdn_url"], default_cdn)
        self.assertFalse(Setting.objects.filter(key="extensions.emoji.cdn_url").exists())
        clear_frontend_runtime_cache.assert_called()
        invalidate_frontend_assets.assert_called_with(
            "extension_settings_changed",
            extension_id="emoji",
        )

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
            source="filesystem",
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
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        resource_registry = get_resource_registry()

        self.assertFalse(any(item.module_id == "flags" for item in resource_registry.get_fields("post")))
        self.assertFalse(any(item.module_id == "flags" for item in resource_registry.get_fields("admin_stats")))
        self.assertFalse(any(item.module_id == "flags" for item in resource_registry.get_fields("user_detail")))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("post", "report", "POST", {}))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("post", "flags/resolve", "POST", {}))

    def test_registry_filters_tag_capabilities_when_extension_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="tags",
            version="1.0.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        resource_registry = get_resource_registry()
        forum_registry = get_forum_registry()

        self.assertFalse(any(item.module_id == "tags" for item in resource_registry.get_fields("discussion")))
        self.assertFalse(any(item.module_id == "tags" for item in resource_registry.get_relationships("discussion")))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("tag", "index", "GET", {}))
        self.assertFalse(any(item.module_id == "tags" for item in forum_registry.get_search_filters()))

    def test_registry_filters_notification_capabilities_when_extension_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="notifications",
            version="1.0.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        resource_registry = get_resource_registry()
        forum_registry = get_forum_registry()

        self.assertIsNone(resource_registry.get_dispatch_endpoint("notification", "read", "POST", {}))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("notification", "index", "GET", {}))
        self.assertFalse(any(item.module_id == "notifications" for item in forum_registry.get_notification_types()))

    def test_registry_filters_likes_and_mentions_when_extensions_disabled(self):
        for extension_id in ("likes", "mentions"):
            ExtensionInstallation.objects.create(
                extension_id=extension_id,
                version="1.0.0",
                source="filesystem",
                enabled=False,
                installed=True,
                booted=False,
            )

        resource_registry = get_resource_registry()
        forum_registry = get_forum_registry()

        self.assertFalse(any(item.module_id == "likes" for item in resource_registry.get_fields("post")))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("post", "like", "POST", {}))
        self.assertFalse(any(item.module_id == "mentions" for item in forum_registry.get_search_filters()))
        self.assertFalse(any(item.module_id == "mentions" for item in forum_registry.get_notification_types()))

    def test_runtime_omits_event_listeners_and_post_lifecycle_when_flags_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="flags",
            version="1.0.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        from apps.core.extensions.bootstrap import bootstrap_extension_host

        try:
            application = bootstrap_extension_host(force=True)

            self.assertEqual(application.post_lifecycle.get_definitions(extension_id="flags"), [])
            self.assertEqual(application.events.get_listeners(extension_id="flags"), [])
        finally:
            reset_extension_application_bootstrap_state()


@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
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

    def test_extensions_api_returns_filesystem_extension_snapshot(self):
        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("extensions", payload)
        self.assertGreaterEqual(payload["summary"]["extension_count"], 1)
        self.assertGreaterEqual(payload["summary"]["filesystem_count"], 1)
        self.assertGreaterEqual(payload["summary"]["product_visible_count"], 1)
        self.assertIn("blocking_count", payload["summary"])
        self.assertIn("warning_count", payload["summary"])
        self.assertIn("attention_count", payload["summary"])
        self.assertIn("frontend_bundle_count", payload["summary"])
        self.assertIn("migration_bundle_count", payload["summary"])

        extension_ids = {item["id"] for item in payload["extensions"]}
        self.assertNotIn("core", extension_ids)
        self.assertNotIn("discussions", extension_ids)
        self.assertNotIn("posts", extension_ids)
        self.assertNotIn("users", extension_ids)
        self.assertNotIn("realtime", extension_ids)
        self.assertIn("tags", extension_ids)
        self.assertIn("sample-hello", extension_ids)

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "sample-hello")
        self.assertEqual(sample_extension["source"], "filesystem")
        self.assertFalse(sample_extension["product_visible"])
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
        self.assertTrue(any(action["action"] == "hook:run_rebuild_cache" for action in sample_extension["runtime_actions"]))

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
        self.assertEqual(payload["operations_profile"]["kicker"], "Sample Runtime")
        self.assertIn("settings", payload["operations_profile"]["recommended_action_keys"])
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["settings_schema"]))
        self.assertEqual(payload["settings_values"]["welcome_message"], "欢迎使用 Sample Hello")
        self.assertIn("diagnostics", payload)
        self.assertIn("delivery_assets", payload)
        self.assertGreaterEqual(payload["delivery_assets"]["asset_count"], 4)
        self.assertTrue(any(item["key"] == "backend_entry" and item["exists"] for item in payload["delivery_assets"]["assets"]))
        self.assertTrue(any(item["key"] == "frontend_admin_entry" and item["exists"] for item in payload["delivery_assets"]["assets"]))
        self.assertTrue(payload["diagnostics"]["warning"])
        self.assertFalse(payload["diagnostics"]["blocking"])
        self.assertIn("迁移状态待完善", payload["diagnostics"]["warning_reasons"])
        self.assertTrue(any(item["key"] == "migrations" for item in payload["delivery_checks"]))
        self.assertTrue(any("不会自动回滚数据库迁移" in item for item in payload["uninstall_warnings"]))
        self.assertIsNone(payload["migration_execution"])
        self.assertEqual(payload["debug_info"]["manifest_path"], str(Path(settings.BASE_DIR) / "extensions" / "sample-hello"))
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

    @patch("apps.core.admin_content_api.get_extension_settings", return_value={})
    @patch("apps.core.admin_content_api.serialize_extension_settings_schema", return_value=[])
    @patch("apps.core.admin_content_api.get_extension_registry")
    def test_extension_detail_api_prefers_contract_runtime_surfaces(
        self,
        get_extension_registry_mock,
        _serialize_extension_settings_schema,
        _get_extension_settings,
    ):
        manifest = ExtensionManifest(
            id="contract-first",
            name="Contract First",
            version="1.0.0",
            frontend_admin_entry="",
            frontend_forum_entry="",
            settings_pages=(),
            permissions_pages=(),
            operations_pages=(),
            admin_actions=(),
            path=str(Path.cwd() / "extensions" / "sample-hello"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/sample-hello/frontend/admin/index.js",
                frontend_forum_entry="extensions/sample-hello/frontend/forum/index.js",
                settings_pages=("/admin/extensions/contract-first/settings",),
                permissions_pages=("/admin/extensions/contract-first/permissions",),
                operations_pages=("/admin/extensions/contract-first/operations",),
                admin_actions=(
                    ExtensionAdminActionDefinition(
                        key="settings",
                        label="设置",
                        kind="route",
                        target="/admin/extensions/contract-first/settings",
                        order=20,
                    ),
                ),
                path=str(Path.cwd() / "extensions" / "sample-hello"),
            ),
            source="filesystem",
        )
        get_extension_registry_mock.return_value = SimpleNamespace(
            extensions_path=Path.cwd() / "extensions",
            get_extension=lambda extension_id: extension,
            get_extensions=lambda: [extension],
        )

        response = self.client.get(
            "/api/admin/extensions/contract-first",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_admin_entry"], "extensions/sample-hello/frontend/admin/index.js")
        self.assertEqual(payload["frontend_forum_entry"], "extensions/sample-hello/frontend/forum/index.js")
        self.assertEqual(payload["settings_pages"], ["/admin/extensions/contract-first/settings"])
        self.assertEqual(payload["permissions_pages"], ["/admin/extensions/contract-first/permissions"])
        self.assertEqual(payload["operations_pages"], ["/admin/extensions/contract-first/operations"])
        self.assertEqual(payload["action_links"]["settings_page"], "/admin/extensions/contract-first/settings")
        self.assertEqual(payload["action_links"]["permissions_page"], "/admin/extensions/contract-first/permissions")
        self.assertEqual(payload["action_links"]["operations_page"], "/admin/extensions/contract-first/operations")
        self.assertEqual(payload["admin_actions"][0]["key"], "settings")
        self.assertTrue(any(
            item["key"] == "settings"
            and item["declared"] == "/admin/extensions/contract-first/settings"
            for item in payload["debug_info"]["route_bindings"]
        ))

    def test_extension_detail_api_returns_not_found_for_core_discussions_module(self):
        response = self.client.get(
            "/api/admin/extensions/discussions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["code"], "extension_not_found")

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

    def test_extensions_api_ignores_stale_core_installation_dependency_record(self):
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
            source="core-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        response = self.client.post(
            "/api/admin/extensions/sample-hello/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        sample_extension = next(item for item in payload["extensions"] if item["id"] == "sample-hello")
        self.assertTrue(sample_extension["enabled"])

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

    def test_extensions_api_uninstall_disables_enabled_extension_first(self):
        self.client.post(
            "/api/admin/extensions/sample-hello/install",
            **self.auth_header(),
        )

        response = self.client.post(
            "/api/admin/extensions/sample-hello/uninstall",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        extension = next(item for item in payload["extensions"] if item["id"] == "sample-hello")
        self.assertFalse(extension["installed"])
        self.assertFalse(extension["enabled"])
        hooks = {item["hook"]: item for item in extension["backend_hooks"]}
        self.assertEqual(hooks["run_disable"]["status"], "ok")
        self.assertEqual(hooks["run_uninstall"]["status"], "ok")


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

        uninstalled = ExtensionService.uninstall_extension("sample-hello")
        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "ok")
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")

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

    def test_enable_ignores_stale_core_installation_dependency_record(self):
        ExtensionService.install_extension("sample-hello")
        ExtensionInstallation.objects.update_or_create(
            extension_id="core",
            defaults={
                "version": "1.0.0",
                "source": "core-module",
                "enabled": False,
                "installed": True,
                "booted": False,
            },
        )

        enabled = ExtensionService.set_extension_enabled("sample-hello", True)

        self.assertTrue(enabled.runtime.enabled)

    def test_disable_raises_when_enabled_dependents_exist(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("notifications", False)

        self.assertEqual(context.exception.code, "extension_disable_blocked")
        self.assertIn("approval", context.exception.details["blocking_dependents"])

    def test_uninstall_disables_enabled_extension_first(self):
        installed = ExtensionService.install_extension("sample-hello")
        self.assertTrue(installed.runtime.enabled)

        uninstalled = ExtensionService.uninstall_extension("sample-hello")

        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "ok")
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")

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
    def test_runtime_reset_clears_extension_event_listeners_and_restores_core_listeners(self):
        bus = get_forum_event_bus()
        bus.clear()

        def handle_tag_refresh(event):
            return None

        bus.register(TagStatsRefreshRequestedEvent, handle_tag_refresh)
        self.assertIn(TagStatsRefreshRequestedEvent, bus._listeners)

        reset_extension_runtime_state()

        self.assertNotIn(handle_tag_refresh, bus._listeners.get(TagStatsRefreshRequestedEvent, []))
        self.assertIn(DiscussionCreatedEvent, bus._listeners)

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
    def test_api_resource_extender_registers_resource_in_bias_api_resources_contract(self):
        class ContractResource(Resource):
            def type(self):
                return "contract"

        app = ExtensionApplication()
        extension = app.get_or_create_runtime_view("alpha-tools")
        ApiResourceExtender.from_resource(ContractResource).extend(app, extension)

        self.assertIn(ContractResource, app.make("bias.api.resources"))

    def test_endpoint_definition_builds_own_pipeline(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="hello"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return QuerySet([item for item in self if str(item.id) == str(kwargs.get("pk"))])

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "pipeline_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

        resource = ItemResource()
        definition = ResourceEndpointDefinition(
            resource="pipeline_items",
            endpoint="show",
            module_id="core",
            kind="show",
        )
        pipeline = definition.build_pipeline(registry, resource)
        context = ResourceContext({"object_id": "1", "include": ()}).with_resource("pipeline_items")

        result = pipeline.action(context)

        self.assertEqual(result.title, "hello")

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

    def test_resource_definition_mutators_raise_for_invalid_return_type(self):
        registry = ResourceRegistry()
        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="title",
                module_id="core",
                resolver=lambda instance, context: "title",
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="title",
                module_id="extension",
                mutator=lambda field: {"name": "title"},
            )
        )

        with self.assertRaises(TypeError):
            registry.get_effective_fields("discussion")

    def test_resource_validator_supports_laravel_like_rules(self):
        validator = ResourceValidatorFactory().make(
            {
                "title": "hello",
                "slug": "hello",
                "status": "archived",
                "summary": "abcd",
            },
            {
                "slug": ("same:title",),
                "status": (("not_in", ("deleted",)),),
                "summary": ("size:4", "different:title"),
            },
        )

        self.assertFalse(validator.fails())

    def test_resource_validator_supports_nested_wildcard_rules(self):
        validator = ResourceValidatorFactory().make(
            {
                "items": [
                    {"name": "alpha"},
                    {"name": ""},
                ],
            },
            {
                "items.*.name": ("required",),
            },
        )

        self.assertTrue(validator.fails())
        self.assertEqual(validator.jsonapi_errors()[0]["source"]["pointer"], "/data/attributes/items.1.name")

    def test_resource_relationship_exposes_schema_field_api(self):
        relationship = (
            ResourceRelationship("owner", resolver=lambda instance, context: instance.owner)
            .to_one("users")
            .include_when(lambda context: context.get("include_owner"))
            .with_linkage(lambda value, context: {"type": "users", "id": str(value.id)})
        )

        self.assertEqual(relationship.field, "owner")
        self.assertTrue(relationship.is_relationship)
        self.assertEqual(relationship.collections(), ("users",))
        self.assertTrue(relationship.is_includable({"include_owner": True}))
        self.assertEqual(relationship.linkage_value(SimpleNamespace(id=7), {}), {"type": "users", "id": "7"})

    def test_search_manager_resolves_filters_and_mutators_from_container(self):
        app = ExtensionApplication()

        def filter_handler(state, value, context):
            state.queryset = [item for item in state.queryset if item == value]
            return state

        def mutator(state, criteria):
            state.queryset = [f"mutated:{item}" for item in state.queryset]
            return state

        app.instance("alpha.search.filter", ResourceSearchFilter("only", filter_handler))
        app.instance("alpha.search.mutator", mutator)
        manager = ResourceSearchManager(container=app)
        manager.register_searcher(str, lambda queryset, criteria, context: queryset, searcher_key="strings")
        manager.register_driver_filter("database", "strings", "alpha.search.filter")
        manager.add_driver_mutator("database", "strings", "alpha.search.mutator")

        result = manager.query(
            str,
            ["a", "b"],
            ResourceSearchCriteria(filters={"only": "b"}),
            {},
        )

        self.assertEqual(result.results, ["mutated:b"])

    def test_search_manager_registers_driver_class_contract(self):
        manager = ResourceSearchManager()

        class DemoDriver:
            name = "demo"

            def supports(self, model):
                return False

        manager.register_driver_class(DemoDriver)

        self.assertIn(DemoDriver, manager.driver_classes())
        self.assertIsInstance(manager.driver("demo"), DemoDriver)

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

    def test_resource_object_defines_base_fields_relationships_endpoints_and_sorts(self):
        registry = ResourceRegistry()

        class Target:
            id = 8
            title = "hello"
            owner = type("Owner", (), {"username": "neo"})()

        class DiscussionResource(Resource):
            module_id = "core"

            def type(self):
                return "discussion"

            def base(self, instance, context):
                return {"id": instance.id}

            def fields(self):
                return [
                    ResourceField(
                        "title",
                        resolver=lambda instance, context: instance.title,
                        select_related=("state",),
                    ),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: {"username": instance.owner.username},
                        select_related=("owner",),
                    ),
                ]

            def endpoints(self):
                return [
                    ResourceEndpoint(
                        "show",
                        handler=lambda context: {"endpoint": context["endpoint"]},
                    )
                ]

            def sorts(self):
                return [
                    ResourceSort("hot", handler=("-hot_score",)),
                ]

        registry.register_resource(DiscussionResource)

        payload = registry.serialize("discussion", Target(), include=("owner",))
        plan = registry.build_preload_plan("discussion", include=("owner",))
        endpoint = registry.get_dispatch_endpoint("discussion", "show", "GET")

        self.assertEqual(payload, {"id": 8, "title": "hello", "owner": {"username": "neo"}})
        self.assertEqual(plan.select_related, ("state", "owner"))
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.handler({"endpoint": "show"}), {"endpoint": "show"})
        self.assertTrue(registry.has_named_sort("discussion", "hot"))

    def test_resource_object_surfaces_are_mutated_by_bias_like_definitions(self):
        registry = ResourceRegistry()

        class Target:
            title = "hello"
            owner = type("Owner", (), {"username": "neo"})()

        class DiscussionResource(Resource):
            def type(self):
                return "discussion"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: {"username": instance.owner.username},
                        select_related=("owner",),
                    ),
                ]

            def endpoints(self):
                return [
                    ResourceEndpoint("show", handler=lambda context: {"version": 1}),
                ]

            def sorts(self):
                return [
                    ResourceSort("hot", handler=("hot",)),
                ]

        registry.register_resource(DiscussionResource())
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="title",
                module_id="extension",
                operation="mutate",
                mutator=lambda field: ResourceFieldDefinition(
                    resource="discussion",
                    field=field.field,
                    module_id="extension",
                    resolver=lambda instance, context: instance.title.upper(),
                ),
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="owner",
                module_id="extension",
                operation="mutate",
                mutator=lambda relationship: ResourceRelationshipDefinition(
                    resource="discussion",
                    relationship=relationship.relationship,
                    module_id="extension",
                    resolver=lambda instance, context: {"username": instance.owner.username.upper()},
                    select_related=("profile",),
                ),
            )
        )
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="show",
                module_id="extension",
                operation="mutate",
                mutator=lambda endpoint: ResourceEndpointDefinition(
                    resource=endpoint.resource,
                    endpoint=endpoint.endpoint,
                    module_id=endpoint.module_id,
                    handler=lambda context: {"version": 2},
                ),
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="hot",
                module_id="extension",
                operation="mutate",
                mutator=lambda sort: ResourceSortDefinition(
                    resource=sort.resource,
                    sort=sort.sort,
                    module_id=sort.module_id,
                    handler=("-hot_score",),
                ),
            )
        )

        payload = registry.serialize("discussion", Target(), include=("owner",))
        plan = registry.build_preload_plan("discussion", include=("owner",))
        endpoint = registry.get_dispatch_endpoint("discussion", "show", "GET")
        queryset = Mock()
        ordered_queryset = Mock()
        queryset.order_by.return_value = ordered_queryset

        self.assertEqual(payload, {"title": "HELLO", "owner": {"username": "NEO"}})
        self.assertEqual(plan.select_related, ("profile",))
        self.assertEqual(endpoint.handler({}), {"version": 2})
        self.assertIs(registry.apply_named_sort("discussion", queryset, "hot"), ordered_queryset)
        queryset.order_by.assert_called_once_with("-hot_score")

    def test_resource_object_fields_support_visibility_and_write_pipeline(self):
        registry = ResourceRegistry()

        class Target:
            title = "hello"
            secret = "hidden"

        def validate_title(value, context):
            if len(value) < 3:
                raise ValueError("too short")

        class DemoResource(Resource):
            def type(self):
                return "demo"

            def fields(self):
                return [
                    ResourceField(
                        "title",
                        resolver=lambda instance, context: instance.title,
                        writable=True,
                        required_on_create=True,
                        setter=lambda instance, value, context: setattr(instance, "title", value.strip()),
                        validator=validate_title,
                    ),
                    ResourceField(
                        "secret",
                        resolver=lambda instance, context: instance.secret,
                        visible=lambda instance, context: context.get("show_secret") is True,
                    ),
                ]

        registry.register_resource(DemoResource())
        target = Target()

        self.assertEqual(registry.serialize("demo", target), {"title": "hello"})
        self.assertEqual(
            registry.serialize("demo", target, {"show_secret": True}),
            {"title": "hello", "secret": "hidden"},
        )
        registry.apply_resource_payload("demo", target, {"title": " updated "}, creating=True)
        self.assertEqual(target.title, "updated")
        with self.assertRaises(ValueError):
            registry.apply_resource_payload("demo", target, {"title": "x"})
        with self.assertRaises(ValueError):
            registry.apply_resource_payload("demo", target, {}, creating=True)

    def test_resource_relationship_includable_controls_include_and_preload(self):
        registry = ResourceRegistry()

        class Target:
            owner = type("Owner", (), {"username": "neo"})()

        class DemoResource(Resource):
            def type(self):
                return "demo"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: {"username": instance.owner.username},
                        includable=lambda context: context.get("can_include") is True,
                        select_related=("owner",),
                    )
                ]

        registry.register_resource(DemoResource())

        self.assertEqual(registry.serialize("demo", Target(), include=("owner",)), {})
        self.assertEqual(registry.build_preload_plan("demo", include=("owner",)).select_related, ())
        self.assertEqual(
            registry.serialize("demo", Target(), {"can_include": True}, include=("owner",)),
            {"owner": {"username": "neo"}},
        )
        self.assertEqual(
            registry.build_preload_plan("demo", {"can_include": True}, include=("owner",)).select_related,
            ("owner",),
        )

    def test_resource_endpoint_metadata_builds_preload_plan(self):
        registry = ResourceRegistry()

        class DemoResource(Resource):
            def type(self):
                return "demo"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: None,
                        select_related=("owner",),
                    )
                ]

            def endpoints(self):
                return [
                    ResourceEndpoint(
                        "show",
                        handler=lambda context: {"include": context["default_include"]},
                    )
                    .add_default_include(["owner"])
                    .eager_load_with("comments")
                    .with_default_sort("-created_at")
                    .with_pagination()
                ]

        registry.register_resource(DemoResource())

        endpoint = registry.get_dispatch_endpoint("demo", "show", "GET")
        plan = registry.build_endpoint_preload_plan("demo", "show", {"method": "GET"})

        self.assertEqual(endpoint.default_include, ("owner",))
        self.assertEqual(endpoint.default_sort, "-created_at")
        self.assertTrue(endpoint.paginate)
        self.assertEqual(plan.select_related, ("owner",))
        self.assertEqual(plan.prefetch_related, ("comments",))

    def test_resource_registry_ignores_non_filesystem_installation_state_overrides(self):
        registry = ResourceRegistry()

        registry.register_field(ResourceFieldDefinition(
            resource="discussion",
            field="core_runtime_field",
            module_id="core",
            resolver=lambda instance, context: True,
        ))
        ExtensionInstallation.objects.create(
            extension_id="core",
            version="1.0.0",
            source="core-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        fields = registry.get_fields("discussion")

        self.assertTrue(any(item.field == "core_runtime_field" for item in fields))

    def test_resource_extender_resolves_endpoint_pipeline_callbacks(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class BeforeHook:
            def __call__(self, context):
                context["seen_before"] = True

        class ResponseCallback:
            def __call__(self, context, response):
                return {
                    "response": response,
                    "seen_before": context.get("seen_before"),
                }

        endpoint = ResourceEndpointDefinition(
            resource="demo",
            endpoint="custom",
            module_id="",
            handler=lambda context: {"ok": True},
            before_hook=BeforeHook,
            response_callback=ResponseCallback,
        )

        ResourceExtender(endpoints=(endpoint,)).extend(app, extension)
        resources = app.make("resources")
        definition = resources.get_dispatch_endpoint("demo", "custom", "GET")

        self.assertEqual(definition.module_id, "alpha-tools")
        self.assertIsNot(definition.before_hook, BeforeHook)
        self.assertIsNot(definition.response_callback, ResponseCallback)
        context = {}
        definition.before_hook(context)
        self.assertEqual(definition.response_callback(context, {"ok": True}), {
            "response": {"ok": True},
            "seen_before": True,
        })

    def test_api_resource_extender_supports_string_resource_endpoint_helpers(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        ApiResourceExtender("post").add_default_include(("index", "show"), ("flags",)).extend(app, extension)
        resources = app.make("resources")
        endpoint = ResourceEndpointDefinition(
            resource="post",
            endpoint="index",
            module_id="core",
            kind="index",
        )

        mutated = resources.apply_endpoint_mutators("post", "index", endpoint)

        self.assertEqual(mutated.default_include, ("flags",))

    def test_resource_endpoint_runner_applies_hooks_to_custom_handlers(self):
        from apps.core.resource_endpoint_runner import ResourceEndpointRunner

        registry = ResourceRegistry()
        events = []

        definition = ResourceEndpointDefinition(
            resource="demo",
            endpoint="custom",
            module_id="alpha-tools",
            handler=lambda context: {
                "data": {"ok": context["prepared"]},
                "queried": context["queried"],
                "included": context["include"],
                "sort": context["sort"],
                "filters": context["filters"],
            },
            default_include=("owner",),
            default_sort="-created_at",
            query_callback=lambda context: context.with_value("queried", True),
            action_callback=lambda context: {**context["result"], "action": True},
            before_serialization_callback=lambda context, result: {**result, "serialized": True},
            before_hook=lambda context: (events.append("before"), context.update({"prepared": True})),
            after_hook=lambda context, result: {**result, "meta": {"after": True}},
            response_callback=lambda context, response: {**response, "links": {"self": "/demo/custom"}},
        )

        response = ResourceEndpointRunner(registry).run(definition, {
            "query": {
                "filter[state]": "open",
            },
        })

        self.assertEqual(events, ["before"])
        self.assertEqual(response["data"], {"ok": True})
        self.assertTrue(response["queried"])
        self.assertTrue(response["action"])
        self.assertTrue(response["serialized"])
        self.assertEqual(response["included"], ("owner",))
        self.assertEqual(response["sort"], "-created_at")
        self.assertEqual(response["filters"], {"state": "open"})
        self.assertEqual(response["meta"], {"after": True})
        self.assertEqual(response["links"], {"self": "/demo/custom"})

    def test_resource_endpoint_eager_loads_when_included_and_where_callbacks(self):
        registry = ResourceRegistry()

        def visible_comments(queryset, context):
            return queryset

        class DemoResource(Resource):
            def type(self):
                return "eager_demo"

            def endpoints(self):
                return [
                    ResourceEndpoint.index()
                    .add_default_include(["owner"])
                    .eager_load_when_included("owner", "owner__profile")
                    .eager_load_where("comments", visible_comments)
                ]

        registry.register_resource(DemoResource())

        plan = registry.build_endpoint_preload_plan("eager_demo", "index", {"method": "GET"})

        self.assertIn("owner__profile", plan.prefetch_related)
        self.assertIn("comments", plan.prefetch_related)
        self.assertEqual(plan.prefetch_where, (("comments", visible_comments),))

    def test_endpoint_where_eager_load_builds_prefetch_before_serialization(self):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint
        from django.db.models import Prefetch

        registry = ResourceRegistry()
        seen = {}

        class RelationManager:
            def all(self):
                return ["base-queryset"]

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id
                self.comments = RelationManager()

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        def only_visible(queryset, context):
            seen["queryset"] = queryset
            return queryset

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "where_eager_items"

            def endpoints(self):
                return [ResourceEndpoint.index().eager_load_where("comments", only_visible)]

        resource = ItemResource()
        definition = ResourceEndpointDefinition(
            resource="where_eager_items",
            endpoint="index",
            module_id="test",
            kind="index",
            methods=("GET",),
            eager_load_where_rules=(("comments", only_visible),),
        )
        endpoint = DatabaseResourceEndpoint(registry, resource, definition)

        with patch("django.db.models.prefetch_related_objects") as prefetch:
            endpoint.before_serialize_includes(ResourceContext({"resource": "where_eager_items"}), [Item()])

        prefetch_arg = prefetch.call_args.args[1]
        self.assertIsInstance(prefetch_arg, Prefetch)
        self.assertEqual(seen["queryset"], ["base-queryset"])

    def test_database_resource_lifecycle_hooks_wrap_save_and_delete_actions(self):
        events = []

        class Instance:
            def save(self):
                events.append("save")

            def delete(self):
                events.append("delete")

        class DemoDatabaseResource(DatabaseResource):
            def type(self):
                return "demo"

            def creating(self, instance, context):
                events.append("creating")
                return instance

            def saving(self, instance, context):
                events.append("saving")
                return instance

            def saved(self, instance, context):
                events.append("saved")
                return instance

            def created(self, instance, context):
                events.append("created")
                return instance

            def updating(self, instance, context):
                events.append("updating")
                return instance

            def updated(self, instance, context):
                events.append("updated")
                return instance

            def deleting(self, instance, context):
                events.append("deleting")

            def deleted(self, instance, context):
                events.append("deleted")

        resource = DemoDatabaseResource()

        resource.create_action(Instance(), {})
        resource.update_action(Instance(), {})
        resource.delete_action(Instance(), {})

        self.assertEqual(
            events,
            [
                "creating",
                "saving",
                "save",
                "saved",
                "created",
                "updating",
                "saving",
                "save",
                "saved",
                "updated",
                "deleting",
                "delete",
                "deleted",
            ],
        )

    def test_database_resource_crud_endpoints_dispatch_without_custom_handlers(self):
        registry = ResourceRegistry()
        events = []

        class Item:
            objects = None

            def __init__(self, id=None, title=""):
                self.id = id
                self.title = title
                self.deleted = False

            def save(self):
                events.append(("save", self.title))

            def delete(self):
                self.deleted = True
                events.append(("delete", self.id))

        class QuerySet(list):
            def filter(self, **kwargs):
                if "pk" in kwargs:
                    return QuerySet([item for item in self if str(item.id) == str(kwargs["pk"])])
                return self

            def first(self):
                return self[0] if self else None

            def order_by(self, *fields):
                events.append(("order_by", fields))
                return self

            def select_related(self, *fields):
                events.append(("select_related", fields))
                return self

            def prefetch_related(self, *fields):
                events.append(("prefetch_related", fields))
                return self

            def __getitem__(self, item):
                result = super().__getitem__(item)
                if isinstance(item, slice):
                    return QuerySet(result)
                return result

        class Manager:
            def __init__(self, items):
                self.items = items

            def all(self):
                return QuerySet(self.items)

        items = [Item(1, "first"), Item(2, "second"), Item(3, "third-page")]
        Item.objects = Manager(items)

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "item"

            def base(self, instance, context):
                return {"id": instance.id}

            def fields(self):
                return [
                    ResourceField(
                        "title",
                        resolver=lambda instance, context: instance.title,
                        writable=True,
                        required_on_create=True,
                    ),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: {"id": "owner"},
                        resource_type="users",
                        select_related=("owner",),
                    ),
                ]

            def endpoints(self):
                return [
                    ResourceEndpoint.index().add_default_include(["owner"]).with_default_sort("recent").with_pagination(default_limit=1, max_limit=2),
                    ResourceEndpoint.show(),
                    ResourceEndpoint.create().add_default_include(["owner"]),
                    ResourceEndpoint.update(),
                    ResourceEndpoint.delete(),
                ]

            def sorts(self):
                return [ResourceSort("recent", handler=("-id",))]

            def new_model(self, context):
                item = Item(4)
                items.append(item)
                return item

            def created(self, instance, context):
                events.append(("created", instance.title))
                return instance

            def updated(self, instance, context):
                events.append(("updated", instance.title))
                return instance

        registry.register_resource(ItemResource())

        index_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("item", "index", "GET"),
            {"resource": "item", "endpoint": "index", "method": "GET", "query": {"page[offset]": "1", "page[limit]": "2"}},
        )
        show_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("item", "show", "GET"),
            {"resource": "item", "endpoint": "show", "method": "GET", "object_id": "1", "query": {}},
        )
        create_status, create_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("item", "create", "POST"),
            {"resource": "item", "endpoint": "create", "method": "POST", "payload": {"data": {"type": "item", "attributes": {"title": "third"}}}, "query": {}},
        )
        update_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("item", "update", "PATCH"),
            {"resource": "item", "endpoint": "update", "method": "PATCH", "object_id": "1", "payload": {"data": {"type": "item", "id": "1", "attributes": {"title": "updated"}}}, "query": {}},
        )
        delete_status, delete_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("item", "delete", "DELETE"),
            {"resource": "item", "endpoint": "delete", "method": "DELETE", "object_id": "2", "query": {}},
        )

        self.assertEqual(
            index_payload["data"][0],
            {
                "type": "item",
                "id": "2",
                "links": {"self": "/api/item/2"},
                "attributes": {"title": "second"},
                "relationships": {"owner": {"data": {"type": "users", "id": "owner"}}},
            },
        )
        self.assertNotIn("included", index_payload)
        self.assertEqual(index_payload["data"][1]["id"], "3")
        self.assertEqual(index_payload["meta"], {"total": 3, "count": 2, "limit": 2, "offset": 1})
        self.assertEqual(
            show_payload,
            {
                "data": {
                    "type": "item",
                    "id": "1",
                    "links": {"self": "/api/item/1"},
                    "attributes": {"title": "first"},
                    "relationships": {"owner": {"data": {"type": "users", "id": "owner"}}},
                }
            },
        )
        self.assertEqual(create_status, 201)
        self.assertEqual(
            create_payload,
            {
                "data": {
                    "type": "item",
                    "id": "4",
                    "links": {"self": "/api/item/4"},
                    "attributes": {"title": "third"},
                    "relationships": {"owner": {"data": {"type": "users", "id": "owner"}}},
                },
            },
        )
        self.assertEqual(
            update_payload,
            {
                "data": {
                    "type": "item",
                    "id": "1",
                    "links": {"self": "/api/item/1"},
                    "attributes": {"title": "updated"},
                    "relationships": {"owner": {"data": {"type": "users", "id": "owner"}}},
                }
            },
        )
        self.assertEqual(delete_status, 204)
        self.assertIsNone(delete_payload)
        self.assertTrue(items[1].deleted)
        self.assertIn(("created", "third"), events)
        self.assertIn(("updated", "updated"), events)

    def test_database_resource_crud_parses_jsonapi_attributes_and_relationships(self):
        registry = ResourceRegistry()
        relationship_updates = []

        class Item:
            objects = None

            def __init__(self, id=None, title=""):
                self.id = id
                self.title = title
                self.owner = None

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item(1, "first")])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "jsonapi_item"

            def base(self, instance, context):
                return {"id": instance.id}

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title, writable=True),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        writable=True,
                    ).set_relationship_with(
                        lambda instance, value, context: (
                            relationship_updates.append(value),
                            setattr(instance, "owner", value),
                        )
                    ),
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("jsonapi_item", "update", "PATCH"),
            {
                "resource": "jsonapi_item",
                "endpoint": "update",
                "method": "PATCH",
                "object_id": "1",
                "payload": {
                    "data": {
                        "type": "jsonapi_item",
                        "id": "1",
                        "attributes": {"title": "updated"},
                        "relationships": {"owner": {"data": {"type": "users", "id": "7"}}},
                    }
                },
                "query": {"include": "owner"},
            },
        )

        self.assertEqual(payload["data"]["attributes"]["title"], "updated")
        self.assertEqual(payload["data"]["relationships"]["owner"]["data"], {"type": "users", "id": "7"})
        self.assertEqual(relationship_updates, [{"type": "users", "id": "7"}])

    def test_database_resource_crud_validates_field_schema_before_writing(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=None, title="", score=0):
                self.id = id
                self.title = title
                self.score = score

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item(1, "first", 1)])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "validated_item"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title, writable=True)
                    .string()
                    .required_on_create_field()
                    .min_length(3)
                    .max_length(20),
                    ResourceField("score", resolver=lambda instance, context: instance.score, writable=True)
                    .integer()
                    .min(0)
                    .max(10),
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("validated_item", "update", "PATCH")

        with self.assertRaises(ValueError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "validated_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"data": {"type": "validated_item", "id": "1", "attributes": {"title": "ok", "score": 3}}},
                    "query": {},
                },
            )
        with self.assertRaises(ValueError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "validated_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"data": {"type": "validated_item", "id": "1", "attributes": {"title": "valid", "score": "high"}}},
                    "query": {},
                },
            )

        payload = registry.dispatch_resource_endpoint(
            endpoint,
            {
                "resource": "validated_item",
                "endpoint": "update",
                "method": "PATCH",
                "object_id": "1",
                "payload": {"data": {"type": "validated_item", "id": "1", "attributes": {"title": "valid", "score": 7}}},
                "query": {},
            },
        )

        self.assertEqual(payload["data"]["attributes"], {"title": "valid", "score": 7})

    def test_database_resource_crud_validates_relationship_schema(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=None):
                self.id = id
                self.owner = None

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item(1)])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "validated_relationship_item"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        writable=True,
                        resource_type="users",
                    )
                    .object()
                    .required_on_update_field()
                    .set_relationship_with(lambda instance, value, context: setattr(instance, "owner", value))
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("validated_relationship_item", "update", "PATCH")

        with self.assertRaises(ValueError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "validated_relationship_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"data": {"type": "validated_relationship_item", "id": "1", "relationships": {}}},
                    "query": {},
                },
            )
        with self.assertRaises(ValueError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "validated_relationship_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"data": {"type": "validated_relationship_item", "id": "1", "relationships": {"owner": {"data": "bad"}}}},
                    "query": {},
                },
            )

        payload = registry.dispatch_resource_endpoint(
            endpoint,
            {
                "resource": "validated_relationship_item",
                "endpoint": "update",
                "method": "PATCH",
                "object_id": "1",
                "payload": {"data": {"type": "validated_relationship_item", "id": "1", "relationships": {"owner": {"data": {"type": "users", "id": "7"}}}}},
                "query": {},
            },
        )

        self.assertEqual(payload["data"]["relationships"]["owner"]["data"], {"type": "users", "id": "7"})

    def test_database_resource_crud_checks_object_level_ability(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "ability_item"

            def endpoints(self):
                return [ResourceEndpoint.show().can("view")]

            def can(self, user, ability, instance, context):
                return bool(user and getattr(user, "can_view", False))

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("ability_item", "show", "GET")

        with self.assertRaises(PermissionError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {"resource": "ability_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(can_view=False), "query": {}},
            )

        payload = registry.dispatch_resource_endpoint(
            endpoint,
            {"resource": "ability_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(can_view=True), "query": {}},
        )
        self.assertEqual(payload, {"data": {"type": "ability_item", "id": "1", "links": {"self": "/api/ability_item/1"}}})

    def test_resource_endpoint_can_keeps_dotted_ability_as_resource_policy(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "dotted_ability_item"

            def endpoints(self):
                return [ResourceEndpoint.show().can("secure.view")]

            def can(self, user, ability, instance, context):
                return ability == "secure.view" and getattr(user, "allowed", False)

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("dotted_ability_item", "show", "GET")

        with self.assertRaises(PermissionError):
            registry.dispatch_resource_endpoint(
                endpoint,
                {"resource": "dotted_ability_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(allowed=False), "query": {}},
            )

        payload = registry.dispatch_resource_endpoint(
            endpoint,
            {"resource": "dotted_ability_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(allowed=True), "query": {}},
        )
        self.assertEqual(payload, {"data": {"type": "dotted_ability_item", "id": "1", "links": {"self": "/api/dotted_ability_item/1"}}})

    def test_resource_endpoint_can_uses_global_and_model_policies_before_resource_can(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "policy_item"

            def endpoints(self):
                return [ResourceEndpoint.show().can("view")]

            def can(self, user, ability, instance, context):
                return False

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("policy_item", "show", "GET")
        app = ExtensionApplication(resource_registry=registry)
        app.policies.global_policy("alpha", lambda **context: True if context["ability"] == "view" else None)

        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            payload = registry.dispatch_resource_endpoint(
                endpoint,
                {"resource": "policy_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(is_authenticated=True), "query": {}},
            )

        self.assertEqual(payload, {"data": {"type": "policy_item", "id": "1", "links": {"self": "/api/policy_item/1"}}})

        app = ExtensionApplication(resource_registry=registry)
        app.policies.model_policy("alpha", Item, lambda **context: False if context["ability"] == "view" else None)
        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            with self.assertRaises(PermissionError):
                registry.dispatch_resource_endpoint(
                    endpoint,
                    {"resource": "policy_item", "endpoint": "show", "method": "GET", "object_id": "1", "user": SimpleNamespace(is_authenticated=True), "query": {}},
                )

    def test_resource_endpoint_hooks_meta_and_links_are_applied_to_default_crud(self):
        registry = ResourceRegistry()
        events = []

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "hooked_item"

            def endpoints(self):
                return [
                    ResourceEndpoint.show()
                    .before(lambda context: events.append(("before", context["endpoint"])))
                    .after(lambda context, item: events.append(("after", getattr(item, "id", None))) or item)
                    .meta(lambda context, item: {"hooked": True})
                    .links(lambda context, item: {"related": "/api/hooked_item/related"})
                ]

        registry.register_resource(ItemResource())
        payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("hooked_item", "show", "GET"),
            {"resource": "hooked_item", "endpoint": "show", "method": "GET", "object_id": "1", "query": {}},
        )

        self.assertEqual(events, [("before", "show"), ("after", 1)])
        self.assertEqual(payload["meta"], {"hooked": True})
        self.assertEqual(payload["links"], {"related": "/api/hooked_item/related"})

    def test_jsonapi_document_serializes_relationship_linkage_and_included_resources(self):
        registry = ResourceRegistry()

        class UserModel:
            def __init__(self, id, username):
                self.id = id
                self.username = username

        class DiscussionModel:
            def __init__(self, id, title, owner):
                self.id = id
                self.title = title
                self.owner = owner

        class UserResource(Resource):
            def type(self):
                return "users"

            def fields(self):
                return [
                    ResourceField("username", resolver=lambda instance, context: instance.username),
                ]

        class DiscussionResource(Resource):
            def type(self):
                return "discussions"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        resource_type="users",
                    ),
                ]

        owner = UserModel(7, "neo")
        registry.register_resource(UserResource())
        registry.register_resource(DiscussionResource())

        payload = registry.serialize_jsonapi_document(
            "discussions",
            [DiscussionModel(1, "first", owner), DiscussionModel(2, "second", owner)],
            include=("owner",),
            many=True,
        )

        self.assertEqual(
            payload["data"][0],
            {
                "type": "discussions",
                "id": "1",
                "links": {"self": "/api/discussions/1"},
                "attributes": {"title": "first"},
                "relationships": {"owner": {"data": {"type": "users", "id": "7"}}},
            },
        )
        self.assertEqual(payload["included"], [{"type": "users", "id": "7", "links": {"self": "/api/users/7"}, "attributes": {"username": "neo"}}])

    def test_jsonapi_document_adds_self_links_and_resolves_related_resource_from_model(self):
        registry = ResourceRegistry()

        class UserModel:
            def __init__(self, id, username):
                self.id = id
                self.username = username

        class DiscussionModel:
            def __init__(self, id, owner):
                self.id = id
                self.owner = owner

        class UserResource(DatabaseResource):
            model = UserModel

            def type(self):
                return "linked_users"

            def fields(self):
                return [ResourceField("username", resolver=lambda instance, context: instance.username)]

        class DiscussionResource(Resource):
            def type(self):
                return "linked_discussions"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                    ),
                ]

        registry.register_resource(UserResource())
        registry.register_resource(DiscussionResource())

        payload = registry.serialize_jsonapi_document(
            "linked_discussions",
            DiscussionModel(4, UserModel(7, "neo")),
            {"api_base_path": "/api"},
            include=("owner",),
        )

        self.assertEqual(payload["data"]["links"]["self"], "/api/linked_discussions/4")
        self.assertEqual(payload["data"]["relationships"]["owner"]["data"], {"type": "linked_users", "id": "7"})
        self.assertEqual(payload["included"][0]["links"]["self"], "/api/linked_users/7")

    def test_nested_include_contributes_nested_preload_plan(self):
        registry = ResourceRegistry()

        class OwnerResource(Resource):
            def type(self):
                return "nested_owner"

            def fields(self):
                return [
                    ResourceRelationship(
                        "profile",
                        resolver=lambda instance, context: getattr(instance, "profile", None),
                        resource_type="nested_profile",
                        select_related=("profile",),
                    )
                ]

        class DiscussionResource(Resource):
            def type(self):
                return "nested_discussion"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: getattr(instance, "owner", None),
                        resource_type="nested_owner",
                        select_related=("owner",),
                    )
                ]

        registry.register_resource(OwnerResource())
        registry.register_resource(DiscussionResource())

        plan = registry.build_preload_plan("nested_discussion", include=("owner.profile",))
        self.assertIn("owner", plan.select_related)
        self.assertIn("owner__profile", plan.select_related)

    def test_jsonapi_serializer_resolves_deferred_field_and_relationship_values(self):
        registry = ResourceRegistry()

        class UserModel:
            def __init__(self, id, username):
                self.id = id
                self.username = username

        class DiscussionModel:
            def __init__(self, id, owner):
                self.id = id
                self.owner = owner

        class UserResource(Resource):
            def type(self):
                return "deferred_users"

            def fields(self):
                return [ResourceField("username", resolver=lambda instance, context: lambda: instance.username)]

        class DiscussionResource(Resource):
            def type(self):
                return "deferred_discussions"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: lambda: "deferred title"),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: lambda: instance.owner,
                        resource_type="deferred_users",
                    ),
                ]

        registry.register_resource(UserResource())
        registry.register_resource(DiscussionResource())

        payload = registry.serialize_jsonapi_document(
            "deferred_discussions",
            DiscussionModel(1, UserModel(7, "neo")),
            include=("owner",),
        )

        self.assertEqual(payload["data"]["attributes"]["title"], "deferred title")
        self.assertEqual(payload["data"]["relationships"]["owner"]["data"], {"type": "deferred_users", "id": "7"})
        self.assertEqual(payload["included"][0]["attributes"]["username"], "neo")

    def test_resource_modifiers_apply_parent_before_child_like_upstream_extendable(self):
        registry = ResourceRegistry()

        class BaseResource(Resource):
            def fields(self):
                return [ResourceField("base", resolver=lambda instance, context: "base")]

        class ChildResource(BaseResource):
            def type(self):
                return "extendable_child"

            def fields(self):
                return [*super().fields(), ResourceField("child", resolver=lambda instance, context: "child")]

        registry.register_resource_modifier(
            BaseResource,
            "fields",
            lambda fields, resource: [*fields, ResourceField("from_base_modifier", resolver=lambda instance, context: "base-mod")],
        )
        registry.register_resource_modifier(
            ChildResource,
            "fields",
            lambda fields, resource: [*fields, ResourceField("from_child_modifier", resolver=lambda instance, context: "child-mod")],
        )
        registry.register_resource(ChildResource())

        fields = [field.field for field in registry.get_effective_fields("extendable_child")]
        self.assertEqual(fields, ["base", "child", "from_base_modifier", "from_child_modifier"])

    def test_resource_modifiers_are_deduped_and_can_be_reset(self):
        registry = ResourceRegistry()

        class DemoResource(Resource):
            def type(self):
                return "modifier_reset_demo"

            def fields(self):
                return [ResourceField("base", resolver=lambda instance, context: "base")]

        def add_field(fields, resource):
            return [*fields, ResourceField("extra", resolver=lambda instance, context: "extra")]

        registry.register_resource_modifier(DemoResource, "fields", add_field)
        registry.register_resource_modifier(DemoResource, "fields", add_field)
        registry.register_resource(DemoResource())

        self.assertEqual(
            [field.field for field in registry.get_effective_fields("modifier_reset_demo")],
            ["base", "extra"],
        )

        registry.reset_resource_modifiers(DemoResource, "fields")

        self.assertEqual(
            [field.field for field in registry.get_effective_fields("modifier_reset_demo")],
            ["base"],
        )

    def test_resource_class_level_modifiers_resolve_like_upstream_extendable(self):
        registry = ResourceRegistry()

        class DemoResource(Resource):
            def type(self):
                return "class_modifier_demo"

            def fields(self):
                return [ResourceField("base", resolver=lambda instance, context: "base")]

        def add_extra(fields, resource):
            return [*fields, ResourceField("extra", resolver=lambda instance, context: "extra")]

        DemoResource.mutate_fields(add_extra)
        registry.register_resource(DemoResource())

        try:
            self.assertEqual(
                [field.field for field in registry.get_effective_fields("class_modifier_demo")],
                ["base", "extra"],
            )
        finally:
            DemoResource.reset_modifiers("fields")

    def test_resource_extender_resolves_import_path_callbacks_like_upstream_container(self):
        registry = ResourceRegistry()
        app = ExtensionApplication(resource_registry=registry)
        extension = SimpleNamespace(extension_id="path-ext")

        extender = ResourceExtender(
            fields=(
                ExtensionResourceFieldDefinition(
                    resource="path_resource",
                    field="username",
                    module_id="",
                    resolver="apps.core.tests.resolve_test_username",
                ),
            )
        )
        extender.extend(app, extension)
        app.make("resources")

        user = SimpleNamespace(username="neo")
        self.assertEqual(registry.serialize("path_resource", user), {"username": user.username})

    def test_api_resource_extender_accepts_bias_style_callable_groups(self):
        registry = ResourceRegistry()
        app = ExtensionApplication(resource_registry=registry)
        extension = SimpleNamespace(extension_id="bias-api")

        class ItemResource(Resource):
            def type(self):
                return "bias_api_items"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceRelationship("owner", resolver=lambda instance, context: instance.owner),
                    ResourceRelationship("legacy_owner", resolver=lambda instance, context: instance.owner),
                ]

            def endpoints(self):
                return [ResourceEndpoint.show()]

            def filters(self):
                return [ResourceFilter("state", handler=lambda queryset, value, context: queryset)]

            def sorts(self):
                return [ResourceSort("created", handler="created_at")]

        extender = (
            ApiResourceExtender.from_resource(ItemResource)
            .fields(lambda: [ResourceField("slug", resolver=lambda instance, context: instance.slug)])
            .relationship(
                "owner",
                lambda relationship: ResourceRelationshipDefinition(
                    resource=relationship.resource,
                    relationship=relationship.relationship,
                    module_id=relationship.module_id,
                    resolver=relationship.resolver,
                    description="mutated owner",
                ),
            )
            .relationships_after(
                "owner",
                ResourceRelationshipDefinition(
                    resource="bias_api_items",
                    relationship="last_editor",
                    module_id="bias-api",
                    resolver=lambda instance, context: None,
                ),
            )
            .remove_relationships("legacy_owner")
            .endpoints(lambda: [ResourceEndpoint.index()])
            .filters_before_all(
                ResourceFilterDefinition(
                    resource="bias_api_items",
                    filter="first",
                    module_id="bias-api",
                    handler=lambda queryset, value, context: queryset,
                ),
            )
            .filters_after(
                "state",
                ResourceFilterDefinition(
                    resource="bias_api_items",
                    filter="after_state",
                    module_id="bias-api",
                    handler=lambda queryset, value, context: queryset,
                ),
            )
            .sorts(lambda: [ResourceSort("hot", handler="score")])
        )
        extender.extend(app, extension)
        app.make("resources")

        self.assertEqual(
            [field.field for field in registry.get_effective_fields("bias_api_items")],
            ["title", "slug"],
        )
        self.assertEqual(
            [endpoint.endpoint for endpoint in registry.get_dispatch_endpoints("bias_api_items")],
            ["show", "index"],
        )
        self.assertEqual(
            [(relationship.relationship, relationship.description) for relationship in registry.get_effective_relationships("bias_api_items")],
            [("owner", "mutated owner"), ("last_editor", "")],
        )
        self.assertEqual(
            [item.filter for item in registry.get_effective_filters("bias_api_items")],
            ["first", "state", "after_state"],
        )
        self.assertEqual(
            [sort.sort for sort in registry.get_effective_sorts("bias_api_items")],
            ["created", "hot"],
        )

    def test_container_resolver_injects_services_by_constructor_name(self):
        from apps.core.extensions.container import resolve_container_value

        class NeedsResources:
            def __init__(self, resources):
                self.resources = resources

        app = ExtensionApplication()
        resolved = resolve_container_value(NeedsResources, app)

        self.assertIs(resolved.resources, app.resources)

    def test_container_resolver_recursively_injects_typed_dependencies(self):
        from apps.core.extensions.container import resolve_container_value

        class Dependency:
            pass

        class Service:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency

        resolved = resolve_container_value(Service, ExtensionApplication())

        self.assertIsInstance(resolved.dependency, Dependency)

    def test_extension_container_resolves_bound_class_and_reuses_singletons(self):
        from apps.core.extensions.container import resolve_container_value

        class Dependency:
            pass

        class Replacement:
            pass

        class Service:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency

        app = ExtensionApplication()
        app.instance(Dependency, Replacement())
        app.singleton(Service, Service)

        first = app.make(Service)
        second = app.make(Service)
        resolved = resolve_container_value(Service, app)

        self.assertIs(first, second)
        self.assertIs(resolved, first)
        self.assertIsInstance(first.dependency, Replacement)

    def test_wrap_callback_resolves_class_string_lazily_like_upstream_container(self):
        from apps.core.extensions.container import wrap_callback

        calls = []

        class Invokable:
            def __init__(self):
                calls.append("constructed")

            def __call__(self):
                calls.append("called")
                return "ok"

        app = ExtensionApplication()
        callback = wrap_callback(Invokable, app)

        self.assertEqual(calls, [])
        self.assertEqual(callback(), "ok")
        self.assertEqual(calls, ["constructed", "called"])

    def test_wrap_callback_does_not_hide_argument_type_errors(self):
        from apps.core.extensions.container import wrap_callback

        def callback(required):
            return required

        wrapped = wrap_callback(callback, ExtensionApplication())

        with self.assertRaises(TypeError):
            wrapped()

    def test_jsonapi_serializer_is_context_driven_and_keeps_included_deduped(self):
        registry = ResourceRegistry()

        class UserResource(Resource):
            def type(self):
                return "serializer_users"

            def fields(self):
                return [ResourceField("username", resolver=lambda instance, context: instance.username)]

        class DiscussionResource(Resource):
            def type(self):
                return "serializer_discussions"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        resource_type="serializer_users",
                    ),
                ]

        owner = SimpleNamespace(id=7, username="neo")
        discussions = [
            SimpleNamespace(id=1, title="first", owner=owner),
            SimpleNamespace(id=2, title="second", owner=owner),
        ]
        registry.register_resource(UserResource())
        registry.register_resource(DiscussionResource())

        payload = registry.serialize_jsonapi_document(
            "serializer_discussions",
            discussions,
            include=("owner",),
            many=True,
        )

        self.assertEqual(len(payload["included"]), 1)
        self.assertEqual(payload["included"][0]["type"], "serializer_users")

    def test_resource_serializer_exposes_bias_style_primary_and_included_api(self):
        registry = ResourceRegistry()

        class ItemResource(Resource):
            def type(self):
                return "serializer_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

        registry.register_resource(ItemResource())
        serializer = ResourceSerializer(registry)
        item = SimpleNamespace(id=1, title="hello")

        serializer.add_primary("serializer_items", item)
        primary, included = serializer.serialize()

        self.assertEqual(primary[0]["type"], "serializer_items")
        self.assertEqual(primary[0]["attributes"]["title"], "hello")
        self.assertEqual(included, [])

    def test_resource_serializer_add_included_returns_identifier(self):
        registry = ResourceRegistry()

        class ItemResource(Resource):
            def type(self):
                return "serializer_include_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

        registry.register_resource(ItemResource())
        serializer = ResourceSerializer(registry)
        item = SimpleNamespace(id=9, title="included")

        identifier = serializer.add_included("serializer_include_items", item)
        primary, included = serializer.serialize()

        self.assertEqual(identifier, {"type": "serializer_include_items", "id": "9"})
        self.assertEqual(primary, [])
        self.assertEqual(included[0]["attributes"]["title"], "included")

    def test_resource_serializer_owns_relationship_linkage_and_included_resolution(self):
        registry = ResourceRegistry()

        class UserResource(Resource):
            def type(self):
                return "owned_serializer_users"

            def fields(self):
                return [ResourceField("username", resolver=lambda instance, context: instance.username)]

        class DiscussionResource(Resource):
            def type(self):
                return "owned_serializer_discussions"

            def fields(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        resource_type="owned_serializer_users",
                    )
                ]

        owner = SimpleNamespace(id=7, username="neo")
        discussion = SimpleNamespace(id=1, owner=owner)
        registry.register_resource(UserResource())
        registry.register_resource(DiscussionResource())

        serializer = ResourceSerializer(registry)
        serializer.add_primary("owned_serializer_discussions", discussion, include_tree={"owner": {}})
        primary, included = serializer.serialize()

        self.assertEqual(primary[0]["relationships"]["owner"]["data"], {"type": "owned_serializer_users", "id": "7"})
        self.assertEqual(included[0]["attributes"]["username"], "neo")

    def test_resource_serializer_uses_schema_object_visibility_and_value_methods(self):
        registry = ResourceRegistry()
        calls = []

        class CustomField(ResourceField):
            def get_value(self, context):
                calls.append(("value", context.model.title))
                return context.model.title.upper()

            def is_visible_for(self, context):
                calls.append(("visible", context.model.title))
                return True

        class ItemResource(Resource):
            def type(self):
                return "schema_serializer_items"

            def fields(self):
                return [CustomField("title", resolver=lambda instance, context: "unused")]

        registry.register_resource(ItemResource())
        payload = registry.serialize_jsonapi_document("schema_serializer_items", SimpleNamespace(id=1, title="hello"))

        self.assertEqual(payload["data"]["attributes"]["title"], "HELLO")
        self.assertEqual(calls, [("visible", "hello"), ("value", "hello")])

    def test_resource_context_sparse_fields_drives_jsonapi_serializer(self):
        registry = ResourceRegistry()

        class ItemResource(Resource):
            def type(self):
                return "sparse_context_items"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceField("body", resolver=lambda instance, context: instance.body),
                ]

        registry.register_resource(ItemResource())
        payload = registry.serialize_jsonapi_document(
            "sparse_context_items",
            SimpleNamespace(id=1, title="hello", body="hidden"),
            context={"query": {"fields": {"sparse_context_items": "title"}}},
        )

        self.assertEqual(payload["data"]["attributes"], {"title": "hello"})

    def test_resource_context_exposes_typed_body_and_collection_helpers(self):
        context = ResourceContext({
            "payload": {"data": {"type": "items", "attributes": {"title": "hello"}, "relationships": {"owner": {"data": None}}}},
            "query": {"fields": {"items": "title"}},
            "resource": "items",
        })

        self.assertEqual(context.data()["type"], "items")
        self.assertEqual(context.attributes(), {"title": "hello"})
        self.assertEqual(context.relationship_data(), {"owner": {"data": None}})
        self.assertEqual(context.collection_resources(), ("items",))


    def test_endpoint_runner_pipeline_stores_query_and_result_context(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id, title):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

        class Manager:
            def all(self):
                return QuerySet([Item(1, "first")])

        Item.objects = Manager()
        seen = {}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "pipeline_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [
                    ResourceEndpoint.index()
                    .after(lambda context, results: seen.update({
                        "has_queryset": context.queryset is not None,
                        "result_count": len(results),
                    }) or results)
                ]

        registry.register_resource(ItemResource())
        payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("pipeline_items", "index", "GET"),
            {"resource": "pipeline_items", "endpoint": "index", "method": "GET"},
        )

        self.assertEqual(payload["data"][0]["attributes"]["title"], "first")
        self.assertEqual(seen, {"has_queryset": True, "result_count": 1})

    def test_resource_endpoint_pipeline_callbacks_can_override_response(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="first"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        order = []

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "pipeline_callback_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [
                    ResourceEndpoint.show()
                    .query(lambda context: order.append("query") or context)
                    .before_serialization(lambda context, result: order.append("before_serialization") or result)
                    .response(lambda context, response: order.append("response") or {"data": {"type": "override"}})
                ]

        registry.register_resource(ItemResource())
        payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("pipeline_callback_items", "show", "GET"),
            {"resource": "pipeline_callback_items", "endpoint": "show", "method": "GET", "object_id": "1"},
        )

        self.assertEqual(order, ["query", "before_serialization", "response"])
        self.assertEqual(payload, {"data": {"type": "override"}})

    def test_database_resource_endpoint_pipeline_is_reusable_like_endpoint_concern(self):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint

        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="first"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "concern_pipeline_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

        resource = ItemResource()
        registry.register_resource(resource)
        definition = ResourceEndpointDefinition(
            resource="concern_pipeline_items",
            endpoint="index",
            module_id="test",
            kind="index",
            methods=("GET",),
        )

        pipeline = DatabaseResourceEndpoint(registry, resource, definition).index_pipeline()
        context = pipeline.query(ResourceContext({"resource": "concern_pipeline_items", "query": {}}))
        results = pipeline.action(context)
        response = pipeline.response(context.with_result(results), results)

        self.assertEqual(response["data"][0]["attributes"]["title"], "first")

    def test_database_resource_endpoint_prepares_include_plan_before_serialization(self):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint

        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="first", owner=None):
                self.id = id
                self.title = title
                self.owner = owner

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def select_related(self, *fields):
                self.select_related_fields = fields
                return self

            def prefetch_related(self, *fields):
                self.prefetch_related_fields = fields
                return self

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class UserResource(Resource):
            def type(self):
                return "concern_plan_users"

            def fields(self):
                return [ResourceField("username", resolver=lambda instance, context: "neo")]

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "concern_plan_items"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title),
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        resource_type="concern_plan_users",
                        select_related=("owner",),
                    ),
                ]

        registry.register_resource(UserResource())
        resource = ItemResource()
        registry.register_resource(resource)
        definition = ResourceEndpointDefinition(
            resource="concern_plan_items",
            endpoint="index",
            module_id="test",
            kind="index",
            methods=("GET",),
            default_include=("owner",),
        )

        pipeline = DatabaseResourceEndpoint(registry, resource, definition).index_pipeline()
        context = pipeline.query(ResourceContext({"resource": "concern_plan_items", "query": {}}))
        results = pipeline.action(context)
        serialization_context = context.with_result(results)
        pipeline.before_serialization(serialization_context, results)

        self.assertEqual(serialization_context["preload_plan"].select_related, ("owner",))

    def test_database_resource_endpoint_listing_params_are_extracted_by_concern(self):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint

        registry = ResourceRegistry()

        class ItemResource(DatabaseResource):
            model = object

            def type(self):
                return "listing_param_items"

        definition = ResourceEndpointDefinition(
            resource="listing_param_items",
            endpoint="index",
            module_id="test",
            kind="index",
            paginate=True,
            default_include=("owner",),
        )
        endpoint = DatabaseResourceEndpoint(registry, ItemResource(), definition)
        params = endpoint.listing_params(ResourceContext({
            "query": {
                "page[limit]": "5",
                "page[offset]": "10",
                "filter[state]": "open",
                "sort": "-created",
            }
        }))

        self.assertEqual(params["pagination"], {"limit": 5, "offset": 10})
        self.assertEqual(params["include"], ("owner",))
        self.assertEqual(params["filters"], {"state": "open"})
        self.assertEqual(params["sort"], "-created")

    def test_database_resource_endpoint_search_concern_can_customize_listing_query(self):
        from apps.core.resource_endpoint_runner import DatabaseResourceEndpoint

        registry = ResourceRegistry()

        class Item:
            def __init__(self, id=1, title="first"):
                self.id = id
                self.title = title

        class QuerySet(list):
            pass

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "custom_listing_items"

            def query(self, context):
                return QuerySet([Item(1, "first"), Item(2, "second")])

            def scope(self, query, context):
                return query

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

        class CustomEndpoint(DatabaseResourceEndpoint):
            def apply_listing_query(self, queryset, context, params):
                return QuerySet([queryset[1]]), None, 1

        resource = ItemResource()
        definition = ResourceEndpointDefinition(
            resource="custom_listing_items",
            endpoint="index",
            module_id="test",
            kind="index",
            methods=("GET",),
            paginate=True,
        )
        endpoint = CustomEndpoint(registry, resource, definition)
        pipeline = endpoint.index_pipeline()
        context = pipeline.query(ResourceContext({"resource": "custom_listing_items", "query": {}}))
        results = pipeline.action(context)

        self.assertEqual([item.title for item in results], ["second"])
        self.assertEqual(context.get("total"), 1)

    def test_resource_payload_uses_schema_object_deserialize_validate_and_setter(self):
        registry = ResourceRegistry()
        calls = []

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class CustomField(ResourceField):
            def deserialize(self, value, context):
                calls.append(("deserialize", value))
                return value.strip()

            def validate(self, value, context):
                calls.append(("validate", value))
                if not value:
                    raise ValueError("title required")

            def set_value(self, instance, value, context):
                calls.append(("set", value))
                instance.title = value.upper()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "schema_payload_items"

            def fields(self):
                return [CustomField("title", resolver=lambda instance, context: instance.title).writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        response = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("schema_payload_items", "update", "PATCH"),
            {
                "resource": "schema_payload_items",
                "endpoint": "update",
                "method": "PATCH",
                "object_id": "1",
                "payload": {"data": {"type": "schema_payload_items", "id": "1", "attributes": {"title": " new "}}},
                "query": {},
            },
        )

        self.assertEqual(response["data"]["attributes"]["title"], "NEW")
        self.assertEqual(calls[-1], ("set", "new"))
        self.assertIn(("deserialize", " new "), calls)
        self.assertIn(("validate", "new"), calls)

    def test_resource_validation_collects_schema_object_rules_messages_and_attributes(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title
                self.owner = None

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class TitleField(ResourceField):
            def get_validation_rules(self, context):
                return {"title": ("required_without:relationships.owner",)}

            def get_validation_messages(self, context):
                return {"title.required_without": "Need either title or owner"}

            def get_validation_attributes(self, context):
                return {"title": "Title"}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "schema_rule_items"

            def fields(self):
                return [
                    TitleField("title", resolver=lambda instance, context: instance.title)
                    .string()
                    .writable_when()
                    .with_validation_rules()
                ]

            def relationships(self):
                return [
                    ResourceRelationship(
                        "owner",
                        resolver=lambda instance, context: instance.owner,
                        resource_type="users",
                        writable=True,
                    )
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/schema_rule_items/1",
            data=json.dumps({"data": {"type": "schema_rule_items", "attributes": {"title": ""}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="schema_rule_items", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["errors"][0]["detail"], "Need either title or owner")
        self.assertEqual(payload["errors"][0]["source"]["pointer"], "/data/attributes/title")

    def test_resource_validation_skips_unmarked_schema_rules_like_upstream_trait_gate(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        seen = {}

        class UnmarkedField(ResourceField):
            def get_validation_rules(self, context):
                return {"title": ("required",)}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "unmarked_rule_items"

            def fields(self):
                return [UnmarkedField("title", resolver=lambda instance, context: instance.title).writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                def validate(data, context, validation):
                    seen["rules"] = validation["rules"]
                    return None
                return validate

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/unmarked_rule_items/1",
            data=json.dumps({"data": {"type": "unmarked_rule_items", "attributes": {"title": ""}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="unmarked_rule_items", endpoint="update", object_id="1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["rules"]["attributes"], {})

    def test_resource_validation_rules_support_conditions_like_upstream(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old", summary="old"):
                self.id = id
                self.title = title
                self.summary = summary

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        seen = {}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "conditional_rule_items"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title)
                    .string()
                    .required(lambda context, model=None: bool(context.get("creating")))
                    .writable_when(),
                    ResourceField("summary", resolver=lambda instance, context: instance.summary)
                    .string()
                    .required_with(["title"])
                    .writable_when(),
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                def validate(data, context, validation):
                    seen["rules"] = validation["rules"]
                    return None
                return validate

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/conditional_rule_items/1",
            data=json.dumps({"data": {"type": "conditional_rule_items", "attributes": {"title": "new"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="conditional_rule_items", endpoint="update", object_id="1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["rules"]["attributes"], {"summary": ("required_with:title",)})

    def test_resource_endpoint_response_callback_receives_result_and_document_context(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="first"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        seen = {}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "pipeline_context_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [
                    ResourceEndpoint.show().response(
                        lambda context, response: seen.update({
                            "result_title": context.result.title,
                            "document_type": context.document["data"]["type"],
                        }) or response
                    )
                ]

        registry.register_resource(ItemResource())
        registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("pipeline_context_items", "show", "GET"),
            {"resource": "pipeline_context_items", "endpoint": "show", "method": "GET", "object_id": "1"},
        )

        self.assertEqual(seen, {"result_title": "first", "document_type": "pipeline_context_items"})

    def test_validation_factory_receives_aggregated_rules_payload(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        seen = {}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "factory_payload_item"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title)
                    .string()
                    .min_length(2)
                    .writable_when()
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                def validate(data, context, validation):
                    seen["rules"] = validation["rules"]
                    return None
                return validate

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/factory_payload_item/1",
            data=json.dumps({"data": {"type": "factory_payload_item", "attributes": {"title": "ok"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="factory_payload_item", endpoint="update", object_id="1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["rules"]["attributes"]["title"], (("min_length", 2),))

    def test_validation_factory_collects_only_writable_schema_rules_like_upstream(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old", slug="old"):
                self.id = id
                self.title = title
                self.slug = slug

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()
        seen = {}

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "writable_rule_items"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title)
                    .string()
                    .rule("required")
                    .writable_when(),
                    ResourceField("slug", resolver=lambda instance, context: instance.slug)
                    .string()
                    .rule("required"),
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                def validate(data, context, validation):
                    seen["rules"] = validation["rules"]
                    return None
                return validate

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/writable_rule_items/1",
            data=json.dumps({"data": {"type": "writable_rule_items", "attributes": {"title": "new"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="writable_rule_items", endpoint="update", object_id="1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["rules"]["attributes"], {"title": ("required",)})

    def test_validation_factory_can_return_validator_protocol(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        class Factory:
            def make(self, data, rules, messages, attributes):
                if data.get("title") == "bad":
                    return ResourceValidator([ResourceValidationError("title", "Validator rejected")])
                return ResourceValidator()

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "validator_protocol_item"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).string().writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                return Factory()

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/validator_protocol_item/1",
            data=json.dumps({"data": {"type": "validator_protocol_item", "attributes": {"title": "bad"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="validator_protocol_item", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["errors"][0]["detail"], "Validator rejected")

    def test_validation_factory_preserves_relationship_error_section(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1):
                self.id = id
                self.owner = None

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "relationship_validation_items"

            def fields(self):
                return []

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                return ResourceValidatorFactory()

            def validation_attributes(self):
                return {"owner": "Owner"}

        registry.register_resource(ItemResource())
        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="relationship_validation_items",
                relationship="owner",
                module_id="test",
                resolver=lambda instance, context: instance.owner,
                writable=True,
                validation_rules=(("in", ("1",)),),
            )
        )
        request = RequestFactory().patch(
            "/api/resources/relationship_validation_items/1",
            data=json.dumps({
                "data": {
                    "type": "relationship_validation_items",
                    "relationships": {"owner": {"data": {"type": "users", "id": "2"}}},
                }
            }),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="relationship_validation_items", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["errors"][0]["source"]["pointer"], "/data/relationships/owner")

    def test_default_validator_factory_interprets_field_rules(self):
        from apps.core.resource_validation import ResourceValidatorFactory

        validator = ResourceValidatorFactory().make(
            {"title": "x"},
            {"title": (("min_length", 3),)},
            attributes={"title": "Title"},
        )

        self.assertTrue(validator.fails())
        self.assertEqual(validator.messages()["title"], ["Title length must be at least 3"])

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

    def test_serialize_applies_registered_field_mutators_to_payload(self):
        registry = ResourceRegistry()

        class Target:
            title = "hello"

        registry.register_field(
            ResourceFieldDefinition(
                resource="discussion",
                field="title",
                module_id="core",
                resolver=lambda instance, context: instance.title,
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="title",
                module_id="extension",
                mutator=lambda value: value.upper(),
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="secret",
                module_id="extension",
                mutator=lambda value: value,
                operation="remove",
            )
        )

        payload = registry.serialize("discussion", Target())

        self.assertEqual(payload["title"], "HELLO")
        self.assertNotIn("secret", payload)

    def test_serialize_applies_bias_like_field_definition_mutators(self):
        registry = ResourceRegistry()

        class Target:
            title = "hello"

        title = ResourceFieldDefinition(
            resource="discussion",
            field="title",
            module_id="core",
            resolver=lambda instance, context: instance.title,
        )
        summary = ResourceFieldDefinition(
            resource="discussion",
            field="summary",
            module_id="extension",
            resolver=lambda instance, context: "summary",
        )
        mutated_title = ResourceFieldDefinition(
            resource="discussion",
            field="title",
            module_id="extension",
            resolver=lambda instance, context: instance.title.upper(),
        )
        registry.register_field(title)
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="summary",
                module_id="extension",
                operation="add",
                mutator=lambda field: summary,
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="title",
                module_id="extension",
                operation="mutate",
                mutator=lambda field: mutated_title,
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="removed",
                module_id="extension",
                operation="add",
                mutator=lambda field: ResourceFieldDefinition(
                    resource="discussion",
                    field="removed",
                    module_id="extension",
                    resolver=lambda instance, context: "removed",
                ),
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="removed",
                module_id="extension",
                operation="remove",
                mutator=lambda field: field,
            )
        )

        payload = registry.serialize("discussion", Target())

        self.assertEqual(payload, {"title": "HELLO", "summary": "summary"})

    def test_relationship_includes_follow_bias_like_field_removal(self):
        registry = ResourceRegistry()

        class Target:
            owner = type("Owner", (), {"username": "neo"})()

        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="discussion",
                relationship="owner",
                module_id="core",
                resolver=lambda instance, context: {"username": instance.owner.username},
                select_related=("owner",),
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="owner",
                module_id="extension",
                operation="remove",
                mutator=lambda field: field,
            )
        )

        payload = registry.serialize("discussion", Target(), include=("owner",))
        plan = registry.build_preload_plan("discussion", include=("owner",))

        self.assertNotIn("owner", payload)
        self.assertEqual(plan.select_related, ())

    def test_relationship_includes_follow_bias_like_field_mutation(self):
        registry = ResourceRegistry()

        class Target:
            owner = type("Owner", (), {"username": "neo"})()

        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="discussion",
                relationship="owner",
                module_id="core",
                resolver=lambda instance, context: {"username": instance.owner.username},
                select_related=("owner",),
            )
        )
        registry.register_field_mutator(
            ResourceFieldMutatorDefinition(
                resource="discussion",
                field="owner",
                module_id="extension",
                operation="mutate",
                mutator=lambda relationship: ResourceRelationshipDefinition(
                    resource=relationship.resource,
                    relationship=relationship.relationship,
                    module_id=relationship.module_id,
                    resolver=lambda instance, context: {"username": instance.owner.username.upper()},
                    select_related=("profile",),
                ),
            )
        )

        payload = registry.serialize("discussion", Target(), include=("owner",))
        plan = registry.build_preload_plan("discussion", include=("owner",))

        self.assertEqual(payload["owner"], {"username": "NEO"})
        self.assertEqual(plan.select_related, ("profile",))

    def test_apply_named_sort_runs_registered_sort_handler(self):
        registry = ResourceRegistry()
        queryset = Mock()
        sorted_queryset = Mock()
        handler = Mock(return_value=sorted_queryset)

        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="hot",
                module_id="extension",
                handler=handler,
            )
        )

        result = registry.apply_named_sort(
            "discussion",
            queryset,
            "hot",
            {"user": "alice"},
        )

        self.assertIs(result, sorted_queryset)
        handler.assert_called_once_with(queryset, {"user": "alice", "sort": "hot", "descending": False})

    def test_apply_named_sort_can_order_by_registered_field_list(self):
        registry = ResourceRegistry()
        queryset = Mock()
        ordered_queryset = Mock()
        queryset.order_by.return_value = ordered_queryset

        registry.register_sort(
            ResourceSortDefinition(
                resource="post",
                sort="recent",
                module_id="extension",
                handler=("-created_at", "id"),
            )
        )

        result = registry.apply_named_sort("post", queryset, "recent")

        self.assertIs(result, ordered_queryset)
        queryset.order_by.assert_called_once_with("-created_at", "id")
        self.assertTrue(registry.has_named_sort("post", "recent"))
        self.assertFalse(registry.has_named_sort("post", "missing"))

    def test_named_sort_uses_effective_sort_definitions(self):
        registry = ResourceRegistry()
        queryset = Mock()
        ordered_queryset = Mock()
        queryset.order_by.return_value = ordered_queryset

        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="hot",
                module_id="extension",
                handler=("hot",),
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="hot",
                module_id="extension",
                operation="mutate",
                mutator=lambda sort: ResourceSortDefinition(
                    resource=sort.resource,
                    sort=sort.sort,
                    module_id=sort.module_id,
                    handler=("-hot_score",),
                ),
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="old",
                module_id="extension",
                handler=("old",),
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="old",
                module_id="extension",
                operation="remove",
            )
        )

        result = registry.apply_named_sort("discussion", queryset, "hot")

        self.assertIs(result, ordered_queryset)
        queryset.order_by.assert_called_once_with("-hot_score")
        self.assertTrue(registry.has_named_sort("discussion", "hot"))
        self.assertFalse(registry.has_named_sort("discussion", "old"))

    def test_sort_definitions_match_objects_by_code(self):
        registry = ResourceRegistry()
        sort = DiscussionSortDefinition(
            code="oldest",
            label="最早",
            module_id="core",
            applier=lambda queryset, context: queryset,
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="oldest",
                module_id="extension",
                operation="remove",
            )
        )

        self.assertEqual(registry.apply_sort_definitions("discussion", [sort]), [])

    def test_sort_definitions_apply_before_after_and_before_all_ordering(self):
        registry = ResourceRegistry()
        base = ResourceSortDefinition(
            resource="discussion",
            sort="base",
            module_id="core",
            handler={"name": "base"},
        )
        first = ResourceSortDefinition(
            resource="discussion",
            sort="first",
            module_id="extension",
            handler={"name": "first"},
            operation="before_all",
        )
        before = ResourceSortDefinition(
            resource="discussion",
            sort="before",
            module_id="extension",
            handler={"name": "before"},
            operation="before",
            anchor="base",
        )
        after = ResourceSortDefinition(
            resource="discussion",
            sort="after",
            module_id="extension",
            handler={"name": "after"},
            operation="after",
            anchor="base",
        )

        registry.register_sort(base)
        registry.register_sort(after)
        registry.register_sort(first)
        registry.register_sort(before)

        self.assertEqual(
            [item.sort for item in registry.get_effective_sorts("discussion")],
            ["first", "before", "base", "after"],
        )
        self.assertEqual(
            registry.apply_sort_definitions("discussion", []),
            [{"name": "first"}, {"name": "before"}, {"name": "base"}, {"name": "after"}],
        )

    def test_get_dispatch_endpoint_matches_method_path_and_condition(self):
        registry = ResourceRegistry()
        handler = Mock(return_value={"ok": True})

        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="feature",
                module_id="extension",
                handler=handler,
                methods=("POST",),
                condition=lambda context: context.get("enabled") is True,
            )
        )

        self.assertIsNone(registry.get_dispatch_endpoint("discussion", "feature", "GET", {"enabled": True}))
        self.assertIsNone(registry.get_dispatch_endpoint("discussion", "feature", "POST", {"enabled": False}))
        self.assertIs(
            registry.get_dispatch_endpoint("discussion", "/feature/", "POST", {"enabled": True}),
            registry.get_endpoints("discussion")[0],
        )

    def test_dispatch_endpoint_list_applies_remove_and_mutate_operations(self):
        registry = ResourceRegistry()

        original = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="feature",
            module_id="extension",
            handler=lambda context: {"version": 1},
            methods=("GET",),
        )
        replacement = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="feature",
            module_id="extension",
            operation="mutate",
            mutator=lambda endpoint: ResourceEndpointDefinition(
                resource=endpoint.resource,
                endpoint=endpoint.endpoint,
                module_id=endpoint.module_id,
                handler=lambda context: {"version": 2},
                methods=endpoint.methods,
            ),
        )
        removed = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="feature",
            module_id="extension",
            operation="remove",
        )

        registry.register_endpoint(original)
        registry.register_endpoint(replacement)

        endpoint = registry.get_dispatch_endpoint("discussion", "feature", "GET")
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.handler({}), {"version": 2})

        registry.register_endpoint(removed)
        self.assertIsNone(registry.get_dispatch_endpoint("discussion", "feature", "GET"))

    def test_apply_endpoint_definitions_applies_remove_without_mutator(self):
        registry = ResourceRegistry()
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="store",
                module_id="extension",
                operation="remove",
            )
        )

        self.assertEqual(
            registry.apply_endpoint_definitions("discussion", [{"name": "index"}, {"name": "store"}]),
            [{"name": "index"}],
        )

    def test_dispatch_endpoint_list_applies_before_and_after_ordering(self):
        registry = ResourceRegistry()
        base = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="base",
            module_id="core",
            handler=lambda context: {"name": "base"},
        )
        before = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="before",
            module_id="extension",
            operation="before",
            anchor="base",
            handler=lambda context: {"name": "before"},
        )
        after = ResourceEndpointDefinition(
            resource="discussion",
            endpoint="after",
            module_id="extension",
            operation="after",
            anchor="base",
            handler=lambda context: {"name": "after"},
        )

        registry.register_endpoint(base)
        registry.register_endpoint(after)
        registry.register_endpoint(before)

        self.assertEqual(
            [item.endpoint for item in registry.get_dispatch_endpoints("discussion")],
            ["before", "base", "after"],
        )

    def test_dispatch_resource_endpoint_invokes_registered_handler(self):
        registry = ResourceRegistry()

        def handler(context):
            return {
                "resource": context["resource"],
                "endpoint": context["endpoint"],
                "object_id": context["object_id"],
                "payload": context["payload"],
                "query": context["query"],
            }

        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="feature",
                module_id="extension",
                handler=handler,
                methods=("POST",),
            )
        )
        request = RequestFactory().post(
            "/api/resources/discussion/12/feature?include=user",
            data=json.dumps({"enabled": True}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(
                request,
                resource="discussion",
                object_id="12",
                endpoint="feature",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {
                "resource": "discussion",
                "endpoint": "feature",
                "object_id": "12",
                "payload": {"enabled": True},
                "query": {"include": "user"},
            },
        )

    def test_dispatch_resource_endpoint_requires_auth_when_declared(self):
        registry = ResourceRegistry()
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="secure",
                module_id="extension",
                handler=lambda context: {"ok": True},
                auth_required=True,
            )
        )
        request = RequestFactory().get("/api/resources/discussion/secure")

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="discussion", endpoint="secure")

        self.assertEqual(response.status_code, 401)

    def test_dispatch_resource_endpoint_checks_declared_permission(self):
        registry = ResourceRegistry()
        registry.register_resource(
            type(
                "SecureResource",
                (Resource,),
                {
                    "type": lambda self: "secure",
                    "endpoints": lambda self: [
                        ResourceEndpoint(
                            "show",
                            handler=lambda context: {"ok": True},
                        ).authenticated().requires_permission("secure.view")
                    ],
                },
            )()
        )
        request = RequestFactory().get("/api/resources/secure/show")
        user = Mock(is_authenticated=True)
        request.user = user

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_optional_user", return_value=user):
                with patch("apps.users.services.UserService.has_forum_permission", return_value=False):
                    denied = dispatch_resource_endpoint(request, resource="secure", endpoint="show")
                with patch("apps.users.services.UserService.has_forum_permission", return_value=True):
                    allowed = dispatch_resource_endpoint(request, resource="secure", endpoint="show")

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

    def test_dispatch_resource_endpoint_runs_database_resource_crud_endpoint(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="hello"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return QuerySet([item for item in self if str(item.id) == str(kwargs.get("pk"))])

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "dispatch_item"

            def base(self, instance, context):
                return {"id": instance.id}

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [ResourceEndpoint.show()]

        registry.register_resource(ItemResource())
        request = RequestFactory().get("/api/resources/dispatch_item/1/show")

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(
                request,
                resource="dispatch_item",
                object_id="1",
                endpoint="show",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {"data": {"type": "dispatch_item", "id": "1", "links": {"self": "/api/dispatch_item/1"}, "attributes": {"title": "hello"}}},
        )

    def test_dispatch_resource_endpoint_passes_page_limit_and_offset_to_index_endpoint(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id):
                self.id = id

        class QuerySet(list):
            def __getitem__(self, item):
                result = super().__getitem__(item)
                if isinstance(item, slice):
                    return QuerySet(result)
                return result

        class Manager:
            def all(self):
                return QuerySet([Item(1), Item(2), Item(3)])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "paged_dispatch_item"

            def endpoints(self):
                return [ResourceEndpoint.index().with_pagination(default_limit=1, max_limit=2)]

        registry.register_resource(ItemResource())
        request = RequestFactory().get("/api/resources/paged_dispatch_item/index", {"page[offset]": "1", "page[limit]": "2"})

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="paged_dispatch_item", endpoint="index")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {
                "data": [
                    {"type": "paged_dispatch_item", "id": "2", "links": {"self": "/api/paged_dispatch_item/2"}},
                    {"type": "paged_dispatch_item", "id": "3", "links": {"self": "/api/paged_dispatch_item/3"}},
                ],
                "meta": {"total": 3, "count": 2, "limit": 2, "offset": 1},
            },
        )

    def test_database_resource_index_applies_bias_like_filter_and_searcher_pipeline(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id, title, state):
                self.id = id
                self.title = title
                self.state = state

        class QuerySet(list):
            def filter(self, *args, **kwargs):
                if kwargs.get("state") is not None:
                    return QuerySet([item for item in self if item.state == kwargs["state"]])
                return self

            def order_by(self, *fields):
                field = fields[0]
                reverse = field.startswith("-")
                key = field.lstrip("-")
                return QuerySet(sorted(self, key=lambda item: getattr(item, key), reverse=reverse))

        class Manager:
            def all(self):
                return QuerySet([
                    Item(1, "alpha", "open"),
                    Item(2, "beta", "closed"),
                    Item(3, "gamma", "open"),
                ])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "searchable_item"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title).string(),
                    ResourceField("state", resolver=lambda instance, context: instance.state).string(),
                ]

            def filters(self):
                return [ResourceFilter("state", handler=lambda queryset, value, context: queryset.filter(state=value))]

            def sorts(self):
                return [ResourceSort("title", "title")]

            def endpoints(self):
                return [ResourceEndpoint.index().with_pagination(default_limit=20)]

        registry.register_resource(ItemResource())
        payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("searchable_item", "index", "GET"),
            {
                "resource": "searchable_item",
                "endpoint": "index",
                "method": "GET",
                "query": {"filter[state]": "open", "sort": "-title"},
            },
        )

        self.assertEqual([item["id"] for item in payload["data"]], ["3", "1"])

        class SearchResource(ItemResource):
            def type(self):
                return "searcher_item"

            def search(self, criteria, context):
                if criteria.filters["q"] != "alpha":
                    raise AssertionError("unexpected search criteria")
                return ResourceSearchResults(QuerySet([Item(9, "alpha result", "open")]), total=1)

        registry.register_resource(SearchResource())
        search_payload = registry.dispatch_resource_endpoint(
            registry.get_dispatch_endpoint("searcher_item", "index", "GET"),
            {
                "resource": "searcher_item",
                "endpoint": "index",
                "method": "GET",
                "query": {"filter[q]": "alpha"},
            },
        )

        self.assertEqual(search_payload["meta"]["total"], 1)
        self.assertEqual(search_payload["data"][0]["id"], "9")

    def test_search_manager_driver_searcher_receives_criteria_from_index_endpoint(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id, title):
                self.id = id
                self.title = title

        class QuerySet(list):
            pass

        class Manager:
            def all(self):
                return QuerySet([Item(1, "first"), Item(2, "second")])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "managed_search_item"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [ResourceEndpoint.index().with_pagination(default_limit=1)]

        seen = {}

        def searcher(queryset, criteria, context):
            seen["filters"] = criteria.filters
            seen["limit"] = criteria.limit
            seen["offset"] = criteria.offset
            return ResourceSearchResults(QuerySet([Item(8, "managed")]), total=1, sort_applied=True, pagination_applied=True)

        manager = ResourceSearchManager()
        manager.register_searcher(Item, searcher)
        registry.register_resource(ItemResource())

        app = ExtensionApplication(resource_registry=registry)
        app.search.manager = manager
        with patch("apps.core.extensions.runtime_access.get_extension_host_service", side_effect=lambda key, default=None: app.search if key == "search" else default):
            payload = registry.dispatch_resource_endpoint(
                registry.get_dispatch_endpoint("managed_search_item", "index", "GET"),
                {
                    "resource": "managed_search_item",
                    "endpoint": "index",
                    "method": "GET",
                    "query": {"filter[q]": "needle", "page[limit]": "1", "page[offset]": "2"},
                },
            )

        self.assertEqual(seen["filters"], {"q": "needle"})
        self.assertEqual(seen["limit"], 1)
        self.assertEqual(seen["offset"], 2)
        self.assertEqual(payload["data"][0]["id"], "8")
        self.assertEqual(payload["meta"]["total"], 1)

    def test_search_manager_database_driver_applies_resource_filters(self):
        manager = ResourceSearchManager()
        manager.register_filter(
            "managed_filter_item",
            ResourceSearchFilter("state", lambda state, value, context: [item for item in state.queryset if item.state == value]),
        )
        class Item:
            def __init__(self, state):
                self.state = state

        results = manager.query(
            object,
            [Item("open"), Item("closed")],
            ResourceSearchCriteria(filters={"state": "open"}, resource="managed_filter_item"),
            {},
        )

        self.assertEqual([item.state for item in results.results], ["open"])

    def test_search_driver_extender_bias_style_api_registers_searcher_filters_fulltext_and_mutator(self):
        class Item:
            pass

        calls = []

        def searcher(queryset, criteria, context):
            calls.append(("search", list(queryset)))
            return list(queryset)

        def filter_handler(state, value, context):
            calls.append(("filter", value, context["negate"]))
            return [item for item in state.queryset if item == value]

        def fulltext(state, query, context):
            calls.append(("fulltext", query))
            return state.queryset

        def mutator(state, criteria):
            calls.append(("mutator", criteria.query))
            return state

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="search-ext")
        extender = (
            SearchDriverExtender("database")
            .add_searcher(Item, searcher, target="items")
            .add_filter(searcher, ("state", filter_handler), target="items")
            .set_fulltext(searcher, fulltext, target="items")
            .add_mutator(searcher, mutator, target="items")
        )
        extender.extend(app, extension)
        app.make("search")

        result = app.search.query(
            Item,
            ["open", "closed"],
            ResourceSearchCriteria(filters={"q": "needle", "state": "open"}, query="needle", resource="items"),
            {},
        )

        self.assertEqual(result.results, ["open"])
        self.assertEqual(calls[0], ("fulltext", "needle"))
        self.assertEqual(calls[1], ("filter", "open", False))
        self.assertEqual(calls[2], ("mutator", "needle"))
        self.assertEqual(calls[3], ("search", ["open"]))

    def test_search_manager_prefers_default_driver_until_fulltext_like_upstream(self):
        class Item:
            pass

        calls = []

        def database_searcher(queryset, criteria, context):
            calls.append("database")
            return ["database"]

        def custom_searcher(queryset, criteria, context):
            calls.append("custom")
            return ["custom"]

        manager = ResourceSearchManager()
        manager.register_searcher(Item, database_searcher, driver="database")
        manager.register_searcher(Item, custom_searcher, driver="external")
        manager.use_driver_for(Item, "external")

        normal = manager.query(Item, [], ResourceSearchCriteria(resource="items"), {})
        fulltext = manager.query(Item, [], ResourceSearchCriteria(filters={"q": "needle"}, resource="items"), {})

        self.assertEqual(normal.results, ["database"])
        self.assertEqual(fulltext.results, ["custom"])
        self.assertEqual(calls, ["database", "custom"])

    def test_search_manager_uses_settings_driver_for_resource_like_upstream(self):
        class Item:
            pass

        calls = []

        def database_searcher(queryset, criteria, context):
            calls.append("database")
            return ["database"]

        def custom_searcher(queryset, criteria, context):
            calls.append("custom")
            return ["custom"]

        manager = ResourceSearchManager(settings={"search_driver_items": "external"})
        manager.register_searcher(Item, database_searcher, driver="database")
        manager.register_searcher(Item, custom_searcher, driver="external")

        result = manager.query(Item, [], ResourceSearchCriteria(filters={"q": "needle"}, resource="items"), {})

        self.assertEqual(result.results, ["custom"])
        self.assertEqual(calls, ["custom"])

    def test_search_manager_runs_indexer_lifecycle(self):
        class Item:
            pass

        calls = []

        class Indexer:
            def index(self, instance, context):
                calls.append(("index", instance, context["source"]))

            def unindex(self, instance):
                calls.append(("unindex", instance))

            def reindex(self, instances, context):
                calls.append(("reindex", tuple(instances), context["source"]))

        manager = ResourceSearchManager()
        indexer = Indexer()
        manager.register_indexer(Item, indexer)

        manager.index(Item, "a", {"source": "test"})
        manager.unindex(Item, "b")
        manager.reindex(Item, ["c", "d"], {"source": "bulk"})

        self.assertEqual(calls, [
            ("index", "a", "test"),
            ("unindex", "b"),
            ("reindex", ("c", "d"), "bulk"),
        ])

    def test_search_driver_extender_registers_indexer(self):
        class Item:
            pass

        class Indexer:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="indexer-ext")
        indexer = Indexer()

        SearchDriverExtender("database").add_indexer(Item, indexer, target="items").extend(app, extension)
        app.make("search")

        self.assertEqual(app.search.indexers(Item), (indexer,))

    def test_search_filter_manager_ignores_unknown_filters_like_upstream_search(self):
        class Item:
            pass

        manager = ResourceSearchManager()
        manager.register_searcher(Item, lambda queryset, criteria, context: list(queryset))

        result = manager.query(
            Item,
            ["open"],
            ResourceSearchCriteria(filters={"unknown": "value"}, resource="items"),
            {},
        )

        self.assertEqual(result.results, ["open"])

    def test_resource_dispatcher_returns_jsonapi_error_document(self):
        registry = ResourceRegistry()
        request = RequestFactory().get("/api/resources/missing/index")

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="missing", endpoint="index")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 404)
        self.assertIn("errors", payload)
        self.assertEqual(payload["errors"][0]["status"], "404")

    def test_database_resource_crud_requires_strict_jsonapi_document(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return QuerySet([item for item in self if str(item.id) == str(kwargs.get("pk"))])

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "strict_item"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).string().writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        endpoint = registry.get_dispatch_endpoint("strict_item", "update", "PATCH")

        with self.assertRaisesMessage(ValueError, "data must be an object"):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "strict_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"title": "new"},
                },
            )

        with self.assertRaisesMessage(ValueError, "collection does not support this resource type"):
            registry.dispatch_resource_endpoint(
                endpoint,
                {
                    "resource": "strict_item",
                    "endpoint": "update",
                    "method": "PATCH",
                    "object_id": "1",
                    "payload": {"data": {"type": "wrong", "attributes": {"title": "new"}}},
                },
            )

    def test_jsonapi_validation_error_carries_source_pointer(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, email="old@example.com"):
                self.id = id
                self.email = email

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "validated_item"

            def fields(self):
                return [ResourceField("email", resolver=lambda instance, context: instance.email).string().email().writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/validated_item/1",
            data=json.dumps({"data": {"type": "validated_item", "attributes": {"email": "bad"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="validated_item", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["errors"][0]["source"]["pointer"], "/data/attributes/email")

    def test_resource_validation_factory_returns_jsonapi_pointer_errors(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "factory_validated_item"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).string().writable_when()]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_factory(self):
                return lambda data, context: {"title": "Title rejected"}

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/factory_validated_item/1",
            data=json.dumps({"data": {"type": "factory_validated_item", "attributes": {"title": "new"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="factory_validated_item", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(payload["errors"][0]["source"]["pointer"], "/data/attributes/title")
        self.assertEqual(payload["errors"][0]["detail"], "Title rejected")

    def test_resource_validation_collects_field_rules_before_factory(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="old"):
                self.id = id
                self.title = title

            def save(self):
                return None

        class QuerySet(list):
            def filter(self, **kwargs):
                return self

            def first(self):
                return self[0]

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "aggregated_validated_item"

            def fields(self):
                return [
                    ResourceField("title", resolver=lambda instance, context: instance.title)
                    .string()
                    .min_length(3)
                    .writable_when()
                ]

            def endpoints(self):
                return [ResourceEndpoint.update()]

            def validation_messages(self):
                return {"title": "Title too short"}

            def validation_factory(self):
                return lambda data, context: {"title": "Factory rejected"}

        registry.register_resource(ItemResource())
        request = RequestFactory().patch(
            "/api/resources/aggregated_validated_item/1",
            data=json.dumps({"data": {"type": "aggregated_validated_item", "attributes": {"title": "x"}}}),
            content_type="application/json",
        )

        with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
            response = dispatch_resource_endpoint(request, resource="aggregated_validated_item", endpoint="update", object_id="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [item["detail"] for item in payload["errors"]],
            ["Title too short", "Factory rejected"],
        )

    def test_resource_route_definitions_follow_Bias_endpoint_paths(self):
        registry = ResourceRegistry()

        class DemoResource(Resource):
            def type(self):
                return "demo_items"

            def endpoints(self):
                return [
                    ResourceEndpoint.index(),
                    ResourceEndpoint.show(),
                    ResourceEndpoint.update(),
                    ResourceEndpoint("feature", methods=("POST",), handler=lambda context: {"ok": True}),
                    ResourceEndpoint("named", methods=("GET",), path="/{object_id}/named", handler=lambda context: {"ok": True}),
                ]

        registry.register_resource(DemoResource())

        routes = {
            (route.endpoint, route.methods): route.path
            for route in build_resource_route_definitions(registry)
        }

        self.assertEqual(routes[("index", ("GET",))], "/demo_items")
        self.assertEqual(routes[("show", ("GET",))], "/demo_items/{object_id}")
        self.assertEqual(routes[("update", ("PATCH", "PUT"))], "/demo_items/{object_id}")
        self.assertEqual(routes[("feature", ("POST",))], "/demo_items/feature")
        self.assertEqual(routes[("named", ("GET",))], "/demo_items/{object_id}/named")

    def test_resource_route_definitions_include_extension_endpoint_only_resources(self):
        registry = ResourceRegistry()
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="post",
                endpoint="like",
                module_id="likes",
                handler=lambda context: {"ok": True},
                methods=("POST", "DELETE"),
                path="posts/{object_id}/like",
                absolute_path=True,
            )
        )

        routes = {
            (route.resource, route.endpoint, route.methods): route.path
            for route in build_resource_route_definitions(registry)
        }

        self.assertEqual(routes[("post", "like", ("DELETE", "POST"))], "/posts/{object_id}/like")

    def test_resource_endpoint_routes_are_registered_on_api_application(self):
        registry = ResourceRegistry()

        class Item:
            objects = None

            def __init__(self, id=1, title="hello"):
                self.id = id
                self.title = title

        class QuerySet(list):
            def filter(self, **kwargs):
                return QuerySet([item for item in self if str(item.id) == str(kwargs.get("pk"))])

            def first(self):
                return self[0] if self else None

        class Manager:
            def all(self):
                return QuerySet([Item()])

        Item.objects = Manager()

        class ItemResource(DatabaseResource):
            model = Item

            def type(self):
                return "auto_items"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title)]

            def endpoints(self):
                return [ResourceEndpoint.show()]

        registry.register_resource(ItemResource())
        host = SimpleNamespace(
            resources=registry,
            make=lambda key, default=None: SimpleNamespace(get_mounts=lambda: ()) if key == "routes" else default,
        )
        api = build_api_application(extension_host=host, urls_namespace=f"auto-resource-test-api-{uuid.uuid4().hex}")
        api_urls = api.urls
        self.assertTrue(any(
            "auto_items" in str(pattern)
            for pattern in api_urls[0]
        ))
        urlconf_name = "apps.core.tests_auto_resource_urls"
        urlconf = ModuleType(urlconf_name)
        urlconf.urlpatterns = [path("api/", api_urls)]
        sys.modules[urlconf_name] = urlconf

        try:
            clear_url_caches()
            with override_settings(ROOT_URLCONF=urlconf_name):
                with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                    response = self.client.get("/api/auto_items/1")
        finally:
            clear_url_caches()
            sys.modules.pop(urlconf_name, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"data": {"type": "auto_items", "id": "1", "links": {"self": "/api/auto_items/1"}, "attributes": {"title": "hello"}}},
        )

class ForumRegistryTests(TestCase):
    def test_core_registry_exposes_default_comment_post_type(self):
        registry = get_forum_registry()

        self.assertEqual(registry.get_default_post_type_code(), "comment")
        self.assertIn("comment", registry.get_stream_post_type_codes())
        self.assertIn("comment", registry.get_searchable_post_type_codes())
        self.assertIn("comment", registry.get_discussion_counted_post_type_codes())
        self.assertIn("comment", registry.get_user_counted_post_type_codes())

    def test_core_registry_exposes_discussion_sort_catalog(self):
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

    def test_core_registry_exposes_discussion_list_filter_catalog(self):
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

    def test_search_api_supports_registered_unread_filter(self):
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
            discussion=read_discussion,
            user=self.user,
            defaults={"is_subscribed": False, "last_read_post_number": read_discussion.last_post_number or 1},
        )
        DiscussionUser.objects.update_or_create(
            discussion=unread_discussion,
            user=self.user,
            defaults={"is_subscribed": False, "last_read_post_number": 0},
        )

        unread_response = self.client.get(
            "/api/search",
            {"q": "关注过滤关键字 is:unread", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(unread_response.status_code, 200, unread_response.content)
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

    def test_search_filters_api_returns_registered_filter_catalog(self):
        response = self.client.get("/api/search/filters")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["target"], "all")
        syntaxes = {item["syntax"] for item in payload["filters"]}
        self.assertIn("author:<username>", syntaxes)
        self.assertIn("is:unread", syntaxes)
        self.assertIn("created:YYYY-MM", syntaxes)

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
        self.assertIn("created:YYYY-MM", {item["syntax"] for item in discussions_payload["filters"]})
        self.assertIn("created:YYYY-MM", {item["syntax"] for item in posts_payload["filters"]})

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
            and (
                (Path(settings.BASE_DIR) / app.replace(".", "/") / "tests.py").exists()
                and "def test_" in (Path(settings.BASE_DIR) / app.replace(".", "/") / "tests.py").read_text(encoding="utf-8")
            )
        ]
        extension_labels = [
            f"extensions.{extension_dir.name}.backend.tests"
            for extension_dir in sorted((Path(settings.BASE_DIR) / "extensions").iterdir(), key=lambda item: item.name)
            if extension_dir.is_dir()
            and extension_dir.name.isidentifier()
            and (extension_dir / "backend" / "tests.py").exists()
        ]

        suite = runner.build_suite([])

        discovered = set()
        discovered_extensions = set()
        stack = [suite]
        while stack:
            item = stack.pop()
            if hasattr(item, "__iter__") and not hasattr(item, "_testMethodName"):
                stack.extend(list(item))
                continue
            module = item.__class__.__module__
            module_name = module.split(".")[0:3]
            if module.startswith("extensions."):
                discovered_extensions.add(".".join(module.split(".")[:4]))
            else:
                discovered.add(".".join(module_name[:2]) + ".tests")

        for label in labels:
            self.assertIn(label, discovered)
        for label in extension_labels:
            self.assertIn(label, discovered_extensions)

    def test_migrated_extension_behavior_tests_do_not_live_in_old_app_modules(self):
        checks = {
            "apps/posts/tests.py": [
                "PostLike",
                "PostFlag",
                "PostMentionsUser",
                "report_post",
                "like_post",
                "mentionsUsers",
                "auto_follows_through_subscriptions_extension",
                "cleans_discussion_reply_notifications_through_subscriptions_extension",
                "post_can_enter_approval_queue",
                "author_can_still_view_rejected_reply",
                "postApproved",
                "postRejected",
                "postResubmitted",
                "cannot_reply_in_tag_without_reply_permission",
                "discussion_tags_payload",
            ],
            "apps/discussions/tests.py": [
                "auto_follows_through_subscriptions_extension",
                "subscription",
                "\"following\"",
                "/following",
                "discussion_can_enter_approval_queue",
                "author_can_still_view_rejected_discussion",
                "discussionApproved",
                "discussionRejected",
                "discussionResubmitted",
                "discussion_list_filters_by_tag_slug",
                "discussion_list_hides_staff_only_tag",
                "cannot_create_discussion_in_staff_only_tag",
                "updating_discussion_tags_creates_discussion_tagged_event_post",
                "update_discussion_dispatches_tag_stats_refresh_request_event",
                "update_discussion_dispatches_discussion_tagged_event_with_all_affected_tag_ids",
                "delete_discussion_dispatches_tag_refresh_through_extension_lifecycle",
                "cannot_create_discussion_with_secondary_tag_only",
                "cannot_create_discussion_with_two_primary_tags",
                "cannot_create_discussion_with_mismatched_parent_child_tags",
                "discussion_tags_payload",
                "registered_user_and_tags",
            ],
            "apps/users/tests.py": [
                "user_detail_exposes_can_mention_groups_for_self",
                "canMentionGroups",
            ],
            "apps/core/tests.py": [
                "Admin" + "ApprovalQueueApiTests",
                "/api/admin/" + "approval-queue",
                "Admin" + "FlagManagementApiTests",
                "/api/admin/" + "flags",
                "Admin" + "TagManagementApiTests",
                "/api/admin/" + "tags",
                "admin.tag." + "refresh_stats",
                "test_discussion_list_search_respects_post_" + "approval_visibility",
                "test_search_api_respects_discussion_" + "approval_visibility",
                "test_search_api_respects_post_" + "approval_visibility",
                "test_search_api_hides_discussions_in_staff_only_" + "tags",
                "test_search_api_supports_registered_tag_filter_" + "syntax",
                "test_search_api_supports_registered_" + "mentioned_me_filter_syntax",
                "test_search_api_supports_registered_" + "mentioned_me_filter_for_first_post",
                "test_public_forum_settings_expose_flags_" + "forum_resource_fields_for_staff",
                "test_public_forum_settings_expose_tags_" + "forum_resource_fields",
                "test_extension_detail_api_surfaces_registered_resources_for_" + "likes_extension",
                "test_extension_detail_api_surfaces_frontend_for_" + "notifications_extension",
                "test_extension_detail_api_surfaces_registered_capabilities_for_" + "subscriptions_extension",
                "test_extension_detail_api_surfaces_registered_capabilities_for_" + "mentions_extension",
                "test_extension_detail_api_surfaces_registered_capabilities_for_" + "flags_extension",
                "test_extension_detail_api_surfaces_registered_resources_for_" + "tags_extension",
                "test_extension_detail_api_surfaces_registered_capabilities_for_" + "approval_extension",
                "test_mentions_extension_conditionally_renders_tag_" + "mentions_when_tags_enabled",
                "tag:" + "<slug>",
                "is:" + "following",
                "mentioned:" + "me",
                "test_public_forum_settings_expose_extension_" + "forum_settings_subset",
            ],
            "apps/notifications/tests.py": [
                "TestCase",
                "NotificationService",
                "def test_",
            ],
            "apps/tags/tests.py": [
                "TestCase",
                "TagService",
                "DiscussionTag",
                "def test_",
            ],
        }

        for relative_path, forbidden_patterns in checks.items():
            path = Path(settings.BASE_DIR) / relative_path
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertNotIn(pattern, source, f"{relative_path} still contains migrated extension test behavior")

    def test_extension_owned_models_are_not_redefined_in_core_model_modules(self):
        checks = {
            "apps/posts/models.py": [
                "class PostLike",
                "class PostFlag",
                "class PostMentionsUser",
            ],
            "apps/tags/models.py": [
                "class Tag",
                "class DiscussionTag",
            ],
            "apps/notifications/models.py": [
                "class Notification",
            ],
        }

        for relative_path, forbidden_patterns in checks.items():
            path = Path(settings.BASE_DIR) / relative_path
            source = path.read_text(encoding="utf-8") if path.exists() else ""
            for pattern in forbidden_patterns:
                self.assertNotIn(pattern, source, f"{relative_path} redefines extension-owned model")


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
            extension_payload=discussion_tags_payload([self.tag.id]),
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
                extension_payload=discussion_tags_payload([self.tag.id, child_tag.id]),
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

    @patch("apps.core.admin_settings_api.SearchIndexService.rebuild_postgres_indexes")
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

    @patch("apps.core.admin_settings_api.SearchIndexService.rebuild_postgres_indexes")
    def test_search_index_rebuild_reports_unsupported_database(self, rebuild_indexes):
        rebuild_indexes.side_effect = RuntimeError("当前数据库不是 PostgreSQL，全文索引无需重建")

        response = self.client.post(
            "/api/admin/search-indexes/rebuild",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "当前数据库不是 PostgreSQL，全文索引无需重建")
        self.assertFalse(AuditLog.objects.filter(action="admin.search_indexes.rebuild").exists())

    @patch("apps.core.admin_settings_api.QueueService.get_worker_status")
    @patch("apps.core.admin_settings_api.SearchIndexService.get_status")
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
        self.assertIn("extension_runtime", payload)
        self.assertIn("stamp", payload["extension_runtime"])
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
        mentions_extension = next(item for item in payload["enabled_extensions"] if item["id"] == "mentions")
        self.assertEqual(mentions_extension["settings_values"], {})
        self.assertEqual(mentions_extension["forum_settings"], {})
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
        self.assertFalse(any(item["id"] == "sample-hello" for item in payload["enabled_extensions"]))
        self.assertNotIn("auth_turnstile_secret_key", payload)

    def test_public_forum_settings_expose_realtime_typing_toggle(self):
        Setting.objects.update_or_create(
            key="advanced.realtime_typing_enabled",
            defaults={"value": json.dumps(False)},
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["realtime_typing_enabled"])

    def test_public_forum_settings_filters_disabled_extension_runtime_capabilities(self):
        self.addCleanup(reset_extension_runtime_state)
        self.addCleanup(clear_runtime_setting_caches)
        ExtensionInstallation.objects.update_or_create(
            extension_id="approval",
            defaults={
                "version": "1.0.0",
                "source": "filesystem",
                "enabled": False,
                "installed": True,
                "booted": False,
            },
        )
        reset_extension_runtime_state()
        clear_runtime_setting_caches()

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertNotIn("approval", payload["enabled_modules"])
        self.assertFalse(any(item["id"] == "approval" for item in payload["enabled_extensions"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["notification_types"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["user_preferences"]))
        self.assertFalse(any(item["module_id"] == "approval" for item in payload["post_types"]))

    @patch("apps.core.admin_settings_api.FileUploadService.upload_site_asset")
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
    def test_public_forum_settings_rebuilds_stale_cache_payload_missing_runtime_fields(self):
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(60)},
        )
        clear_runtime_setting_caches()
        from django.core.cache import cache

        cache.set(
            "settings.public.forum",
            {
                "forum_title": "过期缓存标题",
                "notification_types": [],
                "user_preferences": [],
                "post_types": [],
            },
            60,
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("enabled_modules", payload)
        self.assertIn("enabled_extensions", payload)
        self.assertIn("core", payload["enabled_modules"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_maintenance_mode_blocks_public_api_but_keeps_admin_paths_available(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode_key",
            defaults={"value": json.dumps("high")},
        )
        Setting.objects.update_or_create(
            key="advanced.maintenance_message",
            defaults={"value": json.dumps("站点维护中，请稍后回来。")},
        )
        clear_runtime_setting_caches()

        public_settings_response = self.client.get("/api/forum")
        self.assertEqual(public_settings_response.status_code, 200, public_settings_response.content)
        self.assertTrue(public_settings_response.json()["maintenance_mode"])
        self.assertEqual(public_settings_response.json()["maintenance_mode_key"], "high")
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
    def test_low_maintenance_mode_allows_reads_but_blocks_writes(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode_key",
            defaults={"value": json.dumps("low")},
        )
        clear_runtime_setting_caches()

        read_response = self.client.get("/api/search", {"q": "维护"})
        self.assertNotEqual(read_response.status_code, 503, read_response.content)

        write_response = self.client.post("/api/discussions", data={}, content_type="application/json")
        self.assertEqual(write_response.status_code, 503, write_response.content)
        self.assertEqual(write_response.json()["maintenance_mode_key"], "low")

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

    def test_markdown_preview_applies_extension_formatter_pipeline(self):
        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "今天真开心 :)"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("🙂", response.json()["html"])


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
    @patch("apps.core.admin_runtime_summary.runtime_probe_redis_ping")
    @patch("apps.core.admin_runtime_summary.cache.get", return_value="ok")
    @patch("apps.core.admin_runtime_summary.cache.set", return_value=None)
    @patch("apps.core.admin_settings_api.QueueService.get_worker_status")
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
    @patch("apps.core.admin_runtime_summary.cache.get", side_effect=RuntimeError("cache offline"))
    @patch("apps.core.admin_runtime_summary.cache.set", side_effect=RuntimeError("cache offline"))
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
    @patch("apps.core.admin_runtime_summary.runtime_probe_redis_ping")
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
    @patch("apps.core.admin_settings_api.QueueService.get_worker_status")
    @patch("apps.core.admin_settings_api.get_runtime_advanced_settings")
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
    @patch("apps.core.admin_runtime_summary.cache.get", return_value="ok")
    @patch("apps.core.admin_runtime_summary.cache.set", return_value=None)
    @patch("apps.core.admin_runtime_summary.runtime_probe_redis_ping")
    @patch("apps.core.admin_settings_api.QueueService.get_worker_status")
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
    @patch("apps.core.admin_runtime_summary.cache.get", return_value="ok")
    @patch("apps.core.admin_runtime_summary.cache.set", return_value=None)
    @patch("apps.core.admin_runtime_summary.runtime_probe_redis_ping")
    @patch("apps.core.admin_settings_api.QueueService.get_worker_status")
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
            __module__ = "extensions.notifications.backend.tasks"
            name = "extensions.notifications.backend.tasks.dispatch_notification_batch"

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
                with patch.dict(
                    os.environ,
                    {
                        "DB_NAME": "",
                        "DB_USER": "",
                        "DB_PASSWORD": "",
                        "BIAS_SITE_CONFIG": "",
                    },
                    clear=False,
                ), override_settings(BASE_DIR=Path(temp_dir)):
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
                        "BIAS_SITE_CONFIG": "",
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

        self.assertTrue(set(get_registry_staff_managed_admin_permission_codes()).issubset(permissions))
        self.assertIn("admin.approval.view", permissions)
        self.assertIn("admin.flag.view", permissions)


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

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "attention_count": 0,
                    },
                    "extensions": [],
                }
                with override_settings(BASE_DIR=base_dir):
                    call_command("prepare_release", "--tag", "v1.2.3")
                validate_mock.assert_called_once_with("validate_extensions", "--strict")

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

    def test_prepare_release_rejects_extension_attention_by_default(self):
        temp_dir = make_workspace_temp_dir()
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

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "blocking_count": 2,
                        "warning_count": 0,
                        "attention_count": 2,
                    },
                    "extensions": [],
                }
                with override_settings(BASE_DIR=base_dir):
                    with self.assertRaisesMessage(CommandError, "扩展诊断存在 2 个阻断项"):
                        call_command("prepare_release", "--set-version", "1.0.0", "--allow-dirty")
                validate_mock.assert_called_once_with("validate_extensions", "--strict")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_prepare_release_can_write_extension_report(self):
        temp_dir = make_workspace_temp_dir()
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
            report_path = base_dir / "artifacts" / "extensions-report.json"

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "blocking_count": 0,
                        "warning_count": 0,
                        "attention_count": 0,
                        "asset_count": 5,
                        "frontend_bundle_count": 2,
                        "migration_bundle_count": 1,
                        "locale_bundle_count": 1,
                        "signed_extension_count": 0,
                    },
                    "extensions": [{"id": "core"}],
                }
                with override_settings(BASE_DIR=base_dir):
                    call_command(
                        "prepare_release",
                        "--set-version",
                        "1.0.0",
                        "--allow-dirty",
                        "--extension-report",
                        str(report_path),
                    )
                validate_mock.assert_called_once_with("validate_extensions", "--strict")

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["attention_count"], 0)
            self.assertEqual(payload["summary"]["asset_count"], 5)
            self.assertEqual(payload["summary"]["frontend_bundle_count"], 2)
            self.assertEqual(payload["extensions"][0]["id"], "core")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
            "--allow-extension-attention",
            "--extension-report",
            "artifacts/extensions.json",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3", "--allow-dirty", "--allow-extension-attention", "--dry-run", "--extension-report", "artifacts/extensions.json"),
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

    def test_permissions_api_ignores_unknown_stored_codes_on_read(self):
        Permission.objects.create(group=self.group, permission="reply")
        Permission.objects.create(group=self.group, permission="editPosts")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        group_permissions = payload.get(str(self.group.id), payload.get(self.group.id, []))
        self.assertEqual(group_permissions, [])

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

    def test_permissions_api_rejects_unknown_codes_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["reply", "editPosts", "reply"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Permission.objects.filter(group=self.group).count(), 0)

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
        self.assertIn("modules", payload)
        self.assertNotIn("aliases", payload)
        section_names = {section["name"] for section in payload["sections"]}
        self.assertIn("view", section_names)
        self.assertIn("moderate", section_names)
        all_permission_codes = {
            permission["name"]
            for section in payload["sections"]
            for permission in section["permissions"]
        }
        self.assertIn("discussion.reply", all_permission_codes)
        for section in payload["sections"]:
            for permission in section["permissions"]:
                self.assertNotIn("aliases", permission)
        self.assertTrue(any(module["id"] == "core" for module in payload["modules"]))

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

    def test_registry_staff_managed_admin_permission_helper_uses_registered_admin_permissions(self):
        self.assertTrue(
            {
                "admin.approval.view",
                "admin.approval.approve",
                "admin.approval.reject",
                "admin.flag.view",
                "admin.flag.resolve",
            }.issubset(set(get_registry_staff_managed_admin_permission_codes()))
        )

    def test_search_index_definition_limits_post_index_to_registered_searchable_types(self):
        post_index = next(definition for definition in get_search_index_definitions() if definition["name"] == "posts_content_fts_idx")
        self.assertIn("WHERE type IN ('comment')", post_index["create"])


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
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_inspect_extensions(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "inspect_extensions"]
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
