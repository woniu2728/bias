"""
帖子系统API端点
"""
from typing import Optional
from ninja import Router
from django.db.models import Count
from django.core.exceptions import PermissionDenied

from apps.posts.models import Post, PostLike
from apps.posts.schemas import (
    PostCreateSchema,
    PostUpdateSchema,
    PostOutSchema,
)
from apps.posts.services import PostService
from apps.core.audit import log_admin_action
from apps.core.auth import AuthBearer
from apps.core.forum_registry import get_forum_registry
from apps.core.resource_api import (
    ResourceQueryOptions,
    merge_resource_includes,
    parse_resource_query_options,
)
from apps.core.extensions.runtime_access import get_runtime_resource_registry
from apps.core.resource_dispatcher import dispatch_resource_endpoint
from apps.core.resource_registry import ResourceEndpointDefinition
from apps.core.services import PaginationService
from apps.core.api_errors import api_error

router = Router()


def _get_resource_registry():
    return get_runtime_resource_registry()


def _get_stream_post_types():
    return get_forum_registry().get_stream_post_type_codes()


def _serialize_post(post, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    response = {
        "id": post.id,
        "discussion_id": post.discussion_id,
        "number": post.number,
        "type": post.type,
        "content": post.content,
        "content_html": post.content_html,
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
        "like_count": getattr(post, "like_count", 0),
        "is_liked": getattr(post, "is_liked", False),
    }
    response.update(
        _get_resource_registry().serialize(
            "post",
            post,
            {"user": user},
            only=resource_options.fields,
            include=merge_resource_includes(("user", "edited_user"), default_includes, resource_options.includes),
        )
    )
    return response


def _apply_post_resource_preloads(queryset, user=None, resource_options=None, default_includes=()):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().apply_preload_plan(
        queryset,
        "post",
        {"user": user},
        only=resource_options.fields,
        include=merge_resource_includes(("user", "edited_user"), default_includes, resource_options.includes),
    )


def _register_post_core_resource_endpoints():
    registry = _get_resource_registry()
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="global-index",
            module_id="core",
            handler=_dispatch_post_global_index,
            methods=("GET",),
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="create",
            module_id="core",
            handler=_dispatch_post_create,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="index",
            module_id="core",
            handler=_dispatch_post_index,
            methods=("GET",),
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="show",
            module_id="core",
            handler=_dispatch_post_show,
            methods=("GET",),
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="update",
            module_id="core",
            handler=_dispatch_post_update,
            methods=("PATCH",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="delete",
            module_id="core",
            handler=_dispatch_post_delete,
            methods=("DELETE",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="post",
            endpoint="hide",
            module_id="core",
            handler=_dispatch_post_toggle_hide,
            methods=("POST",),
            auth_required=True,
        )
    )
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


def _dispatch_post_global_index(context):
    user = context.get("user")
    author = _post_query_value(context, "author")
    user_id = _post_query_value(context, "user_id")
    page, limit = PaginationService.normalize(
        _post_query_value(context, "page", 1),
        _post_query_value(context, "limit", 20),
    )
    resource_options = context.get("resource_options") or parse_resource_query_options(context["request"], "post")

    queryset = Post.objects.select_related(
        "discussion",
    ).annotate(
        like_count=Count("likes", distinct=True)
    ).filter(
        type__in=_get_stream_post_types(),
    )
    default_includes = _post_default_includes(context)
    queryset = _apply_post_resource_preloads(
        queryset,
        user=user,
        resource_options=resource_options,
        default_includes=default_includes,
    )

    queryset = PostService.apply_visibility_filters(queryset, user)
    queryset = PostService.annotate_flag_state(queryset, user)

    if author:
        queryset = queryset.filter(user__username=author)

    if user_id:
        queryset = queryset.filter(user_id=user_id)

    sort_context = {"user": user, "author": author, "user_id": user_id}
    resource_registry = _get_resource_registry()
    if resource_registry.has_named_sort("post", "recent", sort_context):
        queryset = resource_registry.apply_named_sort("post", queryset, "recent", sort_context)
    else:
        queryset = queryset.order_by("-created_at")
    total = queryset.count()
    start = (page - 1) * limit
    end = start + limit
    posts = list(queryset[start:end])

    if user:
        liked_post_ids = set(
            PostLike.objects.filter(
                post_id__in=[post.id for post in posts],
                user=user,
            ).values_list("post_id", flat=True)
        )
        for post in posts:
            post.is_liked = post.id in liked_post_ids

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [
            _serialize_post(
                post,
                user,
                resource_options=resource_options,
                default_includes=default_includes,
            )
            for post in posts
        ],
    }


def _dispatch_post_create(context):
    discussion_id = _post_object_id(context)
    payload = PostCreateSchema(**_post_payload(context))
    try:
        post = PostService.create_post(
            discussion_id=discussion_id,
            content=payload.content,
            user=context["user"],
            reply_to_post_id=payload.reply_to_post_id,
        )
        post.like_count = 0
        post.is_liked = False
        return _serialize_post(post, context["user"])
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def _dispatch_post_index(context):
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
            preload=lambda queryset: _apply_post_resource_preloads(
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
            _serialize_post(
                post,
                user,
                resource_options=resource_options,
                default_includes=default_includes,
            )
            for post in window.posts
        ],
    }


def _dispatch_post_show(context):
    post_id = _post_object_id(context)
    user = context.get("user")
    resource_options = context.get("resource_options") or parse_resource_query_options(context["request"], "post")
    default_includes = _post_default_includes(context)
    post = PostService.get_post_by_id(
        post_id,
        user,
        preload=lambda queryset: _apply_post_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
            default_includes=default_includes,
        ),
    )

    if not post:
        return api_error("帖子不存在", status=404)

    return _serialize_post(post, user, resource_options=resource_options, default_includes=default_includes)


def _dispatch_post_update(context):
    post_id = _post_object_id(context)
    payload = PostUpdateSchema(**_post_payload(context))
    try:
        post = PostService.update_post(
            post_id=post_id,
            user=context["user"],
            content=payload.content,
        )
        post = PostService.get_post_by_id(post.id, context["user"])
        return _serialize_post(post, context["user"])
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def _dispatch_post_delete(context):
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


def _dispatch_post_toggle_hide(context):
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


def _dispatch_post_like(context):
    post_id = _post_object_id(context)
    try:
        PostService.like_post(post_id, context["user"])
        return {"message": "点赞成功"}
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def _dispatch_post_unlike(context):
    post_id = _post_object_id(context)
    try:
        PostService.unlike_post(post_id, context["user"])
        return {"message": "取消点赞成功"}
    except Post.DoesNotExist:
        return api_error("帖子不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


@router.get("/posts", tags=["Posts"])
def list_all_posts(
    request,
    author: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
):
    """
    获取全站帖子列表

    参数:
    - author: 作者用户名
    - user_id: 作者ID
    - page: 页码
    - limit: 每页数量
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(request, resource="post", endpoint="global-index")


@router.post("/discussions/{discussion_id}/posts", response=PostOutSchema, auth=AuthBearer(), tags=["Posts"])
def create_post(request, discussion_id: int, payload: PostCreateSchema):
    """
    创建帖子（回复讨论）

    需要认证
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(discussion_id),
        endpoint="create",
    )


@router.get("/discussions/{discussion_id}/posts", tags=["Posts"])
def list_posts(
    request,
    discussion_id: int,
    page: int = 1,
    limit: int = 20,
    near: Optional[int] = None,
    before: Optional[int] = None,
    after: Optional[int] = None,
):
    """
    获取帖子列表

    参数:
    - page: 页码
    - limit: 每页数量
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(discussion_id),
        endpoint="index",
    )


@router.get("/posts/{post_id}", tags=["Posts"])
def get_post(request, post_id: int):
    """
    获取帖子详情
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="show",
    )


@router.patch("/posts/{post_id}", response=PostOutSchema, auth=AuthBearer(), tags=["Posts"])
def update_post(request, post_id: int, payload: PostUpdateSchema):
    """
    更新帖子

    需要认证和权限
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="update",
    )


@router.delete("/posts/{post_id}", auth=AuthBearer(), tags=["Posts"])
def delete_post(request, post_id: int):
    """
    删除帖子

    需要认证和权限
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="delete",
    )


@router.post("/posts/{post_id}/hide", auth=AuthBearer(), tags=["Posts"])
def toggle_hide_post(request, post_id: int):
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="hide",
    )


@router.post("/posts/{post_id}/like", auth=AuthBearer(), tags=["Posts"])
def like_post(request, post_id: int):
    """
    点赞帖子

    需要认证
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="like",
    )


@router.delete("/posts/{post_id}/like", auth=AuthBearer(), tags=["Posts"])
def unlike_post(request, post_id: int):
    """
    取消点赞

    需要认证
    """
    _register_post_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="post",
        object_id=str(post_id),
        endpoint="like",
    )
