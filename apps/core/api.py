"""
搜索功能API端点
"""
import os
from typing import Optional
from django.http import JsonResponse
from ninja import Router
from apps.core.schemas import (
    SearchQuerySchema,
    SearchResultSchema,
    SearchSuggestionSchema,
    DiscussionSearchResultSchema,
    PostSearchResultSchema,
    UserSearchResultSchema,
    MarkdownPreviewInSchema,
    MarkdownPreviewOutSchema,
    UploadFileOutSchema,
)
from apps.core.auth import AuthBearer
from apps.core.auth import get_optional_user
from apps.core.file_service import FileUploadService
from apps.core.forum_resources import serialize_user_payload
from apps.core.markdown_service import MarkdownService
from apps.core.runtime_state import get_runtime_status
from apps.core.settings_service import get_public_forum_settings
from apps.core.resource_registry import get_resource_registry
from apps.core.services import SearchService
from apps.users.services import UserService

router = Router()
RESOURCE_REGISTRY = get_resource_registry()


@router.get("/forum", tags=["Forum"])
def get_forum_settings(request):
    """获取前台公开论坛设置"""
    return get_public_forum_settings()


@router.get("/system/status", tags=["System"])
def get_system_status(request):
    """获取论坛安装/升级状态"""
    status = get_runtime_status()
    return {
        "state": status.state,
        "message": status.message,
        "current_version": status.current_version,
        "installed_version": status.installed_version,
    }


@router.get("/uploads/policy", auth=AuthBearer(), tags=["Uploads"])
def get_upload_policy(request):
    """获取当前上传策略，供前端展示限制和提示。"""
    return FileUploadService.get_upload_policy()


@router.post("/preview", response=MarkdownPreviewOutSchema, tags=["Forum"])
def preview_markdown(request, payload: MarkdownPreviewInSchema):
    """实时预览 Markdown 内容"""
    return {
        "html": MarkdownService.render(payload.content or "", sanitize=True)
    }


@router.post("/uploads", response=UploadFileOutSchema, auth=AuthBearer(), tags=["Uploads"])
def upload_attachment(request):
    """上传 composer 附件或图片"""
    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "请选择要上传的文件"}, status=400)

    try:
        file_url, file_info = FileUploadService.upload_attachment(file, request.auth.id)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    return {
        "url": file_url,
        "original_name": file_info.get("original_name") or file.name,
        "size": file_info.get("size") or file.size,
        "mime_type": file_info.get("mime_type") or file.content_type,
        "hash": file_info.get("hash"),
        "is_image": ext in FileUploadService.ALLOWED_IMAGE_EXTENSIONS,
    }


def serialize_discussion_search_result(discussion):
    payload = {
        'id': discussion.id,
        'title': discussion.title,
        'slug': discussion.slug,
        'comment_count': discussion.comment_count,
        'view_count': discussion.view_count,
        'is_sticky': discussion.is_sticky,
        'is_locked': discussion.is_locked,
        'created_at': discussion.created_at,
        'last_posted_at': discussion.last_posted_at,
        'excerpt': discussion.excerpt,
    }
    payload.update(RESOURCE_REGISTRY.serialize("search_discussion", discussion))
    return payload


def serialize_post_search_result(post):
    payload = {
        'id': post.id,
        'discussion_id': post.discussion_id,
        'discussion_title': post.discussion_title,
        'number': post.number,
        'content': post.content,
        'created_at': post.created_at,
        'excerpt': post.excerpt,
    }
    payload.update(RESOURCE_REGISTRY.serialize("search_post", post))
    return payload


def serialize_user_search_result(user):
    return serialize_user_payload(user, resource="search_user")


@router.get("/search", response=SearchResultSchema, tags=["Search"])
def search(
    request,
    q: str,
    type: str = 'all',
    page: int = 1,
    limit: int = 20,
):
    """
    全局搜索

    参数:
    - q: 搜索关键词
    - type: 搜索类型 (all, discussions, posts, users)
    - page: 页码
    - limit: 每页数量
    """
    page = SearchService.normalize_page(page)
    limit = SearchService.normalize_limit(limit)

    if not q or len(q.strip()) == 0:
        return {
            'total': 0,
            'page': page,
            'limit': limit,
            'type': type,
            'discussion_total': 0,
            'post_total': 0,
            'user_total': 0,
            'discussions': [],
            'posts': [],
            'users': [],
        }

    query = q.strip()
    user = get_optional_user(request)
    can_search_users = bool(user and UserService.has_forum_permission(user, "searchUsers"))
    context = SearchService.build_search_context(query, user=user, include_users=can_search_users)

    if type == 'all':
        result = SearchService.search_all(
            query,
            page,
            limit,
            user=user,
            include_users=can_search_users,
            context=context,
        )
        return {
            **result,
            'discussions': [serialize_discussion_search_result(item) for item in result['discussions']],
            'posts': [serialize_post_search_result(item) for item in result['posts']],
        }

    elif type == 'discussions':
        discussions, total = SearchService.search_discussions(query, page, limit, user=user, context=context)
        discussion_data = [serialize_discussion_search_result(discussion) for discussion in discussions]

        return {
            'total': total,
            'page': page,
            'limit': limit,
            'type': type,
            'discussion_total': total,
            'post_total': context.post_total,
            'user_total': context.user_total,
            'discussions': discussion_data,
            'posts': [],
            'users': [],
        }

    elif type == 'posts':
        posts, total = SearchService.search_posts(query, page, limit, user=user, context=context)
        post_data = [serialize_post_search_result(post) for post in posts]

        return {
            'total': total,
            'page': page,
            'limit': limit,
            'type': type,
            'discussion_total': context.discussion_total,
            'post_total': total,
            'user_total': context.user_total,
            'discussions': [],
            'posts': post_data,
            'users': [],
        }

    elif type == 'users':
        if not can_search_users:
            return JsonResponse({"error": "没有权限搜索用户"}, status=403)

        users, total = SearchService.search_users(query, page, limit, context=context)

        return {
            'total': total,
            'page': page,
            'limit': limit,
            'type': type,
            'discussion_total': context.discussion_total,
            'post_total': context.post_total,
            'user_total': total,
            'discussions': [],
            'posts': [],
            'users': [serialize_user_search_result(item) for item in users],
        }

    else:
        return router.create_response(
            request,
            {"error": "无效的搜索类型"},
            status=400
        )


@router.get("/search/suggestions", response=SearchSuggestionSchema, tags=["Search"])
def get_search_suggestions(request, q: str, limit: int = 5):
    """
    获取搜索建议

    参数:
    - q: 搜索关键词
    - limit: 返回数量
    """
    if not q or len(q.strip()) == 0:
        return {'suggestions': []}

    user = get_optional_user(request)
    suggestions = SearchService.get_search_suggestions(q.strip(), limit, user=user)
    return {'suggestions': suggestions}
