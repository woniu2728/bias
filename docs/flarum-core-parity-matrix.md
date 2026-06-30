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
| 用户模型 | `src/User` | `bias-ext-users` | partial | `bias_ext_users/backend/models.py`、`services.py`、`api.py`、`admin_api.py`；后台用户/组/权限 API 已有核心测试：`bias_core/tests/test_admin_permissions.py`、`test_management.py`；`bias_ext_users/backend/tests.py` 覆盖 `search_user` 资源支持 `include=groups` 并保留 `primary_group` 字段，并覆盖 `POST /api/users/{id}/avatar` 更新 `avatar_url`、跨用户禁止上传和 uploads 扩展头像上限配置，登录限流/封禁提示、忘记密码隐藏未知邮箱、邮箱重发、Turnstile 人机验证等 HTTP 矩阵；`bias/frontend/e2e/forum-home.spec.js` 覆盖真实 Chromium 下 `/profile` 加载 `/api/users/me`、用户讨论、用户回复、偏好、选择图片后 `POST /api/users/{id}/avatar` multipart 上传并渲染新头像，以及设置页 `PATCH /api/users/{id}` 保存资料，并覆盖公开 `/u/{id}` 用户资料页；同一 E2E 还覆盖未登录直达受保护创建页后登录并回到 composer、注册、忘记密码 debug reset link、邮箱验证和重置密码页面，并覆盖登录失败、注册密码不一致/邮箱占用、邮箱验证 token 失败、重置密码确认不一致/token 失败、邮箱重发失败和修改密码失败的浏览器错误展示，以及 security 扩展注册 Turnstile 挑战后登录/注册 payload 携带 `human_verification_token` 的浏览器流程；`bias-ext-users/frontend/forum/useAuthRoutePage.test.js` 覆盖 auth route modal 成功认证后保留 redirect | 继续补更完整账号安全边界和邮件投递端到端证据。 |
| 组和权限 | `src/Group`、`src/User/Access`、`src/*/Access` | `bias-ext-users` + `bias_core.forum_permissions` + extension policy runtime | partial | `bias_ext_users/backend/admin_api.py` 提供 group/permission 管理；`bias_core/tests/test_admin_permissions.py` 覆盖后台权限保存和 registry meta；`bias_core/tests/test_extension_loader.py` 覆盖 forum permission checker bootstrap；`bias_core/tests/test_forum_discussion_api.py` 已覆盖 guest/registered/author/moderator/admin 对 pending/rejected discussion/post 的 HTTP 可见性矩阵，并覆盖非 staff 用户持有 `discussion.lock` / `discussion.sticky` 后可锁定、置顶、PATCH 状态和回复锁定讨论 | 继续补 user 资源、更多 moderation 权限组合，以及浏览器级权限流程。 |
| 讨论模型 | `src/Discussion` | `bias-content` 数据归属，`bias-ext-discussions` 行为包装 | partial | `bias-ext-discussions/extension.json` 声明 discussion API/UI；`bias_ext_discussions/backend/handlers.py` 注册 `/api/discussions/`、`/api/discussions/{id}`；`bias_core/tests/test_forum_discussion_api.py` 覆盖列表、排序、过滤、详情、创建讨论、编辑、隐藏/恢复、删除、锁定、置顶、非 staff lock/sticky 权限、单讨论已读、全部已读、待审核讨论、审核队列通过/拒绝、rejected 后作者重新提交和角色可见性、搜索可见性矩阵、discussion list/detail 的 `fields[discussion]` + `include` 组合、plain error 格式，并覆盖普通讨论列表 SQL 预算 | 继续补浏览器流程和用户/通知联动矩阵。 |
| 帖子模型 | `src/Post` | `bias-content` 数据归属，`bias-ext-posts` 行为包装 | partial | `bias_ext_posts/backend/handlers.py` 注册 `/api/discussions/{id}/posts`、`/api/posts/{id}`；`bias_core/tests/test_forum_discussion_api.py` 覆盖帖子流 `near`/`before`/`after` 窗口、创建回复、编辑回复、隐藏/恢复、删除、待审核回复、审核队列通过/拒绝、rejected 后作者重新提交和角色可见性，post stream/detail 的 `fields[post]` + `include` 组合、plain error 格式，以及搜索 all/posts 入口可见性矩阵；post resource 包含 can_edit/can_delete/can_hide/ip/event_data；普通讨论列表 SQL 预算已覆盖其首帖摘要和最后回复用户关系；`bias-ext-posts` handler 已修复不存在或不可见 discussion 的 post stream 返回 404 | 继续补更多回复作者自助操作边界和浏览器流程。 |
| API Resource | `src/Api/Resource`、`src/Api/Endpoint`、`src/Api/Schema` | `bias_core.resources`、`bias_core.resource_*`、扩展 ResourceExtender | partial | `bias_core/src/bias_core/resources/*`；`bias_core/tests/test_resource_registry.py` 覆盖 resource registry、serializer、search、route definitions；`bias_core/tests/test_extension_loader.py::test_api_application_is_built_from_extension_host_routes`；`bias_core/tests/test_forum_discussion_api.py` 覆盖 discussion/post resource endpoint HTTP 路径，并新增核心论坛 `fields[...]`、`include`、404/403 plain error 格式证据 | 继续补 user 默认关系、更多权限失败路径和浏览器流程。 |
| Policy / Visibility | `src/*/Access`、`src/User/Access/Gate.php` | `bias_core.extensions.policy_runtime_service` + `forum_permissions` + 各扩展 visibility | partial | `bias_core/tests/test_extension_loader.py` 覆盖 policy/middleware bootstrap；`bias_ext_discussions/backend/visibility.py`、`bias_ext_posts/backend/visibility.py` 存在；`bias_core/tests/test_forum_discussion_api.py` 已覆盖 pending/rejected discussion/post 在列表、详情、post stream 中对 guest/registered/author/moderator/admin 的一致过滤，覆盖公开、隐藏、私有、pending、rejected 内容在搜索 all/discussions/posts 入口的角色矩阵，并覆盖非 staff moderation 权限路径 | 继续补浏览器级权限流程和更细 policy 失败路径。 |
| 搜索 | `src/Search`、`src/Discussion/Search`、`src/Post/Filter`、`src/User/Search` | `bias-ext-search` + discussion/post/user/tag search targets | partial | `bias_ext_search/backend/api.py` 提供 `/search`、`/search/suggestions`、`/search/filters`；`bias_core/tests/test_resource_registry.py` 覆盖 SearchDriverExtender 和 search manager；`bias_core/tests/test_forum_discussion_api.py` 覆盖真实 discussion/post 数据的 `/api/search` all/discussions/posts HTTP 可见性矩阵；`bias_ext_search/backend/tests.py` 覆盖 `/api/search?type=users&fields[search_user]=primary_group&include=groups` 的 fields/include 组合，并在 tags 扩展启用、discussion 创建必须带 tags relationship 的条件下跑通 62 个后端测试，覆盖搜索过滤语法、pagination 边界、created 月份过滤和 tags-required 创建夹具；`bias/frontend/e2e/forum-home.spec.js` 覆盖真实 Chromium 下 `/search?q=browser&type=all` 搜索页分组结果渲染、搜索统计、加载态退出，并从讨论搜索结果进入 `/d/101` 详情 | 继续补 tag 搜索结果前台分组、更多 fields/include/error 格式。 |
| 通知 | `src/Notification` | `bias-ext-notifications` + `bias-ext-flags` 等触发源 | partial | `bias_ext_notifications/backend/services.py`、`resources.py`、`tasks.py`、`listeners.py` 存在；runtime service contract 已在 workspace gate 中检查；`bias-ext-notifications/bias_ext_notifications/backend/tests.py` 已覆盖 type count、`read-filtered`、`clear-filtered-read`、单条 soft delete 和 reply/mention/like/approval 触发矩阵，并覆盖 `NotificationCreatedEvent` 监听后派发 `dispatch_notification_batch`、Celery 任务投递通知邮件、队列入队失败同步回退继续加载实时通知和发送邮件；`bias-ext-flags/bias_ext_flags/backend/tests.py` 已在 tags 必填关系组合下覆盖 `POST /api/posts/{id}/report` 创建举报、后台 `/api/admin/flags` 队列列表与处理、前台版主 `/api/posts/{id}/flags/resolve` 处理、非 staff 拒绝和帖子删除清理举报事件；`bias/frontend/e2e/forum-home.spec.js` 覆盖真实 Chromium 下 `/notifications` 请求 `/api/notifications`、渲染 reply/account 通知、单条 `POST /api/notifications/{id}/read` 标记已读、确认后 `DELETE /api/notifications/read/clear` 清理已读并进入空状态，并覆盖 `type`/`state=unread` 筛选刷新、`POST /api/notifications/read-filtered`、单条 `DELETE /api/notifications/{id}` 删除和 `DELETE /api/notifications/read/clear-filtered`；同一 E2E 已覆盖用户在讨论详情提交 `POST /api/discussions/{id}/posts` 后生成新的 `postReply` 通知，再进入 `/notifications` 渲染新通知和未读计数；`bias/frontend/e2e/admin-flags.spec.js` 覆盖真实 Chromium 后台从仪表盘进入“处理举报”、加载 `/api/admin/flags?status=open`、处理举报、刷新待处理空状态，再切到 `status=resolved` 验证处理备注和处理人 | 继续补真实 Redis worker/生产冒烟。 |
| 设置 | `src/Settings` | `bias_core.settings_service`、`bias_core.admin_settings_api`、扩展 SettingsExtender | partial | `bias_core/tests/test_admin_settings_api.py` 覆盖基础、外观、高级、邮件、公开 forum settings；`bias_core/tests/test_settings_fallback.py` 覆盖缓存和 fallback | 前台 runtime settings 与扩展 settings 的浏览器证据不足；需补设置变更后影响论坛 UI/运行时的 E2E。 |
| 邮件 | `src/Mail` | `bias_core.email_service`、`bias_core.mail_drivers`、`bias-ext-users` mail templates、`bias-ext-notifications` mail | partial | `bias_core/tests/test_extension_loader.py` 覆盖 MailExtender driver；`bias_core/tests/test_admin_settings_api.py` 覆盖 mail settings 和 test recipient；`bias_ext_users/backend/mail.py` 存在；`bias_ext_notifications/backend/mail.py` 通过 `bias_core.extensions.platform.EmailService` 发送通知邮件，`bias-ext-notifications/bias_ext_notifications/backend/tests.py` 覆盖通知邮件 subject/body/link、无邮箱收件人跳过、队列失败 fallback 发信 | 继续补注册验证、重置密码、后台发送测试邮件的浏览器或端到端证据，以及驱动错误路径。 |
| 队列 | `src/Queue` | `bias_core.services.queue` | partial | `bias_core/tests/test_queue.py` 覆盖 settings 加载 Celery app、worker status、metrics、dispatch fallback；阶段 1 已移除 core 对 `config.celery` 直接导入；`bias-ext-notifications/bias_ext_notifications/backend/tests.py` 覆盖扩展事件触发 Celery task、入队失败同步 fallback、任务本体调用实时加载和邮件投递 | 缺真实 worker/redis 集成或生产冒烟。 |
| 前台应用 | `js/src/forum` | `bias/frontend/src/forum`、`bias/frontend/src/components`、扩展 forum entry | partial | `bias/frontend/src/forum/*`、`HomePage.vue`、`Header.vue`、composer/runtime 文件存在；`bias/frontend/src/forum/extensionLoader.test.js` 覆盖 discussions/search bundled forum product routes，确认首页、讨论详情、创建讨论和搜索页能由扩展注册并解析到对应 Vue view；`npm run test:node` 可运行前端 Node 测试；`bias/frontend/e2e/forum-home.spec.js` 已用 Playwright 覆盖真实 Chromium + Vite runtime 下的首页讨论列表渲染、`/api/forum` 扩展装载、`/api/discussions/` 请求、`/d/:id` 链接，从首页点击进入讨论详情后请求 `/api/discussions/{id}` 和 `/api/discussions/{id}/posts?limit=20&near=1` 并渲染帖子流，已登录用户从讨论详情打开回复 composer、提交 `POST /api/discussions/{id}/posts` 并追加新回复，随后进入 `/notifications` 渲染由该回复触发的 `postReply` 通知和未读计数；未登录直达受保护创建页后登录并回到 composer，已登录用户直达 `/discussions/create`、等待 session 恢复、选择 tags、提交带 `relationships.tags.data` 的 `POST /api/discussions/`、跳转详情并渲染首帖，tags 首页 `/tags`、tag 详情 `/t/general`、tag 过滤讨论列表请求 `tag=general`，通知页 `/notifications`、通知列表请求、单条标记已读、清理已读确认流程、`type`/未读筛选刷新、当前筛选标记已读、单条删除和当前筛选清除已读，用户资料 `/profile`、头像上传、公开资料 `/u/{id}`、作者讨论/回复列表和资料保存，注册、忘记密码、邮箱验证、重置密码及对应失败路径，security 扩展 Turnstile 登录/注册挑战，以及搜索页 `/search?q=browser&type=all` 请求 `/api/search`、渲染讨论/帖子/用户分组结果并从搜索结果进入讨论详情；`bias/frontend/src/router/guards.test.js` 覆盖受保护路由等待 session 恢复后再判断登录态 | 继续补更多跨扩展组合浏览器流程。 |
| 后台应用 | `js/src/admin` | `bias/frontend/src/admin`、`bias_core.admin_*`、扩展 admin entry | partial | `bias/frontend/src/admin/views/*` 覆盖 dashboard/settings/extensions/permissions/mail/audit；`bias_core/tests/test_admin_extensions_api.py`、`test_admin_settings_api.py`、`test_admin_permissions.py`；`bias/frontend/e2e/admin-flags.spec.js` 覆盖真实 Chromium 后台 runtime 下 flags 扩展路由、页面配置、筛选 tab、处理 modal、`/api/admin/flags/{id}/resolve` 和处理后列表刷新；`bias/frontend/e2e/admin-tags.spec.js` 覆盖真实 Chromium 后台 runtime 下 tags 扩展路由、页面配置、创建顶级标签、创建子标签、编辑显示/发帖权限、刷新统计和删除标签；`bias/frontend/e2e/admin-extensions.spec.js` 覆盖真实 Chromium 后台 runtime 下从仪表盘进入扩展中心、列表状态、protected 扩展不可停用、非 protected 扩展详情页停用/启用、sync extensions、同步启用顺序、rebuild frontend、diagnostics/recovery/frontend asset 状态 | 继续补权限矩阵、用户管理和更多组合后台流程。 |
| 安装/更新 | `src/Install`、`src/Update` | `bias_core.management.commands.install_forum`、`migrate_extensions`、`sync_extensions`、`bias` project bootstrap | partial | `bias_core/src/bias_core/management/commands/install_forum.py`、`migrate_extensions.py`、`sync_extensions.py`；`bias_core/tests/test_bootstrap_config.py`、`test_extension_service.py` 有部分覆盖 | 缺全新 SQLite/PostgreSQL 安装、初始管理员、默认扩展安装启用、升级保留状态、非 editable 安装冒烟。 |
| 扩展管理 | `src/Extension`、`src/Extend` | `bias_core.extensions`、admin extensions API、frontend extension pages | partial | `bias_core/tests/test_admin_extensions_api.py`、`test_extension_service.py`、`test_extension_registry.py`、`test_extension_boundary.py`、`check_extension_workspace` gate 覆盖大量后端能力；`npm run check:platform` 覆盖 17 个官方扩展前端 source tree 同步、SDK package 和前端边界；`bias/frontend/e2e/admin-extensions.spec.js` 覆盖扩展中心浏览器闭环：列表、启停、protected 约束、sync/order/rebuild、diagnostics/recovery/frontend asset 状态 | 缺生成扩展 -> 打包 wheel -> 干净站点安装 -> 后台启停的完整 DX 流程。 |

## 阶段 2 完成条件

阶段 2 目前未完成。原因：

1. 上表所有核心领域均至少存在一个产品路径或测试证据缺口。
2. discussion/post 主流程尚未被明确 HTTP 集成测试证明。
3. 前台、后台、安装升级和扩展开发体验仍缺浏览器或打包级证据。

## 下一批实现任务

遵从“先解决主要矛盾”，阶段 2 之后应优先进入阶段 3 的主论坛 HTTP 流程，而不是继续增加平台抽象。

优先任务：

1. 扩展 discussion/post 的 HTTP 集成覆盖。
   - 已确认现有实现使用 `bias_core.resources` 自动路由，并由 `bias-ext-discussions`、`bias-ext-posts` 的 `handlers.py` 注册标准论坛路径。
   - 已新增 `bias_core/tests/test_forum_discussion_api.py` 覆盖列表、详情、帖子流、创建讨论和回复基础路径。
   - 已覆盖编辑、隐藏、恢复、删除、锁定、置顶和部分权限失败路径。
   - 已覆盖阅读状态和 `before`/`after`。
   - 已覆盖 approval queue approve/reject、pending/rejected discussion/post 和核心角色可见性矩阵。
   - 已补非 staff 用户持有 `discussion.lock` / `discussion.sticky` 后的 endpoint、PATCH 和锁定讨论回复行为。
   - 已补 rejected discussion/post 作者重新提交的 core 级 HTTP 证据。
   - 已补普通讨论列表 SQL 预算，避免标签状态和用户 primary group 序列化重复查询。
   - 已补搜索 all/discussions/posts 入口与隐藏、私有、pending、rejected 内容的角色可见性矩阵。
   - 已补搜索页浏览器主流程，覆盖分组结果渲染和搜索结果进入讨论详情。
   - 已补用户搜索 fields/include 组合，覆盖 `search_user.primary_group` 与 `include=groups` 同时序列化。
   - 已补 `bias_ext_search/backend/tests.py` 全量 62 个后端测试在 tags 启用条件下通过，覆盖搜索过滤语法、pagination 边界、created 月份过滤，以及 discussion 创建必须携带 tags relationship 的测试夹具。
   - 已补核心论坛 discussion/post 的 HTTP `fields[...]`、`include`、404/403 plain error 格式，并修复不存在或不可见 discussion 的 post stream 返回 200 空列表问题。
   - 已补 tags 前台浏览器主流程，覆盖 `/tags`、`/t/:slug`、tag 过滤讨论列表请求和创建讨论时 tags relationship payload。
   - 已补通知前台浏览器主流程，覆盖 `/notifications` 列表、单条标记已读、确认清理已读和清理后的空状态。
   - 已补用户资料前台浏览器主流程，覆盖 `/profile`、`/u/{id}`、作者讨论/回复列表、偏好加载和资料保存。
   - 已补认证与账号安全前台浏览器主流程，覆盖受保护路由登录回跳、注册、忘记密码、邮箱验证和重置密码；同时修复 AuthRouteView 认证成功后过早回首页导致 redirect 丢失的问题。
   - 已补通知筛选与删除前台浏览器主流程，覆盖 `type`/未读筛选刷新、当前筛选标记已读、单条删除和当前筛选清除已读。
   - 已补头像上传前台浏览器主流程，覆盖 profile 隐藏 file input 选择图片、`POST /api/users/{id}/avatar` multipart 请求和新头像渲染。
   - 已补账号安全失败路径前台浏览器主流程，覆盖登录失败、注册失败、邮箱验证失败、重置密码失败、邮箱重发失败和修改密码失败。
   - 已补人机验证浏览器矩阵，覆盖 security 扩展注册 Turnstile 挑战、登录/注册渲染挑战组件并提交 `human_verification_token`；同时修复 AuthSessionModal 因 token 更新触发挑战重置导致递归更新的问题。
   - 已补真实内容操作触发通知浏览器证据，覆盖讨论详情提交回复后生成 `postReply` 通知，并在通知页渲染新通知和未读计数。
   - 已补通知邮件/队列投递后端闭环，覆盖通知创建事件监听、Celery 任务、队列失败同步回退和通知邮件内容断言。
   - 已补 flags 后端组合证据，覆盖当前 tags 必填关系下的举报创建、后台队列列表/处理、前台版主处理、非 staff 拒绝和删除帖子清理举报。
   - 已补 flags/admin 浏览器证据，覆盖后台仪表盘进入举报队列、处理举报、刷新待处理列表、切换已处理 tab 并验证处理备注和处理人；同时修复浏览器构建中 `@bias/core/*` 指向 SDK 包副本导致后台 registry 写读分裂的问题。
   - 已补 tags/admin 浏览器证据，覆盖后台仪表盘进入标签管理、创建顶级标签、创建子标签、编辑隐藏/限制和权限范围、刷新统计、删除标签；同时修复 tags 后台操作按钮默认不可点击和删除成功后编辑 modal 残留的问题。
   - 已补 extensions/admin 浏览器证据，覆盖后台仪表盘进入扩展中心、扩展列表状态、protected 扩展不可停用、非 protected 扩展详情页停用/启用、sync extensions、同步启用顺序、rebuild frontend、diagnostics/recovery/frontend asset 状态；同时补上 `/admin/extensions` 核心后台路由。
   - 下一步继续补真实 Redis worker/生产冒烟。

2. 补全 HTTP 集成测试覆盖讨论列表。
   - `GET /api/discussions`
   - 排序：最新回复、最新发布、热门、未读、我的。
   - 过滤：搜索词、作者、未读，tags 过滤放到 tags 阶段补齐。
   - 默认 include：作者、最后回复、首帖摘要、阅读状态；tags include 在 tags 启用时覆盖。

3. 补全 HTTP 集成测试覆盖讨论详情和帖子流。
   - `GET /api/discussions/{id}`
   - `GET /api/discussions/{id}/posts`
   - `near`、`before`、`after` 或明确记录暂不支持项。

4. 补全 HTTP 集成测试覆盖创建和回复生命周期。
   - 创建讨论、编辑标题、编辑首帖、隐藏/恢复/删除。
   - 创建回复、编辑回复、隐藏/恢复/删除回复。

5. 新增角色可见性测试。
   - guest、registered user、discussion author、moderator、administrator。
   - 列表、详情、搜索结果的可见性必须一致。

完成以上任务后，再回到本矩阵把对应行从 `partial` 收敛到 `done` 或拆出剩余差异。
