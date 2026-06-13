#!/usr/bin/env sh
set -eu

SKIP_PULL="${SKIP_PULL:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_DOCTOR="${SKIP_DOCTOR:-0}"

run_step() {
  label="$1"
  shift
  printf '\n==> %s\n' "$label"
  "$@"
}

if [ ! -f ".env" ]; then
  echo "缺少 .env 文件，请先复制 .env.example 并填写数据库配置。" >&2
  exit 1
fi

if [ "$SKIP_PULL" != "1" ]; then
  run_step "拉取最新代码" git pull --ff-only
fi

if [ "$SKIP_BUILD" != "1" ]; then
  run_step "构建后端镜像" docker compose build web celery
fi

run_step "启动基础服务" docker compose up -d db redis web celery nginx
run_step "执行 Bias 升级" docker compose exec web python manage.py upgrade_forum --non-interactive
run_step "重新构建前端资源" docker compose restart frontend
run_step "等待前端构建完成" docker compose up -d --wait frontend
run_step "重启应用进程" docker compose restart web celery nginx

if [ "$SKIP_DOCTOR" != "1" ]; then
  run_step "运行部署检查" docker compose exec web python manage.py doctor
fi

printf '\nBias 升级完成：http://localhost:8080\n'
