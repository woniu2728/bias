#!/bin/bash
set -e

# ============================================================
# bias entrypoint - run migrations, collect static, then
# drop privileges to the bias user and run the CMD.
# ============================================================

chown -R 1000:1000 /app/instance /app/media /app/static /app/staticfiles 2>/dev/null || true

cd /app
if [ "${BIAS_SKIP_ENTRYPOINT_MIGRATE:-0}" != "1" ]; then
    gosu bias python manage.py migrate --noinput
fi
if [ "${BIAS_SKIP_ENTRYPOINT_COLLECTSTATIC:-0}" != "1" ]; then
    gosu bias python manage.py collectstatic --noinput
fi

exec gosu bias "$@"
