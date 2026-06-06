# 前端注入点指南

## 目标

前台扩展统一走 `frontendRegistry`，避免直接改页面模板造成耦合。

## 常用注入点

- `registerHeaderItem`
- `registerDiscussionAction`
- `registerPostAction`
- `registerComposerTool`
- `registerComposerSecondaryAction`
- `registerComposerStatusItem`
- `registerUiCopy`
- `registerStateBlock`
- `registerNotificationRenderer`
- `registerForumNavItem`
- `registerForumNavSection`
- `registerDiscussionListContext`
- `registerDiscussionListRequest`
- `registerDiscussionListHero`

## 建议

1. 所有注入项使用稳定 `key`。
2. 页面差异优先靠 `surfaces` 区分。
3. 条件展示优先走 `isVisible(context)`。
4. 新增注入点同步补 Node 测试。
5. 扩展前端只导入 `@bias/forum`、`@bias/admin`、`@bias/admin/components` 或 `@bias/core`，不要穿透引用 `frontend/src`。

## 公共前端 SDK

扩展入口可以使用公共 SDK：

- `@bias/forum`
  前台扩展入口。包含 `Forum`、`Routes`、`Search`、`Notification`、`PostTypes`、`Exports`、Vue runtime helper、路由 helper、资源 store helper 和通用组件导出。
- `@bias/admin`
  后台扩展入口。包含 `Admin`、`AdminDashboard`、`AdminPage`、`Routes`、`Exports`、后台 runtime registry 和通用扩展能力。
- `@bias/admin/components`
  后台页面可复用组件和页面状态 helper。
- `@bias/core`
  前后台共享扩展运行时。包含 `ItemList`、`extend`、`override`、`resetPatches`、`createExtensionInitializers`、`createExtensionPatcher`、`ExportRegistry`、`ResourceModel`、`Model`、`Store` 等底层能力。

优先使用 `Forum()` / `Admin()` / registry 声明注入点。只有当现有注入点无法表达“扩展一个核心对象方法”时，才使用 `extend()` 或 `override()`。

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
- 字符串 target 会按公共 export registry 延迟解析；扩展禁用或 runtime 重载时，未触发的 lazy patch 会被取消，已触发的 patch 会按扩展 id 还原。
- patch 能力必须放在扩展生命周期里，不要在模块顶层直接修改核心对象。

## 路线图对应关系

阶段 E 关注的前端注入面，当前统一映射如下：

- `header`
  使用 `registerHeaderItem`
- `discussion actions`
  使用 `registerDiscussionAction`
- `post actions`
  使用 `registerPostAction`
- `composer extension`
  使用 `registerComposerTool`、`registerComposerSecondaryAction`、`registerComposerStatusItem`
- `admin navigation`
  后台导航走 `frontend/src/admin/registry/routes.js` 的 `registerAdminRoute`
- `notification renderer`
  使用 `registerNotificationRenderer`
- `discussion list resource context`
  使用 `Forum().discussionListContext()` 加载扩展拥有的首屏资源，再用 `Forum().discussionListRequest()` 修改列表请求参数。
- `discussion list presentation`
  使用 `Forum().discussionListHero()` 声明列表顶部展示，避免在核心讨论列表里写扩展业务判断。
- `extension route document`
  后端 `FrontendExtender.route(..., preloads=(...))` 可为扩展路由声明页面级资源预取，前端路由切换时会交给 document runtime 应用。

如果新增扩展面无法归到上述协议，先评估是否应扩展现有 registry，而不是直接在页面组件里写死。
