from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.api_errors import api_error
from apps.core.audit import log_admin_action
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.forum_registry import get_forum_registry
from apps.core.resource_api import (
    ResourceQueryOptions,
    merge_resource_includes,
    parse_resource_query_options,
)
from apps.core.resource_errors import BadJsonApiRequest
from apps.core.resource_registry import ResourceEndpointDefinition
from apps.core.services import PaginationService
from extensions.posts.backend.models import Post
from extensions.posts.backend.schemas import PostCreateSchema, PostUpdateSchema
from extensions.posts.backend.services import PostService


def get_resource_registry():
    return get_runtime_resource_registry()


def get_stream_post_types():
    return get_forum_registry().get_stream_post_type_codes()


def serialize_post(post, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    response = {
        "id": post.id,
        "discussion_id": post.discussion_id,
        "number": post.number,
        "type": post.type,
        "content": post.content,
        "content_html": PostService.resolve_content_html(post),
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "edited_at": post.edited_at,
        "discussion": {
            "id": post.discussion.id,
            "title": post.discussion.title,
            "slug": post.discussion.slug,
        } if getattr(post, "discussion", None) else None,
        "is_hidden": post.is_hidden,
        "approval_status": post.approval_status,
        "approval_note": post.approval_note,
    }
    response.update(
        get_resource_registry().serialize(
            "post",
            post,
            {"user": user},
            only=resource_options.fields,
            include=merge_resource_includes(("user", "edited_user"), default_includes, resource_options.includes),
        )
    )
    return response


def apply_post_resource_preloads(queryset, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    return get_resource_registry().apply_preload_plan(
        queryset,
        "post",
        {"user": user},
        only=resource_options.fields,
        include=merge_resource_includes(("user", "edited_user"), default_includes, resource_options.includes),
    )


def post_resource_endpoints():
    endpoints = []

    def add(definition):
        endpoints.append(definition)

    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="global-index",
            module_id="posts",
            handler=dispatch_post_global_index,
            methods=("GET",),
            path="posts",
            absolute_path=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="create",
            module_id="posts",
            handler=dispatch_post_create,
            methods=("POST",),
            path="discussions/{object_id}/posts",
            absolute_path=True,
            auth_required=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="index",
            module_id="posts",
            handler=dispatch_post_index,
            methods=("GET",),
            path="discussions/{object_id}/posts",
            absolute_path=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="show",
            module_id="posts",
            handler=dispatch_post_show,
            methods=("GET",),
            path="posts/{object_id}",
            absolute_path=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="update",
            module_id="posts",
            handler=dispatch_post_update,
            methods=("PATCH",),
            path="posts/{object_id}",
            absolute_path=True,
            auth_required=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="delete",
            module_id="posts",
            handler=dispatch_post_delete,
            methods=("DELETE",),
            path="posts/{object_id}",
            absolute_path=True,
            auth_required=True,
        )
    )
    add(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="hide",
            module_id="posts",
            handler=dispatch_post_toggle_hide,
            methods=("POST",),
            path="posts/{object_id}/hide",
            absolute_path=True,
            auth_required=True,
        )
    )
    return tuple(endpoints)


def _post_query_value(context, key: str, default=None):
    return dict(context.get("query") or {}).get(key, default)


def _post_payload(context) -> dict:
    payload = context.get("payload")
    return payload if isinstance(payload, dict) else {}


def _post_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


def _post_default_includes(context) -> tuple[str, ...]:
    return tuple(context.get("default_include") or ())


def _post_resource_filters(context) -> dict[str, str]:
    query = context.get("query") if isinstance(context.get("query"), dict) else {}
    filters: dict[str, str] = {}
    for key, value in query.items():
        normalized = str(key or "").strip()
        if normalized == "filter":
            if isinstance(value, dict):
                filters.update(value)
            elif value not in (None, ""):
                filters["q"] = value
            continue
        if normalized.startswith("filter[") and normalized.endswith("]"):
            name = normalized[len("filter[") : -1].strip()
            if name:
                filters[name] = value
    return filters


def dispatch_post_global_index(context):
    user = context.get("user")
    author = _post_query_value(context, "author")
    user_id = _post_query_value(context, "user_id")
    page, limit = PaginationService.normalize(
        _post_query_value(context, "page", 1),
        _post_query_value(context, "limit", 20),
    )
    resource_options = context.get("resource_options") or parse_resource_query_options(context["request"], "post")

    queryset = Post.objects.select_related("discussion").filter(
        type__in=get_stream_post_types(),
    )
    default_includes = _post_default_includes(context)
    queryset = apply_post_resource_preloads(
        queryset,
        user=user,
        resource_options=resource_options,
        default_includes=default_includes,
    )

    queryset = PostService.apply_visibility_filters(queryset, user)

    if author:
        queryset = queryset.filter(user__username=author)

    if user_id:
        queryset = queryset.filter(user_id=user_id)

    resource_registry = get_resource_registry()
    try:
        queryset = resource_registry.apply_resource_filters(
            "post",
            queryset,
            _post_resource_filters(context),
            {"user": user, "query": context.get("query") or {}},
        )
    except BadJsonApiRequest as error:
        return api_error(str(error), status=400)

    sort_context = {"user": user, "author": author, "user_id": user_id}
    if resource_registry.has_named_sort("post", "recent", sort_context):
        queryset = resource_registry.apply_named_sort("post", queryset, "recent", sort_context)
    else:
        queryset = queryset.order_by("-created_at")
    total = queryset.count()
    start = (page - 1) * limit
    end = start + limit
    posts = list(queryset[start:end])

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [
            serialize_post(
                post,
                user,
                resource_options=resource_options,
                default_includes=default_includes,
            )
            for post in posts
        ],
    }


def dispatch_post_create(context):
    discussion_id = _post_object_id(context)
    payload = PostCreateSchema(**_post_payload(context))
    try:
        post = PostService.create_post(
            discussion_id=discussion_id,
            content=payload.content,
            user=context["user"],
            reply_to_post_id=payload.reply_to_post_id,
        )
        return serialize_post(post, context["user"])
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_post_index(context):
    discussion_id = _post_object_id(context)
    user = context.get("user")
    page, limit = PaginationService.normalize(
        _post_query_value(context, "page", 1),
        _post_query_value(context, "limit", 20),
    )
    resource_options = context.get("resource_options") or parse_resource_query_options(context["request"], "post")
    default_includes = _post_default_includes(context)
    try:
        window = PostService.get_post_window(
            discussion_id=discussion_id,
            limit=limit,
            page=page,
            near=_post_query_value(context, "near"),
            before=_post_query_value(context, "before"),
            after=_post_query_value(context, "after"),
            user=user,
            preload=lambda queryset: apply_post_resource_preloads(
                queryset,
                user=user,
                resource_options=resource_options,
                default_includes=default_includes,
            ),
        )
    except ValueError as error:
        return api_error(str(error), status=400)

    return {
        "total": window.total,
        "page": window.page,
        "limit": limit,
        "current_start": window.current_start,
        "current_end": window.current_end,
        "has_previous": window.has_previous,
        "has_more": window.has_more,
        "data": [
            serialize_post(
                post,
                user,
                resource_options=resource_options,
                default_includes=default_includes,
            )
            for post in window.posts
        ],
    }


def dispatch_post_show(context):
    post_id = _post_object_id(context)
    user = context.get("user")
    resource_options = context.get("resource_options") or parse_resource_query_options(context["request"], "post")
    default_includes = _post_default_includes(context)
    post = PostService.get_post_by_id(
        post_id,
        user,
        preload=lambda queryset: apply_post_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
            default_includes=default_includes,
        ),
    )

    if not post:
        return api_error("帖子不存在", status=404)

    return serialize_post(post, user, resource_options=resource_options, default_includes=default_includes)


def dispatch_post_update(context):
    post_id = _post_object_id(context)
    payload = PostUpdateSchema(**_post_payload(context))
    try:
        post = PostService.update_post(
            post_id=post_id,
            user=context["user"],
            content=payload.content,
        )
        return serialize_post(post, context["user"])
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_post_delete(context):
    request = context["request"]
    user = context["user"]
    post_id = _post_object_id(context)
    try:
        post = Post.objects.select_related("discussion", "user").get(id=post_id)
        snapshot = {
            "discussion_id": post.discussion_id,
            "discussion_title": post.discussion.title if post.discussion else "",
            "number": post.number,
            "author_id": post.user_id,
            "deleted_by_owner": post.user_id == user.id,
        }
        PostService.delete_post(post_id, user)
        if user.is_staff or not snapshot["deleted_by_owner"]:
            log_admin_action(
                request,
                "admin.post.delete",
                target_type="post",
                target_id=post_id,
                data=snapshot,
            )
        return {"message": "帖子已删除"}
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def dispatch_post_toggle_hide(context):
    request = context["request"]
    post_id = _post_object_id(context)
    try:
        post = Post.objects.select_related("discussion", "user").get(id=post_id)
        next_hidden = post.hidden_at is None
        PostService.set_hidden_state(post, context["user"], next_hidden)
        post.refresh_from_db()
        log_admin_action(
            request,
            "admin.post.hide" if post.hidden_at else "admin.post.restore",
            target_type="post",
            target_id=post.id,
            data={
                "discussion_id": post.discussion_id,
                "discussion_title": post.discussion.title if post.discussion else "",
                "number": post.number,
                "is_hidden": bool(post.hidden_at),
            },
        )
        return {
            "message": "操作成功",
            "is_hidden": bool(post.hidden_at),
        }
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)

