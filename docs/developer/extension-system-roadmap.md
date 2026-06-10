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

截至当前代码状态，扩展系统主线已经完成了第一批、第二批，并继续推进第三批运行时收口：

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
6. 扩展脚手架与测试 fixture 已覆盖文件系统扩展发现链路

当前已经收敛到扩展中心作为后台主入口，旧模块管理页面和接口已移除。

### 已完成：阶段 2 的真实启停基础

已落地：

1. `ExtensionInstallation` 模型
2. 对应数据库迁移
   `apps/core/migrations/0004_extension_installations.py`
3. `ExtensionRegistry` 已能读取持久化状态覆盖扩展的 `installed / enabled / booted`
4. `ExtensionService`
   已接入真实启用 / 禁用逻辑
5. 后台扩展启停 API
   - `POST /api/admin/extensions/{id}/enable`
   - `POST /api/admin/extensions/{id}/disable`
6. 启停依赖校验
   - 缺少依赖时禁止启用
   - 依赖未启用时禁止启用
   - 存在启用中的依赖方时禁止停用
   - `core` 扩展禁止停用
7. 启停操作已写入后台审计日志

### 已完成：阶段 3 的第一批运行时能力过滤

已落地：

1. `ForumRegistry` 已按扩展启停状态过滤：
   - 权限
   - 后台页面
   - 通知类型
   - 用户偏好
   - 语言包
   - 事件监听
   - 帖子类型
   - 搜索过滤器
   - 讨论排序
   - 讨论列表过滤器
2. `ResourceRegistry` 已按扩展启停状态过滤：
   - resource definition
   - resource fields
   - resource relationships
3. 后台前端入口已按扩展启停状态过滤：
   - 后台侧边导航

### 已完成：阶段 3 的扩展后台动作协议首版

已落地：

1. `ExtensionManifest.admin_actions`
   支持扩展声明统一后台动作
2. manifest 校验已覆盖后台动作协议
   - `kind`
   - `tone`
   - `target`
   - `key` 唯一性
3. 内置模块扩展适配层已生成标准后台动作
   - 查看详情
   - 设置
   - 权限
   - 操作
   - 文档
4. 扩展中心 API 已统一输出 `admin_actions`
5. 扩展详情页与扩展列表页已改为按动作协议渲染
6. 需要启用态的后台动作在扩展停用时会自动隐藏

### 已完成：阶段 4 的扩展详情页组件协议首版

已落地：

1. 扩展后台入口支持可选导出 `resolveDetailPage`
2. 扩展详情页已可加载扩展自定义详情组件
3. 扩展后台宿主页与详情页已共用入口解析器
4. `create_extension` 脚手架会生成 `DetailPage.vue`
5. 扩展后台入口协议已有测试 fixture 覆盖自定义详情组件加载链路

### 已完成：阶段 5 的安装状态与运行操作协议首版

已落地：

1. 文件系统扩展默认进入 `待安装` 状态，而不是自动视为已启用
2. 扩展运行时新增统一状态字段：
   - `runtime_status`
   - `runtime_actions`
3. 后台已支持第一批运行操作：
   - `install`
   - `enable`
   - `disable`
   - `uninstall`
4. 扩展中心列表页与详情页都已改为消费统一运行操作协议
5. 卸载当前只移除安装登记，不自动回滚迁移，符合路线图约束

### 已完成：阶段 5 的交付探针与安装摘要首版

已落地：

1. 扩展运行时已增加交付探针摘要：
   - 扩展目录
   - 后端入口
   - 后台入口
   - 迁移目录
   - 文档资源
   - 语言资源
   - 前台入口
2. 扩展详情页已展示安装摘要和卸载风险说明
3. `create_extension` 脚手架已生成：
   - `backend/ext.py`
   - `backend/apps.py`
   - `backend/django_migrations/__init__.py`
   - `docs/README.md`
   - `locale/zh-CN.json`
   - `django_app_config`
   - `django_app_label`
4. 扩展脚手架已补齐交付样板目录
   - 仪表盘快捷入口
   - 后台路由可访问性守卫
   - 扩展启停后的前端状态同步
4. 论坛公开配置已下发运行时启用模块清单：
   - `/api/forum` 返回 `enabled_modules`
5. 论坛公开配置现在会同时下发已启用扩展的前台运行清单：
   - `/api/forum` 返回 `enabled_extensions`
   - 包含 `frontend_forum_entry`
   - 包含扩展公开 `settings_values`
6. 论坛应用启动时已在挂载前动态加载已启用扩展的前台入口：
   - `frontend_forum_entry` 不再只是 manifest 字段
   - 已进入真实运行协议
7. 前台入口协议已由测试 fixture 覆盖，验证前台扩展注入链路可用
5. 论坛前台静态注册中心已按扩展启停状态过滤：
   - 论坛导航
   - 头部菜单
   - 搜索来源
   - 个人资料面板
   - 讨论动作
   - 帖子动作
   - 审核提示 / 举报面板等前台扩展注入项

当前仍未完成前后端所有注入点和设置页协议的彻底扩展化，但“启停后能力真实收敛”已经开始进入主链路。

### 已完成：阶段 4 的第一批扩展后台入口协议

已落地：

1. 扩展 manifest 已支持后台入口分类：
   - `settings_pages`
   - `permissions_pages`
   - `operations_pages`
2. 后台扩展 API 已提供扩展级动作链接：
   - 扩展详情页
   - 设置入口
   - 权限入口
   - 操作入口
   - 文档入口
3. 后台已新增扩展详情页路由：
   - `/admin/extensions/:extensionId`
4. 扩展中心不再只有“跳转字符串”，而是可进入真实扩展详情页查看生命周期、依赖、能力与后台动作

当前阶段 4 仍未完成真正的“扩展自带前端设置组件动态加载”与现有公共页面的彻底下线，但扩展级后台入口协议已经进入主链路。

补充：当前代码已进入“真实后台页面宿主”阶段。

1. 文件系统扩展已通过 `frontend_admin_entry` 加载独立设置页 / 操作页组件
2. `tags` 已作为第一条内置模块迁移样板，通过扩展宿主页承载原有 `TagsPage`
3. `approval`、`flags` 已通过内置扩展宿主页承载原有操作页组件
4. `tags`、`approval`、`flags`、`users` 后台入口已由各自扩展的 `frontend_admin_entry` 注册
5. 扩展宿主页现在支持设置页自动回退：
   - 若扩展未导出自定义 `resolveSettingsPage`
   - 但已声明 `settings_schema`
   - 后台会自动生成统一设置表单，减少每个扩展重复开发设置页的成本
6. 扩展宿主页现在支持权限页 / 操作页统一回退：
   - 权限页可回退到扩展权限说明和全局权限管理入口
   - 操作页可回退到统一后台动作和运行操作面板
   - 扩展未提供自定义组件时，后台不会再出现空白页
7. 扩展权限宿主页已升级为真实聚合视图：
   - 按扩展归属聚合权限分组
   - 显示涉及模块与权限数量
   - 直接跳转全局权限管理完成授权

### 已完成：阶段 6 的第一批开发者工具链

已落地：

1. 扩展 manifest 基础校验已抽成独立验证层：
   - 扩展 ID 格式
   - 语义化版本格式
   - 重复值检查
   - 必需依赖存在性检查
   - 后台入口文件存在性检查
2. 已新增扩展脚手架命令：
   - `python manage.py create_extension <extension_id>`
3. 脚手架默认生成：
   - `extension.json`
   - `frontend/admin/index.js`
   - `frontend/forum/index.js`
   - `frontend/admin/SettingsPage.vue`
   - `frontend/admin/OperationsPage.vue`
   - `backend/ext.py`
   - `docs/README.md`
4. 已新增扩展校验命令：
   - `python manage.py validate_extensions`
   - 支持 `--strict`
5. 扩展巡检现在会输出模型归属审计：
   - `python manage.py inspect_extensions --extension-id <id>`
   - `owned_models` 会包含模型模块、Django app label、数据库表名和存储来源
   - `model_ownership_audit.package_migration_required_count` 表示扩展声明拥有模型，但模型文件仍在 `apps.*` 壳下
   - `model_ownership_audit.app_label_migration_required_count` 表示模型 app label 仍未归属当前扩展

当前阶段 6 仍未完成 manifest 与前端导出约束的更细粒度校验，也还没有把脚手架接入 CI 自动检查，但“新建扩展”和“本地自检”已经进入主链路。

补充：当前代码已补上阶段 6 的第二批约束校验。

1. `validate_extensions` 现在会拦截“声明后台页面但未提供 `frontend_admin_entry`”的 manifest
2. `settings_pages / permissions_pages / operations_pages` 现在必须指向当前扩展自己的标准宿主页路由
3. 前端后台入口缺少必须导出时，仍会在校验阶段直接失败，而不是等后台宿主页运行时报错
4. 扩展详情页现在会展示开发调试信息：
   - manifest 目录
   - 后台入口解析结果
   - 已发现 / 必需前端导出
   - 标准后台路由绑定状态
   - 当前 manifest 校验结果摘要
5. 内置 `core` 模块的后台入口已开始宿主化：
   - `/admin/basics`、`/admin/appearance` 已重定向到 `/admin/extensions/core/settings`
   - `/admin/mail` 重定向到 `/admin/extensions/core/settings`
   - `/admin/advanced` 重定向到 `/admin/extensions/core/operations`
   - `/admin/audit-logs`、`/admin/docs` 也已收敛到 `core` 的操作宿主页
   - 宿主页现在承接核心后台分组入口，并通过内部承载页接住旧核心页面，而不是直接把旧页面当作扩展页面挂载
6. 扩展详情页现在会展示结构化后台页清单：
   - 显示扩展关联的真实后台页面
   - 与 settings / permissions / operations 宿主摘要并列展示
7. 扩展中心与宿主页已开始复用统一后台页解析层：
   - `admin_page_details` 到最终路由目标的解析已共享
   - 扩展中心列表可直接点击扩展关联的后台页
   - `core` 宿主页、扩展详情页、扩展中心不再各自维护一套页面映射
8. 扩展中心卡片入口已开始去重：
   - 已由后台页清单承接的 route 动作，不再重复显示为独立按钮
   - 列表卡片优先保留详情、文档与非重复动作，减少入口噪音
9. 扩展中心到详情页 / 宿主页的来源链路已开始透传：
   - 从扩展中心进入时，会带上统一来源参数
   - 详情页进入宿主页后继续透传来源，便于后续统一返回路径策略
10. 扩展后台导航辅助层已开始共享：
   - 扩展中心、详情页、宿主页、自动生成权限页 / 操作页已复用统一来源解析
   - route 型后台动作会自动透传 `from`
   - 返回扩展中心 / 返回扩展详情不再由各页面各自拼接 query
11. 内置扩展的权限入口已开始标准化：
   - 不再把内置扩展权限按钮直接指向全局 `/admin/permissions`
   - `core / users / approval / flags` 已改为各自的 `/admin/extensions/<id>/permissions`
   - 统一由扩展权限宿主承接，再跳转全局权限矩阵完成授权
12. 扩展开发工具链的结构约束已继续收严：
   - `frontend_admin_entry` 必须指向当前扩展自己的标准后台入口
   - `frontend_forum_entry` 必须指向当前扩展自己的标准前台入口
   - `backend_entry` 必须归属当前扩展命名空间
   - `create_extension` 默认生成扩展 AppConfig 和 `django_migrations`，让新模型归属从一开始就能被审计
13. `validate_extensions` 已支持结构化 JSON 输出：
   - 可直接在 CI、发布脚本和后续自动化工具中消费
   - 保留原有文本输出和失败退出语义
14. 已新增 `inspect_extensions` 诊断导出命令：
   - 可导出扩展清单、迁移状态、运行风险、交付检查和能力摘要
   - 支持单扩展聚焦、仅关注项过滤和权限明细导出
   - 命令输出直接复用后台扩展序列化结果，减少 API 与自动化脚本的结构漂移
15. 发布前检查已接入扩展诊断产物：
   - `prepare_release` 会先执行扩展诊断并统计关注项
   - 默认存在扩展关注项就阻止发布，可显式放行
   - 可把扩展诊断快照落盘为 JSON，供发布记录和 CI 归档
   - `publish_release` 已透传扩展报告和放行参数
16. 扩展诊断已开始分级：
   - 区分阻断发布的 blocking 项和仅告警的 warning 项
   - `inspect_extensions` 已支持 `--only-blocking`
   - 发布链路当前默认只拦截 blocking 项，不再把所有 attention 一刀切

### 已完成：阶段 7 的第一批生态元数据预留

已落地：

1. 扩展 manifest 新增生态边界字段：
   - `compatibility`
   - `security`
   - `distribution`
2. 已支持声明：
   - Bias 兼容版本范围
   - 扩展 API 版本
   - API 稳定等级
   - breaking-change 说明
   - 安全联系邮箱 / 风险提示
   - 分发通道 / 签名占位信息
3. `validate_extensions` 已校验：
   - 兼容版本范围格式
   - API 版本格式
   - 稳定等级枚举
   - 分发通道枚举
   - 安全联系邮箱格式
   - 签名 URL / Key ID 成对声明
4. `create_extension` 脚手架已默认生成上述生态元数据
5. 扩展详情页已展示生态边界摘要，方便后台直接判断哪些协议可依赖
6. Bias 兼容版本范围已进入运行时主链路：
   - 扩展详情页与清单健康摘要会直接暴露兼容性异常
   - 安装 / 启用操作会拦截与当前 Bias 版本不兼容的扩展
7. 扩展中心已承接扩展状态、主要入口、运行风险和开发快照：
   - 主视图优先展示扩展承载状态、主要入口和运行风险
   - 注册表快照下沉到扩展详情页的诊断区域
   - 旧模块管理入口已移除

## 当前状态

### 已有能力

Bias 当前已经具备扩展平台的早期基础：

1. 后端 registry
   `apps/core/forum_registry.py`
   `apps/core/forum_registry_types.py`
2. 内置模块定义
   `apps/core/forum_registry_builtin.py`
3. 扩展中心元数据与健康摘要
   `apps/core/admin_content_api.py`
   `frontend/src/admin/views/ExtensionsPage.vue`
   `frontend/src/admin/views/ExtensionDetailPage.vue`
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

Bias 的目标是做一套以扩展为核心、适配 Python/Django 实现方式的论坛平台系统。

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
  sample_extension/
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
- `django_app_config`
- `django_app_label`

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
4. 扩展中心作为后台主入口
   UI 使用扩展维度而不是模块快照维度
5. 允许现有内置模块先通过扩展定义装配层暴露成扩展

### 演进策略

第一步不能直接删除 `ForumRegistry`，但新能力必须从扩展视角进入主链路。

需要新增装配层：

1. `BuiltinModuleExtensionAdapter`
   把现有 `ForumModuleDefinition` 包装成扩展对象
2. 后台优先显示扩展视角
3. 能力注册逐步收敛到扩展 registry，`ForumRegistry` 仅保留论坛运行期聚合职责

### 涉及代码

- `apps/core/forum_registry.py`
- `apps/core/forum_registry_builtin.py`
- `apps/core/admin_content_api.py`
- `frontend/src/admin/views/ExtensionsPage.vue`
- `frontend/src/admin/views/ExtensionDetailPage.vue`

### 验收标准

1. 后台有独立的“扩展中心”数据模型
2. 扩展列表来自 manifest + 扩展定义装配，不再仅靠内置模块硬编码
3. 扩展中心接口服务扩展列表、详情、启停、诊断和运行操作

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
- `frontend/src/admin/views/ExtensionsPage.vue`
- `frontend/src/admin/views/ExtensionDetailPage.vue`

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

做成真正以 Bias 为中心的“每个扩展可点开进入自己的设置页”。

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
5. 把 `basic/appearance/mail/advanced` 收敛为扩展声明的设置入口

### 前端目标

每个扩展应可声明：

1. 后台设置页面组件
2. 扩展详情页组件
3. 管理动作组件

### 涉及代码

- `frontend/src/admin/router`
- `frontend/src/admin/registry/bootstrap/routes.js`
- `frontend/src/admin/views/ExtensionsPage.vue`
- `frontend/src/admin/views/ExtensionDetailPage.vue`
- `apps/core/admin_content_api.py`

### 验收标准

1. 扩展可声明独立设置页
2. 扩展中心操作不再只是跳公共页面
3. 后台使用体验符合 Bias 扩展管理协议

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
   - `backend/apps.py`
   - `backend/django_migrations`
   - 前端入口
   - `ApiResourceExtender` 示例资源字段
   - 设置页模板
   - 测试模板
3. 增加扩展验证命令
   - manifest 校验
   - 依赖校验
   - 注册导出检查
   - 源码契约检查：业务扩展使用 `ApiResourceExtender`，不直接依赖低层 `ResourceExtender`
   - 产品命名检查：扩展代码、文档和前端入口不允许出现外部项目命名残留
4. 扩展中心支持开发调试信息

### 验收标准

1. 新建扩展不需要手工拷贝旧模块
2. 新扩展能快速跑通前端入口、AppConfig、迁移归属、设置、生命周期和 API 资源字段的最小闭环
3. CI 能校验扩展 manifest、依赖关系和公开 extender 使用边界

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
5. `emoji`
6. `likes`
7. `mentions`
8. `subscriptions`
9. `realtime`
10. `search`
11. `users`
12. `discussions`
13. `posts`

### 第二批

再迁移“强依赖核心模型但边界仍可整理”的功能：

当前第二批已清空，后续如果从核心模块中拆出新的非基础能力，再进入这一批。

### 第三批

最后处理平台核心：

1. `core`

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
3. 扩展中心是后台扩展管理的唯一主入口
4. 不再新增旧模块管理接口或页面

## 下一步

接下来优先继续迁移边界较清晰的运行时能力，并同步清理旧模块注册代码：

1. 检查 `core` 中可拆出的非基础能力
2. 继续减少 `BuiltinModuleExtensionAdapter` 承载范围
3. 优先把仍留在 core 的非基础注册贡献抽成扩展
4. 保持每个迁移批次都覆盖扩展启停、依赖图、运行时过滤和交付诊断测试
