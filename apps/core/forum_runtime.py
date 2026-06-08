from __future__ import annotations


_realtime_included_enrichers = {}


def register_realtime_included_enricher(key: str, handler) -> None:
    normalized = str(key or "").strip()
    if not normalized or not callable(handler):
        return
    _realtime_included_enrichers[normalized] = handler


def clear_realtime_included_enrichers() -> None:
    _realtime_included_enrichers.clear()


def iter_realtime_included_enrichers():
    return tuple(_realtime_included_enrichers.values())
