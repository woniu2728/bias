# Extension Cookbook

本页按常见需求给出可复制的扩展片段。普通扩展优先从这里开始，不需要先阅读 core 内部源码。

## 基础规则

后端只使用公开入口：

```python
from bias_core.extensions import ...
from bias_core.extensions.runtime import call_runtime_service, get_runtime_service, require_runtime_service
from bias_core.extensions.platform import ...
from bias_core.extensions.resources import ...
```

前端只使用公开 SDK：

```js
import { api } from '@bias/core'
import { extendForum } from '@bias/core/forum'
import { extendAdmin } from '@bias/core/admin'
import { AdminPage } from '@bias/core/components/admin'
```

不要直接 import `bias_core` 内部模块、其他扩展 Python 包、`frontend/src/*`、`vue`、`pinia` 或 `vue-router`。

## 增加设置项

`backend/settings.py`:

```python
from bias_core.extensions import SettingsExtender, setting_field


def settings_extender():
    return SettingsExtender(
        fields=[
            setting_field(
                key="enabled",
                label="Enabled",
                type="boolean",
                default=True,
                category="general",
            ),
        ],
    )
```

`backend/ext.py`:

```python
from .settings import settings_extender


def extend():
    return [settings_extender()]
```

适合用模板生成：

```powershell
python manage.py create_extension demo-settings --target D:\files\project\tmp --template settings
```

## 增加后台页面

`backend/ext.py`:

```python
from bias_core.extensions import AdminSurfaceExtender, PermissionDefinition


def extend():
    return [
        AdminSurfaceExtender(
            pages=[{
                "name": "demo-admin.overview",
                "path": "/admin/extensions/demo-admin/overview",
                "label": "Demo Admin",
                "permission": "demo-admin.view",
            }],
            permissions=[
                PermissionDefinition(
                    key="demo-admin.view",
                    label="View demo admin page",
                    category="extensions",
                ),
            ],
        ),
    ]
```

`frontend/admin/index.js`:

```js
import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'demo-admin.overview',
    path: '/admin/extensions/demo-admin/overview',
    label: 'Demo Admin',
    icon: 'fas fa-puzzle-piece',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
```

适合用模板生成：

```powershell
python manage.py create_extension demo-admin --target D:\files\project\tmp --template admin-page
```

## 增加前台 Widget

`frontend/forum/index.js`:

```js
import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.navItem({
    key: 'demo-widget',
    label: 'Demo',
    href: '/demo',
    icon: 'fas fa-puzzle-piece',
    section: 'primary',
    order: 1000,
  })),
]
```

适合用模板生成：

```powershell
python manage.py create_extension demo-widget --target D:\files\project\tmp --template forum-widget
```

## 增加资源字段

`backend/resources.py`:

```python
from bias_core.extensions import ApiResourceExtender, ResourceFieldDefinition


def resource_extender():
    return ApiResourceExtender(
        fields=[
            ResourceFieldDefinition(
                resource="discussion",
                name="demoBadge",
                module_id="demo-resource",
                description="Demo badge shown on discussion resources.",
                resolver=lambda discussion, context: "demo" if discussion else "",
            ),
        ],
    )
```

字段名必须稳定。高成本字段应补预加载或缓存，不要在 resolver 中循环查询数据库。

## 增加资源 Endpoint

`backend/responses.py`:

```python
from bias_core.extensions.resources import dispatch_resource_endpoint


def list_demo_items(request):
    return dispatch_resource_endpoint(
        request,
        resource="demo_item",
        data=[{"id": "demo", "type": "demo_item", "attributes": {"label": "Demo"}}],
    )
```

`backend/resources.py`:

```python
from bias_core.extensions import ApiResourceExtender, ResourceEndpointDefinition

from .responses import list_demo_items


def resource_extender():
    return ApiResourceExtender(
        endpoints=[
            ResourceEndpointDefinition(
                name="demo-items",
                path="/api/forum/demo-items",
                methods=["GET"],
                handler=list_demo_items,
            ),
        ],
    )
```

适合用模板生成：

```powershell
python manage.py create_extension demo-resource --target D:\files\project\tmp --template resource
```

## 监听事件

`backend/events.py`:

```python
from bias_core.extensions import EventListenersExtender, event_listener


def on_post_created(event):
    payload = event.payload or {}
    post_id = payload.get("post_id")
    if not post_id:
        return
    # Keep side effects small and idempotent.


def event_extender():
    return EventListenersExtender(
        listeners=[
            event_listener("posts.created", on_post_created),
        ],
    )
```

事件监听应幂等，避免在请求链路里做耗时工作。耗时任务优先投递队列。

## 调用其他扩展服务

```python
from bias_core.extensions.runtime import call_runtime_service, require_runtime_service


def resolve_author(user_id):
    return call_runtime_service("users.service", "get_user_by_id", user_id)


def create_post(payload):
    posts = require_runtime_service("posts.service")
    return posts.create(payload)
```

新代码不要新增 `get_runtime_*`、`create_runtime_*`、`list_runtime_*` 等 legacy facade import。迁移表见 [runtime-facade-migration.md](runtime-facade-migration.md)。

## 发布前检查

```powershell
python manage.py validate_extensions --extensions-path D:\files\project\tmp --require-extensions
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
python manage.py check_platform_release --extensions-path D:\files\project\tmp --skip-frontend --format json

cd D:\files\project\tmp\bias\frontend
npm run check:platform
```

`check_platform_release` 是后端发布聚合 gate；`npm run check:platform` 会检查前端扩展边界、SDK 包同步和 `@bias/core` 导出稳定性基线。
