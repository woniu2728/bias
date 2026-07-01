# Bias 面向真实用户上线落地文档

日期：2026-07-01

本文档用于判断当前 Bias 是否可以给真实用户使用，以及上线前后按什么顺序执行。

## 当前结论

当前代码尚未达到“小规模真实用户试运行”的容量准入。工程边界、扩展拆包和本地 smoke 已经完成较多工作，但最新正式容量报告 `reports/capacity/20260701-211043` 中 `forum-main` 300 秒压测仍未通过 P95 阈值，因此不能作为给真实用户开放的 release evidence。

已经具备的工程基础：

- `bias_core` 已作为独立后端核心包使用，官方扩展通过 entry point、manifest、runtime service contract 和公开 SDK 接入。
- `bias-content` 与 `bias-ext-users` 是 foundation/system 包，Discussion/Post/User 基础域不再由普通可选扩展拥有。
- 官方扩展生产代码的 import 边界检查通过，未发现 `bias_core -> bias_ext_*` 或扩展直接引用 core 内部实现的问题。
- runtime facade dependency graph 无循环，扩展间依赖可被 CI 检查。
- 前端 SDK 已通过 `@bias/core/*` 公开入口和 boundary gate 固化。
- 安装、升级、wheel 安装态、frontend dist 发布、浏览器主流程已有本地发布 gate 证据。

当前阻塞项：

- `GET /api/forum` P95 约 882.276ms，阈值 300ms。
- `GET /api/discussions/?limit=20` P95 约 1201.599ms，阈值 300ms。
- `GET /api/search?q=loadtest-discussion-00000001` P95 约 1123.727ms，阈值 800ms。
- `GET /api/tags` P95 约 1207.394ms，阈值 300ms。

下一步必须先按 [anonymous-read-performance-development.md](anonymous-read-performance-development.md) 优化匿名读路径，并拿到通过的 `forum-main --concurrency 20 --duration 300 --fail-on-threshold` 正式报告。之后才继续登录态、写入、上传、moderation 和外部 WebSocket 容量 suite。

## 本次已验证

已通过：

```powershell
cd D:\files\project\tmp\bias
python manage.py check
python manage.py validate_extensions --extensions-path D:\files\project\tmp --strict --format json
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --check-runtime-facades --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
python manage.py inspect_performance_baseline --format json --strict
python manage.py smoke_http_p95 --base-url http://127.0.0.1:8080 --requests 3 --warmup 1 --format json
python manage.py smoke_install_upgrade --from-wheels --publish-frontend-dist --format json
python manage.py smoke_install_upgrade --from-wheels --publish-frontend-dist --database postgres --db-host 127.0.0.1 --db-port 55432 --db-name bias_smoke --db-user bias --db-password bias --redis on --redis-host 127.0.0.1 --redis-port 6382 --redis-db 0 --format json
python manage.py smoke_queue_worker --broker-url redis://127.0.0.1:6381/0 --result-backend redis://127.0.0.1:6381/0 --timeout 45 --format json

cd D:\files\project\tmp\bias_core
python -m pytest -q --tb=short

cd D:\files\project\tmp\bias-content
python -m pytest -q --tb=short

cd D:\files\project\tmp\bias-ext-discussions
python -m pytest bias_ext_discussions/backend/tests.py -q --tb=short

cd D:\files\project\tmp\bias-ext-tags
python -m pytest bias_ext_tags/backend/tests.py -q --tb=short

cd D:\files\project\tmp\bias-ext-uploads
python -m pytest bias_ext_uploads/backend/tests.py -q --tb=short

cd D:\files\project\tmp\bias-ext-security
python -m pytest -q --tb=short

cd D:\files\project\tmp\bias\frontend
npm run check:platform
npm run test:node
npm run build
npm run test:e2e
```

Redis/Celery worker smoke 已使用临时 Redis 容器补跑通过，结果要求为 `summary.ok=true`、`worker_status.available=true`、`task_result.ok=true`。

PostgreSQL + Redis 安装升级 smoke 已使用临时 Docker 服务补跑通过，结果要求为 `summary.ok=true`、安装/升级阶段均保留 17 个官方启用扩展，且 `advanced.queue_enabled=true`、`advanced.queue_driver="redis"`。

扩展包审计已覆盖 23 个 manifest：所有 wheel 可构建，单包安装态可发现 manifest 和导入后端入口，整组安装态 boot order 无缺失依赖/循环，生命周期 smoke 对普通扩展验证 disable/enable，对 protected foundation 扩展验证安装、启用和 boot 状态。

`smoke_http_p95` 已作为发布前轻量 P95 smoke 入口加入，但正式容量结论仍必须在生产等价数据量和并发模型下补跑。

## 上线前必须补跑

在生产等价环境执行：

```powershell
python manage.py install_forum --database postgres --config instance/site.json --non-interactive --dry-run
python manage.py smoke_install_upgrade --from-wheels --publish-frontend-dist --database postgres --db-host <postgres-host> --db-port 5432 --db-name <db> --db-user <user> --db-password <password> --redis on --redis-host <redis-host> --redis-port 6379 --redis-db 0 --format json
python manage.py smoke_queue_worker --broker-url redis://<redis-host>:6379/0 --result-backend redis://<redis-host>:6379/0 --timeout 45 --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
python manage.py inspect_performance_baseline --format json --strict
python manage.py smoke_http_p95 --base-url https://<your-domain> --fail-on-threshold --format json
```

压测至少覆盖：

- `/api/forum`
- `/api/discussions`
- `/api/discussions/{id}`
- `/api/discussions/{id}/posts`
- `/api/search`
- `/api/tags`
- `/api/notifications`
- `/api/uploads`
- WebSocket connect/subscribe/broadcast
- 后台 approval/flags queue

建议准入线：

- 讨论列表 P95 小于 300ms。
- 讨论详情 P95 小于 500ms。
- 通知列表 P95 小于 300ms。
- 搜索 P95 小于 800ms。
- 普通发帖 P95 小于 500ms，不含异步通知。
- WebSocket 广播延迟 P95 小于 1s。

## 上线步骤

1. 冻结 release commit，构建并保存所有 wheel 和前端 dist。
2. 备份数据库、`instance/site.json`、`media/`、当前 `static/frontend/`。
3. 执行 `upgrade_forum --dry-run`，确认迁移和扩展计划。
4. 执行 `upgrade_forum --non-interactive --publish-frontend-dist`。
5. 执行 `migrate_extensions --all --format json`，确认扩展迁移状态。
6. 执行 `collectstatic --noinput`。
7. 启动 web、worker、scheduler、WebSocket 服务。
8. 检查 `/api/health`、后台 stats/diagnostics、队列 worker smoke。
9. 执行浏览器主流程 smoke：注册/登录、发帖、回帖、上传、通知、搜索、后台扩展页。

## 回滚条件

出现以下任一情况，停止放量并回滚：

- 数据库迁移失败且无法在 15 分钟内定位。
- `/api/health` 中 app/db/cache/queue/storage 任一生产必需项不可用。
- 扩展启用顺序或 foundation boundary gate 失败。
- 登录、发帖、回帖、后台权限任一主流程失败。
- 队列 worker 无法消费通知/异步任务。

回滚采用恢复备份方式，不依赖扩展 uninstall 删除业务数据。详见 [operations-runbook.md](operations-runbook.md)。

## 耦合度判断

当前耦合度可控：

- `bias_core` 没有直接依赖官方扩展生产模块。
- 扩展间业务能力依赖通过 runtime facade graph 和 service contract 显式化。
- manifest 强依赖必须同步到 `pyproject.toml` 的 wheel 依赖；`sync_extension_package_metadata` 和 `validate_extensions --strict` 会阻断两者漂移。
- `content`、`users` 是基础域，其他扩展扩展 foundation，不拥有基础生命周期。
- 前端扩展通过 `@bias/core/*` 和生成 import map 接入，不直接依赖宿主内部文件。

仍需持续治理：

- 老 runtime facade 仍存在兼容入口，新扩展应优先使用 `get_runtime_service()` 和声明式 service contract。
- `tags` 仍会扩展 discussion 创建 payload，但默认不再强制 discussion 必须携带 tags；只有配置最小标签数量时才强制。
- 每次新增扩展都必须跑 `inspect_extension_imports --check-runtime-facades` 和 `check_extension_workspace`，防止依赖图重新出现 cycle。
