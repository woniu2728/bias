"""
搜索功能业务逻辑层
"""
import re
from typing import Dict, List, Tuple

from django.db.models import Q

from apps.discussions.models import Discussion
from apps.posts.models import Post
from apps.tags.services import TagService
from apps.users.models import User
from apps.core.visibility import build_discussion_visibility_q, build_post_visibility_q

try:
    import jieba
except ImportError:  # pragma: no cover - 部署安装依赖后走 jieba，开发环境可降级。
    jieba = None


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[A-Za-z0-9_]+")


class SearchService:
    """搜索服务"""

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
    def build_discussion_search_query(query: str) -> Q:
        return (
            SearchService.build_text_query(['title', 'slug'], query) |
            SearchService.build_text_query(['posts__content'], query)
        )

    @staticmethod
    def get_search_totals(query: str, user=None, include_users: bool = True) -> Dict[str, int]:
        discussion_total = SearchService._discussion_queryset(query, user=user).count()
        post_total = SearchService._post_queryset(query, user=user).count()
        user_total = SearchService._user_queryset(query).count() if include_users else 0
        return {
            "discussion_total": discussion_total,
            "post_total": post_total,
            "user_total": user_total,
            "total": discussion_total + post_total + user_total,
        }

    @staticmethod
    def search_all(
        query: str,
        page: int = 1,
        limit: int = 20,
        user=None,
        include_users: bool = True,
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
        discussion_queryset = SearchService._discussion_queryset(query, user=user)
        post_queryset = SearchService._post_queryset(query, user=user)
        totals = SearchService.get_search_totals(query, user=user, include_users=include_users)
        discussion_total = totals["discussion_total"]
        post_total = totals["post_total"]
        user_total = totals["user_total"]

        # 搜索讨论
        discussions = SearchService._search_discussions_queryset(
            discussion_queryset,
            query,
            page=1,
            limit=min(limit, 5),
        )

        # 搜索帖子
        posts = SearchService._search_posts_queryset(
            post_queryset,
            query,
            page=1,
            limit=min(limit, 5),
        )

        # 搜索用户
        users = SearchService._search_users(query, limit=min(limit, 5)) if include_users else []

        return {
            'total': totals["total"],
            'page': page,
            'limit': limit,
            'type': 'all',
            'discussion_total': discussion_total,
            'post_total': post_total,
            'user_total': user_total,
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
        queryset = SearchService._discussion_queryset(query, user=user)
        discussions = SearchService._search_discussions_queryset(queryset, query, page, limit)
        total = queryset.count()

        return discussions, total

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
        queryset = SearchService._post_queryset(query, user=user)
        posts = SearchService._search_posts_queryset(queryset, query, page, limit)
        total = queryset.count()

        return posts, total

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
        users = SearchService._search_users(query, page, limit)
        total = SearchService._user_queryset(query).count()

        return users, total

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

        # 排序：按讨论数和评论数
        queryset = queryset.order_by('-discussion_count', '-comment_count')

        # 分页
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
        title_match_q = SearchService.build_text_query(['title', 'slug'], query)
        visible_post_match_q = (
            SearchService.build_text_query(['posts__content'], query)
            & Q(posts__type='comment')
            & build_post_visibility_q(user, prefix="posts__")
        )
        queryset = Discussion.objects.filter(title_match_q | visible_post_match_q).distinct()
        queryset = queryset.filter(build_discussion_visibility_q(user))
        return TagService.filter_discussions_for_user(queryset, user)

    @staticmethod
    def _post_queryset(query: str, user=None):
        queryset = Post.objects.filter(
            SearchService.build_text_query(['content'], query),
            type='comment',
        )
        queryset = queryset.filter(
            build_post_visibility_q(user),
            build_discussion_visibility_q(user, prefix="discussion__"),
        )
        return TagService.filter_posts_for_user(queryset, user)

    @staticmethod
    def _user_queryset(query: str):
        return User.objects.filter(
            SearchService.build_text_query(['username', 'display_name', 'bio'], query)
        )

    @staticmethod
    def _search_discussions_queryset(queryset, query: str, page: int, limit: int) -> List[Discussion]:
        queryset = queryset.select_related('user', 'last_posted_user')
        queryset = queryset.order_by('-is_sticky', '-comment_count', '-view_count')

        offset = (page - 1) * limit
        discussions = list(queryset[offset:offset + limit])
        first_post_ids = [discussion.first_post_id for discussion in discussions if discussion.first_post_id]
        first_posts = Post.objects.in_bulk(first_post_ids)

        for discussion in discussions:
            first_post = first_posts.get(discussion.first_post_id)
            discussion.excerpt = SearchService.make_excerpt(first_post.content, query) if first_post else ''

        return discussions

    @staticmethod
    def _search_posts_queryset(queryset, query: str, page: int, limit: int) -> List[Post]:
        queryset = queryset.select_related('user', 'discussion')
        queryset = queryset.order_by('-created_at')

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
