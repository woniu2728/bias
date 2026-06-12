from apps.core.extensions import ApiRoutesExtender, ForumCapabilitiesExtender, FrontendExtender, LifecycleExtender, ServiceProviderExtender
from apps.core.forum_registry_types import SearchFilterDefinition
from extensions.search.backend.admin_api import router as search_admin_router
from extensions.search.backend.api import router as search_router
from extensions.search.backend.filters import (
    apply_discussion_author_search_filter,
    apply_discussion_created_month_search_filter,
    apply_discussion_locked_search_filter,
    apply_discussion_sticky_search_filter,
    apply_discussion_unread_search_filter,
    apply_post_author_search_filter,
    apply_post_created_month_search_filter,
    parse_author_search_filter,
    parse_created_month_search_filter,
    parse_locked_search_filter,
    parse_sticky_search_filter,
    parse_unread_search_filter,
)
from extensions.search.backend.runtime import search_service_provider


EXTENSION_ID = "search"


def extend():
    return [
        FrontendExtender(
            forum_entry="extensions/search/frontend/forum/index.js",
        ).route(
            "/search",
            "search",
            "./SearchResultsView.vue",
            title="搜索",
            description="搜索论坛中的讨论、回复和用户。",
            order=40,
        ),
        ApiRoutesExtender(
            mounts=(("", search_router), ("/admin", search_admin_router)),
            tags=("Search",),
        ),
        ForumCapabilitiesExtender(
            search_filters=search_filter_definitions(),
        ),
        ServiceProviderExtender(
            key="search.service",
            provider=search_service_provider,
        ),
        LifecycleExtender(),
    ]


def search_filter_definitions():
    return (
        SearchFilterDefinition(
            code="author",
            label="按作者过滤",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_author_search_filter,
            applier=apply_discussion_author_search_filter,
            syntax="author:<username>",
            description="按讨论作者用户名过滤搜索结果。",
        ),
        SearchFilterDefinition(
            code="author",
            label="按作者过滤",
            module_id=EXTENSION_ID,
            target="post",
            parser=parse_author_search_filter,
            applier=apply_post_author_search_filter,
            syntax="author:<username>",
            description="按回复作者用户名过滤搜索结果。",
        ),
        SearchFilterDefinition(
            code="is_sticky",
            label="仅置顶讨论",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_sticky_search_filter,
            applier=apply_discussion_sticky_search_filter,
            syntax="is:sticky",
            description="仅返回已置顶的讨论。",
        ),
        SearchFilterDefinition(
            code="is_locked",
            label="仅锁定讨论",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_locked_search_filter,
            applier=apply_discussion_locked_search_filter,
            syntax="is:locked",
            description="仅返回已锁定的讨论。",
        ),
        SearchFilterDefinition(
            code="is_unread",
            label="仅未读讨论",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_unread_search_filter,
            applier=apply_discussion_unread_search_filter,
            syntax="is:unread",
            description="仅返回当前用户还有未读回复的讨论。",
        ),
        SearchFilterDefinition(
            code="created",
            label="按创建月份过滤",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_created_month_search_filter,
            applier=apply_discussion_created_month_search_filter,
            syntax="created:YYYY-MM",
            description="按讨论创建月份过滤搜索结果。",
        ),
        SearchFilterDefinition(
            code="created",
            label="按创建月份过滤",
            module_id=EXTENSION_ID,
            target="post",
            parser=parse_created_month_search_filter,
            applier=apply_post_created_month_search_filter,
            syntax="created:YYYY-MM",
            description="按回复创建月份过滤搜索结果。",
        ),
    )
