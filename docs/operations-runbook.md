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
curl -f http://127.0.0.1:8000/api/health?strict=1
```

清理：

```powershell
docker compose -f deploy/docker-compose.production-smoke.yml down -v
```

该 smoke 只证明 production-like 链路可启动、可初始化、HTTP 和 worker 可用；不替代真实公网 HTTPS、真实 SMTP、对象存储、多节点部署或 Work Package 4 的容量压测。

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

先输出升级计划：

```powershell
python manage.py upgrade_forum --config instance/site.json --dry-run --non-interactive
```

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
```

Redis/Celery 可用时追加：

```powershell
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6381/0 --result-backend redis://127.0.0.1:6381/0 --timeout 45 --format json
```

## 回滚流程

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
