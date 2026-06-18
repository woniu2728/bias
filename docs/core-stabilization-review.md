# Bias 核心架构稳定化评估（第四轮）

> 评估对象：git HEAD=`36fb286`（registry/ 与 extension_detail/ 拆分、RuntimeServiceProxy 转换、JWT 吊销、flag 删除修复落地之后）。
> 方法：直接读码 + 在生产模式 Docker 实例上跑测试与运行时探测（结论均附证据）。
> 决策基线：**"core 成包"已决定往后放**（复用收益尚不存在、代价高；边界用 import-linter 廉价守住即可）。本轮目标是**先把核心架构稳定住**——细化五维现状与 bug，明确优先级。
>
> 相关文档：`docs/pending-optimizations.md`（待办池）、`docs/optimization-review-round2.md`（第二轮）。
> 优先级：P0=尽快、P1=近期、P2=中期、P3=收尾。

---

## 0. 速览

| 维度 | 结论 |
| --- | --- |
| 架构 | 两大上帝文件已拆分且为**真解耦**（验证通过），核心结构已显著稳定 |
| 功能 | D1 回归已修；JWT 吊销已实现但 **refresh 端点有缺口** |
| 性能 | 无新退化；GIN 索引仍待办 |
| 冗余 | 持续收敛（shim 化 / proxy 化 / 删死代码） |
| Bug | **1 个 P1 运行时缺陷 + 2 个 P2 + 测试侧若干**，详见第 6 节 |

本轮新发现需处理项：**B1（P1 容器写权限）、B2（P2 JWT refresh 黑名单缺口）、B3（P2 sort mutator 失效）**。

---

## 1. 架构（已显著改善，真解耦）

| 项 | 改动 | 验证证据 |
| --- | --- | --- |
| ResourceRegistry 拆分 | `resource_registry.py` 2750→**1693** 行；抽出 `apps/core/registry/`：`definition_mutator(293)`、`endpoint_context(421)`、`jsonapi_serializer(160)`、`preload_planner(311)`、`resource_validator(338)`、`search_bridge(188)` | `test_resource_registry` **110 测试全过** |
| admin_extension_detail 拆分 | `admin_extension_detail.py` 1864→**111 行 re-export shim**；新增 `apps/core/extension_detail/` 包（orchestrator/models/resources/forum_domain/frontend/permissions/settings_theme/debug/_shared） | `test_admin_extensions_api` **20 测试全过** |
| RuntimeServiceProxy 落地 | `runtime_users/tags/notifications/moderation/search` 转为代理（原 #3） | 见 §3 全量测试无相关回归 |

**关键判断：这次是真解耦，不是挪代码。** grep 确认 `apps/core/registry/*.py` 中**不存在** `registry._`、`self.registry._` 等"反向钻私有"调用；`endpoint_context.py` 把 `_resolve_endpoint_*` 收成 resolver 自己的方法，比旧 `ResourceEndpointRunner`（曾依赖 `registry._resolve_*` 私有）干净。

**稳定化后续（低成本、建议做）**
- 加 `import-linter` 合同进 CI：禁止 `apps.core` import `extensions.*` 与论坛领域，把现有越界点暴露出来逐步还债。这是"core 成包"的廉价替代，0.5 天即可守住边界。
- 论坛领域下沉（`forum_*`、`runtime_posts/...`）作为**机会式重构**，碰到再挪，不专门立项。

**明确推迟**：core 物理成包、扩展框架独立包（pending #13 / 附录 C）——等出现第二个复用方或开源意图再做。

---

## 2. 功能

| 项 | 状态 | 证据 / 备注 |
| --- | --- | --- |
| flag 删除权限（原 D1 回归） | ✅ 已修 | `extensions/flags/backend/ext.py:170` 注册 `admin.flag.delete` 并入组；`test_staff_can_delete_post_flags...` 通过 |
| JWT 吊销（#6） | ⚠️ 部分 | `logout` 已把 access(header+cookie)/refresh 入黑名单（`jwt_auth.blacklist_jwt_token`）；**但 `refresh_access_token` 端点不查黑名单**，见 B2 |
| /api/search 论坛闸门（#7） | ✅ 已落地 | `extensions/search/backend/api.py` +10 行（建议补一条匿名搜索的回归测试确认闸门生效） |

---

## 3. 性能

- `_get_enabled_module_ids` 请求/实例级 memoization 仍在（`resource_registry.py`，`_NOT_CACHED` 哨兵 + `reset_resource_registry_state` 失效），序列化热路径不再每对象查库。
- JWT 黑名单为每个已认证请求增加一次缓存查（`is_jwt_blacklisted`，走 Redis），开销可接受。
- **待办**：全文搜索 GIN 索引（pending #4）——`extensions/search/backend/services.py` 用 `SearchVector` 实时算 `to_tsvector`，全库无 `GinIndex`，大数据量顺序扫描。
- 全量测试 475 项 51s，无明显性能异常。

---

## 4. 冗余

- `admin_extension_detail.py` → 111 行 shim（实体迁入 `extension_detail/`）。
- `runtime_*` → RuntimeServiceProxy 代理化（原 #3 收敛）。
- `admin_runtime_helpers.py` 已删（早前）。
- **待办**：17 个扩展中 9 个 `frontend/forum/sdk.js` 与 `nodeSdk.js` 完全相同（pending #12）。

---

## 5. 测试失败分诊（全量 `manage.py test`：apps.core 475 项 → 7 失败 + 2 错误 + 扩展侧若干）

> 关键结论：**除 B3 外，apps.core 的失败几乎全部源于同一个 P1 权限缺陷（B1）或依赖实时基础设施的环境性断言**；修掉 B1 可一并消除约 6 个失败。

| 测试 | 类型 | 归因 |
| --- | --- | --- |
| `test_extension_runtime_state_refreshes_after_enable_toggle`、`test_extension_lifecycle_extender_runs_on_state_changes` | ERROR | `PermissionError: /app/static/extensions/manifest.json` → **B1** |
| `test_smtp_driver_requires_host_before_sending`、`test_mail_settings_*`、`test_advanced_and_cache_endpoints_exist` | FAIL | `PermissionError: /app/instance/site.json` → **B1** |
| `test_admin_stats_*`（redis_enabled / python_runtime_status） | FAIL | 依赖容器内实时 redis/celery 状态 → 环境性 |
| `test_bias_style_conditional_model_search_and_api_resource_extenders` | FAIL | **真断言失败 → B3** |
| flags `test_flag_visibility_uses_post_view_private_scoper` | FAIL | 测试侧 → **B4a** |
| flags `test_inspect_reports_flags_model_as_extension_native` | FAIL | 测试侧 → **B4b** |
| users `AdminMailTestEmailApiTests.test_mail_*`（4） | FAIL | 同 B1 权限 / 邮件后端环境性 |

---

## 6. Bug 细化清单

### B1 【P1·运行时】非 root 容器写不了 instance/site.json 与 static/extensions
- **现象**：后台"保存邮件设置"`POST /api/admin/mail` 返回 **500**：`邮件设置写入站点配置失败: [Errno 13] Permission denied: '/app/instance/site.json'`；扩展启停重建 `/app/static/extensions/manifest.json` 抛 `PermissionError`。
- **证据**（生产模式实例实测）：
  - 容器用户 `id` = `uid=1000(bias)`；
  - `ls -lan` → `/app/instance/site.json`、`/app/instance`、`/app/static/extensions` 属主均为 `0 0`(root)，mode 644/755；
  - `touch /app/instance/.wtest` 与 `touch /app/static/extensions/.wtest` 均 `Permission denied`。
- **根因**：`docker-compose.yml` 的 `web` 用 `.:/app` 绑定挂载，宿主机这些目录是 **root 所有**，运行期挂载**覆盖**了 Dockerfile 构建期的 `chown -R bias:bias /app`（构建期 chown 对 bind mount 无效）。
- **影响**：任何需要写 `site.json` 的后台设置保存、以及扩展启停时的 manifest 重建，在该部署形态下全部失败；并连带导致约 6 个测试失败。
- **修复（任一）**：
  1. 宿主机 `chown -R 1000:1000 instance static`（或安装脚本/entrypoint 启动时修权限）；
  2. `instance/`、`static/` 改用**命名卷**（像 `media`/`staticfiles` 那样），避免绑定宿主机 root 目录；
  3. entrypoint 以 root 修权限后再 `gosu bias` 降权运行。
- **建议**：方案 2（命名卷）最干净，与现有 `media_volume`/`static_volume` 一致。
- **风险**：低　**预估**：0.5 天　**验证**：修后重跑 `inspect_extensions`/`/api/admin/mail` 与上述 6 个测试应转绿。

### B2 【P2·功能】JWT refresh 端点不校验黑名单，登出未真正吊销 refresh 能力
- **现象**：`logout` 已把 refresh token 入黑名单，但 `extensions/users/backend/api.py` 的 `refresh_access_token` 仅 `RefreshToken(refresh_token)` 后即签发新 access token，**未调用 `is_jwt_blacklisted`**。
- **影响**：登出后若 refresh token 泄露，仍可持续换取新 access token，吊销机制存在缺口。
- **修复**：`refresh_access_token` 在构造/使用 refresh token 前先 `if is_jwt_blacklisted(refresh_token): 返回 401`；改密/重置密码路径同理应吊销旧 token。
- **风险**：低　**预估**：0.5 天　**验证**：补"登出后用旧 refresh 调 /token/refresh 应 401"的测试。

### B3 【P2·行为】条件源扩展器的 sort mutator 未生效
- **现象**：`test_bias_style_conditional_model_search_and_api_resource_extenders`（`apps/core/tests/test_extension_loader.py:3500`）断言 `application.resources.apply_sort_definitions("forum", []) == [{"name": "newest-mutated"}]`，实际为 `[{"name": "newest"}]`——sort 未被改写。
- **已排除**：registry 委派正确（`resource_registry.apply_sort_definitions` → `registry/definition_mutator.py:105`，其中 `mutate` 分支逻辑完整）。问题在**条件源扩展器（source-defined extender）的加载/应用管线**，扩展未把 mutate 定义注册进 store。
- **待办**：bisect 确认是本次 `extenders_model_search` / RuntimeServiceProxy 重构引入，还是既有；再决定修代码或修测试。
- **风险**：中（涉及扩展加载管线）　**预估**：0.5–1 天

### B4 【P3·测试侧】2 个长期 flags 失败（自 926560f 起，非本轮引入）
- **B4a `test_flag_visibility_uses_post_view_private_scoper`**：测试 patch 了 `apps.core.extensions.runtime.get_runtime_model_service`，但实际解析路径是 `visibility.py` → `runtime_models.py` 内**同模块**调用 `get_runtime_model_service()`（`runtime_models.py:8`），mock 拦不到 → 用真实(未注册 view scope 的)服务 → 返回空集。**修测试**：patch 到 `runtime_models.get_runtime_model_service`，或改为注册到全局服务。
- **B4b `test_inspect_reports_flags_model_as_extension_native`**：断言 `migration_plan.pending_files` 含 `0001_record_model_ownership.py`，但该文件名**只在测试出现，生产代码从不生成**（discussions/notifications/mentions 同款断言）。需产品决策：补"记录模型归属迁移"特性，或把断言改为实际产出（如 `0001_state_post_flag.py`）。
- **风险**：低　**预估**：各 0.5 天

---

## 7. 建议执行顺序（先稳核心、再清尾巴）
1. **B1（P1）**：容器写权限——影响后台设置保存与扩展启停，且连带 6 个测试，收益最高。
2. **B2（P2）**：JWT refresh 查黑名单——补齐吊销缺口。
3. **B3（P2）**：bisect 并修复 sort mutator 失效。
4. **架构稳定收尾**：加 `import-linter` 边界合同（成包的廉价替代）。
5. **B4（P3）**：修正 2 个测试侧失败让 CI 回绿。
6. 其余进 `pending-optimizations.md`（GIN 索引 #4、SDK 去重 #12 等），按节奏推进；core 成包/框架独立包明确推迟。

---

*创建于：2026-06-18，基于 HEAD=36fb286 的第四轮（核心架构稳定化）评估*
