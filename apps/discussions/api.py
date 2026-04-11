"""
讨论系统API端点
"""
from typing import Optional
from ninja import Router
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from apps.discussions.models import Discussion
from apps.discussions.schemas import (
    DiscussionCreateSchema,
    DiscussionUpdateSchema,
    DiscussionFilterSchema,
    DiscussionOutSchema,
    DiscussionListSchema,
    DiscussionDetailSchema,
)
from apps.discussions.services import DiscussionService
from apps.posts.models import Post
from apps.core.auth import AuthBearer, get_optional_user

router = Router()


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
        return discussion
    except ValueError as e:
        return router.create_response(
            request,
            {"error": str(e)},
            status=400
        )


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

    # 为每个讨论添加标签数据
    for discussion in discussions:
        tags = []
        for dt in discussion.discussion_tags.all():
            tags.append({
                'id': dt.tag.id,
                'name': dt.tag.name,
                'slug': dt.tag.slug,
                'color': dt.tag.color,
                'icon': dt.tag.icon,
            })
        discussion.tags = tags

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": discussions,
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


@router.get("/{discussion_id}", response=DiscussionDetailSchema, tags=["Discussions"])
def get_discussion(request, discussion_id: int):
    """
    获取讨论详情
    """
    user = get_optional_user(request)
    discussion = DiscussionService.get_discussion_by_id(discussion_id, user)

    if not discussion:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )

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
                "user": {
                    "id": post.user.id,
                    "username": post.user.username,
                    "display_name": post.user.display_name,
                    "avatar_url": post.user.avatar_url,
                } if post.user else None,
                "created_at": post.created_at,
                "updated_at": post.updated_at,
            }
        except Post.DoesNotExist:
            pass

    # 权限检查
    can_edit = DiscussionService.can_edit_discussion(discussion, user) if user else False
    can_delete = DiscussionService.can_delete_discussion(discussion, user) if user else False
    can_reply = DiscussionService.can_reply_discussion(discussion, user) if user else False

    # 获取标签
    tags = []
    for dt in discussion.discussion_tags.all():
        tags.append({
            'id': dt.tag.id,
            'name': dt.tag.name,
            'slug': dt.tag.slug,
            'color': dt.tag.color,
            'icon': dt.tag.icon,
        })

    # 构建响应
    response_data = DiscussionOutSchema.from_orm(discussion).dict()
    response_data['first_post'] = first_post
    response_data['can_edit'] = can_edit
    response_data['can_delete'] = can_delete
    response_data['can_reply'] = can_reply
    response_data['tags'] = tags
    response_data['is_subscribed'] = DiscussionService.get_subscription_state(discussion, user)

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
            is_locked=payload.is_locked,
            is_sticky=payload.is_sticky,
            is_hidden=payload.is_hidden,
        )
        return discussion
    except Discussion.DoesNotExist:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )
    except PermissionDenied as e:
        return router.create_response(
            request,
            {"error": str(e)},
            status=403
        )
    except ValueError as e:
        return router.create_response(
            request,
            {"error": str(e)},
            status=400
        )


@router.delete("/{discussion_id}", auth=AuthBearer(), tags=["Discussions"])
def delete_discussion(request, discussion_id: int):
    """
    删除讨论

    需要认证和权限（仅管理员）
    """
    try:
        DiscussionService.delete_discussion(discussion_id, request.auth)
        return {"message": "讨论已删除"}
    except Discussion.DoesNotExist:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )
    except PermissionDenied as e:
        return router.create_response(
            request,
            {"error": str(e)},
            status=403
        )


@router.post("/{discussion_id}/pin", auth=AuthBearer(), tags=["Discussions"])
def toggle_pin_discussion(request, discussion_id: int):
    """
    切换讨论置顶状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return router.create_response(
            request,
            {"error": "需要管理员权限"},
            status=403
        )

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        discussion.is_sticky = not discussion.is_sticky
        discussion.save(update_fields=['is_sticky'])
        return {"message": "操作成功", "is_sticky": discussion.is_sticky}
    except Discussion.DoesNotExist:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )


@router.post("/{discussion_id}/lock", auth=AuthBearer(), tags=["Discussions"])
def toggle_lock_discussion(request, discussion_id: int):
    """
    切换讨论锁定状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return router.create_response(
            request,
            {"error": "需要管理员权限"},
            status=403
        )

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        discussion.is_locked = not discussion.is_locked
        discussion.save(update_fields=['is_locked'])
        return {"message": "操作成功", "is_locked": discussion.is_locked}
    except Discussion.DoesNotExist:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )


@router.post("/{discussion_id}/hide", auth=AuthBearer(), tags=["Discussions"])
def toggle_hide_discussion(request, discussion_id: int):
    """
    切换讨论隐藏状态

    需要管理员权限
    """
    if not request.auth.is_staff:
        return router.create_response(
            request,
            {"error": "需要管理员权限"},
            status=403
        )

    try:
        discussion = Discussion.objects.get(id=discussion_id)
        discussion.is_hidden = not discussion.is_hidden
        discussion.save(update_fields=['is_hidden'])
        return {"message": "操作成功", "is_hidden": discussion.is_hidden}
    except Discussion.DoesNotExist:
        return router.create_response(
            request,
            {"error": "讨论不存在"},
            status=404
        )


@router.post("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def subscribe_discussion(request, discussion_id: int):
    try:
        DiscussionService.subscribe_discussion(discussion_id, request.auth)
        return {"message": "已关注讨论", "is_subscribed": True}
    except Discussion.DoesNotExist:
        return router.create_response(request, {"error": "讨论不存在"}, status=404)


@router.delete("/{discussion_id}/subscribe", auth=AuthBearer(), tags=["Discussions"])
def unsubscribe_discussion(request, discussion_id: int):
    try:
        DiscussionService.unsubscribe_discussion(discussion_id, request.auth)
        return {"message": "已取消关注", "is_subscribed": False}
    except Discussion.DoesNotExist:
        return router.create_response(request, {"error": "讨论不存在"}, status=404)
