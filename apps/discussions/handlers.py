from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.forum_resources import serialize_user_summary
from apps.core.resource_api import ResourceQueryOptions, merge_resource_includes, parse_resource_query_options
from apps.core.resource_registry import ResourceEndpointDefinition
from apps.core.services import PaginationService
from apps.discussions.models import Discussion
from apps.discussions.schemas import (
    DiscussionCreateSchema,
    DiscussionOutSchema,
    DiscussionReadStateSchema,
    DiscussionUpdateSchema,
)
from apps.discussions.services import DiscussionService
from apps.posts.models import Post


def get_resource_registry():
    return get_runtime_resource_registry()


def serialize_discussion_payload(discussion, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    payload = DiscussionOutSchema.from_orm(discussion).dict()
    payload.update(
        get_resource_registry().serialize(
            "discussion",
            discussion,
            {"user": user},
            only=resource_options.fields,
            include=merge_resource_includes(
                ("user", "last_posted_user"),
                default_includes,
                resource_options.includes,
            ),
        )
    )
    return payload


def apply_discussion_resource_preloads(queryset, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    return get_resource_registry().apply_preload_plan(
        queryset,
        "discussion",
        {"user": user},
        only=resource_options.fields,
        include=merge_resource_includes(
            ("user", "last_posted_user"),
            default_includes,
            resource_options.includes,
        ),
    )


def serialize_discussion_sort(definition):
    return {
        "code": definition.code,
        "label": definition.label,
        "module_id": definition.module_id,
        "description": definition.description,
        "icon": definition.icon,
        "is_default": definition.is_default,
        "toolbar_visible": definition.toolbar_visible,
    }


def serialize_discussion_list_filter(definition):
    return {
        "code": definition.code,
        "label": definition.label,
        "module_id": definition.module_id,
        "description": definition.description,
        "icon": definition.icon,
        "is_default": definition.is_default,
        "requires_authenticated_user": definition.requires_authenticated_user,
        "sidebar_visible": definition.sidebar_visible,
        "route_path": definition.route_path,
    }


def register_discussion_core_resource_endpoints(registry=None):
    registry = registry or get_resource_registry()
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="create",
            module_id="core",
            handler=dispatch_discussion_create,
            methods=("POST",),
            path="discussions/",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="index",
            module_id="core",
            handler=dispatch_discussion_index,
            methods=("GET",),
            path="discussions/",
            absolute_path=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="read-all",
            module_id="core",
            handler=dispatch_discussion_mark_all_read,
            methods=("POST",),
            path="discussions/read-all",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="read",
            module_id="core",
            handler=dispatch_discussion_update_read_state,
            methods=("POST",),
            path="discussions/{object_id}/read",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="show",
            module_id="core",
            handler=dispatch_discussion_show,
            methods=("GET",),
            path="discussions/{object_id}",
            absolute_path=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="update",
            module_id="core",
            handler=dispatch_discussion_update,
            methods=("PATCH",),
            path="discussions/{object_id}",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="delete",
            module_id="core",
            handler=dispatch_discussion_delete,
            methods=("DELETE",),
            path="discussions/{object_id}",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="pin",
            module_id="core",
            handler=dispatch_discussion_toggle_pin,
            methods=("POST",),
            path="discussions/{object_id}/pin",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="lock",
            module_id="core",
            handler=dispatch_discussion_toggle_lock,
            methods=("POST",),
            path="discussions/{object_id}/lock",
            absolute_path=True,
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="hide",
            module_id="core",
            handler=dispatch_discussion_toggle_hide,
            methods=("POST",),
            path="discussions/{object_id}/hide",
            absolute_path=True,
            auth_required=True,
        )
    )


def _discussion_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


def _discussion_default_includes(context) -> tuple[str, ...]:
    return tuple(context.get("default_include") or ())


def _discussion_payload(context) -> dict:
    payload = context.get("payload")
    return payload if isinstance(payload, dict) else {}


def _discussion_attributes(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and isinstance(data.get("attributes"), dict):
        return dict(data["attributes"])
    return dict(payload or {})


def _discussion_query_value(context, key: str, default=None):
    return dict(context.get("query") or {}).get(key, default)


def dispatch_discussion_create(context):
    raw_payload = _discussion_payload(context)
    payload = DiscussionCreateSchema(**_discussion_attributes(raw_payload))
    try:
        discussion = DiscussionService.create_discussion(
            title=payload.title,
            content=payload.content,
            user=context["user"],
            extension_payload=raw_payload,
        )
        return serialize_discussion_payload(
            discussion,
            user=context["user"],
            resource_options=context.get("resource_options"),
            default_includes=_discussion_default_includes(context),
        )
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_discussion_index(context):
    request = context["request"]
    user = context.get("user")
    q = _discussion_query_value(context, "q")
    tag = _discussion_query_value(context, "tag")
    author = _discussion_query_value(context, "author")
    filter_code = _discussion_query_value(context, "filter", "all")
    sort = _discussion_query_value(context, "sort", "latest")
    page, limit = PaginationService.normalize(
        _discussion_query_value(context, "page", 1),
        _discussion_query_value(context, "limit", 20),
    )
    resource_options = context.get("resource_options") or parse_resource_query_options(request, "discussion")
    default_includes = _discussion_default_includes(context)

    discussions, total = DiscussionService.get_discussion_list(
        q=q,
        tag=tag,
        author=author,
        list_filter=filter_code,
        sort=sort,
        page=page,
        limit=limit,
        user=user,
        preload=lambda queryset: apply_discussion_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
            default_includes=default_includes,
        ),
    )
    active_filter = DiscussionService.normalize_discussion_list_filter(filter_code)
    active_sort = DiscussionService.normalize_discussion_sort(sort)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "filter": active_filter,
        "available_filters": [
            serialize_discussion_list_filter(item)
            for item in DiscussionService.get_discussion_list_filter_catalog()
        ],
        "sort": active_sort,
        "available_sorts": [
            serialize_discussion_sort(item)
            for item in DiscussionService.get_discussion_sort_catalog()
        ],
        "data": [
            serialize_discussion_payload(
                discussion,
                user=user,
                resource_options=resource_options,
                default_includes=default_includes,
            )
            for discussion in discussions
        ],
    }


def dispatch_discussion_show(context):
    request = context["request"]
    user = context.get("user")
    try:
        discussion_id = int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return api_error("讨论不存在", status=404)

    resource_options = context.get("resource_options") or parse_resource_query_options(request, "discussion")
    default_includes = _discussion_default_includes(context)
    discussion = DiscussionService.get_discussion_by_id(
        discussion_id,
        user,
        preload=lambda queryset: apply_discussion_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
            default_includes=default_includes,
        ),
    )
    if not discussion:
        return api_error("讨论不存在", status=404)

    first_post = None
    if discussion.first_post_id:
        try:
            post = Post.objects.select_related("user").get(id=discussion.first_post_id)
            first_post = {
                "id": post.id,
                "number": post.number,
                "content": post.content,
                "content_html": post.content_html,
                "user": serialize_user_summary(post.user),
                "created_at": post.created_at,
                "updated_at": post.updated_at,
                "approval_status": post.approval_status,
                "approval_note": post.approval_note,
            }
        except Post.DoesNotExist:
            pass

    response_data = serialize_discussion_payload(
        discussion,
        user=user,
        resource_options=resource_options,
        default_includes=default_includes,
    )
    response_data["first_post"] = first_post
    return response_data


def dispatch_discussion_mark_all_read(context):
    marked_at = DiscussionService.mark_all_as_read(context["user"])
    return {
        "message": "已全部标记为已读",
        "marked_all_as_read_at": marked_at,
    }


def dispatch_discussion_update_read_state(context):
    discussion_id = _discussion_object_id(context)
    payload = DiscussionReadStateSchema(**_discussion_payload(context))
    try:
        state = DiscussionService.update_read_state(
            discussion_id=discussion_id,
            user=context["user"],
            last_read_post_number=payload.last_read_post_number,
        )
        return {
            "message": "阅读状态已更新",
            "last_read_at": state.last_read_at,
            "last_read_post_number": state.last_read_post_number,
        }
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


def dispatch_discussion_update(context):
    discussion_id = _discussion_object_id(context)
    raw_payload = _discussion_payload(context)
    payload = DiscussionUpdateSchema(**_discussion_attributes(raw_payload))
    try:
        discussion = DiscussionService.update_discussion(
            discussion_id=discussion_id,
            user=context["user"],
            title=payload.title,
            content=payload.content,
            extension_payload=raw_payload,
            is_locked=payload.is_locked,
            is_sticky=payload.is_sticky,
            is_hidden=payload.is_hidden,
        )
        return serialize_discussion_payload(
            discussion,
            user=context["user"],
            resource_options=context.get("resource_options"),
            default_includes=_discussion_default_includes(context),
        )
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_discussion_delete(context):
    request = context["request"]
    user = context["user"]
    discussion_id = _discussion_object_id(context)
    try:
        discussion = Discussion.objects.select_related("user").get(id=discussion_id)
        snapshot = {
            "title": discussion.title,
            "author_id": discussion.user_id,
            "deleted_by_owner": discussion.user_id == user.id,
        }
        DiscussionService.delete_discussion(discussion_id, user)
        if user.is_staff or not snapshot["deleted_by_owner"]:
            log_admin_action(
                request,
                "admin.discussion.delete",
                target_type="discussion",
                target_id=discussion_id,
                data=snapshot,
            )
        return {"message": "讨论已删除"}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


def dispatch_discussion_toggle_pin(context):
    request = context["request"]
    user = context["user"]
    discussion_id = _discussion_object_id(context)
    if not user.is_staff:
        return api_error("需要管理员权限", status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        DiscussionService.set_sticky_state(discussion, user, not discussion.is_sticky)
        discussion.refresh_from_db()
        log_admin_action(
            request,
            "admin.discussion.sticky" if discussion.is_sticky else "admin.discussion.unsticky",
            target_type="discussion",
            target_id=discussion.id,
            data={"title": discussion.title, "is_sticky": discussion.is_sticky},
        )
        return {"message": "操作成功", "is_sticky": discussion.is_sticky}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)


def dispatch_discussion_toggle_lock(context):
    request = context["request"]
    user = context["user"]
    discussion_id = _discussion_object_id(context)
    if not user.is_staff:
        return api_error("需要管理员权限", status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        DiscussionService.set_locked_state(discussion, user, not discussion.is_locked)
        discussion.refresh_from_db()
        log_admin_action(
            request,
            "admin.discussion.lock" if discussion.is_locked else "admin.discussion.unlock",
            target_type="discussion",
            target_id=discussion.id,
            data={"title": discussion.title, "is_locked": discussion.is_locked},
        )
        return {"message": "操作成功", "is_locked": discussion.is_locked}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)


def dispatch_discussion_toggle_hide(context):
    request = context["request"]
    user = context["user"]
    discussion_id = _discussion_object_id(context)
    if not user.is_staff:
        return api_error("需要管理员权限", status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        next_hidden = not discussion.is_hidden
        DiscussionService.set_hidden_state(discussion, user, next_hidden)
        discussion.refresh_from_db()
        log_admin_action(
            request,
            "admin.discussion.hide" if discussion.is_hidden else "admin.discussion.restore",
            target_type="discussion",
            target_id=discussion.id,
            data={"title": discussion.title, "is_hidden": discussion.is_hidden},
        )
        return {"message": "操作成功", "is_hidden": discussion.is_hidden}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
