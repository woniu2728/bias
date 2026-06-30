# Bias 对齐 Flarum 交付方案

状态：草案
日期：2026-06-30

## 目标

本文档定义 Bias 缩小与本地 Flarum 参照代码差距的具体交付方案。

参照代码位于：

```text
D:\files\project\tmp\flarum_code
```

目标不是只让 Bias “能用”，而是让 Bias 在核心论坛行为、官方扩展、后台运维、安装升级、测试稳定性、浏览器流程、扩展开发体验上都能被明确验收为接近这份 Flarum 参照实现。

当本文档里的所有验收门槛都通过后，剩余差距只能是：

- 生态成熟度；
- 长期生产环境验证；
- 社区扩展数量；
- 已明确记录的产品差异。

完成本文档后，不应再存在“核心架构差很多”或“核心论坛产品能力差很多”这种结论。

## 参照范围

Flarum 参照目录：

```text
D:\files\project\tmp\flarum_code\flarum
D:\files\project\tmp\flarum_code\flarum-core
D:\files\project\tmp\flarum_code\tags
```

Bias 实现范围：

```text
D:\files\project\tmp\bias
D:\files\project\tmp\bias_core
D:\files\project\tmp\bias-content
D:\files\project\tmp\bias-ext-*
```

## 完成定义

只有同时满足以下条件，才算完成本方案：

1. Flarum core 对齐矩阵已完成，所有非刻意差异项都为 `done`。
2. 官方扩展对齐矩阵已完成，所有非刻意差异项都为 `done`。
3. 所有测试门槛在干净工作区通过。
4. 浏览器端到端流程完整通过。
5. 扩展开发体验流程完整通过。
6. 安装、升级、打包、前端构建全部通过。
7. 所有剩余差异都被标记为 `intentionally different`，并写明原因。

## 差距标签

每个对齐项只能使用以下四种状态：

```text
done
partial
not implemented
intentionally different
```

定义：

- `done`：已实现、已测试、能通过正常产品路径使用。
- `partial`：有实现但不完整、不稳定、缺少后台/前端/API 覆盖，或缺少测试。
- `not implemented`：未实现。
- `intentionally different`：刻意不跟 Flarum 一样，并写明原因和替代行为。

规则：

- 任何阶段存在 `partial` 或 `not implemented` 时，不允许称该阶段完成。
- 除非该项被明确改为 `intentionally different`，并写明原因。

## 阶段 1：冻结架构边界

目标：让 `bias_core` 成为真正的平台内核，让产品基础域留在必装基础包里，并防止隐性依赖继续漂移。

必须完成：

1. 移除 `bias_core` 对站点工程的直接导入。
   - `bias_core` 不允许 import `config.*`。
   - 例如 `from config.celery import app` 必须改成通过 settings 间接加载。
   - 建议设置项：`BIAS_CELERY_APP = "config.celery:app"`。

2. 保持 `bias-content` 作为内容数据唯一拥有者。
   - `Discussion`、`Post`、`DiscussionUser` 由 `bias-content` 拥有。
   - `bias-ext-discussions` 和 `bias-ext-posts` 只做 UI/API/生命周期包装，不拥有真实数据模型。
   - 新的内容域行为默认进入 `bias-content`，除非另有文档说明。

3. 保持 `bias-ext-users` 或未来的 `bias-users` 作为用户域拥有者。
   - `bias_core` 不吸收用户、组、账号安全、权限分配等产品行为。
   - 如需改变该边界，必须先更新本文档。

4. 强制扩展 import 边界。
   - 扩展允许导入：
     - `bias_core.extensions`
     - `bias_core.extensions.platform`
     - `bias_core.extensions.runtime`
     - `bias_core.extensions.forum`
     - `bias_core.extensions.contracts`
     - `bias_core.extensions.sdk`
   - 扩展不允许导入 `bias_core` 内部模块。
   - 扩展不允许导入另一个扩展的内部模块。

验收命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py check
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json

cd D:\files\project\tmp\bias_core
rg "from config|import config|from bias_ext_|import bias_ext_" src\bias_core -g "*.py"
```

通过标准：

- `manage.py check` 无错误。
- `check_extension_workspace` 为 0 error、0 warning。
- `bias_core` 没有站点工程导入。
- `bias_core` 没有具体扩展导入。

## 阶段 2：Flarum Core 对齐矩阵

目标：明确对比 `flarum-core`，并关闭或记录所有核心产品差距。

需要新增并维护：

```text
docs/flarum-core-parity-matrix.md
```

当前状态：

- 矩阵文件已创建。
- 阶段 2 尚未完成；矩阵中仍有 `partial` 项，需先补阶段 3 的主论坛 HTTP 流程证据。

最少包含以下条目：

| 领域 | Flarum 参照 | Bias 归属 | 状态 | 必需证据 |
| --- | --- | --- | --- | --- |
| 用户模型 | `flarum-core/src/User` | `bias-ext-users` 或 `bias-users` | TBD | API、policy、admin、tests |
| 组和权限 | `flarum-core/src/Group`、policies | `bias-ext-users`、`bias_core` policy runtime | TBD | 权限矩阵测试 |
| 讨论模型 | `flarum-core/src/Discussion` | `bias-content` | TBD | API 和生命周期测试 |
| 帖子模型 | `flarum-core/src/Post` | `bias-content` | TBD | API 和生命周期测试 |
| API Resource | `flarum-core/src/Api/Resource` | `bias_core.resources`、extensions | TBD | JSON/API 集成测试 |
| Policy / Visibility | `flarum-core/src/*/Access` | `bias_core` + extensions | TBD | 角色可见性测试 |
| 搜索 | `flarum-core/src/Search` | `bias-ext-search`、runtime contracts | TBD | 讨论/帖子/用户/标签搜索测试 |
| 通知 | `flarum-core/src/Notification` | `bias-ext-notifications` | TBD | 通知 E2E 测试 |
| 设置 | `flarum-core/src/Settings` | `bias_core.settings_service` | TBD | 后台/API 测试 |
| 邮件 | `flarum-core/src/Mail` | `bias_core` services | TBD | 邮件驱动测试 |
| 队列 | `flarum-core/src/Queue` | `bias_core` services | TBD | 队列模式测试 |
| 前台应用 | `flarum-core/js/src/forum` | `bias/frontend/src/forum` | TBD | 浏览器 E2E |
| 后台应用 | `flarum-core/js/src/admin` | `bias/frontend/src/admin` | TBD | 浏览器 E2E |
| 安装/更新 | `flarum-core/src/Install`、`Update` | `bias_core` commands + `bias` project | TBD | 全新安装和升级冒烟 |
| 扩展管理 | `flarum-core/src/Extension` | `bias_core.extensions` | TBD | 扩展开发体验 gate |

必须完成：

1. 根据本地 Flarum 源码填完整矩阵。
2. 每个 `partial` 或 `not implemented` 都要拆出实现任务。
3. 每个 `intentionally different` 都要说明 Bias 为什么不同，以及替代行为是什么。
4. 矩阵里存在未处理的 `partial` 或 `not implemented` 时，本阶段不得完成。

## 阶段 3：核心论坛主流程完成

目标：先稳定论坛主链路，再继续扩展可选能力。

必须覆盖的流程：

1. 讨论列表。
   - `GET /api/discussions`
   - 排序：最新回复、最新发布、热门、未读、我的。
   - 过滤：标签、搜索词、作者、未读。
   - 默认 include：作者、最后回复、标签、首帖摘要、阅读状态。
   - 普通列表响应 SQL 数量必须在明确预算内。

2. 讨论详情。
   - `GET /api/discussions/{id}`
   - `GET /api/discussions/{id}/posts`
   - 支持 `near`、`before`、`after`，以及 offset/page fallback。
   - 隐藏、私有、待审核内容必须一致过滤。

3. 讨论创建和编辑。
   - 创建讨论。
   - 编辑标题。
   - 编辑首帖内容。
   - 隐藏、恢复、删除。
   - 如 Bias 支持锁定/置顶，也必须覆盖锁定、解锁、置顶、取消置顶。

4. 回复生命周期。
   - 创建回复。
   - 编辑回复。
   - 隐藏、恢复、删除回复。
   - 启用 approval 时，覆盖通过、拒绝、重新提交。

5. 阅读状态。
   - 标记单个讨论已读。
   - 标记全部已读。
   - 阅读进度不能倒退。
   - 订阅状态变化不能重置阅读进度。

角色覆盖：

```text
guest
registered user
discussion author
moderator
administrator
```

必需证据：

- 每条流程都有 HTTP 集成测试。
- 只测 service 不算完成。
- 测试必须断言状态码、响应结构、可见性行为和相关计数。

当前状态：

- 已在 `bias_core/tests/test_forum_discussion_api.py` 覆盖 discussion/post 主 HTTP 流程：列表、排序、过滤、详情、post stream `near/before/after`、创建、编辑、隐藏/恢复、删除、锁定、置顶、单讨论已读、全部已读。
- 已补 approval 主 HTTP 流程：待审核 discussion/reply、`/api/admin/approval-queue` 列表、通过 discussion、拒绝 reply，以及 pending/rejected discussion/post 对 guest、registered user、author、moderator、administrator 的可见性矩阵。
- 已补非 staff 用户持有 `discussion.lock` / `discussion.sticky` 后通过 endpoint、PATCH 操作锁定/置顶，并可在锁定讨论中回复的 HTTP 证据。
- 已补 rejected discussion/post 作者重新提交后回到 pending、清空审核备注、保持他人不可见并产生 resubmitted event post 的 core 级 HTTP 证据。
- 已补 `GET /api/discussions/?limit=6` 的列表 SQL 预算证据，覆盖含作者、最后回复用户、首帖摘要、标签和阅读状态的普通列表响应，并把查询数限制在 24 次以内。
- 已补 `/api/search` 的 all/discussions/posts HTTP 可见性矩阵，覆盖公开、隐藏、私有、pending、rejected discussion/post 对 guest、registered user、discussion author、approval author、post author、moderator、administrator 的一致过滤。
- 已补 `bias/frontend/src/forum/extensionLoader.test.js` 的 bundled forum product routes 证据，确认 discussions/search 扩展能把首页、讨论详情、创建讨论和搜索页注册到前台 router，并解析到对应 Vue view；新增 `npm run test:node` 作为前端 Node 测试入口。
- 已接入 Playwright 浏览器 E2E，并补 `bias/frontend/e2e/forum-home.spec.js` 覆盖真实 Chromium + Vite runtime 下的论坛首页：`/api/forum` 启用 users/discussions 扩展、装载扩展路由、请求 `/api/discussions/`、渲染讨论列表项并链接到 `/d/:id`；该 E2E 暴露并修复了 `App.vue` 对 `forumStore.settings` 的 deep watch 会遍历扩展 runtime 对象并触发 `Maximum call stack size exceeded` 的前台稳定性问题。
- 已补 Playwright 真实浏览器下从首页讨论列表点击进入讨论详情的闭环，验证 `/api/discussions/{id}`、`/api/discussions/{id}/posts?limit=20&near=1`、详情标题、帖子流正文、楼层编号和加载态退出。
- 已补 Playwright 真实浏览器下已登录用户在讨论详情打开回复 composer、提交回复到 `POST /api/discussions/{id}/posts`、关闭 composer 并把新回复追加进当前帖子流的闭环。
- 已补 Playwright 真实浏览器下已登录用户直达 `/discussions/create`、等待 session 恢复、打开 discussion composer、提交 `POST /api/discussions/`、跳转 `/d/{id}` 并渲染首帖的闭环；该 E2E 暴露并修复了受保护路由在 session 恢复前误判未登录、导致直达创建页弹登录并回首页的前台认证时序问题。
- 已补 Playwright 真实浏览器下搜索页 `/search?q=browser&type=all` 主流程，覆盖 search 扩展路由装载、`GET /api/search?q=browser&type=all&page=1&limit=20`、讨论/帖子/用户分组结果渲染、搜索统计、加载态退出，并从讨论搜索结果点击进入 `/d/101` 详情；该 E2E 暴露并修复了 `SearchResultCard.vue` 把 `computed` import 放在 `<script setup>` 外导致结果卡片渲染时报 `computed is not defined` 的前台稳定性问题。
- 已补 search/user 资源 include 细节：`bias-ext-users` 声明 `search_user.groups` relationship，`bias-ext-search` 的 `/api/search?type=users&include=groups` 现在把 include 传入资源序列化，并用 HTTP 测试覆盖 `fields[search_user]=primary_group&include=groups` 同时返回 `primary_group` 和 `groups`。
- 已补 `bias_ext_search/backend/tests.py` 全量后端测试证据：在 tags 扩展启用且创建 discussion 必须带 tags relationship 的条件下，搜索后端 62 个测试通过；搜索测试夹具统一注入 tag relationship payload，并把 `created:YYYY-MM` 过滤断言切到本地时区语义。
- 已补核心论坛 HTTP resource 格式证据：`bias_core/tests/test_forum_discussion_api.py` 覆盖 discussion list/detail 与 post stream/detail 的 `fields[...]` + `include` 组合，以及 discussion/post 404、403 plain error 格式；同时修复 `/api/discussions/{id}/posts` 在 discussion 不存在或不可见时误返回 200 空列表的问题，改为与 discussion detail 一致的 404 `讨论不存在`。
- 已补 Playwright 真实浏览器下 tags 前台主流程：`/tags` 加载 `GET /api/tags?include_children=true` 并渲染主标签、子标签和二级标签；`/t/general` 加载 tag detail，并让讨论列表请求携带 `tag=general`；从 tag 页面发起讨论时 composer 自动带入主标签、选择次标签，并断言 `POST /api/discussions/` payload 写入 `relationships.tags.data`。
- 已补 Playwright 真实浏览器下通知页主流程：`/notifications` 加载 `GET /api/notifications` 并渲染 reply/account 通知；单条通知点击“标记为已读”触发 `POST /api/notifications/{id}/read`；确认“当前页清除已读”触发 `DELETE /api/notifications/read/clear`，并验证清理后的空状态。
- 已补 Playwright 真实浏览器下通知筛选与删除主流程：`type=postReply` 筛选刷新列表，`state=unread` 让 `GET /api/notifications` 携带 `is_read=false`；当前筛选标记已读触发 `POST /api/notifications/read-filtered?type=postReply`；单条删除触发 `DELETE /api/notifications/{id}` 并显示筛选空状态；账号通知筛选后当前筛选清除已读触发 `DELETE /api/notifications/read/clear-filtered?type=userSuspended`。
- 已补 Playwright 真实浏览器下用户资料主流程：`/profile` 加载 `GET /api/users/me`、作者讨论列表、作者回复列表和 `GET /api/users/me/preferences`；选择头像图片后断言 `POST /api/users/{id}/avatar` multipart 请求并渲染新头像；设置页保存资料时断言 `PATCH /api/users/{id}` payload；公开 `/u/{id}` 加载他人资料和作者讨论，且不显示自己的设置入口。
- 已补 Playwright 真实浏览器下认证与账号安全主流程：未登录直达 `/discussions/create` 会打开登录 modal，登录 `POST /api/users/login` 后保留 redirect 并回到 composer；注册断言 `POST /api/users/register` payload；忘记密码断言 `POST /api/users/forgot-password` 并显示 debug reset link；`/verify-email?token=...` 触发 `POST /api/users/verify-email`；`/reset-password?token=...` 触发 `POST /api/users/reset-password`。同时修复 AuthRouteView 在认证成功时过早 `replace('/')` 导致 redirect 丢失的问题，并用 `bias-ext-users/frontend/forum/useAuthRoutePage.test.js` 覆盖。
- 已补 Playwright 真实浏览器下账号安全失败路径：登录失败显示 `用户名或密码错误` 并清空密码；注册密码确认不一致不发请求，邮箱占用显示后端错误；无效邮箱验证 token 和无效重置密码 token 显示错误；Profile 安全页覆盖邮箱重发失败、修改密码确认不一致和旧密码错误。
- 已补 Playwright 真实浏览器下人机验证流程：`/api/forum` 启用 security 扩展和 Turnstile 设置后，登录/注册 modal 渲染 Turnstile 挑战组件，并断言 `POST /api/users/login`、`POST /api/users/register` payload 携带 `human_verification_token`。该 E2E 暴露并修复了 AuthSessionModal 在 token 更新后重新计算 challenge provider、触发 reset、导致 `Maximum recursive updates exceeded` 的前台稳定性问题。
- 已补 Playwright 真实浏览器下真实内容操作触发通知流程：讨论详情提交 `POST /api/discussions/{id}/posts` 成功追加回复后，通知 fixture 生成新的 `postReply` 通知；随后进入 `/notifications`，断言新通知和未读计数被渲染。
- 已补通知邮件/队列投递后端闭环：`bias-ext-notifications` 注册 `NotificationCreatedEvent` 监听器，通知创建后派发 `dispatch_notification_batch`；Celery 任务执行实时通知加载和 `EmailService` 通知邮件发送；测试覆盖队列启用入队、入队失败同步 fallback、通知邮件 subject/body/link、无邮箱收件人跳过，并让通知测试夹具适配 tags 必填关系。
- 已补 flags 后端组合证据：`bias-ext-flags` 测试夹具适配当前 tags 必填关系后，后端测试覆盖 `POST /api/posts/{id}/report` 创建举报、`/api/admin/flags` 后台队列列表、`/api/admin/flags/{id}/resolve` 后台处理、讨论页版主 `/api/posts/{id}/flags/resolve` 处理、非 staff 拒绝、删除帖子清理举报和对应事件。
- 阶段 3 的后端主流程已进一步收敛；剩余风险转向真实 Redis worker/生产冒烟、flags/admin 浏览器证据和更多跨扩展浏览器矩阵。

## 阶段 4：官方扩展对齐矩阵

目标：把 Bias 官方扩展与 Flarum 官方扩展行为逐项对齐，关闭所有非刻意差异。

需要新增并维护：

```text
docs/flarum-bundled-extension-parity-matrix.md
```

最少纳入：

```text
bias-content
bias-ext-users
bias-ext-discussions
bias-ext-posts
bias-ext-tags
bias-ext-likes
bias-ext-flags
bias-ext-mentions
bias-ext-subscriptions
bias-ext-approval
bias-ext-notifications
bias-ext-search
bias-ext-realtime
bias-ext-uploads
bias-ext-security
```

必须覆盖组合场景：

1. 发帖时选择 tags。
2. 回复讨论触发通知。
3. mention 用户触发通知。
4. like 帖子后更新通知和计数。
5. flag 帖子后进入后台队列。
6. approval 让待审核讨论/回复在通过前不可见。
7. search 能搜索讨论、帖子、用户、标签。
8. realtime 更新讨论/帖子/标签状态时不破坏当前页面状态。
9. subscriptions 产生关注/取消关注状态和通知行为。
10. uploads/security 启用时，权限和存储设置可用。

通过标准：

- 每个官方扩展都有 manifest、backend entry、必要的 frontend entry、测试、后台入口和权限声明。
- 用户可见的组合场景必须有 HTTP/API 测试和浏览器测试。
- optional dependency 必须声明并被运行时正确处理。

## 阶段 5：Tags 对齐 Flarum Tags

目标：让 `bias-ext-tags` 在功能上可对标 `flarum/tags`。

参照：

```text
D:\files\project\tmp\flarum_code\tags\extend.php
D:\files\project\tmp\flarum_code\tags\src
D:\files\project\tmp\flarum_code\tags\js\src
D:\files\project\tmp\flarum_code\tags\tests
```

后端必须对齐：

1. 标签模型。
   - 主标签和次标签。
   - 父子标签。
   - 排序。
   - slug driver 行为。
   - color、icon、description。
   - discussion count。
   - last posted discussion/user 元数据。

2. 标签约束。
   - 最小主标签数。
   - 最大主标签数。
   - 最小次标签数。
   - 最大次标签数。
   - 指定标签下是否可发帖。
   - 指定标签下是否可回复或加入讨论。

3. API 集成。
   - forum resource 暴露代表性 tags。
   - discussion resource 默认 include tags。
   - post resource 支持 tag-change event post 关系。
   - `/tags/order` 可用且有权限保护。

4. policy 和 visibility。
   - 隐藏标签影响讨论可见性。
   - 标签可见性遵守用户权限。
   - 标签相关讨论过滤一致生效。

5. 搜索和实时。
   - tag search target 可用。
   - discussion tag filter 可用。
   - 启用 realtime 时，tag change 会广播。

前端必须对齐：

1. tags 首页。
2. 单个 tag 页面。
3. 讨论列表 tag 过滤/导航。
4. 发帖 composer tag 选择器。
5. 讨论列表 tag labels。
6. 讨论详情/侧边栏 tag 展示。
7. 后台 tag 管理。

通过标准：

- 从 Flarum Tags `extend.php` 派生出的 checklist 全部完成。
- 每个 Flarum extender 行为都有 Bias 等价实现，或标记为 `intentionally different`。
- `bias-ext-tags` 测试通过。

## 阶段 6：后台运维闭环

目标：正常论坛运维不需要直接改数据库或手动跑命令。

必须完成的后台区域：

1. 扩展管理。
   - 扩展列表。
   - 启用/禁用非 protected 扩展。
   - protected 扩展不允许禁用。
   - 展示依赖和 optional dependency 状态。
   - sync extensions。
   - rebuild frontend。
   - 展示 diagnostics 和 recovery state。

2. 用户和权限。
   - 用户列表。
   - 用户详情。
   - 组管理。
   - 权限矩阵。
   - 封禁/解封。
   - 邮箱验证状态。
   - 账号/安全操作。

3. 内容审核。
   - 待审核讨论。
   - 待审核回复。
   - flags 队列。
   - 通过、拒绝、恢复、隐藏、删除操作。

4. 标签。
   - 创建、编辑、删除。
   - 重排。
   - 父子关系管理。
   - 权限和约束。

通过标准：

- 每个后台区域都有 route、UI、API、权限检查、加载态、空态、错误态。
- 常用后台操作有浏览器 E2E 覆盖。

## 阶段 7：前端产品完成

目标：让 Bias 像一个完整论坛产品，而不是只有后端和扩展 hook。

前台必须完成：

1. 首页讨论列表。
   - 加载态、空态、错误态。
   - 分页或无限加载。
   - tag 过滤。
   - 搜索入口。
   - 登录/未登录差异。

2. 讨论详情。
   - 帖子流。
   - 回复 composer。
   - 编辑、删除、隐藏、恢复操作。
   - 楼层导航或 scrubber。
   - realtime 更新不破坏阅读位置。

3. Composer。
   - 创建讨论。
   - 选择 tags。
   - 回复。
   - 编辑已有帖子。
   - 校验错误展示。

4. 用户区域。
   - 资料页。
   - 活动/内容列表。
   - 设置。
   - 安全。
   - 通知偏好。

5. 通知。
   - 通知下拉或通知页。
   - 未读数。
   - 标记已读。
   - reply、mention、like、tag、approval、flag 相关通知。

通过标准：

- 浏览器 E2E 覆盖上述前台流程。
- 前端 build 通过。
- 主导航中没有 broken page 或只有占位内容的页面。

## 阶段 8：安装、升级、打包

目标：Bias 可以不用 editable source install 就完成安装和升级。

安装必须支持：

1. 全新 SQLite 安装。
2. 全新 PostgreSQL 安装。
3. 创建初始管理员。
4. 默认安装并启用必需扩展。
5. 写入初始权限和设置。

升级必须支持：

1. 跑数据库迁移。
2. 同步扩展安装记录。
3. 同步扩展顺序。
4. rebuild frontend。
5. 校验版本兼容。
6. 保留已有设置和已启用扩展状态。

打包必须支持：

1. `bias-core` wheel。
2. `bias-content` wheel。
3. 官方 `bias-ext-*` wheels。
4. 前端 SDK package。
5. 扩展 wheel 必须包含：
   - `extension.json`；
   - backend entry point；
   - Django app 和 migrations；
   - frontend resources 或 frontend manifest；
   - 与 manifest 对齐的 package metadata。

验收命令：

```powershell
cd D:\files\project\tmp\bias_core
python -m build

cd D:\files\project\tmp\bias-content
python -m build

cd D:\files\project\tmp\bias-ext-tags
python -m build

cd D:\files\project\tmp\bias\frontend
npm run build
```

通过标准：

- 上述构建全部通过。
- 在新目录中使用构建产物做一次全新安装冒烟。
- 冒烟安装不能依赖 editable install。

## 阶段 9：全量测试门槛

目标：消除“部分测试失败但先忽略”的不确定性。

必须执行：

```powershell
cd D:\files\project\tmp\bias_core
python -m pytest

cd D:\files\project\tmp\bias-content
python -m pytest

cd D:\files\project\tmp\bias-ext-tags
python -m pytest

cd D:\files\project\tmp\bias
python manage.py check
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json

cd D:\files\project\tmp\bias\frontend
npm run check:platform
npm run build
```

通过标准：

- 所有 pytest 通过。
- Django system check 通过。
- 扩展 workspace 检查 0 error、0 warning。
- 前端 platform check 通过。
- 前端 build 通过。
- 测试不依赖或污染真实兄弟扩展目录，除非该测试明确是在测 workspace discovery。
- 临时测试目录不能泄漏到工作区。

## 阶段 10：浏览器 E2E 门槛

目标：用真实用户和管理员流程验证产品，而不是只验证孤立 API。

必须覆盖完整浏览器流程：

1. 安装或初始化站点。
2. 创建管理员。
3. 注册普通用户。
4. 普通用户登录。
5. 创建讨论。
6. 选择 tags。
7. 回复讨论。
8. 编辑回复。
9. like 帖子。
10. mention 另一个用户。
11. 收到并读取通知。
12. flag 内容。
13. 管理员登录。
14. 管理员处理 flag。
15. 管理员处理待审核讨论/回复。
16. 搜索讨论。
17. 搜索 tag。
18. 打开用户资料页。
19. 禁用一个非 protected 扩展。
20. rebuild frontend。
21. 重新加载前台和后台页面。

通过标准：

- 全流程通过自动化浏览器测试。
- 没有未捕获前端异常。
- 除了刻意测试的失败请求外，没有失败 API 请求。
- rebuild 后页面刷新仍然可用。

## 阶段 11：扩展开发体验门槛

目标：让 Bias 扩展开发体验在实际工作流上可对标 Flarum。

必须覆盖：

1. 使用生成器创建新扩展。
2. 生成的后端只导入公开 `bias_core.extensions.*` API。
3. 生成的前端只导入公开 `@bias/core` API。
4. manifest 和 package metadata 可同步。
5. 扩展校验通过。
6. 扩展可打成 wheel。
7. wheel 包含 manifest、backend entry point、Django app、migrations、frontend resources。
8. wheel 可安装到干净站点环境。
9. 站点能发现该扩展。
10. 后台可启用和禁用该扩展。
11. 扩展能注册至少一个 API route 或 resource field。
12. 扩展能注册至少一个 admin 或 forum 前端 surface。
13. 自动检查能拒绝：
    - 导入 `bias_core` 内部模块；
    - 导入另一个扩展的内部模块；
    - 未声明的 runtime facade 依赖；
    - 前端导入宿主内部文件。

验收命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py create_extension alpha-tools --target D:\files\project\tmp\.tmp-extension-dx
python manage.py validate_extensions --extensions-path D:\files\project\tmp\.tmp-extension-dx
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp\.tmp-extension-dx --check-runtime-facades --format json
```

通过标准：

- 生成的扩展可打包、可安装。
- 安装后的扩展能被站点发现。
- 启用/禁用生命周期可用。
- 边界违规能被自动检查抓住。

## 最终对齐报告

所有阶段通过后，必须产出：

```text
docs/flarum-parity-final-report.md
```

报告必须包含：

1. Flarum core 对齐矩阵总结。
2. 官方扩展对齐矩阵总结。
3. 测试命令结果。
4. 浏览器 E2E 结果。
5. 扩展开发体验结果。
6. 安装和升级冒烟结果。
7. 剩余 `intentionally different` 项。
8. 剩余风险。

完成后允许存在的剩余风险：

- Flarum 生态和社区扩展更多。
- Flarum 有更长的生产环境历史。
- Bias 因为使用 Django/Vue，而不是 PHP/Mithril，内部实现可以不同。
- 部分产品行为可以刻意不同，但必须有文档记录。

完成后不允许继续作为剩余风险的事项：

- 缺少核心 discussion/post/user/tag 流程。
- 安装或升级不可用。
- 核心测试失败。
- 前端 build 失败。
- 扩展生成器不可用。
- 未记录的核心行为差距。
- runtime facade 依赖环。
- `bias_core` 依赖站点工程代码。
- 官方扩展绕过公开 contract，直接导入彼此内部模块。

## 执行规则

除非满足以下条件之一，否则不要继续增加平台抽象：

1. 某个对齐项不增加该抽象就无法完成。
2. 某个边界 gate 不增加该抽象就无法通过。
3. 浏览器 E2E 或扩展开发体验 gate 明确需要。
4. 该抽象能替换至少两个官方扩展里的重复工作代码。

优先级固定为：

```text
对齐证据 -> 产品流程 -> 测试 -> 打包 -> 抽象清理
```
