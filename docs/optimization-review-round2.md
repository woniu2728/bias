# Bias 第二轮评估（生产模式重建后复评）

> 本文档基于在**生产模式**（DEBUG=0、不带临时 DEBUG override）重建 Docker 全栈后的活体验证，以及对 git HEAD=`926560f` 当前代码的直接审查。
>
> 重建方式：`docker compose -f docker-compose.yml --profile queue up -d --build`（用 `-f` 显式排除 `docker-compose.override.yml`，使实例运行在真实生产模式）。
>
> 优先级：P0=尽快、P1=近期、P2=中期、P3=收尾。

---

## 0. 结论速览

| 类别 | 结论 |
| --- | --- |
| 上一轮 P0/P1（安全/部署/性能配置） | 基本全部落地，活体验证生效 |
| 本轮新发现 | 2 个队列检测相关运行时 BUG（P1，影响部署可靠性） |
| 仍存在 | 代码层性能/安全/架构/冗余问题（与第一轮一致，代码未变） |

---

## 1. 重建活体验证：上一轮修复确实生效

| 修复项 | 验证证据 |
| --- | --- |
| celery 并发与内存 | 并发 `52 → 2`（启动日志 `concurrency: 2 (prefork)`），内存 `2.76GiB → 189MiB`（`docker stats`），降约 93% |
| `/assets` 内容哈希资源缓存 | `curl -I` 实测 `Cache-Control: public, immutable; max-age=31536000` + CSP + `X-Frame-Options` |
| SPA 文档 | `/` 实测 `Cache-Control: no-cache` + 完整安全头（CSP / X-Frame / X-Content-Type-Options） |
| DB/Redis 端口收敛 | `docker ps` 显示 `bias_db 5432/tcp`、`bias_redis 6379/tcp`——仅 `expose`，无 `0.0.0.0` 对外映射 |
| 反代安全设置 | `check --deploy` 仅剩 http 部署预期的 4 条 warning（W004/W008/W012/W016），`SITE_SCHEME=https` 时会自动开启对应 secure 项 |
| 容器健康检查 | web/celery/nginx 均有 healthcheck，重建后 `ps` 显示 `(healthy)` |

> 说明：`check --deploy` 的 4 条 warning 是 `http://localhost:8080` 演示部署的**预期值**（SITE_SCHEME=http），不是缺陷。

---

## 2. 本轮新发现 BUG（P1，部署可靠性）

### 2.1【P1】队列 worker 检测假阴性 → `doctor` 稳定误报 CRITICAL
- **现象**：celery 容器 `healthy`、并发 2 正常运行，从 web 容器执行 `celery -A config inspect ping --timeout=8` 可稳定看到 `-> celery@xxxx: OK / pong / 1 node online`；但 `python manage.py doctor` **稳定复现** `CRITICAL: bias.queue-worker-unavailable（队列已启用但没有可用 worker）`。
- **根因**：`apps/core/queue_service.py:127` 使用 `celery_app.control.inspect(timeout=0.5)` 做广播 ping，**0.5 秒超时过短**。正常 broker 往返延迟下 worker 回复来不及返回，`ping_result` 为空，被判为"无 worker"。
- **影响**：
  - `doctor` 在任何启用队列的环境都误报 CRITICAL，污染部署健康闸门 / CI doctor 检查。
  - 同一逻辑被 `startup_guard` 复用，见 2.2。
- **建议**：把探活超时提到 2–5s，并加一次重试；或改用更轻量、稳定的存活判定（如读取 worker 心跳键）。

### 2.2【P1】启动时序崩溃：队列启用时 web 先于 celery 启动即硬失败
- **现象**：重建过程中亲眼观测——`bias_web` 首次启动时 `config/asgi.py:15 → apps/core/startup_guard.py:33` 抛 `ImproperlyConfigured: Bias 生产启动自检失败 …… [bias.queue-worker-unavailable]`，gunicorn worker `exited with code 3 / Worker failed to boot`，进入崩溃重启，直到 celery 上线后重试才成功；其间 `bias_nginx` 因 `depends_on web service_healthy` 一直未能启动。
- **根因**：`startup_guard.enforce_production_runtime_checks()` 把"队列 worker 不在线"当作**阻断级**自检失败；而 web 与 celery 仅都 `depends_on db/redis`，web 不等待 celery，celery `start_period` 又有 40s，于是 web 必然先起、必然先崩。叠加 2.1 的 0.5s 误判，崩溃概率进一步放大。
- **影响**：启用队列的生产部署在冷启动时出现 web 崩溃重启窗口，nginx 连带延迟可用。
- **建议**（任选其一或组合）：
  - web 启动自检对"瞬时无 worker"降级为 warning，而非 raise 阻断启动。
  - 仅在 `--profile queue` 时给 web 增加 `depends_on celery: condition: service_healthy`。
  - 与 2.1 一并放宽探活超时。

> 2.1 与 2.2 同根（检测过严），建议合并修复：放宽 `queue_service` 探活超时+重试，并让 `startup_guard` 不因 worker 缺失阻断 web 启动。

---

## 3. 仍存在的代码层问题（与第一轮一致，重建后依旧成立）

### 3.1 性能（P1）
- **`_get_enabled_module_ids` 序列化热路径每对象查库且无 memoization**：`apps/core/resource_registry.py:73` 每次执行 `ExtensionInstallation.objects.filter(source="filesystem")`，被 `get_fields`/`get_relationships` 等在 `:331/340/365/373` 调用，列表序列化每个对象重复查库。建议按请求缓存或带失效信号的 memoize。
- **全文搜索无 GIN 索引**：`extensions/search/backend/services.py` 用 `SearchVector(...)` 实时算 `to_tsvector`，但全库无任何 `GinIndex`/`SearchVectorField`（grep 仅 services.py 命中）。大数据量下顺序扫描。建议加 `SearchVectorField` + `GinIndex` 或函数索引。
- **多 worker + LocMem 不一致（仅无 Redis 时）**：web 现为 gunicorn 2 worker，回退 `LocMemCache` 时限流计数/在线状态/`public_forum_settings` 各 worker 不一致。生产默认 Redis 时无碍，建议 `doctor` 在"生产+多worker+LocMem"组合显式报警。

### 3.2 安全 / 功能 BUG
- **P2 无 JWT 吊销**：`config/settings.py` 的 `NINJA_JWT` 无 blacklist/rotation、未装 token_blacklist app；`extensions/users/backend/api.py` `logout` 仅清 cookie。登出/改密后既有 token 在有效期内仍可用。建议黑名单+轮换或 token version。
- **P2 登录成功清空 IP 维度限流计数**：`extensions/users/backend/api.py` 登录成功调 `clear_auth_rate_limit("login", …)`，而 `auth_rate_limit.py:_rate_limit_keys` 同时返回 ip+id 两个 key，等于清掉整个 IP 的失败计数。共享 IP 上持有有效账号者可周期性重置 IP 节流。建议成功登录只清 id key。
- **P2 删除举报用只读权限授权**：`extensions/flags/backend/services.py:151` `delete_post_flags` 校验 `admin.flag.view`（只读），而系统已有 `admin.flag.delete`（handlers.py:152）。破坏性删除应用 `admin.flag.delete`。
- **P2 注册成功不计入限流**：`extensions/users/backend/api.py` register 仅在失败分支 `record`，成功建号不计数。建议成功也 record。
- **P2 `/api/search` 路由层无 viewForum 闸门**：匿名可搜索，仅靠逐行可见性兜底。建议路由层加论坛查看权限门槛。
- **P3**：限流 check/record 非原子 TOCTOU（`auth_rate_limit.py:29-42`）；`forgot_password` 吞掉邮件发送失败仍报"已发送"无告警；`update_admin_user` 无"保留最后一个 superuser"护栏；批量通知绕过用户通知偏好与 actor==recipient 去重。

### 3.3 架构（P1/P2，上一轮"拆 god 文件/收敛样板"只做了一半）
- **P1 `ResourceRegistry` 仍是上帝类**：`apps/core/resource_registry.py` 单类 163 方法/2750 行，混注册+查询+分发+校验+序列化+JSON:API+搜索+预加载。建议拆 RegistryStore / Validator / JsonApiSerializer / PreloadPlanner / SearchBridge。
- **P1 `admin_extension_detail.py` 上帝文件**：70 个模块级函数/1864 行，迁移分析/前端路由/权限矩阵/设置/主题/调试一锅烩。建议按子域拆分。
- **P2 `ResourceEndpointRunner` 泄漏式抽取**：`apps/core/resource_endpoint_runner.py:25-50` 反复访问 `registry._resolve_*` 私有方法，逻辑仍绑死 registry，等于双向耦合、无法独立测试。建议提独立 `EndpointContextResolver`。
- **P2 core 仍含论坛领域概念**：`forum_registry.py` / `forum_runtime.py` / `settings_service.py:449` 把 post/discussion/notification 领域逻辑放在平台层，破坏"扩展优先"。建议领域下沉到扩展。

### 3.4 冗余 / 死代码（P2/P3）
- `runtime_*`（posts/tags/discussions/users/moderation）共约 116 个薄封装转发函数，`runtime_core.py` 已引入 `RuntimeServiceProxy` 想替代但代理实例零消费——抽象加了样板没删，反多出死对象。
- `apps/core/resource_registry.py:1035` 区域的 `_dispatch_index/show/create/update/delete`（约 133 行）疑似死代码（实际分发走 `ResourceEndpointRunner`），删除前需确认无反射调用。
- `apps/core/admin_runtime_helpers.py` 整文件是 `runtime_diagnostics` 的纯 re-export，仅 1 个测试引用；探活 lambda 在 `runtime_checks.py:39` 与 `admin_runtime_summary.py:20` 逐字重复。
- 17 个扩展中 9 个 `frontend/forum/sdk.js` 与 `nodeSdk.js` 字节完全相同；其余 8 个仅 node 版把 `.vue` 导出改 null。建议单一 `sdk.js` + 打包层约定。
- flake8：228 条 F401 未用导入（`apps/core/tests/common.py` 居多）、2353 条 F405（测试拆分后 `import *` 连带）——非 bug，属整洁度。建议 `__all__` / `# noqa` 或显式导入。

---

## 4. 建议落地顺序

1. **本轮新 BUG（P1）**：合并修复 2.1 + 2.2（放宽 `queue_service` 探活超时+重试，`startup_guard` 不因 worker 缺失阻断 web 启动），跑 `apps/core/tests/test_queue.py` 验证。
2. **P1 性能**：`_get_enabled_module_ids` 加请求级 memoization（改动小收益大）→ 搜索建 GIN 索引。
3. **P2 安全**：JWT 吊销 → 登录限流只清 id key → flag 删除权限码 → 注册成功计数。
4. **架构/冗余**：先删死代码（3.4 前三项，成本低）；拆 `ResourceRegistry` / `admin_extension_detail` 排期推进。

---

## 5. 善后提示
- `docker-compose.override.yml`（注入 `DEBUG=1`）仍在仓库。本轮用 `-f docker-compose.yml` 显式绕开；下次直接 `docker compose ...`（不带 `-f`）会再次加载它使实例退回 DEBUG 模式。site.json 已合规（installed=True、debug=False、真实密钥、smtp 后端、use_redis=True），**建议删除该临时 override**。
- 当前 celery 由 `--profile queue` 启动；按设计默认不随栈启动。

---

*创建于：2026-06-17（生产模式重建后复评）*
