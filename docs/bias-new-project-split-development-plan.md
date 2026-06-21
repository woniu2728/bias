# Bias 新项目拆分开发方案

## 口径确认

本方案采用“新建项目，旧项目暂且不动”的路线：

```text
旧项目 bias
  只作为参考源、功能基线、测试样本和扩展迁移来源
  第一阶段不直接重构、不改包名、不搬目录

新项目 bias-core
  先开发独立后端核心包
  提供 bias_core Python 包和后端扩展 SDK

新项目 bias-site
  再开发网站工程
  作为最终可部署站点，依赖 bias-core

新项目 bias-ext-*
  最后把旧项目 extensions/ 下的扩展逐个迁移出来
  每个扩展独立成项目
```

这条路线的目标是降低风险：旧项目保持可运行，新项目逐步复刻和收敛能力，直到新架构能独立跑通。

## 一、总体仓库规划

推荐先采用多个独立仓库，或者本地多目录开发：

```text
workspace/
├─ bias/                     # 旧项目，只读参考为主
├─ bias-core/                # 新后端核心包
├─ bias-site/                # 新网站工程
├─ bias-frontend-sdk/        # 可选，@bias/core 前端 SDK 包
├─ bias-ext-users/           # 后续迁移出的用户扩展
├─ bias-ext-discussions/     # 后续迁移出的讨论扩展
├─ bias-ext-posts/
├─ bias-ext-tags/
└─ bias-ext-...
```

如果想先降低仓库管理成本，也可以用 monorepo：

```text
bias-platform/
├─ packages/
│  ├─ bias-core/
│  ├─ bias-site/
│  ├─ frontend-sdk/
│  └─ extensions/
│     ├─ users/
│     ├─ discussions/
│     └─ tags/
└─ docs/
```

但从“旧项目不动、新项目独立”的目标看，初期更推荐多目录独立开发。每个项目都能独立安装、测试、发布，边界更清楚。

## 二、拆分边界

### 1. bias-core 负责什么

`bias-core` 是后端核心平台包，负责：

- Django app。
- 核心数据库模型：
  - settings
  - audit logs
  - extension installations
- 扩展宿主：
  - 扩展发现
  - 扩展加载
  - Extender 解析
  - 生命周期
  - 启停状态
  - 安全/兼容校验
- 后端扩展 SDK：
  - `bias_core.extensions`
  - `bias_core.extensions.runtime`
  - `bias_core.extensions.platform`
  - `bias_core.extensions.forum`
  - `bias_core.extensions.contracts`
  - `bias_core.extensions.sdk`
- 资源 API 运行时：
  - resource registry
  - JSON:API serializer
  - include/filter/sort/page
  - visibility/policy 集成
- 平台服务：
  - settings
  - audit
  - auth helpers
  - authorization/policy
  - visibility
  - queue
  - storage
  - email
  - markdown
  - search index registry
- API 应用构建器：
  - core API
  - admin API
  - extension API routes
- WebSocket/routing 支撑。
- 管理命令：
  - install/upgrade/doctor
  - sync_extensions
  - extension enable/disable/rebuild
- 测试工具：
  - core test runner
  - extension testing helpers

### 2. bias-core 不负责什么

`bias-core` 不包含：

- 具体网站的 `config/settings.py`。
- Docker Compose 部署编排。
- Nginx 配置。
- 完整 Vue 前端宿主应用。
- 具体论坛业务扩展：
  - users
  - discussions
  - posts
  - tags
  - notifications
  - likes
  - search
  - uploads
  - realtime
- 旧项目里的本地 `extensions/` 目录。
- 站点实例配置和运行数据。

但 `bias-core` 需要为主题扩展预留后端协议：

- 主题扩展注册。
- `ThemeExtender` 公共 API。
- 主题 CSS、assets、design tokens 的 manifest 描述。
- primary theme 唯一启用约束。
- 主题兼容版本校验。
- 主题设置项与普通扩展设置项的统一存储。

主题不属于 core 的具体实现内容，但主题协议属于 core 的平台能力。

### 3. bias-site 负责什么

`bias-site` 是网站工程，负责：

- Django 项目配置：
  - settings
  - urls
  - asgi
  - wsgi
  - celery
- 组合 `bias-core` 和已安装扩展。
- 提供前端宿主应用：
  - forum shell
  - admin shell
  - extension manifest loader
  - import map / alias resolver
  - theme CSS loader
  - design token applicator
  - stable theme slots
- 部署：
  - Dockerfile
  - docker-compose.yml
  - nginx.conf
  - install/upgrade 脚本
- 站点配置：
  - `.env`
  - `instance/site.json`
- 静态文件、媒体目录、日志目录。

### 4. 前端 SDK 负责什么

前端 SDK 推荐单独成包，包名 `@bias/core`。

它负责：

- 前端扩展 API。
- forum/admin/common 注册表。
- 类型定义。
- 扩展前端运行时适配层。
- 主题扩展前端 API。

它不负责：

- 完整页面布局。
- 具体论坛 UI。
- 具体后台页面。
- 具体扩展组件。

主题相关 API 应包括：

- 注册 theme variant。
- 注册允许替换的主题 slot component。
- 读取宿主暴露的 design tokens。
- 读取主题设置。
- 注入主题局部样式或 assets。

第一阶段可以把它放在 `bias-site/frontend` 里开发，稳定后再独立成 `bias-frontend-sdk` 项目。

## 三、从旧项目抽取的总体原则

### 1. 先复制，后整理

第一版不要边抽边重构。

推荐顺序：

1. 从旧项目复制 core 相关模块到 `bias-core`。
2. 保持模块行为尽量一致。
3. 建测试保证一致性。
4. 跑通最小网站工程。
5. 再逐步重命名、分层、清理内部模块。

原因：旧项目已经有大量行为细节和测试覆盖，过早重构容易丢行为。

### 2. 先建立新公共路径

新项目里直接使用目标路径：

```python
from bias_core.extensions import SettingsExtender
```

不要在新 `bias-core` 里继续暴露 `apps.core` 作为主路径。

可以提供兼容层：

```python
apps.core.extensions -> bias_core.extensions
```

但兼容层只服务迁移期，不作为新代码入口。

### 3. 旧项目只读参考

旧项目用于：

- 对照行为。
- 复制实现。
- 复制测试。
- 运行旧测试确认基线。
- 迁移扩展时作为源。

旧项目第一阶段不做大改，避免新旧两边同时不稳定。

## 四、bias-core 项目详细开发方案

### Phase C0：创建项目骨架

目录：

```text
bias-core/
├─ pyproject.toml
├─ README.md
├─ CHANGELOG.md
├─ src/
│  └─ bias_core/
│     ├─ __init__.py
│     ├─ apps.py
│     ├─ version.py
│     ├─ models.py
│     ├─ migrations/
│     ├─ extensions/
│     ├─ resources/
│     ├─ services/
│     ├─ api/
│     ├─ conf/
│     ├─ realtime/
│     ├─ management/
│     └─ middleware.py
├─ tests/
└─ docs/
```

`pyproject.toml` 初版：

```toml
[project]
name = "bias-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "Django>=5.0,<5.1",
  "django-ninja>=1.2,<1.3",
  "django-ninja-jwt>=5.3,<5.4",
  "django-ninja-extra>=0.21,<0.22",
  "channels>=4.0,<4.1",
  "channels-redis>=4.2,<4.3",
  "celery>=5.3,<5.4",
  "redis>=5.0,<5.1",
  "django-redis>=5.4,<5.5",
  "pydantic>=2.6,<2.7",
  "markdown>=3.5,<3.6",
  "bleach>=6.1,<6.2",
  "pymdown-extensions>=10.7,<10.8",
  "python-dateutil>=2.9,<3",
]

[project.optional-dependencies]
postgres = ["psycopg2-binary>=2.9,<3"]
storage = ["boto3>=1.34,<2", "oss2>=2.18,<3"]
dev = [
  "pytest>=8.1,<8.2",
  "pytest-django>=4.8,<4.9",
  "pytest-cov>=4.1,<4.2",
  "import-linter>=2.11,<3",
]

[tool.setuptools.packages.find]
where = ["src"]
```

验收：

- `pip install -e .[dev]` 成功。
- `python -c "import bias_core"` 成功。
- 空测试可运行。

### Phase C1：抽取基础 Django app 和模型

从旧项目复制：

```text
apps/core/apps.py        -> bias_core/apps.py
apps/core/models.py      -> bias_core/models.py
apps/core/migrations/    -> bias_core/migrations/
apps/core/version.py     -> bias_core/version.py
```

需要调整：

```python
class CoreConfig(AppConfig):
    name = "bias_core"
    label = "core"
```

为什么固定 `label = "core"`：

- 数据库迁移 app label 稳定。
- contenttypes/permissions 稳定。
- 未来从旧项目迁移数据时更可控。

模型表名保留旧项目表名：

```text
settings
audit_logs
extension_installations
```

验收：

- 测试 Django 项目中 `INSTALLED_APPS = ["bias_core"]` 能启动。
- `makemigrations --check` 不生成意外迁移。
- `migrate` 能创建核心表。

### Phase C2：抽取配置和启动保护

从旧项目复制并重命名：

```text
apps/core/bootstrap_config.py      -> bias_core/conf/bootstrap.py
apps/core/startup_guard.py         -> bias_core/startup_guard.py
apps/core/runtime_checks.py        -> bias_core/runtime_checks.py
apps/core/runtime_diagnostics.py   -> bias_core/runtime_diagnostics.py
apps/core/runtime_state.py         -> bias_core/runtime_state.py
apps/core/secret_validation.py     -> bias_core/secret_validation.py
apps/core/release.py               -> bias_core/release.py
```

新增：

```text
bias_core/conf/defaults.py
bias_core/conf/extension_discovery.py
```

`conf/defaults.py` 提供：

- core required apps。
- core middleware paths。
- core template loader paths。
- default cache/channel/celery helper。

`conf/extension_discovery.py` 从旧 `extension_django_apps.py` 演进而来，但改为支持两类来源：

- entry points 安装扩展。
- 本地 link 扩展。

验收：

- `bias-site` 能从 `bias_core.conf.bootstrap` 读取站点配置。
- `bias-site` 不需要 import core 内部实现。

### Phase C3：抽取扩展 SDK 公共面

优先抽公共 API：

```text
apps/core/extensions/__init__.py      -> bias_core/extensions/__init__.py
apps/core/extensions/sdk.py           -> bias_core/extensions/sdk.py
apps/core/extensions/contracts.py     -> bias_core/extensions/contracts.py
apps/core/extensions/types.py         -> bias_core/extensions/types.py
apps/core/extensions/extenders.py     -> bias_core/extensions/extenders.py
apps/core/extensions/platform.py      -> bias_core/extensions/platform.py
apps/core/extensions/runtime.py       -> bias_core/extensions/runtime.py
apps/core/extensions/forum.py         -> bias_core/extensions/forum.py
```

目标导入：

```python
from bias_core.extensions import SettingsExtender, setting_field
from bias_core.extensions.runtime import get_runtime_user_model
from bias_core.extensions.platform import api_error
from bias_core.extensions.forum import get_forum_registry
```

同时建立 `__all__` 稳定测试：

```text
tests/test_sdk_exports.py
tests/test_extension_boundary.py
```

验收：

- 公共导出可 import。
- 禁止扩展导入 `bias_core` 内部模块。
- 旧项目文档中的 SDK 示例能替换为新路径并运行。
- `ThemeExtender` 保留在公共导出中，后续主题包不需要 import 内部模块。

### Phase C4：抽取扩展宿主内部实现

从旧项目复制：

```text
apps/core/extensions/application*.py
apps/core/extensions/backend.py
apps/core/extensions/bootstrap*.py
apps/core/extensions/container.py
apps/core/extensions/definition_assembler.py
apps/core/extensions/extension_runtime.py
apps/core/extensions/manager*.py
apps/core/extensions/manifest.py
apps/core/extensions/module_loader.py
apps/core/extensions/registry.py
apps/core/extensions/lifecycle.py
apps/core/extensions/validation*.py
apps/core/extensions/version_compatibility.py
apps/core/extensions/frontend_*.py
apps/core/extensions/assets.py
apps/core/extensions/events.py
apps/core/extensions/event_bus.py
apps/core/extensions/signal_*.py
```

调整导入：

```text
apps.core.extensions.* -> bias_core.extensions.*
apps.core.models       -> bias_core.models
apps.core.services     -> bias_core.services.*
```

新边界：

```text
bias_core.extensions.registry    # 内部
bias_core.extensions.lifecycle   # 管理命令/后台可用，第三方不直接用
bias_core.extensions.runtime     # 第三方可用
bias_core.extensions.platform    # 第三方可用
```

验收：

- 可加载一个最小测试扩展。
- 可解析 `extension.json`。
- 可执行 `extend()`。
- 可注册 settings、permissions、routes、resources。
- 可识别 `type = "theme"` 或 manifest 中的 `theme` 字段，但第一版可以只做校验和透传。

### Phase C4.1：预留主题扩展协议

主题不是第一阶段必须完整落地的业务功能，但拆分时必须预留协议，否则后续会破坏前端宿主边界。

`bias-core` 需要定义：

```text
bias_core.extensions.ThemeExtender
bias_core.extensions.contracts.ThemeDefinition
bias_core.extensions.platform.get_enabled_theme
bias_core.extensions.platform.get_theme_settings
```

manifest 支持：

```json
{
  "id": "acme-theme",
  "type": "theme",
  "theme": {
    "kind": "primary",
    "forumCss": "frontend/dist/forum.css",
    "adminCss": "frontend/dist/admin.css",
    "entry": "frontend/dist/theme.js"
  }
}
```

第一版只要求：

- 能识别主题扩展。
- 能把主题 CSS 和 entry 输出到 frontend manifest。
- 能限制 primary theme 同时只启用一个。
- 能保存主题设置。

第一版不要求：

- 完整主题市场。
- 可视化主题编辑器。
- 任意组件替换。
- 多主题叠加。

验收：

- fixture theme extension 可被发现。
- manifest 中能看到 theme assets。
- 启用第二个 primary theme 时返回明确错误。
- 网站工程前端能读取 theme manifest。

### Phase C5：抽取资源 API

从旧项目复制并归类：

```text
apps/core/resource_*.py            -> bias_core/resources/
apps/core/registry/*.py            -> bias_core/resources/registry/
apps/core/resource_registry.py     -> bias_core/resources/registry.py
apps/core/resource_serializer.py   -> bias_core/resources/serializer.py
apps/core/resource_dispatcher.py   -> bias_core/resources/dispatcher.py
apps/core/resource_routes.py       -> bias_core/resources/routes.py
apps/core/resource_search.py       -> bias_core/resources/search.py
```

保留公共定义从 `bias_core.extensions` 暴露，内部实现放到 `bias_core.resources`。

验收：

- core resource registry 测试通过。
- 扩展能注册资源。
- API 能返回 JSON:API 风格响应。

### Phase C6：抽取平台服务

从旧项目复制：

```text
apps/core/settings_service.py       -> bias_core/services/settings.py
apps/core/audit.py                  -> bias_core/services/audit.py
apps/core/authorization.py          -> bias_core/services/authorization.py
apps/core/visibility.py             -> bias_core/services/visibility.py
apps/core/queue_service.py          -> bias_core/services/queue.py
apps/core/storage_service.py        -> bias_core/services/storage.py
apps/core/email_service.py          -> bias_core/services/email.py
apps/core/file_service.py           -> bias_core/services/files.py
apps/core/markdown_service.py       -> bias_core/services/markdown.py
apps/core/search_index_service.py   -> bias_core/services/search_index.py
apps/core/online_service.py         -> bias_core/services/online.py
apps/core/domain_events.py          -> bias_core/services/domain_events.py
```

兼容策略：

- 第三方扩展不直接 import `bias_core.services.*`。
- 通过 `bias_core.extensions.platform` 和 `runtime` 暴露必要能力。

验收：

- settings fallback 测试通过。
- audit 写入测试通过。
- queue/online/search index 基础测试通过。

### Phase C7：抽取 API、middleware、realtime

从旧项目复制：

```text
apps/core/api*.py                   -> bias_core/api/
apps/core/admin_*.py                -> bias_core/api/admin/
apps/core/auth.py                   -> bias_core/api/auth.py
apps/core/jwt_auth.py               -> bias_core/api/jwt_auth.py
apps/core/middleware.py             -> bias_core/middleware.py
apps/core/routing.py                -> bias_core/realtime/routing.py
apps/core/websocket_auth.py         -> bias_core/realtime/websocket_auth.py
```

`bias_core.api.runtime` 提供：

```python
build_api_application(extension_host=None)
```

`bias_core.realtime.routing` 提供：

```python
websocket_urlpatterns
```

验收：

- `bias-site` 可以挂载 `/api/`。
- `/api/system/status` 可用。
- admin auth 基础接口可用。
- WebSocket routing 可初始化。

### Phase C8：抽取管理命令

从旧项目复制：

```text
apps/core/management/commands/
```

第一批必须命令：

- `doctor`
- `install_forum`
- `upgrade_forum`
- `sync_extensions`
- `extension_enable`
- `extension_disable`
- `rebuild_extension_runtime`

如果命令名需要重命名，先保留旧命令兼容。

验收：

- `python manage.py doctor` 可运行。
- `python manage.py sync_extensions` 能发现本地测试扩展。
- `python manage.py migrate` 后核心状态正常。

### Phase C9：测试迁移

从旧项目复制核心测试：

```text
apps/core/tests/ -> tests/
```

优先迁移：

- `test_extension_boundary.py`
- `test_extension_validation.py`
- `test_extension_registry.py`
- `test_resource_registry.py`
- `test_settings_fallback.py`
- `test_admin_auth.py`
- `test_admin_dashboard.py`
- `test_health.py`
- `test_queue.py`
- `test_ws_auth.py`

测试分层：

```text
tests/unit/
tests/integration/
tests/fixtures/extensions/
```

验收：

- 核心测试稳定通过。
- 旧项目对应测试结果可对照。

### Phase C10：发布准备

补齐：

- README。
- API 边界文档。
- changelog。
- wheel build。
- GitHub Actions。
- import-linter 规则。

import-linter 规则：

```text
bias_core 不得 import 任何 bias_ext_* 包
扩展测试 fixture 不得 import bias_core 内部模块
```

验收：

- `python -m build` 成功。
- 新虚拟环境中安装 wheel 成功。
- 安装后测试最小 Django 项目成功。

## 五、bias-site 项目详细开发方案

### Phase S0：创建项目骨架

目录：

```text
bias-site/
├─ pyproject.toml
├─ manage.py
├─ config/
│  ├─ __init__.py
│  ├─ settings.py
│  ├─ urls.py
│  ├─ asgi.py
│  ├─ wsgi.py
│  └─ celery.py
├─ frontend/
├─ docker/
├─ scripts/
├─ instance/
├─ static/
├─ media/
├─ docker-compose.yml
├─ Dockerfile
├─ nginx.conf
└─ README.md
```

`pyproject.toml`：

```toml
[project]
name = "bias-site"
version = "0.1.0"
dependencies = [
  "bias-core>=0.1,<0.2"
]
```

本地开发先用 editable：

```bash
pip install -e ../bias-core
pip install -e .
```

### Phase S1：迁移 Django 配置

从旧项目复制：

```text
manage.py
config/settings.py
config/urls.py
config/asgi.py
config/wsgi.py
config/celery.py
```

改造目标：

```python
from bias_core.conf.bootstrap import load_site_bootstrap
from bias_core.conf.extension_discovery import (
    discover_installed_extension_django_apps,
    discover_extension_migration_modules,
)
```

替换路径：

```text
apps.core -> bias_core
apps.core.middleware.* -> bias_core.middleware.*
apps.core.test_runner.* -> bias_core.test_runner.*
apps.core.extensions.template_loader.* -> bias_core.extensions.template_loader.*
apps.core.api_runtime.* -> bias_core.api.runtime.*
apps.core.websocket_auth.* -> bias_core.realtime.websocket_auth.*
```

验收：

- `python manage.py check` 通过。
- `python manage.py migrate` 通过。
- `python manage.py doctor` 通过。

### Phase S2：最小站点启动

第一版网站工程只需要跑通：

- Django HTTP。
- `/api/system/status`。
- admin API 基础认证。
- core settings。
- core migration。
- 空扩展宿主。

暂不要求完整论坛业务可用，因为 users/discussions/posts 还没迁移为扩展。

验收：

```bash
python manage.py runserver
curl http://localhost:8000/api/system/status
```

### Phase S3：迁移前端宿主

从旧项目复制：

```text
frontend/
package.json
```

保留宿主应用：

- `frontend/src/App.vue`
- `frontend/src/main.js`
- `frontend/src/router`
- `frontend/src/components`
- `frontend/src/admin`
- `frontend/src/forum`
- `frontend/src/common`

但要标记边界：

```text
frontend/src/common/sdk.js   -> 未来 @bias/core/common
frontend/src/forum/sdk.js    -> 未来 @bias/core/forum
frontend/src/admin/sdk.js    -> 未来 @bias/core/admin
frontend/src/assets/main.css -> 需要逐步 token 化，避免主题只能覆盖内部选择器
其余页面和布局            -> bias-site 宿主内部
```

第一阶段不急着发布 `@bias/core`，但代码结构应按未来包边界整理。

同时预留主题宿主能力：

```text
frontend/src/theme/
├─ tokens.js          # 默认 design tokens
├─ themeRuntime.js    # 加载主题 manifest、应用 class 和 CSS
├─ themeSlots.js      # 主题可替换区域注册
└─ cssLayers.css      # 定义 base/components/theme/overrides layer
```

主题相关前端约束：

- 宿主基础样式使用 CSS variables。
- 主题 CSS 进入明确的 `theme` CSS layer。
- 页面结构不承诺给主题直接依赖。
- 只通过稳定 slot 暴露可替换区域。
- forum 和 admin 可以分别加载主题 CSS。

验收：

- `npm install`。
- `npm run build`。
- 空扩展前端 manifest 下页面能打开。
- 未安装主题时使用默认 tokens。

### Phase S4：建立 @bias/core 前端 SDK

两种选择：

方案 A：先在 `bias-site/frontend` 内维护。

```text
frontend/src/sdk/
├─ common/
├─ forum/
└─ admin/
```

方案 B：单独新建 `bias-frontend-sdk`。

```text
bias-frontend-sdk/
├─ package.json
├─ src/common
├─ src/forum
├─ src/admin
└─ dist
```

推荐：

- Phase S4 先用方案 A。
- 等第一个外部扩展跑通后，再切到方案 B。

`package.json` exports 目标：

```json
{
  "name": "@bias/core",
  "exports": {
    "./common": "./dist/common/index.js",
    "./forum": "./dist/forum/index.js",
    "./admin": "./dist/admin/index.js"
  }
}
```

验收：

- 内置测试扩展能 `import "@bias/core/forum"`。
- Vite alias/import map 能解析。
- 测试主题能 `import "@bias/core/forum"` 注册 theme variant 或 theme slot。

### Phase S5：扩展加载链路

网站工程需要实现：

```text
后端 extension registry
  -> frontend manifest API
  -> frontend host fetch manifest
  -> import extension entry
  -> call boot(app)
  -> load enabled theme css/tokens
```

从旧项目迁移：

```text
frontend/extensionImportMapPlugin.mjs
frontend/extensionSdkAliases.mjs
frontend/src/common/extensionRuntime.js
frontend/src/forum/extensionLoader.js
frontend/src/admin/extensionBootstrap.js
```

改造目标：

- 扩展前端只依赖 `@bias/core/*`。
- 宿主提供 import map。
- 扩展 bundle 不打包 Vue、Pinia、Vue Router、`@bias/core`。
- 主题 CSS 和普通扩展 JS 分开加载，避免主题失败影响普通扩展启动。

验收：

- 一个测试扩展的 forum entry 能被加载。
- 一个测试扩展的 admin page 能注册。
- 扩展加载失败不会拖垮整个页面。
- 一个 fixture theme 的 CSS 能被加载并应用到页面根节点。

### Phase S6：迁移部署脚本

从旧项目复制：

```text
Dockerfile
docker-compose.yml
nginx.conf
docker/entrypoint.sh
scripts/docker-install.*
scripts/docker-upgrade.*
```

改造：

- 后端镜像安装 `bias-core`。
- 前端 build 使用 `bias-site/frontend`。
- `doctor` 命令来自 `bias-core`。
- install/upgrade 流程支持包化扩展。

验收：

- `docker compose up -d --build`。
- `install_forum` 成功。
- `doctor` 成功。
- 前端页面可访问。

### Phase S7：主题扩展最小闭环

在真实业务扩展迁移前，建议做一个极小的 fixture theme，用来验证主题协议和宿主前端边界。

默认主题在第一阶段留在 `bias-site`，不单独做成扩展。原因是空网站工程需要一个不依赖扩展系统的基础外观和 fallback tokens。如果默认主题一开始就是扩展，那么 `bias-site` 的最小启动链路会被主题扩展安装、发现、manifest 生成和前端加载同时牵住，调试成本会变高。

但默认主题不能按“永远留在宿主内部”的方式写。它需要按未来可抽离为 `bias-theme-default` 的标准组织：

```text
frontend/src/theme/default/
├─ tokens.css
├─ forum.css
├─ admin.css
└─ slots.js
```

第一阶段默认主题职责：

- 提供无主题安装时的默认 tokens。
- 提供 forum/admin 基础样式。
- 定义主题 CSS layer 顺序。
- 提供 fixture theme 可以覆盖的稳定变量。

第一阶段默认主题不负责：

- 主题市场。
- 多主题切换 UI。
- 第三方主题配置页面。
- 大规模组件替换。

fixture theme 只需要：

```text
bias-theme-fixture/
├─ extension.json
├─ bias_theme_fixture/backend/ext.py
└─ frontend/dist/forum.css
```

`forum.css` 只改几个 CSS variables：

```css
:root.theme-fixture {
  --bias-color-primary: #2563eb;
  --bias-radius-card: 8px;
}
```

验收：

- `bias-site` 能安装 fixture theme。
- 后台能看到 theme 类型扩展。
- 启用后 frontend manifest 包含 theme CSS。
- 页面根节点应用 theme class。
- 禁用后恢复默认 tokens。

这个阶段不追求好看的主题，只验证第三方主题开发者未来不会被迫修改宿主源码。

## 六、旧项目扩展迁移策略

扩展迁移必须在 `bias-core` 和 `bias-site` 最小链路跑通后开始。

推荐顺序：

```text
1. users
2. posts
3. discussions
4. tags
5. notifications
6. uploads
7. likes
8. search
9. realtime
10. approval / flags / mentions / points / subscriptions / emoji / ai
```

原因：

- users 通常是 AUTH_USER_MODEL 和认证基础。
- posts/discussions 是论坛核心内容。
- tags/notifications/uploads 是常见依赖。
- search/realtime 依赖前面模型和事件。

每个扩展迁移步骤：

```text
1. 新建 bias-ext-xxx 项目
2. 复制旧 extensions/xxx/backend
3. 替换 import:
   apps.core.extensions.* -> bias_core.extensions.*
4. 复制前端 src
5. 替换前端 import:
   frontend/src/... 或 @bias/forum -> @bias/core/*
6. 添加 pyproject.toml
7. 添加 extension.json
8. 添加 entry point
9. 迁移 tests
10. 在 bias-site 中 pip install -e ../bias-ext-xxx
11. sync_extensions + migrate + frontend build
12. 和旧项目行为对照
```

每个扩展验收：

- 后端测试通过。
- 前端测试通过。
- 可安装。
- 可启用/禁用。
- 可迁移数据库。
- 可在管理后台看到。
- 和旧项目核心行为一致。

主题迁移策略：

- 旧项目如果已有站点级主题或外观配置，不直接放进 `bias-site` 内部。
- 先沉淀默认主题 tokens，作为 `bias-site` 默认外观和 fallback。
- 再把可替换外观能力抽象成 `bias-theme-*`。
- 官方默认主题第一阶段内置在 `bias-site`。
- 主题协议稳定后，再决定是否抽成官方 `bias-theme-default`。
- 即使默认主题暂时内置，也要按可抽离结构编写，避免后续抽包时重写样式体系。

## 七、关键技术决策

### 1. 第一版 bias-core 是否复制旧 apps/core 全部代码

建议：复制 core 相关代码，但不要复制具体扩展。

理由：

- `apps/core` 内部模块耦合较多，一开始强行精简风险高。
- 复制后再用测试收敛边界更稳。
- 具体扩展必须后续独立迁移，不能混进 core。

### 2. 第一版是否保留 Django app label

建议：使用：

```python
name = "bias_core"
label = "core"
```

理由：

- Python 路径是新路径。
- Django label 保持短且稳定。
- 未来数据迁移时可控。

### 3. 前端 SDK 是否马上独立

建议：不马上独立成仓。

先在 `bias-site/frontend` 内形成 `@bias/core` 的 exports/alias。等至少一个扩展迁移完成后，再抽成独立 npm 包。

主题 API 也按这个节奏处理。先在 `bias-site/frontend` 里实现 theme runtime 和 SDK 导出，等 fixture theme 与一个真实扩展都跑通后，再一起抽出 `@bias/core`。

### 4. 是否支持旧扩展路径

新项目里不鼓励支持：

```python
from apps.core.extensions import ...
```

但可以提供短期兼容包，帮助迁移旧扩展测试。新扩展模板必须只生成：

```python
from bias_core.extensions import ...
```

### 5. 是否先做完整功能再迁移扩展

不建议。

`bias-core` + `bias-site` 先跑空宿主，再迁移 users/discussions/posts 等扩展。这样能尽早验证拆分边界。

## 八、里程碑

### M1：bias-core 可安装

验收：

- `pip install -e ../bias-core`。
- `import bias_core`。
- `INSTALLED_APPS=["bias_core"]` 可 migrate。
- SDK 公共导入可用。

### M2：bias-core 可加载测试扩展

验收：

- 测试扩展可被发现。
- `extend()` 可执行。
- settings/permissions/routes/resources 可注册。

### M3：bias-site 空宿主可运行

验收：

- `python manage.py check`。
- `python manage.py migrate`。
- `/api/system/status`。
- 前端空页面可构建。

### M4：前端扩展加载跑通

验收：

- 测试扩展前端 forum entry 可加载。
- 测试扩展 admin page 可注册。
- `@bias/core/*` import 可解析。
- fixture theme CSS 可加载。
- 默认 tokens 和主题 tokens 可切换。

### M5：第一个真实扩展迁移成功

推荐 users。

验收：

- 用户模型、认证、登录注册相关接口可用。
- 旧项目对应行为对照通过。

### M6：核心论坛链路跑通

至少迁移：

- users
- posts
- discussions

验收：

- 创建讨论。
- 回复帖子。
- 浏览讨论列表。
- 基础权限可用。

### M7：达到替代旧项目的最小版本

至少迁移：

- users
- posts
- discussions
- tags
- notifications
- uploads
- search
- realtime

验收：

- Docker 部署成功。
- install/upgrade/doctor 成功。
- 主要前后台功能可用。

## 九、风险和控制

### 风险 1：core 和扩展边界不清

控制：

- `bias-core` 不允许 import `bias_ext_*`。
- 扩展不允许 import `bias_core` 内部模块。
- 用 import-linter 和扩展源码校验双重控制。

### 风险 2：一次性重构太多

控制：

- 先复制旧实现。
- 用测试对齐行为。
- 分阶段重命名和整理。

### 风险 3：前端 SDK 太早抽离导致反复改包

控制：

- 先在 `bias-site` 内形成稳定 exports。
- 至少迁移一个真实扩展后再独立 npm 包。

### 风险 4：Django migrations 和 app label 出问题

控制：

- 新项目从一开始固定 `label = "core"`。
- 扩展也固定 app label。
- 每个扩展独立迁移验证。

### 风险 5：旧项目和新项目行为不一致

控制：

- 迁移测试。
- 保留旧项目作为对照环境。
- 每个扩展迁移后做行为 checklist。

## 十、建议的第一周任务

1. 创建 `bias-core` 仓库和 `pyproject.toml`。
2. 抽 `apps.py`、`models.py`、`migrations`。
3. 搭一个最小 Django 测试 settings。
4. 跑通 `migrate`。
5. 抽 `extensions.__init__`、`sdk`、`contracts`、`types`、`extenders`。
6. 写 `test_sdk_exports.py`。
7. 抽最小 extension loader，跑通一个 fixture 扩展。
8. 创建 `bias-site` 骨架，editable 安装 `bias-core`。
9. 跑通 `python manage.py check`。
10. 整理第一批缺失依赖和路径替换清单。

## 十一、阶段性结论

这条路线的重点是把旧项目当成稳定样本，而不是在旧项目上做大手术。

开发顺序应该是：

```text
1. bias-core 后端核心包
2. bias-site 空网站工程
3. 前端 SDK 边界
4. 测试扩展
5. users 扩展
6. posts/discussions 扩展
7. 其他扩展逐个独立
```

拆分边界要坚持：

```text
bias-core 只做平台和 SDK
bias-site 只做组合、部署和宿主
bias-ext-* 只做具体业务能力
旧项目只做参考和迁移来源
```
