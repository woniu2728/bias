# Bias

Bias 是一个使用 Django + Vue 3 构建的论坛项目，目标是对齐 Flarum 2.x 的核心论坛体验和后台管理能力，同时采用更适合 Python 项目的实现方式。

当前它已经具备可用的论坛主链路、后台管理页、审核与举报治理能力、通知与搜索能力，但还不应该被描述为“100% 完成”或“完美复刻”。当前主线重点是：

- 完善治理链路
- 优化安装、初始化与升级体验
- 重写文档
- 优化后台管理体验

截至 2026-04-18，本地后端测试套件 `python manage.py test apps` 共 `94` 项通过。

## 当前能力

- 用户注册、登录、邮箱验证重发、密码重置、头像上传、基础资料维护
- 讨论与回复的创建、编辑、删除、置顶、锁定、隐藏、关注、已读
- Composer、附件上传、图片上传、表情面板、@ 提及、预览、草稿恢复
- 站内通知、WebSocket 通知基础链路、全局搜索、搜索结果页
- 标签管理、用户管理、权限管理、邮件设置、基础外观设置
- 举报、审核、封禁、治理通知与作者整改后重新提交审核

## 技术栈

- 后端：Django 5、Django Ninja、Channels、Celery
- 前端：Vue 3、Vue Router、Pinia、Vite
- 数据库：SQLite 或 PostgreSQL
- 缓存与队列：Redis 可选，本地快速启动可不使用

## 安装策略

项目当前明确支持两条安装路径：

1. 本地快速启动：`SQLite + 无 Redis`
2. 正式部署/预发布：`PostgreSQL + Redis`

这套策略已经固化到 `python manage.py init_forum`：

- 当选择 `--database sqlite` 时，默认写入 `USE_REDIS=False`
- 当选择 `--database postgres` 时，默认写入 `USE_REDIS=True`
- 可通过 `--redis on` 或 `--redis off` 显式覆盖默认策略

说明：

- `USE_REDIS=False` 时，项目会退回到进程内缓存、进程内 channel layer、内存 broker/backend，仅适合本地单进程开发或快速体验
- `USE_REDIS=True` 时，缓存、WebSocket channel layer、Celery broker/backend 会默认使用 Redis，更适合正式部署

## 后端安装

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

当前没有网页安装向导，首次安装统一使用 `init_forum` 命令。

#### 本地快速启动

这条路径默认使用 SQLite，且默认关闭 Redis：

```bash
python manage.py init_forum \
  --database sqlite \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password admin123456 \
  --non-interactive
```

命令会完成这些事情：

- 生成 `.env`
- 执行数据库迁移
- 初始化默认用户组与权限
- 创建或更新管理员账号

如果你想交互式填写数据库模式和管理员信息，也可以直接执行：

```bash
python manage.py init_forum
```

#### 正式部署 / 预发布环境

这条路径建议使用 PostgreSQL，并默认开启 Redis：

```bash
python manage.py init_forum \
  --database postgres \
  --db-name bias \
  --db-user postgres \
  --db-password postgres \
  --db-host 127.0.0.1 \
  --db-port 5432 \
  --redis auto \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive
```

如果你的 Redis 不是默认地址，可以继续补充：

```bash
python manage.py init_forum \
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

可选参数：

- `--skip-env-write`：不写 `.env`
- `--skip-migrate`：跳过迁移
- `--skip-admin`：跳过管理员创建
- `--env-file <path>`：指定环境文件路径
- `--frontend-url <url>`：指定前端地址
- `--sqlite-name <path>`：指定 SQLite 文件位置

## 前端安装与启动

```bash
cd frontend
npm install
npm run dev
```

默认前端地址为 `http://localhost:5173`。

## 运行项目

启动后端开发服务：

```bash
python manage.py runserver
```

常用入口：

- Forum 前台：`http://localhost:5173`
- 管理后台 SPA：`http://localhost:5173/admin.html`
- API 文档：`http://127.0.0.1:8000/api/docs`
- Django Admin：`http://127.0.0.1:8000/admin/`

## 环境变量

可参考 [`.env.example`](.env.example)。

关键变量说明：

- `DB_MODE=sqlite|postgres`
- `SQLITE_NAME=db.sqlite3`
- `USE_REDIS=False|True`
- `FRONTEND_URL=http://localhost:5173`
- `CELERY_BROKER_URL` 和 `CELERY_RESULT_BACKEND` 可留空，让系统按 `USE_REDIS` 自动选择默认值

## 升级当前版本

当前已经提供统一升级命令：

```bash
python manage.py upgrade_forum --non-interactive
```

默认会执行：

1. Django 系统检查
2. 数据库迁移
3. 默认用户组与权限同步
4. 运行时缓存清理

常用参数：

- `--collectstatic`：升级后执行 `collectstatic --noinput`
- `--skip-check`：跳过系统检查
- `--skip-migrate`：跳过迁移
- `--skip-init-groups`：跳过默认组同步
- `--skip-clear-cache`：跳过缓存清理
- `--dry-run`：只输出升级计划，不实际执行

推荐升级顺序：

1. 备份数据库、`media/` 和当前 `.env`
2. 拉取新代码
3. 更新 Python 依赖：`pip install -r requirements.txt`
4. 执行 `python manage.py upgrade_forum --non-interactive`
5. 如前端资源有变更，执行 `npm install`、`npm run build` 或重启前端开发服务
6. 重启 Django、Celery、反向代理等相关进程

SQLite 路径建议直接备份数据库文件；PostgreSQL 路径建议使用标准数据库备份方式。若升级失败，优先按你自己的备份方案恢复数据库、`media/` 和 `.env`，确认问题后再重新执行升级命令。

## 测试

运行完整后端测试：

```bash
python manage.py test apps
```

## Docker Compose

仓库内提供了 `docker-compose.yml`，它更接近一套 `PostgreSQL + Redis + Web + Celery + Nginx` 的部署示例。若只是本地快速开发，优先建议使用前面的原生安装方式。

## 项目文档

- 前端说明：[frontend/README.md](frontend/README.md)
- 日常协作与迭代建议通过 GitHub Issues / PR 管理

## 当前已知限制

- 还没有网页安装向导
- 升级命令目前不会自动做备份或自动回滚，生产环境仍应由部署方先完成备份
- 后台体验仍在继续优化，尤其是 Dashboard、Basics、Permissions、Appearance、Users
- 前端自动化测试与端到端测试体系尚未建立
