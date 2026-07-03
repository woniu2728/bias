# Extension Advanced Guide

本页只覆盖高级扩展能力。普通设置、后台页面、前台 widget、资源字段和资源 endpoint 优先参考 [extension-cookbook.md](extension-cookbook.md)。

## Lifecycle

需要在安装、启用、停用或卸载时执行动作时，使用 `LifecycleExtender`。生命周期回调必须可重复执行，并且失败时返回清晰错误。

```python
from bias_core.extensions import LifecycleExtender


def on_enable(context):
    context.logger.info("demo extension enabled")


def lifecycle_extender():
    return LifecycleExtender(on_enable=on_enable)
```

不要在 module import 阶段执行数据库写入、网络请求或文件系统变更。生命周期动作由平台调度，并会被发布 gate 的 lifecycle smoke 覆盖。

## Realtime

实时能力用于广播已经发生的业务状态变化。事件 payload 应保持小而稳定，避免广播完整页面数据。

```python
from bias_core.extensions.forum import broadcast_realtime_event


def notify_changed(discussion_id):
    broadcast_realtime_event(
        "demo.changed",
        {"discussion_id": discussion_id},
        discussion_id=discussion_id,
    )
```

前端语义通过 forum SDK 声明：

```js
import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.realtimeEvent({
    type: 'demo.changed',
    action: 'refresh',
    surfaces: ['discussion'],
  })),
]
```

## Model Visibility

如果扩展拥有模型或需要参与可见性判断，优先声明可见性 extender，而不是让调用方直接 import 扩展模型。

```python
from bias_core.extensions import ModelVisibilityExtender


def can_view_demo(user, obj):
    return bool(user and user.is_authenticated)


def visibility_extender():
    return ModelVisibilityExtender(
        model_key="demo.item",
        can_view=can_view_demo,
    )
```

可见性规则应可组合，避免在其他扩展中硬编码业务判断。

## Search Index

搜索扩展应把索引定义集中在 search extender 中。新增可搜索内容时同时考虑索引字段、过滤器和重建命令。

```python
from bias_core.extensions import SearchIndexExtender


def search_index_extender():
    return SearchIndexExtender(
        indexes=[{
            "name": "demo-items",
            "resource": "demo_item",
            "fields": ["title", "body"],
        }],
    )
```

大批量重建不要放在请求链路中执行，应通过后台动作或管理命令触发。

## Custom Route

扩展前台页面通过 `FrontendExtender` 声明 route，再由前端入口提供组件。不要在宿主 router 中直接改代码。

```python
from bias_core.extensions import FrontendExtender


def frontend_extender():
    return FrontendExtender(
        forum_routes=[{
            "name": "demo.page",
            "path": "/demo",
            "component": "DemoPage",
        }],
    )
```

`frontend/forum/index.js`:

```js
import DemoPage from './DemoPage.vue'

export const components = {
  DemoPage,
}
```

## Package Audit

扩展发布前必须通过包审计。推荐命令：

```powershell
python manage.py inspect_extension_packages `
  --extensions-path D:\files\project\tmp `
  --require-extensions `
  --build `
  --install-smoke `
  --install-set-smoke `
  --migration-smoke `
  --lifecycle-smoke `
  --format json
```

关注字段：

- `summary.error_count`：包结构或构建错误。
- `summary.blocking_risk_count`：必须阻断发布。
- `upgrade_risk.summary.warning_risk_count`：允许发布但需要复核。
- `install_plan.executes_install`：计划说明，不代表已安装到站点。

## Frontend SDK Stability

`@bias/core` 的公开导出由 `frontend/sdk-export-baseline.json` 管理。每个导出必须标注：

- `stable`：可被扩展长期依赖。
- `experimental`：可试用，升级前需要复核。
- `internal`：只为兼容或过渡存在，不推荐新扩展使用。

新增 SDK 导出流程：

```powershell
cd frontend
npm run sync:sdk-package
node ./scripts/checkSdkExports.mjs --write --default-stability=experimental
npm run check:platform
```

提交前应人工确认新增导出的 stability 是否准确。`npm run check:sdk-package` 会阻断未进入基线或 stability 非法的导出。

## Platform Release Gate

站点级发布前使用：

```powershell
python manage.py check_platform_release --extensions-path D:\files\project\tmp --format json
```

该命令聚合：

- `check_extension_workspace`
- `inspect_extensions --fail-on-runtime-service-fallback`
- `inspect_extension_packages --build`
- `doctor`
- 前端 `npm run check:platform`

CI 应只读取稳定字段：

- `status`
- `blocking_count`
- `warning_count`
- `checks.<name>.status`
- `checks.<name>.blocking_count`
- `checks.<name>.issues`

本地缺少前端或运行时依赖时，可以用 `--skip-frontend` 或 `--skip-doctor` 缩小检查范围；正式发布不应跳过。

## Compatibility Policy

高级扩展必须在 manifest 中声明兼容策略：

```json
{
  "compatibility": {
    "bias_version": ">=0.1.0 <0.2.0",
    "api_version": "1.0",
    "api_stability": "experimental",
    "breaking_change_policy": "扩展协议调整会随 Bias 主版本升级同步说明。"
  }
}
```

`experimental` 和 `beta` 会作为升级风险提示；Bias 版本不兼容和依赖缺失会阻断发布。
