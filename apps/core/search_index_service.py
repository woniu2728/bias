from __future__ import annotations

import time
from typing import Dict, List

from django.db import connection

from apps.core.forum_registry import get_forum_registry


FORUM_REGISTRY = get_forum_registry()
SEARCHABLE_POST_TYPES = FORUM_REGISTRY.get_searchable_post_type_codes()
SEARCHABLE_POST_TYPES_SQL = ", ".join(f"'{code}'" for code in SEARCHABLE_POST_TYPES) or "'comment'"


SEARCH_INDEX_DEFINITIONS = [
    {
        "name": "discussions_title_slug_fts_idx",
        "drop": "DROP INDEX CONCURRENTLY IF EXISTS discussions_title_slug_fts_idx",
        "create": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS discussions_title_slug_fts_idx
            ON discussions
            USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(slug, '')))
        """,
    },
    {
        "name": "posts_content_fts_idx",
        "drop": "DROP INDEX CONCURRENTLY IF EXISTS posts_content_fts_idx",
        "create": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS posts_content_fts_idx
            ON posts
            USING GIN (to_tsvector('simple', coalesce(content, '')))
            WHERE type IN ({searchable_post_types})
        """.format(searchable_post_types=SEARCHABLE_POST_TYPES_SQL),
    },
    {
        "name": "users_profile_fts_idx",
        "drop": "DROP INDEX CONCURRENTLY IF EXISTS users_profile_fts_idx",
        "create": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS users_profile_fts_idx
            ON users
            USING GIN (
                to_tsvector(
                    'simple',
                    coalesce(username, '') || ' ' || coalesce(display_name, '') || ' ' || coalesce(bio, '')
                )
            )
        """,
    },
]


class SearchIndexService:
    @staticmethod
    def rebuild_postgres_indexes() -> Dict[str, object]:
        if connection.vendor != "postgresql":
            raise RuntimeError("当前数据库不是 PostgreSQL，全文索引无需重建")
        if not connection.get_autocommit():
            raise RuntimeError("全文索引重建需要在非事务环境中执行")

        started_at = time.monotonic()
        rebuilt_indexes: List[str] = []

        with connection.cursor() as cursor:
            for definition in SEARCH_INDEX_DEFINITIONS:
                cursor.execute(definition["drop"])
                cursor.execute(definition["create"])
                rebuilt_indexes.append(definition["name"])

        return {
            "message": "搜索全文索引已重建",
            "indexes": rebuilt_indexes,
            "duration_ms": int((time.monotonic() - started_at) * 1000),
        }
