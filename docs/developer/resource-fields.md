# Resource 字段扩展指南

## 目标

模块扩展字段应统一挂到 Resource 协议层，而不是每个接口各自拼 response。

## 步骤

1. 选择正确资源名，例如 `discussion`、`post`、`search_post`。
2. 注册字段时带上 `module_id` 和简短描述。
3. 有关联依赖时，优先补预加载声明。
4. 前端通过 `fields[...]`、`include` 和 resource store 消费字段。

## 约束

- 字段名保持稳定。
- 避免和已有关系重复建模。
- 高成本字段必须补测试。
