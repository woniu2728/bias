# Bias Forum Development Roadmap

## 背景

Bias 当前已经具备论坛产品的主体能力：讨论、回复、标签、权限、审核、举报、通知、搜索、后台、上传、Markdown、队列、缓存、WebSocket 等基础模块都已经存在。

结合当前 Bias 源码与 Flarum 2.x 源码对比，Bias 的核心问题已经不是“有没有功能”，而是“这些功能是否建立在论坛平台化底座之上”。

当前差距主要在以下几个方面：

- Flarum 是可扩展论坛平台，Bias 目前更像功能完整的论坛应用。
- Flarum 有稳定的后端 Extend/Resource/Policy/Search 注册体系，Bias 目前主要依赖手写 REST endpoint + service。
- Flarum 前端有统一的 Store、列表状态、帖流状态、Composer 状态和扩展注入点，Bias 的页面状态还偏分散。
- Flarum 的帖子流不仅承载评论，还承载改标题、改标签、锁定、置顶等事件语义，Bias 当前 `Post.type` 还没有真正成为论坛事件系统。
- Bias 后台和运维能力已经很强，但前台论坛交互抽象、扩展机制和一致性还不够平台化。

后续开发不应继续按“功能点堆叠”推进，而应改为：

- 以扩展体系为主线；
- 以事件系统、Resource API、前端资源层为中轴；
- 在做扩展体系时并行补 UI、交互、性能与运营能力。

## 总目标

把 Bias 从“功能完整的论坛源码”升级为“可扩展、可维护、性能稳定、体验顺滑的论坛平台”。

本路线图的总原则：

- 扩展优先：优先建立模块注册、事件分发、能力注入、前后端扩展接口。
- 底座先行：Resource API、前端 Resource Store、统一分页状态、统一错误格式必须尽早落地。
- 并行演进：UI、交互、性能、搜索、运营能力不再单独排在后面，而是在每个扩展阶段并行完成。
- 论坛优先：所有抽象必须优先服务论坛场景，而不是泛后台系统抽象。

## 设计原则

### 1. 以扩展为核心，不再以页面为核心

今后的主问题不是“讨论页还差什么按钮”，而是：

- 新模块如何注册自己的权限？
- 新模块如何给 Discussion/Post/User/Tag 增加字段和关系？
- 新模块如何注册搜索过滤器？
- 新模块如何注入后台页面和前台交互？
- 新模块如何消费领域事件，而不直接侵入主流程？

### 2. 以事件和资源协议替代手工耦合

今后通知、搜索索引、统计刷新、实时广播、时间线事件都应优先通过领域事件驱动，而不是在 service 里同步散落调用。

今后 API 返回格式要优先走统一 Resource 协议，而不是每个 endpoint 手工拼 response。

### 3. 在做扩展底座时同步修体验

扩展体系不是纯后端工作。做扩展时必须同步推进：

- Composer 重构；
- 帖子流状态抽象；
- 前端资源缓存；
- 列表与详情一致性；
- 模块化后台；
- 实时更新和论坛事件时间线。

## 总体执行顺序

1. 先做阶段 0，修生产风险和并发问题，避免后面重构建立在不稳定基础上。
2. 立即进入阶段 1，把扩展/模块化底座作为主线启动。
3. 阶段 2 同步建立 Resource API 和前端 Resource Store，为扩展体系提供统一数据面。
4. 阶段 3 用扩展体系改造现有内置功能，并同步完成论坛事件流和核心 UI/交互重构。
5. 阶段 4 再升级搜索、长讨论、实时能力，因为这三者都需要建立在资源层和事件层之上。
6. 阶段 5 做后台模块中心、主题、国际化和平台化收口。

## 阶段 0：生产稳定性与安全基线

目标：先解决会影响生产使用的风险，为后续扩展化重构提供稳定基础。

优先级：P0

### 任务

- 修复回帖楼层并发问题。
  - 当前回帖通过查询最后楼层再 `+1`，高并发同一讨论回复时存在唯一约束冲突风险。
  - 建议在事务中锁定 `Discussion` 行，或在 `Discussion` 增加 `next_post_number` 并使用数据库原子递增。
  - 保留 `posts(discussion_id, number)` 唯一约束。
  - 增加并发回帖测试。

- 限制分页参数。
  - 所有列表接口统一限制 `page >= 1`。
  - 所有 `limit` 统一设置上限，例如 50 或 100。
  - 搜索深页要限制或降级。

- 强化生产环境缓存与队列约束。
  - 生产环境应强制 Redis，`LocMemCache` 只用于开发。
  - 后台展示 Redis、队列、WebSocket、失败任务数、队列延迟。
  - 队列不可用时给出明确告警。

- 改进认证安全。
  - 短期缩短 access token 生命周期，增加 CSP。
  - 中期把 access token 从 `localStorage` 迁出，改为 HttpOnly Cookie。
  - API 需要匹配 CSRF 策略。

- 图标资源本地化。
  - 当前前端依赖 Font Awesome CDN。
  - 改为本地打包或统一 Icon 组件，减少外部依赖和首屏阻塞。

### 验收标准

- 并发回帖测试稳定通过。
- 所有分页接口都有统一上限。
- 生产环境缺少 Redis 或队列异常时后台有明确风险提示。
- 前端不再依赖外部 Font Awesome CDN。

## 阶段 1：扩展核心底座

目标：建立 Bias 自己的模块/扩展注册体系，作为后续一切演进的主轴。

优先级：P0

这是当前最优先的阶段，其他改进都以它为中心并行推进。

### 任务

- 建立模块注册中心。

先支持内置模块，不急着做第三方在线安装。

建议目标能力：

```python
forum_registry.register_module(...)
forum_registry.register_permission(...)
forum_registry.register_resource(...)
forum_registry.register_serializer_field(...)
forum_registry.register_search_filter(...)
forum_registry.register_notification_type(...)
forum_registry.register_admin_page(...)
forum_registry.register_forum_nav(...)
forum_registry.register_post_type(...)
forum_registry.register_event_listener(...)
```

- 明确模块边界。

先把现有内置能力按模块定义边界：

- core
- tags
- likes
- flags
- approval
- subscriptions
- notifications
- realtime
- mentions
- users

要求每个模块最少具备：

- 模块元信息；
- 依赖声明；
- 启用状态；
- 权限注册；
- API/Resource 注入点；
- 前端注入点；
- 后台配置入口；
- 事件监听注册入口。

- 建立模块生命周期。

需要支持：

- bootstrap
- register
- ready
- optional teardown 或 disable hooks

短期允许只做“启动时静态加载 + 配置启用禁用”，但结构上要为以后动态模块化留口子。

- 权限注册化。

当前权限码仍偏硬编码。

改造目标：

- 模块自行注册权限项；
- 权限页根据 registry 渲染；
- group 默认权限同步逻辑可按模块提供；
- 标签权限、审核权限、运营权限和扩展权限能统一接入。

- 后台模块中心基础页。

后台新增模块页，先支持内置模块展示：

- 名称；
- 描述；
- 版本；
- 启用状态；
- 依赖；
- 提供的权限；
- 提供的后台页面；
- 数据迁移状态；
- 配置入口链接。

### 并行任务：前端扩展注入基础

- 建立前台注册中心。

建议能力：

```js
forumRegistry.registerRoute(...)
forumRegistry.registerHeaderItem(...)
forumRegistry.registerDiscussionAction(...)
forumRegistry.registerPostAction(...)
forumRegistry.registerComposerExtension(...)
forumRegistry.registerSearchSource(...)
forumRegistry.registerNotificationRenderer(...)
forumRegistry.registerAdminNavItem(...)
```

- 把现有 header、discussion menu、post menu、profile tabs、admin navigation 改成注册式渲染，而不是纯手写固定结构。

### 并行任务：扩展优先下的 UI/交互修正

- 在做注入式前端时，同步收紧 UI 一致性。
  - 减少页面级硬编码颜色和块样式。
  - 统一 token 使用。
  - 把论坛首页和讨论页收回到“内容优先”的论坛信息架构。

- 把讨论列表、帖子菜单、标签展示、用户徽章全部组件化并支持模块扩展。

### 验收标准

- 至少 `tags`、`likes`、`flags`、`approval` 四个内置模块通过 registry 注册。
- 权限页不再依赖手工写死权限清单。
- 后台已有可用的模块中心基础页。
- 前台 discussion/post/header/admin 导航具备基础扩展注入能力。

## 阶段 2：领域事件系统与 Resource API

目标：用事件和统一资源协议替代当前大量手工耦合调用。

优先级：P0-P1

这是扩展体系真正落地的平台层。

### 任务

- 建立领域事件系统。

建议第一批事件：

- `DiscussionStarted`
- `DiscussionUpdated`
- `DiscussionDeleted`
- `DiscussionHidden`
- `DiscussionRestored`
- `DiscussionTagged`
- `DiscussionLocked`
- `DiscussionUnlocked`
- `DiscussionPinned`
- `DiscussionUnpinned`
- `DiscussionApproved`
- `DiscussionRejected`
- `PostCreated`
- `PostUpdated`
- `PostDeleted`
- `PostApproved`
- `PostRejected`
- `PostLiked`
- `PostUnliked`
- `PostFlagged`
- `UserSuspended`
- `UserUnsuspended`

- 迁移当前直接耦合调用。

当前下列逻辑应优先改成事件监听驱动：

- 通知发送；
- 标签统计刷新；
- 搜索索引同步；
- 实时广播；
- 审计补充逻辑；
- 论坛事件时间线记录。

- 建立 Resource 层。

建议形态：

```python
class DiscussionResource:
    type = "discussions"
    fields = [...]
    relationships = [...]
    includes = [...]
    filters = [...]
    sorts = [...]
```

支持：

- `include=user,tags,last_post`
- `fields[discussions]=title,slug,comment_count`
- `sort=-last_posted_at`
- `filter[tag]=python`
- `filter[q]=keyword`

- 统一序列化。

优先替换：

- Discussion list/detail
- Post list/detail
- User summary/detail
- Tag list
- Notification list

- API 错误格式统一。

建议统一：

- `code`
- `message`
- `field_errors`
- `permission`
- `request_id`

### 并行任务：论坛事件流

- 基于领域事件建立“Event Post”基础能力。

先让以下操作进入讨论时间线：

- 改标题；
- 改标签；
- 锁定/解锁；
- 置顶/取消置顶；
- 审核通过/拒绝；
- 隐藏/恢复。

这一步非常关键，因为它会真正把 `Post.type` 从预留字段升级为论坛语义模型。

### 并行任务：后台与扩展联动

- 模块可以注册自己的：
  - 后台设置页；
  - 后台卡片；
  - 后台统计项；
  - 审核/运营入口。

### 验收标准

- 通知、标签统计、搜索索引、实时广播至少有一半以上通过事件监听驱动。
- Discussion/Post/User/Tag/Notification 已切换到统一 Resource 响应。
- 讨论时间线已能显示至少 4 类事件型帖子。
- 新模块能通过 Resource/事件层接入，而不是直接改核心 service。

## 阶段 3：前端 Resource Store、Composer 内核与论坛状态层

目标：建立前端统一资源层和论坛状态层，为扩展、实时、长讨论、搜索打基础。

优先级：P1

### 任务

- 建立前端 Resource Store。

建议能力：

```js
resourceStore.upsert('users', user)
resourceStore.get('discussions', id)
resourceStore.mergePayload(payload)
resourceStore.remove('posts', id)
```

收益：

- 列表、详情、搜索、通知共享用户/讨论/帖子/标签数据；
- 模块新增字段更容易联动；
- 实时更新可以直接 merge payload；
- 减少重复 normalize 和重复请求。

- 建立通用列表/分页状态。

建议抽象：

- `usePaginatedResourceList`
- `useCursorResourceList`
- `useSearchResourceList`
- `useDiscussionListState`
- `useNotificationListState`

- 重构 Composer 公共逻辑。

当前 `DiscussionComposer.vue` 和 `PostComposer.vue` 功能接近，重复较多。

建议拆为：

- `useComposerEditor`
- `useComposerDraft`
- `useComposerPreview`
- `useComposerUpload`
- `useComposerMentions`
- `useComposerEmoji`
- `useComposerViewport`
- `useComposerSubmit`

- 建立 Composer 扩展点。

支持模块注册：

- 额外按钮；
- 插入工具；
- mention provider；
- preview transformer；
- 提交前校验；
- 提交后处理；
- 草稿元信息。

- 建立论坛级状态层。

优先统一：

- discussion list state
- discussion detail state
- post stream state
- notification state
- global search state
- composer state

减少页面内 `window` 事件散落耦合。

### 并行任务：UI 与交互修正

- 建立统一动画 token。

```css
--motion-fast: 120ms;
--motion-base: 180ms;
--motion-slow: 260ms;
--ease-standard: cubic-bezier(.2, 0, 0, 1);
--ease-emphasized: cubic-bezier(.2, 0, 0, 1);
```

- Composer 动画优化。
  - 打开时从底部 slide-up。
  - 最小化时做高度收缩。
  - 全屏展开增加过渡。
  - 发布成功后先收起 Composer，再跳转或更新帖子流。
  - 上传、预览、提及搜索、emoji 面板使用统一 loading 和错误反馈。

- 讨论列表体验优化。
  - 桌面端标题允许两行。
  - 未读状态增加左侧细条或未读点。
  - 统计区固定宽度，避免挤压标题。
  - 标签文字根据背景自动计算对比色。
  - 首页减少大面积 hero，把空间还给讨论流。

- 搜索弹层命令面板化。
  - 顶部搜索框点击后打开搜索弹层。
  - 即时展示讨论、帖子、用户、标签。
  - 支持键盘上下选择和 Enter 打开。
  - 空状态展示热门标签、最近搜索、搜索语法提示。

### 验收标准

- 前端列表、详情、搜索、通知共享统一 Resource Store。
- Composer 讨论/回复核心逻辑完成合并。
- 新模块可以给 Composer 注入按钮和能力。
- 列表和详情页 UI 一致性明显提升。
- 搜索弹层支持键盘操作。

## 阶段 4：内置模块迁移与论坛体验重构

目标：用扩展体系重新承载现有核心能力，同时把论坛体验做成真正的平台能力。

优先级：P1

### 任务

- 内置模块逐步迁移到注册体系。

迁移顺序建议：

1. tags
2. likes
3. flags
4. approval
5. subscriptions
6. notifications
7. mentions
8. realtime

要求每个模块都改为：

- 注册自己的权限；
- 注册自己的资源字段；
- 注册自己的前端入口；
- 注册自己的后台设置；
- 注册自己的事件监听器；
- 注册自己的搜索过滤器；
- 注册自己的通知类型和渲染器。

- 标签模块升级。

在迁移 tags 时同步补：

- 主标签/次标签约束抽象；
- 标签权限说明；
- 标签页信息架构优化；
- 标签关注；
- 标签统计刷新状态可视化；
- 标签样式更统一。

- 审核/举报模块升级。

在迁移 approval 与 flags 时同步补：

- 审核原因模板；
- 批量审核；
- 用户历史内容侧栏；
- 审核后自动通知；
- 重复违规计数；
- 举报处理动作与帖子时间线联动。

- 订阅与通知模块升级。

在迁移 subscriptions 与 notifications 时同步补：

- 更清晰的关注/忽略语义；
- 通知聚合；
- 通知类型 renderer 注册化；
- 列表局部刷新；
- 当前页面的轻量更新。

### 并行任务：个人页与移动端

- 个人页结构调整为论坛式信息密度。
  - 活动流优先于设置卡片感。
  - 讨论/回复/最近活动共享资源层。

- 移动端详情页重构。
  - 增加底部操作条：回复、关注、分享、更多。
  - 管理动作放入更多菜单。
  - Composer 打开后进入专注编辑模式，隐藏论坛导航。

### 验收标准

- 至少 6 个核心内置模块完成注册体系迁移。
- 模块不再依赖直接改核心页面才能接入。
- 审核、举报、标签、订阅、通知在前后台都体现为模块化能力。
- 移动端详情页主路径更清晰。

## 阶段 5：长讨论、搜索与实时系统升级

目标：在扩展底座完成后，把论坛高频体验做成平台能力。

优先级：P1-P2

### 任务 A：长讨论 PostStream 升级

- 实现帖子窗口化加载。

建议接口：

```text
GET /api/discussions/:id/posts?near=123&limit=20
GET /api/discussions/:id/posts?before=123&limit=20
GET /api/discussions/:id/posts?after=123&limit=20
```

返回内容：

- 当前窗口帖子；
- 是否有前文；
- 是否有后文；
- 当前楼层索引；
- 总楼层数。

- 前端实现统一 `useDiscussionPostStream`。
  - 管理当前窗口、前后窗口、near 定位；
  - 管理加载前文、加载后文；
  - 滚动时更新已读状态；
  - 滚动时更新 URL 当前楼层；
  - 支持目标楼层 flash。

- 滚动锚定。
  - 图片、代码块、附件加载后不能把用户位置顶走；
  - 使用 ResizeObserver 和 settling 状态；
  - 加载前文时保持当前视口稳定。

- Scrubber 强化。
  - 显示当前楼层和总楼层；
  - 显示未读区间；
  - 支持拖动跳转；
  - 移动端改成底部轻量楼层跳转条或弹层。

- 返回列表位置恢复。
  - 从讨论详情返回列表时，回到刚才那条讨论附近。

### 任务 B：搜索体系升级

- 搜索过滤器/gambit。

支持：

- `tag:python`
- `author:alice`
- `is:unread`
- `is:hidden`
- `is:following`
- `mentioned:me`
- `created:2026-05`
- `in:title`

- 搜索弹层轻量化。
  - 弹层只取每类前 5 条。
  - 弹层不计算全量总数。
  - 搜索结果页再计算当前 tab 总数。

- 搜索索引策略。
  - 短期保留 PostgreSQL FTS。
  - 中文搜索增加 `pg_trgm` 或分词字段，减少 `icontains` 全表扫描。
  - 中长期可选接入 Meilisearch、Typesense 或 OpenSearch。

- 后台索引管理。
  - 搜索索引状态；
  - 重建索引按钮；
  - 索引队列状态；
  - 最近重建时间。

### 任务 C：实时体验升级

- 实时通知强化。
  - toast；
  - 通知聚合；
  - 当前页面局部更新；
  - 连接状态提示。

- 实时讨论更新。
  - 列表显示“有新回复”；
  - 当前详情页底部提示；
  - 用户点击后加载新回复；
  - 不强行打断当前阅读位置。

- 正在输入提示。
  - 当前讨论谁正在回复；
  - 后台可关闭；
  - 权限可配置。

- 在线状态。
  - 用户在线状态；
  - 隐私设置；
  - 缓存失效策略。

### 验收标准

- 1000 回复讨论仍可顺滑浏览。
- `near=楼层` 可以稳定定位。
- 搜索至少支持 5 种过滤器。
- 搜索弹层输入无明显卡顿。
- 新回复能实时提示，但不会打乱当前阅读位置。

## 阶段 6：平台化收口

目标：把 Bias 从“扩展化论坛应用”收口为“可长期演进的平台”。

优先级：P2

### 任务

- 后台模块中心增强。
  - 模块启用状态；
  - 依赖检测；
  - 配置入口；
  - 权限入口；
  - 迁移状态；
  - 健康状态；
  - 调试信息；
  - 模块文档链接。

- 主题与外观体系升级。
  - 设计 token 完整化：
    - 颜色
    - 字体
    - 间距
    - 圆角
    - 阴影
    - 动画
    - z-index
  - 暗色模式：
    - 跟随系统
    - 用户偏好
    - 后台默认设置
  - 外观后台补强：
    - 自定义 Footer HTML
    - `welcome_title` / `welcome_message` 编辑入口
    - 区分“可见 Header/Footer 内容”和“Head/统计代码注入”
    - 增加外观实时预览

- 国际化准备。
  - 前端文案；
  - 后端错误；
  - 邮件模板；
  - 通知文案；
  - 后台配置项；
  - 模块自己的语言包注册机制。

- 开发者文档。
  - 模块开发指南；
  - Resource 字段扩展指南；
  - 事件订阅指南；
  - 前端注入点指南；
  - 权限注册指南；
  - 后台页面注册指南。

### 验收标准

- 后台已有完整模块中心。
- 主题、暗色模式、外观配置进入平台能力。
- 新语言包与新模块都有清晰接入文档。
- 开发者可以按文档新增一个内置模块。

## 性能专项清单

性能工作不再作为单独阶段，而是在各阶段同步推进。

### 数据库

重点检查和补充组合索引：

- `discussions(approval_status, hidden_at, is_sticky, last_posted_at, id)`
- `discussions(user_id, created_at)`
- `posts(discussion_id, number)`
- `posts(discussion_id, approval_status, hidden_at, number)`
- `posts(user_id, created_at)`
- `discussion_user(user_id, is_subscribed, discussion_id)`
- `post_likes(post_id, user_id)`
- `notifications(user_id, read_at, created_at)`
- `discussion_tag(tag_id, discussion_id)`

### 查询

- 讨论列表从 offset 分页逐步改为 cursor/keyset。
- 帖子列表按 `number,id` 做 cursor。
- 搜索页减少重复 `count()`。
- 搜索弹层不计算总数。
- 标签统计、用户计数、搜索索引尽量异步维护。
- Resource include 设计时避免 N+1。

### 前端

- 建立 Resource Store，减少重复请求。
- 长讨论使用窗口化渲染。
- 搜索请求 debounce + 缓存 + 请求取消。
- Composer 预览请求加取消，避免旧响应覆盖新内容。
- 大型依赖按需加载，例如 emoji、highlight、markdown 工具。

## 推荐版本规划

### v1.1：稳定性与扩展底座版本

- 回帖并发修复。
- Redis/队列健康检查。
- 分页参数限制。
- Font Awesome 本地化。
- 模块注册中心雏形。
- 权限注册化雏形。

### v1.2：事件与资源层版本

- 领域事件系统。
- Discussion/Post/Tag/User/Notification Resource 化。
- API 错误统一。
- 后台模块中心基础页。
- Event Post 基础能力。

### v1.3：前端状态层版本

- 前端 Resource Store。
- Composer 公共内核重构。
- 前台扩展注入点。
- 搜索弹层。
- 列表 UI 优化。

### v1.4：内置模块迁移版本

- tags、likes、flags、approval、subscriptions、notifications 模块迁移。
- 审核与举报体验升级。
- 移动端详情操作条。
- 讨论时间线增强。

### v1.5：论坛体验增强版本

- PostStream 窗口化。
- near 定位。
- 滚动锚定。
- Scrubber 增强。
- 返回列表位置恢复。
- 搜索 gambit。

### v2.0：平台版本

- 内置模块全面注册化。
- 实时讨论更新。
- 完整后台模块中心。
- 暗色模式、外观平台化、国际化基础。
- 开发者模块文档。

## 当前最关键的六个底座

- 模块注册中心。
- 领域事件系统。
- Resource API。
- 前端 Resource Store。
- Composer 公共编辑器内核。
- PostStream 长讨论状态层。

这六个底座决定 Bias 后续是继续作为单站论坛源码，还是能逐步发展为真正的可扩展论坛平台。

## 当前最关键的执行原则

- 扩展体系优先于新增业务功能。
- Resource 和事件层优先于页面局部重构。
- 任何新功能都必须优先考虑“能否作为模块能力注册接入”。
- UI、交互、性能优化要在做扩展底座时同步推进，而不是等扩展做完后再返工。

## 开发进度更新

### 2026-05-06

- 已完成：前端 Font Awesome CDN 依赖已移除，论坛端与后台端改为本地打包 `@fortawesome/fontawesome-free`。
- 已完成：后台仪表盘新增运行时风险提示，开始显式暴露 Redis、队列 worker、实时层和 DEBUG 等生产风险。
- 已完成：高级设置保存链路新增生产约束校验，开始阻止 PostgreSQL 形态下的危险缓存/队列配置落库。
- 已完成：后端默认 access token 生命周期从 1 小时收紧为 15 分钟，并补充基础 CSP / `nosniff` / `DENY` / `Referrer-Policy` 安全头。
- 已完成：前端 access token 不再持久化到 `localStorage`，页面刷新时改为依赖 HttpOnly refresh cookie 恢复会话。
- 已完成：通知 WebSocket 新增 refresh cookie 认证回退，前端通知连接不再把 access token 暴露在 URL 查询串。
- 已完成：API 开启 CSRF 校验，前端写请求会先初始化 `csrftoken` 并自动附带 `X-CSRFToken`。
- 已完成：前后端认证主链路切换到 HttpOnly access/refresh cookie，前端不再手动拼接 Bearer access token。
- 已完成：前端 `header`、用户菜单、游客入口和移动抽屉个人入口切换到注册式渲染，前台扩展注入基础继续收口。
- 已完成：讨论详情侧栏主操作区切换到 registry 驱动，回复 / 登录引导 / 关注不再依赖组件内硬编码分支。
- 已完成：前端 ESLint 配置与脚本已修复，`npm run lint` 可稳定校验 Vue/ESM 代码并作为后续前台改造的基础护栏。
- 已完成：通知类型定义、通知页筛选项和头部通知摘要已统一改为从前台 registry 解析，通知渲染注册入口已完成收口。
- 已完成：全局搜索来源定义、筛选项、结果区和搜索弹层已统一切到前台 registry，搜索源注册入口已完成收口。
- 已完成：讨论列表头像区、讨论详情头部和用户主页头图区的徽章展示已切到前台 registry，用户徽章与讨论徽章开始通过统一注册入口分发。
- 已完成：新增统一 `ForumTagBadge` 组件，讨论列表、讨论详情、标签云和标签子标签芯片开始共用同一套标签展示实现。
- 已完成：讨论列表标题状态与个人主页讨论状态已切到前台 registry，新增统一 `ForumStateBadge` 组件并修正 `surface` 过滤，限定区域注入项不再外溢。
- 已完成：个人主页回复状态已切到前台 registry，前台状态展示开始区分 discussion/post 两类独立注册入口，避免状态语义继续混用。
- 已完成：讨论详情帖子头部状态已切到 `postStateBadges`，帖子审核与举报状态开始通过统一状态组件和独立注册入口分发。
- 已完成：讨论详情回复区已切到 `discussionReplyState` 注册入口，并为前台 registry 补充 Node 测试脚本与基础自动化用例，`npm test` / `npm run lint` 已可实际校验这条前台注册链路。
- 已完成：讨论详情帖子审核说明区已切到 `postReviewBanner` 注册入口，帖子审核提示与操作按钮开始通过统一注册结果渲染。
- 已完成：讨论详情讨论审核说明区已切到 `discussionReviewBanner` 注册入口，讨论审核提示与操作按钮开始通过统一注册结果渲染。
- 已完成：讨论详情举报处理面板已切到 `postFlagPanel` 注册入口，举报列表与处理按钮开始通过统一注册结果渲染。
- 已完成：讨论列表与个人主页里的审核反馈文案已切到 `approvalNote` 注册入口，列表型审核提示开始通过统一注册结果分发。
- 已完成：个人主页讨论/回复空状态文案已切到 `emptyState` 注册入口，基础空状态开始通过统一注册结果分发。
- 已完成：讨论列表空状态文案已切到 `emptyState` 注册入口，关注流、我的讨论、未读和标签场景开始通过统一注册结果分发。
- 已完成：通知页与头部通知菜单空状态文案已切到 `emptyState` 注册入口，未读筛选和默认通知为空场景开始通过统一注册结果分发。
- 已完成：标签页与标签卡片最近讨论空状态文案已切到 `emptyState` 注册入口，标签列表为空和标签下暂无讨论场景开始通过统一注册结果分发。
- 已完成：搜索结果页与全局搜索弹层空状态文案已切到 `emptyState` 注册入口，未输入关键词和无结果场景开始通过统一注册结果分发。
- 已完成：讨论详情页与个人主页的页面级状态块已切到 `pageState` 注册入口，`loading/not found` 开始通过统一注册结果分发。
- 已完成：讨论列表、通知中心、标签页、搜索流、个人主页分区、通知菜单与提及选择器的状态提示已批量切到 `stateBlock` 注册入口，`loading/searching/section empty` 开始通过统一注册结果分发。
- 已完成：讨论创建跳转页、讨论/回复 composer 预览状态、发帖标签占位文案、emoji 空状态与真人验证提示已切到 `uiCopy` 注册入口，剩余零散硬编码提示开始通过统一文案解析收口。
- 已完成：认证弹层、密码重置页、个人设置/安全、头部搜索框与预览面板的表单占位、按钮文案和辅助提示已继续切到 `uiCopy` 注册入口，表单语义层开始脱离组件内硬编码。
- 已完成：搜索弹层、移动端导航抽屉、emoji 选择器以及讨论/回复 composer 的占位、按钮标题与提交文案已继续切到 `uiCopy` 注册入口，搜索与编辑器周边的零散提示进一步完成注册化。
- 已完成：邮箱验证页、密码重置页标签、通知页操作文案、举报/审核弹层说明以及一批 modal/search/composer 可访问性标签已继续切到 `uiCopy` 注册入口，认证与公共交互层的硬编码提示进一步收口。
- 已完成：讨论详情头部与个人主页头部新增统一 `heroMeta` 注册入口，作者/发布时间/最后回复/回复数、在线状态/加入时间等元信息已开始通过 registry 分发，讨论详情分页按钮、未读分隔提示以及个人主页头像上传/设置按钮文案也继续切到 `uiCopy` 注册入口。
- 已完成：讨论列表工具栏、头部通知菜单、通知卡片、composer 头部控制以及认证弹层里一批关闭/切换动作文案已继续切到 `uiCopy` 注册入口，按钮标题与可访问性标签开始从组件硬编码进一步收口。
- 已完成：搜索结果页 hero pill/标题/描述、搜索结果分区“查看全部”动作以及搜索弹层“只看某类/查看完整结果”等剩余搜索文案已继续切到 `uiCopy` 注册入口，搜索链路的页面级语义提示进一步完成注册化。
- 已完成：首页 hero 与快捷入口、标签页 hero、搜索讨论/帖子/用户分区标题以及侧栏发帖按钮文案已继续切到 `uiCopy` 注册入口，首页/发现流的剩余页面级语义提示继续完成注册化。
- 已完成：搜索筛选导航、搜索统计标签以及通知页共用的筛选/视图切换标签已继续切到 `uiCopy` 注册入口，搜索与通知两条发现/处理流的共用筛选语义开始统一通过 registry 分发。
- 已完成：通知页标记已读、清除已读、整组处理、删除通知等 confirm/alert 文案已继续切到 `uiCopy` 注册入口，通知处理流里的剩余交互提示开始脱离 composable 内硬编码。
- 已完成：讨论/回复动作菜单里的回复、登录、关注、编辑、置顶、锁定、隐藏、删除、举报等 label/description/confirm 文案已继续切到 `uiCopy` 注册入口，讨论详情动作层开始从菜单工厂与交互 composable 中进一步移除硬编码。
- 已完成：讨论侧栏里的草稿/订阅/锁定辅助提示，以及通用动作菜单的禁用态 `title` 文案已继续切到 `uiCopy` 注册入口，详情页操作区的剩余提示语义开始从组件硬编码进一步收口。
- 已完成：移动端头部的页标题、返回/菜单与右上操作标签，以及讨论列表默认筛选项“全部讨论/关注中”文案已继续切到 `uiCopy` 注册入口，导航层剩余默认语义开始从 composable 内硬编码迁出。
- 已完成：讨论事件帖与回复事件帖里的审核/隐藏/锁定/置顶/改标题/改标签等动作描述，以及楼层跳转 `title` 与通用事件兜底标签已继续切到 `uiCopy` 注册入口，详情流里的系统事件语义开始统一通过 registry 分发。
- 已完成：帖子项里的楼层跳转 `title`、已编辑状态、点赞/回复按钮文案，以及讨论列表卡片里的“发起于/最后回复”时间文案已继续切到 `uiCopy` 注册入口，详情页主体与列表元信息的高频提示进一步脱离组件硬编码。
- 已完成：讨论列表工具栏默认排序标签、列表刷新中提示，以及“加载更多/正在加载讨论”按钮文案已继续切到 `uiCopy` 注册入口，列表流本身的默认交互语义开始从组件内统一迁出。
- 已完成：关注页 hero pill/标题/描述、标签页 hero 兜底描述，以及搜索结果页 `page meta` 标题/描述已继续切到 `uiCopy` 注册入口，页面级描述语义开始从 view 层与硬编码 SEO 文案中继续收口。
- 已完成：搜索结果页顶部统计标签，以及讨论/用户结果卡片里的“X 回复 / X 讨论”计数字段已继续切到 `uiCopy` 注册入口，搜索结果流里的分类统计语义开始进一步脱离组件内拼接。
- 已完成：回复 composer 的标题、副标题、最小化摘要、关闭确认、草稿恢复/保存提示与审核弹窗文案，以及搜索帖子/讨论结果里的匿名用户兜底文案已继续切到 `uiCopy` 注册入口，回复编辑流与搜索帖子结果的剩余高频提示进一步脱离组件硬编码。
- 已完成：讨论 composer 的标题/状态摘要、关闭确认、清草稿确认、草稿恢复/保存提示与讨论更新/审核弹窗文案已继续切到 `uiCopy` 注册入口，发帖编辑流剩余的高频交互反馈进一步脱离组件硬编码。
- 已完成：个人页资料保存、通知偏好、验证邮件、密码修改与头像上传失败等反馈文案已继续切到 `uiCopy` 注册入口，账号设置与安全面板的提交/错误提示开始进一步收口。
- 已完成：讨论详情侧栏封禁提示标题、楼层 scrubber 的“原帖/现在”跳转文案，以及讨论列表侧栏里的“我的主页/标签/更多标签”入口文案已继续切到 `uiCopy` 注册入口，详情页剩余提示区与发现流补充导航语义进一步脱离组件硬编码。
- 已完成：个人设置与账号安全面板的区块标题、说明文案、字段标签，以及通知偏好分组标题/说明已继续切到 `uiCopy` 注册入口，profile 页面块的静态表单语义进一步脱离组件硬编码。
- 已完成：认证会话弹窗里的登录/注册/找回密码标题、副标题、eyebrow、字段标签、真人验证标签与主要成功/失败反馈已继续切到 `uiCopy` 注册入口，认证会话流的剩余表单语义与错误提示进一步脱离组件硬编码。
- 已完成：后台路由注册新增仪表盘快捷入口元数据，后台首页“快速操作”区已改为从 admin registry 渲染，模块化后台入口开始从导航扩展到首页操作面板。
- 已完成：后台 registry 新增仪表盘统计卡片注册入口，后台首页“论坛统计”区已改为从 admin registry 解析，模块级运营指标开始具备首页挂载能力。
- 已完成：后台 registry 新增仪表盘系统状态摘要/徽章/状态项注册入口，后台首页“系统状态”主体已改为从 admin registry 渲染，运行时可视化状态开始具备模块化注入面。
- 已完成：后台 registry 新增仪表盘风险提示注册入口，后台首页顶部运行时风险摘要已改为从 admin registry 渲染，首页告警层开始具备模块化注入面。
- 已完成：后台 registry 新增仪表盘队列指标注册入口，后台首页队列指标展示区已改为从 admin registry 渲染，运行指标面板开始具备模块化注入面。
- 已完成：后台 registry 新增仪表盘页面文案注册入口，后台首页页面标题、描述以及系统状态/论坛统计/快速操作区块标题已改为从 admin registry 渲染，首页语义层继续脱离组件内硬编码。
- 已完成：后台 registry 新增仪表盘交互文案注册入口，后台首页统计加载失败、队列指标重置按钮、确认弹窗与成功/失败反馈已改为从 admin registry 读取，仪表盘交互语义层继续脱离组件内硬编码。
- 已完成：后台 registry 新增仪表盘动作注册入口，队列指标重置行为已改为从 admin registry 分发执行，后台首页开始从展示语义继续收口到行为层。
- 已完成：讨论详情交互 composable 里的封禁提示、审核通过/拒绝弹层、举报处理确认、点赞摘要与删除/举报/关注/状态切换失败反馈已继续切到 `uiCopy` 注册入口，并补齐讨论置顶/锁定/隐藏失败弹窗，详情页交互语义开始从行为层进一步脱离硬编码。
- 已完成：讨论/回复 composer 里的未保存离页提醒、notice 标签、上传进度与成功提示、预览失败、提交失败/校验失败兜底，以及草稿/绝对时间 fallback 已继续切到 `uiCopy` 注册入口，双 composer 的交互反馈层开始进一步共享同一套注册化语义。
- 已完成：前台 composer registry 新增 `mention provider` 与 `preview transformer` 两类扩展管道，`useComposerRuntime` 已改为统一通过 registry 驱动提及搜索与预览 HTML 变换，并补上默认用户提及 provider 与 Twemoji 预览 transformer；配合既有 `tool / secondary action / submit guard / submit success / draft meta` 入口，阶段 3 的 Composer 扩展运行时已形成完整闭环，新模块开始可以在不侵入页面组件的前提下注入编辑器能力、提及源、预览处理和提交钩子。
- 已完成：全局搜索弹层已从“输入框 + 结果列表”升级为更完整的命令面板形态，空态新增最近搜索、本地持久化历史、热门标签和搜索语法三组可键盘选择的动作区；上下键与回车现在不仅能打开结果，也能直接执行空态命令，搜索弹层命令面板化这条阶段 3 任务已开始形成可用闭环。
- 已完成：搜索页与通知页新增统一 `useRoutePagination` 分页路由协议，筛选/视图切换后的“重置到第 1 页”、分页跳转后的滚动复位以及页码更新逻辑开始从页面内联分支收口到共享 composable；阶段 3 的列表状态层因此不再只共享底层请求状态，也开始共享页级路由分页行为。
- 已完成：通知页视图脚本区新增 `useNotificationViewModel` 装配层，hero 文案、筛选标题、批量操作按钮文案、分组计数和页面 meta 从 `NotificationView.vue` 收口到单一 composable，并补上 `notificationMeta` helper 测试；通知页开始并入和 search/profile/detail 一致的 view-model 页面组织方式。
- 已完成：讨论列表头部装配链路已继续收口，`DiscussionListViewBindings` 与 `DiscussionListContent/Header/Toolbar` 不再继续透传未消费的 `filter/search` 死接口，并补上绑定层测试；阶段 3 的讨论列表状态层开始从“已拆分”进一步走向“按当前 UI 真正收紧接口面”。
- 已完成：讨论列表新增 `useDiscussionListPageLifecycle`，把 tracked discussion 同步与 `discussion-read-state/forum-event` 监听注册从 `useDiscussionListRealtimeState` 中拆出，并为 lifecycle/realtime state 补上独立 Node 测试；讨论列表 page data 组织开始和 search/profile/detail 一样把“实时消费逻辑”与“生命周期编排”显式分层。
- 已完成：讨论列表新增 `createDiscussionListLoadState` 纯工厂，把初始加载/刷新/加载更多的 paginated wrapper、错误弹窗和文案解析从组合式入口中抽离，并补上独立 Node 测试；讨论列表加载层开始和搜索页一样具备可直接回归校验的纯逻辑边界。
- 已完成：讨论列表新增 `useDiscussionListRealtimeLifecycleState`，把 `window` 事件监听与 tracked discussion diff/清理从 `useDiscussionListData` 中继续抽到独立 adapter，并补上独立 Node 测试；discussion list data 层开始进一步收口为 route/resource/load/realtime 装配，而不再直接承接浏览器监听和 realtime store 细节。
- 已完成：`approval` 模块的 registry 元数据已补齐审核通过/拒绝四类事件监听定义，审核通知/标签统计/时间线消费不再错误地挂在 `notifications` 模块名下；模块中心现在开始更准确反映审核能力的真实边界，为阶段 4 的内置模块迁移闭环继续收口。
- 已完成：`approval` 与 `flags` 模块已补齐后台审核/举报权限注册定义，模块中心与权限注册化开始能够显式暴露“查看审核队列 / 通过 / 拒绝 / 查看举报 / 处理举报”这组现有后台能力；审核与举报模块因此开始从“已有后台页”进一步收口到“权限、页面、事件元数据一致归属”的模块闭环。
- 已完成：后台审核队列与举报处理接口已接入 `admin.approval.* / admin.flag.*` 权限码校验，不再只是 `staff` 兜底；`approval/flags` 模块的权限注册开始从“可展示元数据”推进到“实际控制后台行为”，阶段 1 的权限注册化因此真正落到审核与举报主链路。
- 已完成：论坛 registry 新增按前缀导出权限码 helper，`init_groups` 与 staff 默认权限开始复用 registry 派生 `admin.approval.* / admin.flag.*` 这组后台治理权限；审核/举报模块的默认 Admin 权限同步因此不再继续把同一组权限硬写在 registry、用户服务和初始化命令三处，阶段 1 的权限注册化开始进一步收口到“注册即同步”的单一来源。
- 已完成：通知页新增 `useNotificationBulkActions`，把“全部标记已读 / 清除已读 / 分组标记 / 分组清除”这组批量动作从 `useNotificationPage` 中拆出，并补上独立 Node 测试覆盖确认弹窗与 filtered action 分支；通知页 page composable 开始和详情页动作层拆分类似，继续从页面状态层向独立动作层收口。
- 已完成：通知页新增 `useNotificationItemActions`，把单条通知的已读标记、删除确认与点击跳转从 `useNotificationPage` 中拆出，并补上独立 Node 测试覆盖“未读先标已读再跳转”和删除确认分支；通知页动作层继续从“批量动作”扩展到“单项动作”，page composable 开始收敛为状态与动作装配层。
- 已完成：搜索结果页视图脚本区新增 `useSearchResultsViewModel` 装配层，hero pill/title、统计卡片、可见分组过滤和页面 meta watch 从 `SearchResultsView.vue` 收口到单一 composable，并补上 `searchMeta` helper 测试；搜索页开始和 discussion list/detail、profile 一样进入统一的 view-model 页面组织方式。
- 已完成：搜索结果页新增 `useSearchResultsPageLifecycle`，把实时事件监听注册/清理、tracked discussion ids 同步和请求 abort 清理从 `useSearchResultsPage` 中独立出去，并补上独立 Node 测试；搜索页 page composable 也开始和详情页、个人主页一样把“状态/行为”和“生命周期编排”拆开。
- 已完成：搜索结果页新增 `useSearchResultsRealtimeState`，把 `forum_event` 的 tracked discussion 判定、刷新型事件回退整页刷新和 payload merge 从 `useSearchResultsPage` 中拆出，并补上独立 Node 测试；搜索页 page composable 继续从“状态 + 生命周期 + 实时消费”收口到更清晰的状态装配层。
- 已完成：搜索结果页新增 `useSearchResultsRouteActions`，把筛选切换、分页跳转和搜索语法注入从 `useSearchResultsPage` 中拆出，并补上独立 Node 测试覆盖“非法类型归一化”“语法未变化不跳转”和分页转发；搜索页 page composable 继续向 discussion list 那种“状态层 + 路由动作层”组织方式靠拢。
- 已完成：搜索结果页新增 `useSearchResultsResourceState`，把 totals、结果 id 列表、resource store 映射、tracked discussion ids 和 source section 派生从 `useSearchResultsPage` 中拆出，并补上独立 Node 测试；搜索页 page composable 进一步收口到“请求装配 + 生命周期编排”职责。
- 已完成：搜索结果页新增 `useSearchResultsLoadState`，把 `/search` 请求参数拼装、AbortController 防并发覆盖、空查询重置和失败后的错误回填从 `useSearchResultsPage` 中拆出，并补上独立 Node 测试；搜索页 page composable 基本完成对 discussion list“加载层 + 资源层 + 路由动作层 + 生命周期层”的阶段 3 组织对齐。
- 已完成：通知页新增 `useNotificationRouteActions`，把类型切换、未读筛选、视图模式切换和分页跳转从 `useNotificationPage` 中拆出，并补上独立 Node 测试覆盖“未变化不跳转”“输入归一化”和分页参数透传；通知页开始继续向 discussion list/search 那种“状态层 + 路由动作层 + 动作层”的阶段 3 组织方式对齐。
- 已完成：通知页新增 `useNotificationLoadState`，把通知列表拉取、筛选参数拼装和 `totalCount/totalPages` 更新从 `useNotificationPage` 中拆出，并补上独立 Node 测试；通知页 page composable 继续向“加载层 + 路由动作层 + 动作层 + 展示派生”拆分。
- 已完成：通知页新增 `useNotificationDisplayState`，把空状态/加载态文案、类型筛选项、视图模式项以及汇总计数字符串从 `useNotificationPage` 中拆出，并补上独立 Node 测试；通知页 page composable 进一步收口到动作装配层。
- 已完成：头部通知新增 `useHeaderNotificationActions`，把菜单开关、批量已读/清除、点击已读后跳转以及分组/类型/通知页跳转从 `useHeaderNotifications` 中拆出，并补上独立 Node 测试覆盖刷新、失败反馈和关闭后路由分支；头部通知 composable 开始和通知中心一起对齐到“展示状态 + 动作层”的阶段 3 组织方式。
- 已完成：头部通知新增 `useHeaderNotificationDisplayState`，把菜单前 8 条切片、已读计数派生、按讨论分组、类型摘要以及空/加载文案从 `useHeaderNotifications` 中拆出，并补上独立 Node 测试；头部通知 composable 进一步收口为反馈状态与动作/展示双装配层。
- 已完成：个人主页新增 `useProfileAccountState`，把资料/安全/偏好表单默认值、头像上传引用以及保存/发送/修改密码等运行时反馈状态从 `useProfilePage` 中拆出，并补上基础 Node 测试；profile page composable 继续向纯装配层收口。
- 已完成：个人主页新增 `useProfilePageActions`，把面板切换、目标 tab 归一化以及切到 posts 时的懒加载预热从 `useProfilePage` 中拆出，并补上独立 Node 测试覆盖“同 tab 不跳转”和无用户兜底分支；profile page composable 继续收口为状态/动作装配层。
- 已完成：个人主页新增 `useProfileContentState`，把讨论/回复列表的资源 id、按需请求式加载、tracked discussion 清理和帖子去重 merge 从 `useProfilePage` 中拆出，并补上独立 Node 测试；profile page composable 开始继续从“账户动作 + 生命周期 + 内容流状态”三层收口。
- 已完成：个人主页新增 `useProfileRealtimeState`，把 forum event 的讨论可见性判定、刷新型事件回退重新拉取和帖子 payload merge/append 从 `useProfilePage` 中拆出，并补上独立 Node 测试；profile page composable 继续向“生命周期层 + 内容流状态层 + 实时消费层 + 账户动作层”拆分。
- 已完成：个人主页新增 `useProfileUserState`，把用户资料拉取、当前查看用户切换、个人资料表单初始化和“仅本人加载偏好”刷新协议从 `useProfilePage` 中拆出，并补上独立 Node 测试；profile page composable 进一步向页面装配层收口。
- 已完成：个人主页的讨论/回复面板新增按需请求式 `useRequestedPaginatedListState` 包装层，讨论列表切到共享分页状态底座，回复列表也保留 tab 懒加载但改为通过统一列表状态驱动；切换用户时的列表重置、讨论实时订阅替换，以及个人页回复 tab 在实时敏感事件后的强制刷新也一并收口，阶段 3 的列表状态层开始继续覆盖 profile 这条用户内容流。
- 已完成：个人主页面板切换新增 `useProfileRouteState` 路由状态协议，`discussions/posts/settings/security` 现在会进入 URL 查询参数，并由页面在面板可见性变化时自动纠正到首个可用 tab；profile 的刷新、分享链接以及返回前进开始具备稳定的论坛级状态层行为。
- 已完成：个人主页视图脚本区新增 `useProfileViewModel` 装配层，面板装配、页面 meta、头像区展示派生和表单字段更新 handlers 从 `ProfileView.vue` 收口到单一 composable，并补上 `profileMeta` helper 测试；profile 页面开始和 discussion list/detail 一样进入“页面只保留模板绑定”的统一组织方式。
- 已完成：个人主页新增 `useProfileMetaState`，把用户徽章派生、`loading/not found` 页面状态文案和页面 meta 同步从 `useProfileViewModel` 中拆出，并补上独立 Node 测试；profile view model 继续向 discussion detail 的“meta state + panel state + presentation state”薄装配结构对齐。
- 已完成：个人主页新增 `useProfilePanelState`，把面板注册上下文组装、当前 panel 选择、不可见 tab 自动回退以及资料/密码/偏好表单字段桥接从 `useProfileViewModel` 中拆出，并补上独立 Node 测试；profile view model 开始进一步对齐 discussion detail 的“展示态 + 面板态 + meta 态”分层方式。
- 已完成：个人主页新增 `useProfileViewBindings`，把头像区、侧栏和当前面板组件的 prop/event 绑线从 `ProfileView.vue` 与 `useProfileViewModel` 的零散字段暴露收口为聚合 bindings，并补上独立 Node 测试；profile 页面模板开始进一步向“只消费 bindings”的极薄视图层收口。
- 已完成：前端新增共享 `userPrimaryGroup` 展示工具，把个人主页与讨论详情里重复的主用户组图标/颜色/标签解析逻辑收口到统一 helper，并补上独立 Node 测试；阶段 3 的展示层拆分开始从单页收口推进到跨页面共享语义收口。
- 已完成：个人主页头部新增 `useProfileHeroState`，把徽章分组、hero meta 项以及头像上传/设置按钮文案从 `ProfileHero.vue` 中拆出，并补上独立 Node 测试；profile 组件层开始继续按“模板 + hero state”方式收口。
- 已完成：个人主页设置区新增 `useProfileSettingsSectionState`，把偏好分组、加载状态文案以及资料/偏好表单文案从 `ProfileSettingsSection.vue` 中拆出，并补上独立 Node 测试；profile 组件层继续从“大脚本区 + 大量 registry 调用”收口到模板消费状态层。
- 已完成：个人主页安全区新增 `useProfileSecuritySectionState`，把邮箱验证状态文案、密码表单标签/占位文案以及发送/提交按钮文案从 `ProfileSecuritySection.vue` 中拆出，并补上独立 Node 测试；profile 组件层继续沿设置区同样的模式收口。
- 已完成：个人主页讨论区/回复区新增共享 `useProfileContentSectionState`，把 section loading/empty 文案、状态徽章和审核提示派生从 `ProfileDiscussionSection.vue` 与 `ProfilePostSection.vue` 中收口到统一 composable，并补上独立 Node 测试；profile 内容分区开始进一步减少组件内重复 registry 调用。
- 已完成：讨论详情头部新增 `useDiscussionHeroState`，把 hero meta 和审核 banner 派生从 `DiscussionHero.vue` 中拆出，并补上独立 Node 测试；阶段 3 的组件状态层收口开始从个人主页横向推广到讨论详情。
- 已完成：讨论列表内容区新增 `useDiscussionListContentState`，把刷新提示和加载更多按钮文案从 `DiscussionListContent.vue` 中拆出，并补上独立 Node 测试；discussion list 组件层开始继续向模板消费轻量状态层收口。
- 已完成：讨论列表工具栏新增 `useDiscussionListToolbarState`，把排序选项归一化和标记已读/刷新按钮文案从 `DiscussionListToolbar.vue` 中拆出，并补上独立 Node 测试；discussion list 组件层继续沿同一模式收口 toolbar 区域。
- 已完成：讨论列表 hero 新增 `useDiscussionListHeroState`，把筛选态协议、hero 文案和图标派生从 `DiscussionListHero.vue` 中拆出，并补上独立 Node 测试；discussion list 顶部区域开始进一步统一到模板消费状态层。
- 已完成：讨论列表视图脚本区新增 `useDiscussionListViewBindings`，把侧边栏与内容区的大量 prop/event 绑线从 `DiscussionListView.vue` 收口为聚合 bindings，并补上独立 Node 测试；discussion list 页面模板开始继续向“只消费 bindings”的极薄视图层推进。
- 已完成：讨论列表侧边栏新增 `useDiscussionListSidebarState`，把发帖按钮显隐、个人主页入口显隐以及侧边栏链接文案从 `DiscussionListSidebar.vue` 中拆出，并补上独立 Node 测试；discussion list 左侧导航区继续按轻量状态层方式收口。
- 已完成：讨论列表侧边栏发帖按钮新增 `useDiscussionListSidebarStartButtonState`，把按钮文案派生从 `DiscussionListSidebarStartButton.vue` 中拆出，并补上独立 Node 测试；discussion list 左侧导航区开始进一步把局部按钮语义收口到独立状态层。
- 已完成：讨论列表条目元信息新增 `useDiscussionListItemMetaState`，把状态徽章、审核提示以及“发起于/最后回复”时间文案从 `DiscussionListItemMeta.vue` 中拆出，并补上独立 Node 测试；discussion list 条目主体开始继续向模板消费轻量 meta state 收口。
- 已完成：讨论列表条目容器新增 `useDiscussionListItemState`，把头像角标所需的 discussion badges 派生从 `DiscussionListItem.vue` 中拆出，并补上独立 Node 测试；discussion list 条目装配层继续从组件脚本区收口到独立状态层。
- 已完成：讨论列表导航态新增可独立测试的 `createDiscussionListNavigation`，把侧栏筛选项、标签导航、当前页判断和空状态/加载态文案继续收口到可注入依赖的导航状态层，并补上独立 Node 测试；discussion list page state 开始不再只能通过页面装配间接验证导航派生。
- 已完成：个人主页新增 `useProfilePageLifecycle`，把首刷、路由切换重置、实时事件监听注册/清理与讨论跟踪释放从 `useProfilePage` 中独立出去，并补上独立 Node 测试；profile 页面层开始和 discussion detail 一样把“状态装配”和“生命周期编排”拆成两段职责。
- 已完成：个人主页新增 `useProfileAccountActions`，把资料保存、通知偏好、验证邮件、密码修改与头像上传从 `useProfilePage` 中拆出，并补上基础 Node 测试；profile 页面开始和通知页一样继续从 page 状态层向独立动作层收口。
- 已完成：讨论详情页的楼层 `near` 状态新增 `useDiscussionNearRouteState` 协议，主动楼层跳转继续通过路由驱动详情刷新，被动滚动位置同步则统一改由同一 composable 负责地址栏 `replaceState`；详情页不再在帖子流 composable 内分散维护两套 `near` URL 写法。
- 已完成：讨论详情页新增 `useDiscussionDetailUiState`，把菜单开关、帖子菜单、移动端头部同步与全局点击/头部动作事件从 `useDiscussionDetailPage` 中独立出去；详情页页面层开始进一步只保留帖子流滚动与 scrubber 逻辑，交互状态与页面数据层的边界更清晰。
- 已完成：讨论详情页的楼层 scrubber UI 状态继续拆到 `useDiscussionSidebarScrubber`，拖拽预览、指针跟踪、尺寸观测、百分比计算与未读区间展示不再混在页面协调 composable 里；`useDiscussionDetailPage` 进一步收敛为帖子流与页面行为协调层。
- 已完成：讨论详情页的可见楼层跟踪、滚动节流、上下翻页自动加载与前翻锚点补偿继续拆到 `useDiscussionPostViewportState`，详情页主 composable 现在主要负责装配 `detail state / post stream / ui state / scrubber / viewport` 五层能力，阶段 3 的详情状态分层进一步清晰。
- 已完成：讨论详情页新增 `useDiscussionDetailPageLifecycle`，把路由切换重置、首次加载、移动端头部同步 watch 和全局监听清理从 `useDiscussionDetailPage` 中独立出去，并补上独立 Node 测试；详情页页面层进一步收敛为“状态装配 + 生命周期注册”两段职责，后续继续拆页面编排时不再需要改动帖子流或 UI state 本体。
- 已完成：讨论详情页视图脚本区新增 `useDiscussionDetailViewModel` 装配层，页面文案、展示派生、交互 handlers、菜单项和页面元信息 watch 从 `DiscussionDetailView.vue` 收口到单一 view-model composable；详情页视图本身开始接近纯模板绑定层。
- 已完成：讨论详情页新增 `useDiscussionDetailPermissionState`，把封禁提示、绝对时间兜底与 `discussion/post` 各类 `can*` 判定从 `useDiscussionDetailInteractions` 中独立出去，并补上独立 Node 测试；详情页交互执行层开始进一步收敛为纯动作运行时，后续继续拆 moderator / author 行为时不再需要同时改权限派生与动作实现。
- 已完成：讨论详情页新增 `useDiscussionDetailModerationActions`，把审核弹层、举报处理、隐藏/锁定/置顶/删除/关注这组 moderator 与讨论管理动作从 `useDiscussionDetailInteractions` 中拆出；详情页交互层开始进一步分成“普通用户动作 + 管理动作”两条执行链，避免大 composable 再次膨胀回单体。
- 已完成：讨论列表视图脚本区也新增 `useDiscussionListViewModel` 装配层，列表页 `page meta` 标题/描述、当前筛选语义与页面状态 watch 从 `DiscussionListView.vue` 收口到 view-model composable，发现流页面开始和详情页形成一致的“页面装配层”结构。
- 已完成：讨论列表数据层里混合的“实时订阅 / 已读同步 / 全部已读”职责继续拆到 `useDiscussionListRealtimeState`，列表请求状态与实时事件合并开始分层，讨论列表页也补上独立的 realtime helper 测试覆盖已读 patch 与订阅 diff 逻辑。
- 已完成：讨论列表数据层里的 tags/currentTag/discussions 资源请求与资源 id 维护继续拆到 `useDiscussionListResourceState`，`useDiscussionListData` 开始收口为路由状态、分页协议和错误提示协调层，发现流请求层与实时层进一步解耦。
- 已完成：讨论列表数据层里的分页加载协议、首刷/刷新/加载更多并发门禁与错误提示协调继续拆到 `useDiscussionListLoadState`，`useDiscussionListData` 进一步收口为 route/resource/load/realtime 四层装配。
- 已完成：讨论列表导航层里的筛选路由、侧栏标签排序/上下文父标签判断、激活态判定与发帖按钮对比色算法继续拆到 `discussionListNavigation` helper，并补上独立 Node 测试，侧栏导航逻辑开始脱离 composable 内联实现。
- 已完成：讨论列表数据层里的 `sort/filter/search` 路由变更 handlers 继续拆到 `useDiscussionListRouteActions`，并补上 Node 测试锁定 query push 协议，`useDiscussionListData` 进一步趋近纯装配层。
- 已完成：讨论列表页面层里的“开始发帖”动作组装继续拆到 `useDiscussionListPageActions`，并补上 Node 测试锁定 `tagId/source` 选择逻辑，`useDiscussionListPage` 进一步接近纯页面装配层。
- 已完成：讨论列表页面层里的 data/navigation 双装配继续收口到 `useDiscussionListPageState`，`useDiscussionListPage` 现在主要负责 page action 装配，页面层级关系继续向 detail 页的 page/view-model 结构靠拢。
- 已完成：讨论列表 view-model 里的当前筛选码、page meta 计算与 meta watch 继续拆到 `useDiscussionListMetaState`，`useDiscussionListViewModel` 进一步收口为 page state + meta state 装配层。
- 已完成：讨论详情 view-model 里的 hero badge、加载/缺失状态文案、加载更多文案、未读分隔文案与 page meta watch 继续拆到 `useDiscussionDetailMetaState`，详情页 view-model 也开始和讨论列表页对齐为“页面状态 + meta 状态 + 交互/展示装配”结构。
- 已完成：通知页 composable 里的加载失败、通用重试提示、筛选/总量统计、当前筛选标题以及批量/分组处理失败反馈已继续切到 `uiCopy` 注册入口，通知中心的交互与统计语义开始从 view/composable 内进一步脱离重复硬编码。
- 已完成：通知页新增 `useNotificationViewBindings`，把侧栏起帖入口、hero 操作区、筛选卡片与列表事件/属性映射从 `NotificationView.vue` 收口到独立视图绑定层，并补上 Node 测试；通知页开始和 tags / profile / discussion list 一样进入“page state + view model + view bindings”三段式页面装配结构。
- 已完成：搜索结果页新增 `useSearchResultsViewBindings`，把侧栏起帖入口、hero 搜索语法/统计区以及结果列表/分页绑定从 `SearchResultsView.vue` 收口到独立视图绑定层，并让起帖与结果跳转动作并回 `useSearchResultsViewModel` 统一装配，同时补上 Node 测试；搜索页因此开始和通知页、标签页、个人页一样进入“view 只消费 bindings”的阶段 3 页面组织方式。
- 已完成：讨论详情页新增 `useDiscussionDetailViewBindings`，把页面级状态块、hero、移动端动作、帖子流、回复区与侧栏 scrubber 的 props/events 绑定从 `DiscussionDetailView.vue` 收口到独立视图绑定层，并让 `buildUserPath/buildTagPath` 与用户展示 helper 回到 `useDiscussionDetailViewModel` 装配，同时补上 Node 测试；详情页开始继续从“已拆出 page/presentation/meta”推进到“模板只消费 bindings”的阶段 3 页面组织方式。
- 已完成：讨论创建重定向页新增 `useDiscussionCreatePage`、`useDiscussionCreateViewModel` 与 `useDiscussionCreateViewBindings`，把起帖重定向副作用、`tag/returnTo` 路由参数解析和加载文案从 `DiscussionCreateView.vue` 收口到统一页面装配层，并补上 Node 测试；这条轻量页面也开始对齐阶段 3 的“page state + view model + view bindings”结构，而不再直接在视图里混合副作用与展示文案。
- 已完成：首页、认证路由壳、邮箱验证页与重置密码页已补齐阶段 3 收尾装配层，`HomeView/AuthRouteView/VerifyEmailView/ResetPasswordView` 里的起帖入口、副作用跳转、token watch、表单提交与文案解析已分别收口到 `page / view-model / view-bindings` 或轻量 `page` composable，并补上 Node 测试；前台剩余轻页面因此不再继续把路由副作用和 registry 文案直接留在视图里，阶段 3 的页面层收尾基本闭合。
- 已完成：个人页 composable 里的资料加载、讨论/回复加载、资料保存、通知偏好、验证邮件、密码修改和头像上传错误兜底已继续切到 `uiCopy` 注册入口，profile 反馈链路开始从多处分散 fallback 收口到统一 helper。
- 已完成：头部通知菜单里的批量已读/清除已读 confirm、成功/失败反馈、通用重试提示以及摘要 chip 计数字段已继续切到 `uiCopy` 注册入口，顶部通知处理流开始与通知中心共用同一套注册化语义。
- 已完成：搜索页与过滤目录 composable 里的过滤目录加载失败、搜索结果加载失败、筛选计数字段以及错误提示展示已继续切到 `uiCopy` 注册入口，搜索链路的错误/统计反馈开始从内联 fallback 收口到统一 registry 语义。
- 已完成：讨论列表 composable 里的刷新 / 加载更多 / 全部标记已读失败反馈已继续切到 `uiCopy` 注册入口，首页筛选“全部讨论 / 关注中 / 未读 / 我的讨论”也开始与移动端页头共用同一套 registry 文案解析，讨论列表导航与动作反馈语义进一步完成收口。
- 已完成：讨论列表视图新增动态 `page meta` 标题 / 描述注册入口，`following / unread / my / tag` 这些发现流页面状态开始与 hero 文案共用同一套 registry 语义，首页发现流的页面级 SEO 与标题描述不再分散写在 router / view 中。
- 已完成：后端 `ResourceRegistry` 已从单纯附加字段表升级为“资源定义 + 扩展字段 + 关系 include”协议层，搜索结果、讨论/帖子作者摘要、用户详情和后台模块注册快照已开始共用这套资源协议，阶段 2 的统一 Resource API 底座向真实接口落地推进了一大步。
- 已完成：后台标签管理页的页面文案、交互文案以及颜色 / 权限 / 图标选项已继续切到 admin registry，标签页开始从单纯文案注册推进到整页配置注册。
- 已完成：后台审计日志页的页面文案、筛选项、表头与操作/对象标签已继续切到 admin registry，审计日志页面开始从静态映射推进到注册化配置。
- 已完成：后台用户管理页的搜索、表头、移动端卡片、编辑弹层以及保存/删除确认反馈文案已继续切到 admin registry，并补上列表加载失败的页面态提示。
- 已完成：后台审核队列与举报管理页的筛选项、状态文案、卡片元信息、处理弹层和成功/失败反馈已继续切到 admin registry，内容治理流开始形成统一的注册化页面配置。
- 已完成：后台审核队列页新增 `approval note template` 注册入口，审核通过/拒绝弹窗现在可按动作与内容类型消费 `approval` 模块提供的常用原因模板，并补上独立 Node 测试锁定模板筛选逻辑；阶段 4 的审核模块升级已从权限注册化继续推进到后台治理交互能力的模块化接入，而且仍保持在“可配置模板”这一窄切片内，没有提前扩成批量审核或新存储模型。
- 已完成：后台审核队列已补齐批量通过/拒绝接口与多选操作栏，批量审核继续复用既有单条审核权限、通知与备注模板链路，并补上 Django/Node 两侧测试锁定权限、模板适配与选择状态；阶段 4 的 `approval` 模块因此从“单条审核可配置”继续推进到“后台治理批量操作可用”，但仍限定在复用现有审批语义的窄切片内，没有提前引入新的审批存储或异步任务模型。
- 已完成：后台权限管理页的页面文案、权限统计说明、用户组弹层、保存/删除确认反馈与默认颜色配置已继续切到 admin registry，权限矩阵和分组维护流开始进入统一注册化配置。
- 已完成：后台模块中心页的页面文案、筛选项、摘要标签、模块卡片语义、注册表表头与能力文案已继续切到 admin registry，模块注册快照页开始具备完整的注册化页面配置。
- 已完成：前端通知 renderer 已补齐 `moduleId` 归属元数据，模块中心页现在会同时展示通知类型与通知 renderer 快照，并按模块筛选展示前端通知展示/跳转接入面；阶段 4 的 `notifications / likes / mentions / approval` 通知链路因此从“后端声明类型”进一步收口到“类型与前端 renderer 归属一致”的窄闭环，没有提前扩成新的通知协议或聚合模型。
- 已完成：讨论流里的 `following` 列表过滤和 `is:following` 搜索过滤已从 `discussions` 元数据归属修正到 `subscriptions` 模块，模块中心、registry 快照与回归测试现在开始更准确反映“关注流/关注过滤属于订阅能力”这一边界；阶段 4 的 `subscriptions` 模块因此继续从“只有偏好与事件监听”推进到“过滤入口归属一致”的窄收口，但没有提前扩成新的关注模型或通知聚合行为。
- 已完成：讨论详情页移动端主路径已补齐固定底部操作条与专注编辑态，`DiscussionMobileActions` 现在提供“回复 / 关注 / 分享 / 更多”四个主入口，现有编辑/管理动作继续收口到更多菜单，且手机端 reply/edit composer 打开时会隐藏站点头部与公告进入专注编辑模式；阶段 4 最后一条“移动端详情页主路径更清晰”验收口径因此闭合，没有额外扩到通知聚合、个人页 IA 或新的后端协议。
- 已完成：讨论详情帖子流已开始切到阶段 5 的窗口协议，后端 `/api/discussions/:id/posts` 现在除旧 `page` 外同步支持 `near / before / after` 三种窗口查询，并返回 `current_start/current_end/has_previous/has_more` 元数据；前端 `useDiscussionPostStreamState` 也已改为按楼层窗口边界继续前后加载，而不是继续把 `near` 映射成页码。这个切片先只收口 PostStream 协议本身，没有提前扩成虚拟列表、Scrubber 重做或实时“有新回复”提示。
- 已完成：讨论详情页的 `near` 路由变化已从“整页重刷”收口为“帖子窗口切换 + 目标楼层定位”，`useDiscussionDetailPageLifecycle` 现在只在讨论 id 变化时重置整页状态，而在 `near` 变化时直接驱动 `useDiscussionPostStreamState.syncWindowToRouteNear()` 切换窗口、flash 目标楼层并在必要时把地址栏校正到真实可见楼层；阶段 5 的 `near=楼层` 稳定定位因此开始具备独立链路，但这一步仍没有提前扩到 ResizeObserver 锚定或虚拟列表。
- 已完成：讨论详情页“加载前文”链路已补上一层轻量滚动锚定 settling，`useDiscussionPostViewportState` 现在会在 prepend 窗口后围绕原首个可见楼层做最多数帧的滚动校正，并在校正期间暂停继续自动翻前文，先把长讨论最容易出现的“前文插入后再被图片/代码块二次顶走”问题收口；这一刀仍保持在短周期 anchor 校正，没有提前扩成全量 `ResizeObserver` 监听或虚拟列表。
- 已完成：讨论列表到详情页的主链路已补齐“返回后回到刚才那条讨论附近”的显式恢复协议，列表项进入详情时会记录当前列表上下文与目标讨论 id，`useDiscussionListPageLifecycle` 会在列表重新挂载且命中同一路由上下文时把对应卡片滚回可视区并再清掉一次性标记；阶段 5 的“返回列表位置恢复”因此先在主列表链路闭合，没有顺手扩成更重的全站滚动缓存系统。
- 已完成：讨论详情页的远端新回复已从“实时到达就直接插入并打断阅读”收口为“底部提示 + 用户点击后再补载后文”，`useDiscussionPostStreamState` 现在只会在读者仍停留在尾部时立即拼接新帖，否则先累计 `pendingNewReplyCount` 并在页面底部显示“点击加载”提示；阶段 5 的“当前详情页底部提示 / 用户点击后加载新回复 / 不强行打断当前阅读位置”因此先在主详情阅读链路闭合，没有提前扩成通知聚合或全量虚拟流。
- 已完成：讨论详情页移动端已补齐轻量楼层跳转面板，`DiscussionMobileActions` 现在新增“楼层”入口，直接复用当前楼层 / 总楼层 / 未读起点和既有 `jumpToPost` 链路提供“原帖 / 未读 / 当前 / 现在”快捷跳转与数字输入跳转；阶段 5 的 “移动端改成底部轻量楼层跳转条或弹层” 因此先在主详情页闭合，没有提前扩成新的跨页导航状态或完整移动端 scrubber 重做。
- 已完成：讨论列表对当前可见讨论的 `post.created/post.approved/post.resubmitted` 事件已补齐“有新回复”本地提示，`useDiscussionListRealtimeState` 现在会为命中的讨论资源打上 `has_new_replies/new_reply_count` 补丁并在读状态同步时清空，列表卡片标题旁也会显示轻量“有新回复/ N 条新回复”提示；阶段 5 的“列表显示有新回复”因此先在当前页可见列表链路闭合，没有提前扩成全站 toast、聚合摘要或跨页缓存。
- 已完成：全局搜索弹层已改成轻量预览协议，`/api/search?preview=true&type=all` 现在只返回讨论/帖子/用户各前 5 条结果而不再计算全量 totals，`GlobalSearchModal` 也同步固定为每类最多显示 5 条并直接使用预览数量；阶段 5 的“弹层只取每类前 5 条 / 弹层不计算全量总数 / 结果页再算总数”因此先在搜索弹层主链路闭合，没有提前扩成索引后台、建议缓存或新的搜索服务拆分。
- 已完成：搜索过滤目录继续补齐 `created:YYYY-MM` 语法，`forum_registry` 现在会把它同时注册到 discussion/post 搜索，`SearchService` 也会按月份过滤讨论与回复创建时间；阶段 5 的“搜索至少支持 5 种过滤器”因此继续沿现有注册式搜索链路收口，没有提前扩成更重的高级查询构建器或新的前端筛选面板。
- 已完成：后台高级设置页已补齐搜索索引运行时状态面板，新增 `/api/admin/search-indexes/status` 统一返回 PostgreSQL 全文索引存在性、最近一次重建快照和当前队列 worker 状态；高级设置页现在会显示当前数据库、缺失索引、最近重建时间/耗时，并在重建后即时刷新状态。阶段 5 的“后台索引管理”因此先在现有高级设置页内完成最小可用闭环，没有提前扩成异步重建队列、独立索引中心或新的搜索存储模型。
- 已完成：前台统一 `forumRealtime` store 已补齐连接状态派生，应用顶层现在会在实时断线重连或多次失败后显示轻量状态提示；提示文案走 `uiCopy` registry，重连中与暂时不可用两类状态都已接入统一前台语义层，并补上 Node 测试覆盖。阶段 5 的“连接状态提示”因此先在现有论坛实时主链路闭合，没有提前扩成 toast 中心、typing 面板或新的连接管理服务。
- 已完成：讨论实时输入提示已补齐最小闭环，统一 `ws/forum` 现在支持前台回复 composer 节流发送 `typing_indicator`，讨论详情回复区会按当前讨论展示“谁正在输入”，并在输入停止后自动过期清理；后台高级设置也新增 `realtime_typing_enabled` 开关，权限注册新增 `discussion.typing`，默认成员/管理组与 `init_groups` 会同步拿到该能力。阶段 5 的“正在输入提示 / 后台可关闭 / 权限可配置”因此先在既有回复主链路闭合，没有提前扩成在线隐私面板、输入历史或新的 presence 系统。
- 已完成：前台新增统一 `onlineUsers` store 接入现有 `ws/online` 在线用户流，应用顶层会常驻维护在线用户 ID 集合；个人主页头图区的“在线 / 最近活跃”现在会优先读取真实在线状态，再回退到 `last_seen_at` 近似判断，并补上纯 helper Node 测试覆盖在线判定。阶段 5 的“在线状态”因此先在既有个人主页主链路闭合，没有提前扩成隐私开关、在线用户面板或新的 presence 协议。
- 已完成：模块中心卡片区已把“配置入口 / 权限入口 / 调试视图 / 模块文档”补成显式动作条，后端 `runtime` 快照也开始统一返回 `settings_entry_path / permissions_entry_path / module_center_path / debug_items`；现有设置组和权限注册因此不再只停留在元信息表格里，管理员可以直接从模块卡片进入对应后台页面，同时看到模块 ID、分类、启动方式和迁移状态这组调试快照。阶段 6 的“模块中心增强”因此先完成第一刀显式入口与调试信息收口，没有提前扩成动态启停、在线安装或新的模块生命周期系统。
- 已完成：后端新增统一 `ResourceQueryOptions` / `fields[...]` / `include` 解析层，讨论、帖子、标签、通知四条主读接口已开始通过同一套资源查询协议裁剪注册字段并显式展开关系，阶段 2 的 Resource API 已从“能挂字段”推进到“主接口可查询”的实际形态。
- 已完成：后端 `ResourceRegistry` 新增资源级预加载协议，注册字段与关系现在可以声明 `select_related/prefetch_related` 依赖；discussion / post / notification 主读接口已接入统一预加载计划并补齐查询回归测试，阶段 2 的 Resource API 开始从“可查询”继续推进到“可扩展且可控查询成本”。
- 已完成：搜索 API 与用户列表/详情接口已接入统一资源查询与预加载协议，`search_discussion/search_post/search_user/user_detail` 现在开始共用 `fields[...]` 与 registry 预加载计划，搜索用户结果和用户列表的主用户组查询也已补齐回归测试，阶段 2 的 Resource API 覆盖面进一步扩到搜索与用户域。
- 已完成：后端论坛领域事件已开始驱动统一讨论实时广播协议，讨论/回复创建、审核、重命名、锁定、置顶等事件现在会通过统一 `forum_event` websocket payload 推送到讨论组；讨论详情页也已接入新的讨论实时流，对公开可见内容做增量合并，对隐藏/驳回/重新提交等敏感状态退回详情刷新，阶段 2 的事件层开始真正落到实时链路而不是停留在通知/时间线。
- 已完成：前端新增统一 `forumRealtime` store，论坛实时连接已从“讨论详情页单独建链”升级为“应用级单连接 + 多讨论订阅 + Resource Store merge”模式；讨论详情、讨论列表与个人主页现在开始共用同一套 `forum_event` 消费层，对公开变更直接合并资源，对隐藏/驳回/重提等敏感状态退回列表/详情刷新，阶段 2 的实时消费开始从单页能力扩成前端资源层能力。
- 已完成：搜索结果页与全局搜索弹窗也已接入统一实时资源层，当前页可见的 discussion/post 结果现在会跟随 `forum_event` 做增量 merge 或整页刷新；通知展示层也开始优先读取最新 discussion 资源标题，统一实时资源层的收益开始从讨论域扩展到搜索和通知视图。
- 已完成：前端统一实时工具已开始承担 discussion 关联资源传播，讨论事件进入 Resource Store 后会同步刷新关联的 user/tag 资源快照；标签页也已改造为基于 Resource Store 和统一实时订阅，标签最近讨论信息开始不再依赖单次接口快照，阶段 2 的实时资源层开始从 discussion/post 本体扩展到 tag/user 关联视图。
- 已完成：`forum_event` 实时协议已进一步收口为“主资源 + included 关联资源”形态，后端讨论/回复实时事件现在会直接广播标准化 `users/tags` 资源集合并在标签变更、创建回复前先刷新相关标签统计，前端 `forumRealtime`、搜索结果页、全局搜索弹窗与标签页也已改回统一 `resourceStore.mergePayload(payload)` 消费，不再依赖页面侧手工传播 discussion 关联 user/tag 快照；retag 场景的新增/移除标签资源也会一起随事件刷新，阶段 2 的实时资源层开始从“能传播关联资源”推进到“协议级 included 资源闭环”。
- 已完成：讨论列表、个人主页与讨论详情页剩余的实时消费分支也已继续收口到统一前端实时工具层，`shouldRefreshForumEvent` 与 `mergeForumEventPayload` 现在开始接管这些页面对 `forum_event` 的刷新/合并判定；列表页不再重复维护敏感事件集合，个人主页帖子 tab 会在资源 merge 后自动吸纳新增回复 ID，讨论详情页也开始直接复用统一 payload merge 再走现有帖子流插入逻辑，阶段 2 的前端实时消费开始从“共享连接层”进一步推进到“共享消费判定层”。
- 已完成：标签页新增 `useTagsMetaState` 与 `useTagsViewModel`，把 hero 文案、空/加载态 copy、页面 SEO meta 和侧栏发帖动作从 `TagsView.vue` 收口到统一页面装配层，并补上 `tagsMeta`/`useTagsMetaState` Node 测试；标签页现在开始和 discussion list、search、profile 一样进入阶段 3 的 view-model 页面组织方式，但仍保持既有 Resource Store 与实时刷新链路不变，没有偏离主线去扩新功能。
- 已完成：标签页底层状态继续拆出 `useTagsResourceState`、`useTagsLoadState`、`useTagsRealtimeState` 与 `useTagsPageLifecycle`，`useTagsPage` 现在开始只负责装配资源映射、加载协议、实时消费与生命周期编排，并补上对应 Node 测试；阶段 3 的页面状态分层因此从标签页 view-model 继续推进到底层 page-state 结构，同时保持 `/tags` 接口、Resource Store 和实时刷新行为不变。
- 已完成：标签页新增 `useTagsViewBindings`，把 sidebar / hero / content 三块模板绑定从 `TagsView.vue` 与 `useTagsViewModel` 的零散字段暴露收口成统一 bindings/events，对齐 discussion list/profile 那种“视图只消费 bindings”的阶段 3 页面组织方式；这一步仍只整理装配层，没有扩标签页的新交互或数据协议。
- 当前阶段状态更新：
  - 阶段 0：图标资源本地化已完成；并发回帖修复、分页限制已存在；后台已开始显式暴露并阻止部分 Redis/队列危险配置；认证安全已完成短期 token 收紧、基础安全头、access/refresh Cookie 化、access token 去本地持久化、WebSocket 去 URL token 以及 API CSRF 收口，阶段 0 认证主线已基本闭合。
  - 阶段 1：前台讨论详情、个人主页、讨论列表、通知中心、标签浏览与搜索流里的状态徽章、审核说明、举报处理、审核反馈、空状态文案、部分页面级状态块、批量加载提示、部分零散 UI 文案、一批表单语义文案、部分搜索/编辑器周边提示以及部分认证/公共交互文案已持续切到 registry，前端扩展注入基础正在从导航类入口延伸到列表状态与提示语义层；标签管理页、审计日志页、用户管理页、审核队列页、举报管理页、权限管理页、模块中心页、基础设置页、外观设置页、邮件设置页、高级设置页与仪表盘的文案、交互文案、默认配置、统计快照、驱动选项、语言/公告选项、用户组/日期/分页配置、预设片段、测试发送反馈、运维动作反馈和页面级状态也已继续注册化。
  - 阶段 1：模块注册中心、权限注册化、后台模块中心基础页、前端基础注入点已落地，`discussion/post` 动作、讨论侧栏主操作区与辅助提示、回复区状态、帖子/讨论审核说明区、举报处理面板、列表型审核反馈、基础空状态、部分页面级状态、批量状态提示、部分 UI 文案、部分表单语义文案、部分搜索/编辑器提示、部分认证/公共交互提示、认证会话弹窗核心表单语义与反馈、composer、reply composer 草稿与关闭/审核提示、discussion composer 草稿与关闭/审核提示、profile 资料与安全反馈、profile 设置/安全面板静态表单语义、header、游客入口与移动端个人入口、移动端头部导航语义、通知渲染入口、搜索来源入口、搜索统计与结果计数字段、搜索帖子结果兜底语义、用户/讨论徽章展示、讨论/回复状态展示、讨论/回复事件帖语义、详情页帖子主体动作文案、讨论列表元信息语义、讨论列表工具栏与加载语义、列表 hero 与搜索 meta 描述语义、详情/主页 hero 元信息、详情侧栏剩余提示区、讨论列表侧栏补充入口语义、通用动作菜单标题语义、部分标签展示以及后台仪表盘快速操作/统计卡片/系统状态主体/风险提示/队列指标展示/页面文案/交互文案/动作行为都已进入注册式渲染/组件化，前端 lint 护栏与基础 Node 测试链路已恢复可用，后续重点是继续把更多内置能力从“已注册”推进到“完全按模块接入”，尤其是更多模块级页面块。
  - 阶段 2：领域事件、事件帖、资源字段注册层已落地；`ResourceRegistry` 已进一步升级为资源定义 / 关系 include / 扩展字段三层协议，并新增字段/关系预加载声明能力；讨论 / 帖子 / 标签 / 通知 / 搜索 / 用户这些主读接口已开始接入统一 `fields[...]` 与 registry 预加载计划；前端也已开始用应用级单连接消费统一 `forum_event` 协议，并把讨论详情、讨论列表、个人主页、搜索结果页、全局搜索弹窗、标签页接到同一套实时资源合并层，通知展示也开始读取最新资源快照；实时事件里的 discussion/post 变更现在也会携带标准化 `users/tags` included 资源并覆盖 retag 受影响标签，前端手工关联传播层与剩余页面侧刷新/merge 判定分支也已继续收口到统一实时工具，但更完整的 relationships 文档化约定、剩余接口预加载收口、更多事件驱动迁移以及更广覆盖的实时消费仍需继续推进。
  - 阶段 3：前端 Resource Store 已投入使用；discussion / post Composer 的编辑器、预览、上传、mention / emoji、浮层高度与二级动作运行时也已收口到共享 `useComposerRuntime`，并补上 `registerComposerDraftMeta` / `registerComposerSubmitSuccess` 这两类扩展点，让草稿元信息展示和提交后处理开始从页面硬编码推进到注册式接入；同时新增统一 `usePaginatedListState` 底层，把 discussion list、notification、search 三条页面状态线的首屏加载、路由驱动刷新、分页切换与“加载更多”并发门禁开始收口到同一套列表状态协议，并继续补上 `useRoutePagination` 把搜索页/通知页的页码跳转、筛选后回第一页与滚动复位协议也收口为共享页级行为，profile 页的讨论/回复面板也开始通过按需请求式列表状态包装层接入同一底座，面板切换也已新增 `useProfileRouteState` 进入统一路由状态协议，discussion detail 的 `near` 楼层状态也开始通过 `useDiscussionNearRouteState` 收口主动跳转与被动地址栏同步，并继续拆出 `useDiscussionDetailUiState`、`useDiscussionSidebarScrubber`、`useDiscussionPostViewportState`、`useDiscussionDetailPermissionState`、`useDiscussionDetailModerationActions`、`useDiscussionDetailPostModerationActions`、`useDiscussionDetailUserActions`、`useDiscussionDetailMetaState` 与 `useDiscussionDetailViewModel` 承担菜单开关、移动端头部同步、scrubber 交互、权限派生、讨论级管理动作、帖子级管理动作、普通用户动作、滚动/自动加载协调、meta side effect 以及视图装配；discussion list 视图也已新增 `useDiscussionListViewModel` 收口页面 meta 与发现流页面装配层，开始和详情页形成一致的页面层组织方式，列表数据层里的实时订阅 / 已读同步 / 全部已读职责也开始继续拆到 `useDiscussionListRealtimeState`，tags/currentTag/discussions 资源请求与资源 id 维护也继续拆到 `useDiscussionListResourceState`，分页加载协议与错误提示协调也继续拆到 `useDiscussionListLoadState`，侧栏筛选/标签排序/激活态等导航算法也继续拆到 `discussionListNavigation` helper，`sort/filter/search` 路由变更 handlers 也继续拆到 `useDiscussionListRouteActions`，“开始发帖”动作组装也继续拆到 `useDiscussionListPageActions`，data/navigation 双装配也继续收口到 `useDiscussionListPageState`，当前筛选码与 page meta side effect 也继续拆到 `useDiscussionListMetaState`；discussion detail 也已进一步拆出 `useDiscussionDetailState` + `useDiscussionPostStreamState` 两层，把讨论资源加载/patch/refresh 与帖子流分页、实时事件消费、本地回复事件合并、阅读进度同步从单一大 composable 中分层抽离，并继续补上统一 `discussion/post` 动作运行时，让详情页菜单、侧栏操作和帖子动作开始通过 registry action + handler map 调度，不再由页面手写 `actionMap` 维护；这两轮又把 `can*` 判定、封禁提示和 moderator/管理动作从通用交互执行层进一步剥离，这一轮也继续把普通用户动作、帖子级管理动作与 `discussion/post` handler map 从交互总线拆到独立 composable/helper，并补上 pending helper 测试，同时修正举报处理在确认框阶段可能双开导致的重复确认竞态，阶段 3 的详情状态与交互层继续向“权限派生 / 普通动作 / 讨论级管理动作 / 帖子级管理动作 / handler 装配 / 展示装配”六层结构推进，后续重点转到更完整的列表状态组件化与详情交互层继续瘦身。
