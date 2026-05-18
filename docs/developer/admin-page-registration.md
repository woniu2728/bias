# 后台页面注册指南

## 目标

后台页面需要同时进入后端模块定义和前端后台路由，才能真正成为平台能力。

## 步骤

1. 在 `apps/core/forum_registry.py` 增加 `AdminPageDefinition`。
2. 在 `frontend/src/admin/registry.js` 增加 `registerAdminRoute`。
3. 若页面属于设置组，补 `settings_group`。
4. 页面文案优先放到 admin registry 的 copy/config 区域。

## 约束

- 路径统一 `/admin/...`
- 路由名统一 `admin-*`
- 模块中心应能看到该后台页
