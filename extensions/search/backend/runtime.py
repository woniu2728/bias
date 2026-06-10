from __future__ import annotations


def search_service_provider() -> dict:
    from extensions.search.backend.services import SearchService

    return {
        "apply_discussion_search": SearchService.apply_discussion_search,
        "apply_post_search": SearchService.apply_post_search,
        "apply_user_search": SearchService.apply_user_search,
        "build_search_context": SearchService.build_search_context,
        "search_all": SearchService.search_all,
        "search_preview": SearchService.search_preview,
        "search_discussions": SearchService.search_discussions,
        "search_posts": SearchService.search_posts,
        "search_users": SearchService.search_users,
        "get_public_search_filters": SearchService.get_public_search_filters,
        "get_search_suggestions": SearchService.get_search_suggestions,
        "normalize_page": SearchService.normalize_page,
        "normalize_limit": SearchService.normalize_limit,
    }
