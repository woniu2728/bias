# Bias

Bias 是一个使用 Django + Vue 3 构建的论坛项目，目标是提供扩展优先的现代论坛体验和后台管理能力。

## 技术栈

- 后端：Django 5、Django Ninja、Channels、Celery
- 前端：Vue 3、Vue Router、Pinia、Vite
- 数据库：PostgreSQL
- 缓存与队列：Redis
- 部署方式：Docker Compose

## Docker 安装

### 1. 准备配置

```bash
git clone <your-repo-url>
cd bias
cp .env.example .env
```

至少填写 `.env` 中的数据库配置：

```env
DB_NAME=your_bias_db
DB_USER=your_bias_user
DB_PASSWORD=your_strong_password
```

如果这台机器之前运行过同名 Bias 容器，首次安装前建议先清理旧卷，避免 PostgreSQL 复用历史账号：

```bash
docker compose down -v
```

### 2. 一键安装

Windows / PowerShell:

```powershell
.\scripts\docker-install.ps1 `
  -SiteDomains "bias.chat,www.bias.chat" `
  -SiteScheme "https" `
  -AdminUsername "admin" `
  -AdminEmail "admin@example.com"
```

Linux / macOS:

```bash
SITE_DOMAINS="bias.chat,www.bias.chat" \
SITE_SCHEME="https" \
ADMIN_USERNAME="admin" \
ADMIN_EMAIL="admin@example.com" \
sh scripts/docker-install.sh
```

脚本会依次完成：

- 构建并启动 Docker 服务
- 执行 `install_forum`
- 同步扩展、迁移数据库、生成扩展前端 manifest
- 重启 web、celery、frontend、nginx
- 执行 `doctor` 部署检查

默认访问入口：

- Forum 前台：`http://localhost:8080`
- 管理后台：`http://localhost:8080/admin.html`
- API 文档：`http://localhost:8080/api/docs`
- 系统状态：`http://localhost:8080/api/system/status`

## Docker 升级

Windows / PowerShell:

```powershell
.\scripts\docker-upgrade.ps1
```

Linux / macOS:

```bash
sh scripts/docker-upgrade.sh
```

升级脚本会依次完成：

- `git pull --ff-only`
- 构建后端镜像
- 启动基础服务
- 执行 `upgrade_forum --non-interactive`
- 重启 frontend 触发 Vite 构建
- 重启 web、celery、nginx
- 执行 `doctor` 部署检查

可选跳过项：

PowerShell:

```powershell
.\scripts\docker-upgrade.ps1 -SkipPull -SkipBuild -SkipDoctor
```

Shell:

```bash
SKIP_PULL=1 SKIP_BUILD=1 SKIP_DOCTOR=1 sh scripts/docker-upgrade.sh
```

## 部署检查

任何时候都可以执行：

```bash
docker compose exec web python manage.py doctor
```

JSON 输出：

```bash
docker compose exec web python manage.py doctor --format json
```

`doctor` 会检查：

- 安装版本是否与代码版本一致
- 数据库连接是否正常
- Django 迁移是否已完成
- 扩展包是否缺失或版本漂移
- 前端 dist 是否存在
- 扩展前端 manifest 是否存在且未过期
- 缓存是否可读写

## 版本发布

版本只认这 3 个来源：

- `VERSION`
- `frontend/package.json`
- Git tag，格式 `vX.Y.Z`

发布前同步版本：

```bash
python manage.py prepare_release --set-version 1.0.1
```

创建发布 tag：

```bash
python manage.py finalize_release --tag v1.0.1
git push origin main --tags
```

一条命令完成版本同步、提交、打 tag：

```bash
python manage.py publish_release --set-version 1.0.1
```

如果需要连 push 一起执行：

```bash
python manage.py publish_release --set-version 1.0.1 --push
```

## CI

GitHub Actions 会执行：

- `VERSION` 与 `frontend/package.json` 一致性检查
- 后端关键 `flake8`
- `pytest`
- `python manage.py test`
- `npm run build`

当 push `vX.Y.Z` tag 时，`.github/workflows/release.yml` 会自动创建 GitHub Release。

## 常见故障

### PostgreSQL 提示 role 不存在

如果安装时报：

```text
role "<your user>" does not exist
```

通常是旧的 `postgres_data` 卷仍在使用旧账号。无数据需要保留时执行：

```bash
docker compose down -v
docker compose up -d --build
```

然后重新运行安装脚本。

### 页面仍是旧版本

前端页面由 `frontend` 容器执行 `npm run build` 生成到 `frontend/dist`。如果升级后页面仍旧，执行：

```bash
docker compose restart frontend nginx
docker compose exec web python manage.py doctor
```

### 只改域名

重新运行安装脚本并允许覆盖配置。

PowerShell:

```powershell
.\scripts\docker-install.ps1 -SiteDomains "bias.chat,www.bias.chat" -SiteScheme "https" -Overwrite
```

Shell:

```bash
SITE_DOMAINS="bias.chat,www.bias.chat" SITE_SCHEME="https" OVERWRITE=1 sh scripts/docker-install.sh
```

已有密钥、数据库配置、Redis 配置会保留。
