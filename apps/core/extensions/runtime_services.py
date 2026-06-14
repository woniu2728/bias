from __future__ import annotations

from typing import Any

from apps.core.extensions.runtime_core import get_extension_host_service, require_extension_host_service, runtime_service_method


def get_runtime_locale_service():
    return get_extension_host_service("locales")


def get_runtime_formatter_service():
    return get_extension_host_service("formatters")


def get_runtime_view_service():
    return get_extension_host_service("views")


def render_runtime_template(template_name: str, context: dict | None = None, *, request: Any = None) -> str:
    service = get_runtime_view_service()
    if service is None:
        raise RuntimeError("扩展视图服务尚未启动")
    return service.render(template_name, context or {}, request=request)


def get_runtime_discussion_lifecycle_service():
    return get_extension_host_service("discussion.lifecycle")


def get_runtime_post_lifecycle_service():
    return get_extension_host_service("post.lifecycle")


def get_runtime_post_event_data_service():
    return get_extension_host_service("post.events")


def get_runtime_timeline_service():
    return require_extension_host_service("discussions.timeline")


def create_runtime_timeline_from_builder(
    event: Any,
    builder: str,
    *,
    extra: dict | None = None,
    update_discussion_last_post: bool = True,
):
    return runtime_service_method(get_runtime_timeline_service(), "create_from_builder")(
        event,
        builder,
        extra=dict(extra or {}),
        update_discussion_last_post=update_discussion_last_post,
    )


def broadcast_runtime_discussion_event(
    discussion_id: int,
    event_type: str,
    *,
    include_discussion: bool = False,
    include_post: bool = False,
    post_id: int | None = None,
    post_id_getter=None,
    extension_context: dict | None = None,
) -> None:
    broadcaster = get_extension_host_service("realtime.discussion_broadcaster")
    if not callable(broadcaster):
        raise RuntimeError("扩展运行时服务未注册: realtime.discussion_broadcaster")
    return broadcaster(
        discussion_id,
        event_type,
        include_discussion=include_discussion,
        include_post=include_post,
        post_id=post_id,
        post_id_getter=post_id_getter,
        extension_context=extension_context,
    )
