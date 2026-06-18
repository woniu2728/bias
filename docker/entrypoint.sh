#!/bin/bash
set -e

# ============================================================
# bias entrypoint — fix writable directory permissions, then
# drop privileges to the bias user and run the CMD.
# ============================================================

# Fix ownership of directories that the bias user needs to write
# at runtime.  With a host bind mount (:./app) the Dockerfile's
# `chown -R bias:bias /app` is overridden, so directories created
# on the host (or owned by root inside the build context) appear
# as root-owned inside the container.
#
# `|| true` swallows errors from paths that don't exist yet
# (first-run, empty bind mount).
chown -R 1000:1000 /app/instance /app/static/extensions 2>/dev/null || true

# Drop privileges and run the original CMD
exec gosu bias "$@"
