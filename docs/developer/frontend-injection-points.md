# 前端注入点指南

## 目标

前台扩展统一走 `frontendRegistry`，避免直接改页面模板造成耦合。

## 常用注入点

- `registerHeaderItem`
- `registerDiscussionAction`
- `registerDiscussionActionHandler`
- `registerPostAction`
- `registerPostActionHandler`
- `registerComposerTool`
- `registerComposerSecondaryAction`
- `registerComposerStatusItem`
- `registerComposerInitialState`
- `registerComposerPayloadContributor`
- `registerComposerSubmitSuccess`
- `registerUiCopy`
- `registerStateBlock`
- `registerPageState`
- `registerFeedbackNote`
- `registerForumRealtimeEvent`
- `registerNotificationRenderer`
- `registerForumNavItem`
- `registerForumNavSection`
- `registerProfilePanel`
- `registerSearchSource`
- `registerHeroMeta`
- `registerUserBadge`
- `registerDiscussionListContext`
- `registerDiscussionListRequest`
- `registerDiscussionListHero`

## 建议

1. 所有注入项使用稳定 `key`。
2. 页面差异优先靠 `surfaces` 区分。
3. 条件展示优先走 `isVisible(context)`。
4. 新增注入点同步补 Node 测试。
5. 扩展前端只导入 `@bias/core/forum`、`@bias/core/admin`、`@bias/core/components/admin`、`@bias/core` 或扩展自己的 `@bias/<extension-id>` SDK，不要穿透引用 `frontend/src`。

## 公共前端 SDK

扩展入口可以使用公共 SDK：

- `@bias/core/forum`
  前台扩展入口。包含 `extendForum`、`ForumExtender` 和前台注入声明能力。
- `@bias/core/admin`
  后台扩展入口。包含 `extendAdmin`、`AdminExtender`、`Exports` 和后台注入声明能力。
- `@bias/core/components/admin`
  后台页面可复用组件和页面状态 helper。
- `@bias/core`
  前后台共享扩展开发 API。包含 Vue/Pinia helper、`api`、`ItemList`、`extend`、`override`、`resetPatches`、registry helper、`ResourceModel`、`Model`、`Store`、`ResourceNormalizer`、分页状态和格式化工具等能力；不暴露宿主启动、export registry 或扩展模块加载运行时。

优先使用 `extendForum(...)` / `extendAdmin(...)` 声明注入点。只有当现有注入点无法表达“扩展一个核心对象方法”时，才使用 `extend()` 或 `override()`。

## 推荐入口模板

前台入口：

```js
import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.navItem({
    key: 'alpha-tools',
    label: 'Alpha Tools',
    href: '/alpha-tools',
    icon: 'fas fa-puzzle-piece',
    section: 'primary',
    order: 1000,
  })),
]
```

后台入口：

```js
import { extendAdmin } from '@bias/core/admin'

export const extend = [
  extendAdmin(admin => admin.page({
    name: 'alpha-tools.getting-started',
    path: '/admin/extensions/alpha-tools/getting-started',
    label: 'Alpha Tools',
    icon: 'fas fa-puzzle-piece',
    navSection: 'feature',
    navOrder: 1000,
  })),
]

export function resolveDetailPage() {
  return null
}
```

规则：

- `export const extend = [...]` 是扩展入口的稳定协议。
- 所有 `key`、`name`、`path` 必须稳定，避免升级后丢失设置、权限或路由状态。
- 前台 UI 注入优先使用 `extendForum(...)`，后台 UI 注入优先使用 `extendAdmin(...)`。
- 只有明确需要 patch 核心对象方法时，才使用 `extend()` / `override()`，并且必须放在扩展生命周期中。

## SDK 入口边界

允许导入：

```js
import { api, ItemList, ref, computed } from '@bias/core'
import { extendForum, ForumActionMenu } from '@bias/core/forum'
import { extendAdmin } from '@bias/core/admin'
import { AdminPage, AdminToolbar, AdminInlineMessage } from '@bias/core/components/admin'
```

禁止导入：

```js
import Something from '../../bias/frontend/src/...'
import Something from 'bias/frontend/src/...'
import { internalRegistry } from '@bias/core/src/...'
```

`npm run check:extension-boundary` 和 `inspect_extension_imports --check-runtime-facades` 会阻止扩展穿透宿主源码。新增公共能力时，应先导出到 `@bias/core/*`，再让扩展使用。

## SDK 导出稳定性

`@bias/core` 的导出基线在 `frontend/sdk-export-baseline.json`。每个导出都必须标注稳定性：

- `stable`：新扩展可以长期依赖。
- `experimental`：可试用，升级前需要复核。
- `internal`：只为兼容或过渡存在，不推荐新扩展使用。

新增公共 SDK 能力时：

```powershell
cd frontend
npm run sync:sdk-package
node ./scripts/checkSdkExports.mjs --write --default-stability=experimental
npm run check:platform
```

`npm run check:sdk-package` 会阻断未进入基线、缺少稳定性标注或稳定性值非法的导出。

## @bias/core

`@bias/core` 是前后台共享 SDK，适合通用状态、API、资源模型和列表组合：

- Vue/Pinia helper：`ref`、`computed`、`watch`、`defineStore`。
- HTTP API：`api` / `coreApi`。
- patch 工具：`extend`、`override`、`resetPatches`。
- 列表组合：`ItemList`、`orderedRegisteredItems`、`upsertByKey`。
- 资源模型：`ResourceModel`、`normalizeModelData`、`unwrapList`。
- 分页和列表状态：`usePaginatedListState`、`useRequestedPaginatedListState`、`useRouteListState`、`useRoutePagination`。
- 主题能力：`getThemeSlot`、`registerThemeSlot`、`applyTheme`。

示例：

```js
import { api, ref } from '@bias/core'

export function useExtensionStatus() {
  const loading = ref(false)
  const status = ref(null)

  async function load() {
    loading.value = true
    try {
      status.value = await api.get('/api/forum/alpha-tools/status')
    } finally {
      loading.value = false
    }
  }

  return { loading, status, load }
}
```

## @bias/core/forum

`@bias/core/forum` 用于前台注入和可复用 forum UI：

- 入口：`extendForum`、`ForumExtender`。
- 导航：`forum.navItem(...)`、`forum.navSection(...)`。
- Composer：`forum.composerTool(...)`、`forum.composerPayloadContributor(...)`、`forum.composerSubmitSuccess(...)`。
- Realtime：`forum.realtimeEvent(...)`、`registerForumRuntime(...)`。
- 搜索和列表：`forum.searchSource(...)`、`forum.discussionListContext(...)`、`forum.discussionListRequest(...)`、`forum.discussionListHero(...)`。
- UI 组件：`ForumActionMenu`、`ForumHeroPanel`、`ForumInlineMessage`、`ForumPagination`、`ForumPrimaryNav`、`ForumStateBlock`。

前台扩展应把业务状态放在扩展自己的模块中，向宿主提交声明式注入项。不要直接修改 `frontendRegistry` 的内部数组，也不要直接 import 页面组件。

## @bias/core/admin

`@bias/core/admin` 用于后台声明：

- 入口：`extendAdmin`、`AdminExtender`、`Exports`。
- 页面：`admin.page(...)`。
- 设置：`admin.setting(...)`、`admin.customSetting(...)`、`admin.replaceSetting(...)`、`admin.setSettingPriority(...)`、`admin.removeSetting(...)`。
- 权限：`admin.permission(...)`、`admin.permissionScope(...)`、`admin.replacePermission(...)`、`admin.setPermissionPriority(...)`、`admin.removePermission(...)`。
- Dashboard：`admin.dashboardStat(...)`、`admin.dashboardAction(...)`、`admin.dashboardConfig(...)`、`admin.dashboardCopy(...)`。
- 页面元信息：`admin.pageCopy(...)`、`admin.pageConfig(...)`、`admin.pageActionMeta(...)`、`admin.pageNoteTemplate(...)`。

后台扩展也应只走公共 SDK：

- `extendAdmin(admin => admin.page(...))`
  声明后台页面和路由。
- `admin.setting(...)` / `admin.customSetting(...)`
  声明设置项；用 `admin.replaceSetting(...)`、`admin.setSettingPriority(...)`、`admin.removeSetting(...)` 调整已有设置。
- `admin.permission(...)` / `admin.permissionScope(...)`
  声明权限项和权限分组；用 `admin.replacePermission(...)`、`admin.setPermissionPriority(...)`、`admin.removePermission(...)` 调整已有权限。
- `admin.generalIndexItems(...)`
  向后台通用索引页注入扩展拥有的条目。
- `admin.dashboardStat(...)`、`admin.dashboardAction(...)`、`admin.dashboardConfig(...)`、`admin.dashboardCopy(...)`
  声明 dashboard 展示和交互入口。
- `admin.pageCopy(...)`、`admin.pageConfig(...)`、`admin.pageActionMeta(...)`、`admin.pageNoteTemplate(...)`
  声明后台页面级文案、配置、动作元信息和模板。

## @bias/core/components/admin

后台页面组件从 `@bias/core/components/admin` 引入：

- `AdminPage`
- `AdminToolbar`
- `AdminInlineMessage`
- `AdminStateBlock`
- `AdminSummaryGrid`
- `AdminPagination`
- `AdminSelectMenu`
- `AdminMultiSelectMenu`
- `AdminFilterTabs`
- `AdminColorField`
- `AdminActionNoteModal`

后台页面应复用这些组件保持一致的信息密度、错误态和保存反馈。不要直接 import `frontend/src/admin/components/...`。

## 方法扩展和列表组合

公共 SDK 提供方法扩展能力：

```js
import { ItemList } from '@bias/core'

export const extend = [{
  extend(app) {
    app.initializers.add('example', () => {
      app.extend('extensions/example/frontend/forum/lazyTools.js', 'items', items => {
        const list = items || new ItemList()
        list.add('example', { label: 'Example' }, 20)
      })
    })
  },
}]
```

规则：

- `extend(target, method, callback)` 保留原方法返回值，并把返回值传给 callback 做追加修改。
- `override(target, method, callback)` 接收 `original` 函数，适合替换行为。
- `ItemList` 用于 key + priority 的有序列表组合，扩展列表项必须有稳定 key。
- `@bias/core` 导出的 `extend()` / `override()` 只处理已拿到的对象；扩展生命周期里的 `app.extend()` / `app.override()` 额外支持字符串 target，会按宿主 export registry 延迟解析。扩展禁用或 runtime 重载时，未触发的 lazy patch 会被取消，已触发的 patch 会按扩展 id 还原。
- patch 能力必须放在扩展生命周期里，不要在模块顶层直接修改核心对象。

## 路线图对应关系

阶段 E 关注的前端注入面，当前统一映射如下：

- `header`
  使用 `registerHeaderItem`
- `discussion actions`
  使用 `registerDiscussionAction` 声明动作项；使用 `registerDiscussionActionHandler` / `forum.discussionActionHandler(...)` 声明动作执行逻辑。
- `post actions`
  使用 `registerPostAction` 声明动作项；使用 `registerPostActionHandler` / `forum.postActionHandler(...)` 声明动作执行逻辑。
- `post types`
  使用 `extendForum(forum => forum.postType(...))` 或 `new PostTypes().add(...)` 声明事件帖渲染类型。
- `composer extension`
  使用 `extendForum(forum => forum.composerTool(...))`、`forum.composerSecondaryAction(...)`、`forum.composerStatusItem(...)`、`forum.composerInitialState(...)`、`forum.composerPayloadContributor(...)`、`forum.composerSubmitSuccess(...)`
- `feedback notes`
  使用 `extendForum(forum => forum.feedbackNote(...))` 声明列表、资料页等位置的反馈提示，避免核心认识具体业务字段。
- `realtime events`
  使用 `extendForum(forum => forum.realtimeEvent(...))` 声明扩展事件的前台语义，例如 `refresh`、`newReply`、`appendPost` 或 `upsertPost`。
- `admin navigation`
  后台导航走 `frontend/src/admin/registry/routes.js` 的 `registerAdminRoute`
- `notification renderer`
  使用 `registerNotificationRenderer`
- `discussion list resource context`
  使用 `extendForum(forum => forum.discussionListContext(...))` 加载扩展拥有的首屏资源，再用 `forum.discussionListRequest(...)` 修改列表请求参数。
- `discussion list presentation`
  使用 `extendForum(forum => forum.discussionListHero(...))` 声明列表顶部展示，避免在核心讨论列表里写扩展业务判断。
- `profile panels`
  使用 `extendForum(forum => forum.profilePanel(...))` 声明个人资料页扩展面板。
- `search sources`
  使用 `extendForum(forum => forum.searchSource(...))` 声明搜索来源，避免扩展直接修改搜索页状态。
- `hero meta`
  使用 `extendForum(forum => forum.heroMeta(...))` 声明讨论、个人资料等 hero 区域的补充元信息。
- `user badges`
  使用 `extendForum(forum => forum.userBadge(...))` 声明用户徽章。
- `page state`
  使用 `extendForum(forum => forum.pageState(...))` 声明页面级空态、加载态或异常态的补充展示。
- `extension route document`
  后端 `FrontendExtender.route(..., preloads=(...))` 可为扩展路由声明页面级资源预取，前端路由切换时会交给 document runtime 应用。

如果新增扩展面无法归到上述协议，先评估是否应扩展现有 registry，而不是直接在页面组件里写死。
