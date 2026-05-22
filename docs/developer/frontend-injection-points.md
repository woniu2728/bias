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

## 建议

1. 所有注入项使用稳定 `key`。
2. 页面差异优先靠 `surfaces` 区分。
3. 条件展示优先走 `isVisible(context)`。
4. 新增注入点同步补 Node 测试。

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

如果新增扩展面无法归到上述协议，先评估是否应扩展现有 registry，而不是直接在页面组件里写死。
