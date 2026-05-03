"""
搜索功能业务逻辑层
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import OuterRef, Q, Subquery

from apps.discussions.models import Discussion
from apps.posts.models import Post
from apps.core.forum_registry import get_forum_registry
from apps.tags.services import TagService
from apps.users.models import User
from apps.core.visibility import build_discussion_visibility_q, build_post_visibility_q

try:
    import jieba
except ImportError:  # pragma: no cover - 部署安装依赖后走 jieba，开发环境可降级。
    jieba = None


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[A-Za-z0-9_]+")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
POSTGRES_FULL_TEXT_CONFIG = "simple"
FORUM_REGISTRY = get_forum_registry()


@dataclass
class SearchContext:
    discussion_queryset: object
    post_queryset: object
    user_queryset: object | None
    discussion_total: int
    post_total: int
    user_total: int

    @property
    def total(self) -> int:
        return self.discussion_total + self.post_total + self.user_total


class SearchService:
    """搜索服务"""

    MIN_PAGE = 1
    MIN_LIMIT = 1
    MAX_LIMIT = 100

    @staticmethod
    def normalize_page(page: int) -> int:
        try:
            normalized = int(page)
        except (TypeError, ValueError):
            return SearchService.MIN_PAGE
        return max(SearchService.MIN_PAGE, normalized)

    @staticmethod
    def normalize_limit(limit: int) -> int:
        try:
            normalized = int(limit)
        except (TypeError, ValueError):
            return 20
        return max(SearchService.MIN_LIMIT, min(normalized, SearchService.MAX_LIMIT))

    @staticmethod
    def tokenize_query(query: str) -> List[str]:
        """
        将中英文混合查询拆成 token。

        中文优先使用 jieba；如果当前环境还没安装依赖，则回退到内置的
        CJK 二元切分，保证 API 不会因为缺少可选分词器而不可用。
        """
        normalized = (query or "").strip().lower()
        if not normalized:
            return []

        tokens = []
        raw_parts = TOKEN_RE.findall(normalized)

        for part in raw_parts:
            SearchService._append_token(tokens, part)

            if CJK_RE.fullmatch(part):
                if jieba:
                    for token in jieba.cut_for_search(part):
                        SearchService._append_token(tokens, token)
                else:
                    SearchService._append_cjk_fallback_tokens(tokens, part)

        return tokens[:16]

    @staticmethod
    def build_text_query(fields: List[str], query: str) -> Q:
        text_query = Q()

        for token in SearchService.tokenize_query(query):
            for field in fields:
                text_query |= Q(**{f"{field}__icontains": token})

        return text_query if text_query else Q(pk__in=[])

    @staticmethod
    def extract_filter_tokens(query: str) -> tuple[str, dict[str, list]]:
        text_tokens: List[str] = []
        filters: dict[str, list] = {}

        for raw_token in (query or "").split():
            matched = False
            for definition in FORUM_REGISTRY.get_search_filters():
                parsed_value = definition.parser(raw_token)
                if parsed_value is None:
                    continue
                filters.setdefault(definition.target, []).append((definition, parsed_value))
                matched = True
                break

            if not matched:
                text_tokens.append(raw_token)

        return " ".join(text_tokens).strip(), filters

    @staticmethod
    def build_discussion_search_query(query: str) -> Q:
        return (
            SearchService.build_text_query(['title', 'slug'], query) |
            SearchService.build_text_query(['posts__content'], query)
        )

    @staticmethod
    def should_use_postgres_full_text(query: str, vendor: str | None = None) -> bool:
        normalized = (query or "").strip()
        if not normalized:
            return False
        if CJK_RE.search(normalized):
            return False
        database_vendor = vendor or connection.vendor
        return database_vendor == "postgresql" and bool(ASCII_TOKEN_RE.search(normalized))

    @staticmethod
    def apply_discussion_search(queryset, query: str, user=None):
        text_query, parsed_filters = SearchService.extract_filter_tokens(query)

        if text_query:
            if SearchService.should_use_postgres_full_text(text_query):
                queryset = SearchService._apply_postgres_discussion_search(queryset, text_query, user=user)
            else:
                title_match_q = SearchService.build_text_query(['title', 'slug'], text_query)
                visible_post_match_q = (
                    SearchService.build_text_query(['posts__content'], text_query)
                    & Q(posts__type='comment')
                    & build_post_visibility_q(user, prefix="posts__")
                )
                queryset = queryset.filter(title_match_q | visible_post_match_q)

        for definition, parsed_value in parsed_filters.get("discussion", []):
            queryset = definition.applier(queryset, parsed_value, {"user": user, "query": query, "text_query": text_query})

        return queryset

    @staticmethod
    def apply_post_search(queryset, query: str):
        if SearchService.should_use_postgres_full_text(query):
            search_query = SearchService._postgres_search_query(query)
            search_vector = SearchVector('content', config=POSTGRES_FULL_TEXT_CONFIG)
            return queryset.annotate(
                search_vector=search_vector,
                search_rank=SearchRank(search_vector, search_query),
            ).filter(search_vector=search_query)

        return queryset.filter(SearchService.build_text_query(['content'], query))

    @staticmethod
    def apply_user_search(queryset, query: str):
        if SearchService.should_use_postgres_full_text(query):
            search_query = SearchService._postgres_search_query(query)
            search_vector = (
                SearchVector('username', weight='A', config=POSTGRES_FULL_TEXT_CONFIG)
                + SearchVector('display_name', weight='B', config=POSTGRES_FULL_TEXT_CONFIG)
                + SearchVector('bio', weight='C', config=POSTGRES_FULL_TEXT_CONFIG)
            )
            return queryset.annotate(
                search_vector=search_vector,
                search_rank=SearchRank(search_vector, search_query),
            ).filter(search_vector=search_query)

        return queryset.filter(SearchService.build_text_query(['username', 'display_name', 'bio'], query))

    @staticmethod
    def build_search_context(query: str, user=None, include_users: bool = True) -> SearchContext:
        discussion_queryset = SearchService._discussion_queryset(query, user=user)
        post_queryset = SearchService._post_queryset(query, user=user)
        user_queryset = SearchService._user_queryset(query) if include_users else None

        return SearchContext(
            discussion_queryset=discussion_queryset,
            post_queryset=post_queryset,
            user_queryset=user_queryset,
            discussion_total=discussion_queryset.count(),
            post_total=post_queryset.count(),
            user_total=user_queryset.count() if user_queryset is not None else 0,
        )

    @staticmethod
    def get_search_totals(query: str, user=None, include_users: bool = True) -> Dict[str, int]:
        context = SearchService.build_search_context(query, user=user, include_users=include_users)
        return {
            "discussion_total": context.discussion_total,
            "post_total": context.post_total,
            "user_total": context.user_total,
            "total": context.total,
        }

    @staticmethod
    def search_all(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
        include_users: bool = True,
        context: SearchContext | None = None,
    ) -> Dict:
        """
        全局搜索

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            Dict: 搜索结果
        """
        context = context or SearchService.build_search_context(
            query,
            user=user,
            include_users=include_users,
        )

        # 搜索讨论
        discussions = SearchService._search_discussions_queryset(
            context.discussion_queryset,
            query,
            page=1,
            limit=min(limit, 5),
        )

        # 搜索帖子
        posts = SearchService._search_posts_queryset(
            context.post_queryset,
            query,
            page=1,
            limit=min(limit, 5),
        )

        # 搜索用户
        users = (
            SearchService._search_users_queryset(context.user_queryset, limit=min(limit, 5))
            if include_users and context.user_queryset is not None
            else []
        )

        return {
            'total': context.total,
            'page': page,
            'limit': limit,
            'type': 'all',
            'discussion_total': context.discussion_total,
            'post_total': context.post_total,
            'user_total': context.user_total,
            'discussions': discussions,
            'posts': posts,
            'users': users,
        }

    @staticmethod
    def search_discussions(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
        context: SearchContext | None = None,
    ) -> Tuple[List[Discussion], int]:
        """
        搜索讨论

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Discussion], int]: (讨论列表, 总数)
        """
        context = context or SearchService.build_search_context(query, user=user, include_users=False)
        queryset = context.discussion_queryset
        discussions = SearchService._search_discussions_queryset(queryset, query, page, limit)
        return discussions, context.discussion_total

    @staticmethod
    def _search_discussions(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
    ) -> List[Discussion]:
        """
        内部方法：搜索讨论

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            List[Discussion]: 讨论列表
        """
        queryset = SearchService._discussion_queryset(query, user=user)
        return SearchService._search_discussions_queryset(queryset, query, page, limit)

    @staticmethod
    def search_posts(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
        context: SearchContext | None = None,
    ) -> Tuple[List[Post], int]:
        """
        搜索帖子

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[Post], int]: (帖子列表, 总数)
        """
        context = context or SearchService.build_search_context(query, user=user, include_users=False)
        queryset = context.post_queryset
        posts = SearchService._search_posts_queryset(queryset, query, page, limit)
        return posts, context.post_total

    @staticmethod
    def _search_posts(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
    ) -> List[Post]:
        """
        内部方法：搜索帖子

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            List[Post]: 帖子列表
        """
        queryset = SearchService._post_queryset(query, user=user)
        return SearchService._search_posts_queryset(queryset, query, page, limit)

    @staticmethod
    def search_users(
        query: str,
        page: int = 1,
        limit: int = 20,
        context: SearchContext | None = None,
    ) -> Tuple[List[User], int]:
        """
        搜索用户

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        context = context or SearchService.build_search_context(query, include_users=True)
        users = SearchService._search_users_queryset(context.user_queryset, page, limit)
        return users, context.user_total

    @staticmethod
    def _search_users(
        query: str,
        page: int = 1,
        limit: int = 20,
    ) -> List[User]:
        """
        内部方法：搜索用户

        Args:
            query: 搜索关键词
            page: 页码
            limit: 每页数量

        Returns:
            List[User]: 用户列表
        """
        queryset = SearchService._user_queryset(query)
        return SearchService._search_users_queryset(queryset, page, limit)

    @staticmethod
    def _search_users_queryset(queryset, page: int = 1, limit: int = 20) -> List[User]:
        # 排序：按讨论数和评论数
        if SearchService._queryset_has_annotation(queryset, "search_rank"):
            queryset = queryset.order_by('-search_rank', '-discussion_count', '-comment_count')
        else:
            queryset = queryset.order_by('-discussion_count', '-comment_count')

        # 分页
        page = SearchService.normalize_page(page)
        limit = SearchService.normalize_limit(limit)
        offset = (page - 1) * limit
        users = list(queryset[offset:offset + limit])

        return users

    @staticmethod
    def get_search_suggestions(query: str, limit: int = 5, user=None) -> List[str]:
        """
        获取搜索建议

        Args:
            query: 搜索关键词
            limit: 返回数量

        Returns:
            List[str]: 建议列表
        """
        suggestions = []
        limit = SearchService.normalize_limit(limit)

        # 从讨论标题中获取建议
        discussions = SearchService._discussion_queryset(query, user=user).values_list('title', flat=True)[:limit]

        suggestions.extend(discussions)

        return suggestions[:limit]

    @staticmethod
    def make_excerpt(content: str, query: str, length: int = 200) -> str:
        if not content:
            return ''

        content_lower = content.lower()
        for token in SearchService.tokenize_query(query):
            index = content_lower.find(token)
            if index != -1:
                start = max(0, index - 50)
                end = min(len(content), index + len(token) + 50)
                return ('...' if start > 0 else '') + content[start:end] + ('...' if end < len(content) else '')

        return content[:length] + '...' if len(content) > length else content

    @staticmethod
    def _discussion_queryset(query: str, user=None):
        queryset = SearchService.apply_discussion_search(Discussion.objects.all(), query, user=user).distinct()
        queryset = queryset.filter(build_discussion_visibility_q(user))
        return TagService.filter_discussions_for_user(queryset, user)

    @staticmethod
    def _post_queryset(query: str, user=None):
        queryset = SearchService.apply_post_search(Post.objects.filter(type='comment'), query)
        queryset = queryset.filter(
            build_post_visibility_q(user),
            build_discussion_visibility_q(user, prefix="discussion__"),
        )
        return TagService.filter_posts_for_user(queryset, user)

    @staticmethod
    def _user_queryset(query: str):
        return SearchService.apply_user_search(User.objects.all(), query)

    @staticmethod
    def _search_discussions_queryset(queryset, query: str, page: int, limit: int) -> List[Discussion]:
        first_post_content = Post.objects.filter(
            id=OuterRef("first_post_id"),
        ).values("content")[:1]
        queryset = queryset.select_related('user', 'last_posted_user').annotate(
            first_post_content=Subquery(first_post_content)
        )
        if SearchService._queryset_has_annotation(queryset, "search_rank"):
            queryset = queryset.order_by('-is_sticky', '-search_rank', '-comment_count', '-view_count')
        else:
            queryset = queryset.order_by('-is_sticky', '-comment_count', '-view_count')

        page = SearchService.normalize_page(page)
        limit = SearchService.normalize_limit(limit)
        offset = (page - 1) * limit
        discussions = list(queryset[offset:offset + limit])

        for discussion in discussions:
            discussion.excerpt = SearchService.make_excerpt(
                getattr(discussion, "first_post_content", "") or "",
                query,
            )

        return discussions

    @staticmethod
    def _search_posts_queryset(queryset, query: str, page: int, limit: int) -> List[Post]:
        queryset = queryset.select_related('user', 'discussion')
        if SearchService._queryset_has_annotation(queryset, "search_rank"):
            queryset = queryset.order_by('-search_rank', '-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        page = SearchService.normalize_page(page)
        limit = SearchService.normalize_limit(limit)
        offset = (page - 1) * limit
        posts = list(queryset[offset:offset + limit])

        for post in posts:
            post.discussion_title = post.discussion.title
            post.excerpt = SearchService.make_excerpt(post.content, query)

        return posts

    @staticmethod
    def _append_token(tokens: List[str], token: str):
        token = token.strip().lower()
        if token and token not in tokens:
            tokens.append(token)

    @staticmethod
    def _append_cjk_fallback_tokens(tokens: List[str], value: str):
        if len(value) <= 2:
            pieces = list(value)
        else:
            pieces = [value[index:index + 2] for index in range(len(value) - 1)]

        for piece in pieces:
            SearchService._append_token(tokens, piece)

    @staticmethod
    def _apply_postgres_discussion_search(queryset, query: str, user=None):
        search_query = SearchService._postgres_search_query(query)
        title_vector = (
            SearchVector('title', weight='A', config=POSTGRES_FULL_TEXT_CONFIG)
            + SearchVector('slug', weight='B', config=POSTGRES_FULL_TEXT_CONFIG)
        )
        visible_post_discussion_ids = SearchService.apply_post_search(
            Post.objects.filter(type='comment'),
            query,
        ).filter(
            build_post_visibility_q(user),
            build_discussion_visibility_q(user, prefix="discussion__"),
        ).values("discussion_id")

        return queryset.annotate(
            title_search_vector=title_vector,
            search_rank=SearchRank(title_vector, search_query),
        ).filter(
            Q(title_search_vector=search_query) | Q(id__in=Subquery(visible_post_discussion_ids))
        )

    @staticmethod
    def _postgres_search_query(query: str) -> SearchQuery:
        return SearchQuery(query, config=POSTGRES_FULL_TEXT_CONFIG, search_type="plain")

    @staticmethod
    def _queryset_has_annotation(queryset, name: str) -> bool:
        return name in getattr(getattr(queryset, "query", None), "annotations", {})
