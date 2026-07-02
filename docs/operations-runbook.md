# Bias 生产运维手册

本文档面向真实站点管理员，用于安装、升级、回滚和故障诊断。正式给用户使用前，至少按本文档跑通一次演练。

## 安装前准备

- 生产环境优先使用 PostgreSQL、Redis、Celery worker 和独立静态/媒体目录。
- SQLite 只用于本地开发或单机小规模试用。
- 管理员密码、`SECRET_KEY`、JWT signing key、数据库密码不能使用示例值。
- 邮件后端必须配置真实 SMTP 或事务邮件服务，否则注册、验证邮箱、重置密码不可用。

安装前先看计划：

```powershell
cd D:\files\project\tmp\bias
python manage.py install_forum --database postgres --config instance/site.json --non-interactive --dry-run --format json
```

CI 或部署流水线应读取 JSON 中的 `summary.error_count`、`summary.warning_count`、`production_config_findings` 和 `install_steps`。正式生产部署必须要求 `summary.error_count == 0`，否则不得继续执行安装或升级。

执行安装：

```powershell
python manage.py install_forum --database postgres --config instance/site.json --overwrite --non-interactive --publish-frontend-dist
```

安装后检查：

```powershell
python manage.py check
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
python manage.py inspect_performance_baseline --format json --strict
python manage.py smoke_http_p95 --base-url http://127.0.0.1:8000 --fail-on-threshold --format json
```

发布预检可以通过 `prepare_release` 汇总仓库内 gate；容量 smoke 需要显式启用：

```powershell
cd D:\files\project\tmp\bias
python manage.py prepare_release --set-version <version> --dry-run --allow-dirty --run-capacity-smoke --websocket-smoke-connections 20 --websocket-smoke-discussion-id 101 --websocket-smoke-p95-threshold-ms 1000
```

`--run-capacity-smoke` 会追加 `inspect_performance_baseline --format json --strict` 和 `smoke_websocket_realtime --format json`。它用于发布 gate 的轻量准入，不会替代 `load_test_http --duration 300` 这类真实目标环境压测。

启动服务后检查健康探针：

```powershell
curl http://127.0.0.1:8000/api/health
```

返回中的 `checks.app/db/http/cache/queue/realtime/storage` 应按当前部署形态分别为 `available`、`disabled` 或明确的错误状态。`checks.http.metrics` 包含请求数、状态码桶和耗时指标；`checks.storage.metrics` 包含上传/删除计数、失败率、耗时和字节数。

部署 gate 使用严格健康检查：

```powershell
curl -f http://127.0.0.1:8000/api/health?strict=1
```

默认 `/api/health` 为开发和诊断保持 200，并在 payload 中展示降级项。`strict=1` 或环境变量 `BIAS_HEALTH_STRICT=1` 会在整体状态不是 `ok` 时返回 503，负载均衡、容器 healthcheck 或发布流水线应使用严格模式。

## Production smoke 演练

本地 production-like 演练使用 `deploy/docker-compose.production-smoke.yml`，覆盖 PostgreSQL、Redis、一次性初始化、web、worker、scheduler、static/media/instance volumes。

production smoke 默认设置 `DB_CONN_MAX_AGE=0`、`DB_CONN_HEALTH_CHECKS=1`。这是为了在 ASGI/Gunicorn 并发压测时避免 Django sync 线程持有大量 PostgreSQL 长连接，导致 `FATAL: sorry, too many clients already`。正式生产如果要把 `DB_CONN_MAX_AGE` 调大，必须同时按 `WEB_CONCURRENCY`、ASGI 线程池、worker/scheduler 数量和 PostgreSQL `max_connections` 做连接预算；未完成预算前不要把长连接结果作为容量通过证据。

演练前可复制环境模板：

```powershell
cd D:\files\project\tmp\bias
Copy-Item .env.production-smoke.example .env.production-smoke
```

启动并验证：

```powershell
docker compose -f deploy/docker-compose.production-smoke.yml config
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build
docker compose -f deploy/docker-compose.production-smoke.yml ps
python manage.py smoke_http_p95 --base-url http://127.0.0.1:8000 --requests 3 --warmup 1 --format json
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6379/1 --result-backend redis://127.0.0.1:6379/2 --timeout 45 --format json
python manage.py smoke_runtime_integrations --storage-write --format json
curl -f http://127.0.0.1:8000/api/health?strict=1
```

清理：

```powershell
docker compose -f deploy/docker-compose.production-smoke.yml down -v
```

`smoke_runtime_integrations` 默认只做 SMTP 配置 dry-run；传入 `--smtp-connect` 才会实际连接 SMTP。`--storage-write` 会通过当前 storage backend 写入临时对象并删除。production-smoke 默认 local storage 只能证明本地 media volume 可写删，不替代对象存储 provider 验证。

该 smoke 只证明 production-like 链路可启动、可初始化、HTTP、worker 和本地 storage 可用；不替代真实公网 HTTPS、真实 SMTP、对象存储、多节点部署或 Work Package 4 的容量压测。

## 容量压测

生产发布前至少准备一轮接近目标规模的数据：

```powershell
cd D:\files\project\tmp\bias
python manage.py seed_load_test_data --users 1000 --discussions 10000 --posts 100000 --tags 200 --notifications 50000 --format json
```

该命令通过 Django app registry 发现 `content`、`users`、`tags`、`notifications` 模型；`tags` 或 `notifications` 未安装时会在 JSON 中标记为 skipped，foundation 模型缺失时直接失败。命令按 `prefix` 幂等补齐数据，重复执行不会重复创建已满足目标数量的数据。

容量压测前先确认数据库连接策略。若使用 ASGI + sync Django ORM，`DB_CONN_MAX_AGE=60` 这类长连接会被多个 worker 和线程长期占用；当 PostgreSQL 默认 `max_connections=100` 时，300 秒并发读写压测可能先失败在连接耗尽，而不是业务路径性能。production smoke 的正式容量报告应保留 `DB_CONN_MAX_AGE=0`，除非报告中同时记录连接预算、PostgreSQL `max_connections` 和压测期间 `pg_stat_activity` 峰值。

PostgreSQL 全文搜索压测前先确认搜索索引状态：

```powershell
python manage.py shell -c "from bias_core.search_index_service import SearchIndexService; print(SearchIndexService.get_status())"
python manage.py shell -c "from bias_core.search_index_service import SearchIndexService; print(SearchIndexService.rebuild_postgres_indexes())"
```

`forum-main` 默认搜索目标使用选择性 seed 词 `loadtest-discussion-00000001`，用于验证普通搜索路径。`loadtest` 会命中几乎全部 seed discussion/post，属于热门词压力项，不能和普通搜索阈值混在同一个通过 gate；需要单独压测时使用自定义 path，例如：`--path "GET /api/search?q=loadtest=3000"`，并在报告中标明这是 hot-term stress。

HTTP 并发压测：

```powershell
python manage.py load_test_http --base-url https://<your-domain> --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
python manage.py load_test_http --base-url https://<your-domain> --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json
python manage.py load_test_http --base-url https://<your-domain> --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url https://<your-domain> --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url https://<your-domain> --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json
```

报告包含每个 target 的 method/path、是否覆盖、是否 JSON/multipart、`p50_ms`、`p95_ms`、`p99_ms`、`error_rate`、状态码分布、失败样本，以及总吞吐 `requests_per_second`。`forum-main` 只覆盖公开匿名读路径；`forum-main-auth` 覆盖 `/api/users/me`、我的讨论、未读讨论和通知列表；`forum-write` 会向 `/api/discussions/{discussion_id}/posts` 发起登录态回复写入；`forum-write-mixed` 覆盖新建讨论、编辑讨论、标记已读、点赞/取消点赞、订阅/取消订阅；`forum-upload` 覆盖 `POST /api/uploads` multipart 附件上传；`forum-write-moderation` 覆盖帖子编辑、举报、通知已读、隐藏/恢复、通知清理和删除。登录态、写入和上传 profile 推荐使用 `--login-username/--login-password` 自动获取 `/api/csrf`、JWT Bearer token 和 session cookie；`--auth-token` 只能提供 Bearer token，若站点启用 CSRF 写保护，还必须额外提供有效 CSRF cookie/header。placeholder token 只能验证失败报告格式，不能作为容量通过证据。`forum-write-mixed` 和 `forum-write-moderation` 属于有状态写 profile，默认应使用 `--prepare-isolated-targets --cleanup-isolated-targets` 自动创建并清理隔离目标；只有确认目标属于 seed/load-test 数据时，才手工传 `--discussion-id`、`--post-id`、`--tag-id`、`--notification-id`。自定义 `--path` 支持 `GET /api/forum=300`、`POST /api/discussions/{discussion_id}/posts {"content":"Load {sequence}"}=500` 或 `POST /api/uploads FILE file:guide.txt:text/plain:hello=800`。JSON 报告在创建隔离目标时会输出 `isolated_targets.prefix`；如遇中断或历史遗留，可使用下列命令按安全前缀清理：

```powershell
python manage.py load_test_http --base-url https://<your-domain> --cleanup-isolated-prefix loadtest-isolated-<sequence> --requests 0 --duration 0 --format json
```

建议发布阈值：

```text
讨论列表 P95 < 300ms
讨论详情 P95 < 500ms
通知列表 P95 < 300ms
搜索 P95 < 800ms
普通发帖 P95 < 500ms，不含异步通知
HTTP error rate < 0.5%
```

WebSocket 实时链路 smoke：

```powershell
python manage.py smoke_websocket_realtime --connections 20 --discussion-id 101 --p95-threshold-ms 1000 --format json
```

当前 WebSocket smoke 使用 in-process Channels 和已注册的 `realtime.forum` route，优先验证当前已启用扩展；如果当前站点尚未完成扩展安装态 bootstrap，会 fallback 到 workspace 中的 realtime 测试 host，并在 JSON 中标记 `workspace_fallback=true`。它验证 connect、subscribe discussions、discussion group broadcast 和客户端接收 `forum_event` 的链路，报告 connect/subscribe/broadcast 的 P50/P95/P99。它用于快速定位应用内 realtime route 和 consumer 问题，不替代真实公网 WebSocket、反向代理、TLS 和跨节点 Redis channel layer 压测。

目标部署环境追加外部 WebSocket 压测：

```powershell
python manage.py load_test_websocket --base-url https://<your-domain> --connections 20 --discussion-id 101 --auth-token <access-token> --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json
```

`load_test_websocket` 会把 `https://` 转换为 `wss://`，连接 `/ws/forum/`，发送 `subscribe_discussions`，然后通过当前 Django 进程配置的 channel layer 向 `discussion_<id>` 广播 `forum_event`。因此该命令应在和目标 web/worker 使用同一 Redis channel layer 配置的环境执行；通过时可证明外部 WebSocket 握手、代理/TLS、订阅协议和跨进程 channel layer 广播同时可用。只想验证外部握手和订阅时可加 `--skip-channel-broadcast`。

## 升级流程

升级前必须备份：

- `instance/site.json`
- PostgreSQL 数据库，或 SQLite 数据库文件
- `media/`
- 已发布的 `static/frontend/`

先创建机器可读备份：

```powershell
python manage.py backup_forum --config instance/site.json --backup-dir backups/<release-or-timestamp> --format json
```

发布流水线应读取 JSON 中的 `summary.ok`、`summary.error_count`、`summary.artifact_count`、`summary.missing_required_artifact_count` 和 `backup_artifacts`。升级前必须要求 `summary.ok == true` 且 `summary.missing_required_artifact_count == 0`。

目标环境 P2 证据的 `--backup-dir` 必须指向 durable backup location，例如对象存储 URI、备份服务挂载点或可跨节点/跨容器生命周期保留的卷；不要使用容器内 `/app/backups/...`、`/tmp/...`、本地 workspace 或相对 `backups/...` 作为最终 P2 证据。`validate_target_environment_evidence` 会拒绝这些本地/临时路径。

再验证备份产物可读：

```powershell
python manage.py verify_forum_backup --config instance/site.json --backup-dir backups/<release-or-timestamp> --format json
```

发布流水线应读取 JSON 中的 `summary.ok`、`summary.error_count` 和 `checks`。PostgreSQL 备份会通过 `pg_restore --list` 验证 dump 格式，SQLite 备份会以只读方式打开数据库文件，目录备份会统计文件数量和字节数。升级前必须要求 `summary.ok == true`。

先输出升级计划：

```powershell
python manage.py upgrade_forum --config instance/site.json --dry-run --non-interactive --format json
```

CI 或部署流水线应读取 JSON 中的 `summary.ok`、`summary.error_count`、`summary.warning_count`、`summary.dry_run`、`summary.executed` 和 `upgrade_steps`。正式升级预检必须要求 `summary.ok == true`、`summary.error_count == 0`、`summary.dry_run == true` 且 `summary.executed == false`。

执行升级：

```powershell
python manage.py upgrade_forum --config instance/site.json --non-interactive --publish-frontend-dist
```

升级后执行：

```powershell
python manage.py check
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
python manage.py inspect_performance_baseline --format json --strict
python manage.py smoke_install_upgrade --from-wheels --publish-frontend-dist --database postgres --db-host <postgres-host> --db-port 5432 --db-name <db> --db-user <user> --db-password <password> --redis on --redis-host <redis-host> --redis-port 6379 --redis-db 0 --format json
python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json
python manage.py smoke_runtime_integrations --smtp-connect --storage-write --require-smtp-connect --require-storage-write --require-object-storage --fail-on-warning --format json
python manage.py inspect_target_topology --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database <db-endpoint> --redis <redis-endpoint> --load-balancer https://<your-domain> --require-multi-node --format json
```

目标环境执行前可先生成完整 evidence run plan：

```powershell
python manage.py plan_target_environment_evidence --base-url https://<your-domain> --report-dir reports/capacity/<target-run-id> --p0-report-dir reports/capacity/<target-p0-run-id> --p1-report-dir reports/capacity/<target-p1-run-id> --backup-dir s3://<backup-bucket>/<release-or-timestamp> --discussion-id <discussion-id> --load-username <load-user> --load-password <load-password> --moderator-username <moderator-user> --moderator-password <moderator-password> --redis-broker-url redis://<redis-host>:6379/1 --redis-result-backend redis://<redis-host>:6379/2 --web-nodes <web-count> --worker-nodes <worker-count> --scheduler-nodes <scheduler-count> --image <image-or-release> --app-version <version> --database-endpoint <db-endpoint> --redis-endpoint <redis-endpoint> --write-plan-file reports/capacity/<target-run-id>/target-environment-evidence-plan.json --format json
```

如需直接生成安全批量脚本，追加：

```powershell
--write-safe-script reports/capacity/<target-run-id>/target-environment-safe-archive.ps1
--write-safe-shell-script reports/capacity/<target-run-id>/target-environment-safe-archive.sh
```

该计划只输出固定文件名、推荐命令、`archive_command`、`safe_to_run_unattended`、`safe_archive_ready`、`requires_completed_commands`、`execution_group`、`requires_substitution`、`substitution_tokens`、`target_value_errors`、destructive 标记和人工审批标记，不会执行任何命令；`summary.executes_commands` 必须为 `false`。`safe_to_run_unattended=true` 只表示命令本身无需审批、无需替换且目标值合格；只有同时满足 `safe_archive_ready=true` 且没有 `requires_completed_commands` 的命令才会进入顶层 `safe_archive_commands` 和 `safe_archive_manifest`。部署系统可以直接读取 `safe_archive_commands` 执行初始无人值守批量归档，读取 `excluded_from_safe_archive` 审计每条被排除命令的 `exclude_reasons`、`safe_archive_ready` 和 `requires_completed_commands`，读取顶层 `command_groups` 按 `execution_group` 获得 command keys、原始 commands、output/stderr files、archive commands、审批状态、destructive 状态、substitution 状态、target-value 状态和依赖阻断状态，或读取顶层 `execution_queues` 直接获得 safe unattended、requires substitution、target-value required、dependency blocked、maintenance approval、destructive approval 和 final validation 队列；每个队列都保留完整 command/output/stderr/archive 元数据，`summary.execution_queue_counts` 提供同一组队列计数，用于目标环境执行前分流和审计。顶层 `dependency_execution_waves` 会按 `requires_completed_commands` 派生可执行波次，每个波次包含 `wave`、`dependency_depth`、`command_count`、`command_keys`、聚合后的 `requires_completed_commands` 和完整 `commands` 元数据；`summary.dependency_execution_wave_count` 必须与该列表一致。

顶层 `execution_sequence` 会给出推荐顺序：safe unattended、requires substitution、target-value required、maintenance approval、destructive approval、final validation；每一步包含 command keys、计数、policy 和状态标记，`final_validation` 必须最后运行。`dependency_execution_waves` 只排序已有前置依赖的命令，用于在前置证据归档后分批放行 dependency-blocked 队列；它不替代 substitution、target-value、maintenance、destructive 或 final validation gate。也可以使用 `--write-safe-script` / `--write-safe-shell-script` 分别生成只包含 `safe_archive_ready=true` 命令的 PowerShell/POSIX shell 脚本；这些脚本不包含 `<...>` 待替换 token、本地/临时目标值、前置依赖未完成、manual approval、final validation 或 destructive live restore 命令。PowerShell 脚本会在命令重定向前用 `New-Item -ItemType Directory -Force` 创建 safe 输出目录，并在每条归档命令前重置 `$LASTEXITCODE`、执行后同时检查 `$?` 和 `$LASTEXITCODE`；POSIX shell 脚本使用 `mkdir -p` 和 `set -eu`，并对输出和 stderr 重定向路径做 shell 引号包裹；每条归档命令执行后都会立即检查对应 `output_file` 已生成且非空、`stderr_file` 已生成且为空，缺失、空 output 或非空 stderr 都会让脚本失败。最终 `target_archive_integrity` gate 会进一步确认 plan 中每个非 final validation 命令的 `output_file` 已归档，且 `stderr_file` 已归档并为空。顶层 `manual_approval_commands`、`final_validation_commands`、`substitution_required_commands`、`target_value_required_commands` 和 `dependency_blocked_commands` 都会保留 `requires_substitution`、`substitution_tokens`、`target_value_errors`、`safe_archive_ready` 和 `requires_completed_commands`，审批系统必须先检查这些字段。

尽量在生成计划时传入真实 `--base-url`、`--discussion-id`、压测账号、Redis broker/result backend、durable backup dir、web/worker/scheduler 节点数、image/release、app version、数据库端点和 Redis 端点；传齐后 queue worker、外部 WebSocket、P1 容量、backup、topology 等无前置依赖命令可进入 `safe_archive_commands`。post-upgrade smoke、restore rehearsal、restore dry-run、P1 mixed write 和 P1 moderation 这类有顺序要求的命令即使命令本身安全，也会因为 `requires_completed_commands` 留在 `excluded_from_safe_archive`，必须等前置证据归档后再执行。仍含占位符的命令会归入顶层 `substitution_required_commands`、顶层 `execution_queues.requires_substitution` 和 `execution_group=requires_substitution`，必须先替换为目标环境真实值后再人工执行或纳入部署系统。已填值但不是合格目标值的命令会归入顶层 `target_value_required_commands`、顶层 `execution_queues.target_value_required` 和 `execution_group=target_value_required`，例如相对 `backups/...`、本地 Redis/PostgreSQL、`local-production-smoke`、`latest` 或非 HTTPS LB；这些命令也不会写入 safe-only 脚本。实际 `upgrade_forum --non-interactive` 会归入 `execution_group=maintenance_approval` 和顶层 `execution_queues.maintenance_approval`；`restore-forum-backup-live.json` 会归入 `execution_group=destructive_approval`、顶层 `execution_queues.destructive_approval` 且 `destructive=true`；这两项会出现在顶层 `manual_approval_commands` 中，不会写入 safe-only 脚本，必须只在维护窗口和人工确认后复制执行。最终 `validate_target_environment_evidence` 会归入顶层 `final_validation_commands` 和顶层 `execution_queues.final_validation`，自动带上 `--plan-file <target-run-id>/target-environment-evidence-plan.json` 和 `--write-remediation-checklist <target-run-id>/target-environment-remediation-checklist.md`，也不会写入 safe-only 脚本；只有人工审批命令、替换后命令、target-value-required 命令和 dependency-blocked 命令归档完成后才运行它。

目标环境报告目录归档所有 JSON 后，执行最终证据校验：

```powershell
python manage.py validate_target_environment_evidence --report-dir reports/capacity/<target-run-id> --p0-report-dir reports/capacity/<target-p0-run-id> --p1-report-dir reports/capacity/<target-p1-run-id> --plan-file reports/capacity/<target-run-id>/target-environment-evidence-plan.json --write-remediation-checklist reports/capacity/<target-run-id>/target-environment-remediation-checklist.md --require-multi-node --format json
```

该 gate 会拒绝把本地 production-smoke 当成目标环境证据：HTTP smoke 和 P0/P1 容量 suite 必须使用 `https://`，WebSocket 必须使用 `wss://`，queue worker 不能指向本地/container-only Redis，backup、backup verification、rollback plan、restore rehearsal、restore dry-run 和 live restore 必须引用 durable backup location，runtime integrations 必须实际 SMTP connect、storage write/delete、非 local object storage 且 `--fail-on-warning`，必须存在 destructive live restore 执行证据 `restore-forum-backup-live.json`，且该证据必须包含 post-restore `verification`：`site_config` 通过 `read_site_config`，`database` 通过 live SQLite/PostgreSQL 读取并记录 `table_count >= 1`，`media` 和 `static_frontend` 通过目录扫描。传入 `--plan-file` 时还会校验目标 evidence plan 的 `report_dir`/P0/P1 目录与当前 gate 参数一致，`summary.executes_commands=false`，`commands.key`、`safe_archive_manifest.key`、`excluded_from_safe_archive.key`、`commands.output_file` 和 `commands.stderr_file` 不能重复，`safe_archive_manifest` 与 `safe_archive_commands` 一致，`excluded_from_safe_archive` 覆盖所有 `safe_archive_ready=false` 命令，`manual_approval_commands`、`final_validation_commands`、`substitution_required_commands`、`target_value_required_commands` 和 `dependency_blocked_commands` 与每条 command 派生结果一致，相关 summary 计数与这些顶层列表一致，`command_groups` 与每条 command 的 execution group、输出文件、归档命令、`safe_archive_ready`、`requires_completed_commands` 和状态标记一致，`execution_sequence` 覆盖所有 command groups、step 连续且 `final_validation` 最后，`execution_queues` 与每条 command 派生出的执行队列完全一致，`summary.execution_queue_counts` 与 `execution_queues` 一致，`dependency_execution_waves` 与 `requires_completed_commands` 派生结果一致，`summary.dependency_execution_wave_count` 与波次数一致，最终校验命令带有同一报告目录的 `--write-remediation-checklist`，并且最终计划中不再残留 `<...>` substitution token、`target_value_errors`、`plan_file_path`、`safe_script_path` 或 `safe_shell_script_path` 这类只应出现在控制台输出中的运行时字段；`requires_completed_commands` 还必须引用同一计划中的命令 key，不能自引用，不能形成环路。计划一致性通过后，`target_archive_integrity` 会检查 plan 中每个非 final validation 证据命令的 `output_file` 已归档，且 `stderr_file` 已归档并为空；任何缺失 output 或 stderr 输出都必须先解释并修正后再作为 P2 证据提交。不要把模板 plan 当成最终目标环境 plan。

失败输出的 `remediation.actions` 会列出阻塞项；传入 `--plan-file` 时，匹配的 action 还会带 `planned_commands`，其中包含对应计划命令的 `command`、`output_file`、`stderr_file`、`archive_command`、`execution_group`、`safe_to_run_unattended`、`safe_archive_ready`、`requires_completed_commands`、`manual_approval_required`、`destructive` 和 substitution/target-value 状态，用于后续执行清单和审批分流。`target_archive_integrity` 失败时，action details 和 Markdown checklist 会明确列出 `missing_output_keys`、`missing_stderr_keys` 与 `non_empty_stderr_keys`，用于直接定位需要补归档或重跑的计划命令。`remediation.command_groups` 会再按 `execution_group` 汇总这些计划命令，输出每组 command/action keys、commands、output/stderr files、archive commands、是否需要人工审批、是否 destructive、是否仍需 substitution、target value 修正或前置证据完成；`remediation.execution_sequence` 会按推荐顺序串起这些分组，并要求 `final_validation` 保持最后一步；`remediation.execution_queues` 会另外派生 safe unattended、requires substitution、target-value required、dependency blocked、maintenance approval、destructive approval 和 final validation 队列，保留每条命令的完整 command/output/stderr/archive 元数据，`remediation.execution_queue_counts` 提供同一组队列计数，部署系统可以据此拆分无人值守、待替换、待修正目标值、待前置证据、维护审批、destructive 审批和最终校验队列。多个失败 action 指向同一 planned command 时，remediation 的 command groups、execution queues 和 dependency waves 会去重，避免同一命令在执行清单中重复出现。`remediation.dependency_execution_waves` 只对仍需补证且有前置依赖的 planned commands 建波次，`remediation.dependency_execution_wave_count` 给出波次数，Markdown checklist 会渲染同一组 “Dependency Execution Waves”。传入 `--write-remediation-checklist` 时，失败和成功场景都会写出 Markdown checklist；它只渲染 remediation 信息，不执行任何命令，并包含 guardrails、执行顺序、执行队列、依赖执行波次、每组 `execution_policy`、每条计划命令的 command、output/stderr file、substitution tokens、target value errors 和 requires-completed commands，避免把 checklist 当成 P2 通过证据或直接运行含 `<...>` 的模板命令。还必须归档 `multi-node-topology.json` 证明 web、worker、scheduler 目标拓扑、非本地 release image/version、共享数据库/Redis 和 HTTPS 负载均衡入口。只有该命令 `summary.ok == true` 时，P2 目标环境证据才算完整。

`multi-node-topology.json` 应由 `inspect_target_topology` 生成。目标环境至少要记录 web、worker、scheduler 节点数，共用的 image/release、数据库、Redis/channel layer 和公网负载均衡入口；传入 `--require-multi-node` 时 web 节点数必须至少为 2。`inspect_target_topology` 和最终校验都会拒绝 `local-production-smoke`、`latest`、`<...>` 占位符、本地/container-only PostgreSQL/Redis 主机，以及非 HTTPS 的负载均衡入口。

Redis/Celery 可用时追加：

```powershell
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6381/0 --result-backend redis://127.0.0.1:6381/0 --timeout 45 --format json
```

## 回滚流程

回滚前先生成机器可读计划，并确认备份产物齐全：

```powershell
python manage.py plan_forum_rollback --config instance/site.json --backup-dir backups/<release-or-timestamp> --require-existing-backups --format json
```

发布流水线应读取 JSON 中的 `summary.ok`、`summary.error_count`、`summary.missing_required_artifact_count`、`summary.executes_restore`、`backup_artifacts`、`restore_steps` 和 `verification_steps`。正式回滚演练必须要求 `summary.ok == true` 且 `summary.executes_restore == false`，然后由人工或部署系统按计划执行恢复步骤。

正式执行 destructive 回滚前，先做一次隔离恢复演练：

```powershell
python manage.py rehearse_forum_restore --config instance/site.json --backup-dir backups/<release-or-timestamp> --format json
```

发布流水线应读取 JSON 中的 `summary.ok`、`summary.error_count`、`summary.warning_count`、`summary.executes_live_restore`、`summary.uses_isolated_restore_targets`、`summary.dropped_temp_database`、`restore_steps` 和 `verification`。PostgreSQL 演练会创建临时数据库、把 dump 恢复进去、查询 public schema 表数量，并在默认情况下删除临时库；SQLite 演练会把数据库备份复制到临时目录并只读打开；media/static 目录会复制到临时目录。隔离恢复演练必须要求 `summary.ok == true`、`summary.executes_live_restore == false` 且 `summary.uses_isolated_restore_targets == true`。它不覆盖当前运行数据，也不替代目标环境的真实 destructive 回滚演练。

维护窗口内执行真实恢复前，先输出 destructive restore dry-run：

```powershell
python manage.py restore_forum_backup --config instance/site.json --backup-dir backups/<release-or-timestamp> --dry-run --format json
```

发布流水线应读取 JSON 中的 `summary.ok`、`summary.dry_run`、`summary.executes_live_restore`、`summary.destructive`、`backup_artifacts` 和 `restore_steps`。dry-run 必须满足 `summary.ok == true`、`summary.dry_run == true`、`summary.executes_live_restore == false` 且全部 planned step 指向预期备份目录和 live 目标。

确认停机、备份产物正确、维护窗口和值守人员到位后，才执行 live 恢复：

```powershell
python manage.py restore_forum_backup --config instance/site.json --backup-dir backups/<release-or-timestamp> --i-understand-this-overwrites-live-data --confirm-phrase "restore live forum data" --format json
```

非 dry-run 必须同时传入 `--i-understand-this-overwrites-live-data` 和确认短语，否则命令拒绝执行。live 恢复会覆盖当前数据库、`media/`、`static/frontend/` 和 `instance/site.json`，除非显式使用 `--skip-database`、`--skip-media`、`--skip-static-frontend` 或 `--skip-site-config`。恢复后必须要求 JSON 中 `summary.ok == true`、`summary.executes_live_restore == true`，并检查 `verification` 包含 `site_config`、`database`、`media`、`static_frontend` 四类 post-restore 证据且全部 `ok == true`；数据库证据必须证明 live database 可读并记录 `table_count >= 1`。随后立即执行后续健康检查和容量 smoke。

优先采用“恢复备份 + 重新启动服务”的回滚方式：

1. 停止 web、worker、scheduler。
2. 恢复数据库备份。
3. 恢复 `media/` 和 `static/frontend/`。
4. 恢复 `instance/site.json`。
5. 启动 web、worker、scheduler。
6. 执行 `python manage.py check` 和主流程冒烟。

不要在没有备份的情况下依赖扩展 uninstall 自动回滚业务数据。扩展卸载只负责运行生命周期 hook 和已声明的迁移摘要，真实业务数据默认保留，避免误删用户内容。

## 扩展数据保留策略

- disable：只停用扩展运行时能力，默认保留数据库表、设置、媒体文件和审计记录。
- uninstall：移除安装态和可回滚迁移摘要；默认仍保留业务数据，除非扩展明确声明并实现数据清理 hook。
- protected/foundation 扩展不能 disable/uninstall，例如 `content`、`users` 等基础域。
- 有依赖关系的扩展必须通过后台计划或 `include_dependents` 级联处理，不能强行跳过依赖检查。

## 故障诊断

常用命令：

```powershell
python manage.py doctor
python manage.py inspect_extensions --format json
python manage.py migrate_extensions --all --dry-run --format json
python manage.py verify_forum_backup --config instance/site.json --backup-dir backups/latest --format json
python manage.py plan_forum_rollback --config instance/site.json --backup-dir backups/latest --format json
python manage.py inspect_performance_baseline --format json --strict
python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json
```

HTTP 健康探针：

```powershell
curl http://127.0.0.1:8000/api/health
curl -f http://127.0.0.1:8000/api/health?strict=1
```

后台仪表盘会展示 cache、queue、realtime、HTTP、storage、runtime risks 和扩展诊断。若扩展前端加载失败，前台/后台会出现可关闭的运行时降级提示；优先重建并发布前端资源：

```powershell
python manage.py build_extension_frontend --rebuild --publish
python manage.py collectstatic --noinput
```
