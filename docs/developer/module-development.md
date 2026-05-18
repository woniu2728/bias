# 模块开发指南

## 目标

Bias 以内置 registry 作为平台收口中心。新增模块时，先声明 `ForumModuleDefinition`，再逐步接入权限、后台页、资源字段、事件和前端注入点。

## 基本步骤

1. 在 `apps/core/forum_registry.py` 增加模块定义。
2. 使用稳定的 `module_id` 作为所有扩展能力的归属标识。
3. 只注册当前切片需要的能力，避免一次性过度铺开。
4. 需要前台扩展时，再进入 `frontend/src/forum/registry.js` 挂接注入点。

## 最小原则

- 不直接把模块信息硬写到后台页面。
- 不绕过 registry 直接改核心 service 暴露元数据。
- 模块文档能放进开发者文档页时，优先复用统一入口。
