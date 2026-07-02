# Bias 匿名读路径性能开发文档

日期：2026-07-01

## 结论

P0 匿名读路径性能 gate 已通过。`reports/capacity/20260702-011925` 的正式 300 秒 `forum-main` 容量报告证明：

- PostgreSQL 连接耗尽问题已通过 `DB_CONN_MAX_AGE=0` 收敛。
- 搜索 10 秒超时和 500/503 已通过默认搜索词和查询优化收敛。
- 最新一轮 `forum-main` error rate 为 0，四个匿名读接口全部达到 P95 阈值。

因此，P0 可以作为匿名读 release evidence。P1 auth/write/upload/moderation gate 已在 `reports/capacity/20260702-020409` 通过；WebSocket/realtime 与 P2 production-smoke ops gate 已在 `reports/capacity/20260702-025600` 通过。后续仍需进入目标环境部署、升级执行、回滚恢复和真实生产集成 gate，不能仅凭本地 production-smoke 结果宣称“足够给真实用户长期使用”。

最新正式通过结果：

| 接口 | 最新 P95 | 阈值 | 结果 |
| --- | ---: | ---: | --- |
| `GET /api/forum` | 227.741ms | 300ms | passed |
| `GET /api/discussions/?limit=20` | 286.790ms | 300ms | passed |
| `GET /api/search?q=loadtest-discussion-00000001` | 477.282ms | 800ms | passed |
| `GET /api/tags` | 218.777ms | 300ms | passed |

正式容量报告位置：[reports/capacity/20260702-011925/summary.md](../reports/capacity/20260702-011925/summary.md)。

## 当前上线判断

当前项目可以继续做内部工程验证和受控本地 smoke，但还没有完成“给真实用户使用”的容量准入。

上线状态按下面口径判断：

| 阶段 | 是否满足 | 原因 |
| --- | --- | --- |
| 内部开发 smoke | 是 | check、扩展边界、安装态、短 smoke 已有证据 |
| 小规模真实用户试运行 | 条件性满足 P0/P1/realtime smoke | 匿名读、登录态/写入正式容量 gate 和 production-smoke realtime/ops smoke 已通过；仍需补升级执行、回滚恢复和目标环境运维 gate |
| 正式生产发布 | 不满足 | 还缺目标环境容量报告、真实生产集成和升级回滚演练 |

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

下面记录按时间保留当时状态；2026-07-02 后 P0/P1 和 production-smoke realtime/ops smoke 已通过，最新结论以文档顶部和最新报告为准。

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

### 2026-07-01 Work Package 4.17 第一批

已完成：

- 在 `bias-ext-tags/bias_ext_tags/backend/responses.py` 新增 `/api/tags` 默认 plain index fast serializer。
- fast serializer 仅用于非 JSON:API、未请求 `fields[tag]` 且 include 集合可覆盖的 tag index 响应。
- 保留 JSON:API、显式字段裁剪、写入、详情页和 unsupported include 的通用 resource serializer 路径。
- fast serializer 复用现有 tag preload、permission cache、forbidden tag cache、state preload 和 last posted summary resolver。
- `can_view_tag_stored_slug()` 增加 request-local capability cache，避免同一 tag index 请求逐条调用 `tag.edit` 权限判断。
- 新增 200 tag query budget 回归测试，覆盖 plain `/api/tags?include=children` 查询数固定，不随 tag 数线性增长。

验证：

```powershell
cd D:\files\project\tmp\bias-ext-tags
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_tags/backend/tests.py::TagAccessApiTests -q --tb=short
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_tags/backend/tests.py -k "tag" -q --tb=short

cd D:\files\project\tmp\bias
python manage.py check
python manage.py profile_read_paths --in-process --path "/api/tags" --repeat 3 --warmup 1 --format json
```

结果：

- `TagAccessApiTests`：83 passed。
- `bias_ext_tags/backend/tests.py -k "tag"`：256 passed。
- `python manage.py check`：System check identified no issues。
- 本地非 production smoke 站点的 `/api/tags` profile 仍返回 HTTP 503，因此该 profile 不是容量证据。

下一步：

- 在 production smoke 环境重建 web 后，运行 `/api/tags` in-process profile 和单接口 120 秒压测。
- 若 `/api/tags` 达标，继续推进 `/api/discussions/?limit=20`、`/api/search?q=loadtest-discussion-00000001` 和 `/api/forum` 的单接口 gate。

### 2026-07-01 Work Package 4.17 第二批

已完成：

- 将 `/api/tags` anonymous/plain/default-view cache 前移到 tag index endpoint handler，命中时绕过通用 DatabaseResource query/results/serializer pipeline。
- cache key 从每次请求聚合 tags 表改为 Redis/Django cache 中的版本号，避免 cache hit 仍访问 tag 表。
- 新增 `Tag` save/delete signal invalidation，并在 tag 排序、统计、latest discussion 等 bulk update 路径主动 bump anonymous tag index cache version。
- handler 仅接管 anonymous、plain、default `view`、无 `fields[tag]`、无 `include_hidden`、无 `discussion_tag_ids`、include 集合受支持的请求；JSON:API、认证用户、特殊 purpose 和 unsupported include 仍回落到通用 resource runner。
- 修复 `bias_core` runtime URLConf rebuild 竞争：`sync_extension_runtime_state_if_stale()`/`rebuild_runtime_urlconf()` 加入进程内 reentrant lock，并串行化 API namespace 分配，避免并发压测时 NinjaAPI 重复注册导致偶发 500。

验证：

```powershell
cd D:\files\project\tmp\bias-ext-tags
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_tags/backend/tests.py::TagAccessApiTests -q --tb=short
git diff --check

cd D:\files\project\tmp\bias_core
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest tests/test_extension_loader.py::ExtensionManifestLoaderTests::test_extension_runtime_invalidation_middleware_rebuilds_from_persistent_version tests/test_extension_loader.py::ExtensionManifestLoaderTests::test_extension_runtime_invalidation_middleware_uses_short_version_cache tests/test_extension_registry.py::ExtensionRegistryTests::test_runtime_invalidation_resets_runtime_and_url_caches -q --tb=short
git diff --check

cd D:\files\project\tmp\bias
python manage.py check
docker compose -f deploy/docker-compose.production-smoke.yml build web
docker compose -f deploy/docker-compose.production-smoke.yml up -d --no-deps --force-recreate web
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py profile_read_paths --in-process --path "/api/tags" --repeat 5 --warmup 1 --format json
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/tags=300" --concurrency 20 --duration 120 --fail-on-threshold --format json
```

结果：

- `TagAccessApiTests`：84 passed。
- `bias_core` focused runtime invalidation tests：3 passed。
- `python manage.py check`：System check identified no issues。
- production smoke strict health：ok。
- installed-code probe confirmed `dispatch_tag_index` uses `can_use_anonymous_tag_index_cache` and `sync_extension_runtime_state_if_stale` uses `_runtime_rebuild_lock`。
- `/api/tags` in-process profile：5 samples, 0 errors, P95 `3.5055ms`, query average `0.2`, query max `1`。
- host-side external 120s run after cache optimization reached P95 `150.096ms` but failed because Windows client exhausted ephemeral sockets (`WinError 10048`) and produced proxy fallout; not used as pass evidence.
- in-container 120s run before core lock reached P95 `93.7188ms` but had one 500 from concurrent runtime URLConf rebuild / NinjaAPI registration race; not used as pass evidence.
- final in-container 120s `/api/tags` gate passed:
  - request_count `31321`
  - status `31321x 200`
  - error_count `0`
  - error_rate `0.0`
  - average `76.614ms`
  - P50 `77.961ms`
  - P95 `101.682ms`
  - P99 `152.852ms`
  - threshold `300ms`
  - requests_per_second `260.906`
  - summary.ok `true`

下一步：

- `/api/tags` 可视为单接口 120 秒 gate 已通过。
- 继续推进 `/api/discussions/?limit=20`、`/api/search?q=loadtest-discussion-00000001` 和 `/api/forum` 单接口 gate。
- P0 仍未完成；必须等 `forum-main --concurrency 20 --duration 300 --fail-on-threshold` 正式通过并归档证据后，才能标记 release evidence。

### 2026-07-02 Work Package 4.16

已完成：

- 为 `/api/discussions/?limit=20` 增加 anonymous/plain/default-list lightweight payload。
- 快路径仅用于匿名、plain、默认 all/latest、page 1、limit 20、无搜索、无 author、无显式 include、无 `fields[discussion]` 的请求。
- 允许 tags 扩展注入的默认 `tags` / `tags.parent` include，并在快路径中直接输出轻量 tag 摘要。
- 保留 JSON:API、登录态、字段裁剪、显式 include、搜索、筛选和非默认分页的通用 resource serializer 行为。
- 默认匿名列表响应从约 `39001` bytes 降到约 `20341` bytes，移除匿名场景下恒为 false 的 capability 字段、points、primary_group 和完整 tag payload。

验证：

```powershell
cd D:\files\project\tmp\bias-ext-discussions
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest bias_ext_discussions/backend/tests.py -k "anonymous_default_discussion_list_uses_lightweight_payload or discussion_list_field_selection_bypasses_anonymous_lightweight_payload or discussion_list_default_page_has_bounded_queries or discussion_list_does_not_default_to_most_relevant_post_user_include" -q --tb=short
git diff --check

cd D:\files\project\tmp\bias
docker compose -f deploy/docker-compose.production-smoke.yml build web
docker compose -f deploy/docker-compose.production-smoke.yml up -d --no-deps --force-recreate web
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py profile_read_paths --in-process --path "/api/discussions/?limit=20" --repeat 5 --warmup 1 --format json
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py load_test_http --base-url http://127.0.0.1:8000 --path "GET /api/discussions/?limit=20=300" --concurrency 20 --duration 120 --fail-on-threshold --format json
docker compose -f deploy/docker-compose.production-smoke.yml exec -T web python manage.py load_test_http --base-url http://127.0.0.1:8000 --profile forum-main --concurrency 20 --duration 300 --fail-on-threshold --format json
```

结果：

- Focused discussion tests：4 passed。
- `git diff --check`：通过。
- production smoke strict health：ok。
- `/api/discussions/?limit=20` in-process profile：5 samples, 0 errors, P95 `47.429ms`, query average `5.2`, query max `6`, serialize average `17.855ms`。
- `/api/discussions/?limit=20` in-container 120s gate passed:
  - request_count `11999`
  - status `11999x 200`
  - error_count `0`
  - error_rate `0.0`
  - average `200.084ms`
  - P50 `197.060ms`
  - P95 `272.993ms`
  - P99 `294.214ms`
  - threshold `300ms`
  - summary.ok `true`
- final in-container 300s `forum-main` gate passed:
  - request_count `27378`
  - error_count `0`
  - error_rate `0.0`
  - requests_per_second `91.153`
  - failed_threshold_count `0`
  - `/api/forum` P95 `227.741ms`
  - `/api/discussions/?limit=20` P95 `286.790ms`
  - `/api/search?q=loadtest-discussion-00000001` P95 `477.282ms`
  - `/api/tags` P95 `218.777ms`
  - summary.ok `true`

正式证据：

- [reports/capacity/20260702-011925/summary.md](../reports/capacity/20260702-011925/summary.md)

结论：

- P0 匿名读路径正式容量 gate 已通过。
- P1 登录态和写入容量已在后续报告中通过，不再把匿名读性能作为当前阻塞项。

### 2026-07-02 P1 登录态和写入容量

已完成：

- 新增 `prepare_load_test_actors`，创建稳定 auth/moderator 压测用户并关闭负载测试通知偏好。
- `forum-main-auth` 登录态读路径增加默认轻量响应和 skip-total 首屏路径。
- unread filter 改为 `Subquery + Coalesce` annotation，减少 join duplication 和 `distinct()` 成本。
- `load_test_http` 支持请求时序列渲染、隔离写入目标和按目标字段独立推进的状态转换池。
- production smoke 中 web/worker 使用同一构建产物后，P1 五个正式 profile 均通过。

正式证据：

- [reports/capacity/20260702-020409/summary.md](../reports/capacity/20260702-020409/summary.md)

结果：

- `forum-main-auth` 300 秒：`summary.ok=true`，error rate `0.0`。
- `forum-write` 120 秒：`summary.ok=true`，reply P95 `384.437ms`。
- `forum-write-mixed` 120 秒：`summary.ok=true`，like P95 `134.853ms`。
- `forum-upload` 120 秒：`summary.ok=true`，upload P95 `202.891ms`。
- `forum-write-moderation` 60 秒：`summary.ok=true`，hide P95 `82.947ms`。

后续：

- 进入目标环境 P2 部署运维、升级执行、回滚恢复和目标环境容量 gate。

### 2026-07-02 WebSocket/realtime 与 P2 production-smoke ops

已完成：

- 在 production-smoke 栈补跑外部 WebSocket connect/subscribe/broadcast gate。
- 补跑 strict health、HTTP P95 smoke、queue worker smoke。
- `install_forum --dry-run --format json` 和 `upgrade_forum --dry-run --format json` 均输出机器可读计划。
- `backup_forum --format json` 能创建 site config、PostgreSQL dump、media、static/frontend 四类备份产物。
- `verify_forum_backup --format json` 能验证备份产物可读。
- `upgrade_forum --non-interactive --format json` 能实际执行升级步骤并输出纯 JSON。
- `plan_forum_rollback --require-existing-backups --format json` 能检查备份产物并输出机器可读恢复计划。
- `rehearse_forum_restore --format json` 能在隔离临时目标中恢复备份并验证，不覆盖当前运行数据。
- `restore_forum_backup --dry-run --format json` 能输出受保护 live restore 计划；非 dry-run 必须双重确认，且尚未在目标环境执行 destructive restore。
- `smoke_runtime_integrations --format json` 能输出 SMTP 配置和 storage backend 的机器可读 smoke 结果；production-smoke 已覆盖 local storage 写删。

正式证据：

- [reports/capacity/20260702-025600/summary.md](../reports/capacity/20260702-025600/summary.md)

结果：

- WebSocket 20/20 connections，connect P95 `3.019ms`，subscribe P95 `20.345ms`，broadcast P95 `2.604ms`。
- strict health：`status=ok`，`strict_failed=false`。
- HTTP P95 smoke：5 targets，0 failed。
- queue worker smoke：1 worker online，probe task ok。
- install dry-run：8 steps，0 errors，0 warnings。
- upgrade dry-run：10 steps，`dry_run=true`，`executed=false`，0 errors，0 warnings。
- backup：4 artifacts，0 missing，0 errors，0 warnings。
- backup verification：4 checks，0 errors。
- upgrade executed：10 executed steps，`dry_run=false`，`executed=true`，0 errors，0 warnings。
- post-upgrade smoke：strict health、HTTP P95 smoke、queue worker smoke 均通过。
- rollback plan with backups：`require_existing_backups=true`，0 missing，0 errors，0 warnings，`executes_restore=false`。
- restore rehearsal：`summary.ok=true`，0 errors，1 PostgreSQL client/server compatibility warning；临时库 `bias_smoke_restore_smoke_20260702_p2_smoke` 已删除，验证 31 张 public 表，media 10718 files，static/frontend 131 files，`executes_live_restore=false`。
- restore live dry-run：`summary.ok=true`，0 errors，0 warnings，4 个 destructive restore steps，`dry_run=true`，`executes_live_restore=false`。
- runtime integrations：`summary.ok=true`，0 errors，1 warning；email config dry-run 通过，local storage 临时对象写入/删除通过且无 probe 文件残留。

后续：

- 目标环境真实 HTTPS/WebSocket、SMTP connect、对象存储、多节点和 destructive 回滚恢复演练仍未完成。
