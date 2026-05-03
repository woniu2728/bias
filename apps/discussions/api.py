"""
讨论系统API端点
"""
from typing import Optional
from ninja import Router
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from apps.discussions.models import Discussion
from apps.discussions.schemas import (
    DiscussionCreateSchema,
    DiscussionUpdateSchema,
    DiscussionReadStateSchema,
    DiscussionFilterSchema,
    DiscussionOutSchema,
    DiscussionListSchema,
    DiscussionDetailSchema,
)
from apps.discussions.services import DiscussionService
from apps.posts.models import Post
from apps.core.audit import log_admin_action
from apps.core.auth import AuthBearer, get_optional_user
from apps.core.forum_resources import serialize_user_payload, serialize_user_summary
from apps.core.resource_registry import get_resource_registry

router = Router()
RESOURCE_REGISTRY = get_resource_registry()


def _serialize_discussion_payload(discussion, user=None):
    payload = DiscussionOutSchema.from_orm(discussion).dict()
    payload["user"] = serialize_user_payload(getattr(discussion, "user", None), resource="discussion_user")
    payload["last_posted_user"] = serialize_user_payload(
        getattr(discussion, "last_posted_user", None),
        resource="discussion_user",
    )
    payload["tags"] = RESOURCE_REGISTRY.serialize(
        "discussion",
        discussion,
        {"user": user},
    ).get("tags", [])
    return payload


@router.post("/", response=DiscussionOutSchema, auth=AuthBearer(), tags=["Discussions"])
def create_discussion(request, payload: DiscussionCreateSchema):
    """
    创建讨论

    需要认证
    """
    try:
        discussion = DiscussionService.create_discussion(
            title=payload.title,
            content=payload.content,
            user=request.auth,
            tag_ids=payload.tag_ids,
        )
        return _serialize_discussion_payload(discussion, user=request.auth)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.get("/", response=DiscussionListSchema, tags=["Discussions"])
def list_discussions(
    request,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    author: Optional[str] = None,
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
    user = get_optional_user(request)

    discussions, total = DiscussionService.get_discussion_list(
        q=q,
        tag=tag,
        author=author,
        subscription=subscription,
        sort=sort,
        page=page,
        limit=limit,
        user=user,
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [_serialize_discussion_payload(discussion, user=user) for discussion in discussions],
    }


@router.post("/read-all", auth=AuthBearer(), tags=["Discussions"])
def mark_all_discussions_as_read(request):
    """
    将当前用户可见的讨论标记为已读

    需要认证
    """
    marked_at = DiscussionService.mark_all_as_read(request.auth)
    return {
        "message": "已全部标记为已读",
        "marked_all_as_read_at": marked_at,
    }


@router.post("/{discussion_id}/read", auth=AuthBearer(), tags=["Discussions"])
def update_discussion_read_state(request, discussion_id: int, payload: DiscussionReadStateSchema):
    try:
        state = DiscussionService.update_read_state(
            discussion_id=discussion_id,
            user=request.auth,
            last_read_post_number=payload.last_read_post_number,
        )
        return {
            "message": "阅读状态已更新",
            "last_read_at": state.last_read_at,
            "last_read_post_number": state.last_read_post_number,
        }
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)


@router.get("/{discussion_id}", response=DiscussionDetailSchema, tags=["Discussions"])
def get_discussion(request, discussion_id: int):
    """
    获取讨论详情
    """
    user = get_optional_user(request)
    discussion = DiscussionService.get_discussion_by_id(discussion_id, user)

    if not discussion:
        return JsonResponse({"error": "讨论不存在"}, status=404)

    # 获取第一条帖子
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

    resource_fields = RESOURCE_REGISTRY.serialize(
        "discussion",
        discussion,
        {"user": user},
    )

    # 构建响应
    response_data = _serialize_discussion_payload(discussion, user=user)
    response_data['first_post'] = first_post
    response_data.update(resource_fields)

    return response_data


@router.patch("/{discussion_id}", response=DiscussionOutSchema, auth=AuthBearer(), tags=["Discussions"])
def update_discussion(request, discussion_id: int, payload: DiscussionUpdateSchema):
    """
    更新讨论

    需要认证和权限
    """
    try:
        discussion = DiscussionService.update_discussion(
            discussion_id=discussion_id,
            user=request.auth,
            title=payload.title,
            content=payload.content,
            tag_ids=payload.tag_ids,
            is_locked=payload.is_locked,
            is_sticky=payload.is_sticky,
            is_hidden=payload.is_hidden,
        )
        return _serialize_discussion_payload(discussion, user=request.auth)
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.delete("/{discussion_id}", auth=AuthBearer(), tags=["Discussions"])
def delete_discussion(request, discussion_id: int):
    """
    删除讨论

    需要认证和权限（仅管理员）
    """
    try:
        discussion = Discussion.objects.select_related("user").get(id=discussion_id)
        snapshot = {
            "title": discussion.title,
            "author_id": discussion.user_id,
            "deleted_by_owner": discussion.user_id == request.auth.id,
        }
        DiscussionService.delete_discussion(discussion_id, request.auth)
        if request.auth.is_staff or not snapshot["deleted_by_owner"]:
            log_admin_action(
                request,
                "admin.discussion.delete",
                target_type="discussion",
                target_id=discussion_id,
                data=snapshot,
            )
        return {"message": "讨论已删除"}
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)


@router.post("/{discussion_id}/pin", auth=AuthBearer(), tags=["Discussions"])
def toggle_pin_discussion(request, discussion_id: int):
    """
    切换讨论置顶状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return JsonResponse({"error": "需要管理员权限"}, status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        discussion.is_sticky = not discussion.is_sticky
        discussion.save(update_fields=['is_sticky'])
        log_admin_action(
            request,
            "admin.discussion.sticky" if discussion.is_sticky else "admin.discussion.unsticky",
            target_type="discussion",
            target_id=discussion.id,
            data={"title": discussion.title, "is_sticky": discussion.is_sticky},
        )
        return {"message": "操作成功", "is_sticky": discussion.is_sticky}
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)


@router.post("/{discussion_id}/lock", auth=AuthBearer(), tags=["Discussions"])
def toggle_lock_discussion(request, discussion_id: int):
    """
    切换讨论锁定状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return JsonResponse({"error": "需要管理员权限"}, status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        DiscussionService.set_locked_state(discussion, request.auth, not discussion.is_locked)
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
        return JsonResponse({"error": "讨论不存在"}, status=404)


@router.post("/{discussion_id}/hide", auth=AuthBearer(), tags=["Discussions"])
def toggle_hide_discussion(request, discussion_id: int):
    """
    切换讨论隐藏状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return JsonResponse({"error": "需要管理员权限"}, status=403)

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        next_hidden = not discussion.is_hidden
        DiscussionService.set_hidden_state(discussion, request.auth, next_hidden)
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
        return JsonResponse({"error": "讨论不存在"}, status=404)


@router.post("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def subscribe_discussion(request, discussion_id: int):
    try:
        DiscussionService.subscribe_discussion(discussion_id, request.auth)
        return {"message": "已关注讨论", "is_subscribed": True}
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)


@router.delete("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def unsubscribe_discussion(request, discussion_id: int):
    try:
        DiscussionService.unsubscribe_discussion(discussion_id, request.auth)
        return {"message": "已取消关注", "is_subscribed": False}
    except Discussion.DoesNotExist:
        return JsonResponse({"error": "讨论不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
