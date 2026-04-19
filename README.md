# Bias

Bias 是一个使用 Django + Vue 3 构建的论坛项目，目标是对齐 Flarum 2.x 的核心论坛体验和后台管理能力，同时采用更适合 Python 项目的实现方式。

## 技术栈

- 后端：Django 5、Django Ninja、Channels、Celery
- 前端：Vue 3、Vue Router、Pinia、Vite
- 数据库：SQLite 或 PostgreSQL
- 缓存与队列：Redis 可选，本地快速启动可不使用

## 当前安装/升级设计

当前流程参考了 Flarum 的安装与升级思路：

- 论坛运行时配置写入 `instance/site.json`
- `install_forum` / `init_forum` 负责首次安装
- `upgrade_forum` / `migrate_forum` 负责版本升级
- 运行时会区分 `uninstalled`、`upgrade_required`、`ready`
- API 可通过 `/api/system/status` 查看当前状态

这意味着：

- `.env` 不再是论坛运行时配置的主入口
- Docker 下的域名、CORS、CSRF、`ALLOWED_HOSTS` 不需要分别手填
- 升级时不会再依赖 `web` 容器启动时偷偷跑迁移

## Docker 安装

### 1. 准备环境

- Docker Desktop 或 Docker Engine + Docker Compose Plugin

### 2. 启动完整容器栈

```bash
git clone <your-repo-url>
cd bias
docker compose up -d --build
```

默认会启动：

- PostgreSQL
- Redis
- Django Web
- Celery
- 前端构建容器
- Nginx

此时如果还没有安装论坛，API 状态会是 `uninstalled`，这是正常行为。

### 3. 安装论坛

Docker 默认推荐使用 PostgreSQL + Redis，因此首次安装通常只需要这一条命令：

```bash
docker compose exec web python manage.py install_forum \
  --database postgres \
  --site-domains bias.chat,www.bias.chat \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive
```

命令会完成这些事情：

- 生成 `instance/site.json`
- 执行数据库迁移
- 初始化默认用户组与权限
- 写入当前安装版本
- 执行 `collectstatic`
- 创建或更新管理员账号

安装完成后重启应用进程，让新配置生效：

```bash
docker compose restart web celery
```

### 4. 域名配置

安装时只需要告诉 Bias 站点域名：

```bash
--site-domains bias.chat,www.bias.chat
```

Bias 会自动推导：

- `FRONTEND_URL`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`

默认按 `https` 推导。如果你的站点暂时只跑 HTTP，可额外传：

```bash
--site-scheme http
```

如果需要修改域名或协议，可以重新执行安装命令覆盖配置：

```bash
docker compose exec web python manage.py install_forum \
  --database postgres \
  --site-domains bias.chat,www.bias.chat \
  --site-scheme https \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive \
  --overwrite

docker compose restart web celery
```

### 5. Docker 下什么时候还需要 `.env`

`.env` 现在只建议用于 Docker 基础设施层，例如 PostgreSQL 容器初始化参数：

```env
DB_NAME=bias
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432
```

常见场景：

- 你想修改 PostgreSQL 默认库名、用户名、密码或映射端口
- 你在第一次 `docker compose up` 之前就决定不用默认数据库参数

不要再把站点域名、CORS、CSRF 等论坛运行时配置长期写在 `.env` 里。

### 6. 访问入口

- Forum 前台：`http://localhost:8080`
- 管理后台 SPA：`http://localhost:8080/admin.html`
- API 文档：`http://localhost:8080/api/docs`
- 系统状态：`http://localhost:8080/api/system/status`

如果你配置了正式域名，请把上面的地址替换为你的站点域名。

### 7. 常用 Docker 命令

```bash
docker compose logs -f
docker compose ps
docker compose down
```

如需清空数据库和媒体等持久化数据，可在确认无保留价值后执行：

```bash
docker compose down -v
```

## Docker 升级

推荐按下面顺序升级：

```bash
git pull
docker compose build web celery
docker compose up -d db redis frontend nginx web celery
docker compose exec web python manage.py upgrade_forum --non-interactive
docker compose restart web celery
```

`upgrade_forum` 默认会执行：

1. Django 系统检查
2. 数据库迁移
3. 默认用户组与权限同步
4. 写入当前安装版本
5. 运行时缓存清理
6. `collectstatic`

如果你的旧版本还是 `.env` 驱动，并且 `.env` 里保存的是完整旧配置，首次执行 `upgrade_forum` 时会自动迁移到 `instance/site.json`。

升级前建议备份：

- PostgreSQL 数据库
- `media/`
- `instance/site.json`

如果升级后日志出现：

```text
FATAL:  database "bias" does not exist
```

这通常表示 PostgreSQL 实例里的真实数据库名，与当前 Docker 基础设施层配置不一致。先检查库列表：

```bash
docker compose exec db psql -U "${DB_USER:-postgres}" -d postgres -c "\l"
```

然后二选一处理：

1. 如果历史数据在别的数据库里，把 `.env` 中的 `DB_NAME` 改成真实库名，再重建 `db/web/celery`
2. 如果你本来就应该使用 `bias`，就在 PostgreSQL 里创建 `bias` 数据库后重新执行升级

## 原生安装

### 1. 准备环境

- Python 3.11+
- Node.js 18+
- 本地快速启动不要求 Redis
- 正式部署建议准备 PostgreSQL 15+ 和 Redis 7+

### 2. 克隆项目并安装依赖

```bash
git clone <your-repo-url>
cd bias
python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

### 3. 初始化论坛

#### 本地快速启动

```bash
python manage.py install_forum \
  --database sqlite \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password admin123456 \
  --non-interactive
```

这条路径默认：

- 使用 SQLite
- 默认关闭 Redis
- 前端地址为 `http://localhost:5173`

#### 正式部署 / 预发布环境

```bash
python manage.py install_forum \
  --database postgres \
  --site-domains bias.chat,www.bias.chat \
  --db-name bias \
  --db-user postgres \
  --db-password postgres \
  --db-host 127.0.0.1 \
  --db-port 5432 \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive
```

如果 Redis 不是默认地址，可以继续补充：

```bash
python manage.py install_forum \
  --database postgres \
  --redis on \
  --redis-host 127.0.0.1 \
  --redis-port 6379 \
  --redis-db 0 \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive
```

安装完成后，核心配置会写入 `instance/site.json`。

### 4. 前端开发

```bash
cd frontend
npm install
npm run dev
```

默认前端地址为 `http://localhost:5173`。

### 5. 启动后端开发服务

```bash
python manage.py runserver
```

常用入口：

- Forum 前台：`http://localhost:5173`
- 管理后台 SPA：`http://localhost:5173/admin.html`
- API 文档：`http://127.0.0.1:8000/api/docs`
- 系统状态：`http://127.0.0.1:8000/api/system/status`

## 升级当前版本

```bash
python manage.py upgrade_forum --non-interactive
```

常用参数：

- `--config <path>`：指定站点配置文件，默认 `instance/site.json`
- `--skip-check`：跳过系统检查
- `--skip-migrate`：跳过迁移
- `--skip-init-groups`：跳过默认组同步
- `--skip-clear-cache`：跳过缓存清理
- `--skip-collectstatic`：跳过 `collectstatic`
- `--dry-run`：只输出升级计划，不实际执行

推荐升级顺序：

1. 备份数据库、`media/`、`instance/site.json`
2. 拉取新代码
3. 更新 Python 依赖：`pip install -r requirements.txt`
4. 执行 `python manage.py upgrade_forum --non-interactive`
5. 如前端资源有变更，执行 `npm install`、`npm run build` 或重启前端开发服务
6. 重启 Django、Celery、反向代理等相关进程

## 兼容命令

为兼容旧脚本，下面两组命令等价：

- `python manage.py install_forum`
- `python manage.py init_forum`

- `python manage.py upgrade_forum`
- `python manage.py migrate_forum`
