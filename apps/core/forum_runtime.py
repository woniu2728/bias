from __future__ import annotations


_realtime_included_enrichers = {}
_realtime_discussion_visibility_resolvers = {}


def register_realtime_included_enricher(key: str, handler) -> None:
    normalized = str(key or "").strip()
    if not normalized or not callable(handler):
        return
    _realtime_included_enrichers[normalized] = handler


def clear_realtime_included_enrichers() -> None:
    _realtime_included_enrichers.clear()


def iter_realtime_included_enrichers():
    if not _realtime_included_enrichers:
        _ensure_realtime_runtime_bootstrapped(force=True)
    return tuple(_realtime_included_enrichers.values())


def register_realtime_discussion_visibility_resolver(key: str, handler) -> None:
    normalized = str(key or "").strip()
    if not normalized or not callable(handler):
        return
    _realtime_discussion_visibility_resolvers[normalized] = handler


def clear_realtime_discussion_visibility_resolvers() -> None:
    _realtime_discussion_visibility_resolvers.clear()


def iter_realtime_discussion_visibility_resolvers():
    return tuple(_realtime_discussion_visibility_resolvers.values())


def resolve_realtime_visible_discussion_ids(discussion_ids, user) -> list[int]:
    if not _realtime_discussion_visibility_resolvers:
        _ensure_realtime_runtime_bootstrapped(force=True)
    for resolver in iter_realtime_discussion_visibility_resolvers():
        resolved = resolver(discussion_ids, user)
        if resolved is not None:
            return list(resolved)
    return []


def can_view_realtime_discussion(discussion_id: int, user) -> bool:
    return int(discussion_id) in set(resolve_realtime_visible_discussion_ids([discussion_id], user))


def _ensure_realtime_runtime_bootstrapped(*, force: bool = False) -> None:
    if not force and (_realtime_included_enrichers or _realtime_discussion_visibility_resolvers):
        return
    try:
        from apps.core.extensions.bootstrap import get_extension_application

        get_extension_application(force=force)
    except Exception:
        return
