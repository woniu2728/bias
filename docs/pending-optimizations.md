# 待推进的复杂优化项

> 以下事项已评估，但需要更深入的架构讨论或较大的重构工作量。
> 标注了风险等级、预估工作量、建议方案，供决策参考。

---

## 架构拆分（高风险，大工作量）

### 1. ResourceRegistry 上帝类拆分 (P1)
- **现状**: `apps/core/resource_registry.py` 单类 163 方法 / 2750 行
- **方案**: 拆为 RegistryStore / Validator / JsonApiSerializer / PreloadPlanner / SearchBridge
- **风险**: 高（内部调用链复杂，需要保持 API 兼容）
- **预估**: 3-5 天

### 2. admin_extension_detail.py 拆分 (P1)
- **现状**: 1864 行 / 70 个模块级函数
- **方案**: 按子域拆分：前端路由 / 权限矩阵 / 设置 / 主题 / 调试
- **风险**: 中（函数间耦合度低于 ResourceRegistry）
- **预估**: 1-2 天

### 3. RuntimeServiceProxy 落地使用 (P2)
- **现状**: `runtime_core.py` 已定义 `RuntimeServiceProxy` 但无消费方
- **方案**: 逐步替换 runtime_*.py 中的简单转发函数为代理调用
- **风险**: 低（API 兼容，渐进式替换）
- **预估**: 1 天

---

## 性能优化

### 4. 全文搜索 GIN 索引 (P1)
- **现状**: `extensions/search/backend/services.py` 用 `SearchVector(...)` 实时算 `to_tsvector`，无 `GinIndex`
- **方案**: 加 `SearchVectorField` + `GinIndex`，或 PG 函数索引
- **风险**: 中（需要数据库迁移、验证查询计划）
- **预估**: 1-2 天

### 5. web 多 worker + LocMem 不一致报警 (P2)
- **现状**: gunicorn 2 worker，无 Redis 时限流/在线状态/缓存不一致
- **方案**: `doctor` 在"生产+多worker+LocMem"组合显式报警
- **风险**: 低
- **预估**: 0.5 天

---

## 安全加固

### 6. JWT 吊销机制 (P2)
- **现状**: 无 blacklist/rotation，登出仅清 cookie
- **方案**: token_blacklist app + token version
- **风险**: 中（影响登录态管理，需兼容现有 token）
- **预估**: 1-2 天

### 7. /api/search 路由层 viewForum 闸门 (P2)
- **现状**: 匿名可搜索，仅靠逐行可见性兜底
- **方案**: 路由层加论坛查看权限门槛
- **风险**: 低
- **预估**: 0.5 天

### 8. 限流 check/record 非原子 TOCTOU (P3)
- **现状**: `auth_rate_limit.py` check 和 record 之间有竞态窗口
- **方案**: 用 Redis Lua 脚本或 `cache.incr` 原子化
- **风险**: 低
- **预估**: 0.5 天

### 9. forgot_password 吞掉邮件发送失败 (P3)
- **现状**: 邮件发送失败仍返回"已发送"
- **方案**: 捕获异常并返回具体错误
- **风险**: 低
- **预估**: 0.5 天

### 10. admin_user 最后 superuser 护栏 (P3)
- **现状**: 无"保留最后一个超级管理员"检查
- **方案**: `update_admin_user`/`delete_admin_user` 加检查
- **风险**: 低
- **预估**: 0.5 天

---

## 整洁度

### 11. Runtime_* facade 样板收敛 (P2)
- **现状**: 约 116 个薄封装转发函数，与 SDK 重复
- **方案**: 用 RuntimeServiceProxy 逐步收敛
- **风险**: 低
- **预估**: 1 天

### 12. SDK 文件重复 (P3)
- **现状**: 17 个扩展中 9 个 `frontend/forum/sdk.js` 与 `nodeSdk.js` 完全相同
- **方案**: 单一 `sdk.js` + 打包层约定
- **风险**: 中（影响前端构建）
- **预估**: 1 天

---

*创建于：2026-06-17，基于 round2.md 第二轮评估*
