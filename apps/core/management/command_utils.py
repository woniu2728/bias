from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from django.conf import settings


def build_manage_env(
    extra_env: Mapping[str, str] | None = None,
    *,
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items() if value is not None})
    if config_path is not None:
        env["BIAS_SITE_CONFIG"] = str(config_path)
    if env_path is not None:
        env["BIAS_ENV_FILE"] = str(env_path)
    return env


def run_manage_py(args: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(Path(settings.BASE_DIR) / "manage.py"), *args]
    return subprocess.run(
        command,
        cwd=str(settings.BASE_DIR),
        env=dict(env),
        capture_output=True,
        text=True,
        check=True,
    )
