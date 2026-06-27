#!/bin/bash
# bias-site docker upgrade script
set -e

echo "=== Bias Site Docker Upgrade ==="

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

if ! docker compose ps &> /dev/null; then
    echo "Bias is not running. Use docker-install.sh to install."
    exit 1
fi

# Pull latest images and rebuild
mkdir -p wheels
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
docker compose pull
docker compose down --remove-orphans
docker compose up -d --build
docker compose exec -T web python manage.py upgrade_forum --non-interactive --skip-migrate --skip-collectstatic
docker compose exec -T web python manage.py doctor

echo ""
echo "=== Upgrade Complete ==="
echo "Run 'docker compose logs -f web' to verify startup."
