# Bias 拆分后的扩展开发形式

## 目标

拆分后，扩展开发者不需要理解 Bias 网站工程内部结构，也不需要从仓库内部 import `apps.core.*`。扩展只依赖两个稳定 SDK：

```text
后端扩展 -> bias_core.extensions.*
前端扩展 -> @bias/core/*
```

理想体验是：

```bash
bias extension create acme-badges
cd acme-badges
pip install -e .
npm install
bias extension link .
```

然后扩展即可在本地 Bias 站点里热加载或重启后加载。

## 一、扩展项目形态

### 1. 最小后端扩展

只写后端能力时，目录可以很小：

```text
acme-badges/
├─ pyproject.toml
├─ extension.json
└─ acme_badges/
   ├─ __init__.py
   └─ backend/
      ├─ __init__.py
      └─ ext.py
```

`pyproject.toml`：

```toml
[project]
name = "bias-ext-acme-badges"
version = "0.1.0"
dependencies = [
  "bias-core>=0.3,<0.4"
]

[project.entry-points."bias.extensions"]
acme_badges = "acme_badges.backend.ext:extend"
```

`extension.json`：

```json
{
  "id": "acme-badges",
  "name": "Acme Badges",
  "version": "0.1.0",
  "bias": {
    "core": ">=0.3.0 <0.4.0",
    "frontend": ">=0.3.0 <0.4.0"
  },
  "backend": {
    "entry": "acme_badges.backend.ext:extend"
  }
}
```

`acme_badges/backend/ext.py`：

```python
from bias_core.extensions import SettingsExtender, setting_field


def extend():
    return [
        SettingsExtender(
            fields=[
                setting_field(
                    key="acme_badges.enabled",
                    type="boolean",
                    label="Enable badges",
                    default=True,
                )
            ]
        )
    ]
```

### 2. 带前端的完整扩展

如果扩展同时有后端和前端，推荐结构：

```text
acme-badges/
├─ pyproject.toml
├─ extension.json
├─ acme_badges/
│  ├─ __init__.py
│  └─ backend/
│     ├─ __init__.py
│     ├─ apps.py
│     ├─ ext.py
│     ├─ models.py
│     ├─ resources.py
│     ├─ handlers.py
│     └─ django_migrations/
│        └─ __init__.py
└─ frontend/
   ├─ package.json
   ├─ vite.config.js
   ├─ src/
   │  ├─ forum/
   │  │  ├─ index.js
   │  │  └─ BadgeList.vue
   │  └─ admin/
   │     ├─ index.js
   │     └─ BadgesSettingsPage.vue
   └─ dist/
```

这种形式和普通 Python/npm 项目接近，扩展作者可以独立开发、测试、发布。

## 二、后端开发入口

### 1. 声明扩展能力

后端统一从 `extend()` 返回 Extender：

```python
from bias_core.extensions import (
    ApiRoutesExtender,
    FrontendExtender,
    PermissionDefinition,
    ForumPermissionExtender,
    SettingsExtender,
    setting_field,
)

from .handlers import router


def extend():
    return [
        SettingsExtender(
            fields=[
                setting_field(
                    key="acme_badges.max_badges",
                    type="number",
                    label="Max badges per user",
                    default=5,
                )
            ]
        ),
        ForumPermissionExtender(
            permissions=[
                PermissionDefinition(
                    code="acme_badges.manage",
                    label="Manage badges",
                )
            ]
        ),
        ApiRoutesExtender(
            routes=[
                {
                    "path": "/acme-badges",
                    "router": router,
                }
            ]
        ),
        FrontendExtender(
            forum_entry="frontend/dist/forum/index.js",
            admin_entry="frontend/dist/admin/index.js",
        ),
    ]
```

扩展作者不需要接触 core 内部 registry。所有能力通过 Extender 声明。

### 2. 使用平台能力

通用平台能力从 `bias_core.extensions.platform` 获取：

```python
from bias_core.extensions.platform import (
    AccessTokenAuth,
    PaginationService,
    api_error,
    get_extension_settings,
    require_staff,
)
```

论坛运行时能力从 `bias_core.extensions.runtime` 获取：

```python
from bias_core.extensions.runtime import (
    get_runtime_user_by_id,
    get_runtime_resource_registry,
    notify_runtime_notification,
)
```

论坛宿主能力从 `bias_core.extensions.forum` 获取：

```python
from bias_core.extensions.forum import (
    get_forum_registry,
    broadcast_realtime_discussion_event,
)
```

开发者只需要记住三类入口：

```text
bias_core.extensions          # 声明能力
bias_core.extensions.platform # 平台工具
bias_core.extensions.runtime  # 运行时领域能力
bias_core.extensions.forum    # 论坛宿主能力
```

### 3. 写 API

```python
from ninja import Router

from bias_core.extensions.platform import AccessTokenAuth, api_error
from bias_core.extensions.runtime import get_runtime_user_by_id

router = Router(tags=["acme-badges"])


@router.get("/users/{user_id}/badges", auth=AccessTokenAuth())
def list_user_badges(request, user_id: int):
    user = get_runtime_user_by_id(user_id)
    if user is None:
        return api_error("user_not_found", "User not found", status=404)

    return {
        "data": [],
    }
```

### 4. 写资源

资源型扩展通过 `ApiResourceExtender` 和 resource definition 声明，而不是直接操作内部 resource registry。

```python
from bias_core.extensions import (
    ApiResourceExtender,
    ResourceDefinition,
    ResourceFieldDefinition,
)


def extend():
    return [
        ApiResourceExtender(
            resources=[
                ResourceDefinition(
                    type="badges",
                    model="acme_badges.Badge",
                    fields=[
                        ResourceFieldDefinition(name="name"),
                        ResourceFieldDefinition(name="color"),
                    ],
                )
            ]
        )
    ]
```

### 5. 写模型和迁移

有数据库模型时，扩展提供自己的 Django app：

```python
from django.apps import AppConfig


class AcmeBadgesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "acme_badges.backend"
    label = "acme_badges"
```

`extension.json`：

```json
{
  "django": {
    "app_config": "acme_badges.backend.apps.AcmeBadgesConfig"
  }
}
```

站点安装扩展后，Bias 会把扩展 Django app 加入 `INSTALLED_APPS` 并发现迁移。

## 三、前端开发入口

### 1. forum 入口

`frontend/src/forum/index.js`：

```js
import { registerDiscussionSidebarSection } from "@bias/core/forum"
import BadgeList from "./BadgeList.vue"

export function boot(app) {
  registerDiscussionSidebarSection(app, {
    id: "acme-badges.badges",
    component: BadgeList,
    priority: 60,
  })
}
```

### 2. admin 入口

`frontend/src/admin/index.js`：

```js
import { registerAdminPage } from "@bias/core/admin"
import BadgesSettingsPage from "./BadgesSettingsPage.vue"

export function boot(app) {
  registerAdminPage(app, {
    id: "acme-badges.settings",
    path: "/extensions/acme-badges",
    title: "Badges",
    component: BadgesSettingsPage,
  })
}
```

### 3. package.json

```json
{
  "name": "@acme/bias-badges-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite build --watch",
    "build": "vite build"
  },
  "peerDependencies": {
    "@bias/core": ">=0.3 <0.4",
    "vue": "^3.0.0",
    "pinia": "^2.0.0",
    "vue-router": "^4.0.0"
  },
  "devDependencies": {
    "@bias/core": "file:../path-to-bias-core-frontend",
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

### 4. Vite external

扩展 bundle 不应打包宿主提供的 SDK 和 Vue：

```js
export default {
  build: {
    lib: {
      entry: {
        forum: "src/forum/index.js",
        admin: "src/admin/index.js"
      },
      formats: ["es"]
    },
    rollupOptions: {
      external: [
        "vue",
        "pinia",
        "vue-router",
        "@bias/core/common",
        "@bias/core/forum",
        "@bias/core/admin"
      ]
    }
  }
}
```

宿主前端通过 import map 或运行时 alias 提供这些依赖。

## 四、本地开发体验

### 1. 创建扩展

```bash
bias extension create acme-badges --with-frontend --with-models
```

生成：

```text
acme-badges/
├─ pyproject.toml
├─ extension.json
├─ acme_badges/backend/ext.py
└─ frontend/src/forum/index.js
```

### 2. 链接到本地站点

```bash
cd acme-badges
pip install -e .
bias extension link .
```

`link` 做的事情：

- 记录本地扩展路径。
- 校验 `extension.json`。
- 检查 `bias-core` 和 `@bias/core` 版本兼容。
- 如果有 Django app，加入扩展发现结果。
- 如果有前端入口，加入前端 manifest。

### 3. 启动开发

后端：

```bash
python manage.py sync_extensions
python manage.py migrate
python manage.py runserver
```

前端：

```bash
cd frontend
npm install
npm run dev
```

扩展前端：

```bash
cd acme-badges/frontend
npm install
npm run dev
```

### 4. 调试循环

后端 Python 代码：

- editable install 后直接改源码。
- Django runserver 自动重载。
- 修改 models 后生成/执行迁移。

前端代码：

- 扩展 Vite watch 输出 dist。
- 宿主前端检测 manifest 或 dist mtime。
- 页面刷新后加载最新 bundle。

扩展清单或 Extender 变更：

```bash
python manage.py sync_extensions
python manage.py rebuild_extension_runtime
```

## 五、发布形式

### 1. 纯后端扩展

```bash
python -m build
twine upload dist/*
```

用户安装：

```bash
pip install bias-ext-acme-badges
python manage.py sync_extensions
python manage.py migrate
```

### 2. 带前端扩展

发布前先构建前端：

```bash
cd frontend
npm run build
cd ..
python -m build
```

前端 dist 随 Python wheel 一起发布，适合普通扩展。

如果扩展前端较大，也可以拆成 npm 包，但第一阶段不建议强制这样做。对开发者来说，一个 Python 包同时包含后端和已构建前端 dist 更简单。

### 3. 安装体验

```bash
pip install bias-ext-acme-badges
python manage.py extension install acme-badges
python manage.py migrate
python manage.py collectstatic
```

管理后台也可以提供图形化安装：

```text
Extensions -> Install package -> bias-ext-acme-badges -> Enable
```

## 六、开发者需要理解的概念

最少概念：

```text
extension.json    # 扩展元信息和兼容声明
extend()          # 后端能力声明入口
Extender          # 设置、权限、API、前端、资源等能力声明
@bias/core        # 前端扩展 SDK
bias_core         # 后端扩展 SDK
```

不需要理解：

```text
core 内部 registry 怎么实现
resource dispatcher 怎么实现
extension host 怎么启动
前端宿主如何拼 import map
Django settings 如何组合所有扩展
```

## 七、和当前项目开发方式对比

当前方式：

```python
from apps.core.extensions import SettingsExtender
```

拆分后：

```python
from bias_core.extensions import SettingsExtender
```

当前方式的问题：

- 扩展看起来依赖项目内部目录。
- 第三方扩展无法自然声明 PyPI 依赖。
- 扩展作者容易误 import `apps.core` 内部模块。
- 前端扩展容易依赖宿主内部文件。

拆分后的改善：

- 后端只依赖 `bias-core`。
- 前端只依赖 `@bias/core`。
- 官方扩展和第三方扩展同形态。
- 能通过包版本声明兼容范围。
- 能用模板、校验器和 CI 保护公共 API 边界。

## 八、是否容易开发

如果模板和命令补齐，扩展开发应当比较直接：

```bash
bias extension create my-ext --with-frontend
cd my-ext
pip install -e .
npm install
bias extension link .
npm run dev
```

后端写 `extend()`，前端写 `boot(app)`，其他由 Bias 负责发现、校验、加载。

真正影响易用性的不是拆包本身，而是三件事：

- 公共 SDK 是否稳定且足够覆盖常见能力。
- 扩展模板是否能生成可运行项目。
- 本地 link、watch、sync、migrate 是否顺滑。

因此拆分时应优先做开发工具和模板，而不是只迁移目录。
