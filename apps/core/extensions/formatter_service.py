from __future__ import annotations

from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.runtime_access import get_runtime_formatter_service


_extension_formatter_pipeline_cache: list | None = None


def clear_extension_formatter_cache() -> None:
    global _extension_formatter_pipeline_cache
    _extension_formatter_pipeline_cache = None


def apply_extension_formatters(html: str) -> str:
    output = html or ""
    for transform in get_extension_formatter_pipeline():
        output = str(transform(output))
    return output


def get_extension_formatter_pipeline() -> list:
    global _extension_formatter_pipeline_cache
    if _extension_formatter_pipeline_cache is not None:
        return list(_extension_formatter_pipeline_cache)

    pipeline = []
    formatter_service = get_runtime_formatter_service()
    if formatter_service is not None:
        pipeline = formatter_service.get_pipeline()
        _extension_formatter_pipeline_cache = list(pipeline)
        return pipeline

    host = get_extension_host()
    if host is None:
        return pipeline
    for extension in host.get_extension_views():
        for transform in extension.formatter_pipeline:
            pipeline.append(transform)
    _extension_formatter_pipeline_cache = list(pipeline)
    return pipeline
