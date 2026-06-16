# Bias 优化评估与改进计划

> 本文档基于对 `config/settings.py`、`apps/core/middleware.py`、`apps/core/bootstrap_config.py`、`apps/core/runtime_checks.py`、`apps/core/startup_guard.py`、`apps/core/jwt_auth.py`、`extensions/users/backend/api.py`、`docker-compose.yml`、`Dockerfile`、`nginx.conf` 的直接审查，以及全库符号/规模扫描得出。
>
> 说明：性能相关结论为基于代码路径的静态分析，**未做基准压测**；安全项中部分已有缓解（见正文），文档会标注。优先级：P0=尽快、P1=近期、P2=中期、P3=收尾。

---

## 0. 优先级总览

| 优先级 | 类别 | 事项 | 影响 |
| --- | --- | --- | --- |
| P0 | 安全 | 登录/注册/找回密码默认限流 | 撞库、账号枚举 |
| P0 | 安全 | https 反代安全设置（SECURE_PROXY_SSL_HEADER 等） | cookie/CSRF 行为异常 |
| P0 | 安全 | Redis/Postgres 端口与 Redis 鉴权 | 数据泄露 |
| P0 | 部署 | 生产镜像默认命令去 runserver | 不安全/单线程 |
| P1 | 性能 | 每请求运行时同步改为版本号比对 | 每请求多次 cache 往返 |
| P1 | 性能 | ASGI 多进程部署 | 并发受限 |
| P1 | 架构 | 拆解 apps/core 巨型文件 | 维护/回归风险 |
| P2 | 可维护 | 拆分 tests.py（660KB 单文件） | 测试效率 |
| P2 | 可维护 | 合并 runtime_checks 与 admin_runtime_helpers 重复逻辑 | 逻辑漂移 |
| P2 | 架构 | 论坛领域概念下沉、framework 物理隔离 | 内核可复用性 |
| P3 | 收尾 | 移除死代码、生产 CORS 收敛、CI 覆盖率门槛 | 整洁度 |

---

## 1. 架构层面

### 1.1 拆解"上帝应用" apps/core（P1）
- **现状**：`apps/core` 承载资源框架、扩展运行时、设置、admin API、邮件、存储、在线状态、搜索等。单文件过大：`resource_registry.py` 2833 行（单类 `ResourceRegistry`）、`admin_content_api.py` 2195 行、`resource_objects.py` 856 行。
- **问题**：关注点混杂，改动牵连面大，回归风险高，新人上手成本高。
- **建议**：按三层拆分
  - `core/resource_framework`：`resource_objects/registry/serializer/endpoint_runner/search/validation`，纯框架、可独立测试。
  - `core/extension_runtime`：`apps/core/extensions/*`（加载、manifest、extender、lifecycle、frontend compiler）。
  - `core/platform`：设置、邮件、存储、在线、队列。
  - `core/admin_api`：按 router 拆成 extensions / settings / content / audit 多文件。
- **判断标准**：一个文件同时出现"序列化 + 权限 + 迁移 + 前端资源 + 调试信息"即应拆（`admin_content_api.py` 即是）。

### 1.2 收敛 runtime_* facade 样板（P2）
- **现状**：每扩展有 `runtime_posts/discussions/tags/users/moderation` 等逐方法转发封装，`apps/core/extensions/runtime_*` 又镜像一层。
- **问题**：样板代码多，"加一个方法改三处"。
- **建议**：基于已有 IoC 容器 `ExtensionApplication` 用统一 service-locator/代理暴露服务；或用 Protocol/ABC 声明 SDK 暴露面并自动校验。

### 1.3 论坛领域概念下沉（P2）
- **现状**：`apps/core/forum_registry.py` 仍内含 post_type/discussion_sort 等论坛业务概念。
- **建议**：把 discussion/post/tag 等领域概念彻底下沉到扩展，core 只保留通用 module/permission/resource 抽象，使 core 成为真正可复用的内核。

### 1.4 每请求运行时同步改造（P1，与 2.1 同源）
- **现状**：`ExtensionRuntimeInvalidationMiddleware` 每请求 `sync_extension_runtime_state_if_stale()`，可能重建 urlconf。
- **建议**：进程启动读一次运行时版本号，中间件只比对内存中的 version 整数，命中才重建；version 变更经 Redis pub/sub 或 cache 版本键广播。将"维护模式""启动状态"并入同一轻量运行时状态对象，单次内存读取替代 3 个中间件各自查 cache/DB。

### 1.5 多进程一致性作为架构约束（P2）
- **现状**：无 Redis 时回退 `LocMemCache`/`InMemoryChannelLayer`，在线状态/限流/运行时版本在多进程间不一致。
- **建议**：明确"多进程部署必须依赖 Redis"；让 `doctor`/启动自检在 `生产 + 多进程 + LocMem` 组合下显式报警。

### 1.6 扩展框架物理隔离（P2/P3）
- **现状**：manifest 校验、源码契约校验、安全模式、二分排障已成体系，边界靠约定 + import 校验。
- **建议**：将扩展框架物理隔离为独立包（同仓即可），独立测试集与版本号，强化 API 边界、隔离 core 业务改动对框架稳定性的影响。

---

## 2. 性能层面

### 2.1 热路径中间件开销（P1）
- **现状**：每请求叠加 `StartupStateMiddleware.get_runtime_status`、`MaintenanceModeMiddleware.get_maintenance_mode`、`ExtensionRuntimeInvalidationMiddleware.sync_extension_runtime_state_if_stale`，多次 cache 往返。维护模式开启时 `MaintenanceModeMiddleware._is_exempt` 对每个非 staff 请求执行 `resolve_authenticated_user`（JWT 解码）。
- **建议**：
  - 合并为单个轻量运行时状态对象，进程内短 TTL 缓存 + 失效信号，减少 cache 往返。
  - 维护模式热路径避免每请求 JWT 解码（仅在确需判定 staff 时再解码，或缓存判定结果）。

### 2.2 ASGI 单进程（P1）
- **现状**：`docker-compose.yml` 中 `web` 为 `daphne -b 0.0.0.0 -p 8000` 单进程，无多 worker/进程管理。
- **建议**：改用 `uvicorn --workers N` 或 `gunicorn -k uvicorn.workers.UvicornWorker --workers N`，worker 数按 CPU 调优；nginx 后做负载。

### 2.3 缓存后端一致性（P1/P2）
- **现状**：无 Redis 回退 `LocMemCache`，多进程下在线状态、限流计数、`public_forum_settings` 缓存彼此不一致。
- **建议**：生产强制 Redis（见 1.5）；为关键缓存键设计合理 TTL 与失效路径。

### 2.4 查询与序列化（P2）
- **现状**：已有 preload plan 与 N+1 回归测试（`test_*_avoids_n_plus_one`），方向正确。
- **建议**：
  - 对 `admin_content_api` 中的扩展详情/列表序列化做查询计数审查（这些接口字段多、易触发额外查询）。
  - 搜索（PG 全文 + jieba）在大数据量下确认已建 GIN 索引；`should_use_postgres_full_text` 路径补充 `EXPLAIN` 验证。

### 2.5 浏览量与实时（P2）
- **现状**：浏览量已节流 + 批量 flush（cache + celery），实时有 typing/online。设计良好。
- **建议**：压测 channels 在目标并发下的内存/连接数；确认 `channels_redis` group 订阅在大量讨论页时的开销。

---

## 3. 安全层面

### 3.1 登录暴力破解/枚举防护（P0）
- **现状**：`extensions/users/backend/api.py` 的 `login/register` 仅可选挂 Turnstile 人机验证（`extensions/security/backend/human_verification.py`）。通用 `ExtensionThrottleApiMiddleware` 存在，但 throttler 需扩展注册，**默认无登录/注册/找回密码限流**。
- **风险**：撞库、账号枚举。
- **建议**：默认提供基于 IP + 账号的失败计数限流（不依赖 Turnstile）；登录/注册错误消息统一化，避免泄露账号是否存在（`forgot_password` 已做防枚举，可作范式）。

### 3.2 https 反代安全设置缺失（P0）
- **现状**：部署在 nginx 后（`X-Forwarded-Proto`），但 settings 未设 `SECURE_PROXY_SSL_HEADER`，故 `request.is_secure()` 恒为 False；缺 `SESSION_COOKIE_SECURE`、`SECURE_HSTS_SECONDS`、`SECURE_SSL_REDIRECT`。`CSRF_COOKIE_SECURE = not DEBUG` 已设。
- **风险**：https 下 CSRF/cookie 行为异常、缺 HSTS。
- **建议**（https 部署）：
  ```python
  SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
  SESSION_COOKIE_SECURE = not DEBUG
  SECURE_SSL_REDIRECT = not DEBUG
  SECURE_HSTS_SECONDS = 31536000
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  SECURE_HSTS_PRELOAD = True
  ```

### 3.3 Redis/Postgres 暴露与 Redis 无鉴权（P0）
- **现状**：`docker-compose.yml` 将 5432、6379 `ports:` 暴露到宿主机；Redis 为 `redis-server --appendonly yes`，无密码。
- **风险**：公网/多租户主机上 Redis、DB 可被直接访问。
- **建议**：生产移除对外端口映射（仅 `expose` 或仅内网），Redis 设 `requirepass` 并在连接串携带密码。

### 3.4 生产镜像默认命令（P0）
- **现状**：`Dockerfile` 默认 `CMD ["python","manage.py","runserver","0.0.0.0:8000"]`（dev server），compose 虽覆盖，但裸用镜像不安全。
- **建议**：默认改为 daphne/uvicorn/gunicorn 生产命令。

### 3.5 密钥占位回退（已缓解，P2 巩固）
- **现状**：`bootstrap_config._load_env_bootstrap` 在缺 `SECRET_KEY/JWT_SECRET_KEY` 时回退硬编码占位值；但 `startup_guard.enforce_production_runtime_checks` 在生产环境检测到占位密钥（`runtime_checks.py:279` 识别 `change-this`）会 **拒绝启动**。
- **建议**：保留该守卫；补充文档强调生产必须显式设置；可考虑非生产也告警。

### 3.6 CORS 始终包含开发源（P3）
- **现状**：`resolved_cors_origins()` 永远含 `http://localhost:3000/5173`，生产配置亦然；`CORS_ALLOW_CREDENTIALS=True`。
- **建议**：生产环境剔除开发源。

### 3.7 异常吞没（P3）
- **现状**：`jwt_auth.resolve_authenticated_user/resolve_user_from_access_token` 用 `except Exception: return None`。
- **建议**：保留行为但加 debug 级日志，便于排查 token 校验异常。

### 3.8 挂载面（P3）
- **现状**：`web/celery` 挂入整仓 `.:/app`，`nginx` 只读挂入全仓，会把 `.git`、`instance/site.json`（含密钥）带入 nginx 容器。
- **建议**：nginx 仅挂载 `frontend/dist`、`staticfiles`、`media`，收窄挂载面。

### 3.9 CSP（P3）
- **现状**：`SecurityHeadersMiddleware` 的 CSP 中 `style-src` 含 `'unsafe-inline'`。
- **建议**：评估是否可用 nonce 替代内联样式，逐步收紧。

---

## 4. 可维护性

### 4.1 拆分巨型测试文件（P2）
- **现状**：`apps/core/tests.py` 660KB（核心测试约 15044 行单文件）。
- **建议**：按特性拆为多个测试模块（resource_framework / extension_runtime / settings / admin_api ...），提升发现与编辑效率。

### 4.2 拆解巨型业务文件（P1，见 1.1）
- `resource_registry.py`、`admin_content_api.py` 拆分。

### 4.3 去重（P2）
- **现状**：`runtime_checks.py` 与 `admin_runtime_helpers.py` 均定义 `KNOWN_PLACEHOLDER_SECRETS`、`looks_like_placeholder_secret`、`build_auth_secret_risks`、`build_auth_secret_status`、`probe_*`。前端序列化 `_serialize_frontend_value(s)` 在 `extensions/assets.py` 与 `frontend_runtime_service.py` 各有一份。
- **建议**：抽取共享模块，单一来源。

### 4.4 死代码/困惑配置（P3）
- `settings.py` 中 `ENABLE_DEBUG_TOOLBAR = DEBUG and False`（永久关闭），建议移除或改为环境变量开关。

### 4.5 CI 强化（P3）
- 现有 CI 跑 flake8/pytest/django test/npm build；建议增加测试覆盖率门槛与关键路径冒烟。

---

## 5. 代码冗余（汇总，详见 4.3）
- `runtime_checks.py` ↔ `admin_runtime_helpers.py` 密钥/探活逻辑重复。
- 前端序列化助手重复。
- 大量 `runtime_*` 薄封装样板（见 1.2）。
- `secure=not settings.DEBUG` 等 cookie 配置多处手写。

---

## 6. 功能完整性与缺口
- **已覆盖**：讨论/帖子/标签/点赞/举报/提及/通知/实时(打字、在线)/订阅/积分/AI/搜索/审核/上传(本地/S3/OSS/图床)/邮件。
- **缺口**：
  - 登录限流（见 3.1）。
  - 错误消息防枚举一致性（见 3.1）。
- **建议**：上述缺口补齐后，功能面已相当完整。

---

## 7. Bug / 风险点清单
- Dockerfile 默认 runserver（3.4）。
- Redis/DB 端口暴露 + Redis 无密码（3.3）。
- 缺 `SECURE_PROXY_SSL_HEADER` 等反代设置（3.2）。
- CORS 始终含开发源（3.6）。
- 异常静默吞没（3.7）。
- nginx 挂载面过大（3.8）。
- 死开关 `ENABLE_DEBUG_TOOLBAR`（4.4）。

---

## 8. 建议执行顺序（落地路线）
1. **第一批（P0，安全/部署）**：3.1 登录限流 → 3.2 反代安全设置 → 3.3 端口与 Redis 鉴权 → 3.4 生产镜像命令。
2. **第二批（P1，性能/架构）**：2.1+1.4 运行时状态版本号化 → 2.2 ASGI 多进程 → 1.1 拆 `admin_content_api.py`/`resource_registry.py`。
3. **第三批（P2，可维护/架构）**：4.1 拆 tests.py → 4.3 去重 → 1.2/1.3/1.5 facade 收敛与领域下沉。
4. **第四批（P3，收尾）**：4.4 死代码 → 3.6 CORS → 4.5 CI 覆盖率 → 3.9 CSP 收紧。

---

## 9. 运行实测补充发现（基于 Docker Compose 实际搭建）

> 环境：Docker 29 / Compose v5，postgres+redis 生产模式（debug=false），nginx 暴露 8080。以下为按 README 实际部署过程中暴露、仅静态阅读看不出的问题。

### 9.1【P0 阻断】README 的全新 PostgreSQL 安装根本无法完成
- **复现**：仅按 README 在 `.env` 填 DB 配置后执行 `docker compose up -d --build`，`bias_web` 立即陷入崩溃重启循环，日志报 `startup_guard` 生产自检失败（占位密钥 / 缺 FRONTEND_URL / console 邮件）。
- **根因链**：
  1. `bootstrap_config._load_env_bootstrap` 只要检测到 DB 凭据就把 `installed=True`、`debug=False` → `is_production_runtime()` 在**安装前**即为真。
  2. `startup_guard.enforce_production_runtime_checks()` 对占位密钥/缺 FRONTEND_URL/console 邮件 `raise ImproperlyConfigured`，web 无法启动。
  3. 而 `install_forum` 必须经 `docker compose exec web` 执行 → **鸡生蛋**，安装无法开始。
  4. 即便让 web 先以 DEBUG 启动，`install_forum._build_site_config` 对全新 postgres 安装**硬编码 `email_backend=console.EmailBackend` 且 `debug=False`**，且无任何 CLI 参数/环境变量可覆盖邮件后端；其迁移子进程（`run_manage_py` → `manage.py main()` → 同一个 guard）再次被 console 邮件后端拦截，安装中断并回滚 `site.json`。
- **结论**：文档化的"最小配置 + 一键脚本"在 postgres 模式下不可用。本次是通过手工预置合规 `site.json`（真实密钥 + smtp 邮件后端）再 `--overwrite` 才完成。
- **建议**：
  - env-bootstrap 在缺密钥时不应标记 `installed=True`；或 guard 对"未完成安装"状态放行。
  - `install_forum` 增加 `--email-backend` 并读取 `EMAIL_*` 环境变量；对 console 后端在安装阶段降级为告警而非 Critical。
  - `docker-compose.yml` 的 web/celery 注入 `SECRET_KEY/JWT_SECRET_KEY/FRONTEND_URL`，或 README 明确要求这些变量。

### 9.2【P0】http 部署下 Secure Cookie 全部失效（活体复现 3.2）
- **现象**：生产模式下 `/api/csrf` 下发 `csrftoken=...; Secure`，登录下发的 access/refresh cookie 同样 `Secure`，但站点运行在 `http://localhost:8080`。真实浏览器会**拒绝存储 Secure cookie**，导致 CSRF 校验与 cookie 登录在 http 部署下直接不可用（curl 因忽略 Secure 才"看似正常"）。
- **根因**：`CSRF_COOKIE_SECURE = not DEBUG`，但缺 `SECURE_PROXY_SSL_HEADER`，且 nginx 以 http 对外。
- **建议**：见 3.2；http 演示环境应允许非 Secure cookie，https 环境补 `SECURE_PROXY_SSL_HEADER`。

### 9.3【P1】前台 HTML 与静态资源无任何安全响应头
- **现象**：`/api/*`（经 Django）带 CSP/X-Frame-Options/X-Content-Type-Options/Referrer-Policy；但 `/`、`/admin.html`、JS/CSS 由 **nginx 直接返回，无上述任何安全头**（实测 `/` 响应头为空）。
- **根因**：`SecurityHeadersMiddleware` 只覆盖 Django 响应；`nginx.conf` 未对静态/SPA 文档添加安全头。
- **建议**：在 `nginx.conf` 的 `location /` 与静态块补 `add_header`（CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy、HSTS），与 Django 端保持一致。

### 9.4【P1】Celery worker 空转（队列默认关闭但仍起容器）
- **现象**：`bias_celery` 已 `Connected to redis://redis:6379/1` 且 `ready`，但 `/api/health` 显示 `queue_enabled=false`、`queue_worker_status=disabled`（"队列关闭，任务同步执行"）。
- **影响**：默认配置下 worker 收不到任何任务，浏览量 flush、邮件、通知等都同步执行；celery 容器纯属空耗资源，且运维易误判"已异步化"。
- **建议**：安装/设置层面统一语义——启用 Redis 即默认启用队列并把同步任务路由给 worker；或默认不启动 celery 容器，待显式开启队列再拉起。

### 9.5【P2】公开 health 端点信息披露
- **现象**：`/api/health` 匿名可读，返回数据库标签 `PostgreSQL (bias @ db)`、缓存/实时/队列驱动、`redis_enabled`、依赖探活明细等基础设施拓扑。
- **建议**：匿名仅返回 `state/version` 等最小信息，基础设施明细移至需鉴权的 admin 接口。

### 9.6 运行正常项（已验证）
- `doctor` 7 项全过（runtime_status/database/migrations/extensions/frontend_dist/extension_frontend_manifest/cache）。
- 用户组与权限初始化正常（Admin/Member/Guest）。
- 登录（带 CSRF）→ 返回 JWT 与 httponly cookie；`/api/discussions/` 列表 200（空论坛 total=0，过滤器元数据完整）；`/api/docs`、`/admin.html` 均 200。
- 前端 dist 构建成功，扩展前端 manifest 覆盖 17 个扩展。
- 注意：`/api/discussions` 无尾斜杠时 301 跳 `/api/discussions/`（APPEND_SLASH），前端/客户端需跟随重定向。

### 9.7 本次为搭建所做的临时改动（评估用，需还原）
- 新增 `docker-compose.override.yml`：给 web/celery 注入 `DEBUG=1`，仅用于让安装前的 web 能启动。
- 手工写入 `instance/site.json`（真实密钥 + `smtp` 邮件后端 + `frontend_url=http://localhost:8080`）以绕过 9.1 的安装阻断。
- 上述两项是为获得可评估实例的权宜手段，**不代表推荐配置**；正式修复应走 9.1 的建议。

---

## 10. 运行时深挖补充（实例已稳定运行后采集）

> 环境：实例已 `Up` 二十余分钟，postgres+redis 生产模式。以下基于 `docker stats`、`docker top`、容器日志、响应头与延迟实测，是仅看代码或仅看一次启动日志发现不了的运行态问题。

### 10.1【P0】Celery 默认 52 个 prefork worker 空转，吃掉 2.76 GiB
- **实测**：`docker stats` 显示 `bias_celery` 常驻 **2.762 GiB**（web 仅 103 MiB、redis 4.6 MiB）；`docker top bias_celery` 共 **53 个进程**；启动日志 `concurrency: 52 (prefork)`。
- **根因**：`docker-compose.yml` 中 celery 命令为 `celery -A config worker -l info`，未指定 `--concurrency`，Celery 默认取宿主机 CPU 数（本机 52 核），于是 fork 出 52 个 worker，每个都完整加载 Django + 17 个扩展。
- **双重浪费**：结合 9.4，当前 `queue_enabled=false`，这 52 个进程**收不到任何任务**，2.76 GiB 内存纯属空耗；即便开启队列，论坛场景 52 并发也远超所需。
- **建议**：
  - 显式 `--concurrency`（如 2~4，按实际任务量定）并加 `--max-tasks-per-child=200` 限制单 worker 生命周期内存增长。
  - 与 9.4 联动：队列关闭时干脆不启动 celery 容器（compose profile），开启队列再拉起。
  - 高并发再考虑 `-P gevent/eventlet`（IO 密集型任务）替代 prefork 以降进程内存。

### 10.2【P1】Vite 内容哈希资源无 `Cache-Control`，每次加载都回源校验
- **实测**：`curl -I http://localhost:8080/assets/main-BcPEsDWj.js` 仅返回 `Last-Modified` + `ETag`，**无 `Cache-Control`/`Expires`**。`index.html`、`/assets/*.css/js` 均如此。
- **根因**：`nginx.conf` 只对 `location /static/`（Django collectstatic）和 `/media/` 配了 `expires`/`Cache-Control immutable`；但 SPA 构建产物在 `root /app/frontend/dist`，`/assets/*` 走 `location /` 的 `try_files`，没有任何缓存指令。
- **影响**：带内容哈希的 JS/CSS 本应 `immutable` 缓存一年，现在浏览器每次访问都发条件请求拿 304，徒增 RTT 与 nginx 开销；反而 `index.html` 没有 `no-cache`，新版上线可能被旧缓存挡住。
- **建议**：在 nginx 增加
  ```nginx
  location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; }
  location = /index.html { add_header Cache-Control "no-cache"; }
  ```
  （admin.html 同理），与 9.3 的安全头一并补在静态/文档块。

### 10.3【P1】web / celery / nginx 三个容器均无 Docker healthcheck
- **实测**：`docker inspect` 显示 `bias_web`、`bias_celery`、`bias_nginx` 全部 `NO HEALTHCHECK`（仅 db/redis/frontend 有）。
- **影响**：daphne/celery 若进入假死或事件循环阻塞，进程未退出，`restart: unless-stopped` 不会触发重启；`nginx depends_on web` 用的是 `service_started` 而非 `service_healthy`，nginx 可能在 web 尚未就绪时就转发请求。
- **建议**：
  - web 加 HTTP healthcheck（如 `curl -f http://localhost:8000/api/health`）。
  - celery 加 `celery -A config inspect ping` healthcheck。
  - nginx 加 `service_healthy` 依赖，并对自身加 `wget -qO- localhost/`。

### 10.4【P2】Celery 以 root 运行
- **实测**：celery 日志 `SecurityWarning: You're running the worker with superuser privileges`。
- **建议**：Dockerfile/compose 切换非 root 用户运行（或 celery `--uid`），与最小权限原则一致。

### 10.5【P2】frontend 容器用 `npm install` 而非 `npm ci`，且常驻空转
- **现状**：compose 中 frontend 命令为 `npm install && npm run build && tail -f /dev/null`。
- **问题**：`npm install` 不锁定，构建结果不可复现；容器构建完后靠 `tail -f` 空转常驻，仅为持有 dist。
- **建议**：改用 `npm ci`（有 lockfile 时）保证可复现；构建产物可改为一次性 job 或多阶段构建产出后退出，避免常驻空容器。

### 10.6【P3】Celery `broker_connection_retry` 弃用告警
- **实测**：日志反复出现 `CPendingDeprecationWarning: The broker_connection_retry configuration setting will no longer determine...`。
- **建议**：在 Celery 配置中显式设置 `broker_connection_retry_on_startup = True`，消除告警并适配新版本语义。

### 10.7【P3】nginx 压缩可进一步优化
- **现状**：`gzip on` 已生效（实测 `/`、JS 均 `Content-Encoding: gzip`），但未设 `gzip_min_length`、无 `gzip_static`（预压缩）、无 brotli。
- **建议**：设 `gzip_min_length 1024`；若构建产出 `.gz`/`.br` 可启用 `gzip_static`/`brotli_static`，把压缩从请求时移到构建时。

### 10.8 运行时基线（参考，非问题）
- 空论坛 `/api/discussions/` 单进程 daphne 延迟 ~115~134ms（TTFB≈total），可作为 2.2 多进程改造前的对照基线。
- web 内存 103 MiB、nginx 2.9 MiB、redis 4.6 MiB、db 32 MiB，均健康；唯 celery 异常（见 10.1）。

---

*最后更新：2026-06-16（含运行实测补充 + 运行时深挖第 10 节）*
