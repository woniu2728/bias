# Flarum Core 对齐矩阵

状态：草案
日期：2026-06-30

本文档对应 `docs/flarum-parity-delivery-plan.md` 的阶段 2，用于把本地 `flarum-core` 参照拆成 Bias 可验收的核心能力清单。

参照代码：

```text
D:\files\project\tmp\flarum_code\flarum-core
```

状态只能使用：

```text
done
partial
not implemented
intentionally different
```

当前矩阵采用保守口径：只有实现、产品路径、测试证据都齐全的项目才标 `done`。已有后端服务但缺少 HTTP/API 集成测试、前端路径或浏览器证据的项目标 `partial`。

## 总览

| 领域 | Flarum 参照 | Bias 归属 | 状态 | 当前证据 | 缺口 / 下一步 |
| --- | --- | --- | --- | --- | --- |
| 用户模型 | `src/User` | `bias-ext-users` | partial | `bias_ext_users/backend/models.py`、`services.py`、`api.py`、`admin_api.py`；后台用户/组/权限 API 已有核心测试：`bias_core/tests/test_admin_permissions.py`、`test_management.py` | 补前台用户资料、用户搜索、注册/登录/邮箱验证、头像、密码重置的 HTTP 集成矩阵；补浏览器流程。 |
| 组和权限 | `src/Group`、`src/User/Access`、`src/*/Access` | `bias-ext-users` + `bias_core.forum_permissions` + extension policy runtime | partial | `bias_ext_users/backend/admin_api.py` 提供 group/permission 管理；`bias_core/tests/test_admin_permissions.py` 覆盖后台权限保存和 registry meta；`bias_core/tests/test_extension_loader.py` 覆盖 forum permission checker bootstrap | 补 guest/registered/author/moderator/admin 对 discussion/post/user 可见性和操作权限的 HTTP 集成测试。 |
| 讨论模型 | `src/Discussion` | `bias-content` 数据归属，`bias-ext-discussions` 行为包装 | partial | `bias-ext-discussions/extension.json` 声明 discussion API/UI；`bias_ext_discussions/backend/services.py`、`resources.py`、`visibility.py`、`runtime.py` 存在；阶段 1 已保持 content foundation 边界 | 缺 `/api/discussions`、`/api/discussions/{id}`、创建/编辑/隐藏/恢复/删除/锁定/置顶的明确 HTTP 集成测试；确认或补 resource endpoint 映射。 |
| 帖子模型 | `src/Post` | `bias-content` 数据归属，`bias-ext-posts` 行为包装 | partial | `bias_ext_posts/backend/services.py`、`resources.py`、`visibility.py`、`runtime.py` 存在；post resource 包含 can_edit/can_delete/can_hide/ip/event_data | 缺 `/api/discussions/{id}/posts`、回复创建/编辑/隐藏/恢复/删除、楼层分页、approval 状态的 HTTP 集成测试。 |
| API Resource | `src/Api/Resource`、`src/Api/Endpoint`、`src/Api/Schema` | `bias_core.resources`、`bias_core.resource_*`、扩展 ResourceExtender | partial | `bias_core/src/bias_core/resources/*`；`bias_core/tests/test_resource_registry.py` 覆盖 resource registry、serializer、search、route definitions；`bias_core/tests/test_extension_loader.py::test_api_application_is_built_from_extension_host_routes` | 缺核心论坛资源的端到端 API 合约测试，尤其是 discussion/post/user 默认 include、fields、relationships 和错误格式。 |
| Policy / Visibility | `src/*/Access`、`src/User/Access/Gate.php` | `bias_core.extensions.policy_runtime_service` + `forum_permissions` + 各扩展 visibility | partial | `bias_core/tests/test_extension_loader.py` 覆盖 policy/middleware bootstrap；`bias_ext_discussions/backend/visibility.py`、`bias_ext_posts/backend/visibility.py` 存在 | 缺角色矩阵 HTTP 测试，尤其隐藏讨论/隐藏帖子/私有或待审核内容在列表、详情、搜索中的一致过滤。 |
| 搜索 | `src/Search`、`src/Discussion/Search`、`src/Post/Filter`、`src/User/Search` | `bias-ext-search` + discussion/post/user/tag search targets | partial | `bias_ext_search/backend/api.py` 提供 `/search`、`/search/suggestions`、`/search/filters`；`bias_core/tests/test_resource_registry.py` 覆盖 SearchDriverExtender 和 search manager | 缺真实 discussion/post/user/tag 数据的 HTTP 搜索测试；缺与 tags、visibility、permissions、pagination 组合测试。 |
| 通知 | `src/Notification` | `bias-ext-notifications` | partial | `bias_ext_notifications/backend/services.py`、`resources.py`、`tasks.py`、`listeners.py` 存在；runtime service contract 已在 workspace gate 中检查 | 缺通知列表、标记已读、删除、reply/mention/like/approval/flag 组合触发的 HTTP 和浏览器证据。 |
| 设置 | `src/Settings` | `bias_core.settings_service`、`bias_core.admin_settings_api`、扩展 SettingsExtender | partial | `bias_core/tests/test_admin_settings_api.py` 覆盖基础、外观、高级、邮件、公开 forum settings；`bias_core/tests/test_settings_fallback.py` 覆盖缓存和 fallback | 前台 runtime settings 与扩展 settings 的浏览器证据不足；需补设置变更后影响论坛 UI/运行时的 E2E。 |
| 邮件 | `src/Mail` | `bias_core.email_service`、`bias_core.mail_drivers`、`bias-ext-users` mail templates | partial | `bias_core/tests/test_extension_loader.py` 覆盖 MailExtender driver；`bias_core/tests/test_admin_settings_api.py` 覆盖 mail settings 和 test recipient；`bias_ext_users/backend/mail.py` 存在 | 缺注册验证、重置密码、通知邮件等真实产品流程测试；缺驱动错误路径和后台发送测试邮件端到端证据。 |
| 队列 | `src/Queue` | `bias_core.services.queue` | partial | `bias_core/tests/test_queue.py` 覆盖 settings 加载 Celery app、worker status、metrics、dispatch fallback；阶段 1 已移除 core 对 `config.celery` 直接导入 | 缺真实 worker/redis 集成或生产冒烟；缺 extension task 调度组合测试。 |
| 前台应用 | `js/src/forum` | `bias/frontend/src/forum`、`bias/frontend/src/components`、扩展 forum entry | partial | `bias/frontend/src/forum/*`、`HomePage.vue`、`Header.vue`、composer/runtime 文件存在；前端有若干 unit test | 缺浏览器 E2E 覆盖首页、讨论详情、composer、用户资料、通知、搜索、tags。 |
| 后台应用 | `js/src/admin` | `bias/frontend/src/admin`、`bias_core.admin_*`、扩展 admin entry | partial | `bias/frontend/src/admin/views/*` 覆盖 dashboard/settings/extensions/permissions/mail/audit；`bias_core/tests/test_admin_extensions_api.py`、`test_admin_settings_api.py`、`test_admin_permissions.py` | 缺浏览器 E2E 覆盖扩展启停、权限矩阵、用户管理、内容审核、标签管理、rebuild frontend。 |
| 安装/更新 | `src/Install`、`src/Update` | `bias_core.management.commands.install_forum`、`migrate_extensions`、`sync_extensions`、`bias` project bootstrap | partial | `bias_core/src/bias_core/management/commands/install_forum.py`、`migrate_extensions.py`、`sync_extensions.py`；`bias_core/tests/test_bootstrap_config.py`、`test_extension_service.py` 有部分覆盖 | 缺全新 SQLite/PostgreSQL 安装、初始管理员、默认扩展安装启用、升级保留状态、非 editable 安装冒烟。 |
| 扩展管理 | `src/Extension`、`src/Extend` | `bias_core.extensions`、admin extensions API、frontend extension pages | partial | `bias_core/tests/test_admin_extensions_api.py`、`test_extension_service.py`、`test_extension_registry.py`、`test_extension_boundary.py`、`check_extension_workspace` gate 覆盖大量后端能力 | 缺浏览器 E2E；缺生成扩展 -> 打包 wheel -> 干净站点安装 -> 后台启停的完整 DX 流程。 |

## 阶段 2 完成条件

阶段 2 目前未完成。原因：

1. 上表所有核心领域均至少存在一个产品路径或测试证据缺口。
2. discussion/post 主流程尚未被明确 HTTP 集成测试证明。
3. 前台、后台、安装升级和扩展开发体验仍缺浏览器或打包级证据。

## 下一批实现任务

遵从“先解决主要矛盾”，阶段 2 之后应优先进入阶段 3 的主论坛 HTTP 流程，而不是继续增加平台抽象。

优先任务：

1. 明确 discussion/post 的 API 路由策略。
   - 如果使用 `bias_core.resources` 自动路由，则为 `discussion`、`post` 注册标准 `index/show/create/update/delete` endpoint，并验证生成路径。
   - 如果使用扩展 router，则在 `bias-ext-discussions` 和 `bias-ext-posts` 中显式挂载 `/discussions`、`/discussions/{id}`、`/discussions/{id}/posts` 等端点。

2. 新增 HTTP 集成测试覆盖讨论列表。
   - `GET /api/discussions`
   - 排序：最新回复、最新发布、热门、未读、我的。
   - 过滤：搜索词、作者、未读，tags 过滤放到 tags 阶段补齐。
   - 默认 include：作者、最后回复、首帖摘要、阅读状态；tags include 在 tags 启用时覆盖。

3. 新增 HTTP 集成测试覆盖讨论详情和帖子流。
   - `GET /api/discussions/{id}`
   - `GET /api/discussions/{id}/posts`
   - `near`、`before`、`after` 或明确记录暂不支持项。

4. 新增 HTTP 集成测试覆盖创建和回复生命周期。
   - 创建讨论、编辑标题、编辑首帖、隐藏/恢复/删除。
   - 创建回复、编辑回复、隐藏/恢复/删除回复。

5. 新增角色可见性测试。
   - guest、registered user、discussion author、moderator、administrator。
   - 列表、详情、搜索结果的可见性必须一致。

完成以上任务后，再回到本矩阵把对应行从 `partial` 收敛到 `done` 或拆出剩余差异。
