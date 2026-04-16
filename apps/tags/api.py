"""
标签系统API端点
"""
from typing import Optional
from ninja import Router
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from apps.tags.models import Tag
from apps.tags.schemas import (
    TagCreateSchema,
    TagUpdateSchema,
    TagFilterSchema,
    TagOutSchema,
    TagListSchema,
)
from apps.tags.services import TagService
from apps.core.auth import AuthBearer, get_optional_user

router = Router()


def _serialize_discussion_summary(discussion):
    if not discussion:
        return None

    return {
        "id": discussion.id,
        "title": discussion.title,
        "slug": discussion.slug,
        "last_post_number": discussion.last_post_number,
        "last_posted_at": discussion.last_posted_at,
    }


def _serialize_tag(tag, user=None, include_children=False, action="view"):
    children = []
    if include_children:
        children = [
            _serialize_tag(child, user=user, include_children=True, action=action)
            for child in tag.children.all().order_by('position', 'name')
            if not child.is_hidden and child.id not in TagService.get_forbidden_tag_ids(user, action=action)
        ]

    return {
        'id': tag.id,
        'name': tag.name,
        'slug': tag.slug,
        'description': tag.description,
        'color': tag.color,
        'icon': tag.icon,
        'background_url': tag.background_url,
        'position': tag.position,
        'parent_id': tag.parent_id,
        'is_hidden': tag.is_hidden,
        'is_restricted': tag.is_restricted,
        'view_scope': tag.view_scope,
        'start_discussion_scope': tag.start_discussion_scope,
        'reply_scope': tag.reply_scope,
        'can_start_discussion': TagService.can_start_discussion_in_tag(tag, user),
        'can_reply': TagService.can_reply_in_tag(tag, user),
        'discussion_count': tag.discussion_count,
        'last_posted_at': tag.last_posted_at,
        'last_posted_discussion': _serialize_discussion_summary(tag.last_posted_discussion),
        'created_at': tag.created_at,
        'updated_at': tag.updated_at,
        'children': children,
    }


@router.post("/tags", response=TagOutSchema, auth=AuthBearer(), tags=["Tags"])
def create_tag(request, payload: TagCreateSchema):
    """
    创建标签

    需要管理员权限
    """
    try:
        tag = TagService.create_tag(
            name=payload.name,
            slug=payload.slug,
            description=payload.description or "",
            color=payload.color or "",
            icon=payload.icon or "",
            background_url=payload.background_url or "",
            position=payload.position or 0,
            parent_id=payload.parent_id,
            is_hidden=payload.is_hidden or False,
            is_restricted=payload.is_restricted or False,
            view_scope=payload.view_scope or Tag.ACCESS_PUBLIC,
            start_discussion_scope=payload.start_discussion_scope or Tag.ACCESS_MEMBERS,
            reply_scope=payload.reply_scope or Tag.ACCESS_MEMBERS,
            user=request.auth,
        )

        # 加载子标签
        tag.children = []

        return _serialize_tag(tag, user=request.auth, include_children=True)
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


@router.get("/tags", response=TagListSchema, tags=["Tags"])
def list_tags(
    request,
    parent_id: Optional[int] = None,
    include_hidden: bool = False,
    include_children: bool = True,
    purpose: str = "view",
):
    """
    获取标签列表

    参数:
    - parent_id: 父标签ID（不传或传null表示顶级标签）
    - include_hidden: 是否包含隐藏标签（需要管理员权限）
    """
    # 只有管理员可以查看隐藏标签
    user = get_optional_user(request)
    if include_hidden and (not user or not user.is_staff):
        include_hidden = False
    if purpose not in {"view", "start_discussion", "reply"}:
        purpose = "view"

    TagService.refresh_tag_stats()

    queryset = Tag.objects.select_related('last_posted_discussion').prefetch_related('children').all()

    if parent_id is None:
        queryset = queryset.filter(parent__isnull=True)
    else:
        queryset = queryset.filter(parent_id=parent_id)

    if not include_hidden:
        queryset = queryset.filter(is_hidden=False)

    queryset = TagService.filter_tags_for_user(queryset, user, action=purpose)
    tags = queryset.order_by('position', 'name')

    return {"data": [_serialize_tag(tag, user=user, include_children=include_children, action=purpose) for tag in tags]}


@router.get("/tags/popular", response=TagListSchema, tags=["Tags"])
def get_popular_tags(request, limit: int = 10):
    """
    获取热门标签

    参数:
    - limit: 返回数量（默认10）
    """
    TagService.refresh_tag_stats()
    user = get_optional_user(request)
    tags = TagService.filter_tags_for_user(
        Tag.objects.filter(is_hidden=False),
        user,
        action="view",
    ).order_by('-discussion_count', '-last_posted_at')[:limit]

    # 添加空的children字段
    for tag in tags:
        tag.children = []

    return {"data": [_serialize_tag(tag, user=user) for tag in tags]}


@router.get("/tags/{tag_id}", response=TagOutSchema, tags=["Tags"])
def get_tag(request, tag_id: int):
    """
    获取标签详情
    """
    tag = TagService.get_tag_by_id(tag_id)

    if not tag:
        return router.create_response(
            request,
            {"error": "标签不存在"},
            status=404
        )

    user = get_optional_user(request)
    tag = Tag.objects.select_related('last_posted_discussion').prefetch_related('children').get(id=tag.id)
    if not TagService.can_view_tag(tag, user):
        return JsonResponse({"error": "没有权限查看此标签"}, status=403)
    return _serialize_tag(tag, user=user, include_children=True)


@router.get("/tags/slug/{slug}", response=TagOutSchema, tags=["Tags"])
def get_tag_by_slug(request, slug: str):
    """
    通过slug获取标签
    """
    tag = TagService.get_tag_by_slug(slug)

    if not tag:
        return router.create_response(
            request,
            {"error": "标签不存在"},
            status=404
        )

    user = get_optional_user(request)
    tag = Tag.objects.select_related('last_posted_discussion').prefetch_related('children').get(id=tag.id)
    if not TagService.can_view_tag(tag, user):
        return JsonResponse({"error": "没有权限查看此标签"}, status=403)
    return _serialize_tag(tag, user=user, include_children=True)


@router.patch("/tags/{tag_id}", response=TagOutSchema, auth=AuthBearer(), tags=["Tags"])
def update_tag(request, tag_id: int, payload: TagUpdateSchema):
    """
    更新标签

    需要管理员权限
    """
    try:
        tag = TagService.update_tag(
            tag_id=tag_id,
            user=request.auth,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            background_url=payload.background_url,
            position=payload.position,
            parent_id=payload.parent_id,
            is_hidden=payload.is_hidden,
            is_restricted=payload.is_restricted,
            view_scope=payload.view_scope,
            start_discussion_scope=payload.start_discussion_scope,
            reply_scope=payload.reply_scope,
        )

        tag = Tag.objects.select_related('last_posted_discussion').prefetch_related('children').get(id=tag.id)
        return _serialize_tag(tag, user=request.auth, include_children=True)
    except Tag.DoesNotExist:
        return router.create_response(
            request,
            {"error": "标签不存在"},
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


@router.delete("/tags/{tag_id}", auth=AuthBearer(), tags=["Tags"])
def delete_tag(request, tag_id: int):
    """
    删除标签

    需要管理员权限
    """
    try:
        TagService.delete_tag(tag_id, request.auth)
        return {"message": "标签已删除"}
    except Tag.DoesNotExist:
        return router.create_response(
            request,
            {"error": "标签不存在"},
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
