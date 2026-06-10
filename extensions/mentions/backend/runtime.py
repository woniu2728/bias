from __future__ import annotations

from apps.core.extensions.runtime_access import require_extension_host_service


def mention_service_provider() -> dict:
    from extensions.mentions.backend.models import PostMentionsUser

    return {
        "model": PostMentionsUser,
    }


def get_post_mention_model():
    service = require_extension_host_service("mentions.service")
    model = service.get("model") if isinstance(service, dict) else getattr(service, "model", None)
    if model is None:
        raise RuntimeError("mentions.service 未提供提及关系模型")
    return model

