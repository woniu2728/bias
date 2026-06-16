import importlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
import shutil
from io import StringIO
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
from django.db import OperationalError, connection
from django.db.migrations.recorder import MigrationRecorder
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
from apps.core.extensions.registry import get_extension_registry
from apps.core.extensions import ApiResourceExtender, ConditionalExtender, PostEventExtender, SearchDriverExtender
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
from apps.core.bootstrap_config import SiteBootstrapConfig, load_site_bootstrap
from apps.core.models import AuditLog, ExtensionInstallation, Setting
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


def call_command_quietly(*args, **kwargs):
    kwargs.setdefault("stdout", StringIO())
    kwargs.setdefault("stderr", StringIO())
    return call_command(*args, **kwargs)


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
    return Path(tempfile.mkdtemp(prefix=f"bias-test-{uuid.uuid4().hex}-"))


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
        "from apps.core.extensions import LifecycleExtender, SettingsExtender, setting_field\n"
        "\n"
        "def extend():\n"
        "    return [\n"
        "        LifecycleExtender(install=install, enable=enable, disable=disable, uninstall=uninstall),\n"
        "        SettingsExtender(fields=(\n"
        "            setting_field({'key': 'welcome_message', 'label': '欢迎语', 'type': 'text', 'default': '欢迎使用 Alpha Tools'}),\n"
        "            setting_field({'key': 'card_tone', 'label': '卡片风格', 'type': 'select', 'default': 'primary', 'options': ({'value': 'primary', 'label': '主色'}, {'value': 'warm', 'label': '暖色'})}),\n"
        "            setting_field({'key': 'show_runtime_tips', 'label': '显示运行提示', 'type': 'boolean', 'default': True}),\n"
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



@dataclass(frozen=True)
class AlphaStringEvent(DomainEvent):
    value: str
    def event_type(self) -> str:
        return "alpha.string"
