# 权限注册指南

## 目标

权限必须以 registry 为单一来源，后台 UI、默认权限和接口判定都围绕同一套权限码工作。

## 步骤

1. 注册 `PermissionDefinition`。
2. 权限 code 一经发布应保持稳定；需要改名时按迁移脚本更新持久化数据，不在运行时注册别名。
3. 需要前置依赖时补 `required_permissions`。
4. 用统一 helper 做校验，不要继续散落硬编码权限串。

## 校验

- `/api/admin/permissions/meta`
- `init_groups`
- 权限保存/读取测试
