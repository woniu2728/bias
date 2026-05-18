# 前端注入点指南

## 目标

前台扩展统一走 `frontendRegistry`，避免直接改页面模板造成耦合。

## 常用注入点

- `registerHeaderItem`
- `registerDiscussionAction`
- `registerPostAction`
- `registerUiCopy`
- `registerStateBlock`
- `registerNotificationRenderer`

## 建议

1. 所有注入项使用稳定 `key`。
2. 页面差异优先靠 `surfaces` 区分。
3. 条件展示优先走 `isVisible(context)`。
4. 新增注入点同步补 Node 测试。
