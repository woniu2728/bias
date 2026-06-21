# Bias 独立包拆分后架构设计

## 目标

拆分后的 Bias 不再把“网站工程、后端核心、前端扩展 SDK、内置扩展”都绑定在同一个运行边界里，而是形成四类清晰产物：

```text
Bias 网站工程
├─ bias-core        # Python 包，后端核心平台
├─ @bias/core       # npm 包，前端扩展 SDK
├─ bias-ext-*       # Python/npm 扩展包，内置扩展和第三方扩展同形态
└─ site project     # 站点配置、部署、主题、前端宿主壳
```

核心目标不是为了拆而拆，而是让第三方扩展能稳定依赖公共 API，并让网站工程只负责组合和部署。

## 一、拆分后的整个网站架构

### 1. 总体分层

```text
┌────────────────────────────────────────────────────────────┐
│                     Bias Site Project                      │
│  config / deployment / env / frontend host / installed ext │
└───────────────┬──────────────────────────────┬─────────────┘
                │                              │
                │ Python dependency            │ npm dependency
                ▼                              ▼
┌─────────────────────────────┐      ┌────────────────────────┐
│          bias-core           │      │       @bias/core        │
│ Django app + extension host  │      │ frontend extension SDK  │
│ resource API + runtime       │      │ forum/admin/common APIs │
└───────────────┬─────────────┘      └───────────┬────────────┘
                │                                │
                │ loads backend ext              │ imported by frontend ext
                ▼                                ▼
┌────────────────────────────────────────────────────────────┐
│                        Extensions                          │
│ bias-ext-users / bias-ext-discussions / third-party-ext    │
│ backend: Python package, frontend: JS bundle or source     │
└────────────────────────────────────────────────────────────┘
```

### 2. 网站工程职责

网站工程是最终部署物，保留以下内容：

- `config/`：Django settings、urls、asgi、wsgi、celery entrypoint。
- `frontend/`：论坛和后台宿主应用壳，负责页面框架、路由容器、扩展前端加载。
- `docker-compose.yml`、`Dockerfile`、`nginx.conf`、安装升级脚本。
- `.env`、`instance/site.json`、媒体文件、静态文件、运行日志。
- 已安装扩展清单与本地扩展目录。

网站工程不再承载后端核心实现。它只把 `bias-core` 加入 `INSTALLED_APPS`，调用 core 提供的 API 构建器、扩展发现器和默认配置工具。

示例：

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "ninja_extra",
    "ninja_jwt",
    "corsheaders",
    "channels",
    "bias_core",
    *discover_installed_extension_django_apps(),
]
```

### 3. 后端运行时关系

```text
HTTP / WebSocket request
        │
        ▼
site config.urls / asgi
        │
        ▼
bias_core.api_runtime / websocket routing
        │
        ▼
bias_core extension host
        │
        ├─ core services
        ├─ resource registry
        ├─ permission / policy runtime
        ├─ settings / audit / queue / storage
        └─ installed extensions
```

`bias-core` 负责提供后端平台能力，网站工程只负责把它挂到 Django 项目里。

### 4. 前端运行时关系

```text
Browser
  │
  ▼
Bias frontend host
  │
  ├─ Vue app shell
  ├─ router / layout / state containers
  ├─ extension manifest loader
  ├─ import map / module federation adapter
  └─ @bias/core runtime providers
          │
          ▼
      extension frontend bundles
```

前端拆分的重点是 SDK，而不是立刻把完整宿主应用拆包。

推荐 npm 包：

```text
@bias/core
├─ common      # 通用模型、资源、注册表、扩展运行工具
├─ forum       # 前台论坛扩展 SDK
├─ admin       # 后台管理扩展 SDK
└─ components  # 少量稳定公共组件，谨慎开放
```

第三方前端扩展只允许依赖 `@bias/core` 的公开入口，不直接 import 宿主内部文件。

示例：

```js
import { registerForumRoute } from "@bias/core/forum"
import { registerAdminPage } from "@bias/core/admin"
```

### 5. 扩展包形态

扩展应逐步从“仓库内目录”过渡为可安装包。

```text
bias-ext-example/
├─ pyproject.toml
├─ extension.json
├─ bias_ext_example/
│  └─ backend/
│     ├─ apps.py
│     ├─ ext.py
│     ├─ models.py
│     └─ django_migrations/
└─ frontend/
   ├─ package.json
   ├─ src/
   └─ dist/
```

后端依赖：

```toml
[project]
dependencies = ["bias-core>=0.1,<0.2"]
```

前端依赖：

```json
{
  "peerDependencies": {
    "@bias/core": ">=0.1 <0.2",
    "vue": "^3.0.0"
  }
}
```

### 6. 安装和发现机制

扩展来源分三类：

- `builtin`：官方内置扩展，也以包形态安装。
- `package`：通过 pip/npm 安装的第三方扩展。
- `local`：站点本地开发扩展。

后端推荐使用 Python entry points 发现扩展：

```toml
[project.entry-points."bias.extensions"]
example = "bias_ext_example.backend.ext:extend"
```

前端推荐由后端扩展清单暴露 frontend manifest，宿主前端根据 manifest 加载 bundle。

```json
{
  "id": "example",
  "version": "0.1.0",
  "frontend": {
    "forum": "dist/forum/index.js",
    "admin": "dist/admin/index.js"
  }
}
```

### 7. 主题扩展形态

主题应作为扩展的一种特殊类型支持，而不是作为网站工程里的静态目录。原因是第三方主题开发者需要和普通扩展一样获得可安装、可启用、可禁用、可升级的开发体验。

推荐包名：

```text
bias-theme-*
```

推荐结构：

```text
bias-theme-acme/
├─ pyproject.toml
├─ extension.json
├─ bias_theme_acme/
│  └─ backend/
│     ├─ __init__.py
│     └─ ext.py
└─ frontend/
   ├─ package.json
   ├─ src/
   │  ├─ forum.css
   │  ├─ admin.css
   │  ├─ theme.js
   │  └─ assets/
   └─ dist/
```

主题扩展允许提供：

- design tokens：颜色、字号、间距、圆角、阴影、边框、布局密度。
- CSS assets：forum/admin CSS、字体、图片、图标。
- theme settings：主题自定义配置。
- registered surfaces：通过稳定 slot 替换或增强局部区域。
- optional components：只替换 core 明确开放的组件。

主题扩展不允许直接依赖宿主前端内部 Vue 文件或内部 CSS 结构。主题能力必须基于稳定 token、CSS layer、slot 和公开前端 SDK。

`extension.json` 示例：

```json
{
  "id": "acme-theme",
  "type": "theme",
  "name": "Acme Theme",
  "version": "0.1.0",
  "bias": {
    "core": ">=0.3.0 <0.4.0",
    "frontend": ">=0.3.0 <0.4.0"
  },
  "theme": {
    "kind": "primary",
    "forumCss": "frontend/dist/forum.css",
    "adminCss": "frontend/dist/admin.css",
    "entry": "frontend/dist/theme.js"
  }
}
```

后端声明示例：

```python
from bias_core.extensions import ThemeExtender


def extend():
    return [
        ThemeExtender(
            id="acme-theme",
            name="Acme Theme",
            forum_css="frontend/dist/forum.css",
            admin_css="frontend/dist/admin.css",
            css_variables={
                "--bias-color-primary": "#2563eb",
                "--bias-radius-card": "8px",
            },
        )
    ]
```

主题运行规则建议：

- 同一站点同一时间只能启用一个 primary theme。
- 可以同时启用多个 appearance extension，例如代码高亮、字体包、小型装饰包。
- `bias-core` 负责主题注册、启停、设置、manifest 暴露和兼容校验。
- `bias-site` 前端宿主负责加载 CSS、应用 theme class、注入 design tokens。
- `@bias/core` 提供主题前端 API，例如注册 theme variant 或 slot component。

默认主题建议分阶段处理：

- 第一阶段默认主题留在 `bias-site`，作为宿主基础外观、默认 design tokens 和无主题安装时的 fallback。
- 第一阶段不要求 `bias-site` 必须安装一个 `bias-theme-default` 才能运行，避免空站点启动链路依赖主题扩展系统。
- 主题协议稳定后，可以把默认主题抽成官方扩展 `bias-theme-default`。
- 即使默认主题初期内置在 `bias-site`，它也必须按未来主题扩展的边界编写：使用 CSS variables、CSS layer、theme slots，不依赖一次性写死的内部覆盖规则。

拆分时需要提前预留主题边界。即使第一版不迁移具体主题，也应保证宿主前端的基础样式由 token 和 CSS layer 驱动，避免后续主题只能通过覆盖内部选择器实现。

### 8. 版本关系

后端 Python 包和前端 npm SDK 版本应保持同一主版本和次版本：

```text
bias-core==0.3.0
@bias/core@0.3.0
```

扩展声明兼容范围：

```json
{
  "bias": {
    "core": ">=0.3.0 <0.4.0",
    "frontend": ">=0.3.0 <0.4.0"
  }
}
```

公共 API 只在 minor 版本增加能力，不在 minor 版本破坏兼容。破坏性变更进入下一个 major。

## 二、bias-core 包架构

### 1. 包定位

`bias-core` 是后端核心平台包，不是纯 SDK。

它包含：

- Django app。
- 数据模型和迁移。
- API 构建器。
- 扩展宿主和扩展 SDK。
- 资源注册和 JSON:API 运行时。
- 权限、策略、可见性、设置、审计、队列、存储、邮件、Markdown 等平台服务。
- 管理命令。

它不包含：

- 具体站点的 `config/settings.py`。
- Docker 部署配置。
- 完整 Vue 宿主应用。
- 具体业务扩展实现。

### 2. 推荐目录结构

长期目标结构：

```text
bias_core/
├─ __init__.py
├─ apps.py
├─ models.py
├─ migrations/
├─ api/
│  ├─ runtime.py
│  ├─ routers.py
│  ├─ errors.py
│  └─ auth.py
├─ conf/
│  ├─ bootstrap.py
│  ├─ defaults.py
│  └─ extension_discovery.py
├─ extensions/
│  ├─ __init__.py
│  ├─ sdk.py
│  ├─ contracts.py
│  ├─ runtime.py
│  ├─ platform.py
│  ├─ forum.py
│  ├─ extenders.py
│  ├─ validation.py
│  ├─ host.py
│  ├─ registry.py
│  ├─ lifecycle.py
│  └─ internal/
├─ resources/
│  ├─ registry.py
│  ├─ serializer.py
│  ├─ dispatcher.py
│  ├─ validation.py
│  └─ search.py
├─ services/
│  ├─ settings.py
│  ├─ audit.py
│  ├─ authorization.py
│  ├─ visibility.py
│  ├─ queue.py
│  ├─ storage.py
│  ├─ email.py
│  └─ markdown.py
├─ realtime/
│  ├─ routing.py
│  ├─ websocket_auth.py
│  └─ online.py
├─ management/
│  └─ commands/
├─ middleware.py
├─ test_runner.py
└─ version.py
```

过渡期可以保留当前 `apps.core` 实现路径，并新增 `bias_core` 门面包：

```text
bias_core/
├─ __init__.py
├─ extensions/
│  ├─ __init__.py       # re-export apps.core.extensions
│  ├─ runtime.py        # re-export apps.core.extensions.runtime
│  ├─ platform.py       # re-export apps.core.extensions.platform
│  ├─ forum.py          # re-export apps.core.extensions.forum
│  ├─ contracts.py      # re-export apps.core.extensions.contracts
│  └─ sdk.py            # re-export apps.core.extensions.sdk
└─ compat/
```

这样可以先建立公共依赖路径，再迁移内部实现。

### 3. 公共 API 边界

第三方扩展允许导入：

```text
bias_core.extensions
bias_core.extensions.runtime
bias_core.extensions.platform
bias_core.extensions.forum
bias_core.extensions.contracts
bias_core.extensions.sdk
```

第三方扩展禁止导入：

```text
bias_core.models
bias_core.resources.*
bias_core.services.*
bias_core.extensions.internal.*
bias_core.extensions.registry
bias_core.extensions.host
```

如果扩展需要能力，必须通过 `runtime`、`platform`、`forum` 三类门面暴露。

### 4. extensions 子系统结构

```text
bias_core.extensions
├─ __init__        # 声明式 Extender 和 definition helper
├─ sdk             # helper function、definition aliases
├─ contracts       # 类型和定义类
├─ runtime         # 面向扩展的业务运行时能力
├─ platform        # 面向扩展的平台服务能力
├─ forum           # 面向扩展的论坛宿主能力
├─ validation      # 扩展清单和源码校验
├─ lifecycle       # 启停、安装、卸载、缓存失效
├─ registry        # 内部扩展注册表，不对第三方公开
└─ internal        # 内部实现
```

三个主要门面职责：

```text
runtime:
  用户、帖子、讨论、标签、通知、搜索、审核等运行时模型和领域操作。

platform:
  API 错误、鉴权、分页、资源查询、设置、队列、存储、邮件、Markdown、领域事件、策略判断。

forum:
  论坛宿主注册表、实时广播、在线用户、搜索索引、审计记录、上传 schema、数据库辅助工具。
```

### 5. Django app 和迁移策略

最稳策略是分两阶段。

第一阶段：

- wheel 中继续包含 `apps.core`。
- `bias_core` 只是公共门面。
- Django `INSTALLED_APPS` 仍可使用 `"apps.core"`。
- migrations 不移动。

第二阶段：

- 物理迁移到 `bias_core`。
- `CoreConfig.name = "bias_core"`。
- `CoreConfig.label` 固定为稳定 label，例如 `"core"`。
- 提供迁移路径和兼容检查。

迁移阶段必须重点验证：

- 旧数据库 `django_migrations` 记录能否识别。
- `contenttypes` app label 是否稳定。
- 权限 codename 是否稳定。
- 旧配置里的 middleware/template loader/test runner 字符串是否有兼容路径。

### 6. 配置模块设计

`bias-core` 提供配置工具，不接管站点 settings。

```text
bias_core.conf.bootstrap
  load_site_bootstrap()
  validate_site_bootstrap()

bias_core.conf.defaults
  default middleware
  default installed apps
  default cache/channel/celery helpers

bias_core.conf.extension_discovery
  discover_installed_extension_django_apps()
  discover_extension_migration_modules()
```

网站工程仍然拥有最终 settings：

```python
from bias_core.conf.bootstrap import load_site_bootstrap
from bias_core.conf.extension_discovery import (
    discover_installed_extension_django_apps,
    discover_extension_migration_modules,
)
```

### 7. API 和资源层设计

```text
bias_core.api
  build_api_application()
  core routers
  admin routers
  auth integration

bias_core.resources
  resource registry
  resource definitions
  endpoint dispatcher
  JSON:API serializer
  filter/sort/include parser
  visibility and policy integration
```

扩展不能直接操作内部 resource registry。扩展通过 `ApiResourceExtender`、`ResourceDefinition`、`ResourceEndpointDefinition` 等公共定义注册资源。

### 8. 前端 SDK 包架构

`@bias/core` 是独立 npm 包，和 `bias-core` 同版本节奏。

推荐结构：

```text
packages/bias-core-frontend/
├─ package.json
├─ src/
│  ├─ common/
│  │  ├─ sdk.js
│  │  ├─ resourceModels.js
│  │  ├─ routeRegistry.js
│  │  └─ contributionRegistry.js
│  ├─ forum/
│  │  ├─ sdk.js
│  │  ├─ registry.js
│  │  └─ extensionRuntime.js
│  ├─ admin/
│  │  ├─ sdk.js
│  │  ├─ registry.js
│  │  └─ componentsSdk.js
│  └─ components/
├─ dist/
└─ types/
```

`package.json` exports：

```json
{
  "name": "@bias/core",
  "exports": {
    "./common": "./dist/common/index.js",
    "./forum": "./dist/forum/index.js",
    "./admin": "./dist/admin/index.js",
    "./components/admin": "./dist/components/admin.js"
  },
  "peerDependencies": {
    "vue": "^3.0.0",
    "pinia": "^2.0.0",
    "vue-router": "^4.0.0"
  }
}
```

### 9. 发布产物

```text
Python:
  bias-core
  bias-ext-users
  bias-ext-discussions
  bias-ext-posts
  bias-ext-tags

npm:
  @bias/core
  optional: @bias/ext-users-frontend
  optional: @bias/ext-discussions-frontend
```

内置扩展可以先继续随网站仓库发布，等 core 包稳定后再逐个包化。

### 10. 推荐迁移路线

#### Phase 1：建立公共门面

- 新建 `bias_core` Python 门面包。
- 新建 `@bias/core` npm SDK 包或正规化当前 `@bias/forum`。
- 公共 API 测试覆盖导出符号。
- 扩展校验白名单允许新旧两套导入。

#### Phase 2：单仓库包化

- 在当前仓库或新 core 仓库中加入 `pyproject.toml`。
- wheel 包含当前 core 实现。
- 网站工程通过 editable install 接入。
- CI 验证 wheel 安装、Django check、核心测试。

#### Phase 3：内置扩展迁移

- 扩展生产代码改用 `bias_core.extensions.*`。
- 前端扩展改用 `@bias/core/*`。
- 生成扩展模板默认使用新导入路径。
- 文档全部改为新 SDK。

#### Phase 4：扩展包化

- 内置扩展逐个变成 `bias-ext-*`。
- 后端通过 entry points 发现。
- 前端通过 manifest 加载。
- 网站工程只声明安装哪些扩展。

#### Phase 5：物理迁移 core

- 将 `apps.core` 内部实现迁移到 `bias_core`。
- 保留 `apps.core` 兼容导入一个大版本。
- 完成 migrations、contenttypes、middleware 字符串路径兼容验证。

## 三、最终依赖方向

允许的依赖方向：

```text
site project -> bias-core
site project -> @bias/core
site project -> extensions
extensions backend -> bias_core.extensions.*
extensions frontend -> @bias/core/*
bias-core -> Django / Ninja / Channels / Celery / Redis
@bias/core -> Vue / Pinia / Vue Router as peer dependencies
```

禁止的依赖方向：

```text
bias-core -> site project
bias-core -> concrete extensions
extensions -> bias_core internal modules
extensions frontend -> frontend host internal files
@bias/core -> site project
```

## 四、架构判断

拆分后的核心不是“把目录换个名字”，而是建立两个稳定 SDK：

- 后端：`bias_core.extensions.*`
- 前端：`@bias/core/*`

网站工程继续作为宿主负责组合、部署和运行。`bias-core` 负责后端平台能力，`@bias/core` 负责前端扩展 API，扩展包只依赖公开 SDK。这样拆分后，官方内置扩展和第三方扩展可以采用同一套开发、安装、校验和运行机制。
