from __future__ import annotations

from apps.core.extensions.bootstrap import get_extension_host
from apps.core.extensions.runtime_access import get_runtime_formatter_service


_extension_formatter_pipeline_cache: dict[str, list] = {}


def clear_extension_formatter_cache() -> None:
    global _extension_formatter_pipeline_cache
    _extension_formatter_pipeline_cache = {}


def apply_extension_formatters(html: str) -> str:
    return apply_extension_formatter_render(html)


def apply_extension_formatter_config(configuration: dict) -> dict:
    output = dict(configuration or {})
    for callback in get_extension_formatter_pipeline(phase="configure"):
        result = _call_formatter_callback(callback, output)
        if isinstance(result, dict):
            output = result
    return output


def apply_extension_formatter_parse(text: str, context: dict | None = None) -> str:
    output = text or ""
    for callback in get_extension_formatter_pipeline(phase="parse"):
        output = str(_call_formatter_callback(callback, output, context or {}))
    return output


def apply_extension_formatter_render(html: str, context: dict | None = None) -> str:
    output = html or ""
    for transform in get_extension_formatter_pipeline(phase="render"):
        output = str(_call_formatter_callback(transform, output, context or {}))
    return output


def apply_extension_formatter_unparse(text: str, context: dict | None = None) -> str:
    output = text or ""
    for callback in get_extension_formatter_pipeline(phase="unparse"):
        output = str(_call_formatter_callback(callback, output, context or {}))
    return output


def get_extension_formatter_pipeline(*, phase: str = "render") -> list:
    global _extension_formatter_pipeline_cache
    normalized_phase = str(phase or "render").strip().lower() or "render"
    if normalized_phase == "transform":
        normalized_phase = "render"
    if normalized_phase in _extension_formatter_pipeline_cache:
        return list(_extension_formatter_pipeline_cache[normalized_phase])

    pipeline = []
    formatter_service = get_runtime_formatter_service()
    if formatter_service is not None:
        pipeline = formatter_service.get_pipeline(phase=normalized_phase)
        _extension_formatter_pipeline_cache[normalized_phase] = list(pipeline)
        return pipeline

    host = get_extension_host()
    if host is None:
        return pipeline
    for extension in host.get_extension_views():
        callbacks = tuple(getattr(extension, "formatter_callbacks", ()) or ())
        if callbacks:
            transforms = [
                definition.callback
                for definition in callbacks
                if definition.phase == normalized_phase
            ]
        elif normalized_phase == "render":
            transforms = list(extension.formatter_pipeline)
        else:
            transforms = []
        for transform in transforms:
            pipeline.append(transform)
    _extension_formatter_pipeline_cache[normalized_phase] = list(pipeline)
    return pipeline


def _call_formatter_callback(callback, value, context: dict | None = None):
    if context is None:
        return callback(value)
    try:
        return callback(value, context)
    except TypeError:
        return callback(value)
