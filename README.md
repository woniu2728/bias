# Bias

Bias 是一个使用 Django + Vue 3 构建的论坛项目，目标是提供扩展优先的现代论坛体验和后台管理能力，同时采用更适合 Python 项目的实现方式。

## 技术栈

- 后端：Django 5、Django Ninja、Channels、Celery
- 前端：Vue 3、Vue Router、Pinia、Vite
- 数据库：SQLite 或 PostgreSQL
- 缓存与队列：Redis 可选，本地快速启动可不使用

## 当前安装/升级设计

当前安装与升级流程：

- 论坛运行时配置只写入 `instance/site.json`
- 首次安装使用 `install_forum`
- 版本升级使用 `upgrade_forum`
- 运行时会区分 `uninstalled`、`upgrade_required`、`ready`
- API 可通过 `/api/system/status` 查看状态

## 版本发布规范

后续版本只认这 3 个概念：

- `VERSION`：代码版本源
- Git tag：发布标签，固定格式 `vX.Y.Z`
- `system.version`：站点已安装版本

强制规则：

- `VERSION` 必须和 `frontend/package.json` 的 `version` 完全一致
- Git tag 必须和 `VERSION` 一致，例如 `VERSION=1.2.3` 对应 `v1.2.3`
- 安装和升级完成后，必须写入 `system.version`
- 以后不要手工分别修改多个版本文件，统一走命令

发布前先执行：

```bash
python manage.py prepare_release --set-version 1.0.1
```

或者直接按 tag 校验：

```bash
python manage.py prepare_release --tag v1.0.1
```

这个命令会：

- 校验版本号是否符合语义化版本
- 同步 `VERSION` 与 `frontend/package.json`
- 校验 Git tag 格式
- 默认要求 Git 工作区干净

如果只是预检查，不写文件：

```bash
python manage.py prepare_release --tag v1.0.1 --dry-run
```

准备好版本后，再创建发布 tag：

```bash
python manage.py finalize_release --tag v1.0.1
git push origin main --tags
```

如果只想校验，不实际创建 tag：

```bash
python manage.py finalize_release --tag v1.0.1 --dry-run
```

`finalize_release` 会强制检查：

- `VERSION`
- `frontend/package.json`
- Git tag 与代码版本是否一致
- Git 工作区是否干净
- Git tag 是否已经存在

如果你希望本地一条命令串起来做“版本准备 + tag 校验/创建”，可以直接用：

```bash
python manage.py publish_release --set-version 1.0.1
```

它会顺序执行：

- `prepare_release --set-version 1.0.1 --tag v1.0.1`
- `git add VERSION frontend/package.json frontend/package-lock.json`
- `git commit -m "发布 1.0.1"`
- `finalize_release --tag v1.0.1`

然后你再执行：

```bash
git push origin main --tags
```

如果希望连 push 一起自动做掉：

```bash
python manage.py publish_release --set-version 1.0.1 --push
```

## 持续集成

仓库已提供最小 GitHub Actions 工作流 `.github/workflows/ci.yml`，默认会执行：

- 版本一致性检查（`VERSION == frontend/package.json`）
- 后端关键 `flake8` 检查
- `pytest`
- `python manage.py test`
- 前端 `npm run build`

仓库还提供了 `.github/workflows/release.yml`：

- 当 push `vX.Y.Z` tag 时自动创建 GitHub Release
- Release 前会再次校验 `VERSION` 和 tag 是否一致

本地提交前建议至少执行：

```bash
pytest
python manage.py test
cd frontend && npm run build
```

## Docker 安装

### 1. 启动容器栈

先创建 `.env`：

```bash
git clone <your-repo-url>
cd bias
cp .env.example .env
```

然后至少填写这三个变量：

```env
DB_NAME=your_bias_db
DB_USER=your_bias_user
DB_PASSWORD=your_strong_password
```

`DB_PORT` 可选，默认 `5432`。

如果这台机器之前跑过同名 Bias 容器，首次安装前建议先清掉旧卷，避免 PostgreSQL 复用历史账号体系：

```bash
docker compose down -v
```

再启动容器：

```bash
docker compose up -d --build
```

默认会启动：

- PostgreSQL
- Redis
- Django Web
- Celery
- 前端构建容器
- Nginx

此时如果还没有安装论坛，`/api/system/status` 会返回 `uninstalled`，这是正常行为。

### 2. 安装论坛

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

安装完成后重启应用进程：

```bash
docker compose restart web celery
```

如果安装时报错：

```text
role "<your user>" does not exist
```

通常说明 PostgreSQL 复用了旧的 `postgres_data` 卷，而不是按当前 `.env` 重新初始化。无数据需要保留时，执行：

```bash
docker compose down -v
docker compose up -d --build
```

然后重新执行 `install_forum`。

### 3. 域名配置

安装时只需要传：

```bash
--site-domains bias.chat,www.bias.chat
```

默认按 `https` 推导。如果站点暂时只跑 HTTP，可加：

```bash
--site-scheme http
```

如果后续只想改域名，可重新执行安装命令并加 `--overwrite`：

```bash
docker compose exec web python manage.py install_forum \
  --database postgres \
  --site-domains bias.chat,www.bias.chat \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password change-me \
  --non-interactive \
  --overwrite

docker compose restart web celery
```

已有密钥、数据库配置、Redis 配置会保留，只会按你传入的参数更新。

### 4. 访问入口

- Forum 前台：`http://localhost:8080`
- 管理后台 SPA：`http://localhost:8080/admin.html`
- API 文档：`http://localhost:8080/api/docs`
- 系统状态：`http://localhost:8080/api/system/status`

### 5. 登录/注册真人验证

如果需要防止机器人批量注册，可在后台 `高级设置` 中开启：

- `验证提供方` 选择 `Cloudflare Turnstile`
- 填写 `Site Key` 和 `Secret Key`
- 勾选要拦截的场景：`登录`、`注册`

开启后，前台登录/注册弹窗会自动显示真人验证组件，服务端也会强制校验 token，仅前端绕不过去。

### 6. Docker 升级

```bash
git pull
docker compose build web celery
docker compose up -d db redis web celery nginx
docker compose restart frontend
docker compose exec web python manage.py upgrade_forum --non-interactive
docker compose restart web celery nginx
```

推荐发布顺序固定为：

```bash
python manage.py prepare_release --set-version 1.0.1
git add VERSION frontend/package.json frontend/package-lock.json
git commit -m "发布 1.0.1"
python manage.py finalize_release --tag v1.0.1
git push origin main --tags
```

`upgrade_forum` 默认会执行：

1. Django 系统检查
2. 数据库迁移
3. 默认用户组与权限同步
4. 写入当前安装版本
5. 运行时缓存清理
6. `collectstatic`

说明：

- `web` / `celery` 挂载的是项目目录，`git pull` 后代码会直接出现在容器里；`docker compose build web celery` 主要用于同步新的 Python 依赖或镜像层变更。
- 前端页面由 `frontend` 容器执行 `npm run build` 产出到 `frontend/dist`，Nginx 直接读取这个目录。
- `docker compose up -d frontend` 对已存在且正在运行的 `frontend` 容器通常不会重新执行构建命令，所以升级后网页可能还是旧版本。
- 因此升级时必须额外执行一次 `docker compose restart frontend`，让它重新跑 `npm install && npm run build`。

如果只更新了前端代码，也至少需要执行：

```bash
git pull
docker compose restart frontend nginx
```

升级前建议备份：

- PostgreSQL 数据库
- `media/`
- `instance/site.json`

## 原生安装

### 1. 准备环境

- Python 3.11+
- Node.js 18+
- 正式部署建议准备 PostgreSQL 15+ 和 Redis 7+

### 2. 安装依赖

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

```bash
pip install -r requirements.txt
```

### 3. 初始化论坛

本地快速启动：

```bash
python manage.py install_forum \
  --database sqlite \
  --admin-username admin \
  --admin-email admin@example.com \
  --admin-password admin123456 \
  --non-interactive
```

正式部署 / 预发布环境：

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

### 4. 前端开发

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

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

`upgrade_forum` 现在会先强制校验：

- `VERSION`
- `frontend/package.json`

如果两者不一致，会直接中止升级，避免出现“代码版本”和“站点版本”错位。

常用参数：

- `--config <path>`：指定站点配置文件，默认 `instance/site.json`
- `--skip-check`：跳过系统检查
- `--skip-migrate`：跳过迁移
- `--skip-init-groups`：跳过默认组同步
- `--skip-clear-cache`：跳过缓存清理
- `--skip-collectstatic`：跳过 `collectstatic`
- `--dry-run`：只输出升级计划，不实际执行
