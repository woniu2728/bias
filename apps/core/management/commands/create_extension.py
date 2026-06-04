from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.version import APP_VERSION
from apps.core.extensions.validation import EXTENSION_ID_PATTERN


class Command(BaseCommand):
    help = "创建 Bias 扩展脚手架，生成 manifest、后台入口与基础目录。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("extension_id", help="扩展 ID，例如 sample-tools")
        parser.add_argument("--name", help="扩展显示名称，默认根据扩展 ID 推导")
        parser.add_argument("--description", default="", help="扩展描述")
        parser.add_argument("--author", default="Bias", help="扩展作者")
        parser.add_argument("--category", default="feature", help="扩展分类，默认 feature")
        parser.add_argument("--extension-version", default="0.1.0", help="扩展版本，默认 0.1.0")
        parser.add_argument("--force", action="store_true", help="若目录已存在则覆盖可生成文件")

    def handle(self, *args, **options):
        extension_id = str(options["extension_id"]).strip()
        if not EXTENSION_ID_PATTERN.match(extension_id):
            raise CommandError("扩展 ID 只能包含小写字母、数字和中划线，且不能以中划线开头或结尾")

        name = str(options.get("name") or self._build_default_name(extension_id)).strip()
        description = str(options.get("description") or "").strip()
        author = str(options.get("author") or "Bias").strip() or "Bias"
        category = str(options.get("category") or "feature").strip() or "feature"
        version = str(options.get("extension_version") or "0.1.0").strip() or "0.1.0"
        force = bool(options.get("force"))

        extension_dir = Path(settings.BASE_DIR) / "extensions" / extension_id
        if extension_dir.exists() and not force:
            raise CommandError(f"扩展目录已存在: {extension_dir}。如需覆盖，请传 --force")

        frontend_admin_dir = extension_dir / "frontend" / "admin"
        frontend_forum_dir = extension_dir / "frontend" / "forum"
        backend_dir = extension_dir / "backend"
        migrations_dir = backend_dir / "migrations"
        docs_dir = extension_dir / "docs"
        locale_dir = extension_dir / "locale"

        for path in (frontend_admin_dir, frontend_forum_dir, backend_dir, migrations_dir, docs_dir, locale_dir):
            path.mkdir(parents=True, exist_ok=True)

        self._write_json(
            extension_dir / "extension.json",
            self._build_manifest(extension_id, name, description, author, category, version),
        )
        self._write_text(
            frontend_admin_dir / "index.js",
            self._build_admin_index_source(extension_id),
        )
        self._write_text(
            frontend_admin_dir / "DetailPage.vue",
            self._build_detail_page_source(name),
        )
        self._write_text(
            frontend_admin_dir / "SettingsPage.vue",
            self._build_settings_page_source(name),
        )
        self._write_text(
            frontend_admin_dir / "PermissionsPage.vue",
            self._build_permissions_page_source(name),
        )
        self._write_text(
            frontend_admin_dir / "OperationsPage.vue",
            self._build_operations_page_source(name),
        )
        self._write_text(
            frontend_forum_dir / "index.js",
            self._build_forum_index_source(extension_id, name),
        )
        self._write_text(
            backend_dir / "__init__.py",
            "",
        )
        self._write_text(
            migrations_dir / "__init__.py",
            "",
        )
        self._write_text(
            migrations_dir / "0001_initial.py",
            self._build_migration_stub_source(),
        )
        self._write_text(
            backend_dir / "ext.py",
            self._build_backend_entry_source(extension_id, name),
        )
        self._write_text(
            docs_dir / "README.md",
            self._build_readme_source(extension_id, name),
        )
        self._write_text(
            locale_dir / ".gitkeep",
            "",
        )
        self._write_text(
            locale_dir / "zh-CN.json",
            self._build_locale_source(name),
        )

        self.stdout.write(self.style.SUCCESS("[OK] 已创建扩展脚手架"))
        self.stdout.write(f"- 扩展目录: {extension_dir}")
        self.stdout.write(f"- manifest: {extension_dir / 'extension.json'}")
        self.stdout.write(f"- 前端后台入口: {frontend_admin_dir / 'index.js'}")
        self.stdout.write(f"- 前台入口: {frontend_forum_dir / 'index.js'}")

    def _build_default_name(self, extension_id: str) -> str:
        return " ".join(part.capitalize() for part in extension_id.split("-"))

    def _build_manifest(
        self,
        extension_id: str,
        name: str,
        description: str,
        author: str,
        category: str,
        version: str,
    ) -> dict:
        return {
            "id": extension_id,
            "name": name,
            "version": version,
            "description": description,
            "icon": "fas fa-puzzle-piece",
            "category": category,
            "authors": [author],
            "documentation_url": f"/admin.html#/admin/docs?guide=extension-system-roadmap&extension={extension_id}",
            "dependencies": ["core"],
            "provides": [f"{extension_id}-panel"],
            "backend_entry": f"extensions.{extension_id.replace('-', '_')}.backend.ext",
            "compatibility": {
                "bias_version": f"^{APP_VERSION}",
                "api_version": "1.0",
                "api_stability": "experimental",
                "api_stability_label": "实验性",
                "breaking_change_policy": "Bias 在主版本升级前会优先通过路线图与开发文档公告扩展协议的 breaking change。",
            },
            "security": {
                "support_email": "security@example.com",
                "capabilities_notice": "此扩展处于实验阶段，请在生产环境启用前完成本地校验与权限审查。",
            },
            "distribution": {
                "channel": "private",
                "channel_label": "私有分发",
                "signing_key_id": "",
                "signature_url": "",
            },
            "migration_namespace": f"extensions.{extension_id.replace('-', '_')}.backend.migrations",
            "extra": {
                "display_order": 1000,
                "experimental": True,
            },
        }

    def _build_admin_index_source(self, extension_id: str) -> str:
        return (
            "import DetailPage from './DetailPage.vue'\n"
            "import OperationsPage from './OperationsPage.vue'\n"
            "import PermissionsPage from './PermissionsPage.vue'\n"
            "import SettingsPage from './SettingsPage.vue'\n\n"
            "export function resolveDetailPage() {\n"
            "  return DetailPage\n"
            "}\n\n"
            "export function resolveSettingsPage() {\n"
            "  return SettingsPage\n"
            "}\n\n"
            "export function resolvePermissionsPage() {\n"
            "  return PermissionsPage\n"
            "}\n\n"
            "export function resolveOperationsPage() {\n"
            "  return OperationsPage\n"
            "}\n"
        )

    def _build_detail_page_source(self, name: str) -> str:
        return (
            "<template>\n"
            "  <section class=\"ExtensionScaffoldCard\">\n"
            "    <header>\n"
            f"      <h2>{name} 详情</h2>\n"
            "      <p>这里承载扩展自己的详情摘要、诊断信息和平台之外的补充说明。</p>\n"
            "    </header>\n"
            "  </section>\n"
            "</template>\n\n"
            "<script setup>\n"
            "defineProps({\n"
            "  extension: {\n"
            "    type: Object,\n"
            "    default: () => ({}),\n"
            "  },\n"
            "  surface: {\n"
            "    type: String,\n"
            "    default: 'detail',\n"
            "  },\n"
            "})\n"
            "</script>\n\n"
            "<style scoped>\n"
            ".ExtensionScaffoldCard {\n"
            "  padding: 24px;\n"
            "  border: 1px solid var(--forum-border-color);\n"
            "  border-radius: var(--forum-radius-md);\n"
            "  background: var(--forum-bg-elevated);\n"
            "}\n"
            ".ExtensionScaffoldCard h2 {\n"
            "  margin: 0 0 8px;\n"
            "}\n"
            ".ExtensionScaffoldCard p {\n"
            "  margin: 0;\n"
            "  color: var(--forum-text-soft);\n"
            "}\n"
            "</style>\n"
        )

    def _build_forum_index_source(self, extension_id: str, name: str) -> str:
        return (
            "import { registerForumNavItem } from '@/forum/registry'\n\n"
            "export async function bootForumExtension() {\n"
            "  registerForumNavItem({\n"
            f"    key: '{extension_id}-entry',\n"
            f"    moduleId: '{extension_id}',\n"
            "    section: 'primary',\n"
            "    order: 90,\n"
            "    icon: 'fas fa-puzzle-piece',\n"
            f"    label: '{name}',\n"
            "    to: '/',\n"
            "    description: '扩展前台入口已成功注册。',\n"
            "  })\n"
            "}\n"
        )

    def _build_settings_page_source(self, name: str) -> str:
        return (
            "<template>\n"
            "  <section class=\"ExtensionScaffoldCard\">\n"
            "    <header>\n"
            f"      <h2>{name} 设置</h2>\n"
            "      <p>这里承载扩展自己的设置表单，后续可继续接入真实保存逻辑。</p>\n"
            "    </header>\n"
            "  </section>\n"
            "</template>\n\n"
            "<script setup>\n"
            "defineProps({\n"
            "  extension: {\n"
            "    type: Object,\n"
            "    default: () => ({}),\n"
            "  },\n"
            "  hostKind: {\n"
            "    type: String,\n"
            "    default: 'settings',\n"
            "  },\n"
            "})\n"
            "</script>\n\n"
            "<style scoped>\n"
            ".ExtensionScaffoldCard {\n"
            "  padding: 24px;\n"
            "  border: 1px solid var(--forum-border-color);\n"
            "  border-radius: var(--forum-radius-md);\n"
            "  background: var(--forum-bg-elevated);\n"
            "}\n"
            ".ExtensionScaffoldCard h2 {\n"
            "  margin: 0 0 8px;\n"
            "}\n"
            ".ExtensionScaffoldCard p {\n"
            "  margin: 0;\n"
            "  color: var(--forum-text-soft);\n"
            "}\n"
            "</style>\n"
        )

    def _build_operations_page_source(self, name: str) -> str:
        return (
            "<template>\n"
            "  <section class=\"ExtensionScaffoldCard\">\n"
            "    <header>\n"
            f"      <h2>{name} 操作</h2>\n"
            "      <p>这里承载扩展自己的运维动作、诊断信息或批处理工具。</p>\n"
            "    </header>\n"
            "  </section>\n"
            "</template>\n\n"
            "<script setup>\n"
            "defineProps({\n"
            "  extension: {\n"
            "    type: Object,\n"
            "    default: () => ({}),\n"
            "  },\n"
            "  hostKind: {\n"
            "    type: String,\n"
            "    default: 'operations',\n"
            "  },\n"
            "})\n"
            "</script>\n\n"
            "<style scoped>\n"
            ".ExtensionScaffoldCard {\n"
            "  padding: 24px;\n"
            "  border: 1px solid var(--forum-border-color);\n"
            "  border-radius: var(--forum-radius-md);\n"
            "  background: var(--forum-bg-elevated);\n"
            "}\n"
            ".ExtensionScaffoldCard h2 {\n"
            "  margin: 0 0 8px;\n"
            "}\n"
            ".ExtensionScaffoldCard p {\n"
            "  margin: 0;\n"
            "  color: var(--forum-text-soft);\n"
            "}\n"
            "</style>\n"
        )

    def _build_permissions_page_source(self, name: str) -> str:
        return (
            "<template>\n"
            "  <section class=\"ExtensionScaffoldCard\">\n"
            "    <header>\n"
            f"      <h2>{name} 权限</h2>\n"
            "      <p>这里承载扩展自己的授权说明、权限分组摘要或更细粒度的授权向导。</p>\n"
            "    </header>\n"
            "  </section>\n"
            "</template>\n\n"
            "<script setup>\n"
            "defineProps({\n"
            "  extension: {\n"
            "    type: Object,\n"
            "    default: () => ({}),\n"
            "  },\n"
            "  hostKind: {\n"
            "    type: String,\n"
            "    default: 'permissions',\n"
            "  },\n"
            "})\n"
            "</script>\n\n"
            "<style scoped>\n"
            ".ExtensionScaffoldCard {\n"
            "  padding: 24px;\n"
            "  border: 1px solid var(--forum-border-color);\n"
            "  border-radius: var(--forum-radius-md);\n"
            "  background: var(--forum-bg-elevated);\n"
            "}\n"
            ".ExtensionScaffoldCard h2 {\n"
            "  margin: 0 0 8px;\n"
            "}\n"
            ".ExtensionScaffoldCard p {\n"
            "  margin: 0;\n"
            "  color: var(--forum-text-soft);\n"
            "}\n"
            "</style>\n"
        )

    def _build_backend_entry_source(self, extension_id: str, name: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            "from apps.core.extensions import AdminNavigationExtender, ApiResourceExtender, FrontendExtender, LifecycleExtender, RuntimeActionsExtender, SettingsExtender\n"
            "from apps.core.extensions.backend import _build_runtime_action_definition, _build_setting_field_definition\n\n"
            "from apps.core.resource_registry import ResourceFieldDefinition\n\n"
            f"EXTENSION_ID = '{extension_id}'\n"
            f"EXTENSION_NAME = '{name}'\n\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        FrontendExtender(\n"
            f"            admin_entry='extensions/{extension_id}/frontend/admin/index.js',\n"
            f"            forum_entry='extensions/{extension_id}/frontend/forum/index.js',\n"
            "        ),\n"
            "        SettingsExtender(fields=(\n"
            "            _build_setting_field_definition({\n"
            "                'key': 'welcome_message',\n"
            "                'label': '欢迎语',\n"
            "                'type': 'text',\n"
            f"                'default': '欢迎使用 {name}',\n"
            "                'placeholder': '输入展示给管理员或用户的欢迎语',\n"
            "                'help_text': '示例设置项，用于验证扩展设置协议已经打通。',\n"
            "                'order': 10,\n"
            "            }),\n"
            "            _build_setting_field_definition({\n"
            "                'key': 'feature_enabled',\n"
            "                'label': '启用功能开关',\n"
            "                'type': 'boolean',\n"
            "                'default': True,\n"
            "                'help_text': '示例布尔型设置项。',\n"
            "                'order': 20,\n"
            "            }),\n"
            "        )),\n"
            "        ApiResourceExtender('forum').fields(forum_resource_field_definitions),\n"
            "        RuntimeActionsExtender(actions=(\n"
            "            _build_runtime_action_definition({\n"
            "                'key': 'rebuild-cache',\n"
            "                'label': '刷新缓存',\n"
            "                'hook': 'run_rebuild_cache',\n"
            "                'tone': 'subtle',\n"
            "                'confirm_title': '刷新扩展缓存',\n"
            f"                'confirm_message': '确定执行 {name} 的缓存刷新操作吗？',\n"
            "                'confirm_text': '刷新',\n"
            "                'success_message': '扩展缓存已刷新。',\n"
            "                'requires_enabled': True,\n"
            "                'requires_installed': True,\n"
            "                'order': 5,\n"
            "            }),\n"
            "        ), generated_page=True),\n"
            "        AdminNavigationExtender(generated_permissions_page=True),\n"
            "        LifecycleExtender(\n"
            "            install=install,\n"
            "            enable=enable,\n"
            "            disable=disable,\n"
            "            uninstall=uninstall,\n"
            "        ),\n"
            "    ]\n\n"
            "\n"
            "def forum_resource_field_definitions():\n"
            "    return (\n"
            "        ResourceFieldDefinition(\n"
            "            resource='forum',\n"
            "            field='scaffold_status',\n"
            "            module_id=EXTENSION_ID,\n"
            "            resolver=resolve_forum_scaffold_status,\n"
            "            description='脚手架示例字段，用于验证 ApiResourceExtender 已接入。',\n"
            "        ),\n"
            "    )\n\n"
            "\n"
            "def resolve_forum_scaffold_status(forum, context):\n"
            "    return {\n"
            "        'extension_id': EXTENSION_ID,\n"
            "        'extension_name': EXTENSION_NAME,\n"
            "        'ready': True,\n"
            "    }\n\n"
            "\n"
            "def install(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已完成',\n"
            "        'message': f'{context.extension_name} 安装生命周期已执行。',\n"
            "        'details': {\n"
            "            'extension_id': context.extension_id,\n"
            "            'migration_namespace': context.migration_namespace,\n"
            "        },\n"
            "    }\n\n"
            "\n"
            "def enable(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已启用',\n"
            "        'message': f'{context.extension_name} 启用生命周期已执行。',\n"
            "    }\n\n"
            "\n"
            "def disable(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已停用',\n"
            "        'message': f'{context.extension_name} 停用生命周期已执行。',\n"
            "    }\n\n"
            "\n"
            "def uninstall(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已完成',\n"
            "        'message': f'{context.extension_name} 卸载生命周期已执行。',\n"
            "    }\n\n"
            "\n"
            "def run_rebuild_cache(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已刷新',\n"
            "        'message': f'{context.extension_name} 的运行缓存已刷新。',\n"
            "    }\n\n"
            "\n"
            "def run_migrations(context):\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'status_label': '已执行',\n"
            "        'message': f'{context.extension_name} 的扩展迁移钩子已执行。',\n"
            "        'details': {\n"
            "            'migration_namespace': context.migration_namespace,\n"
            "            'hook': 'run_migrations',\n"
            "        },\n"
            "    }\n"
        )

    def _build_migration_stub_source(self) -> str:
        return (
            "from __future__ import annotations\n\n"
            "\n"
            "def apply():\n"
            "    return 'initial'\n"
        )

    def _build_readme_source(self, extension_id: str, name: str) -> str:
        return (
            f"# {name}\n\n"
            f"- 扩展 ID: `{extension_id}`\n"
            "- 用途：通过脚手架生成的 Bias 扩展样板。\n"
            "- 迁移目录：`backend/migrations`\n"
            "- API 资源：默认通过 `ApiResourceExtender(\"forum\")` 注册 `scaffold_status` 示例字段。\n"
            "- 后续可在 `frontend/admin`、`backend`、`locale` 中继续扩展能力。\n"
        )

    def _build_locale_source(self, name: str) -> str:
        return json.dumps({
            "extension.name": name,
            "extension.status.ready": "扩展资源已就绪",
        }, ensure_ascii=False, indent=2) + "\n"

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
