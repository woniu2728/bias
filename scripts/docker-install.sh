#!/bin/bash
# bias-site docker install script
set -e

echo "=== Bias Site Docker Installation ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

resolve_workspace_root() {
    local candidates=()
    if [ -n "${WORKSPACE_ROOT:-}" ]; then
        candidates+=("$WORKSPACE_ROOT")
    fi
    local windows_pwd
    windows_pwd="$(cmd.exe /c cd 2>/dev/null | tr -d '\r' || true)"
    if [[ "$windows_pwd" =~ ^([A-Za-z]):\\(.*)$ ]]; then
        local drive="${BASH_REMATCH[1],,}"
        local tail="${BASH_REMATCH[2]//\\//}"
        candidates+=("/mnt/$drive/$tail/..")
    fi
    candidates+=("$SITE_DIR/..")

    local candidate
    for candidate in "${candidates[@]}"; do
        [ -n "$candidate" ] || continue
        candidate="$(cd "$candidate" 2>/dev/null && pwd || true)"
        [ -n "$candidate" ] || continue
        if [ -d "$candidate/bias_core" ] && compgen -G "$candidate/bias-ext-*" >/dev/null; then
            echo "$candidate"
            return 0
        fi
    done

    echo "Error: could not locate workspace root containing bias_core and bias-ext-*." >&2
    echo "Set WORKSPACE_ROOT to the parent directory of bias_site and retry." >&2
    return 1
}

WORKSPACE_ROOT="$(resolve_workspace_root)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN=python
    else
        echo "Error: Python is not available."
        exit 1
    fi
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

# Check docker-compose
if ! docker compose version &> /dev/null; then
    echo "Error: docker compose plugin is not available."
    exit 1
fi

# Create instance directory
mkdir -p instance
mkdir -p wheels

# Copy .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || true
    echo "Created .env from .env.example"
fi
$PYTHON_BIN scripts/ensure-secrets.py
set -a
. ./.env
set +a
case "${EMAIL_USE_TLS:-on}" in
    1|true|TRUE|yes|YES|on|ON)
        EMAIL_USE_TLS_OPTION=on
        ;;
    0|false|FALSE|no|NO|off|OFF)
        EMAIL_USE_TLS_OPTION=off
        ;;
    *)
        EMAIL_USE_TLS_OPTION=auto
        ;;
esac

# Build and start
rm -f wheels/*.whl
if $PYTHON_BIN -c "import build" >/dev/null 2>&1; then
    $PYTHON_BIN -m build --wheel --no-isolation "$WORKSPACE_ROOT/bias_core" -o wheels
    for extension_dir in "$WORKSPACE_ROOT"/bias-ext-*; do
        [ -d "$extension_dir" ] || continue
        $PYTHON_BIN -m build --wheel --no-isolation "$extension_dir" -o wheels
    done
else
    docker run --rm -v "$WORKSPACE_ROOT":/workspace -w /workspace python:3.12-slim sh -lc '
        pip install --no-cache-dir build setuptools wheel >/dev/null &&
        python -m build --wheel --no-isolation bias_core -o bias_site/wheels &&
        for extension_dir in bias-ext-*; do
            [ -d "$extension_dir" ] || continue
            python -m build --wheel --no-isolation "$extension_dir" -o bias_site/wheels
        done
    '
fi
docker compose down --remove-orphans
docker compose up -d --build
docker compose exec -T web python manage.py install_forum \
    --non-interactive \
    --overwrite \
    --database postgres \
    --db-name "${DB_NAME:-bias}" \
    --db-user "${DB_USER:-bias}" \
    --db-password "${DB_PASSWORD:-bias}" \
    --db-host db \
    --db-port "${DB_PORT:-5432}" \
    --redis on \
    --redis-host redis \
    --redis-port 6379 \
    --frontend-url "${FRONTEND_URL:-http://localhost:8080}" \
    --site-scheme "${SITE_SCHEME:-http}" \
    --email-backend "${EMAIL_BACKEND:-django.core.mail.backends.smtp.EmailBackend}" \
    --email-host "${EMAIL_HOST:-smtp.example.com}" \
    --email-port "${EMAIL_PORT:-587}" \
    --email-use-tls "$EMAIL_USE_TLS_OPTION" \
    --default-from-email "${DEFAULT_FROM_EMAIL:-noreply@example.com}" \
    --skip-migrate \
    --skip-collectstatic \
    --skip-admin
docker compose exec -T web python manage.py doctor

echo ""
echo "=== Installation Complete ==="
echo "Site will be available at http://localhost:8080 after startup."
echo "Run 'docker compose logs -f web' to follow startup."
