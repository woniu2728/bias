from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    RuntimeServiceProxy,
    get_extension_host_service,
    require_extension_host_service,
)

_tag = RuntimeServiceProxy("tags.service")


def get_runtime_tag_service(default: Any = None):
    return get_extension_host_service("tags.service", default)


def require_runtime_tag_service():
    return require_extension_host_service("tags.service")


def get_runtime_tag_model():
    return _tag.value("model", required_message="tags.service 未提供标签模型")


def get_runtime_discussion_tag_model():
    return _tag.value("relationship_model", required_message="tags.service 未提供讨论标签关系模型")


def get_runtime_tag_summaries_by_slugs(slugs) -> dict[str, dict]:
    service = get_runtime_tag_service()
    if service is None:
        return {}
    from apps.core.extensions.runtime_core import runtime_service_method
    return dict(runtime_service_method(service, "summaries_by_slugs")(slugs) or {})


def get_runtime_tag_scope_label(scope: str) -> str:
    return str(_tag.get_scope_label(scope))


def validate_runtime_tag_parent_assignment(tag: Any, parent: Any) -> None:
    _tag.validate_parent_assignment(tag, parent)


def validate_runtime_tag_scope_configuration(view_scope: str, start_discussion_scope: str, reply_scope: str):
    return _tag.validate_scope_configuration(view_scope, start_discussion_scope, reply_scope)


def create_runtime_tag(**kwargs):
    return _tag.create_tag(**kwargs)


def move_runtime_tag(*, tag_id: int, direction: str, user: Any) -> bool:
    return bool(_tag.move_tag(tag_id, direction, user))


def delete_runtime_tag(tag_id: int, user: Any) -> bool:
    return bool(_tag.delete_tag(tag_id, user))


def dispatch_runtime_tag_stats_refresh(tag_ids=None) -> dict:
    return dict(_tag.dispatch_refresh_tag_stats(tag_ids) or {})


def filter_runtime_tags_for_user(queryset, user: Any, *, action: str = "view"):
    return _tag.filter_tags_for_user(queryset, user, action=action)


def can_runtime_view_tag(tag: Any, user: Any) -> bool:
    return bool(_tag.can_view_tag(tag, user))


def can_runtime_start_discussion_in_tag(tag: Any, user: Any) -> bool:
    return bool(_tag.can_start_discussion_in_tag(tag, user))


def can_runtime_reply_in_tag(tag: Any, user: Any) -> bool:
    return bool(_tag.can_reply_in_tag(tag, user))


def refresh_runtime_discussion_tag_stats(discussion) -> None:
    _tag.refresh_discussion_tag_stats(discussion)


def refresh_runtime_tag_stats(tag_ids=None) -> None:
    _tag.refresh_tag_stats(tag_ids)


def ensure_can_start_discussion_in_runtime_tags(user: Any, tag_ids) -> list[Any]:
    return list(_tag.ensure_can_start_discussion(user, tag_ids))


# 向后兼容：旧版 runtime_tag_method 动态方法解析
from apps.core.extensions.runtime_core import runtime_service_method as _runtime_service_method

def runtime_tag_method(name: str):
    return _runtime_service_method(require_runtime_tag_service(), name)
