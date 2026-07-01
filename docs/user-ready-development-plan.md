# Bias 用户可用版本开发落地文档

日期：2026-07-01

## 目标

本文档用于回答三个问题：

1. Bias、bias_core、bias-ext-tags 与 Flarum、flarum-core、tags 的主要差距是什么。
2. 当前 Bias 的耦合度如何，bias_core 是否已经解耦出来。
3. 下一步应该开发什么，做到什么程度才可以给真实用户使用。

结论先行：

- Bias 已经完成 Flarum-like 主流程和拆包架构的主体工作，但还没有达到真实用户容量准入。
- `bias_core` 已经在运行时基本解耦，不应再直接认识 `bias` 或官方 `bias-ext-*` 生产模块。
- 当前最优下一步不是继续补功能，而是先打穿匿名读路径性能 gate。
- 只有正式 `forum-main --concurrency 20 --duration 300 --fail-on-threshold` 通过后，才进入登录态、写入、上传、moderation、WebSocket 的正式容量 suite。
- 未完成正式容量报告和升级回滚演练前，不能宣称“足够给真实用户长期使用”。

## 当前状态

当前正式容量报告：

```text
bias/reports/capacity/20260701-211043
```

报告状态：

```text
failed, not release evidence
```

目标 seed 规模已经确认：

```text
users: 1000
discussions: 10000
posts: 100000
tags: 200
notifications: 50000
```

当前阻塞项是匿名读路径 P95：

| 接口 | 阈值 | 当前结论 |
| --- | ---: | --- |
| `GET /api/forum` | 300ms | 正式 300 秒报告未通过 |
| `GET /api/discussions/?limit=20` | 300ms | 正式 300 秒报告未通过 |
| `GET /api/tags` | 300ms | 正式 300 秒报告未通过 |
| `GET /api/search?q=loadtest-discussion-00000001` | 800ms | 正式 300 秒报告未通过 |

已经完成但不能替代正式 release evidence 的改进：

- `load_test_http` 已改为每个 worker 复用一个 `httpx.Client`，避免压测器自身制造连接和 TLS/HTTP 开销。
- Discussion list 已做两阶段分页和列表序列化瘦身。
- `/api/discussions/?limit=20` 单接口 120 秒外部压测已经从约 2706ms P95 改善到约 681ms P95，但仍未达到 300ms。
- 最新 in-process profile 显示 `/api/tags` 的 Python 序列化成本是当前明显热点之一。

因此当前项目可以继续内部工程验证，不应开放真实用户试运行。

## 与 Flarum 的差距

### bias 对比 flarum

Bias 站点宿主已经具备：

- Django 后端宿主。
- 前端 shell。
- 扩展发现、启用、禁用、安装态检查。
- 生产 smoke compose。
- 健康检查、安装升级 smoke、容量压测命令雏形。

与 Flarum 的主要差距不再是“有没有 discussion、post、tag、notification 这些主功能”，而是：

| 方向 | Flarum 成熟点 | Bias 当前差距 | 下一步 |
| --- | --- | --- | --- |
| 生产稳定性 | 长期社区验证、成熟升级路径 | 还缺正式容量通过报告和升级回滚演练 | 先完成 P0/P1/P2 gate |
| 扩展生态 | Composer 生态、稳定 extension API | Bias SDK 已成型但仍需固化兼容契约 | 补 SDK 文档、兼容矩阵、发布策略 |
| 性能基线 | 主路径经过真实站点验证 | 匿名读 P95 未过当前目标阈值 | 优先优化读路径 |
| 运维经验 | 部署、队列、缓存、邮件、文件存储已有经验模型 | Bias 有 runbook，但缺目标环境演练 | 补 production-like 演练 |
| 主题和前端生态 | 现有主题/扩展实践多 | Bias 仍以官方扩展为主 | 后置到容量 gate 之后 |

### bias_core 对比 flarum-core

`bias_core` 当前承担平台核心职责：

- 扩展加载和 manifest 解析。
- 权限、资源、preload、runtime service contract。
- 管理命令、health、storage、queue、search baseline。
- 后端公开 SDK 和测试辅助能力。

与 `flarum-core` 的差距：

| 方向 | 当前判断 | 风险 |
| --- | --- | --- |
| 核心平台能力 | 主体已拆出 | 需要继续防止业务语义回流 core |
| 公开 API 稳定性 | 有雏形 | 缺正式 semver/compatibility policy |
| 扩展生命周期 | 可发现、可安装、可 smoke | 安装、升级、卸载的数据迁移策略还需收口 |
| 运行时 contract | 已有 service contract | 老 runtime facade 仍需迁移和废弃节奏 |
| 发布 gate | 命令较完整 | 需要把 gate 固化为 release checklist/CI |

### bias-ext-tags 对比 flarum/tags

`bias-ext-tags` 已具备 tag 主流程：

- tag index。
- discussion 关联 tag。
- tag 权限。
- child/parent tag。
- discussion 列表和创建流程的 tag 扩展。
- preloads 和资源序列化。

主要差距：

| 方向 | 当前问题 | 下一步 |
| --- | --- | --- |
| `/api/tags` 性能 | 200 tags 下序列化耗时偏高 | 加默认 plain fast serializer |
| 权限矩阵 | 主流程已有，边界组合需加强 | 补权限组合测试 |
| 大量 tag 管理 | 需验证后台排序、隐藏、父子级联 | 补 E2E 和容量样本 |
| 与 discussion 的耦合 | tags 会扩展 discussion payload | 继续通过 service contract 和 preload contract 收口 |
| JSON:API/plain 双路径 | 默认读路径不应为通用 serializer 付全量成本 | 保留 JSON:API 行为，优化 plain index |

## 耦合度判断

当前依赖方向总体可控。

允许的方向：

```text
bias -> bias_core
bias -> installed extensions
extensions backend -> bias_core public APIs
extensions frontend -> @bias/core/*
extensions -> other extensions through service contract
```

禁止的方向：

```text
bias_core -> bias
bias_core -> bias_ext_*
bias_ext_a -> bias_ext_b internal modules
extension frontend -> bias/frontend/src internal modules
```

当前结论：

- `bias_core` 在运行时已经基本解耦出来。
- `bias_core` 不应该包含官方扩展业务逻辑，也不应该 import 具体 `bias_ext_*` 生产模块。
- 扩展间依赖应通过 manifest dependency、runtime service contract、preload contract 显式化。
- 老 runtime facade 可以作为兼容层短期保留，但新能力必须走 service contract。
- 每次新增扩展或跨扩展能力，都必须跑 import boundary 和 facade graph gate。

验收命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py validate_extensions --extensions-path D:\files\project\tmp --strict --format json
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --check-runtime-facades --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
```

通过标准：

- 未出现 `bias_core -> bias_ext_*`。
- runtime facade graph 无 cycle。
- 新扩展不直接引用宿主前端内部文件。
- manifest dependency 与 Python package dependency 不漂移。

## 下一步开发总路线

开发顺序必须按 gate 推进，不能跳过容量准入直接做功能市场或主题生态。

### P0：匿名读路径性能

目标：

```text
forum-main 300s 正式压测通过
```

必须优化的接口：

- `/api/forum`
- `/api/discussions/?limit=20`
- `/api/tags`
- `/api/search?q=loadtest-discussion-00000001`

当前下一批具体开发：

1. 为 `/api/tags` 增加默认 plain fast serializer，避免默认 tag index 为通用 resource serializer 付全量成本。
2. 保留 JSON:API 和显式 include 行为，不破坏现有扩展 contract。
3. 复用 `build_tag_serialize_context()` 中的 tag cache 和 permission cache。
4. 避免 parent/children/permission/last posted summary 在 200 tags 下重复遍历。
5. 继续 profile `/api/search`，区分 PostgreSQL full-text 查询成本和 Python section aggregation 成本。
6. 对 `/api/forum` 做 public payload cache，只在 settings、extension set、frontend asset revision 变化时失效。
7. 对 `/api/discussions` 继续减少列表默认 payload，默认不返回搜索专用字段和昂贵 include。

目标阈值：

| 接口 | P95 |
| --- | ---: |
| `/api/forum` | `< 300ms` |
| `/api/discussions/?limit=20` | `< 300ms` |
| `/api/tags` | `< 300ms` |
| `/api/search?q=loadtest-discussion-00000001` | `< 800ms` |

验证命令：

```powershell
cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build web
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health?strict=1'

docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py profile_read_paths --in-process --path "/api/forum" --path "/api/discussions/?limit=20" --path "/api/tags" --path "/api/search?q=loadtest-discussion-00000001" --repeat 5 --warmup 1 --explain --format json

python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
```

完成标准：

- `summary.ok=true`
- error rate `< 0.5%`
- 四个匿名读接口全部达标
- 报告写入 `bias/reports/capacity/<run-id>/summary.md`

详细执行文档见：

```text
bias/docs/anonymous-read-performance-development.md
```

### P1：登录态和写入容量

进入条件：

```text
P0 forum-main 300s passed
```

开发目标：

- 登录态首页和讨论列表达标。
- 发帖、回帖、编辑、删除、隐藏、恢复主流程达标。
- 上传主流程达标。
- moderation/flags/approval 主流程达标。
- 通知队列和异步任务不阻塞写入主链路。

验证命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json
```

完成标准：

- 主写入接口 error rate `< 0.5%`
- 普通发帖 P95 `< 500ms`，不含异步通知完成时间
- 上传 P95 和失败样本可解释
- moderation 操作无权限绕过和数据残留

### P2：生产部署和运维闭环

目标：

- Docker Compose production smoke 可重复启动。
- web、worker、scheduler 使用同一构建产物。
- PostgreSQL、Redis、media/static、SMTP、storage 配置有 dry-run 校验。
- `/api/health?strict=1` 能作为发布 gate。
- 有备份、升级、回滚、恢复手册。

开发任务：

1. 固化 `.env.production-smoke.example`。
2. 固化 `instance/site.example.json`。
3. `install_forum --dry-run --format json` 输出机器可读部署计划。
4. `upgrade_forum --dry-run --format json` 输出迁移计划和风险。
5. `operations-runbook.md` 补目标环境执行步骤。
6. 禁止用 `docker compose down -v` 破坏正式容量 seed 证据。

验证命令：

```powershell
cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml config
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build
docker compose -f deploy/docker-compose.production-smoke.yml ps
python manage.py smoke_http_p95 --base-url http://127.0.0.1:8000 --fail-on-threshold --format json
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6379/1 --result-backend redis://127.0.0.1:6379/2 --timeout 45 --format json
python manage.py install_forum --database postgres --config instance/site.example.json --non-interactive --skip-admin --dry-run --format json
```

完成标准：

- strict health 返回成功。
- worker probe task 成功。
- dry-run 能清楚输出 missing/error/warning/fix。
- 升级失败时有明确回滚路径。

### P3：扩展开发者体验

目标：

第三方开发者不读 Bias 内部源码，也能创建、测试、打包、安装、升级扩展。

开发任务：

1. 完善 `docs/developer/extension-quickstart.md`。
2. 完善后端公开 API 文档。
3. 完善前端 `@bias/core/*` SDK 文档。
4. manifest 增加 schema version、core compatibility、dependency metadata。
5. 扩展安装前输出 plan。
6. 扩展升级前输出 breaking risk。
7. 扩展模板默认使用 service contract 示例。

验证命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py create_extension alpha-tools --target D:\files\project\tmp\.tmp-extension-dx
python manage.py validate_extensions --extensions-path D:\files\project\tmp\.tmp-extension-dx --strict --format json
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp\.tmp-extension-dx --check-runtime-facades --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp\.tmp-extension-dx --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
```

完成标准：

- 新扩展不引用宿主内部代码。
- wheel 可构建、可安装、可发现 manifest。
- enable/disable 生命周期通过。
- 文档能覆盖一个真实扩展从创建到发布的完整路径。

### P4：用户体验和产品完整性

进入条件：

```text
P0/P1/P2 已通过
```

开发目标：

- Tags 后台管理体验补齐。
- Search 结果准确性、空状态、热词 stress 分离。
- Notifications 实时和队列一致性。
- Uploads 文件类型、大小、失败重试、权限检查。
- Realtime 断线重连和广播延迟。
- Security headers、rate limit、audit log。
- 邮件模板和用户设置。

完成标准：

- 浏览器 E2E 覆盖注册、登录、发帖、回帖、编辑、上传、通知、搜索、后台扩展管理。
- 关键用户路径有错误态和恢复路径。
- 后台 stats 能展示 queue、storage、search、realtime、capacity smoke 结果。

## 用户开放分级

### M0：内部开发可用

条件：

- 单元测试和基础 smoke 通过。
- 扩展边界 gate 通过。
- 不要求正式容量报告。

结论：

```text
仅限开发者和内部测试。
```

### M1：受控演示可用

条件：

- P0 匿名读路径通过。
- production smoke 可重复启动。
- 有备份和回滚手册。

结论：

```text
可以给少量内部/客户演示使用，但不建议开放注册。
```

### M2：小规模真实用户试运行

条件：

- P0、P1、P2 通过。
- 正式容量报告存档。
- 升级和回滚演练完成。
- 有人工监控和值守窗口。

结论：

```text
可以小规模开放真实用户，需限制用户规模和发帖量。
```

### M3：正式生产发布

条件：

- P0 到 P4 完成。
- 目标部署环境容量 suite 通过。
- 第三方扩展兼容策略明确。
- 安全、备份、日志、告警、回滚都有演练证据。

结论：

```text
可以作为正式生产版本对外发布。
```

## 每次开发后的必跑 gate

后端基础：

```powershell
cd D:\files\project\tmp\bias_core
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q --tb=short

cd D:\files\project\tmp\bias-content
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q --tb=short

cd D:\files\project\tmp\bias
python manage.py check
python manage.py validate_extensions --extensions-path D:\files\project\tmp --strict --format json
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --check-runtime-facades --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
```

前端基础：

```powershell
cd D:\files\project\tmp\bias\frontend
npm run check:platform
npm run test:node
npm run build
npm run test:e2e
```

生产等价：

```powershell
cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health?strict=1'
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6379/1 --result-backend redis://127.0.0.1:6379/2 --timeout 45 --format json
```

## 当前最具体的下一步

下一步直接进入 P0，不再扩大功能范围。

开发顺序：

1. `bias-ext-tags`：实现 `/api/tags` 默认 plain fast serializer。
2. `bias-ext-tags`：补 children、parent、permission cache、query budget 测试。
3. `bias` production smoke：重建 web，跑 `/api/tags` in-process profile 和 120 秒单接口压测。
4. `bias-content` / `bias-ext-discussions`：继续降低 discussion list 外部 P95。
5. `bias` / `bias_core`：profile `/api/search`，优化普通选择性搜索 gate。
6. `bias`：重跑正式 `forum-main` 300 秒。
7. 只有第 6 步通过后，再进入 P1。

当前不能做的结论：

```text
不能说已经足够给真实用户使用。
不能把 120 秒单接口改善当成正式 release evidence。
不能绕过 P0 去做 marketplace、主题市场或复杂插件 UI。
```

