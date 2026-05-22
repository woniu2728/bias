# 模块开发指南

## 目标

Bias 以内置 registry 作为平台收口中心。新增模块时，先声明 `ForumModuleDefinition`，再逐步接入权限、后台页、资源字段、事件和前端注入点。

阶段 E 后，模块不再只是“注册一组能力”，而是必须具备统一生命周期定义，确保模块中心、开发者文档和运行时诊断看到的是同一套协议。

## 标准生命周期

每个模块默认遵循以下阶段：

1. `register`
   声明模块元数据，并注册权限、后台页、通知类型、资源字段和搜索扩展。
2. `bootstrap`
   在前后端启动期挂接默认配置、事件监听、路由和前端注入点。
3. `ready`
   依赖与健康检查通过后，对外提供稳定能力。
4. `optional disable`
   当配置关闭、依赖缺失或健康检查不通过时，可显式停用模块能力。
5. `teardown`
   在卸载、实现切换或未来热更新场景中回收监听器、注入点和运行时资源。

当前内置模块默认是静态注册模式，因此 `disable` / `teardown` 先以协议位存在，后续按能力逐步落地，不要求所有模块立刻实现真实热插拔。

## 基本步骤

1. 在 `apps/core/forum_registry_builtin.py` 增加 `ForumModuleDefinition`。
2. 使用稳定的 `module_id` 作为所有扩展能力的归属标识。
3. 根据模块实际情况补 `capabilities`、`settings_groups`、`documentation_url` 和 `lifecycle`。
4. 只注册当前切片需要的能力，避免一次性过度铺开。
5. 需要前台扩展时，再进入 `frontend/src/forum/registry.js` 或对应 bootstrap 文件挂接注入点。
6. 补后台模块中心、开发者文档和测试，保证注册结果可见、可检验。

## 最小实现模板

```python
from apps.core.forum_registry_types import (
    ForumModuleDefinition,
    ModuleLifecycleDefinition,
)

ForumModuleDefinition(
    module_id="example",
    name="Example",
    description="示例模块。",
    category="feature",
    capabilities=("example-capability",),
    lifecycle=ModuleLifecycleDefinition(
        registration_mode="static",
        registration_mode_label="启动时静态注册",
        readiness_probe="依赖校验与健康摘要",
        supports_disable=False,
        supports_teardown=False,
    ),
)
```

## 接入清单

新增模块时，按下面顺序检查：

1. 后端注册
   在 `ForumModuleDefinition` 中声明模块、依赖、能力、设置组和生命周期。
2. 管理入口
   如有后台页，同时补 `AdminPageDefinition` 和 `frontend/src/admin/registry/bootstrap/routes.js` 相关注册。
3. 领域协议
   如有资源字段、事件监听、通知类型、帖子类型或搜索过滤器，统一走 registry 注册。
4. 前端注入
   如需 header、discussion action、post action、composer extension、admin navigation、notification renderer，统一走对应 registry。
5. 文档
   至少在本页说明模块边界；如有单独说明页，可把 `documentation_url` 指向开发者文档页。
6. 测试
   至少覆盖模块中心接口输出、注入点解析或对应注册导出。

## 最小原则

- 不直接把模块信息硬写到后台页面。
- 不绕过 registry 直接改核心 service 暴露元数据。
- 不新增“只在某个页面可见”的私有扩展协议。
- 模块文档能放进开发者文档页时，优先复用统一入口。
