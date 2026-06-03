"""
讨论系统API端点
"""
from typing import Optional
from ninja import Body, Router
from django.core.exceptions import PermissionDenied

from apps.discussions.models import Discussion
from apps.discussions.schemas import (
    DiscussionCreateSchema,
    DiscussionUpdateSchema,
    DiscussionReadStateSchema,
    DiscussionOutSchema,
)
from apps.discussions.services import DiscussionService
from apps.posts.models import Post
from apps.core.audit import log_admin_action
from apps.core.auth import AuthBearer
from apps.core.forum_resources import serialize_user_summary
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


def _serialize_discussion_payload(discussion, user=None, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    payload = DiscussionOutSchema.from_orm(discussion).dict()
    payload.update(
        _get_resource_registry().serialize(
            "discussion",
            discussion,
            {"user": user},
            only=resource_options.fields,
            include=merge_resource_includes(("user", "last_posted_user"), resource_options.includes),
        )
    )
    return payload


def _apply_discussion_resource_preloads(queryset, user=None, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().apply_preload_plan(
        queryset,
        "discussion",
        {"user": user},
        only=resource_options.fields,
        include=merge_resource_includes(("user", "last_posted_user"), resource_options.includes),
    )


def _serialize_discussion_sort(definition):
    return {
        "code": definition.code,
        "label": definition.label,
        "module_id": definition.module_id,
        "description": definition.description,
        "icon": definition.icon,
        "is_default": definition.is_default,
        "toolbar_visible": definition.toolbar_visible,
    }


def _serialize_discussion_list_filter(definition):
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


def _register_discussion_core_resource_endpoints():
    registry = _get_resource_registry()
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="create",
            module_id="core",
            handler=_dispatch_discussion_create,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="index",
            module_id="core",
            handler=_dispatch_discussion_index,
            methods=("GET",),
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="read-all",
            module_id="core",
            handler=_dispatch_discussion_mark_all_read,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="read",
            module_id="core",
            handler=_dispatch_discussion_update_read_state,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="show",
            module_id="core",
            handler=_dispatch_discussion_show,
            methods=("GET",),
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="update",
            module_id="core",
            handler=_dispatch_discussion_update,
            methods=("PATCH",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="delete",
            module_id="core",
            handler=_dispatch_discussion_delete,
            methods=("DELETE",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="pin",
            module_id="core",
            handler=_dispatch_discussion_toggle_pin,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="lock",
            module_id="core",
            handler=_dispatch_discussion_toggle_lock,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="hide",
            module_id="core",
            handler=_dispatch_discussion_toggle_hide,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="subscribe",
            module_id="core",
            handler=_dispatch_discussion_subscribe,
            methods=("POST",),
            auth_required=True,
        )
    )
    registry.register_core_endpoint(
        ResourceEndpointDefinition(
            resource="discussion",
            endpoint="subscribe",
            module_id="core",
            handler=_dispatch_discussion_unsubscribe,
            methods=("DELETE",),
            auth_required=True,
        )
    )


def _discussion_object_id(context) -> int:
    try:
        return int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return 0


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


def _dispatch_discussion_create(context):
    raw_payload = _discussion_payload(context)
    payload = DiscussionCreateSchema(**_discussion_attributes(raw_payload))
    try:
        discussion = DiscussionService.create_discussion(
            title=payload.title,
            content=payload.content,
            user=context["user"],
            extension_payload=raw_payload,
        )
        return _serialize_discussion_payload(discussion, user=context["user"])
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def _dispatch_discussion_index(context):
    request = context["request"]
    user = context.get("user")
    q = _discussion_query_value(context, "q")
    tag = _discussion_query_value(context, "tag")
    author = _discussion_query_value(context, "author")
    filter_code = _discussion_query_value(context, "filter", "all")
    subscription = _discussion_query_value(context, "subscription")
    sort = _discussion_query_value(context, "sort", "latest")
    page, limit = PaginationService.normalize(
        _discussion_query_value(context, "page", 1),
        _discussion_query_value(context, "limit", 20),
    )
    resource_options = parse_resource_query_options(request, "discussion")

    normalized_filter = filter_code
    if subscription == "following" and normalized_filter == "all":
        normalized_filter = "following"

    discussions, total = DiscussionService.get_discussion_list(
        q=q,
        tag=tag,
        author=author,
        list_filter=normalized_filter,
        sort=sort,
        page=page,
        limit=limit,
        user=user,
        preload=lambda queryset: _apply_discussion_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
        ),
    )
    active_filter = DiscussionService.normalize_discussion_list_filter(normalized_filter)
    active_sort = DiscussionService.normalize_discussion_sort(sort)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "filter": active_filter,
        "available_filters": [
            _serialize_discussion_list_filter(item)
            for item in DiscussionService.get_discussion_list_filter_catalog()
        ],
        "sort": active_sort,
        "available_sorts": [
            _serialize_discussion_sort(item)
            for item in DiscussionService.get_discussion_sort_catalog()
        ],
        "data": [
            _serialize_discussion_payload(discussion, user=user, resource_options=resource_options)
            for discussion in discussions
        ],
    }


def _dispatch_discussion_show(context):
    request = context["request"]
    user = context.get("user")
    try:
        discussion_id = int(context.get("object_id") or 0)
    except (TypeError, ValueError):
        return api_error("讨论不存在", status=404)

    resource_options = parse_resource_query_options(request, "discussion")
    discussion = DiscussionService.get_discussion_by_id(
        discussion_id,
        user,
        preload=lambda queryset: _apply_discussion_resource_preloads(
            queryset,
            user=user,
            resource_options=resource_options,
        ),
    )
    if not discussion:
        return api_error("讨论不存在", status=404)

    first_post = None
    if discussion.first_post_id:
        try:
            post = Post.objects.select_related('user').get(id=discussion.first_post_id)
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

    resource_fields = _get_resource_registry().serialize(
        "discussion",
        discussion,
        {"user": user},
        only=resource_options.fields,
        include=resource_options.includes,
    )
    response_data = _serialize_discussion_payload(discussion, user=user, resource_options=resource_options)
    response_data['first_post'] = first_post
    response_data.update(resource_fields)
    return response_data


def _dispatch_discussion_mark_all_read(context):
    marked_at = DiscussionService.mark_all_as_read(context["user"])
    return {
        "message": "已全部标记为已读",
        "marked_all_as_read_at": marked_at,
    }


def _dispatch_discussion_update_read_state(context):
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


def _dispatch_discussion_update(context):
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
        return _serialize_discussion_payload(discussion, user=context["user"])
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)
    except ValueError as e:
        return api_error(str(e), status=400)


def _dispatch_discussion_delete(context):
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


def _dispatch_discussion_toggle_pin(context):
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


def _dispatch_discussion_toggle_lock(context):
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


def _dispatch_discussion_toggle_hide(context):
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


def _dispatch_discussion_subscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        DiscussionService.subscribe_discussion(discussion_id, context["user"])
        return {"message": "已关注讨论", "is_subscribed": True}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


def _dispatch_discussion_unsubscribe(context):
    discussion_id = _discussion_object_id(context)
    try:
        DiscussionService.unsubscribe_discussion(discussion_id, context["user"])
        return {"message": "已取消关注", "is_subscribed": False}
    except Discussion.DoesNotExist:
        return api_error("讨论不存在", status=404)
    except PermissionDenied as e:
        return api_error(str(e), status=403)


@router.post("/", response=DiscussionOutSchema, auth=AuthBearer(), tags=["Discussions"])
def create_discussion(request, payload: dict = Body(...)):
    """
    创建讨论

    需要认证
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(request, resource="discussion", endpoint="create")


@router.get("/", tags=["Discussions"])
def list_discussions(
    request,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    author: Optional[str] = None,
    filter: str = 'all',
    subscription: Optional[str] = None,
    sort: str = 'latest',
    page: int = 1,
    limit: int = 20,
):
    """
    获取讨论列表

    参数:
    - q: 搜索关键词
    - tag: 标签slug
    - author: 作者用户名
    - sort: 排序方式 (latest, top, oldest, newest)
    - page: 页码
    - limit: 每页数量
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(request, resource="discussion", endpoint="index")


@router.post("/read-all", auth=AuthBearer(), tags=["Discussions"])
def mark_all_discussions_as_read(request):
    """
    将当前用户可见的讨论标记为已读

    需要认证
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(request, resource="discussion", endpoint="read-all")


@router.post("/{discussion_id}/read", auth=AuthBearer(), tags=["Discussions"])
def update_discussion_read_state(request, discussion_id: int, payload: DiscussionReadStateSchema):
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="read",
    )


@router.get("/{discussion_id}", tags=["Discussions"])
def get_discussion(request, discussion_id: int):
    """
    获取讨论详情
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="show",
    )


@router.patch("/{discussion_id}", response=DiscussionOutSchema, auth=AuthBearer(), tags=["Discussions"])
def update_discussion(request, discussion_id: int, payload: dict = Body(...)):
    """
    更新讨论

    需要认证和权限
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="update",
    )


@router.delete("/{discussion_id}", auth=AuthBearer(), tags=["Discussions"])
def delete_discussion(request, discussion_id: int):
    """
    删除讨论

    需要认证和权限（仅管理员）
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="delete",
    )


@router.post("/{discussion_id}/pin", auth=AuthBearer(), tags=["Discussions"])
def toggle_pin_discussion(request, discussion_id: int):
    """
    切换讨论置顶状态

    需要管理员权限
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="pin",
    )


@router.post("/{discussion_id}/lock", auth=AuthBearer(), tags=["Discussions"])
def toggle_lock_discussion(request, discussion_id: int):
    """
    切换讨论锁定状态

    需要管理员权限
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="lock",
    )


@router.post("/{discussion_id}/hide", auth=AuthBearer(), tags=["Discussions"])
def toggle_hide_discussion(request, discussion_id: int):
    """
    切换讨论隐藏状态

    需要管理员权限
    """
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="hide",
    )


@router.post("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def subscribe_discussion(request, discussion_id: int):
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="subscribe",
    )


@router.delete("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def unsubscribe_discussion(request, discussion_id: int):
    _register_discussion_core_resource_endpoints()
    return dispatch_resource_endpoint(
        request,
        resource="discussion",
        object_id=str(discussion_id),
        endpoint="subscribe",
    )
