#!/usr/bin/env sh
set -eu

SITE_DOMAINS="${SITE_DOMAINS:-localhost}"
SITE_SCHEME="${SITE_SCHEME:-http}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
OVERWRITE="${OVERWRITE:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"

run_step() {
  label="$1"
  shift
  printf '\n==> %s\n' "$label"
  "$@"
}

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "已从 .env.example 创建 .env，请确认 DB_NAME/DB_USER/DB_PASSWORD 后重新执行。"
    exit 1
  fi
  echo "缺少 .env 文件。" >&2
  exit 1
fi

if [ -z "$ADMIN_PASSWORD" ]; then
  printf "管理员密码: "
  stty -echo
  read ADMIN_PASSWORD
  stty echo
  printf '\n'
fi

if [ "$SKIP_BUILD" = "1" ]; then
  run_step "启动 Docker 服务" docker compose up -d
else
  run_step "构建并启动 Docker 服务" docker compose up -d --build
fi

if [ "$OVERWRITE" = "1" ]; then
run_step "安装 Bias" docker compose exec web python manage.py install_forum \
    --database postgres \
    --site-domains "$SITE_DOMAINS" \
    --site-scheme "$SITE_SCHEME" \
    --admin-username "$ADMIN_USERNAME" \
    --admin-email "$ADMIN_EMAIL" \
    --admin-password "$ADMIN_PASSWORD" \
    --non-interactive \
    --overwrite
else
  run_step "安装 Bias" docker compose exec web python manage.py install_forum \
    --database postgres \
    --site-domains "$SITE_DOMAINS" \
    --site-scheme "$SITE_SCHEME" \
    --admin-username "$ADMIN_USERNAME" \
    --admin-email "$ADMIN_EMAIL" \
    --admin-password "$ADMIN_PASSWORD" \
    --non-interactive
fi
run_step "重启应用进程" docker compose restart web celery
run_step "构建前端资源" docker compose restart frontend
run_step "等待前端构建完成" docker compose up -d --wait frontend
run_step "重启 Nginx" docker compose restart nginx
run_step "运行部署检查" docker compose exec web python manage.py doctor

printf '\nBias 安装完成：http://localhost:8080\n'
