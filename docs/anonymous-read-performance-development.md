# Bias 匿名读路径性能开发文档

日期：2026-07-01

## 结论

当前下一步开发必须先集中处理匿名读路径性能。`reports/capacity/20260701-211043` 的正式 300 秒 `forum-main` 容量报告已经证明：

- PostgreSQL 连接耗尽问题已通过 `DB_CONN_MAX_AGE=0` 收敛。
- 搜索 10 秒超时和 500/503 已通过默认搜索词和查询优化收敛。
- 最新一轮 `forum-main` error rate 为 0，但四个匿名读接口全部未达到 P95 阈值。

因此，在匿名读路径通过正式容量 gate 前，不继续推进 auth/write/upload/moderation/WebSocket 的正式容量结论，也不能把当前状态写成“足够给用户正式使用”。

最新失败基线：

| 接口 | 最新 P95 | 阈值 | 结果 |
| --- | ---: | ---: | --- |
| `GET /api/forum` | 882.276ms | 300ms | failed |
| `GET /api/discussions/?limit=20` | 1201.599ms | 300ms | failed |
| `GET /api/search?q=loadtest-discussion-00000001` | 1123.727ms | 800ms | failed |
| `GET /api/tags` | 1207.394ms | 300ms | failed |

正式容量报告位置：[reports/capacity/20260701-211043/summary.md](../reports/capacity/20260701-211043/summary.md)。

## 当前上线判断

当前项目可以继续做内部工程验证和受控本地 smoke，但还没有完成“给真实用户使用”的容量准入。

上线状态按下面口径判断：

| 阶段 | 是否满足 | 原因 |
| --- | --- | --- |
| 内部开发 smoke | 是 | check、扩展边界、安装态、短 smoke 已有证据 |
| 小规模真实用户试运行 | 暂不满足 | 正式 `forum-main` 300 秒 P95 未通过 |
| 正式生产发布 | 不满足 | 还缺匿名读容量、登录态/写入容量、升级回滚演练和目标环境报告 |

## 本阶段目标

把匿名公开读路径做到可以承受当前目标 seed 规模：

```text
users: 1000
discussions: 10000
posts: 100000
tags: 200
notifications: 50000
concurrency: 20
duration: 300s
```

验收命令：

```powershell
cd D:\files\project\tmp\bias
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
```

通过标准：

- `summary.ok=true`
- `summary.error_rate < 0.5%`
- `GET /api/forum` P95 < 300ms
- `GET /api/discussions/?limit=20` P95 < 300ms
- `GET /api/tags` P95 < 300ms
- `GET /api/search?q=loadtest-discussion-00000001` P95 < 800ms

## 开发原则

本阶段只处理匿名读性能，不做功能扩展。

优先级：

1. 先拿 query count、SQL explain、序列化耗时证据。
2. 先优化最热路径和重复工作，再考虑加缓存。
3. 缓存必须有明确失效源，不能牺牲权限正确性。
4. 修改后先跑 targeted tests，再重建 production smoke，再跑正式 300 秒。
5. 每批结果必须更新容量报告 summary 和本文档的执行记录。

不要做：

- marketplace、主题市场、复杂插件 UI。
- 改容量阈值来制造通过。
- 把热门词 `loadtest` 混入普通搜索 gate。
- 在没有连接预算的情况下用 `DB_CONN_MAX_AGE>0` 作为通过证据。

## Work Package 4.14：建立读路径画像

目标：拿到四个接口的 SQL 数量、慢 SQL、重复 SQL、序列化耗时和扩展 bootstrap 成本。

建议新增命令：

```text
bias_core/src/bias_core/management/commands/profile_read_paths.py
```

命令能力：

- 支持 `--base-url` 使用外部 HTTP 采样，输出端到端耗时。
- 支持 `--in-process` 使用 Django test client 或 RequestFactory，配合 `CaptureQueriesContext` 输出 SQL query count。
- 支持 `--path` 重复指定接口。
- 支持 `--repeat`、`--warmup`、`--format json`。
- PostgreSQL 下对慢 SQL 输出 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`，默认只 explain SELECT。
- 输出按 target 聚合的 total_ms、db_ms、serialize_ms、query_count、duplicate_query_count、slow_queries。

目标接口：

```powershell
python manage.py profile_read_paths --in-process --path "/api/forum" --path "/api/discussions/?limit=20" --path "/api/tags" --path "/api/search?q=loadtest-discussion-00000001" --repeat 5 --explain --format json
```

验收：

- 生成 `reports/capacity/<run-id>/read-path-profile-before.json`。
- 每个接口至少列出 query count 前 10 慢 SQL。
- 能区分 DB 时间和 Python 序列化/扩展 runtime 时间。

## Work Package 4.15：优化 `/api/forum`

疑似问题方向：

- public forum settings payload 每次重复组装。
- extension host、runtime view、frontend manifest、settings exposure 反复计算。
- 扩展 bootstrap 和公开能力列表缺少 request 外缓存。

开发任务：

1. 找到 `/api/forum` 的实际 handler 和 public settings serialization 路径。
2. 给 public forum payload 建立稳定缓存，缓存 key 至少包含 enabled extension set/version、frontend asset revision、public settings revision、locale。
3. settings、extension enable/disable、frontend publish 后必须失效缓存。
4. 避免每个请求重复扫描 workspace、manifest 或 frontend dist。
5. 保持开发模式和测试模式可强制绕过缓存。

验收：

```powershell
cd D:\files\project\tmp\bias
python manage.py check
python manage.py profile_read_paths --in-process --path "/api/forum" --repeat 5 --explain --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/forum=300" --concurrency 20 --duration 120 --fail-on-threshold --format json
```

通过标准：

- `/api/forum` query count 明显下降或稳定在可解释预算内。
- 单接口 120 秒 P95 < 300ms。
- public settings 修改后缓存能失效。

## Work Package 4.16：优化 `/api/discussions/?limit=20`

疑似问题方向：

- discussion list preload 不完整，序列化触发 N+1。
- tag、user、read state、last post、first post、权限判断重复访问数据库。
- 排序和可见性过滤在大表下缺少合适索引或顺序不佳。
- JSON:API include/resource field 扩展在每条 discussion 上重复计算。

重点文件：

```text
bias-content/bias_content/backend/runtime.py
bias-ext-tags/bias_ext_tags/backend/preloads.py
bias-ext-tags/bias_ext_tags/backend/resources.py
bias_core/src/bias_core/resource_*.py
```

开发任务：

1. 对 list query 输出 explain，确认排序字段、where 条件和索引使用。
2. 将当前页 discussion id 两阶段取出，再对当前页批量 preload 关系。
3. 保证 author、last_post_user、first_post_user、tags、user read state 都批量加载。
4. 权限判断使用批量上下文或 request-local memo，避免每条 discussion 重复计算相同 permission。
5. discussion resource serialization 增加 query budget 回归测试。

验收：

```powershell
cd D:\files\project\tmp\bias-content
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_content/backend/tests.py -k "discussion_list_preloads_core_user_relations" -q --tb=short

cd D:\files\project\tmp\bias
python manage.py profile_read_paths --in-process --path "/api/discussions/?limit=20" --repeat 5 --explain --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/discussions/?limit=20=300" --concurrency 20 --duration 120 --fail-on-threshold --format json
```

通过标准：

- `/api/discussions/?limit=20` 单接口 120 秒 P95 < 300ms。
- query count 有固定预算测试。
- explain 中 list 排序不出现全表高成本排序。

## Work Package 4.17：优化 `/api/tags`

疑似问题方向：

- tag list 序列化时重复计算 parent/children/latest discussion/user。
- tag permission scope 对每个 tag 重复访问 group/permission。
- tag stats 和 relation include 没有一次性 preload。
- 200 tag 并发下 Python 序列化和权限判断成本过高。

重点文件：

```text
bias-ext-tags/bias_ext_tags/backend/resources.py
bias-ext-tags/bias_ext_tags/backend/services.py
bias-ext-tags/bias_ext_tags/backend/preloads.py
bias-ext-tags/bias_ext_tags/backend/policies.py
```

开发任务：

1. `/api/tags` 默认响应按树结构一次性 preload parent、children、last discussion、last posted user。
2. 对匿名用户权限结果做 request-local 或短生命周期缓存。
3. 避免在每个 tag serialization 中单独查询 latest discussion、state、permission。
4. 如果 include 参数请求 children/parent，必须复用同一批已加载 tag 对象。
5. 增加 200 tag 的 query budget 回归测试。

验收：

```powershell
cd D:\files\project\tmp\bias-ext-tags
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_tags/backend/tests.py -k "tag" -q --tb=short

cd D:\files\project\tmp\bias
python manage.py profile_read_paths --in-process --path "/api/tags" --repeat 5 --explain --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/tags=300" --concurrency 20 --duration 120 --fail-on-threshold --format json
```

通过标准：

- `/api/tags` 单接口 120 秒 P95 < 300ms。
- 200 tag 下 query count 固定，不随 tag 数线性增长。
- 权限矩阵测试仍通过。

## Work Package 4.18：优化普通搜索

现状：

- `forum-main` 已从热门词 `loadtest` 改为选择性词 `loadtest-discussion-00000001`。
- 500/503 和 timeout 已消失。
- P95 仍高于 800ms，说明普通搜索还有排序、count、序列化或资源竞争问题。

重点文件：

```text
bias-ext-search/bias_ext_search/backend/services.py
bias-ext-search/bias_ext_search/backend/api.py
bias_core/src/bias_core/search_index_service.py
```

开发任务：

1. 对普通搜索输出 discussion query、post query、count query 的 explain。
2. 确认选择性 seed 词命中路径使用 PostgreSQL full-text GIN 索引。
3. 避免 `type=all` 为每个 section 做不必要 totals；普通 `forum-main` 可使用 bounded preview 或只取必要 section。
4. discussion search 继续保持两阶段分页，只对当前页补 excerpt 和 relevant post。
5. 将 hot-term stress 单独做 profile，不影响普通搜索 gate。

验收：

```powershell
cd D:\files\project\tmp\bias-ext-search
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_search/backend/tests.py -k "search_api_discussions_type_has_bounded_query_budget or search_discussions" -q --tb=short

cd D:\files\project\tmp\bias
python manage.py shell -c "from bias_core.search_index_service import SearchIndexService; print(SearchIndexService.get_status())"
python manage.py profile_read_paths --in-process --path "/api/search?q=loadtest-discussion-00000001" --repeat 5 --explain --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/search?q=loadtest-discussion-00000001=800" --concurrency 20 --duration 120 --fail-on-threshold --format json
```

通过标准：

- 普通搜索单接口 120 秒 P95 < 800ms。
- PostgreSQL search index status 为 healthy。
- 热门词 `loadtest` 只出现在单独 stress 报告中。

## Work Package 4.19：正式容量复跑

前置条件：

- 4.14 到 4.18 的单接口 120 秒压测全部通过。
- production smoke compose 已重建。
- strict health 返回 200。
- seed 目标规模确认。

执行：

```powershell
cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml up -d --build
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py shell -c "from django.conf import settings; db=settings.DATABASES['default']; print({'CONN_MAX_AGE': db.get('CONN_MAX_AGE'), 'CONN_HEALTH_CHECKS': db.get('CONN_HEALTH_CHECKS')})"
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py shell -c "from bias_core.search_index_service import SearchIndexService; print(SearchIndexService.get_status())"
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
```

报告要求：

- 新建或复用 `reports/capacity/<run-id>/`。
- 保存 `read-path-profile-before.json`、`read-path-profile-after.json`、单接口 120 秒报告、`load-http-forum-main-300s-after-read-optimization.json`、`summary.md`。
- `summary.md` 必须写明是否可作为 release evidence。

通过后再继续：

```powershell
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main-auth --login-username <load-user> --login-password <load-password> --concurrency 20 --duration 300 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write --login-username <load-user> --login-password <load-password> --discussion-id <discussion-id> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write-mixed --login-username <load-user> --login-password <load-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-upload --login-username <load-user> --login-password <load-password> --concurrency 5 --duration 120 --fail-on-threshold --format json
python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-write-moderation --login-username <moderator-user> --login-password <moderator-password> --prepare-isolated-targets --cleanup-isolated-targets --concurrency 2 --duration 60 --fail-on-threshold --format json
python manage.py load_test_websocket --base-url http://127.0.0.1:8000 --connections 20 --discussion-id <discussion-id> --p95-threshold-ms 1000 --broadcast-p95-threshold-ms 1000 --fail-on-threshold --format json
```

## 发布准入更新

在本阶段完成前，发布准入必须增加硬性阻断：

```text
reports/capacity/<latest>/summary.md 中 Status 必须是 passed release evidence。
最新 forum-main 300 秒正式容量必须 summary.ok=true。
不得使用短 smoke、单接口 120 秒结果或 error_rate=0 但 P95 失败的报告替代。
```

## 开发记录

### 2026-07-01

- 新增本文档作为 Work Package 4 第十四批入口。
- 当前正式容量报告 `20260701-211043` 状态为 failed，不是 release evidence。
- 下一批开发从 `profile_read_paths` 和四个匿名读接口画像开始。

### 2026-07-01 Work Package 4.14 第一批

已完成：

- 新增 `bias_core/src/bias_core/management/commands/profile_read_paths.py`。
- 命令支持 `--in-process` 使用 Django test client 捕获 SQL query count。
- 命令支持 `--base-url` 外部 HTTP 采样。
- 命令支持 `--path`、`--repeat`、`--warmup`、`--host`、`--header`、`--explain`、`--top-queries`、`--format json`。
- JSON 输出包含 `total_p50_ms`、`total_p95_ms`、`db_average_ms`、`db_p95_ms`、`serialize_average_ms`、`serialize_p95_ms`、`query_count_average`、`duplicate_query_count_average`、`slow_queries`、`errors`。
- PostgreSQL 下 `--explain` 会尝试 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`；非 PostgreSQL 使用 `EXPLAIN QUERY PLAN`。
- in-process 默认 `--host 127.0.0.1`，避免 Django test client 默认 `testserver` 被生产 `ALLOWED_HOSTS` 拦截。

验证：

```powershell
cd D:\files\project\tmp\bias_core
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest tests/test_extension_commands.py -k "profile_read_paths or extension_management_commands_skip_django_system_checks" -q --tb=short
```

结果：

- 5 passed，154 deselected。

站点层试跑：

```powershell
cd D:\files\project\tmp\bias
python manage.py profile_read_paths --in-process --path "/api/forum" --repeat 1 --warmup 0 --format json
```

结果：

- 命令可执行，并输出 query count、duplicate query count、slow query 列表。
- 当前本地非 production smoke 站点返回 HTTP 503，因此该试跑不是容量证据。
- 下一步应在 `deploy/docker-compose.production-smoke.yml` 环境中运行四个匿名读路径画像，并归档到容量报告目录。
