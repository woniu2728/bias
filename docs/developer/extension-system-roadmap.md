# 扩展系统路线图

## 目标

Bias 后续不再停留在“内置模块注册中心”阶段，而是要演进为“可发现、可启停、可配置、可迁移、可交付”的论坛扩展平台。

这份文档定义：

1. 当前实现和目标实现的差距
2. 扩展系统的目标架构
3. 分阶段实施路线
4. 每阶段的代码边界、验收标准和风险
5. 后续新增扩展时必须遵守的约束

本文档是 Bias 扩展系统改造的主规范。

## 当前进展

截至当前代码状态，扩展系统主线已经完成了第一批和第二批基础设施落地：

### 已完成：阶段 0 设计冻结的首批代码承载

已新增扩展系统基础目录与核心类型：

- `apps/core/extensions/types.py`
- `apps/core/extensions/manifest.py`
- `apps/core/extensions/exceptions.py`
- `apps/core/extensions/registry.py`

这意味着扩展系统不再停留在文档阶段，而是已经有正式的后端抽象承载 manifest、runtime state、lifecycle 和 registry。

### 已完成：阶段 1 扩展发现与清单层的第一版实现

已落地：

1. `ExtensionManifestLoader`
   可以扫描 `extensions/*/extension.json`
2. `ExtensionRegistry`
   可以汇总文件系统扩展与内置模块扩展
3. `BuiltinModuleExtensionAdapter`
   可以把现有 `ForumModuleDefinition` 包装为扩展定义
4. 后台扩展清单 API
   `GET /api/admin/extensions`
5. 后台扩展中心页面
   `frontend/src/admin/views/ExtensionsPage.vue`
6. 真实示例扩展目录
   `extensions/sample-hello/extension.json`

当前已经进入“扩展中心和模块中心并行存在”的兼容阶段。

### 已完成：阶段 2 的状态持久化基础

已落地：

1. `ExtensionInstallation` 模型
2. 对应数据库迁移
   `apps/core/migrations/0004_extension_installations.py`
3. `ExtensionRegistry` 已能读取持久化状态覆盖扩展的 `installed / enabled / booted`

当前尚未完成真实启停 API 和能力过滤，但状态模型与 registry 覆盖链路已经建立。

## 当前状态

### 已有能力

Bias 当前已经具备扩展平台的早期基础：

1. 后端 registry
   `apps/core/forum_registry.py`
   `apps/core/forum_registry_types.py`
2. 内置模块定义
   `apps/core/forum_registry_builtin.py`
3. 模块中心元数据与健康摘要
   `apps/core/admin_content_api.py`
   `apps/core/admin_module_helpers.py`
   `frontend/src/admin/views/ModulesPage.vue`
4. 领域事件、资源字段、前端注入点等平台协议
   `apps/core/domain_events.py`
   `apps/core/resource_registry.py`
   `frontend/src/admin/registry/*`
   `frontend/src/forum/*`

### 当前局限

这些能力仍然更接近“内置模块注册平台”，而不是成熟扩展系统：

1. 模块来源是硬编码注册，不是动态发现
2. `enabled` 状态主要是静态声明，不是持久化运行时状态
3. 模块停用后不会真正撤销权限、路由、监听器、通知、搜索扩展
4. 模块设置页只是映射到公共后台页面，不是扩展自带设置入口
5. 没有统一的扩展清单、扩展目录结构、扩展 manifest 和加载协议
6. 没有扩展迁移、扩展资源发布、扩展启停事件、扩展依赖图

## 目标架构

Bias 的目标不是照搬 PHP 版 Flarum，而是做一套“Flarum 产品体验 + Python/Django 实现方式”的扩展系统。

### 目标能力

扩展系统最终至少要支持：

1. 扩展发现
   从已安装扩展目录中发现扩展，而不是只读取内置模块列表。
2. 扩展 manifest
   每个扩展声明自己的元数据、依赖、版本、设置页、能力边界。
3. 扩展启停
   在后台启用、禁用扩展，并持久化到数据库或站点配置。
4. 生命周期
   扩展在 `register / boot / ready / disable / teardown` 阶段拥有明确协议。
5. 扩展设置
   每个扩展可声明自己的后台设置页、权限入口、说明文档和状态摘要。
6. 扩展迁移
   每个扩展拥有自己的数据库迁移和初始化逻辑。
7. 扩展资源发布
   前端 JS、CSS、静态资源、语言包可按扩展交付。
8. 扩展依赖管理
   能校验必需依赖、可选依赖、冲突关系和启动顺序。
9. 扩展级诊断
   能展示扩展健康状态、依赖风险、迁移状态、运行时故障。
10. 平台协议收口
   权限、通知、资源字段、搜索过滤、后台页、前端注入统一经扩展协议注册。

### 不在第一阶段做的事

以下能力先不作为初始目标：

1. 在线安装市场
2. 浏览器内直接下载第三方扩展包
3. 真正热插拔到“无需重启进程”
4. 任意扩展执行不可信代码的沙箱
5. 跨版本自动升级兼容层

## 推荐目录结构

扩展系统落地后，推荐采用如下结构：

```text
apps/
  core/
  discussions/
  posts/
  tags/
  users/
extensions/
  flarum_compat/
  approval/
    extension.json
    backend/
      app.py
      ext.py
      migrations/
      services/
      listeners/
      api/
    frontend/
      admin/
      forum/
    locale/
    docs/
```

说明：

1. `apps/*` 保留平台核心与首批内置能力
2. `extensions/*` 承担扩展化交付目录
3. 每个扩展必须有独立 manifest
4. 扩展内部自行维护后端、前端、文档、迁移与资源

第一阶段不要求立刻把所有现有内置模块搬出 `apps/*`，但新协议必须围绕 `extensions/*` 设计。

## 核心抽象

### 1. ExtensionManifest

统一描述扩展元数据：

- `id`
- `name`
- `version`
- `description`
- `icon`
- `authors`
- `homepage`
- `documentation_url`
- `dependencies`
- `optional_dependencies`
- `conflicts`
- `provides`
- `backend_entry`
- `frontend_admin_entry`
- `frontend_forum_entry`
- `settings_pages`
- `permissions_pages`
- `migration_namespace`

### 2. ExtensionRuntimeState

统一描述扩展运行状态：

- `installed`
- `enabled`
- `booted`
- `healthy`
- `migration_state`
- `dependency_state`
- `runtime_issues`

### 3. ExtensionLifecycle

统一扩展生命周期：

1. `discover`
2. `register`
3. `boot`
4. `ready`
5. `disable`
6. `teardown`

说明：

- `discover` 负责发现和读取 manifest
- `register` 只注册元数据和能力声明
- `boot` 才真正接入运行时
- `disable` 负责撤销可撤销能力
- `teardown` 用于迁移、卸载和未来更强的回收场景

### 4. ExtensionRegistry

现有 `ForumRegistry` 要逐步演进为两层：

1. `ExtensionRegistry`
   维护扩展对象、manifest、依赖图、运行状态
2. `CapabilityRegistry`
   维护权限、后台页、资源字段、事件监听、通知、搜索等具体能力

不要继续把“扩展发现”和“能力注册”都混在一个 registry 中。

## 扩展系统实施路线

## 阶段 0：设计冻结

### 目标

在改代码前先冻结扩展系统协议，避免边做边改抽象。

### 任务

1. 定义 `extension.json` 或 `pyproject` 风格 manifest 格式
2. 定义扩展 Python 入口协议
3. 定义扩展前端入口协议
4. 定义扩展 settings page 协议
5. 定义扩展生命周期事件
6. 定义扩展状态持久化模型
7. 定义依赖和冲突规则

### 涉及文件

建议新增：

- `apps/core/extensions/manifest.py`
- `apps/core/extensions/types.py`
- `apps/core/extensions/exceptions.py`
- `docs/developer/extension-system-roadmap.md`

### 验收标准

1. manifest 字段冻结
2. 目录约定冻结
3. 生命周期语义冻结
4. 不再新增新的“临时模块字段”

## 阶段 1：扩展发现与清单层

### 目标

先把“模块清单”升级为“扩展清单”，但先不做真实启停。

### 任务

1. 新增 `ExtensionManifestLoader`
   扫描 `extensions/*/extension.json`
2. 新增 `ExtensionDefinition`
   替代纯 `ForumModuleDefinition` 的外层语义
3. 建立 `ExtensionRegistry`
   负责加载 manifest 和依赖图
4. 模块中心改造成“扩展中心”
   UI 使用扩展维度而不是模块快照维度
5. 允许现有内置模块先通过“兼容适配层”暴露成扩展

### 兼容策略

第一步不能直接删除 `ForumRegistry`。

需要新增适配层：

1. `BuiltinModuleExtensionAdapter`
   把现有 `ForumModuleDefinition` 包装成扩展对象
2. 后台优先显示扩展视角
3. 能力注册仍可暂时复用旧 registry

### 涉及代码

- `apps/core/forum_registry.py`
- `apps/core/forum_registry_builtin.py`
- `apps/core/admin_content_api.py`
- `apps/core/admin_module_helpers.py`
- `frontend/src/admin/views/ModulesPage.vue`

### 验收标准

1. 后台有独立的“扩展中心”数据模型
2. 扩展列表来自 manifest + 兼容适配，不再仅靠内置模块硬编码
3. 旧模块中心接口可以保留一段时间，但新接口优先服务扩展中心

## 阶段 2：扩展状态持久化与启停

### 目标

支持扩展启用、禁用和依赖校验。

### 任务

1. 新增扩展状态模型
   建议：
   - `ExtensionInstallation`
   - `ExtensionSetting`
   - 或在 `Setting` 中保存 `extensions.enabled`
2. 实现 `enable_extension()` / `disable_extension()`
3. 接入依赖检查：
   - 必需依赖
   - 可选依赖
   - 冲突扩展
4. 后台增加启停操作
5. 扩展状态变化写入审计日志

### 关键约束

启停不是只改一个布尔值。

扩展禁用后，至少要保证：

1. 后台入口不可见
2. 权限项不再参与权限矩阵
3. 前端注入点不再挂接
4. 通知类型和搜索过滤不再暴露
5. 依赖它的扩展不能启用

### 涉及代码

- `apps/core/models.py`
- `apps/core/settings_service.py`
- `apps/core/admin_api.py`
- `apps/core/admin_content_api.py`
- `apps/core/audit.py`
- `frontend/src/admin/views/ModulesPage.vue`

### 验收标准

1. 后台可启用/禁用扩展
2. 依赖缺失时阻止启用
3. 依赖链存在时阻止禁用
4. 启停后扩展能力可见性发生真实变化

## 阶段 3：能力注册拆层

### 目标

把“扩展存在”和“扩展提供哪些能力”彻底拆开。

### 任务

1. 把现有 registry 拆为：
   - `ExtensionRegistry`
   - `PermissionRegistry`
   - `AdminPageRegistry`
   - `NotificationRegistry`
   - `ResourceFieldRegistry`
   - `EventListenerRegistry`
   - `SearchRegistry`
2. 每个 registry 支持按扩展启停过滤
3. 所有读取注册结果的调用方改为走“仅返回已启用扩展能力”
4. 建立统一的 `ExtensionContext`
   把扩展 id、版本、设置、状态传给注册器

### 最大风险

这是扩展系统的核心重构阶段，回归面很大。

重点受影响的区域：

- 权限矩阵
- 后台导航
- 搜索过滤
- 通知投递
- 资源字段输出
- 讨论/帖子副作用链路

### 涉及代码

- `apps/core/forum_registry.py`
- `apps/core/resource_registry.py`
- `apps/core/search_index_service.py`
- `apps/core/services.py`
- `apps/core/settings_service.py`
- `apps/core/forum_resources_post_events.py`
- `frontend/src/admin/registry/*`
- `frontend/src/forum/*`

### 验收标准

1. 所有平台能力都能按扩展维度开关
2. 不再存在“扩展禁用了但能力还在”的假状态
3. 新增能力时必须声明归属扩展

## 阶段 4：扩展设置页与后台入口

### 目标

做成真正接近 Flarum 的“每个扩展可点开进入自己的设置页”。

### 任务

1. 新增扩展后台页协议
2. 新增扩展设置页注册协议
3. 支持三类入口：
   - `settings`
   - `permissions`
   - `operations`
4. 后台扩展中心支持：
   - 打开设置
   - 打开权限
   - 查看文档
   - 查看扩展详情
5. 把现在的 `basic/appearance/mail/advanced` 兼容映射逐步下线

### 前端目标

每个扩展应可声明：

1. 后台设置页面组件
2. 扩展详情页组件
3. 管理动作组件

### 涉及代码

- `frontend/src/admin/router`
- `frontend/src/admin/registry/bootstrap/routes.js`
- `frontend/src/admin/views/ModulesPage.vue`
- `apps/core/admin_module_helpers.py`
- `apps/core/admin_content_api.py`

### 验收标准

1. 扩展可声明独立设置页
2. 扩展中心操作不再只是跳公共页面
3. 后台使用体验接近 Flarum 扩展管理

## 阶段 5：扩展迁移、资源发布与安装协议

### 目标

让扩展具备真正可交付能力。

### 任务

1. 扩展独立迁移目录
2. 扩展启用时执行迁移
3. 扩展禁用时不自动回滚迁移
4. 扩展卸载时允许显式执行清理流程
5. 扩展前端静态资源独立构建和发布
6. 扩展语言包与文档资源独立挂载

### 建议实现

1. 后端迁移可采用 Django app 或扩展迁移适配器
2. 前端可采用按扩展 chunk 注册的加载方式
3. 发布流程里把扩展资源纳入构建产物清单

### 涉及代码

- `manage.py` 命令
- `apps/core/management/commands/*`
- `frontend/vite.config.*`
- Docker 构建流程
- 发布流程与 CI

### 验收标准

1. 扩展能带自己的迁移
2. 扩展前端资源能独立交付
3. 扩展启用流程能处理迁移与构建产物

## 阶段 6：开发者工具链与扩展脚手架

### 目标

让后续开发扩展不再靠手工复制。

### 任务

1. 提供扩展脚手架命令
   `python manage.py create_extension`
2. 生成：
   - `extension.json`
   - 后端入口
   - 前端入口
   - 设置页模板
   - 测试模板
3. 增加扩展验证命令
   - manifest 校验
   - 依赖校验
   - 注册导出检查
4. 扩展中心支持开发调试信息

### 验收标准

1. 新建扩展不需要手工拷贝旧模块
2. 新扩展能快速跑通最小闭环
3. CI 能校验扩展 manifest 和依赖关系

## 阶段 7：第三方扩展生态预留

### 目标

先把边界预留好，不急着做市场。

### 任务

1. 扩展版本兼容声明
2. 平台 API 稳定等级定义
3. 扩展安全约束说明
4. 扩展发布和签名策略预留
5. 扩展 API breaking-change 流程

### 验收标准

1. 平台升级时知道哪些扩展协议是稳定的
2. 第三方开发者知道哪些入口可以依赖
3. 后续引入扩展市场时无需重写底层协议

## 推荐实施顺序

扩展系统主线按这个顺序推进：

1. 阶段 0：冻结协议
2. 阶段 1：扩展清单层
3. 阶段 2：状态持久化与启停
4. 阶段 3：能力注册拆层
5. 阶段 4：独立设置页与后台体验
6. 阶段 5：迁移与资源发布
7. 阶段 6：脚手架与工具链
8. 阶段 7：生态预留

不要先做：

1. 在线市场
2. 热更新
3. 浏览器内安装扩展

否则会在基础设施还不稳定时把复杂度直接拉满。

## 每阶段的测试要求

扩展系统每推进一阶段，都必须补对应测试：

1. manifest 解析测试
2. 依赖图测试
3. 启停 API 测试
4. registry 过滤测试
5. 扩展设置页路由测试
6. 前端注入点按启停过滤测试
7. 扩展迁移命令测试

重点要求：

扩展启停必须进入 CI，不能只靠手工点后台验证。

## 现有模块的迁移策略

现有内置模块建议分三批迁移：

### 第一批

先迁移“已有清晰边界”的功能：

1. `approval`
2. `flags`
3. `notifications`
4. `tags`

### 第二批

再迁移“强依赖核心模型但边界仍可整理”的功能：

1. `search`
2. `mentions`
3. `subscriptions`
4. `realtime`

### 第三批

最后处理平台核心：

1. `core`
2. `users`
3. `discussions`
4. `posts`

原因：

核心模块最难拆，应该放到扩展系统协议已经稳定之后再收口。

## 需要避免的错误

1. 不要把扩展系统做成新的大而全 `core/extensions.py`
2. 不要继续往旧 `ForumRegistry` 塞更多职责
3. 不要只做后台按钮，不做真实运行时启停
4. 不要在扩展系统未稳定前引入在线市场
5. 不要让扩展绕过 service 和 registry 直接改核心状态

## 当前建议

从今天开始，Bias 后续平台开发按下面原则执行：

1. 新功能优先考虑未来是否要成为独立扩展
2. 新增平台协议时，优先挂到扩展层而不是模块快照层
3. 模块中心后续演进目标明确改名为“扩展中心”
4. 阶段 1 和阶段 2 完成前，不再继续放大旧模块中心的复杂度

## 下一步

扩展系统的第一个实际开发动作建议是：

1. 新增 `apps/core/extensions/` 目录
2. 冻结 manifest 和 runtime state 类型
3. 建立 `ExtensionRegistry`
4. 让当前内置模块先通过适配器显示为扩展
5. 把后台“模块中心”接口平滑演进为“扩展中心”接口

这一步做完，Bias 才真正从“模块化论坛”进入“可扩展论坛平台”阶段。
