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
        extension_package = self._build_extension_package(extension_id)
        app_config_class = self._build_app_config_class(extension_package)

        extension_dir = Path(settings.BASE_DIR) / "extensions" / extension_package
        if extension_dir.exists() and not force:
            raise CommandError(f"扩展目录已存在: {extension_dir}。如需覆盖，请传 --force")

        frontend_admin_dir = extension_dir / "frontend" / "admin"
        frontend_forum_dir = extension_dir / "frontend" / "forum"
        backend_dir = extension_dir / "backend"
        django_migrations_dir = backend_dir / "django_migrations"
        docs_dir = extension_dir / "docs"
        locale_dir = extension_dir / "locale"

        for path in (frontend_admin_dir, frontend_forum_dir, backend_dir, django_migrations_dir, docs_dir, locale_dir):
            path.mkdir(parents=True, exist_ok=True)

        self._write_json(
            extension_dir / "extension.json",
            self._build_manifest(extension_id, extension_package, app_config_class, name, description, author, category, version),
        )
        self._write_text(
            frontend_admin_dir / "index.js",
            self._build_admin_index_source(extension_id),
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
            backend_dir / "apps.py",
            self._build_app_config_source(extension_package, app_config_class, name),
        )
        self._write_text(
            backend_dir / "ext.py",
            self._build_backend_entry_source(extension_id, extension_package, name),
        )
        self._write_text(
            django_migrations_dir / "__init__.py",
            "",
        )
        self._write_text(
            extension_dir / "README.md",
            self._build_readme_source(extension_id, name),
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
        self.stdout.write("- 校验扩展: python manage.py validate_extensions --strict")
        self.stdout.write("- 生成前端资源: python manage.py build_extension_frontend --rebuild")

    def _build_default_name(self, extension_id: str) -> str:
        return " ".join(part.capitalize() for part in extension_id.split("-"))

    def _build_extension_package(self, extension_id: str) -> str:
        return extension_id.replace("-", "_")

    def _build_app_config_class(self, extension_package: str) -> str:
        return "".join(part.capitalize() for part in extension_package.split("_") if part) + "ExtensionConfig"

    def _build_manifest(
        self,
        extension_id: str,
        extension_package: str,
        app_config_class: str,
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
            "backend_entry": f"extensions.{extension_package}.backend.ext",
            "django_app_config": f"extensions.{extension_package}.backend.apps.{app_config_class}",
            "django_app_label": extension_package,
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
            "extra": {
                "display_order": 1000,
                "experimental": True,
            },
        }

    def _build_admin_index_source(self, extension_id: str) -> str:
        return (
            "import { extendAdmin } from '@bias/admin'\n"
            "\n"
            "export const extend = [\n"
            "  extendAdmin(admin => admin),\n"
            "]\n\n"
            "export function resolveDetailPage() {\n"
            "  return null\n"
            "}\n"
        )

    def _build_forum_index_source(self, extension_id: str, name: str) -> str:
        return (
            "import { extendForum } from '@bias/forum'\n\n"
            "export const extend = [\n"
            "  extendForum(forum => forum),\n"
            "]\n"
        )

    def _build_backend_entry_source(self, extension_id: str, extension_package: str, name: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            "from apps.core.extensions import FrontendExtender\n\n"
            f"EXTENSION_ID = '{extension_id}'\n"
            f"EXTENSION_NAME = '{name}'\n\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        (FrontendExtender()\n"
            f"            .admin('extensions/{extension_package}/frontend/admin/index.js')\n"
            f"            .forum('extensions/{extension_package}/frontend/forum/index.js')),\n"
            "    ]\n\n"
        )

    def _build_app_config_source(self, extension_package: str, app_config_class: str, name: str) -> str:
        verbose_name = name.replace('"', '\\"')
        return (
            "from django.apps import AppConfig\n\n\n"
            f"class {app_config_class}(AppConfig):\n"
            "    default_auto_field = \"django.db.models.BigAutoField\"\n"
            f"    label = \"{extension_package}\"\n"
            f"    name = \"extensions.{extension_package}.backend\"\n"
            f"    verbose_name = \"Bias {verbose_name} Extension\"\n"
        )

    def _build_readme_source(self, extension_id: str, name: str) -> str:
        return (
            f"# {name}\n\n"
            f"- 扩展 ID: `{extension_id}`\n"
            "- 用途：通过脚手架生成的 Bias 最小扩展样板。\n"
            "- 后端入口：`backend/ext.py` 的 `extend()` 返回扩展器列表，是扩展接入 Bias 运行时的主入口。\n"
            "- 后端 SDK：扩展代码只应从 `apps.core.extensions`、`apps.core.extensions.runtime`、`apps.core.extensions.platform`、`apps.core.extensions.forum` 获取宿主能力，不直接 import `apps.core.*` 内部实现。\n"
            "- Django AppConfig：`backend/apps.py` 绑定扩展 app label，确保模型与迁移归属能被审计。\n"
            "- 前端入口：`frontend/admin/index.js` 与 `frontend/forum/index.js` 导出 `extend`，由 Bias 前端扩展注册中心加载。\n"
            "- API 资源：如需扩展 JSON:API 资源，请在 `backend/ext.py` 中加入 `ApiResourceExtender(...)`。\n"
            "- 迁移：如需扩展迁移，请添加到 `backend/django_migrations`；Bias 会按扩展 app label 注册 Django migration 模块。\n"
            "- 模型归属：如需拥有模型，请在 `backend/ext.py` 中使用 `ModelExtender().owns(...)` 声明，并通过 `python manage.py inspect_extensions --extension-id "
            f"{extension_id}` 查看模型归属审计。\n"
            "- 校验命令：`python manage.py validate_extensions --strict`\n"
            "- 前端资源：`python manage.py build_extension_frontend --rebuild`\n"
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
