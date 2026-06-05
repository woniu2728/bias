from __future__ import annotations

import time
from typing import Dict, List

from django.db import connection

from apps.core.forum_registry import get_forum_registry


def _get_searchable_post_types_sql() -> str:
    searchable_post_types = get_forum_registry().get_searchable_post_type_codes()
    return ", ".join(f"'{code}'" for code in searchable_post_types) or "'comment'"


def get_search_index_definitions() -> list[dict[str, str]]:
    return [
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
            """.format(searchable_post_types=_get_searchable_post_types_sql()),
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
    def get_status() -> Dict[str, object]:
        definitions = get_search_index_definitions()
        defined_indexes = [definition["name"] for definition in definitions]

        if connection.vendor != "postgresql":
            return {
                "supported": False,
                "status": "unsupported",
                "label": "当前数据库不需要全文索引重建",
                "message": "只有 PostgreSQL 需要维护这组全文索引。",
                "expected_indexes": defined_indexes,
                "existing_indexes": [],
                "missing_indexes": defined_indexes,
            }

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = ANY (current_schemas(false))
                      AND indexname = ANY (%s)
                    """,
                    [defined_indexes],
                )
                existing_indexes = sorted(row[0] for row in cursor.fetchall())
        except Exception as exc:
            return {
                "supported": True,
                "status": "unknown",
                "label": "索引状态检测失败",
                "message": str(exc) or "无法检测 PostgreSQL 全文索引状态。",
                "expected_indexes": defined_indexes,
                "existing_indexes": [],
                "missing_indexes": defined_indexes,
            }

        existing_index_set = set(existing_indexes)
        missing_indexes = [name for name in defined_indexes if name not in existing_index_set]
        if missing_indexes:
            status = "missing"
            label = f"缺少 {len(missing_indexes)} 个索引"
            message = "建议先补齐缺失索引，再继续依赖 PostgreSQL 全文搜索。"
        else:
            status = "healthy"
            label = "索引状态正常"
            message = "讨论、回复和用户搜索所需的 PostgreSQL 全文索引都已存在。"

        return {
            "supported": True,
            "status": status,
            "label": label,
            "message": message,
            "expected_indexes": defined_indexes,
            "existing_indexes": existing_indexes,
            "missing_indexes": missing_indexes,
        }

    @staticmethod
    def rebuild_postgres_indexes() -> Dict[str, object]:
        if connection.vendor != "postgresql":
            raise RuntimeError("当前数据库不是 PostgreSQL，全文索引无需重建")
        if not connection.get_autocommit():
            raise RuntimeError("全文索引重建需要在非事务环境中执行")

        started_at = time.monotonic()
        rebuilt_indexes: List[str] = []

        with connection.cursor() as cursor:
            for definition in get_search_index_definitions():
                cursor.execute(definition["drop"])
                cursor.execute(definition["create"])
                rebuilt_indexes.append(definition["name"])

        return {
            "message": "搜索全文索引已重建",
            "indexes": rebuilt_indexes,
            "duration_ms": int((time.monotonic() - started_at) * 1000),
        }
