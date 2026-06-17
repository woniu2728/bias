from __future__ import annotations

from django.http import JsonResponse
from ninja import Router

from apps.core.extensions.platform import api_error
from apps.core.extensions.platform import get_optional_user
from apps.core.extensions.runtime import get_runtime_resource_registry
from apps.core.extensions.platform import has_forum_permission
from apps.core.extensions.platform import ResourceQueryOptions, apply_resource_preloads, parse_resource_query_options
from extensions.search.backend.schemas import SearchFilterCatalogSchema, SearchSuggestionSchema
from extensions.search.backend.services import SearchService


router = Router()


def _get_resource_registry():
    return get_runtime_resource_registry()


def serialize_discussion_search_result(discussion, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().serialize(
        "search_discussion",
        discussion,
        only=resource_options.fields,
        include=resource_options.includes,
    )


def serialize_post_search_result(post, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().serialize(
        "search_post",
        post,
        only=resource_options.fields,
        include=resource_options.includes,
    )


def serialize_user_search_result(user, resource_options=None):
    resource_options = resource_options or ResourceQueryOptions()
    return _get_resource_registry().serialize(
        "search_user",
        user,
        only=resource_options.fields,
    )


def serialize_search_filter(definition):
    return {
        "code": definition.code,
        "label": definition.label,
        "module_id": definition.module_id,
        "target": definition.target,
        "syntax": definition.syntax,
        "description": definition.description,
    }


@router.get("/search", tags=["Search"])
def search(
    request,
    q: str,
    type: str = "all",
    page: int = 1,
    limit: int = 20,
    preview: bool = False,
):
    page = SearchService.normalize_page(page)
    limit = SearchService.normalize_limit(limit)

    if not q or len(q.strip()) == 0:
        return {
            "total": 0,
            "page": page,
            "limit": limit,
            "type": type,
            "discussion_total": 0,
            "post_total": 0,
            "user_total": 0,
            "discussions": [],
            "posts": [],
            "users": [],
        }

    query = q.strip()
    user = get_optional_user(request)

    if user and user.is_authenticated and not has_forum_permission(user, "viewForum"):
        return api_error("没有权限访问搜索", status=403)

    can_search_users = user and has_forum_permission(user, "searchUsers")
    discussion_resource_options = parse_resource_query_options(request, "search_discussion")
    post_resource_options = parse_resource_query_options(request, "search_post")
    user_resource_options = parse_resource_query_options(request, "search_user")

    if preview and type == "all":
        result = SearchService.search_preview(
            query,
            limit=limit,
            user=user,
            include_users=can_search_users,
        )
        response_payload = {
            **result,
            "discussions": [
                serialize_discussion_search_result(item, resource_options=discussion_resource_options)
                for item in result["discussions"]
            ],
            "posts": [
                serialize_post_search_result(item, resource_options=post_resource_options)
                for item in result["posts"]
            ],
            "users": [
                serialize_user_search_result(item, resource_options=user_resource_options)
                for item in result["users"]
            ],
        }
        return JsonResponse(response_payload)

    context = SearchService.build_search_context(query, user=user, include_users=can_search_users)

    if type == "all":
        result = SearchService.search_all(
            query,
            page,
            limit,
            user=user,
            include_users=can_search_users,
            context=context,
        )
        response_payload = {
            **result,
            "discussions": [
                serialize_discussion_search_result(item, resource_options=discussion_resource_options)
                for item in result["discussions"]
            ],
            "posts": [
                serialize_post_search_result(item, resource_options=post_resource_options)
                for item in result["posts"]
            ],
            "users": [
                serialize_user_search_result(item, resource_options=user_resource_options)
                for item in result["users"]
            ],
        }
        return JsonResponse(response_payload)

    if type == "discussions":
        discussions, total = SearchService.search_discussions(
            query,
            page,
            limit,
            user=user,
            context=context,
            preload=lambda queryset: apply_resource_preloads(
                _get_resource_registry(),
                queryset,
                "search_discussion",
                resource_options=discussion_resource_options,
                default_includes=("user",),
            ),
        )
        discussion_data = [
            serialize_discussion_search_result(discussion, resource_options=discussion_resource_options)
            for discussion in discussions
        ]

        return JsonResponse({
            "total": total,
            "page": page,
            "limit": limit,
            "type": type,
            "discussion_total": total,
            "post_total": context.post_total,
            "user_total": context.user_total,
            "discussions": discussion_data,
            "posts": [],
            "users": [],
        })

    if type == "posts":
        posts, total = SearchService.search_posts(
            query,
            page,
            limit,
            user=user,
            context=context,
            preload=lambda queryset: apply_resource_preloads(
                _get_resource_registry(),
                queryset,
                "search_post",
                resource_options=post_resource_options,
                default_includes=("user",),
            ),
        )
        post_data = [
            serialize_post_search_result(post, resource_options=post_resource_options)
            for post in posts
        ]

        return JsonResponse({
            "total": total,
            "page": page,
            "limit": limit,
            "type": type,
            "discussion_total": context.discussion_total,
            "post_total": total,
            "user_total": context.user_total,
            "discussions": [],
            "posts": post_data,
            "users": [],
        })

    if type == "users":
        if not can_search_users:
            return api_error("没有权限搜索用户", status=403)

        users, total = SearchService.search_users(
            query,
            page,
            limit,
            context=context,
            preload=lambda queryset: apply_resource_preloads(
                _get_resource_registry(),
                queryset,
                "search_user",
                resource_options=user_resource_options,
            ),
        )

        return JsonResponse({
            "total": total,
            "page": page,
            "limit": limit,
            "type": type,
            "discussion_total": context.discussion_total,
            "post_total": context.post_total,
            "user_total": total,
            "discussions": [],
            "posts": [],
            "users": [serialize_user_search_result(item, resource_options=user_resource_options) for item in users],
        })

    return api_error("无效的搜索类型", status=400)


@router.get("/search/suggestions", response=SearchSuggestionSchema, tags=["Search"])
def get_search_suggestions(request, q: str, limit: int = 5):
    if not q or len(q.strip()) == 0:
        return {"suggestions": []}

    user = get_optional_user(request)

    if user and user.is_authenticated and not has_forum_permission(user, "viewForum"):
        return api_error("没有权限访问搜索", status=403)

    suggestions = SearchService.get_search_suggestions(q.strip(), limit, user=user)
    return {"suggestions": suggestions}


@router.get("/search/filters", response=SearchFilterCatalogSchema, tags=["Search"])
def get_search_filters(request, target: str = "all"):
    target_map = {
        "all": ("discussion", "post"),
        "discussions": ("discussion",),
        "discussion": ("discussion",),
        "posts": ("post",),
        "post": ("post",),
    }
    targets = target_map.get((target or "all").strip().lower())
    if targets is None:
        return api_error("无效的搜索过滤目标", status=400)

    return {
        "target": target,
        "filters": [
            serialize_search_filter(item)
            for item in SearchService.get_public_search_filters(targets=targets)
        ],
    }
