# 后台页面注册指南

## 目标

后台页面需要通过后端扩展声明和前端后台入口同时注册，才能真正成为平台能力。

## 步骤

1. 在扩展后端入口使用 `AdminSurfaceExtender` 或 `FrontendExtender` 声明后台页。
2. 在扩展的 `frontend/admin/index.js` 导出对应页面组件或 bootstrap。
3. 若页面属于设置组，补 `settings_group`。
4. 页面文案优先放到 admin registry 的 copy/config 区域。

## 约束

- 路径统一 `/admin/...`
- 路由名统一 `admin-*`
- 扩展中心或扩展详情页应能看到该后台页
