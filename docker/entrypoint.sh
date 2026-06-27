#!/bin/bash
set -e

# ============================================================
# bias-site entrypoint — run migrations, collect static, then
# drop privileges to the bias user and run the CMD.
# ============================================================

chown -R 1000:1000 /app/instance /app/media /app/staticfiles 2>/dev/null || true

cd /app
gosu bias python manage.py migrate --noinput
gosu bias python manage.py collectstatic --noinput

exec gosu bias "$@"
