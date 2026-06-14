from __future__ import annotations

import re


SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
EXTENSION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PACKAGE_NAME_PATTERN = re.compile(r"^[a-z0-9_.-]+/[a-z0-9_.-]+$")
DJANGO_APP_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
EXPORT_FUNCTION_PATTERN = re.compile(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(")
EXPORT_DECLARATION_PATTERN = re.compile(r"export\s+(?:const|let|var|class)\s+([A-Za-z0-9_]+)\b")
VERSION_RANGE_PATTERN = re.compile(r"^(?:\^|~|>=|<=|>|<)?\d+\.\d+\.\d+$")
API_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
MIGRATION_FILE_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.py$")
EXTENSION_SOURCE_SUFFIXES = {".json", ".js", ".jsx", ".ts", ".tsx", ".vue", ".py", ".md", ".css", ".scss", ".less"}
SKIPPED_SOURCE_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "dist", "build", ".venv", "venv"}
EXTERNAL_PROJECT_NAME_PATTERN = re.compile(r"\b" + "fla" + "rum" + r"\b", re.IGNORECASE)
PYTHON_EXTENSION_IMPORT_PATTERN = re.compile(
    r"^(?:from\s+extensions\.([A-Za-z0-9_]+)([A-Za-z0-9_\.]*)\b|import\s+extensions\.([A-Za-z0-9_]+)([A-Za-z0-9_\.]*)\b)",
    re.MULTILINE,
)
PYTHON_EXTENSION_INTERNAL_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from\s+extensions\.([A-Za-z0-9_]+)([A-Za-z0-9_\.]*)\b|import\s+extensions\.([A-Za-z0-9_]+)([A-Za-z0-9_\.]*)\b)",
    re.MULTILINE,
)
FORBIDDEN_CROSS_EXTENSION_INTERNAL_IMPORT_RE = re.compile(
    r"^\.backend\.(?:models|services|tasks|signals|events|visibility|admin|admin_api|api|handlers|resources|resource|listeners)(?:\.|$)"
)
FORBIDDEN_EXTENSION_SOURCE_PATTERNS = (
    (
        "forbidden_low_level_resource_extender",
        re.compile(r"\bResourceExtender\b"),
        "扩展源码不能直接使用 ResourceExtender；请使用 ApiResourceExtender 注册资源、字段、关系、端点和排序。",
    ),
    (
        "forbidden_external_project_name",
        EXTERNAL_PROJECT_NAME_PATTERN,
        "扩展源码不能包含外部项目命名残留；产品命名必须使用 Bias/bias。",
    ),
    (
        "forbidden_core_module_frontend_contribution",
        re.compile(r"\bmoduleId\s*:\s*['\"]core['\"]"),
        "扩展前端贡献不能声明为 core 模块；请使用当前扩展 ID 作为 moduleId，或省略 moduleId 由扩展运行域归属。",
    ),
    (
        "forbidden_django_app_entry_import",
        re.compile(r"^\s*(?:from|import)\s+apps\.[A-Za-z0-9_]+(?:\.(?:admin|views|tasks|signals)\b|\s+import\s+(?:admin|views|tasks|signals)\b)", re.MULTILINE),
        "扩展后端不能直接导入 Django app 的 admin/views/tasks/signals 入口；请把运行入口声明到扩展 backend 下。",
    ),
)
FORBIDDEN_EXTENSION_MANIFEST_FIELD_PATTERNS = (
    (
        "forbidden_django_migration_module_manifest_field",
        re.compile(r'"django_migration_module"\s*:'),
        "扩展清单不能声明 django_migration_module；Django migration 模块由 Bias 根据扩展 ID 内部推导。",
    ),
    (
        "forbidden_migration_namespace_manifest_field",
        re.compile(r'"migration_namespace"\s*:'),
        "扩展清单不能声明 migration_namespace；扩展迁移必须通过 django_app_config 与 backend/django_migrations 接入。",
    ),
)
