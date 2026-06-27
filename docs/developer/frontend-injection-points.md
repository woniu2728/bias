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
