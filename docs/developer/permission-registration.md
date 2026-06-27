# 权限注册指南

## 目标

权限必须以 registry 为单一来源，后台 UI、默认权限和接口判定都围绕同一套权限码工作。

## 步骤

1. 注册 `PermissionDefinition`。
2. 权限 code 一经发布应保持稳定；需要改名时按迁移脚本更新持久化数据，不在运行时注册别名。
3. 需要前置依赖时补 `required_permissions`。
4. 用统一 helper 做校验，不要继续散落硬编码权限串。

## 权限范围入口

如果扩展需要像标签权限那样维护分域访问范围，不要把控件写进核心权限页。前端使用 `extendAdmin(admin => admin.permissionScope({ ... }))` 注册入口，权限页会在布尔权限矩阵上方渲染对应 scope panel。

常用字段：

- `key`
- `moduleId`
- `label`
- `description`
- `icon`
- `to`
- `actionLabel`

## 校验

- `/api/admin/permissions/meta`
- `init_groups`
- 权限保存/读取测试
