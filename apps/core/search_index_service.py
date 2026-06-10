from __future__ import annotations

import time
from typing import Dict, List

from django.db import connection


def get_search_index_definitions() -> list[dict[str, str]]:
    definitions = []
    try:
        from apps.core.extensions.bootstrap import get_extension_host

        host = get_extension_host(force=True)
        search_service = getattr(host, "search", None) if host is not None else None
        raw_definitions = search_service.get_index_definitions() if search_service is not None else []
    except Exception:
        raw_definitions = []

    for definition in raw_definitions:
        name = str(getattr(definition, "name", "") or "").strip()
        drop = str(getattr(definition, "drop", "") or "").strip()
        create = getattr(definition, "create", "")
        if callable(create):
            create = create()
        create = str(create or "").strip()
        if not name or not drop or not create:
            continue
        definitions.append({
            "name": name,
            "drop": drop,
            "create": create,
            "module_id": str(getattr(definition, "module_id", "") or "").strip(),
            "description": str(getattr(definition, "description", "") or "").strip(),
        })

    return definitions


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
            message = "扩展声明的 PostgreSQL 全文索引都已存在。"

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
