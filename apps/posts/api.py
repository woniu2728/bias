"""
帖子系统API端点
"""
from typing import Optional
from ninja import Router
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from apps.posts.models import Post, PostLike, PostFlag
from apps.posts.schemas import (
    PostCreateSchema,
    PostUpdateSchema,
    PostReportSchema,
    PostFilterSchema,
    PostOutSchema,
    PostListSchema,
)
from apps.posts.services import PostService
from apps.tags.services import TagService
from apps.core.auth import AuthBearer, get_optional_user

router = Router()


def _serialize_post(post, user=None):
    return {
        "id": post.id,
        "discussion_id": post.discussion_id,
        "number": post.number,
        "user": {
            "id": post.user.id,
            "username": post.user.username,
            "display_name": post.user.display_name,
            "avatar_url": post.user.avatar_url,
        } if post.user else None,
        "type": post.type,
        "content": post.content,
        "content_html": post.content_html,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "edited_at": post.edited_at,
        "edited_user": {
            "id": post.edited_user.id,
            "username": post.edited_user.username,
            "display_name": post.edited_user.display_name,
            "avatar_url": post.edited_user.avatar_url,
        } if post.edited_user else None,
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
        "can_edit": PostService.can_edit_post(post, user) if user else False,
        "can_delete": PostService.can_delete_post(post, user) if user else False,
        "can_like": PostService.can_like_post(post, user) if user else False,
    }


def _serialize_flag(flag):
    return {
        "id": flag.id,
        "reason": flag.reason,
        "message": flag.message,
        "status": flag.status,
        "created_at": flag.created_at,
        "resolved_at": flag.resolved_at,
        "resolution_note": flag.resolution_note,
        "post": {
            "id": flag.post.id,
            "number": flag.post.number,
            "content": flag.post.content,
            "discussion_id": flag.post.discussion_id,
            "discussion_title": flag.post.discussion.title if flag.post.discussion else "",
            "author": {
                "id": flag.post.user.id,
                "username": flag.post.user.username,
                "display_name": flag.post.user.display_name,
            } if flag.post.user else None,
        },
        "user": {
            "id": flag.user.id,
            "username": flag.user.username,
            "display_name": flag.user.display_name,
        },
        "resolved_by": {
            "id": flag.resolved_by.id,
            "username": flag.resolved_by.username,
            "display_name": flag.resolved_by.display_name,
        } if flag.resolved_by else None,
    }


@router.get("/posts", response=PostListSchema, tags=["Posts"])
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
    user = get_optional_user(request)

    queryset = Post.objects.select_related(
        "discussion",
        "user",
        "edited_user",
    ).annotate(
        like_count=Count("likes")
    ).filter(
        type="comment",
        hidden_at__isnull=True,
    )

    if user and user.is_authenticated and not user.is_staff:
        queryset = queryset.filter(
            Q(approval_status=Post.APPROVAL_APPROVED)
            | Q(approval_status=Post.APPROVAL_PENDING, user=user)
        )
    elif not user or not user.is_authenticated:
        queryset = queryset.filter(approval_status=Post.APPROVAL_APPROVED)

    queryset = TagService.filter_posts_for_user(queryset, user)

    if author:
        queryset = queryset.filter(user__username=author)

    if user_id:
        queryset = queryset.filter(user_id=user_id)

    total = queryset.count()
    start = (page - 1) * limit
    end = start + limit
    posts = list(queryset.order_by("-created_at")[start:end])

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
        "data": [_serialize_post(post, user) for post in posts],
    }


@router.post("/discussions/{discussion_id}/posts", response=PostOutSchema, auth=AuthBearer(), tags=["Posts"])
def create_post(request, discussion_id: int, payload: PostCreateSchema):
    """
    创建帖子（回复讨论）

    需要认证
    """
    try:
        post = PostService.create_post(
            discussion_id=discussion_id,
            content=payload.content,
            user=request.auth,
            reply_to_post_id=payload.reply_to_post_id,
        )
        post.like_count = 0
        post.is_liked = False
        return _serialize_post(post, request.auth)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.get("/discussions/{discussion_id}/posts", response=PostListSchema, tags=["Posts"])
def list_posts(
    request,
    discussion_id: int,
    page: int = 1,
    limit: int = 20,
    near: Optional[int] = None,
):
    """
    获取帖子列表

    参数:
    - page: 页码
    - limit: 每页数量
    """
    user = get_optional_user(request)
    if near:
        page = PostService.get_page_for_near_post(
            discussion_id=discussion_id,
            near=near,
            limit=limit,
            user=user,
        )

    posts, total = PostService.get_post_list(
        discussion_id=discussion_id,
        page=page,
        limit=limit,
        user=user,
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [_serialize_post(post, user) for post in posts],
    }


@router.get("/posts/{post_id}", response=PostOutSchema, tags=["Posts"])
def get_post(request, post_id: int):
    """
    获取帖子详情
    """
    user = get_optional_user(request)
    post = PostService.get_post_by_id(post_id, user)

    if not post:
        return JsonResponse({"error": "帖子不存在"}, status=404)

    return _serialize_post(post, user)


@router.patch("/posts/{post_id}", response=PostOutSchema, auth=AuthBearer(), tags=["Posts"])
def update_post(request, post_id: int, payload: PostUpdateSchema):
    """
    更新帖子

    需要认证和权限
    """
    try:
        post = PostService.update_post(
            post_id=post_id,
            user=request.auth,
            content=payload.content,
        )

        # 重新获取帖子数据
        post = PostService.get_post_by_id(post.id, request.auth)

        return _serialize_post(post, request.auth)
    except Post.DoesNotExist:
        return JsonResponse({"error": "帖子不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.delete("/posts/{post_id}", auth=AuthBearer(), tags=["Posts"])
def delete_post(request, post_id: int):
    """
    删除帖子

    需要认证和权限
    """
    try:
        PostService.delete_post(post_id, request.auth)
        return {"message": "帖子已删除"}
    except Post.DoesNotExist:
        return JsonResponse({"error": "帖子不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/posts/{post_id}/like", auth=AuthBearer(), tags=["Posts"])
def like_post(request, post_id: int):
    """
    点赞帖子

    需要认证
    """
    try:
        PostService.like_post(post_id, request.auth)
        return {"message": "点赞成功"}
    except Post.DoesNotExist:
        return JsonResponse({"error": "帖子不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.delete("/posts/{post_id}/like", auth=AuthBearer(), tags=["Posts"])
def unlike_post(request, post_id: int):
    """
    取消点赞

    需要认证
    """
    try:
        PostService.unlike_post(post_id, request.auth)
        return {"message": "取消点赞成功"}
    except Post.DoesNotExist:
        return JsonResponse({"error": "帖子不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@router.post("/posts/{post_id}/report", auth=AuthBearer(), tags=["Posts"])
def report_post(request, post_id: int, payload: PostReportSchema):
    """举报帖子"""
    try:
        flag = PostService.report_post(
            post_id=post_id,
            user=request.auth,
            reason=payload.reason,
            message=payload.message,
        )
        return _serialize_flag(flag)
    except Post.DoesNotExist:
        return JsonResponse({"error": "帖子不存在"}, status=404)
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
