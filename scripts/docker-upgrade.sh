#!/bin/bash
# bias docker upgrade script
set -e

echo "=== Bias Docker Upgrade ==="

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
        if validate_workspace_root "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done

    echo "Error: could not locate workspace root containing required Bias source packages." >&2
    echo "Required sibling directories: bias_core, bias-content, and at least one bias-ext-*." >&2
    echo "Set WORKSPACE_ROOT to the parent directory of bias and retry." >&2
    if [ "${#candidates[@]}" -gt 0 ]; then
        echo "Checked candidates:" >&2
        for candidate in "${candidates[@]}"; do
            [ -n "$candidate" ] || continue
            candidate="$(cd "$candidate" 2>/dev/null && pwd || true)"
            [ -n "$candidate" ] || continue
            echo "- $candidate" >&2
            validate_workspace_root "$candidate" >&2 || true
        done
    fi
    return 1
}

validate_workspace_root() {
    local candidate="$1"
    local missing=()
    [ -d "$candidate/bias_core" ] || missing+=("bias_core")
    [ -d "$candidate/bias-content" ] || missing+=("bias-content")
    compgen -G "$candidate/bias-ext-*" >/dev/null || missing+=("at least one bias-ext-*")
    if [ "${#missing[@]}" -gt 0 ]; then
        printf 'Missing required package directories:\n'
        local item
        for item in "${missing[@]}"; do
            printf -- '- %s\n' "$item"
        done
        return 1
    fi
    return 0
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
    $PYTHON_BIN -m build --wheel --no-isolation "$WORKSPACE_ROOT/bias-content" -o wheels
    for extension_dir in "$WORKSPACE_ROOT"/bias-ext-*; do
        [ -d "$extension_dir" ] || continue
        $PYTHON_BIN -m build --wheel --no-isolation "$extension_dir" -o wheels
    done
else
    docker run --rm -v "$WORKSPACE_ROOT":/workspace -w /workspace python:3.12-slim sh -lc '
        pip install --no-cache-dir build setuptools wheel >/dev/null &&
        python -m build --wheel --no-isolation bias_core -o bias/wheels &&
        python -m build --wheel --no-isolation bias-content -o bias/wheels &&
        for extension_dir in bias-ext-*; do
            [ -d "$extension_dir" ] || continue
            python -m build --wheel --no-isolation "$extension_dir" -o bias/wheels
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
