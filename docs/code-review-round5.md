# Bias 第五轮代码复评（架构/功能/性能/冗余/Bug）

> 评估对象：git HEAD=`9ea4fd6`（registry/ 与 extension_detail/ 拆分、JWT 吊销、B1-B4 修复、import-linter 边界、SDK 去重落地之后）+ 一处本地未提交的 Dockerfile 修复。
> 方法：生产模式 Docker 实例（`-f docker-compose.yml --profile queue`，已重建）上跑全量测试 + import-linter + flake8 + 运行时探测；结论均附证据。
> 相关文档：`docs/core-stabilization-review.md`（第四轮）、`docs/pending-optimizations.md`（待办池）、`docs/optimization-review-round2.md`。
> 优先级：P0=尽快、P1=近期、P2=中期、P3=收尾。

---

## 0. 总览

| 维度 | 结论 |
| --- | --- |
| 架构 | registry/ + extension_detail/ 拆分到位且**真解耦**；import-linter 边界 0 broken；稳定 |
| 功能 | D1/B2/B3 + JWT 吊销 + search 闸门 全部已修并验证；健康 |
| 性能 | 无退化；GIN 索引仍待办 |
| 冗余 | SDK 去重完成；残留少量 import/星号导入整洁度问题 |
| Bug | **1 个真实 latent bug（frontend.py 未定义 logger）** + 构建 bug（Dockerfile）+ 测试侧未收尾 |

**关键结论：没有用户可见的生产功能 bug。** 全量测试的 14 个失败全部是**测试侧或环境性**；唯一真实代码缺陷是错误路径上的 `NameError`（见 B-1）。

---

## 1. 架构（稳定，真解耦）

| 项 | 证据 |
| --- | --- |
| ResourceRegistry 拆分 | `resource_registry.py` 1693 行 + `apps/core/registry/`（definition_mutator/endpoint_context/jsonapi_serializer/preload_planner/resource_validator/search_bridge）；`test_resource_registry` **110 全过** |
| admin_extension_detail 拆分 | 111 行 shim + `apps/core/extension_detail/`（9 模块）；`test_admin_extensions_api` **20 全过** |
| 边界守护 | `import-linter`：分析 483 文件，**Contracts: 1 kept, 0 broken**（`apps.core` 不依赖 `extensions`） |
| 成包 / 框架独立包 | 已决定**推迟**（无第二消费者，代价高）；用 import-linter 廉价守边界 |

**待清理（整洁度，非功能问题）**：`resource_registry.py` 中 `ResourceValidator` 被 flake8 标 **F811 重复定义 10 次**（line 45 顶层 import 与方法内重复 import/赋值，拆分残留）。建议统一为单一来源。

---

## 2. 功能（健康）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| flag 删除（原 D1） | ✅ | `flags/ext.py:170` 注册 `admin.flag.delete`，删除测试通过 |
| JWT 吊销（#6 / B2） | ✅ | `logout` 把 access/refresh 入黑名单；`refresh_access_token` 已加 `is_jwt_blacklisted` → 双端闭环 |
| sort mutator（B3） | ✅ | `test_bias_style_conditional_..._extenders` 通过 |
| /api/search 论坛闸门（#7） | ✅ | 已落地 |

---

## 3. 性能（无退化）

- `_get_enabled_module_ids` 实例级 memoization 仍在，序列化热路径不再每对象查库。
- JWT 黑名单为每个已认证请求加一次 Redis 查，开销可接受。
- **待办**：全文搜索 GIN 索引（`extensions/search/backend/services.py` 用 `SearchVector` 实时算 `to_tsvector`，全库无 `GinIndex`），见 `pending-optimizations.md #4`。

---

## 4. 冗余（持续改善）

- ✅ #12：删除 9 个与 `sdk.js` 完全相同的 `nodeSdk.js`。
- ✅ admin_extension_detail → shim；runtime_* → RuntimeServiceProxy；admin_runtime_helpers 已删。
- **残留整洁度**（flake8 统计）：
  - 271 × F401（多为 shim 再导出 + tests/common）
  - 2353 × F405 / 30 × F403（拆分后测试 `from ...common import *` 星号导入连带）
  - 11 × F811（含上文 ResourceValidator 重复定义）
  - 建议：shim 用 `# noqa`/`__all__`；测试改显式导入或集中 `__all__`。

---

## 5. Bug 细化

### B-1 【P2·真实 latent bug】`extension_detail/frontend.py` 使用未定义的 `logger`
- **证据**：`flake8` → `apps/core/extension_detail/frontend.py:45:9: F821 undefined name 'logger'`。该模块 import 区无 `logging`/`logger`，但第 45 行 `except Exception:` 分支调用 `logger.warning(...)`。
- **影响**：当 `get_extension_settings(...)` 抛异常走进该分支时 → `NameError: name 'logger' is not defined`，**异常处理器自身崩溃**，把本可降级的告警变成 500（后台扩展详情/前端文档序列化）。
- **根因**：`admin_extension_detail.py` 拆分到 `extension_detail/` 时，`frontend.py` 漏带 module-level logger。
- **修复**：`frontend.py` 顶部加 `import logging` + `logger = logging.getLogger(__name__)`。
- **风险**：低　**预估**：5 分钟　**验证**：flake8 该项清零 + 构造 settings 加载异常确认走 warning 而非 500。

### B-2 【构建·阻断】committed Dockerfile 构建不出来（已本地修复，待提交）
- **现象**：`docker compose build` 失败 `exit code 127`；gosu 安装步骤用 `wget`，但基础镜像 `python:3.12-slim` 未装 wget。即便补 wget，后续 `gpg --keyserver hkps://keys.openpgp.org` 收 key 会**长时间挂住**（实测 buildx 进程 CPU 0.6% 空转等网络）。
- **修复（本地已改，未提交）**：把"wget 下载 GitHub release + keyserver 验签"整段换成 `apt-get install -y gosu`（Debian 源自带 `gosu 1.17-3+b4`，同版本），又快又稳。
- **验证**：重建成功；`/proc/1` 确认 web/celery 进程 `Uid=1000`（gosu 降权生效）；B1 写权限通过（`instance`/`static/extensions` 属主翻为 1000、bias 实测可写）。
- **待办**：尽快提交该 Dockerfile 修复，否则他人 `up --build` 会同样失败/卡住。

### B-3 【P3·测试侧未收尾】B4 修复只打在 flags，未传播到其它扩展
- **现象**：显式跑扩展套件（250 测试）**11 失败**，全是与 flags B4 同款的两类测试侧问题：
  - 可见性 scoper：`test_view_private_scoper_*`、`test_hide_*_scoper_*`、`test_*_runtime_private_checkers`、`test_model_private_extender_*`（discussions 4 + posts 4）——`AssertionError: 1 not found in set()`，因 `patch("apps.core.extensions.runtime.get_runtime_model_service")` 打错路径（真实调用经 `runtime_models` 同模块），mock 不生效 → 空集。
  - inspect 归属：`test_inspect_reports_discussions_models_as_extension_owned`、`test_inspect_reports_notification_model_as_extension_native`——期望 `0001_record_model_ownership.py`（生产从不生成）。
- **根因**：`a421a65` 仅修了 `extensions/flags/backend/tests.py`（B4a 改 patch 路径为 `runtime_models`，B4b 改断言为实际迁移名），**未同步修 discussions/posts/notifications/mentions** 的同款测试。
- **影响**：纯测试侧，**非生产 bug**（生产可见性/迁移计划逻辑自洽）；但 CI 仍红。
- **修复**：把 flags 的两处改法机械传播到 discussions/posts/notifications/mentions。
- **风险**：低　**预估**：0.5 天

### B-4 【环境性】apps.core 3 个失败 = 测试不隔离于运行环境
- `test_admin_stats_returns_python_runtime_status`：期望风险列表为空，实际含 `locmem-cache-multiprocess`（测试用 LocMemCache + 多 worker，风险检测正确触发）。
- `test_mail_settings_expose_default_templates`：`'smtp.example.com' != 'smtp.gmail.com'`，测试读到了实例 `instance/site.json` 的真实邮件配置，而非代码默认值。
- `test_admin_stats_does_not_mark_redis_enabled_from_idle_broker_config`：依赖容器内实时 redis/celery 状态。
- **根因**：测试在配置好的生产容器内运行、读真实 site.json/实时基础设施，缺隔离。在干净 CI checkout（无 site.json、无实时 infra）下应通过。
- **建议**：测试 fixture 隔离 site.json 与 cache backend；或在干净环境跑 CI。

---

## 6. 测试现状汇总

| 套件 | 结果 | 性质 |
| --- | --- | --- |
| `apps.core`（475） | 3 失败 | 全环境性（B-4） |
| 扩展主要套件（250） | 11 失败 | 全测试侧（B-3，未传播的 B4） |
| import-linter | 1 kept, 0 broken | ✅ |
| flake8 严重类（E9/F821/F811…） | 1×F821（B-1 真 bug）+ F811 冗余 | 见 B-1 / §4 |

> 14 个测试失败中**无一为生产功能 bug**；唯一真实代码缺陷是 B-1（错误路径 NameError，flake8 独立发现）。

---

## 7. 建议优先级
1. **B-1（P2）**：修 `extension_detail/frontend.py` 未定义 logger（真 latent bug）。
2. **B-2（构建）**：提交 Dockerfile 的 gosu→apt 修复（committed 版构建不出来）。
3. **B-3（P3）**：把 B4 测试修复传播到 discussions/posts/notifications/mentions，刷绿扩展套件。
4. **B-4 / §4**：改善测试隔离（site.json / cache backend）；清理 ResourceValidator F811 与 F401。
5. **待办池**：GIN 索引（#4）等按节奏推进；core 成包/框架独立包维持推迟。

---

*创建于：2026-06-18，基于 HEAD=9ea4fd6（+本地 Dockerfile 修复）的第五轮复评*
