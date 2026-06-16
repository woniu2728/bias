from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import (
    get_extension_host_service,
    require_extension_host_service,
    runtime_service_method,
    runtime_service_value,
    RuntimeServiceProxy,
)

# 便捷代理
_tags = RuntimeServiceProxy("tags.service")


def get_runtime_tag_service(default: Any = None):
    return get_extension_host_service("tags.service", default)


def require_runtime_tag_service():
    return require_extension_host_service("tags.service")


def get_runtime_tag_model():
    return runtime_service_value(
        require_runtime_tag_service(),
        "model",
        required_message="tags.service 未提供标签模型",
    )


def get_runtime_discussion_tag_model():
    return runtime_service_value(
        require_runtime_tag_service(),
        "relationship_model",
        required_message="tags.service 未提供讨论标签关系模型",
    )


def get_runtime_tag_summaries_by_slugs(slugs) -> dict[str, dict]:
    service = get_runtime_tag_service()
    if service is None:
        return {}
    return dict(runtime_service_method(service, "summaries_by_slugs")(slugs) or {})


def runtime_tag_method(name: str):
    return runtime_service_method(require_runtime_tag_service(), name)


def get_runtime_tag_scope_label(scope: str) -> str:
    return str(runtime_tag_method("get_scope_label")(scope))


def validate_runtime_tag_parent_assignment(tag: Any, parent: Any) -> None:
    runtime_tag_method("validate_parent_assignment")(tag, parent)


def validate_runtime_tag_scope_configuration(view_scope: str, start_discussion_scope: str, reply_scope: str):
    return runtime_tag_method("validate_scope_configuration")(view_scope, start_discussion_scope, reply_scope)


def create_runtime_tag(**kwargs):
    return runtime_tag_method("create_tag")(**kwargs)


def move_runtime_tag(*, tag_id: int, direction: str, user: Any) -> bool:
    return bool(runtime_tag_method("move_tag")(tag_id, direction, user))


def delete_runtime_tag(tag_id: int, user: Any) -> bool:
    return bool(runtime_tag_method("delete_tag")(tag_id, user))


def dispatch_runtime_tag_stats_refresh(tag_ids=None) -> dict:
    return dict(runtime_tag_method("dispatch_refresh_tag_stats")(tag_ids) or {})


def filter_runtime_tags_for_user(queryset, user: Any, *, action: str = "view"):
    return runtime_tag_method("filter_tags_for_user")(queryset, user, action=action)


def can_runtime_view_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_view_tag")(tag, user))


def can_runtime_start_discussion_in_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_start_discussion_in_tag")(tag, user))


def can_runtime_reply_in_tag(tag: Any, user: Any) -> bool:
    return bool(runtime_tag_method("can_reply_in_tag")(tag, user))


def refresh_runtime_discussion_tag_stats(discussion) -> None:
    runtime_tag_method("refresh_discussion_tag_stats")(discussion)


def refresh_runtime_tag_stats(tag_ids=None) -> None:
    runtime_tag_method("refresh_tag_stats")(tag_ids)


def ensure_can_start_discussion_in_runtime_tags(user: Any, tag_ids) -> list[Any]:
    return list(runtime_tag_method("ensure_can_start_discussion")(user, tag_ids))
