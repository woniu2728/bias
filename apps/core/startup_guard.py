from __future__ import annotations

import os

from django.core.checks import Critical, run_checks
from django.core.exceptions import ImproperlyConfigured


def enforce_production_runtime_checks() -> None:
    from apps.core.runtime_checks import PRODUCTION_RUNTIME_CHECK_TAG, is_production_runtime

    if not is_production_runtime():
        return

    messages = run_checks(tags=[PRODUCTION_RUNTIME_CHECK_TAG])
    criticals = [message for message in messages if isinstance(message, Critical)]
    if os.getenv("BIAS_INSTALLING") == "1":
        criticals = [
            message
            for message in criticals
            if message.id != "bias.email-backend-development-production"
        ]
    if not criticals:
        return

    lines = ["Bias 生产启动自检失败，已拒绝启动："]
    for message in criticals:
        entry = f"- [{message.id}] {message.msg}"
        if message.hint:
            entry += f" 建议：{message.hint}"
        lines.append(entry)

    raise ImproperlyConfigured("\n".join(lines))
