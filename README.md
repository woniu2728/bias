# Bias

Bias 是一个可扩展的论坛系统。`bias` 是站点工程，`bias-core` 提供后端核心能力，`bias-ext-*` 是官方功能扩展，例如用户、讨论、帖子、标签、搜索、通知、上传和实时功能。

本文面向部署和维护站点的用户。

## 前置条件

- Docker 和 Docker Compose
- Python 3.11 或更高版本
- Node.js 和 npm
- Bash 环境（Linux、macOS、WSL 或 Git Bash）

## 首次部署

进入站点目录：

```bash
cd bias
```

准备配置：

```bash
cp .env.example .env
```

编辑 `.env`，至少替换数据库账号密码，并按实际访问地址设置：

```env
DB_NAME=bias
DB_USER=bias
DB_PASSWORD=replace-with-strong-password
FRONTEND_URL=http://localhost:8080
SITE_SCHEME=http
```

如果使用 HTTPS，请把 `FRONTEND_URL` 改成正式域名，并设置：

```env
SITE_SCHEME=https
CSRF_COOKIE_SECURE=1
SESSION_COOKIE_SECURE=1
```

构建前端：

```bash
cd frontend
npm install
npm run build
cd ..
```

启动并初始化：

```bash
bash scripts/docker-install.sh
```

创建管理员账号：

```bash
docker compose exec web python manage.py ensure_admin \
  --username admin \
  --email admin@example.com \
  --password "replace-with-admin-password"
```

访问地址：

- 前台：http://localhost:8080
- 后台：http://localhost:8080/admin.html

## 升级

升级前请先备份数据库、`instance/site.json` 和 `media/`。

```bash
cd bias
cd frontend
npm install
npm run build
cd ..
bash scripts/docker-upgrade.sh
```

升级完成后检查服务：

```bash
docker compose ps
docker compose exec web python manage.py doctor
```

## 安装扩展

官方扩展位于 `bias` 同级目录，名称为 `bias-ext-*`。安装或升级脚本会自动构建这些扩展的 wheel，并在容器镜像中安装。

安装新扩展的推荐流程：

1. 将扩展目录放到 `bias` 同级目录，目录名形如 `bias-ext-example`。
2. 重新构建前端。
3. 执行升级脚本。

```bash
cd bias/frontend
npm run build
cd ..
bash scripts/docker-upgrade.sh
```

同步并检查已安装扩展：

```bash
docker compose exec web python manage.py sync_extensions
docker compose exec web python manage.py inspect_extensions
```

启用或停用扩展：

```bash
docker compose exec web python manage.py extension_enable tags
docker compose exec web python manage.py extension_disable tags
```

后台也可以在“扩展”页面查看扩展状态和配置项。

## 常用命令

```bash
docker compose ps
docker compose logs -f web
docker compose restart web nginx
docker compose exec web python manage.py doctor
```

如启用了队列服务：

```bash
docker compose --profile queue up -d celery
docker compose logs -f celery
```

如需清空本地测试环境并重新安装：

```bash
docker compose down -v
bash scripts/docker-install.sh
```
