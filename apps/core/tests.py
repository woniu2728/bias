import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
from io import StringIO
from subprocess import CompletedProcess
import sys
from types import ModuleType, SimpleNamespace
import uuid

from django.conf import settings
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, path
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from unittest.mock import Mock, patch

from apps.core.domain_events import DomainEvent, DomainEventBus, get_forum_event_bus
from apps.core.extensions.backend import run_extension_backend_hook
from apps.core.extensions.exceptions import ExtensionStateError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.registry import ExtensionRegistry
from apps.core.extensions import ApiResourceExtender, ConditionalExtender, PostEventExtender, SearchDriverExtender, get_extension_registry
from apps.core.extensions.extenders import ResourceExtender
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
    get_extension_frontend_build_manifest_path,
    get_frontend_vite_manifest_path,
    get_published_frontend_root,
    inspect_extension_frontend_output_manifest,
    recompile_extension_frontend_assets,
    write_extension_frontend_import_map,
    write_extension_frontend_output_manifest,
)
from apps.core.extensions.runtime_event_listeners import bootstrap_extension_runtime_event_listeners
from apps.core.extensions.runtime_access import (
    evaluate_runtime_extension_policy,
    evaluate_runtime_model_policy,
)
from apps.core.forum_permissions import has_forum_permission
from apps.core.extensions.lifecycle import reset_extension_runtime_state
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
from apps.core.extension_django_apps import discover_extension_django_apps, discover_extension_django_migration_modules
from apps.core.extension_service import ExtensionService
from apps.core.middleware import ExtensionRequestMiddleware
from apps.core.api_runtime import build_api_application
from apps.core.forum_registry import (
    ForumRegistry,
    get_forum_registry,
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
from apps.core.resource_routes import build_resource_path_route_definitions, build_resource_route_definitions
from apps.core.resource_search import ResourceSearchFilter, ResourceSearchManager, ResourceSearchState
from apps.core.resource_serializer import ResourceSerializer
from apps.core.resource_context import ResourceContext
from apps.core.resource_validation import ResourceValidationError, ResourceValidator, ResourceValidatorFactory
from apps.core.bootstrap_config import load_site_bootstrap, read_site_config
from apps.core.models import AuditLog, ExtensionInstallation, Setting
from apps.core.release import build_git_command, ensure_release_versions_aligned
from apps.core.settings_service import (
    clear_runtime_setting_caches,
    get_advanced_settings,
    get_extension_setting_group_defaults,
    get_public_forum_settings,
    get_setting_group,
)
from apps.core.test_runner import BiasDiscoverRunner
from apps.core.websocket_auth import (
    REFRESH_TOKEN_COOKIE_NAME,
    _parse_cookie_header,
    resolve_user_from_refresh_token,
    resolve_user_from_token,
)


class RuntimeModelProxy:
    def __init__(self, app_label, model_name):
        self._app_label = app_label
        self._model_name = model_name

    @property
    def model(self):
        return apps.get_model(self._app_label, self._model_name)

    def __getattr__(self, name):
        return getattr(self.model, name)


Discussion = RuntimeModelProxy("discussions", "Discussion")
DiscussionUser = RuntimeModelProxy("discussions", "DiscussionUser")
Post = RuntimeModelProxy("posts", "Post")
Group = RuntimeModelProxy("users", "Group")
Permission = RuntimeModelProxy("users", "Permission")
User = RuntimeModelProxy("users", "User")


@dataclass(frozen=True)
class TestDiscussionCreatedEvent(DomainEvent):
    discussion_id: int
    actor_user_id: int
    is_approved: bool = True


@dataclass(frozen=True)
class TestUserSuspendedEvent(DomainEvent):
    user_id: int
    actor_user_id: int | None


@dataclass(frozen=True)
class TestUserUnsuspendedEvent(DomainEvent):
    user_id: int
    actor_user_id: int | None


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


TEST_EXTENSION_ID = "alpha-tools"


def make_extension_test_base_dir() -> Path:
    base_dir = make_workspace_temp_dir()
    extensions_dir = base_dir / "extensions"
    shutil.copytree(
        Path.cwd() / "extensions",
        extensions_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    create_alpha_tools_extension(extensions_dir)
    return base_dir


def create_alpha_tools_extension(extensions_dir: Path) -> Path:
    manifest_dir = extensions_dir / TEST_EXTENSION_ID
    backend_dir = manifest_dir / "backend"
    migrations_dir = backend_dir / "django_migrations"
    admin_dir = manifest_dir / "frontend" / "admin"
    forum_dir = manifest_dir / "frontend" / "forum"
    locale_dir = manifest_dir / "locale"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    admin_dir.mkdir(parents=True, exist_ok=True)
    forum_dir.mkdir(parents=True, exist_ok=True)
    locale_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "__init__.py").write_text("", encoding="utf-8")
    (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
    (backend_dir / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class AlphaToolsConfig(AppConfig):\n"
        "    default_auto_field = 'django.db.models.BigAutoField'\n"
        "    name = 'extensions.alpha_tools.backend'\n"
        "    label = 'alpha_tools'\n"
        "    verbose_name = 'Alpha Tools'\n",
        encoding="utf-8",
    )
    (manifest_dir / "extension.json").write_text(json.dumps({
        "id": TEST_EXTENSION_ID,
        "name": "Alpha Tools",
        "version": "0.1.0",
        "description": "测试扩展，用于验证 Bias 扩展 lifecycle、设置和前端入口协议。",
        "authors": [
            {"name": "Alpha Maintainer", "homepage": "https://bias.local/authors/alpha"},
            {"name": "Security Contact", "email": "security-author@bias.local"},
        ],
        "dependencies": ["core"],
        "homepage": "https://bias.local/extensions/alpha-tools",
        "documentation_url": "https://bias.local/docs/alpha-tools",
        "backend_entry": "extensions.alpha_tools.backend.ext",
        "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
        "django_app_label": "alpha_tools",
        "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
        "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
        "settings_pages": ["/admin/extensions/alpha-tools/settings"],
        "permissions_pages": ["/admin/extensions/alpha-tools/permissions"],
        "operations_pages": ["/admin/extensions/alpha-tools/operations"],
        "settings_schema": [
            {"key": "welcome_message", "label": "欢迎语", "type": "text", "default": "欢迎使用 Alpha Tools"},
            {"key": "card_tone", "label": "卡片风格", "type": "select", "default": "primary", "options": [
                {"value": "primary", "label": "主色"},
                {"value": "warm", "label": "暖色"},
            ]},
            {"key": "show_runtime_tips", "label": "显示运行提示", "type": "boolean", "default": True},
        ],
        "compatibility": {
            "bias_version": "^1.0.0",
            "api_version": "1.0",
            "api_stability": "experimental",
            "api_stability_label": "实验性",
        },
        "distribution": {
            "channel": "private",
            "channel_label": "私有分发",
            "abandoned": True,
            "replacement": "beta-tools",
        },
        "security": {
            "support_email": "security@bias.local",
            "capabilities_notice": "测试扩展仅用于验证扩展协议，不提供生产能力。",
        },
        "admin_actions": [
            {"key": "details", "label": "查看详情", "kind": "route", "target": "/admin/extensions/alpha-tools", "order": 10},
            {"key": "documentation", "label": "文档", "kind": "link", "target": "/admin/docs/extensions", "order": 50},
        ],
        "runtime_actions": [
            {"key": "rebuild-cache", "label": "刷新缓存", "hook": "run_rebuild_cache", "requires_enabled": True, "requires_installed": True}
        ],
        "operations_profile": {
            "kicker": "Alpha Runtime",
            "recommended_action_keys": ["settings", "operations", "details"],
        },
        "extra": {
            "product_hidden": True,
            "links": {
                "source": "https://bias.local/source/alpha-tools",
                "discuss": "https://bias.local/discuss/alpha-tools",
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    (manifest_dir / "README.md").write_text(
        "# Alpha Tools\n\n"
        "Alpha Tools README for extension detail rendering.\n",
        encoding="utf-8",
    )
    (backend_dir / "ext.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "from apps.core.extensions import LifecycleExtender, SettingsExtender\n"
        "from apps.core.extensions.backend import _build_setting_field_definition\n"
        "\n"
        "def extend():\n"
        "    return [\n"
        "        LifecycleExtender(install=install, enable=enable, disable=disable, uninstall=uninstall),\n"
        "        SettingsExtender(fields=(\n"
        "            _build_setting_field_definition({'key': 'welcome_message', 'label': '欢迎语', 'type': 'text', 'default': '欢迎使用 Alpha Tools'}),\n"
        "            _build_setting_field_definition({'key': 'card_tone', 'label': '卡片风格', 'type': 'select', 'default': 'primary', 'options': ({'value': 'primary', 'label': '主色'}, {'value': 'warm', 'label': '暖色'})}),\n"
        "            _build_setting_field_definition({'key': 'show_runtime_tips', 'label': '显示运行提示', 'type': 'boolean', 'default': True}),\n"
        "        )),\n"
        "    ]\n"
        "\n"
        "def install(context):\n"
        "    return {'status': 'ok', 'status_label': '已完成', 'details': {'extension_id': context.extension_id}}\n"
        "\n"
        "def enable(context):\n"
        "    return {'status': 'ok', 'status_label': '已启用'}\n"
        "\n"
        "def disable(context):\n"
        "    return {'status': 'ok', 'status_label': '已停用'}\n"
        "\n"
        "def uninstall(context):\n"
        "    return {'status': 'ok', 'status_label': '已完成'}\n"
        "\n"
        "def run_rebuild_cache(context):\n"
        "    return {'status': 'ok', 'status_label': '已刷新'}\n"
        "\n",
        encoding="utf-8",
    )
    (migrations_dir / "0001_bootstrap.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = []\n",
        encoding="utf-8",
    )
    (admin_dir / "index.js").write_text(
        "export function extend() {}\n"
        "export function resolveDetailPage() { return null }\n"
        "export function resolveSettingsPage() { return null }\n"
        "export function resolvePermissionsPage() { return null }\n"
        "export function resolveOperationsPage() { return null }\n",
        encoding="utf-8",
    )
    (forum_dir / "index.js").write_text("export function extend() {}\n", encoding="utf-8")
    (locale_dir / "zh-CN.json").write_text(json.dumps({"extension.name": "Alpha Tools"}, ensure_ascii=False), encoding="utf-8")
    return manifest_dir


class DomainEventBusTests(TestCase):
    def test_dispatches_registered_event_handlers(self):
        bus = DomainEventBus()
        received = []

        def handle_created(event):
            received.append((event.discussion_id, event.actor_user_id, event.is_approved))

        bus.register(TestDiscussionCreatedEvent, handle_created)
        bus.dispatch(
            TestDiscussionCreatedEvent(
                discussion_id=7,
                actor_user_id=3,
                is_approved=True,
            )
        )

        self.assertEqual(received, [(7, 3, True)])

    def test_register_deduplicates_explicit_listener_key(self):
        bus = DomainEventBus()
        received = []

        def handle_created(event):
            received.append("first")

        def reloaded_handle_created(event):
            received.append("reloaded")

        listener_key = ("alpha-tools", "DiscussionCreatedEvent", "handle_created")
        bus.register(TestDiscussionCreatedEvent, handle_created, listener_key=listener_key)
        bus.register(TestDiscussionCreatedEvent, reloaded_handle_created, listener_key=listener_key)
        bus.dispatch(
            TestDiscussionCreatedEvent(
                discussion_id=7,
                actor_user_id=3,
                is_approved=True,
            )
        )

        self.assertEqual(received, ["first"])

    def test_dispatches_handlers_for_additional_domain_events(self):
        bus = DomainEventBus()
        received = []

        def handle_suspended(event):
            received.append(("suspended", event.user_id, event.actor_user_id))

        def handle_unsuspended(event):
            received.append(("unsuspended", event.user_id, event.actor_user_id))

        bus.register(TestUserSuspendedEvent, handle_suspended)
        bus.register(TestUserUnsuspendedEvent, handle_unsuspended)
        bus.dispatch(TestUserSuspendedEvent(user_id=9, actor_user_id=2))
        bus.dispatch(TestUserUnsuspendedEvent(user_id=9, actor_user_id=2))

        self.assertEqual(
            received,
            [("suspended", 9, 2), ("unsuspended", 9, 2)],
        )


@dataclass(frozen=True)
class AlphaStringEvent(DomainEvent):
    value: str


@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class ExtensionManifestLoaderTests(TestCase):
    def test_discovers_declared_extension_django_apps_and_infers_migration_modules(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
            }, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(
                discover_extension_django_apps(temp_dir),
                ["extensions.alpha_tools.backend.apps.AlphaToolsConfig"],
            )
            self.assertEqual(
                discover_extension_django_migration_modules(temp_dir),
                {"alpha_tools": "extensions.alpha_tools.backend.django_migrations"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_discovers_explicit_extension_django_app_label(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_app_label": "alpha",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifest = loader.discover_manifests()[0]

            self.assertEqual(manifest.django_app_label, "alpha")
            self.assertEqual(
                discover_extension_django_migration_modules(temp_dir),
                {"alpha": "extensions.alpha_tools.backend.django_migrations"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
                    "kicker": "Alpha Runtime",
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
            self.assertEqual(results[0].manifest.operations_profile["kicker"], "Alpha Runtime")
            self.assertEqual(results[0].manifest.operations_profile["focus_panels"][0]["key"], "notification_types")
            self.assertEqual(results[0].manifest.admin_actions[0].key, "details")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_schema[0].key, "theme")
            self.assertFalse(hasattr(results[0].manifest, "migration_namespace"))
            self.assertEqual(results[0].manifest.django_app_config, "")
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
                "        (FrontendExtender()\n"
                "            .admin('extensions/alpha-tools/frontend/admin/index.js')\n"
                "            .forum('extensions/alpha-tools/frontend/forum/index.js')),\n"
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

    def test_application_bootstrap_collects_extension_websocket_routes(self):
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
                "from channels.generic.websocket import AsyncWebsocketConsumer\n"
                "from apps.core.extensions import WebSocketRoutesExtender\n"
                "\n"
                "class AlphaConsumer(AsyncWebsocketConsumer):\n"
                "    pass\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        WebSocketRoutesExtender().route(r'ws/alpha/$', 'alpha.websocket', AlphaConsumer),\n"
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
            routes = application.get_websocket_routes()
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0].path, "ws/alpha/$")
            self.assertEqual(routes[0].name, "alpha.websocket")
            self.assertEqual(routes[0].module_id, "alpha-tools")
            self.assertEqual(runtime_view.websocket_routes[0].name, "alpha.websocket")
            self.assertEqual(runtime_view.extender_keys, ("WebSocketRoutesExtender",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_frontend_extender_aliases_match_runtime_registration(self):
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
                "        (FrontendExtender()\n"
                "            .js('forum.js')\n"
                "            .js('admin.js', frontend='admin')\n"
                "            .common('common.js')\n"
                "            .css('forum.css')\n"
                "            .jsDirectory('chunks')\n"
                "            .preload([\n"
                "                {'href': '/x.js', 'as': 'script'},\n"
                "                {'href': '/x.css', 'as': 'style'},\n"
                "            ])\n"
                "            .extraDocumentAttributes({'data-alpha': '1'})\n"
                "            .extraDocumentClasses('alpha-page')\n"
                "            .route('/alpha', 'alpha', 'AlphaPage')\n"
                "            .removeRoute('old-alpha')),\n"
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

            application = build_extension_application(manager=ExtensionRegistry(extensions_path=extensions_dir), force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(runtime_view.frontend_forum_entry, "forum.js")
            self.assertEqual(runtime_view.frontend_admin_entry, "admin.js")
            self.assertEqual(runtime_view.frontend_common_entry, "common.js")
            self.assertEqual(runtime_view.frontend_css, ("forum.css",))
            self.assertEqual(runtime_view.frontend_js_directories, ("chunks",))
            self.assertEqual(runtime_view.frontend_preloads[0]["as"], "script")
            self.assertEqual(runtime_view.frontend_preloads[1]["as"], "style")
            self.assertEqual(runtime_view.frontend_document_attributes[0]["data-alpha"], "1")
            self.assertIn({"class": "alpha-page"}, runtime_view.frontend_document_attributes)
            self.assertEqual(runtime_view.frontend_routes[0].path, "/alpha")
            self.assertEqual(runtime_view.frontend_routes[1].name, "old-alpha")
            self.assertTrue(runtime_view.frontend_routes[1].removed)
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

    def test_runtime_model_reference_resolves_model_relations_and_policies(self):
        from apps.core.extensions import ModelExtender, PolicyExtender, RuntimeModel, ServiceProviderExtender
        from apps.core.extensions.policy_runtime_service import evaluate_model_policy

        class DemoModel:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        runtime_model = RuntimeModel("alpha.model")

        ServiceProviderExtender(
            key="alpha.model",
            provider=lambda: {"model": DemoModel},
        ).extend(app, extension)
        ModelExtender(model=runtime_model).belongs_to_many(
            "followers",
            runtime_model,
            resolver=lambda instance: ["alice"],
            inject_attribute=False,
        ).extend(app, extension)
        PolicyExtender().policy(
            runtime_model,
            lambda user=None, ability="", model=None, **context: ability == "view",
        ).extend(app, extension)

        app.make("models")
        app.make("policies")

        relations = app.models.get_relations_for_model(DemoModel)
        self.assertEqual(relations[0].name, "followers")
        self.assertEqual(app.models.resolve_relation(DemoModel, "followers", DemoModel()), ["alice"])
        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            self.assertTrue(evaluate_model_policy("view", model=DemoModel(), default=False))

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

        event_data = app.make("post.events").resolve(
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

        discussion_model = Discussion.model

        app = ExtensionApplication()
        app.policies.query_model_policy(
            "alpha-tools",
            discussion_model,
            lambda **context: False if context["ability"] == "view" else None,
        )

        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            queryset = apply_model_visibility_scope(
                discussion_model,
                discussion_model.objects.all(),
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

    @override_settings(BIAS_EXTENSION_AUTO_FRONTEND_REBUILD=True, BIAS_EXTENSION_AUTO_FRONTEND_PUBLISH=True)
    def test_extension_runtime_invalidation_can_auto_rebuild_frontend_assets(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            RUNTIME_VERSION_KEY,
            invalidate_extension_frontend_assets,
        )

        class CompileResult:
            def to_dict(self):
                return {"status": "ok", "message": "rebuilt"}

        Setting.objects.filter(key__in=[RUNTIME_REBUILD_MARKER_KEY, RUNTIME_VERSION_KEY]).delete()
        with patch(
            "apps.core.extensions.frontend_compiler.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            result = invalidate_extension_frontend_assets("extension_enabled", extension_id="alpha-tools")

        self.assertTrue(result["auto_rebuild"])
        self.assertTrue(result["auto_publish"])
        recompile.assert_called_once()
        self.assertTrue(recompile.call_args.kwargs["run_build"])
        self.assertTrue(recompile.call_args.kwargs["clear_marker"])
        self.assertTrue(recompile.call_args.kwargs["publish_dist"])
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        self.assertIn("extension_enabled", Setting.objects.get(key=RUNTIME_VERSION_KEY).value)

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
                self.assertTrue(output_payload["input_revision"])
                self.assertFalse(output_payload["build"]["ran"])
                inspected = inspect_extension_frontend_output_manifest()
                self.assertEqual(inspected["input_revision"], output_payload["input_revision"])
                self.assertEqual(inspected["current_input_revision"], output_payload["input_revision"])
                self.assertFalse(inspected["input_stale"])
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
                self.assertTrue(output["input_revision"])
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

    def test_extension_frontend_output_manifest_detects_stale_extension_inputs(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                first_manifest = {
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                        }
                    }
                }
                second_manifest = {
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/changed.js",
                        }
                    }
                }
                output = build_extension_frontend_output_manifest(first_manifest)
                write_extension_frontend_output_manifest(output)
                build_manifest_path = get_extension_frontend_build_manifest_path()
                build_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                build_manifest_path.write_text(json.dumps(second_manifest, ensure_ascii=False), encoding="utf-8")

                inspected = inspect_extension_frontend_output_manifest()

                self.assertTrue(inspected["input_revision"])
                self.assertTrue(inspected["current_input_revision"])
                self.assertNotEqual(inspected["input_revision"], inspected["current_input_revision"])
                self.assertTrue(inspected["input_stale"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_recompile_extension_frontend_assets_reports_missing_npm(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extension = SimpleNamespace(
                    id="alpha-tools",
                    source="filesystem",
                    frontend_admin_entry="",
                    frontend_forum_entry="extensions/alpha-tools/frontend/forum/index.js",
                    manifest=SimpleNamespace(path=str(Path(temp_dir) / "extensions" / "alpha-tools")),
                    runtime=SimpleNamespace(enabled=True),
                    frontend_routes=(),
                    discover=lambda: SimpleNamespace(
                        frontend_css=(),
                        frontend_js_directories=(),
                        frontend_preloads=(),
                        frontend_document_attributes=(),
                        frontend_title_driver=None,
                        frontend_routes=(),
                    ),
                )
                with patch("apps.core.extensions.frontend_compiler.subprocess.run", side_effect=FileNotFoundError("npm")):
                    result = recompile_extension_frontend_assets([extension], run_build=True)

                self.assertEqual(result.status, "error")
                self.assertEqual(result.status_label, "编译环境缺失")
                self.assertIn("npm", result.message)
                self.assertTrue(result.input_revision)
                self.assertTrue(get_extension_frontend_output_manifest_path().exists())
                payload = json.loads(get_extension_frontend_output_manifest_path().read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "error")
                self.assertEqual(payload["status_label"], "编译环境缺失")
                self.assertEqual(payload["input_revision"], result.input_revision)
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

    def test_sync_extension_packages_creates_records_for_discovered_extensions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING, ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)

            self.assertEqual(result["created"], ["alpha-tools"])
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["package_inspection"]["summary"]["installation_record_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["unmanaged_discovered_count"], 1)
            self.assertFalse(installation.installed)
            self.assertFalse(installation.enabled)
            self.assertFalse(installation.booted)
            self.assertEqual(installation.version, "1.0.0")
            self.assertEqual(installation.source, "filesystem")
            self.assertTrue(installation.meta["sync"]["created"])
            self.assertEqual(lock["packages"][0]["id"], "alpha-tools")
            self.assertFalse(lock["packages"][0]["installed"])
            self.assertFalse(lock["packages"][0]["enabled"])
            self.assertFalse(lock["packages"][0]["missing"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extension_packages_preserves_auto_install_runtime_state_when_creating_records(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "users"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "users",
                    "name": "Users",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="users")

            self.assertEqual(result["created"], ["users"])
            self.assertEqual(result["package_inspection"]["summary"]["installation_record_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["unmanaged_discovered_count"], 0)
            self.assertTrue(installation.installed)
            self.assertTrue(installation.enabled)
            self.assertTrue(installation.booted)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_protected_auto_enabled_extension_loads_enabled_from_stale_disabled_record(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "discussions"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "discussions",
                    "name": "Discussions",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                        "protected": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="discussions",
                    version="1.0.0",
                    source="filesystem",
                    installed=True,
                    enabled=False,
                    booted=False,
                )

                extension = ExtensionManager(extensions_path=extensions_dir).get_extension("discussions")

            self.assertTrue(extension.runtime.installed)
            self.assertTrue(extension.runtime.enabled)
            self.assertTrue(extension.runtime.booted)
            self.assertEqual(extension.runtime.status_key, "active")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extension_packages_repairs_protected_auto_enabled_disabled_record(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "discussions"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "discussions",
                    "name": "Discussions",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                        "protected": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="discussions",
                    version="1.0.0",
                    source="filesystem",
                    installed=True,
                    enabled=False,
                    booted=False,
                )

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()
                installation = ExtensionInstallation.objects.get(extension_id="discussions")

            self.assertEqual(result["updated"], ["discussions"])
            self.assertTrue(installation.installed)
            self.assertTrue(installation.enabled)
            self.assertTrue(installation.booted)
            self.assertEqual(installation.meta["sync"]["reason"], "protected_extension_auto_enabled")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rebuild_api_urlpatterns_is_idempotent_after_runtime_sync(self):
        import config.urls as root_urls

        first_patterns = root_urls.rebuild_api_urlpatterns()
        second_patterns = root_urls.rebuild_api_urlpatterns()

        self.assertTrue(first_patterns)
        self.assertTrue(second_patterns)
        self.assertNotEqual(root_urls.api.urls_namespace, "bias-api-1")

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
                    "abandoned": "vendor/beta-tools",
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
            self.assertTrue(lock["packages"][0]["abandoned"])
            self.assertEqual(lock["packages"][0]["replacement"], "vendor/beta-tools")
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
            clear_realtime_service,
            iter_realtime_included_enrichers,
            iter_realtime_discussion_transports,
            resolve_realtime_visible_discussion_ids,
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
                "def visible_discussions(discussion_ids, user):\n"
                "    return [int(item) for item in discussion_ids if int(item) == 2]\n"
                "\n"
                "def broadcast_alpha(discussion_id, event_type, payload):\n"
                "    return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RealtimeExtender()\n"
                "            .included_payload('alpha', enrich_alpha, description='Alpha included payload')\n"
                "            .discussion_visibility(visible_discussions, description='Alpha discussion visibility')\n"
                "            .discussion_transport('alpha.websocket', broadcast_alpha, description='Alpha discussion transport'),\n"
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

            clear_realtime_service()
            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.realtime_included), 1)
            self.assertEqual(runtime_view.realtime_included[0].key, "alpha")
            self.assertEqual(len(runtime_view.realtime_discussion_visibility), 1)
            self.assertEqual(len(runtime_view.realtime_discussion_transports), 1)
            self.assertEqual(application.realtime.get_included_enrichers(extension_id="alpha-tools")[0].description, "Alpha included payload")
            self.assertEqual(
                application.realtime.get_discussion_visibility_resolvers(extension_id="alpha-tools")[0].description,
                "Alpha discussion visibility",
            )
            self.assertEqual(
                application.realtime.get_discussion_transports(extension_id="alpha-tools")[0].description,
                "Alpha discussion transport",
            )
            included_payload = {}
            for enricher in iter_realtime_included_enrichers():
                included_payload.update(enricher())

            self.assertEqual(included_payload["alpha"][0]["value"], "ok")
            self.assertEqual(resolve_realtime_visible_discussion_ids([1, 2], Mock()), [2])
            self.assertEqual(len(iter_realtime_discussion_transports()), 1)
        finally:
            clear_realtime_service()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_registers_string_domain_event_listeners(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (extensions_dir / "__init__.py").write_text("", encoding="utf-8")
            package_dir = extensions_dir / "alpha_tools"
            package_backend_dir = package_dir / "backend"
            package_backend_dir.mkdir(parents=True, exist_ok=False)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_backend_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import EventListenersExtender\n"
                "from apps.core.extensions.types import ExtensionEventListenerDefinition\n"
                "\n"
                "seen = []\n"
                "\n"
                "def record_alpha(event):\n"
                "    seen.append(event.value)\n"
                "\n"
                "def extend():\n"
                "    return [EventListenersExtender(listeners=(ExtensionEventListenerDefinition(\n"
                "        event_type='apps.core.tests.AlphaStringEvent',\n"
                "        handler=record_alpha,\n"
                "        description='String event listener',\n"
                "    ),))]\n",
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

            application.event_bus.dispatch(AlphaStringEvent(value="ok"))
            handler_state = runtime_view.event_listeners[0].handler.__globals__["seen"]

            self.assertIsNotNone(runtime_view)
            self.assertEqual(runtime_view.event_listeners[0].event_type, AlphaStringEvent)
            self.assertEqual(handler_state, ["ok"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_registers_extension_realtime_discussion_broadcasts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (extensions_dir / "__init__.py").write_text("", encoding="utf-8")
            package_dir = extensions_dir / "alpha_tools"
            package_backend_dir = package_dir / "backend"
            package_backend_dir.mkdir(parents=True, exist_ok=False)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_backend_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from dataclasses import dataclass\n"
                "from apps.core.domain_events import DomainEvent\n"
                "from apps.core.extensions import RealtimeExtender\n"
                "\n"
                "@dataclass(frozen=True)\n"
                "class AlphaDiscussionCreatedEvent(DomainEvent):\n"
                "    discussion_id: int\n"
                "    actor_user_id: int\n"
                "    is_approved: bool = True\n"
                "\n"
                "@dataclass(frozen=True)\n"
                "class AlphaDiscussionRenamedEvent(DomainEvent):\n"
                "    discussion_id: int\n"
                "    actor_user_id: int\n"
                "    old_title: str\n"
                "    new_title: str\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RealtimeExtender().broadcast_discussion_event(\n"
                "            AlphaDiscussionRenamedEvent,\n"
                "            'discussion.renamed',\n"
                "            include_discussion=True,\n"
                "            description='Alpha realtime broadcast',\n"
                "        ).broadcast_discussion_event(\n"
                "            AlphaDiscussionCreatedEvent,\n"
                "            'discussion.created',\n"
                "            include_discussion=True,\n"
                "            condition=lambda event: event.is_approved,\n"
                "            description='Approved discussion broadcast',\n"
                "        ),\n"
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
            self.assertEqual(len(runtime_view.realtime_discussion_broadcasts), 2)
            self.assertEqual(
                application.realtime.get_discussion_broadcasts(extension_id="alpha-tools")[0].description,
                "Alpha realtime broadcast",
            )
            broadcasts = application.realtime.get_discussion_broadcasts(extension_id="alpha-tools")
            renamed_event_type = broadcasts[0].event_type
            created_event_type = broadcasts[1].event_type
            broadcast = Mock()
            application.instance("realtime.discussion_broadcaster", broadcast)
            application.event_bus.dispatch(renamed_event_type(
                discussion_id=7,
                actor_user_id=3,
                old_title="Old title",
                new_title="New title",
            ))

            broadcast.assert_called_once_with(
                7,
                "discussion.renamed",
                include_discussion=True,
                include_post=False,
                post_id=None,
                post_id_getter=None,
                extension_context=None,
            )
            broadcast.reset_mock()

            application.event_bus.dispatch(created_event_type(
                discussion_id=8,
                actor_user_id=3,
                is_approved=False,
            ))
            application.event_bus.dispatch(created_event_type(
                discussion_id=8,
                actor_user_id=3,
                is_approved=True,
            ))

            broadcast.assert_called_once_with(
                8,
                "discussion.created",
                include_discussion=True,
                include_post=False,
                post_id=None,
                post_id_getter=None,
                extension_context=None,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_forum_permission_checkers(self):
        from apps.core.forum_permissions import clear_forum_permission_checkers, has_forum_permission

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
                "from apps.core.extensions import ForumPermissionExtender\n"
                "\n"
                "def can_use_alpha(user, permission_names):\n"
                "    return 'alpha.use' in permission_names\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ForumPermissionExtender().checker('alpha', can_use_alpha, description='Alpha permission checker'),\n"
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

            clear_forum_permission_checkers()
            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")
            user = Mock(is_authenticated=True)

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.forum_permission_checkers), 1)
            self.assertEqual(runtime_view.forum_permission_checkers[0].key, "alpha")
            self.assertEqual(application.forum_permissions.get_checkers(extension_id="alpha-tools")[0].description, "Alpha permission checker")
            self.assertTrue(has_forum_permission(user, "alpha.use"))
            self.assertFalse(has_forum_permission(user, "alpha.missing"))
        finally:
            clear_forum_permission_checkers()
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
            runtime_text_query, runtime_filters = application.search.extract_filter_tokens(
                "alpha:1 body",
                targets=("discussion",),
            )
            self.assertEqual(runtime_text_query, "body")
            self.assertEqual(runtime_filters["discussion"][0][0].code, "alpha")
            self.assertTrue(any(
                item.code == "alpha"
                for item in application.search.get_available_filters(targets=("discussion",))
            ))
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

    def test_extension_enabled_order_sync_reports_and_repairs_drift(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            beta_dir = extensions_dir / "beta"
            alpha_dir = extensions_dir / "alpha"
            beta_dir.mkdir(parents=True, exist_ok=False)
            alpha_dir.mkdir(parents=True, exist_ok=False)
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta",
                "name": "Beta",
                "version": "1.0.0",
                "dependencies": ["alpha"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha",
                "name": "Alpha",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")
            ExtensionInstallation.objects.create(
                extension_id="alpha",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            ExtensionInstallation.objects.create(
                extension_id="beta",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            Setting.objects.update_or_create(
                key="extensions_enabled_order",
                defaults={"value": json.dumps(["beta", "alpha", "missing"], ensure_ascii=False)},
            )

            manager = ExtensionRegistry(extensions_path=extensions_dir)
            before = manager.inspect_enabled_extension_order(force=True)
            self.assertTrue(before["drift"])
            self.assertEqual(before["persisted"], ["beta", "alpha", "missing"])
            self.assertEqual(before["resolved"], ["alpha", "beta"])
            self.assertEqual(before["stale"], ["missing"])

            result = manager.sync_enabled_extension_order()

            self.assertTrue(result["changed"])
            self.assertEqual(result["after"]["persisted"], ["alpha", "beta"])
            self.assertFalse(result["after"]["drift"])
            persisted = Setting.objects.get(key="extensions_enabled_order")
            self.assertEqual(json.loads(persisted.value), ["alpha", "beta"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
                "from apps.core.extensions import AdminSurfaceExtender, ApiResourceExtender, EventListenersExtender\n"
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
                "        ApiResourceExtender.from_resource(\n"
                "            ExtensionResourceDefinition(resource='alpha', module_id='alpha-tools', resolver=_serialize),\n"
                "        ),\n"
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

    def test_extension_application_catalogs_disabled_extensions_without_running_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id, permission in (
                ("alpha-tools", "alpha.manage"),
                ("beta-tools", "beta.manage"),
            ):
                manifest_dir = extensions_dir / extension_id
                backend_dir = manifest_dir / "backend"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id.title(),
                    "version": "1.0.0",
                    "backend_entry": f"extensions.{extension_id.replace('-', '_')}.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text(
                    "from apps.core.extensions import AdminSurfaceExtender\n"
                    "from apps.core.forum_registry_types import PermissionDefinition\n"
                    "\n"
                    "def extend():\n"
                    "    return [AdminSurfaceExtender(permissions=(\n"
                    f"        PermissionDefinition(code='{permission}', label='{permission}', section='admin', section_label='后台', module_id='{extension_id}'),\n"
                    "    ))]\n",
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
            ExtensionInstallation.objects.create(
                extension_id="beta-tools",
                version="1.0.0",
                source="filesystem",
                enabled=False,
                installed=True,
                booted=False,
            )

            application = build_extension_application(
                manager=ExtensionRegistry(extensions_path=extensions_dir),
                forum_registry=ForumRegistry(),
                resource_registry=ResourceRegistry(),
                event_bus=DomainEventBus(),
                force=True,
            )
            modules = {module.module_id: module for module in application.forum.get_modules()}

            self.assertTrue(modules["alpha-tools"].enabled)
            self.assertFalse(modules["beta-tools"].enabled)
            self.assertTrue(any(item.code == "alpha.manage" for item in application.forum.get_all_permissions()))
            self.assertFalse(any(item.code == "beta.manage" for item in application.forum.get_all_permissions()))
            self.assertIsNotNone(application.get_runtime_view("alpha-tools"))
            self.assertIsNone(application.get_runtime_view("beta-tools"))
        finally:
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
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.0.0")["compatible"])
            self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.2.3")["compatible"])
            self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="2.0.0")["compatible"])
            self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="0.9.9")["compatible"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_frontend_admin_entry_reports_available_exports(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_frontend_admin_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("resolveDetailPage", payload["available_exports"])
            self.assertIn("resolveSettingsPage", payload["available_exports"])
            self.assertIn("resolveOperationsPage", payload["available_exports"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_backend_entry_reports_available_hooks(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_backend_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("install", payload["available_hooks"])
            self.assertIn("run_migrations", payload["available_hooks"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_frontend_forum_entry_reports_available_exports(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_frontend_forum_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("available_exports", payload)
            self.assertTrue(payload["resolved_path"].endswith("extensions/alpha-tools/frontend/forum/index.js"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
    def test_authorization_decision_priority_matches_gate_semantics(self):
        from apps.core.authorization import (
            allow,
            assert_can,
            AuthorizationPolicy,
            can,
            deny,
            force_allow,
            force_deny,
            resolve_authorization_decision,
        )

        self.assertFalse(resolve_authorization_decision([allow(), force_deny(), force_allow()], default=True))
        self.assertTrue(resolve_authorization_decision([deny(), force_allow()], default=False))
        self.assertFalse(resolve_authorization_decision([allow(), deny()], default=True))
        self.assertTrue(resolve_authorization_decision([allow()], default=False))
        self.assertIsNone(resolve_authorization_decision([None], default=None))
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=True) as evaluate:
            self.assertTrue(can("actor", "discussion.edit", "discussion"))
            assert_can("actor", "discussion.edit", "discussion")
        evaluate.assert_called_with("discussion.edit", user="actor", model="discussion", default=None)
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=False):
            with self.assertRaises(PermissionError):
                assert_can("actor", "discussion.edit", "discussion")
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=None):
            with patch("apps.core.forum_permissions.has_forum_permission", return_value=True) as has_permission:
                self.assertTrue(can("actor", "discussion.edit", "discussion"))
        has_permission.assert_called_with("actor", "discussion.edit")
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=None):
            with patch("apps.core.forum_permissions.has_forum_permission", return_value=False):
                self.assertFalse(can("actor", "discussion.edit", "discussion"))

        class DiscussionPolicy(AuthorizationPolicy):
            def discussion_edit(self, user, model, **context):
                return self.forceDeny()

            def can(self, user, ability, model, **context):
                if ability == "discussion.view":
                    return True
                return None

        policy = DiscussionPolicy()
        self.assertFalse(resolve_authorization_decision([
            policy(user="actor", ability="discussion.edit", model="discussion"),
            force_allow(),
        ]))
        self.assertTrue(resolve_authorization_decision([
            policy(user="actor", ability="discussion.view", model="discussion"),
        ]))

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
            "def extend():\n"
            "    return [\n"
            "        PolicyExtender(mounts=(\n"
            "            ('forum.permission.searchUsers', grant_search_users),\n"
            "            ('discussion.delete', deny_delete_own_discussion),\n"
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

            self.assertFalse(has_forum_permission(user, "searchUsers"))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertTrue(has_forum_permission(user, "searchUsers"))
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
            discussion = Discussion.objects.create(
                title="Policy delete discussion",
                user=author,
                last_posted_user=author,
            )

            self.assertTrue(evaluate_runtime_extension_policy(
                "discussion.delete",
                default=True,
                user=author,
                discussion=discussion,
            ))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertFalse(evaluate_runtime_extension_policy(
                    "discussion.delete",
                    default=True,
                    user=author,
                    discussion=discussion,
                ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_policy_extender_accepts_policy_classes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = temp_dir / "extensions"
            manifest_dir = extensions_dir / "alpha-policy-class"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-policy-class",
                "name": "Alpha Policy",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_policy_class.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AuthorizationPolicy, PolicyExtender\n"
                "\n"
                "class AlphaModel:\n"
                "    pass\n"
                "\n"
                "class AlphaPolicy(AuthorizationPolicy):\n"
                "    instances = 0\n"
                "\n"
                "    def __init__(self):\n"
                "        type(self).instances += 1\n"
                "\n"
                "    def alpha_edit(self, user, model, **context):\n"
                "        return self.forceDeny()\n"
                "\n"
                "    def can(self, user, ability, model, **context):\n"
                "        if ability == 'alpha.view':\n"
                "            return self.allow()\n"
                "        return None\n"
                "\n"
                "class GlobalPolicy(AuthorizationPolicy):\n"
                "    def can(self, user, ability, model, **context):\n"
                "        if ability == 'alpha.global':\n"
                "            return self.forceAllow()\n"
                "        return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        (PolicyExtender()\n"
                "            .policy(AlphaModel, AlphaPolicy)\n"
                "            .global_policy(GlobalPolicy)),\n"
                "    ]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-policy-class",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            application = build_extension_application(manager=ExtensionRegistry(extensions_path=extensions_dir), force=True)
            runtime_view = application.get_runtime_view("alpha-policy-class")
            model_mount = next(item for item in runtime_view.policy_mounts if item.model is not None)
            model_class = model_mount.model

            from apps.core.extensions.policy_runtime_service import evaluate_model_policy
            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=application):
                self.assertFalse(evaluate_model_policy("alpha.edit", user="actor", model=model_class(), default=True))
                self.assertTrue(evaluate_model_policy("alpha.view", user="actor", model=model_class(), default=False))
                self.assertTrue(evaluate_model_policy("alpha.global", user="actor", model=None, default=False))
                self.assertFalse(evaluate_model_policy("alpha.missing", user="actor", model=model_class(), default=False))

            policy_instance = model_mount.handler._bias_policy_cache["value"]
            self.assertEqual(policy_instance.__class__.instances, 1)
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

    def test_validate_extension_manifests_rejects_optional_dependency_top_level_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.ext import beta_extenders\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "optional_dependency_top_level_import"
                and item.extension_id == "alpha-tools"
                and item.field.endswith("extensions/alpha-tools/backend/ext.py")
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_undeclared_cross_extension_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.ext import beta_extenders\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "undeclared_cross_extension_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_declared_dependency_internal_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.services import BetaService\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_cross_extension_internal_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_cross_extension_events_and_visibility_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.events import BetaHappened\n"
                "from extensions.beta_tools.backend.visibility import scope_beta\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            issues = [
                item for item in result.issues
                if item.code == "forbidden_cross_extension_internal_import"
                and item.extension_id == "alpha-tools"
            ]
            self.assertFalse(result.ok)
            self.assertEqual(len(issues), 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_delayed_internal_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ConditionalExtender\n"
                "\n"
                "def beta_extenders():\n"
                "    from extensions.beta_tools.backend.models import BetaThing\n"
                "    return []\n"
                "\n"
                "def extend():\n"
                "    return [ConditionalExtender().when_extension_enabled('beta-tools', beta_extenders)]\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_cross_extension_internal_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_conditional_optional_dependency_delayed_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ConditionalExtender\n"
                "\n"
                "def beta_extenders():\n"
                "    from extensions.beta_tools.backend.ext import beta_extenders\n"
                "    return []\n"
                "\n"
                "def extend():\n"
                "    return [ConditionalExtender().when_extension_enabled('beta-tools', beta_extenders)]\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertTrue(result.ok)
            self.assertFalse(any(item.code == "optional_dependency_top_level_import" for item in result.issues))
            self.assertFalse(any(item.code == "undeclared_cross_extension_import" for item in result.issues))
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

    def test_validate_extension_manifests_rejects_migration_namespace_field(self):
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
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_migration_namespace_manifest_field"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_backend_and_forbidden_migration_namespace(self):
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
            self.assertTrue(any(item.code == "forbidden_migration_namespace_manifest_field" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_django_app_config_namespace(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "apps.core.apps.CoreConfig",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_django_app_config_namespace" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_django_migration_module_field(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_migration_module": "extensions.posts.backend.wrong_migrations",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_django_migration_module_manifest_field" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_django_app_label_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_label": "alpha",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "django_app_label_without_app_config" for item in result.issues))

            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_app_label": "123-invalid",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_django_app_label" for item in result.issues))
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
                "from apps.core import signals\n"
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
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

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
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

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
                    "replacement": "not a package!",
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
            self.assertTrue(any(item.code == "invalid_distribution_replacement" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_security_support_email" for item in result.issues))
            self.assertTrue(any(item.code == "signature_url_without_key" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_checks_local_distribution_signature(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            manifest = {
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "distribution": {
                    "channel": "private",
                    "signing_key_id": "local-dev",
                    "signature_url": "signature.txt",
                },
                "security": {
                    "capabilities_notice": "测试签名文件校验。",
                },
            }
            (manifest_dir / "extension.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(any(item.code == "missing_distribution_signature_file" for item in result.issues))

            (manifest_dir / "signature.txt").write_text("signature", encoding="utf-8")
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(any(item.code == "missing_distribution_signature_file" for item in result.issues))
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
                beta_manifest_path = Path(temp_dir) / "extensions" / "beta_tools" / "extension.json"
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

    def test_create_extension_command_scaffolds_minimal_extension_entry(self):
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

                extension_dir = Path(temp_dir) / "extensions" / "alpha_tools"
                manifest = json.loads((extension_dir / "extension.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["id"], "alpha-tools")
                self.assertEqual(manifest["name"], "Alpha Tools")
                self.assertEqual(manifest["backend_entry"], "extensions.alpha_tools.backend.ext")
                self.assertEqual(
                    manifest["django_app_config"],
                    "extensions.alpha_tools.backend.apps.AlphaToolsExtensionConfig",
                )
                self.assertEqual(manifest["django_app_label"], "alpha_tools")
                self.assertNotIn("frontend_admin_entry", manifest)
                self.assertNotIn("frontend_forum_entry", manifest)
                self.assertNotIn("migration_namespace", manifest)
                self.assertEqual(manifest["compatibility"]["bias_version"], "^1.0.0")
                self.assertEqual(manifest["compatibility"]["api_stability"], "experimental")
                self.assertEqual(manifest["distribution"]["channel"], "private")
                self.assertEqual(manifest["security"]["support_email"], "security@example.com")
                self.assertTrue((extension_dir / "frontend" / "admin" / "index.js").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "DetailPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "SettingsPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "PermissionsPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "OperationsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "forum" / "index.js").exists())
                self.assertTrue((extension_dir / "backend" / "ext.py").exists())
                self.assertTrue((extension_dir / "backend" / "apps.py").exists())
                self.assertTrue((extension_dir / "backend" / "django_migrations" / "__init__.py").exists())
                self.assertFalse((extension_dir / "backend" / "migrations").exists())
                self.assertTrue((extension_dir / "README.md").exists())
                self.assertTrue((extension_dir / "docs" / "README.md").exists())
                self.assertTrue((extension_dir / "locale" / "zh-CN.json").exists())
                backend_source = (extension_dir / "backend" / "ext.py").read_text(encoding="utf-8")
                self.assertIn("def extend():", backend_source)
                self.assertIn("FrontendExtender()", backend_source)
                self.assertIn("extensions/alpha_tools/frontend/admin/index.js", backend_source)
                apps_source = (extension_dir / "backend" / "apps.py").read_text(encoding="utf-8")
                self.assertIn("class AlphaToolsExtensionConfig(AppConfig):", apps_source)
                self.assertIn('label = "alpha_tools"', apps_source)
                self.assertNotIn("LifecycleExtender", backend_source)
                self.assertNotIn("def install(context):", backend_source)
                self.assertNotIn("def run_migrations(context):", backend_source)
                self.assertNotIn("def rollback_migrations(context):", backend_source)
                self.assertNotIn("def uninstall(context):", backend_source)
                self.assertNotIn("SettingsExtender", backend_source)
                self.assertNotIn("ApiResourceExtender", backend_source)
                self.assertNotIn("RuntimeActionsExtender", backend_source)
                self.assertNotIn("AdminNavigationExtender", backend_source)
                admin_source = (extension_dir / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                forum_source = (extension_dir / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("from '@bias/admin'", admin_source)
                self.assertIn("export const extend", admin_source)
                self.assertIn("extendAdmin(admin => admin", admin_source)
                self.assertIn("export function resolveDetailPage()", admin_source)
                self.assertIn("return null", admin_source)
                self.assertNotIn(".page({", admin_source)
                self.assertIn("from '@bias/forum'", forum_source)
                self.assertIn("extendForum(forum => forum", forum_source)
                self.assertNotIn(".navItem({", forum_source)
                readme_source = (extension_dir / "README.md").read_text(encoding="utf-8")
                self.assertIn("backend/ext.py", readme_source)
                self.assertIn("validate_extensions --strict", readme_source)
                self.assertIn("build_extension_frontend --rebuild", readme_source)
                self.assertIn("ApiResourceExtender(...)", readme_source)
                self.assertIn("backend/apps.py", readme_source)
                self.assertIn("backend/django_migrations", readme_source)
                self.assertNotIn("migration_namespace", readme_source)
                docs_readme_source = (extension_dir / "docs" / "README.md").read_text(encoding="utf-8")
                self.assertEqual(docs_readme_source, readme_source)

                from apps.core.extension_django_apps import (
                    discover_extension_django_apps,
                    discover_extension_django_migration_modules,
                )

                self.assertEqual(
                    discover_extension_django_apps(Path(temp_dir)),
                    ["extensions.alpha_tools.backend.apps.AlphaToolsExtensionConfig"],
                )
                self.assertEqual(
                    discover_extension_django_migration_modules(Path(temp_dir)),
                    {"alpha_tools": "extensions.alpha_tools.backend.django_migrations"},
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_frontend_entries_use_public_sdks(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")

                entry_source = (Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export function resolveDetailPage()", entry_source)
                self.assertIn("return null", entry_source)
                self.assertNotIn("import DetailPage", entry_source)
                self.assertNotIn("export function resolvePermissionsPage()", entry_source)
                self.assertIn("extendAdmin(admin => admin", entry_source)
                forum_entry_source = (Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export const extend", forum_entry_source)
                self.assertIn("extendForum(forum => forum", forum_entry_source)
                self.assertNotIn(".navItem({", forum_entry_source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_rejects_existing_directory_without_force(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extension_dir = Path(temp_dir) / "extensions" / "alpha_tools"
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
                backend_path = Path(temp_dir) / "extensions" / "alpha_tools" / "backend" / "ext.py"
                backend_path.write_text(
                    backend_path.read_text(encoding="utf-8")
                    + "\nfrom apps.core.extensions.extenders import ResourceExtender\n",
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

    def test_validate_extensions_command_reports_optional_dependency_top_level_import_before_backend_load(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.models import BetaThing\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            output = StringIO()
            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(extensions_dir),
                    stdout=output,
                )

            self.assertIn("forbidden_cross_extension_internal_import", output.getvalue())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_external_project_name_residue_in_extension_source(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                backend_path = Path(temp_dir) / "extensions" / "alpha_tools" / "backend" / "ext.py"
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

    def test_validate_extensions_command_allows_direct_admin_frontend_extender(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command("create_extension", "alpha-tools")
                admin_path = Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "admin" / "index.js"
                admin_path.write_text(
                    "export const extend = [\n"
                    "  new AdminExtender().page({ path: '/admin/direct' }),\n"
                    "]\n"
                    "export function resolveDetailPage() { return null }\n",
                    encoding="utf-8",
                )

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

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
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
        self.assertIn("package_lock", payload["runtime"])
        self.assertIn("summary", payload["runtime"]["package_lock"])
        self.assertIn("packages", payload["runtime"]["package_lock"])
        self.assertIn("diagnostics", payload["extensions"][0])
        self.assertTrue(any(item["id"] == "core" for item in payload["extensions"]))
        self.assertTrue(any(item["id"] == "tags" for item in payload["extensions"]))
        alpha_extension = next((item for item in payload["extensions"] if item["id"] == "alpha-tools"), None)
        if alpha_extension is not None:
            self.assertFalse(alpha_extension["product_visible"])

    def test_inspect_extensions_command_can_focus_single_extension_with_permissions(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "tags",
            "--include-permissions",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["summary"]["extension_count"], 1)
        self.assertEqual(payload["meta"]["extension_id"], "tags")
        self.assertEqual(payload["extensions"][0]["id"], "tags")
        self.assertIn("permission_sections", payload["extensions"][0])
        self.assertIn("package_lock", payload)
        self.assertIn("summary", payload["package_lock"])
        self.assertIn("packages", payload["package_lock"])
        self.assertIn("dependency_resolution", payload["package_lock"])
        self.assertIn("boot_order", payload["package_lock"]["dependency_resolution"])
        self.assertIn("graph", payload["package_lock"]["dependency_resolution"])

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
        self.assertIn("owned_model_count", audit)
        self.assertIn("items", audit)
        self.assertIn("target_app_label", audit)
        self.assertIn("model_package_migration_required_count", extension["capability_summary"])

    def test_inspect_extensions_command_can_filter_attention_only(self):
        ExtensionInstallation.objects.create(
            extension_id="notifications",
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
        self.assertTrue(any(item["id"] == "notifications" for item in payload["extensions"]))
        self.assertTrue(all("django_app_label" in item for item in payload["extensions"]))

    def test_inspect_extensions_command_can_filter_blocking_only(self):
        ExtensionInstallation.objects.create(
            extension_id="notifications",
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

    def test_classify_extension_diagnostics_ignores_absent_migration_plan(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "migration_state": "pending",
            "migration_plan": {
                "declared_files": [],
                "applied_files": [],
                "pending_files": [],
            },
            "delivery_checks": [],
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertFalse(diagnostics["warning"])
        self.assertNotIn("迁移状态待完善", diagnostics["warning_reasons"])

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

    def test_classify_extension_diagnostics_marks_frontend_asset_state_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "frontend_asset_state": {
                "has_frontend": True,
                "manifest_exists": True,
                "compiled": True,
                "requires_rebuild": True,
            },
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("扩展前端资源待重建", diagnostics["warning_reasons"])

        missing = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "frontend_asset_state": {
                "has_frontend": True,
                "manifest_exists": False,
                "compiled": False,
                "requires_rebuild": False,
            },
        })

        self.assertIn("扩展前端资源尚未生成", missing["warning_reasons"])

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

    def test_uninstall_clears_django_migration_summary(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                migrations_dir = backend_dir / "django_migrations"
                migrations_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                    "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                    "django_app_label": "alpha_tools",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")
                (backend_dir / "apps.py").write_text(
                    "from django.apps import AppConfig\n"
                    "\n"
                    "\n"
                    "class AlphaToolsConfig(AppConfig):\n"
                    "    default_auto_field = 'django.db.models.BigAutoField'\n"
                    "    name = 'extensions.alpha_tools.backend'\n"
                    "    label = 'alpha_tools'\n",
                    encoding="utf-8",
                )
                (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
                (migrations_dir / "0001_bootstrap.py").write_text(
                    "from django.db import migrations\n"
                    "\n"
                    "\n"
                    "class Migration(migrations.Migration):\n"
                    "    initial = True\n"
                    "    dependencies = []\n"
                    "    operations = []\n",
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
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_registry_exposes_filesystem_extensions_only(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extensions = registry.get_extensions()

        extension_ids = {item.id for item in extensions}
        self.assertNotIn("core", extension_ids)
        self.assertNotIn("alpha-tools", extension_ids)
        self.assertIn("posts", extension_ids)
        self.assertIn("discussions", extension_ids)
        self.assertIn("users", extension_ids)
        self.assertIn("emoji", extension_ids)
        self.assertTrue(all(item.source == "filesystem" for item in extensions))

        emoji_extension = next(item for item in extensions if item.id == "emoji")
        self.assertEqual(emoji_extension.source, "filesystem")
        self.assertTrue(emoji_extension.runtime.installed)
        self.assertTrue(emoji_extension.runtime.enabled)
        self.assertEqual(emoji_extension.runtime.status_key, "active")

    def test_runtime_probe_prefers_contract_frontend_entries(self):
        manifest = ExtensionManifest(
            id="contract-first",
            name="Contract First",
            version="1.0.0",
            frontend_admin_entry="",
            frontend_forum_entry="",
            path=str(Path.cwd() / "extensions" / "alpha-tools"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/contract-first/frontend/admin/index.js",
                frontend_forum_entry="extensions/contract-first/frontend/forum/index.js",
                path=str(Path.cwd() / "extensions" / "tags"),
            ),
            source="filesystem",
        )

        payload = inspect_extension_runtime(extension)

        checks = {item.key: item for item in payload["delivery_checks"]}
        self.assertEqual(checks["frontend-admin-entry"].status, "ready")
        self.assertEqual(checks["frontend-forum-entry"].status, "ready")

    def test_registry_applies_persisted_installation_state(self):
        ExtensionInstallation.objects.create(
            extension_id="emoji",
            version="0.1.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

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
        self.assertFalse(any(item["id"] == "alpha-tools" for item in entries))

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
        self.assertTrue(any(item["id"] == "uploads" for item in entries))

        with patch("apps.core.extension_service.reset_extension_runtime_state") as reset_runtime_mock:
            ExtensionService.set_extension_enabled("uploads", False)

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

    @patch("apps.core.extensions.runtime_probe.resolve_bias_version_compatibility")
    def test_registry_marks_extension_unhealthy_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

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

@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class AdminExtensionsApiTests(TestCase):
    def setUp(self):
        self.extension_base_dir = make_extension_test_base_dir()
        self.settings_override = override_settings(BASE_DIR=self.extension_base_dir)
        self.settings_override.enable()
        reset_extension_runtime_state()
        self.addCleanup(self._cleanup_extension_base_dir)
        self.admin = User.objects.create_superuser(
            username="admin-extensions",
            email="admin-extensions@example.com",
            password="password123",
        )

    def _cleanup_extension_base_dir(self):
        reset_extension_runtime_state()
        self.settings_override.disable()
        reset_extension_runtime_state()
        shutil.rmtree(self.extension_base_dir, ignore_errors=True)

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
        self.assertIn("posts", extension_ids)
        self.assertIn("discussions", extension_ids)
        self.assertIn("users", extension_ids)
        self.assertIn("realtime", extension_ids)
        self.assertIn("tags", extension_ids)
        self.assertIn("alpha-tools", extension_ids)

        users_extension = next(item for item in payload["extensions"] if item["id"] == "users")
        self.assertEqual(users_extension["source"], "filesystem")
        self.assertTrue(users_extension["product_visible"])
        self.assertTrue(users_extension["protected"])
        self.assertIn("认证基础域", users_extension["protected_reason"])
        self.assertFalse(any(action["action"] == "disable" for action in users_extension["runtime_actions"]))
        self.assertIn("/admin/extensions/users/permissions", users_extension["permissions_pages"])

        discussions_extension = next(item for item in payload["extensions"] if item["id"] == "discussions")
        self.assertEqual(discussions_extension["source"], "filesystem")
        self.assertTrue(discussions_extension["product_visible"])
        self.assertEqual(
            discussions_extension["frontend_admin_entry"],
            "extensions/discussions/frontend/admin/index.js",
        )
        self.assertIn("/admin/extensions/discussions/permissions", discussions_extension["permissions_pages"])

        posts_extension = next(item for item in payload["extensions"] if item["id"] == "posts")
        self.assertEqual(posts_extension["source"], "filesystem")
        self.assertTrue(posts_extension["product_visible"])
        self.assertTrue(posts_extension["protected"])
        self.assertFalse(any(action["action"] == "disable" for action in posts_extension["runtime_actions"]))
        self.assertIn("post-types", posts_extension["provides"])

        realtime_extension = next(item for item in payload["extensions"] if item["id"] == "realtime")
        self.assertEqual(realtime_extension["source"], "filesystem")
        self.assertTrue(realtime_extension["product_visible"])
        self.assertIn("core", realtime_extension["dependencies"])

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertEqual(sample_extension["source"], "filesystem")
        self.assertFalse(sample_extension["product_visible"])
        self.assertEqual(sample_extension["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertIn("/admin/extensions/alpha-tools/settings", sample_extension["settings_pages"])
        self.assertIn("/admin/extensions/alpha-tools/permissions", sample_extension["permissions_pages"])
        self.assertEqual(sample_extension["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(sample_extension["compatibility"]["api_stability"], "experimental")
        self.assertEqual(sample_extension["distribution"]["channel"], "private")
        self.assertTrue(sample_extension["distribution"]["abandoned"])
        self.assertEqual(sample_extension["distribution"]["replacement"], "beta-tools")
        self.assertEqual(sample_extension["action_links"]["settings_page"], "/admin/extensions/alpha-tools/settings")
        self.assertEqual(sample_extension["action_links"]["permissions_page"], "/admin/extensions/alpha-tools/permissions")
        self.assertTrue(any(item["key"] == "welcome_message" for item in sample_extension["settings_schema"]))
        self.assertEqual(sample_extension["admin_actions"][0]["key"], "details")
        self.assertTrue(any(action["key"] == "documentation" for action in sample_extension["admin_actions"]))
        self.assertTrue(any(action["action"] == "hook:run_rebuild_cache" for action in sample_extension["runtime_actions"]))

    def test_extensions_sync_api_prunes_missing_installations_and_returns_package_lock(self):
        ExtensionInstallation.objects.create(
            extension_id="missing-package",
            version="1.0.0",
            source="python-package",
            enabled=True,
            installed=True,
            booted=True,
        )

        response = self.client.post(
            "/api/admin/extensions/sync",
            data=json.dumps({"prune_missing": True}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        installation = ExtensionInstallation.objects.get(extension_id="missing-package")
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)
        self.assertTrue(installation.meta["sync"]["missing"])
        payload = response.json()
        package_lock = payload["runtime"]["package_lock"]
        self.assertGreaterEqual(package_lock["summary"]["missing_count"], 1)
        self.assertIn("missing-package", package_lock["missing"])
        missing_record = next(item for item in package_lock["packages"] if item["id"] == "missing-package")
        self.assertTrue(missing_record["missing"])

    def test_extensions_sync_order_api_repairs_enabled_order_drift(self):
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "1.0.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        Setting.objects.update_or_create(
            key="extensions_enabled_order",
            defaults={"value": json.dumps(["alpha-tools", "missing-package"], ensure_ascii=False)},
        )

        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        before_order = response.json()["runtime"]["package_lock"]["enabled_order"]
        self.assertTrue(before_order["drift"])
        self.assertIn("missing-package", before_order["stale"])

        response = self.client.post(
            "/api/admin/extensions/sync-order",
            data=json.dumps({}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        after_order = response.json()["runtime"]["package_lock"]["enabled_order"]
        self.assertFalse(after_order["drift"])
        self.assertEqual(after_order["stale"], [])
        self.assertEqual(after_order["persisted"], after_order["resolved"])

    def test_extensions_rebuild_frontend_api_runs_build_and_returns_payload(self):
        from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY, mark_extension_runtime_requires_rebuild

        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "1.0.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")

        class CompileResult:
            def to_dict(self):
                return {
                    "status": "ok",
                    "status_label": "已编译",
                    "message": "rebuilt",
                    "extension_count": 1,
                    "returncode": 0,
                    "output_manifest": {
                        "extensions": {
                            "alpha-tools": {
                                "outputs": {"admin": {"entry": "assets/alpha.js"}},
                            },
                        },
                    },
                }

        with patch(
            "apps.core.extension_service.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            response = self.client.post(
                "/api/admin/extensions/rebuild-frontend",
                data=json.dumps({"run_build": True, "include_disabled": False}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        recompile.assert_called_once()
        self.assertTrue(recompile.call_args.kwargs["run_build"])
        self.assertTrue(recompile.call_args.kwargs["clear_marker"])
        self.assertFalse(recompile.call_args.kwargs["publish_dist"])
        payload = response.json()
        self.assertEqual(payload["frontend_rebuild"]["status"], "ok")
        self.assertIn("extensions", payload)
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())

    def test_extensions_rebuild_frontend_api_can_generate_manifest_only(self):
        from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY

        class CompileResult:
            def to_dict(self):
                return {
                    "status": "ok",
                    "status_label": "已生成",
                    "message": "manifest built",
                    "extension_count": 1,
                    "returncode": None,
                }

        with patch(
            "apps.core.extension_service.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            response = self.client.post(
                "/api/admin/extensions/rebuild-frontend",
                data=json.dumps({"run_build": False}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(recompile.call_args.kwargs["run_build"])
        self.assertFalse(recompile.call_args.kwargs["clear_marker"])
        self.assertIn("extension_frontend_manifest_built", Setting.objects.get(key=RUNTIME_REBUILD_MARKER_KEY).value)

    def test_extension_detail_api_returns_extension_actions(self):
        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["id"], "alpha-tools")
        self.assertEqual(payload["action_links"]["detail_page"], "/admin/extensions/alpha-tools")
        self.assertEqual(payload["action_links"]["settings_page"], "/admin/extensions/alpha-tools/settings")
        self.assertEqual(payload["action_links"]["permissions_page"], "/admin/extensions/alpha-tools/permissions")
        self.assertEqual(payload["action_links"]["operations_page"], "/admin/extensions/alpha-tools/operations")
        self.assertEqual(payload["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertEqual(payload["admin_actions"][0]["key"], "details")
        self.assertEqual(payload["runtime_status"]["key"], "pending_install")
        self.assertEqual(payload["runtime_actions"][0]["action"], "install")
        self.assertEqual(payload["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(payload["compatibility"]["api_stability_label"], "实验性")
        self.assertEqual(payload["distribution"]["channel_label"], "私有分发")
        self.assertTrue(payload["distribution"]["abandoned"])
        self.assertEqual(payload["distribution"]["replacement"], "beta-tools")
        self.assertEqual(payload["security"]["support_email"], "security@bias.local")
        self.assertEqual(payload["homepage"], "https://bias.local/extensions/alpha-tools")
        self.assertEqual(payload["authors"], ["Alpha Maintainer", "Security Contact"])
        self.assertEqual(payload["links"]["authors"][0], {
            "name": "Alpha Maintainer",
            "link": "https://bias.local/authors/alpha",
        })
        self.assertEqual(payload["links"]["authors"][1], {
            "name": "Security Contact",
            "link": "mailto:security-author@bias.local",
        })
        self.assertEqual(payload["links"]["documentation"], "https://bias.local/docs/alpha-tools")
        self.assertEqual(payload["links"]["website"], "https://bias.local/extensions/alpha-tools")
        self.assertEqual(payload["links"]["support"], "mailto:security@bias.local")
        self.assertEqual(payload["links"]["source"], "https://bias.local/source/alpha-tools")
        self.assertEqual(payload["links"]["discuss"], "https://bias.local/discuss/alpha-tools")
        self.assertTrue(payload["readme"]["available"])
        self.assertIn("<h1", payload["readme"]["html"])
        self.assertIn("Alpha Tools README", payload["readme"]["html"])
        self.assertEqual(payload["operations_profile"]["kicker"], "Alpha Runtime")
        self.assertIn("settings", payload["operations_profile"]["recommended_action_keys"])
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["settings_schema"]))
        self.assertEqual(payload["settings_values"]["welcome_message"], "欢迎使用 Alpha Tools")
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
        self.assertEqual(payload["debug_info"]["manifest_path"], str(Path(settings.BASE_DIR) / "extensions" / "alpha-tools"))
        self.assertEqual(payload["debug_info"]["frontend_admin_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_admin_entry"]["exists"])
        self.assertIn("resolveDetailPage", payload["debug_info"]["frontend_admin_entry"]["available_exports"])
        self.assertEqual(payload["debug_info"]["frontend_forum_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_forum_entry"]["exists"])
        self.assertIn("0001_bootstrap.py", payload["migration_plan"]["pending_files"])
        self.assertTrue(any(
            item["key"] == "settings"
            and item["matches_expected"]
            and item["declared"] == "/admin/extensions/alpha-tools/settings"
            for item in payload["debug_info"]["route_bindings"]
        ))
        self.assertTrue(any(
            item["key"] == "frontend_forum_entry"
            and item["matches_expected"]
            and item["declared"] == "extensions/alpha-tools/frontend/forum/index.js"
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

    def test_extension_detail_api_surfaces_runtime_system_hooks(self):
        ext_path = self.extension_base_dir / "extensions" / "alpha-tools" / "backend" / "ext.py"
        ext_path.write_text(
            "from __future__ import annotations\n"
            "\n"
            "from apps.core.extensions import ConsoleExtender, CsrfExtender, ThrottleApiExtender\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        ConsoleExtender().command('alpha:refresh', lambda payload, context: {'ok': True}, description='Alpha refresh', order=20),\n"
            "        CsrfExtender().exempt_route('alpha-webhook', description='Alpha webhook', order=30),\n"
            "        ThrottleApiExtender().set('alpha', lambda request: False, description='Alpha throttler', order=40),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "0.1.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        sys.modules.pop("extensions.alpha_tools.backend.ext", None)
        reset_extension_runtime_state()

        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        hooks = response.json()["extension"]["debug_info"]["system_hooks"]
        hook_keys = {
            (item["service"], item["key"], item["order"], item["description"])
            for item in hooks
        }
        self.assertIn(("console", "command", 20, "Alpha refresh"), hook_keys)
        self.assertIn(("csrf", "exempt_route", 30, "Alpha webhook"), hook_keys)
        self.assertIn(("throttle.api", "throttler", 40, "Alpha throttler"), hook_keys)

    def test_extension_detail_api_surfaces_settings_frontend_and_theme_runtime(self):
        ext_path = self.extension_base_dir / "extensions" / "alpha-tools" / "backend" / "ext.py"
        ext_path.write_text(
            "from __future__ import annotations\n"
            "\n"
            "from apps.core.extensions import FrontendExtender, SettingsExtender, ThemeExtender\n"
            "from apps.core.extensions.backend import _build_setting_field_definition\n"
            "\n"
            "def is_default(value):\n"
            "    return value == 'primary'\n"
            "\n"
            "def expose_upper(value):\n"
            "    return str(value or '').upper()\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        SettingsExtender(fields=(\n"
            "            _build_setting_field_definition({'key': 'card_tone', 'label': '卡片风格', 'type': 'text', 'default': 'primary'}),\n"
            "        ))\n"
            "            .default('card_tone', 'primary')\n"
            "            .reset_when('card_tone', is_default)\n"
            "            .reset_frontend_cache_for('card_tone')\n"
            "            .theme_variable('bias-alpha-card-tone', 'card_tone', expose_upper)\n"
            "            .serialize_to_forum('alphaCardTone', 'card_tone', expose_upper),\n"
            "        FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/index.js')\n"
            "            .preload({'href': '/assets/alpha.css', 'as': 'style'})\n"
            "            .extra_document_attributes({'data-alpha': '1'})\n"
            "            .content('alpha.content', priority=90)\n"
            "            .title('AlphaTitle'),\n"
            "        ThemeExtender()\n"
            "            .variables({'bias-alpha-accent': '#335577'})\n"
            "            .document_classes(['alpha-theme'])\n"
            "            .head_tag('meta', {'name': 'alpha-theme', 'content': 'enabled'}),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "0.1.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        Setting.objects.update_or_create(
            key="extensions.alpha-tools.card_tone",
            defaults={"value": json.dumps("warm", ensure_ascii=False)},
        )
        sys.modules.pop("extensions.alpha_tools.backend.ext", None)
        reset_extension_runtime_state()

        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        debug_info = response.json()["extension"]["debug_info"]
        settings_runtime = debug_info["settings_runtime"]
        self.assertEqual(settings_runtime["defaults"], [{
            "key": "card_tone",
            "value": "primary",
            "module_id": "alpha-tools",
        }])
        self.assertEqual(settings_runtime["reset_rules"][0]["key"], "card_tone")
        self.assertEqual(settings_runtime["reset_rules"][0]["callback"], "is_default")
        self.assertEqual(settings_runtime["frontend_cache_keys"], ["card_tone"])
        self.assertEqual(settings_runtime["theme_variables"][0]["name"], "bias-alpha-card-tone")
        self.assertEqual(settings_runtime["theme_variables"][0]["callback"], "expose_upper")
        self.assertEqual(settings_runtime["forum_serializations"][0]["attribute"], "alphaCardTone")
        self.assertEqual(settings_runtime["forum_serializations"][0]["callback"], "expose_upper")

        frontend_document = debug_info["frontend_document"]
        self.assertEqual(frontend_document["preloads"], [{"href": "/assets/alpha.css", "as": "style"}])
        self.assertIn({"data-alpha": "1"}, frontend_document["document_attributes"])
        self.assertIn({"class": ["alpha-theme"]}, frontend_document["document_attributes"])
        self.assertEqual(frontend_document["title_driver"], "AlphaTitle")
        self.assertEqual(frontend_document["content_callbacks"], [{"callback": "alpha.content", "priority": 90}])
        self.assertIn({"bias-alpha-card-tone": "WARM"}, frontend_document["theme_variables"])
        self.assertIn({"bias-alpha-accent": "#335577"}, frontend_document["theme_variables"])
        self.assertEqual(frontend_document["head_tags"][0]["attributes"]["name"], "alpha-theme")

        theme_runtime = debug_info["theme_runtime"]
        self.assertTrue(any(item["key"] == "variables" for item in theme_runtime["handlers"]))
        self.assertEqual(theme_runtime["variables"], [{"bias-alpha-accent": "#335577"}])
        self.assertEqual(theme_runtime["document_attributes"], [{"class": ["alpha-theme"]}])
        self.assertEqual(theme_runtime["head_tags"][0]["attributes"]["name"], "alpha-theme")

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
            path=str(Path.cwd() / "extensions" / "alpha-tools"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/alpha-tools/frontend/admin/index.js",
                frontend_forum_entry="extensions/alpha-tools/frontend/forum/index.js",
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
                path=str(Path.cwd() / "extensions" / "alpha-tools"),
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
        self.assertEqual(payload["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertEqual(payload["frontend_forum_entry"], "extensions/alpha-tools/frontend/forum/index.js")
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

    def test_extension_settings_api_can_read_and_save_declared_schema(self):
        response = self.client.get(
            "/api/admin/extensions/alpha-tools/settings",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["extension_id"], "alpha-tools")
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["schema"]))
        self.assertEqual(payload["settings"]["card_tone"], "primary")

        save_response = self.client.post(
            "/api/admin/extensions/alpha-tools/settings",
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
            json.loads(Setting.objects.get(key="extensions.alpha-tools.welcome_message").value),
            "新的欢迎语",
        )

    def test_extension_settings_api_rejects_unknown_key(self):
        response = self.client.post(
            "/api/admin/extensions/alpha-tools/settings",
            data=json.dumps({"unknown_key": "x"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_settings_unknown_key")

    def test_extensions_api_can_install_disable_enable_and_uninstall_extension(self):
        install_response = self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )

        self.assertEqual(install_response.status_code, 200, install_response.content)
        installed_payload = install_response.json()
        installed_extension = next(item for item in installed_payload["extensions"] if item["id"] == "alpha-tools")
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
            "/api/admin/extensions/alpha-tools/disable",
            **self.auth_header(),
        )

        self.assertEqual(disable_response.status_code, 200, disable_response.content)
        disabled_payload = disable_response.json()
        disabled_extension = next(item for item in disabled_payload["extensions"] if item["id"] == "alpha-tools")
        self.assertFalse(disabled_extension["enabled"])
        self.assertEqual(disabled_extension["runtime_status"]["key"], "disabled")
        self.assertTrue(any(item["action"] == "uninstall" for item in disabled_extension["runtime_actions"]))
        self.assertTrue(any(item["hook"] == "run_disable" for item in disabled_extension["backend_hooks"]))

        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)
        self.assertIn("run_install", installation.meta["backend_hooks"])
        self.assertIn("run_disable", installation.meta["backend_hooks"])

        enable_response = self.client.post(
            "/api/admin/extensions/alpha-tools/enable",
            **self.auth_header(),
        )

        self.assertEqual(enable_response.status_code, 200, enable_response.content)
        enabled_payload = enable_response.json()
        enabled_extension = next(item for item in enabled_payload["extensions"] if item["id"] == "alpha-tools")
        self.assertTrue(enabled_extension["enabled"])
        self.assertTrue(any(item["hook"] == "run_enable" for item in enabled_extension["backend_hooks"]))

        runtime_hook_response = self.client.post(
            "/api/admin/extensions/alpha-tools/runtime-hooks/run_rebuild_cache",
            **self.auth_header(),
        )
        self.assertEqual(runtime_hook_response.status_code, 200, runtime_hook_response.content)
        runtime_hook_payload = runtime_hook_response.json()
        runtime_hook_extension = next(item for item in runtime_hook_payload["extensions"] if item["id"] == "alpha-tools")
        self.assertTrue(any(item["hook"] == "run_rebuild_cache" for item in runtime_hook_extension["backend_hooks"]))

        migrations_response = self.client.post(
            "/api/admin/extensions/alpha-tools/migrations",
            **self.auth_header(),
        )
        self.assertEqual(migrations_response.status_code, 200, migrations_response.content)
        migrations_payload = migrations_response.json()
        migrations_extension = next(item for item in migrations_payload["extensions"] if item["id"] == "alpha-tools")
        self.assertTrue(any(item["hook"] == "run_migrations" for item in migrations_extension["backend_hooks"]))
        self.assertEqual(migrations_extension["migration_label"], "最近已执行")
        self.assertEqual(migrations_extension["migration_execution"]["state"], "applied")

        installation.refresh_from_db()
        self.assertTrue(installation.enabled)
        self.assertTrue(installation.booted)
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disable_response = self.client.post(
            "/api/admin/extensions/alpha-tools/disable",
            **self.auth_header(),
        )
        self.assertEqual(disable_response.status_code, 200, disable_response.content)

        uninstall_response = self.client.post(
            "/api/admin/extensions/alpha-tools/uninstall",
            **self.auth_header(),
        )
        self.assertEqual(uninstall_response.status_code, 200, uninstall_response.content)
        uninstalled_payload = uninstall_response.json()
        uninstalled_extension = next(item for item in uninstalled_payload["extensions"] if item["id"] == "alpha-tools")
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
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )
        self.client.post(
            "/api/admin/extensions/alpha-tools/disable",
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
            "/api/admin/extensions/alpha-tools/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        sample_extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertTrue(sample_extension["enabled"])

    def test_extensions_api_blocks_enable_when_extension_not_installed(self):
        response = self.client.post(
            "/api/admin/extensions/alpha-tools/enable",
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
            "/api/admin/extensions/alpha-tools/install",
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

    def test_extensions_api_blocks_disable_for_protected_extension(self):
        response = self.client.post(
            "/api/admin/extensions/posts/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_protected_blocked")
        self.assertIn("protected_reason", payload["field_errors"])

    def test_extensions_api_uninstall_disables_enabled_extension_first(self):
        self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )

        response = self.client.post(
            "/api/admin/extensions/alpha-tools/uninstall",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertFalse(extension["installed"])
        self.assertFalse(extension["enabled"])
        hooks = {item["hook"]: item for item in extension["backend_hooks"]}
        self.assertEqual(hooks["run_disable"]["status"], "ok")
        self.assertEqual(hooks["run_uninstall"]["status"], "ok")


class ExtensionServiceTests(TestCase):
    def setUp(self):
        self.extension_base_dir = make_extension_test_base_dir()
        self.settings_override = override_settings(BASE_DIR=self.extension_base_dir)
        self.settings_override.enable()
        reset_extension_runtime_state()
        self.addCleanup(self._cleanup_extension_base_dir)

    def _cleanup_extension_base_dir(self):
        reset_extension_runtime_state()
        self.settings_override.disable()
        reset_extension_runtime_state()
        shutil.rmtree(self.extension_base_dir, ignore_errors=True)

    def test_install_and_uninstall_transition_filesystem_extension(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.installed)
        self.assertTrue(installed.runtime.enabled)
        self.assertEqual(installed.runtime.backend_hooks["run_install"]["status"], "ok")
        self.assertEqual(installed.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(installed.runtime.migration_state, "applied")
        self.assertEqual(installed.runtime.migration_label, "最近已执行")
        self.assertEqual(installed.runtime.migration_execution["state"], "applied")
        self.assertIn("0001_bootstrap.py", installed.runtime.migration_execution["details"]["migration_files"])
        self.assertIn("0001_bootstrap", installed.runtime.migration_execution["details"]["applied_steps"])
        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disabled = ExtensionService.set_extension_enabled("alpha-tools", False)
        self.assertFalse(disabled.runtime.enabled)
        self.assertEqual(disabled.runtime.backend_hooks["run_disable"]["status"], "ok")

        enabled = ExtensionService.set_extension_enabled("alpha-tools", True)
        self.assertTrue(enabled.runtime.enabled)
        self.assertEqual(enabled.runtime.backend_hooks["run_enable"]["status"], "ok")

        uninstalled = ExtensionService.uninstall_extension("alpha-tools")
        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "ok")
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")
        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertEqual(installation.meta["applied_migration_files"], [])

    def test_run_extension_backend_hook_skips_when_hook_missing(self):
        registry = ExtensionRegistry(extensions_path=Path(settings.BASE_DIR) / "extensions")
        definition = registry.get_extension("alpha-tools")

        result = run_extension_backend_hook(definition, "run_reconcile")

        self.assertEqual(result["status"], "skipped")
        self.assertIn("run_reconcile", result["message"])

    def test_runtime_hook_executes_declared_extension_operation(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.enabled)

        updated = ExtensionService.run_extension_runtime_hook("alpha-tools", "run_rebuild_cache")

        self.assertEqual(updated.runtime.backend_hooks["run_rebuild_cache"]["status"], "ok")

    def test_run_extension_migrations_executes_declared_migration_hook(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.installed)

        updated = ExtensionService.run_extension_migrations("alpha-tools")

        self.assertEqual(updated.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(updated.runtime.migration_state, "applied")
        self.assertEqual(updated.runtime.migration_label, "最近已执行")
        self.assertEqual(updated.runtime.migration_execution["status"], "ok")
        self.assertEqual(updated.runtime.migration_execution["details"]["migration_files"], [])
        self.assertIn("0001_bootstrap.py", updated.runtime.migration_execution["details"]["skipped_migration_files"])

    def test_run_extension_migrations_refreshes_auto_installed_extension(self):
        updated = ExtensionService.run_extension_migrations("users")

        self.assertEqual(updated.id, "users")
        self.assertEqual(updated.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(updated.runtime.migration_state, "applied")

    def test_runtime_reset_keeps_full_extension_catalog_on_reload(self):
        from apps.core.extensions.manager import get_extension_manager

        manager = get_extension_manager()
        manager.load(force=True)
        before_ids = {extension.id for extension in manager.get_extensions()}

        reset_extension_runtime_state()
        manager = get_extension_manager()
        manager.load(force=True)
        after_ids = {extension.id for extension in manager.get_extensions()}

        self.assertIn("approval", before_ids)
        self.assertIn("emoji", after_ids)
        self.assertIn("flags", after_ids)
        self.assertIn("approval", after_ids)

    def test_run_extension_migrations_requires_installation(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_migrations("alpha-tools")

        self.assertEqual(context.exception.code, "extension_migrations_not_installed")

    def test_migrate_extensions_command_requires_installation(self):
        with self.assertRaisesMessage(CommandError, "尚未安装"):
            call_command("migrate_extensions", "alpha-tools")

    def test_migrate_extensions_command_executes_single_extension(self):
        ExtensionService.install_extension("alpha-tools")

        stdout = StringIO()
        call_command("migrate_extensions", "alpha-tools", "--format", "json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["summary"]["target_count"], 1)
        self.assertEqual(payload["summary"]["error_count"], 0)
        self.assertEqual(payload["extensions"][0]["id"], "alpha-tools")
        self.assertEqual(payload["extensions"][0]["status"], "ok")
        self.assertIn("0001_bootstrap.py", payload["extensions"][0]["details"]["skipped_migration_files"])

    def test_migrate_extensions_command_dry_run_all_does_not_persist_state(self):
        installation = ExtensionInstallation.objects.create(
            extension_id="alpha-tools",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={},
        )

        stdout = StringIO()
        call_command("migrate_extensions", "--all", "--dry-run", "--format", "json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertEqual(sample_extension["status"], "ok")
        self.assertIn("0001_bootstrap.py", sample_extension["migration_plan"]["pending_files"])
        installation.refresh_from_db()
        self.assertEqual(installation.meta, {})

    def test_runtime_hook_requires_manifest_declaration(self):
        ExtensionService.install_extension("alpha-tools")

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_runtime_hook("alpha-tools", "run_unknown")

        self.assertEqual(context.exception.code, "extension_runtime_hook_not_declared")

    def test_enable_ignores_stale_core_installation_dependency_record(self):
        ExtensionService.install_extension("alpha-tools")
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

        enabled = ExtensionService.set_extension_enabled("alpha-tools", True)

        self.assertTrue(enabled.runtime.enabled)

    def test_disable_raises_when_enabled_dependents_exist(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("notifications", False)

        self.assertEqual(context.exception.code, "extension_disable_blocked")
        self.assertIn("approval", context.exception.details["blocking_dependents"])

    def test_disable_raises_for_protected_extension(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("posts", False)

        self.assertEqual(context.exception.code, "extension_disable_protected_blocked")
        self.assertIn("protected_reason", context.exception.details)

    def test_uninstall_raises_for_protected_extension(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.uninstall_extension("posts")

        self.assertEqual(context.exception.code, "extension_uninstall_protected_blocked")
        self.assertIn("protected_reason", context.exception.details)

    def test_uninstall_disables_enabled_extension_first(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.enabled)

        uninstalled = ExtensionService.uninstall_extension("alpha-tools")

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
            ExtensionService.install_extension("alpha-tools")

        self.assertEqual(context.exception.code, "extension_install_incompatible_bias_version")
        self.assertEqual(context.exception.details["required_bias_version"], "^2.0.0")


class DomainEventRegistryTests(TestCase):
    def test_runtime_reset_clears_extension_event_listeners_and_restores_runtime_listeners(self):
        from apps.core.extensions.bootstrap import get_extension_host

        class TemporaryExtensionEvent:
            pass

        bus = get_forum_event_bus()
        bus.clear()

        def handle_temporary_event(event):
            return None

        bus.register(TemporaryExtensionEvent, handle_temporary_event)
        self.assertIn(TemporaryExtensionEvent, bus._listeners)

        reset_extension_runtime_state()

        self.assertNotIn(handle_temporary_event, bus._listeners.get(TemporaryExtensionEvent, []))
        get_extension_host()
        self.assertTrue(any(event_type is not TemporaryExtensionEvent for event_type in bus._listeners))

    def test_dispatches_handlers_for_extension_events(self):
        class DiscussionRefreshEvent:
            def __init__(self, discussion_id: int):
                self.discussion_id = discussion_id

        class RelatedRecordsRefreshEvent:
            def __init__(self, record_ids):
                self.record_ids = tuple(record_ids)

        bus = DomainEventBus()
        received = []

        def handle_discussion_refresh(event):
            received.append(("discussion", event.discussion_id))

        def handle_related_refresh(event):
            received.append(("related", event.record_ids))

        bus.register(DiscussionRefreshEvent, handle_discussion_refresh)
        bus.register(RelatedRecordsRefreshEvent, handle_related_refresh)
        bus.dispatch(DiscussionRefreshEvent(discussion_id=12))
        bus.dispatch(RelatedRecordsRefreshEvent(record_ids=(3, 7)))

        self.assertEqual(received, [("discussion", 12), ("related", (3, 7))])

class ResourceRegistryTests(TestCase):
    def test_api_resource_extender_registers_resource_in_bias_api_resources_contract(self):
        class ContractResource(Resource):
            def type(self):
                return "contract"

        app = ExtensionApplication()
        extension = app.get_or_create_runtime_view("alpha-tools")
        ApiResourceExtender.from_resource(ContractResource).extend(app, extension)

        self.assertIn(ContractResource, app.make("bias.api.resources"))

    def test_extension_runtime_reset_allows_core_resources_to_rebootstrap(self):
        from apps.core.forum_resources import bootstrap_forum_resource_fields

        reset_extension_runtime_state()
        registry = get_resource_registry()
        bootstrap_forum_resource_fields(registry)

        self.assertIsNotNone(registry.get_resource("forum"))
        self.assertIsNotNone(registry.get_resource("admin_stats"))

    def test_core_resources_bootstrap_per_resource_registry_instance(self):
        from apps.core.forum_resources import bootstrap_forum_resource_fields

        first = ResourceRegistry()
        second = ResourceRegistry()

        bootstrap_forum_resource_fields(first)
        bootstrap_forum_resource_fields(second)

        self.assertIsNotNone(first.get_resource("forum"))
        self.assertIsNotNone(second.get_resource("forum"))

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

    def test_api_resource_extender_aliases_apply_fluent_mutations(self):
        registry = ResourceRegistry()
        app = ExtensionApplication(resource_registry=registry)
        extension = SimpleNamespace(extension_id="bias-api")

        registry.register_field(ResourceFieldDefinition(
            resource="alias_items",
            field="title",
            module_id="core",
            resolver=lambda instance, context: "title",
        ))
        registry.register_relationship(ResourceRelationshipDefinition(
            resource="alias_items",
            relationship="owner",
            module_id="core",
            resolver=lambda instance, context: "owner",
        ))
        registry.register_endpoint(ResourceEndpointDefinition(
            resource="alias_items",
            endpoint="show",
            module_id="core",
            handler=lambda context: {"show": True},
            operation="add",
        ))
        registry.register_sort(ResourceSortDefinition(
            resource="alias_items",
            sort="created",
            module_id="core",
            handler="created_at",
            operation="add",
        ))
        registry.register_filter(ResourceFilterDefinition(
            resource="alias_items",
            filter="state",
            module_id="core",
            handler=lambda queryset, value, context: queryset,
            operation="add",
        ))

        (
            ApiResourceExtender("alias_items")
            .fields_before_all(ResourceFieldDefinition(
                resource="alias_items",
                field="first_field",
                module_id="",
                resolver=lambda instance, context: "first",
            ))
            .mutate_field("title", lambda field: ResourceFieldDefinition(
                resource=field.resource,
                field=field.field,
                module_id=field.module_id,
                resolver=field.resolver,
                description="mutated title",
            ))
            .relationships_before_all(ResourceRelationshipDefinition(
                resource="alias_items",
                relationship="first_relation",
                module_id="",
                resolver=lambda instance, context: None,
            ))
            .mutate_relationship("owner", lambda relationship: ResourceRelationshipDefinition(
                resource=relationship.resource,
                relationship=relationship.relationship,
                module_id=relationship.module_id,
                resolver=relationship.resolver,
                description="mutated owner",
            ))
            .endpoint_before_all(ResourceEndpointDefinition(
                resource="alias_items",
                endpoint="first_endpoint",
                module_id="",
                handler=lambda context: {"first": True},
                operation="add",
            ))
            .mutate_endpoint("show", lambda endpoint: ResourceEndpointDefinition(
                resource=endpoint.resource,
                endpoint=endpoint.endpoint,
                module_id=endpoint.module_id,
                handler=lambda context: {"show": "mutated"},
            ))
            .sort_before_all(ResourceSortDefinition(
                resource="alias_items",
                sort="first_sort",
                module_id="",
                handler=("first_at",),
            ))
            .mutate_sort("created", lambda sort: ResourceSortDefinition(
                resource=sort.resource,
                sort=sort.sort,
                module_id=sort.module_id,
                handler=("-created_at",),
            ))
            .filter_before_all(ResourceFilterDefinition(
                resource="alias_items",
                filter="first_filter",
                module_id="",
                handler=lambda queryset, value, context: queryset,
            ))
            .mutate_filter("state", lambda item: ResourceFilterDefinition(
                resource=item.resource,
                filter=item.filter,
                module_id=item.module_id,
                handler=item.handler,
                description="mutated state",
            ))
            .extend(app, extension)
        )
        app.make("resources")

        self.assertEqual(
            [(item.field, item.description) for item in registry.get_effective_fields("alias_items")],
            [("first_field", ""), ("title", "mutated title")],
        )
        self.assertEqual(
            [(item.relationship, item.description) for item in registry.get_effective_relationships("alias_items")],
            [("first_relation", ""), ("owner", "mutated owner")],
        )
        self.assertEqual(
            [item.endpoint for item in registry.get_dispatch_endpoints("alias_items")],
            ["first_endpoint", "show"],
        )
        self.assertEqual(
            registry.get_dispatch_endpoint("alias_items", "show", "GET").handler({}),
            {"show": "mutated"},
        )
        self.assertEqual(
            [item.sort for item in registry.get_effective_sorts("alias_items")],
            ["first_sort", "created"],
        )
        self.assertEqual(
            [item.handler for item in registry.get_effective_sorts("alias_items")],
            [("first_at",), ("-created_at",)],
        )
        self.assertEqual(
            [(item.filter, item.description) for item in registry.get_effective_filters("alias_items")],
            [("first_filter", ""), ("state", "mutated state")],
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

    def test_sort_definitions_apply_to_external_sort_list_with_anchors(self):
        registry = ResourceRegistry()
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="first",
                module_id="extension",
                handler={"name": "first"},
                operation="before_all",
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="before",
                module_id="extension",
                handler={"name": "before"},
                operation="before",
                anchor="base",
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="after",
                module_id="extension",
                handler={"name": "after"},
                operation="after",
                anchor="base",
            )
        )
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="base",
                module_id="extension",
                operation="mutate",
                mutator=lambda sort: {"name": sort["name"], "mutated": True},
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

        self.assertEqual(
            registry.apply_sort_definitions("discussion", [{"name": "base"}, {"name": "old"}]),
            [{"name": "first"}, {"name": "before"}, {"name": "base", "mutated": True}, {"name": "after"}],
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
                with patch("apps.core.resource_dispatcher.has_forum_permission", return_value=False):
                    denied = dispatch_resource_endpoint(request, resource="secure", endpoint="show")
                with patch("apps.core.resource_dispatcher.has_forum_permission", return_value=True):
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

    def test_resource_path_routes_group_same_path_operations(self):
        registry = ResourceRegistry()
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="shared_item",
                endpoint="create",
                module_id="shared",
                handler=lambda context: {"method": "POST"},
                methods=("POST",),
                path="/shared-items",
                absolute_path=True,
            )
        )
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="shared_item",
                endpoint="index",
                module_id="shared",
                handler=lambda context: {"method": "GET"},
                methods=("GET",),
                path="/shared-items",
                absolute_path=True,
            )
        )

        routes = {
            route.path: route
            for route in build_resource_path_route_definitions(registry)
        }

        route = routes["/shared-items"]
        self.assertEqual(route.methods, ("GET", "POST"))
        self.assertEqual(
            {(operation.endpoint, operation.methods) for operation in route.operations},
            {("create", ("POST",)), ("index", ("GET",))},
        )

    def test_resource_endpoint_router_dispatches_same_path_by_method(self):
        registry = ResourceRegistry()
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="shared_item",
                endpoint="create",
                module_id="shared",
                handler=lambda context: {"endpoint": context["endpoint"], "method": context["method"]},
                methods=("POST",),
                path="/shared-items",
                absolute_path=True,
            )
        )
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="shared_item",
                endpoint="index",
                module_id="shared",
                handler=lambda context: {"endpoint": context["endpoint"], "method": context["method"]},
                methods=("GET",),
                path="/shared-items",
                absolute_path=True,
            )
        )
        host = SimpleNamespace(
            resources=registry,
            make=lambda key, default=None: SimpleNamespace(get_mounts=lambda: ()) if key == "routes" else default,
        )
        api = build_api_application(extension_host=host, urls_namespace=f"same-path-resource-test-api-{uuid.uuid4().hex}")
        api_urls = api.urls
        urlconf_name = "apps.core.tests_same_path_resource_urls"
        urlconf = ModuleType(urlconf_name)
        urlconf.urlpatterns = [path("api/", api_urls)]
        sys.modules[urlconf_name] = urlconf

        try:
            clear_url_caches()
            with override_settings(ROOT_URLCONF=urlconf_name):
                with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                    get_response = self.client.get("/api/shared-items")
                    post_response = self.client.post(
                        "/api/shared-items",
                        data=json.dumps({}),
                        content_type="application/json",
                    )
        finally:
            clear_url_caches()
            sys.modules.pop(urlconf_name, None)

        self.assertEqual(get_response.status_code, 200, get_response.content)
        self.assertEqual(get_response.json(), {"endpoint": "index", "method": "GET"})
        self.assertEqual(post_response.status_code, 200, post_response.content)
        self.assertEqual(post_response.json(), {"endpoint": "create", "method": "POST"})

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

class TestRunnerTests(TestCase):
    def test_default_runner_uses_app_test_modules_without_explicit_labels(self):
        runner = BiasDiscoverRunner()
        app_names = {app for app in settings.INSTALLED_APPS if app.startswith("apps.")}
        app_names.update(
            app_config.name
            for app_config in apps.get_app_configs()
            if app_config.name.startswith("apps.")
        )
        labels = []
        for app in sorted(app_names):
            tests_path = Path(settings.BASE_DIR) / app.replace(".", "/") / "tests.py"
            if tests_path.exists() and "def test_" in tests_path.read_text(encoding="utf-8"):
                labels.append(f"{app}.tests")
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

    def test_core_product_code_does_not_import_extension_backends(self):
        violations: list[str] = []
        core_root = Path(settings.BASE_DIR) / "apps" / "core"
        for path in sorted(core_root.rglob("*.py")):
            if path.name == "tests.py" or "__pycache__" in path.parts:
                continue
            relative_path = path.relative_to(settings.BASE_DIR).as_posix()
            source = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(source.splitlines(), start=1):
                stripped = line.lstrip()
                if stripped.startswith(("from extensions.", "import extensions.")):
                    violations.append(f"{relative_path}:{line_number}: {line.strip()}")

        self.assertEqual(violations, [], "core product code must depend on extension runtime contracts, not extension backends")

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
                "storage_local_path": "custom-media",
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
        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["storage_driver"], "r2")
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
        ExtensionInstallation.objects.create(
            extension_id="alpha-tools",
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
        self.assertIn("notification_types", payload)
        self.assertIn("user_preferences", payload)
        self.assertIn("post_types", payload)
        self.assertIn("enabled_modules", payload)
        self.assertIn("enabled_extensions", payload)
        self.assertIn("extension_runtime", payload)
        self.assertIn("stamp", payload["extension_runtime"])
        self.assertIn("core", payload["enabled_modules"])
        self.assertFalse(any(item["id"] == "alpha-tools" for item in payload["enabled_extensions"]))

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
    def setUp(self):
        super().setUp()
        clear_runtime_setting_caches()

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_get_setting_group_returns_defaults_when_settings_table_is_unavailable(self):
        defaults = {"log_queries": False, "maintenance_mode": False}

        with patch("apps.core.settings_service.Setting.objects.filter", side_effect=OperationalError("no such table")):
            values = get_setting_group("advanced", defaults)

        self.assertEqual(values, defaults)

    def test_extension_setting_defaults_do_not_force_rebuild_on_hot_path(self):
        host = SimpleNamespace(
            get_runtime_extensions=lambda: (),
            get_extension_views=lambda: (),
        )

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=host) as get_host:
            self.assertEqual(get_extension_setting_group_defaults("advanced"), {})
            self.assertEqual(get_extension_setting_group_defaults("advanced"), {})

        get_host.assert_called_once_with()

    def test_advanced_settings_are_cached_until_runtime_settings_are_cleared(self):
        with patch("apps.core.settings_service.get_extension_setting_group_defaults", return_value={}) as get_defaults:
            first = get_advanced_settings()
            second = get_advanced_settings()

        self.assertEqual(first["maintenance_mode_key"], "none")
        self.assertEqual(second["maintenance_mode_key"], "none")
        get_defaults.assert_called_once_with("advanced")


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


