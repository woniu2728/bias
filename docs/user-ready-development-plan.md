# Bias 用户可用版本开发落地文档

日期：2026-07-01

## 目标

本文档用于回答三个问题：

1. Bias、bias_core、bias-ext-tags 与 Flarum、flarum-core、tags 的主要差距是什么。
2. 当前 Bias 的耦合度如何，bias_core 是否已经解耦出来。
3. 下一步应该开发什么，做到什么程度才可以给真实用户使用。

结论先行：

- Bias 已经完成 Flarum-like 主流程和拆包架构的主体工作，且 P0 匿名读容量 gate、P1 登录态/写入容量 gate 已通过，但还没有完成真实用户完整容量准入。
- `bias_core` 已经在运行时基本解耦，不应再直接认识 `bias` 或官方 `bias-ext-*` 生产模块。
- 当前最优下一步不是继续补功能，而是进入 WebSocket/realtime、生产部署、升级回滚、运维闭环的正式 gate。
- 正式 `forum-main` 和 P1 auth/write/upload/moderation 容量 suite 已通过，P2+ gate 是当前阻塞项。
- 未完成 P2+ 部署运维、升级回滚和目标环境演练前，不能宣称“足够给真实用户长期使用”。

## 当前状态

当前正式容量报告：

```text
P0 anonymous read: bias/reports/capacity/20260702-011925
P1 auth/write/upload/moderation: bias/reports/capacity/20260702-020409
WebSocket/realtime + P2 production-smoke ops: bias/reports/capacity/20260702-025600
```

报告状态：

```text
P0: passed, release evidence for anonymous read gate
P1: passed, release evidence for authenticated read/write/upload/moderation gate
Realtime/P2 smoke: passed for local production-smoke stack only
```

目标 seed 规模已经确认：

```text
users: 1000
discussions: 10000
posts: 100000
tags: 200
notifications: 50000
```

P0 匿名读路径正式通过结果：

| 接口 | P95 | 阈值 | 当前结论 |
| --- | ---: | ---: | --- |
| `GET /api/forum` | 227.741ms | 300ms | 通过 |
| `GET /api/discussions/?limit=20` | 286.790ms | 300ms | 通过 |
| `GET /api/tags` | 218.777ms | 300ms | 通过 |
| `GET /api/search?q=loadtest-discussion-00000001` | 477.282ms | 800ms | 通过 |

已经完成并进入 P0 release evidence 的改进：

- `load_test_http` 已改为每个 worker 复用一个 `httpx.Client`，避免压测器自身制造连接和 TLS/HTTP 开销。
- Discussion list 已做两阶段分页和匿名默认列表轻量序列化。
- `/api/tags` 已增加 anonymous/plain/default fast serializer 和缓存失效链路。
- `/api/forum`、`/api/search?q=loadtest-discussion-00000001`、`/api/tags`、`/api/discussions/?limit=20` 均已通过正式 300 秒 `forum-main` gate。

P1 已在 production smoke 环境完成；是否开放真实用户试运行现在取决于 WebSocket/realtime、部署升级回滚和目标环境运维 gate 的后续结果。

P1 登录态和写入路径正式通过结果：

| Profile | 请求数 | Error rate | 关键 P95 | 阈值 | 当前结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| `forum-main-auth` | 33256 | 0.0 | unread list `284.129ms` | 300ms | 通过 |
| `forum-write` | 2036 | 0.0 | reply `384.437ms` | 500ms | 通过 |
| `forum-write-mixed` | 8085 | 0.0 | like `134.853ms` | 500ms | 通过 |
| `forum-upload` | 4265 | 0.0 | upload `202.891ms` | 800ms | 通过 |
| `forum-write-moderation` | 2782 | 0.0 | hide `82.947ms` | 300ms | 通过 |

P1 正式容量报告位置：

```text
bias/reports/capacity/20260702-020409/summary.md
```

WebSocket/realtime 与 P2 production-smoke 结果：

| Gate | 关键结果 | 当前结论 |
| --- | --- | --- |
| WebSocket external load | 20/20 connections，connect P95 `3.019ms`，subscribe P95 `20.345ms`，broadcast P95 `2.604ms` | 通过 production-smoke realtime gate |
| Strict health | `status=ok`，`strict_failed=false` | 通过 |
| HTTP P95 smoke | 5 targets，0 failed | 通过 |
| Queue worker smoke | 1 worker online，probe task ok | 通过 |
| `install_forum --dry-run --format json` | 8 install steps，0 errors，0 warnings | 通过 |
| `upgrade_forum --dry-run --format json` | 10 upgrade steps，`dry_run=true`，`executed=false`，0 errors，0 warnings | 通过 |
| `backup_forum --format json` | 创建 site config、PostgreSQL dump、media、static/frontend 四类备份产物 | production-smoke 备份创建通过 |
| `verify_forum_backup --format json` | 验证 site config 可解析、PostgreSQL dump 可 `pg_restore --list`、目录备份可遍历 | production-smoke 备份验证通过 |
| `upgrade_forum --non-interactive --format json` | 10 executed steps，`dry_run=false`，`executed=true`，0 errors，0 warnings | production-smoke 升级执行通过 |
| Post-upgrade smoke | strict health、HTTP P95 smoke、queue worker smoke 均通过 | 通过 |
| `plan_forum_rollback --require-existing-backups --format json` | 输出 4 类必需备份产物、6 个恢复步骤和 4 个恢复后验证步骤；备份产物检查通过 | 计划生成通过 |
| `rehearse_forum_restore --format json` | 隔离临时库恢复 PostgreSQL dump，验证 31 张 public 表，复制 media/static 到临时目录并删除临时库 | production-smoke 隔离恢复演练通过；destructive 回滚演练未完成 |
| `restore_forum_backup --dry-run --format json` | `summary.ok=true`，4 个 destructive live restore steps，`dry_run=true`，`executes_live_restore=false` | production-smoke dry-run 已归档；目标环境 live 恢复未执行，正式 live 证据还必须包含 site_config/database/media/static_frontend post-restore verification |
| `smoke_runtime_integrations --storage-write --format json` | local storage 临时对象写入/删除通过，email 配置 dry-run 通过 | production-smoke 本地 runtime integration smoke 通过；真实 SMTP/对象存储未验证 |

本轮报告位置：

```text
bias/reports/capacity/20260702-025600/summary.md
```

这份报告只证明本地 production-smoke 栈的 realtime、运维 smoke、隔离恢复演练和本地 storage/email 配置 gate，不替代真实公网 HTTPS/WebSocket、SMTP、对象存储、多节点部署、备份、升级执行和 destructive 回滚恢复演练。

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
| 生产稳定性 | 长期社区验证、成熟升级路径 | P0/P1 正式容量与本地 production-smoke realtime/ops smoke 已通过；还缺目标环境和升级回滚演练 | 继续完成 P2+ gate |
| 扩展生态 | Composer 生态、稳定 extension API | Bias SDK 已成型但仍需固化兼容契约 | 补 SDK 文档、兼容矩阵、发布策略 |
| 性能基线 | 主路径经过真实站点验证 | P0 匿名读、P1 登录态/写入/上传/moderation 和 production-smoke WebSocket 已过；目标环境容量尚未完成正式证据 | 推进目标环境 P2+ gate |
| 运维经验 | 部署、队列、缓存、邮件、文件存储已有经验模型 | Bias 有 runbook 和 production-smoke ops 证据，但缺目标环境演练 | 补目标环境演练 |
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
| `/api/tags` 性能 | P0 匿名 tag index 已通过容量 gate | 后续验证后台管理和登录态组合 |
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

已完成：

1. 为 `/api/tags` 增加默认 plain fast serializer，避免默认 tag index 为通用 resource serializer 付全量成本。
2. 保留 JSON:API 和显式 include 行为，不破坏现有扩展 contract。
3. 复用 `build_tag_serialize_context()` 中的 tag cache 和 permission cache。
4. 避免 parent/children/permission/last posted summary 在 200 tags 下重复遍历。
5. 搜索 gate 使用选择性 seed 词并通过正式 P0 容量报告。
6. `/api/forum` P95 已在正式 P0 容量报告中达标。
7. `/api/discussions` 默认匿名列表已减少 payload，默认不返回搜索专用字段和昂贵 include。

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

当前结果：

- `bias/reports/capacity/20260702-011925/summary.md` 已归档。
- `summary.ok=true`，error rate `0.0`，四个匿名读接口全部达标。

详细执行文档见：

```text
bias/docs/anonymous-read-performance-development.md
```

### P1：登录态和写入容量

当前状态：

```text
passed, release evidence: bias/reports/capacity/20260702-020409/summary.md
```

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

当前结果：

- `forum-main-auth` 300 秒：`summary.ok=true`，error rate `0.0`，四个登录态读接口全部达标。
- `forum-write` 120 秒：`summary.ok=true`，reply P95 `384.437ms`。
- `forum-write-mixed` 120 秒：`summary.ok=true`，全部混合写入目标达标，隔离目标已清理。
- `forum-upload` 120 秒：`summary.ok=true`，upload P95 `202.891ms`。
- `forum-write-moderation` 60 秒：`summary.ok=true`，审核写入目标全部达标，隔离目标已清理。

本阶段完成的关键修正：

- 登录态 discussion list 默认轻量响应，`filter=my`/`filter=unread` 首屏跳过昂贵 total count。
- unread filter 使用 `Subquery + Coalesce` annotation，避免 join duplication 和不必要 `distinct()` 成本。
- `load_test_http` 支持请求时序列渲染和按目标字段独立推进的状态转换池，避免 like/unlike 压测重复命中同一状态。
- `prepare_load_test_actors` 创建稳定 auth/moderator 账号并关闭负载测试通知偏好，避免不可达 SMTP 污染写入容量证据。
- production smoke 中 web/worker 使用同一构建产物，最终 P1 正式压测均在容器内执行。

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
5. `backup_forum --format json` 创建升级前备份产物。
6. `verify_forum_backup --format json` 验证备份产物可读。
7. `plan_forum_rollback --require-existing-backups --format json` 检查备份产物并输出恢复计划。
8. `rehearse_forum_restore --format json` 在隔离临时目标中恢复备份并验证，不覆盖当前运行数据。
9. `restore_forum_backup --dry-run --format json` 输出受保护 live restore 计划；非 dry-run 必须双重确认。
10. `smoke_runtime_integrations --format json` 验证 SMTP 配置和 storage backend；目标环境必须开启真实 SMTP 连接、storage 写删、非 local 对象存储和 warning 失败策略。
11. `inspect_target_topology --format json` 输出目标环境 web/worker/scheduler、共享 image/release、数据库、Redis 和负载均衡拓扑证据。
12. `plan_target_environment_evidence --format json` 输出目标环境 evidence run plan，固定 `schema_version=1`、文件名、`archive_command`、`safe_to_run_unattended`、`safe_archive_ready`、`requires_completed_commands`、`execution_group`、`target_value_errors`、顶层 `safe_archive_commands`、`safe_archive_manifest`、`excluded_from_safe_archive`、`command_groups`、`execution_sequence`、`execution_queues`、`dependency_execution_waves`、`substitution_required_commands`、`target_value_required_commands`、`dependency_blocked_commands`、`manual_approval_commands`、`final_validation_commands` 和可选 PowerShell/POSIX shell safe-only 脚本，避免目标环境归档漏项、旧格式计划、待替换 token、本地/临时目标值或前置依赖未完成命令误进无人值守脚本、提前跑最终校验、误跑实际升级或误跑 live restore。
13. `validate_target_environment_evidence --format json` 汇总校验目标环境归档证据，覆盖 HTTPS/WSS、SMTP/object storage、multi-node、live restore、目标 P0/P1 容量 suite，以及可选 `--plan-file` 的 final plan manifest 一致性和 `target_archive_integrity` output/stderr 归档完整性，防止把 production-smoke、模板计划、缺失 output 或带异常 stderr 的执行结果误当成完整 P2。
14. `operations-runbook.md` 补目标环境执行步骤。
15. 禁止用 `docker compose down -v` 破坏正式容量 seed 证据。

验证命令：

```powershell
cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml config
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build
docker compose -f deploy/docker-compose.production-smoke.yml ps
python manage.py smoke_http_p95 --base-url http://127.0.0.1:8000 --fail-on-threshold --format json
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6379/1 --result-backend redis://127.0.0.1:6379/2 --timeout 45 --format json
python manage.py install_forum --database postgres --config instance/site.example.json --non-interactive --skip-admin --dry-run --format json
python manage.py upgrade_forum --config instance/site.json --dry-run --non-interactive --format json
python manage.py backup_forum --config instance/site.json --backup-dir backups/latest --format json
python manage.py verify_forum_backup --config instance/site.json --backup-dir backups/latest --format json
python manage.py upgrade_forum --config instance/site.json --non-interactive --format json
python manage.py plan_forum_rollback --config instance/site.json --backup-dir backups/latest --require-existing-backups --format json
python manage.py rehearse_forum_restore --config instance/site.json --backup-dir backups/latest --format json
python manage.py restore_forum_backup --config instance/site.json --backup-dir backups/latest --dry-run --format json
python manage.py smoke_runtime_integrations --storage-write --format json
python manage.py inspect_target_topology --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database <db-endpoint> --redis <redis-endpoint> --load-balancer https://<your-domain> --require-multi-node --format json
python manage.py plan_target_environment_evidence --base-url https://<your-domain> --report-dir reports/capacity/<target-run-id> --p0-report-dir reports/capacity/<target-p0-run-id> --p1-report-dir reports/capacity/<target-p1-run-id> --backup-dir s3://<backup-bucket>/<release-or-timestamp> --discussion-id <discussion-id> --load-username <load-user> --load-password <load-password> --moderator-username <moderator-user> --moderator-password <moderator-password> --redis-broker-url redis://<redis-host>:6379/1 --redis-result-backend redis://<redis-host>:6379/2 --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database-endpoint <db-endpoint> --redis-endpoint <redis-endpoint> --write-plan-file reports/capacity/<target-run-id>/target-environment-evidence-plan.json --write-safe-script reports/capacity/<target-run-id>/target-environment-safe-archive.ps1 --write-safe-shell-script reports/capacity/<target-run-id>/target-environment-safe-archive.sh --format json
python manage.py validate_target_environment_evidence --report-dir reports/capacity/<target-run-id> --p0-report-dir reports/capacity/<target-p0-run-id> --p1-report-dir reports/capacity/<target-p1-run-id> --plan-file reports/capacity/<target-run-id>/target-environment-evidence-plan.json --write-remediation-checklist reports/capacity/<target-run-id>/target-environment-remediation-checklist.md --require-multi-node --format json
```

完成标准：

- strict health 返回成功。
- worker probe task 成功。
- dry-run 能清楚输出 missing/error/warning/fix。
- 升级失败时有明确回滚路径。

当前结果：

- `bias/reports/capacity/20260702-025600/summary.md` 已归档。
- production-smoke strict health、HTTP P95 smoke、queue worker smoke、install dry-run JSON、upgrade dry-run JSON 均通过。
- `backup_forum --format json` 已在 production-smoke 中创建机器可读备份产物。
- `verify_forum_backup --format json` 已在 production-smoke 中验证备份产物可读。
- `upgrade_forum --non-interactive --format json` 已在 production-smoke 中实际执行 10 个升级步骤并输出纯 JSON。
- 升级后 strict health、HTTP P95 smoke、queue worker smoke 均通过。
- `plan_forum_rollback --require-existing-backups --format json` 已能用备份产物输出机器可读回滚计划。
- `rehearse_forum_restore --format json` 已在 production-smoke 中把 PostgreSQL dump 恢复到隔离临时库，验证 31 张 public 表，复制 media/static 备份到临时目录，并删除临时库；未覆盖当前运行数据。
- `restore_forum_backup --dry-run --format json` 已提供受保护 destructive live restore 入口；非 dry-run 需要 `--i-understand-this-overwrites-live-data` 和 `--confirm-phrase "restore live forum data"`，并且正式目标环境证据必须归档 post-restore `verification`，覆盖 site config 读取、live database 读取和 media/static frontend 目录扫描。
- `smoke_runtime_integrations --storage-write --format json` 已在 production-smoke 中完成 local storage 临时对象写入/删除和 email 配置 dry-run；未连接真实 SMTP，未验证对象存储 provider。
- `plan_target_environment_evidence --format json` 已生成目标环境执行清单；它只规划 25 个证据命令，输出 `schema_version=1`，`executes_commands=false`，当前模板产物包含 3 条顶层 `safe_archive_commands`、3 条 `safe_archive_manifest`、22 条 `excluded_from_safe_archive`、5 个 `command_groups`、5 步 `execution_sequence`、7 个 `execution_queues`、`summary.execution_queue_counts`、3 个 `dependency_execution_waves`、`summary.dependency_execution_wave_count=3`、20 条 `substitution_required_commands`、0 条 `target_value_required_commands`、8 条 `dependency_blocked_commands`、2 条 `manual_approval_commands`、1 条 `final_validation_commands`，并生成 safe-only PowerShell 和 POSIX shell 脚本；safe-only 脚本会先创建 safe 输出目录，PowerShell 版本会在每条归档命令前重置 `$LASTEXITCODE` 并在执行后同时检查 `$?` 与 `$LASTEXITCODE`，POSIX shell 版本会对输出和 stderr 重定向路径加 shell 引号，且每条归档命令后都会立即检查对应 `output_file` 已生成且非空、`stderr_file` 已生成且为空，缺失、空 output 或非空 stderr 都会失败，同时不包含 `<...>` 待替换 token、本地/临时 target value、相对备份路径、前置依赖未完成命令、实际升级、live restore 或最终校验。`command_groups` 按 `execution_group` 聚合 command keys、原始 commands、output/stderr files、archive commands、审批状态、destructive 状态、substitution 状态、target-value 状态和 dependency-blocked 状态，可在目标环境执行前分流；`execution_sequence` 给出推荐执行顺序，确保 final validation 最后运行；`execution_queues` 直接派生 safe unattended、requires substitution、target-value required、dependency blocked、maintenance approval、destructive approval 和 final validation 队列，保留完整 command/output/stderr/archive 元数据，`summary.execution_queue_counts` 提供同一组队列计数。当前模板队列为 3 条 `safe_unattended`、20 条 `requires_substitution`、0 条 `target_value_required`、8 条 `dependency_blocked`、1 条 `maintenance_approval`、1 条 `destructive_approval` 和 1 条 `final_validation`，其中 live restore 同时在 substitution、dependency-blocked 与 destructive 队列中，避免误并入 safe-only 执行。`dependency_execution_waves` 将前置依赖命令分成 3 波：第 1 波 `post_upgrade_strict_health`、`post_upgrade_http_smoke`、`post_upgrade_queue_worker`、`restore_rehearsal`、`p1_forum_write_mixed`，第 2 波 `restore_dry_run`、`p1_forum_moderation`，第 3 波 `live_restore`。目标环境传入真实 base URL、discussion id、压测账号、Redis、durable backup dir 和 topology 参数后，queue worker、WebSocket、backup、topology 和部分容量命令可进入 `safe_archive_commands`；post-upgrade smoke、restore dry-run、P1 mixed write/moderation 等有 `requires_completed_commands` 的命令必须等前置证据完成后再执行。实际升级为 `execution_group=maintenance_approval`，live restore 为 `execution_group=destructive_approval`，最终校验为 `execution_group=final_validation` 且自动带上同一目标 run 的 `--plan-file` 和同一 report dir 的 `--write-remediation-checklist`，不替代目标环境执行结果。
- `validate_target_environment_evidence` 的 plan consistency 校验已覆盖 plan `schema_version=1`、顶层 `base_url`/`backup_dir`/`remediation_checklist`、顶层 `errors`/`warnings` 及 summary 计数、唯一性、dependency graph、派生命令列表和波次一致性：`base_url` 必须使用 HTTPS，且 health、HTTP smoke、WebSocket、topology、P0/P1 capacity 计划命令都必须使用同一个 plan `base_url`，对应 command metadata 的 `base_url` 也必须等于 plan `base_url`，不使用 base URL 的命令不得携带陈旧 `base_url`；`backup_dir` 必须是真实 durable target backup location、不能是 `<...>` 占位符或本地路径，且 backup、verify、rollback、restore rehearsal、restore dry-run 和 live restore 计划命令都必须使用同一个 plan `backup_dir`，对应 command metadata 的 `backup_dir` 也必须等于 plan `backup_dir`，不使用 backup dir 的命令不得携带陈旧 `backup_dir`；queue worker 和 post-upgrade queue worker 计划命令必须携带非空 `redis_broker_url`/`redis_result_backend` metadata，且 command/archive_command 必须使用相同 broker/result backend，其他命令不得携带陈旧 Redis metadata；multi-node topology 计划命令必须携带 web/worker/scheduler 节点数、image、app version、database/Redis endpoint 和 load balancer metadata，且 command/archive_command 必须使用相同 topology 参数，其他命令不得携带陈旧 topology metadata；P0/P1 capacity 计划命令必须携带 profile、concurrency、duration、登录账号、discussion id 和 isolated target 开关等 `capacity_profile` metadata，且 command/archive_command 必须使用相同容量参数，其他命令不得携带陈旧 capacity metadata；`remediation_checklist` 必须指向同一 `--report-dir` 下的固定文件，且 Markdown checklist 会在 planned commands 中渲染 `base_url`、`backup_dir`、Redis、topology 和 capacity profile metadata，方便目标环境执行者直接核对替换值；`errors` 必须为空，`errors`/`warnings` 必须是非空字符串列表且 `summary.error_count`/`summary.warning_count` 必须与列表长度一致；`summary.command_count`、`summary.missing_output_count`、`summary.destructive_command_count`、`summary.safe_unattended_command_count`、`summary.safe_archive_ready_command_count`、`summary.excluded_from_safe_archive_count` 也必须与 `commands` 派生结果一致；`commands`、`safe_archive_manifest`、`excluded_from_safe_archive`、`execution_sequence`、`dependency_execution_waves` 和派生命令列表必须是 object 列表；`command_groups` 的每个分组必须是 object，内部 action/command/output/stderr/archive/dependency 列表必须由非空字符串组成，审批、destructive、safe、substitution、target-value 和 dependency-blocked 状态必须是真正的 JSON boolean；`execution_queues` 的每个队列必须是 object，队列内 `commands` 必须是 object 列表，`command_keys` 和 `archive_commands` 必须由非空字符串组成；`commands.key` 必须属于固定目标环境证据命令集合且不能混入未知命令，`commands.phase` 必须符合固定证据阶段，`commands.execution_group` 必须由 destructive/manual approval/final validation/substitution/target-value 状态派生，每个固定 command key 还必须包含对应的核心 manage.py 子命令和关键 gate 参数，并且 `safe_to_run_unattended` 必须由 `execution_group=safe_unattended`、无 substitution、无 target value error 派生，`safe_archive_ready` 必须再要求无前置依赖，`safe_archive_manifest`、`excluded_from_safe_archive` 和顶层 `safe_archive_commands` 的顺序必须按 `commands` 列表派生，`excluded_from_safe_archive.exclude_reasons` 必须和 destructive/manual/substitution/target-value/dependency/final-validation 状态精确派生一致，`upgrade_executed`、`live_restore`、`validate_target_environment_evidence` 的 `manual_approval_required`、`destructive`、`safe_to_run_unattended` 和 `safe_archive_ready` 必须符合固定安全属性，且 post-upgrade smoke 必须依赖 `upgrade_executed`、restore rehearsal 必须依赖 `backup_verification`、restore dry-run 必须依赖 `backup_verification` 与 `restore_rehearsal`、live restore 必须依赖 `backup_verification` 与 `restore_dry_run`、P1 mixed/moderation 必须按写入链路逐级依赖，其他命令不得携带非预期依赖，防止 destructive、维护审批、最终校验、前置依赖命令或错误 profile/工具命令被误标成 safe archive ready，也防止手工削弱 live restore/restore dry-run 依赖后误采信计划；`commands.key`、`safe_archive_manifest.key`、`excluded_from_safe_archive.key` 必须非空且不能重复，每条 command 的 `phase`、`execution_group`、`command`、`output_file`、`stderr_file` 和 `archive_command` 必须非空，顶层 `safe_archive_commands` 和 commands/safe manifest/excluded manifest 中的列表字段必须由非空字符串组成，commands、safe manifest 和 excluded manifest 中的布尔字段必须是真正的 JSON boolean，`commands.exists` 必须是真正的 JSON boolean 且 `safe_archive_manifest.exists` 必须与对应 command 一致，`commands.output_file` 和 `commands.stderr_file` 不能重复；`manual_approval_commands`、`final_validation_commands`、`substitution_required_commands`、`target_value_required_commands`、`dependency_blocked_commands` 及其 summary 计数必须与每条 command 派生结果一致；`requires_completed_commands` 必须引用同一计划中的命令 key，不能自引用，不能形成环路；`dependency_execution_waves` 必须与命令依赖派生结果一致，`summary.dependency_execution_wave_count` 必须与波次数一致，且落盘 plan 不得包含 `plan_file_path`、`safe_script_path` 或 `safe_shell_script_path` 这类只应出现在控制台输出中的运行时字段，防止目标环境执行队列卡死、错误排序、审批/替换/依赖清单漂移、证据归档互相覆盖或误提交被 stdout 污染的 plan。传入有效 `--plan-file` 后还会追加 `target_archive_integrity` 检查，要求 plan 中每个非 final validation 证据命令的 `output_file` 已归档且非空，且 `stderr_file` 已归档为可读空文件；失败 action details 和 Markdown checklist 会列出 `missing_output_keys`、`missing_stderr_keys` 与 `non_empty_stderr_keys`，便于直接定位需要补归档或重跑的计划命令，避免把缺失/空 output、缺失/无效 stderr 或非空 stderr 的目标环境执行结果当成通过证据。多个失败 action 指向同一 planned command 时，remediation 的 command groups、execution queues 和 dependency waves 会去重，避免同一命令在执行清单中重复出现。
- 本地 P2 evidence plan/validator 继续加固：`external_websocket` 现在输出并校验 `websocket_profile`，覆盖 discussion id、20 连接数、P95/broadcast P95 阈值和 fail-on-threshold；`runtime_integrations` 输出并校验 `runtime_integration_profile`，覆盖 SMTP connect、storage write、object storage requirement 和 fail-on-warning；`validate_target_environment_evidence` 输出并校验 `validation_profile`，要求 `plan_file`、`remediation_checklist` 和 `require_multi_node` 与最终校验命令一致。上述 metadata 会进入 planned commands、safe/excluded manifest、execution queues、dependency waves 和 remediation checklist，非对应命令不得携带陈旧 profile。
- `validate_target_environment_evidence` 现在在 plan 通过结构校验后追加 `target_plan_evidence_alignment` 检查，读取 plan 中每个 evidence command 的 `output_file`，并把已归档 JSON 的 base URL、WebSocket discussion/阈值、Redis broker/result backend、backup dir、topology、runtime integration flags 和 P0/P1 capacity profile 与 plan metadata 对齐；P1 容量 evidence 还会对齐登录账号、discussion id、prepare/cleanup isolated target flags，避免旧账号或未隔离写入样本混进目标 run；若 evidence 文件存在但来自旧域名、旧 Redis、旧备份目录、错误 topology 或错误容量参数，会单独列出 `mismatched_command_keys` 并在 remediation planned commands 中指回需要重跑的计划命令。缺失、空 output 或 stderr 异常仍由 `target_archive_integrity` 负责。
- `validate_target_environment_evidence` 现在在 plan 通过结构校验后追加 `target_dependency_evidence` 检查，遍历每条计划命令的 `requires_completed_commands`，要求前置依赖命令的归档 evidence 自身也通过对应 action 校验，并在 action 通过后继续套用同一条命令的 plan/evidence alignment 校验；P0/P1 capacity 依赖不再只看 `summary.ok=true`，还会按目标 profile 校验 HTTPS base URL、profile、并发、持续时间、threshold failure、error count，以及和计划一致的登录账号/隔离目标参数；若 upgrade、backup verification、restore dry-run 或 P1/P2 前置命令失败，失败 action details 会列出 `failed_dependency_keys` 和 `blocked_command_keys`，remediation planned commands 会同时指向失败依赖和被阻塞命令，避免 post-upgrade、restore、live restore 或 P1 dependent command 在前置证据失败时被单独误采信。
- `inspect_target_topology --require-multi-node --format json` 已对本地 production-smoke 拓扑归档执行，按预期失败：本地只有 1 个 web 节点，且 image、PostgreSQL、Redis、LB 都是本地 smoke 值，不满足目标 multi-node/topology gate。
- `validate_target_environment_evidence --report-dir reports/capacity/20260702-025600 --p0-report-dir reports/capacity/20260702-011925 --p1-report-dir reports/capacity/20260702-020409 --plan-file reports/capacity/20260702-025600/target-environment-evidence-plan.json --write-remediation-checklist reports/capacity/20260702-025600/target-environment-remediation-checklist.md --require-multi-node --format json` 已对本地 production-smoke 报告归档执行，按预期失败：升级前和升级后 HTTP smoke 都不是 HTTPS，WebSocket 不是 WSS，queue worker 使用本地/container-only Redis 地址，备份、rollback plan artifact、restore rehearsal source 和 restore dry-run source 都指向容器本地 `/app/backups/...` 而非目标环境 durable backup location，缺少 live restore 执行证据，runtime integrations 未使用真实 SMTP connect、对象存储和 fail-on-warning，本地拓扑不满足 multi-node，且 image、PostgreSQL、Redis、LB 都是本地 smoke 值而非目标 release/shared services/HTTPS LB，P0/P1 容量报告也是本地 HTTP 而非目标环境 HTTPS，模板 target evidence plan 仍含占位符。失败 JSON 的 `remediation.actions` 已包含 16 个后续动作；传入 `--plan-file` 后，匹配动作还会带 `planned_commands`，暴露计划命令的 `command`、`output_file`、`stderr_file`、`archive_command`、`execution_group`、`safe_to_run_unattended`、`safe_archive_ready`、`requires_completed_commands`、`manual_approval_required`、`destructive` 和 substitution/target-value 状态，便于目标环境执行者区分无人值守、待前置证据、维护审批和 destructive 审批步骤；每个 remediation action 的具体 `errors` 也会写入 Markdown checklist，执行者不必回查 JSON 才能看到 HTTPS/WSS、依赖失败、归档缺失或 metadata mismatch 的原始失败原因；若失败来自 `target_archive_integrity`，action details 和 checklist 还会直接列出缺失/空 output、缺失/无效 stderr 或非空 stderr 对应的命令 key。`remediation.command_groups` 还会按 `execution_group` 聚合后续命令；当前模板归档为 1 条 `safe_unattended`、17 条 `requires_substitution`、1 条 `destructive_approval` 和 1 条 `final_validation`。`remediation.execution_sequence` 按推荐执行顺序渲染这些分组，并让 `final_validation` 保持最后一步。`remediation.execution_queues` 额外派生执行队列，`remediation.execution_queue_counts` 记录为：1 条 `safe_unattended`、18 条 `requires_substitution`、0 条 `target_value_required`、7 条 `dependency_blocked`、0 条 `maintenance_approval`、1 条 `destructive_approval` 和 1 条 `final_validation`，其中 destructive live restore 因含 `<durable-backup-uri>` 且依赖备份验证/restore dry-run，同时出现在 destructive、substitution 与 dependency-blocked 队列中，避免被误并入 safe-only 执行。`remediation.dependency_execution_waves` 为本地失败结果派生 4 个补救波次：第 1 波 `post_upgrade_http_smoke`、`post_upgrade_queue_worker`，第 2 波 `restore_rehearsal`、`p1_forum_write_mixed`，第 3 波 `restore_dry_run`、`p1_forum_moderation`，第 4 波 `live_restore`。`--write-remediation-checklist` 额外写出 `target-environment-remediation-checklist.md`，只渲染后续执行清单，不执行命令，也不代表 P2 已通过；该清单包含 guardrails、执行顺序、执行队列、依赖执行波次、每组 `execution_policy` 和每条计划命令的 command、output/stderr file、substitution tokens、target value errors 和 requires-completed commands，避免直接运行含 `<...>` 或前置依赖未完成的模板命令。
- 外部 WebSocket connect/subscribe/broadcast 20 连接 gate 通过。
- 真实目标环境验证已在本地开发阶段跳过；后续由目标环境执行者完成 HTTPS/WebSocket、SMTP、对象存储、多节点、目标容量和 destructive 回滚恢复演练归档后，才能把 P2 视为完整通过。

### P3：扩展开发者体验

目标：

第三方开发者不读 Bias 内部源码，也能创建、测试、打包、安装、升级扩展。

开发任务：

1. 完善 `docs/developer/extension-quickstart.md`。
2. 完善后端公开 API 文档。
3. 完善前端 `@bias/core/*` SDK 文档。
4. manifest 增加 schema version、core compatibility、dependency metadata。
5. 扩展安装前输出 plan：`inspect_extension_packages --format json` 的 `install_plan` 暴露依赖安装顺序、wheel 构建/选择、安装态 smoke 和 lifecycle smoke 步骤，且 `executes_install=false`。
6. 扩展升级前输出 breaking risk：`inspect_extension_packages --format json` 的 `upgrade_risk` 汇总 Bias 版本兼容、缺失依赖、依赖环、experimental/beta API 和 abandoned distribution 风险，并在 `summary.blocking_risk_count` 暴露阻断计数。
7. `inspect_extensions --format json` 输出兼容矩阵，覆盖 manifest schema、Bias/API 兼容、依赖/冲突/能力声明、分发状态和 release policy gate。
8. 扩展模板默认使用 service contract 示例。

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

当前结果：

- `create_extension` 默认模板已包含 manifest `schema_version=1`、compatibility/dependency metadata、runtime service provider、service contract、通过 `call_runtime_service(...)` 调用的 resource endpoint 示例，以及 `tool.pytest.ini_options.DJANGO_SETTINGS_MODULE="bias_core.extension_test_settings"` 共享测试配置。
- `validate_extensions --format json` 已输出并校验 manifest `schema_version`；旧 manifest 缺省按 schema 1 处理，低于 1 或高于当前支持版本的 schema 会被拒绝。
- `inspect_extension_packages --format json` 已输出 `install_plan`，在不安装真实站点的前提下给出扩展安装顺序、构建/审计/安装态 smoke/lifecycle smoke 计划，供 CI 和发布流水线提前审计。
- `inspect_extension_packages --format json` 已输出 `upgrade_risk`，覆盖缺失依赖、依赖环、Bias 版本不兼容、experimental/beta API 稳定性和 abandoned distribution 风险；`summary.risk_count` 与 `summary.blocking_risk_count` 可直接作为发布 gate 输入，`prepare_release` 会阻断扩展包升级阻断风险。
- `prepare_release` 的扩展包 gate 已执行 `inspect_extension_packages --build --install-smoke --install-set-smoke --migration-smoke --lifecycle-smoke --format json`，把 wheel 交付、安装态发现、整组依赖顺序、迁移 smoke、enable/disable 生命周期 smoke 和升级阻断风险纳入正式发布策略。
- `prepare_release --extension-report <path>` 已把 `package_audit` 写入扩展发布报告，归档 `install_plan`、`upgrade_risk`、install-set/migration/lifecycle smoke 结果和阻断风险计数，避免发布报告只有扩展诊断而缺少包审计证据。
- `inspect_extensions --format json` 已输出 `compatibility_matrix`，按扩展归档 manifest `schema_version`、Bias 版本范围和当前兼容结果、API 版本/稳定性、依赖/可选依赖/冲突/能力声明、分发签名/abandoned 状态和 release policy gate；顶层 `summary.compatibility_blocking_count`、`summary.bias_version_incompatible_count`、`summary.unstable_api_count` 和 `summary.abandoned_distribution_count` 可作为发布策略输入，`prepare_release` 会阻断兼容矩阵阻断项和 Bias 版本不兼容扩展。
- `inspect_extensions --contract-baseline-only` 与 `prepare_release --contract-baseline` 已形成契约基线发布策略，可阻断 public resource、runtime service、frontend route 等破坏性 contract 变化。
- `docs/developer/extension-quickstart.md` 已补充 `install_plan` 与 `upgrade_risk` 的发布前检查说明，并链接到后端/前端 SDK 参考。
- `docs/developer/extension-api.md` 已补齐公开后端 API 参考，覆盖推荐后端入口结构、runtime service contract、API resource endpoint、`FrontendExtender`、manifest/pyproject 和发布前 gate。
- `docs/developer/frontend-injection-points.md` 已补齐 `@bias/core`、`@bias/core/forum`、`@bias/core/admin`、`@bias/core/components/admin` 的入口边界、推荐模板、禁止导入和常用注入面。
- 本地 `.tmp-extension-dx` 验证已通过：`create_extension alpha-tools --force`、`validate_extensions --strict --format json`、`inspect_extension_imports --check-runtime-facades --format json`、`check_extension_workspace --skip-inspect-extensions --format json` 和 `inspect_extension_packages --build --install-smoke --install-set-smoke --lifecycle-smoke --format json` 均成功；包审计输出 `install_plan.executes_install=false`、安装顺序 `alpha-tools`、`install_set.lifecycle_states.alpha-tools.enabled=true`、`summary.blocking_risk_count=0`。完整 `check_extension_workspace` 的 foundation boundary gate 仍应在包含 content/users foundation 扩展的完整工作区运行，单扩展示例目录只验证静态门禁。

### P4：用户体验和产品完整性

进入条件：

```text
P0/P1 已通过，且目标环境 P2 gate 已通过
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

- P0、P1 和目标环境 P2 通过。
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

下一步进入 P2 目标环境演练，不再扩大功能范围。

开发顺序：

1. 在目标部署环境按 runbook 跑 `install_forum --dry-run --format json`、`backup_forum --format json`、`verify_forum_backup --format json`、`upgrade_forum --dry-run --format json`、`upgrade_forum --non-interactive --format json`、`plan_forum_rollback --require-existing-backups --format json`、`rehearse_forum_restore --format json` 和 `restore_forum_backup --dry-run --format json`。
2. 执行真实 HTTPS HTTP smoke、外部 WebSocket、queue worker、strict health 和 `smoke_runtime_integrations --smtp-connect --storage-write --require-smtp-connect --require-storage-write --require-object-storage --fail-on-warning --format json`。
3. 做一次回滚/恢复演练，并记录恢复耗时和验证命令。
4. 通过 `inspect_target_topology --require-multi-node --format json` 归档 `multi-node-topology.json`，并归档带有 site_config/database/media/static_frontend post-restore verification 的 `restore-forum-backup-live.json` 后运行 `validate_target_environment_evidence --report-dir reports/capacity/<target-run-id> --p0-report-dir reports/capacity/<target-p0-run-id> --p1-report-dir reports/capacity/<target-p1-run-id> --plan-file reports/capacity/<target-run-id>/target-environment-evidence-plan.json --write-remediation-checklist reports/capacity/<target-run-id>/target-environment-remediation-checklist.md --require-multi-node --format json`，要求 `summary.ok=true`。
5. 目标环境容量 suite 通过后，再进入 P3/P4 的开发者体验和产品完整性 gate。

当前不能做的结论：

```text
不能说已经足够给真实用户使用。
不能把 production-smoke 结果替代目标环境和回滚恢复演练。
不能绕过 P2 去做 marketplace、主题市场或复杂插件 UI。
```
