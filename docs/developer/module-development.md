# 扩展开发指南

> 扩展系统主线已单独整理为 [扩展系统路线图](./extension-system-roadmap.md)。
> 当前这份文档服务扩展开发；内置 registry 只作为核心能力的底层注册表。

## 目标

Bias 以扩展清单和 Extender 作为平台接入中心。新增可插拔能力时，先创建 `extensions/<id>/extension.json` 和后端 `extend()` 入口，再逐步接入权限、后台页、资源字段、事件和前端注入点。

扩展不只是“注册一组能力”，还必须具备统一生命周期、依赖、运行时诊断和交付资产信息，确保扩展中心、开发者文档和运行时诊断看到的是同一套协议。

## 标准生命周期

每个扩展默认遵循以下阶段：

1. `register`
   声明扩展元数据，并注册权限、后台页、通知类型、资源字段和搜索扩展。
2. `bootstrap`
   在前后端启动期挂接默认配置、事件监听、路由和前端注入点。
3. `ready`
   依赖与健康检查通过后，对外提供稳定能力。
4. `optional disable`
   当配置关闭、依赖缺失或健康检查不通过时，可显式停用模块能力。
5. `teardown`
   在卸载、实现切换或未来热更新场景中回收监听器、注入点和运行时资源。

当前内置核心能力默认是静态注册模式；文件系统扩展通过安装、启用、禁用和卸载生命周期接入。

## 基本步骤

1. 在 `extensions/<id>/extension.json` 声明扩展清单。
2. 在 `extensions/<id>/backend/ext.py` 返回 Extender 列表。
3. 在 `extensions/<package>/backend/apps.py` 声明扩展 AppConfig，并在 manifest 中写入 `django_app_config` 和 `django_app_label`。
4. 使用稳定的扩展 id 作为所有扩展能力的归属标识。
5. 只注册当前切片需要的能力，避免一次性过度铺开。
6. 需要前台扩展时，在扩展自己的 `frontend/forum/index.js` 或 `frontend/admin/index.js` 中挂接注入点。
7. 补扩展中心可见信息、开发者文档和测试，保证注册结果可见、可检验。

## 最小实现模板

```python
from apps.core.extensions import SettingsExtender

def extend():
    return [
        SettingsExtender().default("example.enabled", True),
    ]
```

## 接入清单

新增扩展时，按下面顺序检查：

1. 后端注册
   在 `extension.json` 中声明扩展、依赖、兼容性、分发信息、`django_app_config`、`django_app_label` 和生命周期操作。
2. 管理入口
   如有后台页，通过 `AdminSurfaceExtender` / `FrontendExtender` 声明，并在扩展前端入口导出对应组件。
3. 领域协议
   如有资源字段、事件监听、通知类型、帖子类型或搜索过滤器，统一通过 Extender 注册。
4. 模型与迁移
   如扩展拥有模型，必须使用 `ModelExtender().owns(...)` 声明归属；迁移文件放入 `backend/django_migrations`，并用 `inspect_extensions --extension-id <id>` 检查 `model_ownership_audit`。
5. 前端注入
   如需 header、discussion action、post action、composer extension、admin navigation、notification renderer，统一走扩展前端入口。
6. 禁用验收
   禁用扩展后，该扩展注册的后端 routes/resources/events、前端 routes/actions/registries 和后台入口都必须消失；core 只保留宿主 shell。
7. 文档
   至少说明扩展边界；如有单独说明页，可把 `documentation_url` 指向开发者文档页。
8. 测试
   至少覆盖扩展中心接口输出、注入点解析或对应注册导出。

## 最小原则

- 不直接把扩展信息硬写到后台页面。
- 不绕过 registry 直接改核心 service 暴露元数据。
- 不新增“只在某个页面可见”的私有扩展协议。
- 不把业务模型、迁移或测试继续放回旧 `apps/<module>` 结构。
- 扩展文档能放进开发者文档页时，优先复用统一入口。

## 与扩展系统的关系

Bias 已经以扩展系统作为新增可插拔能力的主线。

因此新增能力时，需要额外遵守：

1. 优先设计成独立扩展边界。
2. 不把新能力继续硬耦合进 `core` 大页面。
3. 所有新增后台入口、权限、事件、资源字段都必须保留清晰归属。
4. 如功能具有独立配置、独立依赖、独立运维价值，优先按未来扩展拆分。

详细路线见：

- [扩展系统路线图](./extension-system-roadmap.md)
