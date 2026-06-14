from __future__ import annotations


_realtime_service = None


def set_realtime_service(service) -> None:
    global _realtime_service
    _realtime_service = service


def clear_realtime_service() -> None:
    global _realtime_service
    _realtime_service = None


def iter_realtime_included_enrichers():
    service_enrichers = _get_realtime_service_included_enrichers()
    if service_enrichers:
        return service_enrichers
    _ensure_realtime_runtime_bootstrapped(force=True)
    return _get_realtime_service_included_enrichers()


def iter_realtime_discussion_visibility_resolvers():
    service_resolvers = _get_realtime_service_discussion_visibility_resolvers()
    if service_resolvers:
        return service_resolvers
    _ensure_realtime_runtime_bootstrapped(force=True)
    return _get_realtime_service_discussion_visibility_resolvers()


def resolve_realtime_visible_discussion_ids(discussion_ids, user) -> list[int]:
    for resolver in iter_realtime_discussion_visibility_resolvers():
        resolved = resolver(discussion_ids, user)
        if resolved is not None:
            return list(resolved)
    return []


def can_view_realtime_discussion(discussion_id: int, user) -> bool:
    return int(discussion_id) in set(resolve_realtime_visible_discussion_ids([discussion_id], user))


def iter_realtime_discussion_transports():
    service_transports = _get_realtime_service_discussion_transports()
    if service_transports:
        return service_transports
    _ensure_realtime_runtime_bootstrapped(force=True)
    return _get_realtime_service_discussion_transports()


def broadcast_realtime_discussion_event(discussion_id: int, event_type: str, payload: dict) -> None:
    service = _get_realtime_service()
    if service is not None and hasattr(service, "broadcast_discussion_event"):
        service.broadcast_discussion_event(discussion_id, event_type, payload)
        return
    for transport in iter_realtime_discussion_transports():
        transport(discussion_id, event_type, payload)


def _ensure_realtime_runtime_bootstrapped(*, force: bool = False) -> None:
    if not force and _realtime_service is not None:
        return
    try:
        from apps.core.extensions.bootstrap import get_extension_application

        get_extension_application(force=force)
    except Exception:
        return


def _get_realtime_service():
    if _realtime_service is not None:
        return _realtime_service
    try:
        from apps.core.extensions.runtime import get_extension_host_service

        return get_extension_host_service("realtime")
    except Exception:
        return None


def _get_realtime_service_included_enrichers():
    service = _get_realtime_service()
    if service is None or not hasattr(service, "get_included_enrichers"):
        return ()
    try:
        definitions = service.get_included_enrichers()
    except Exception:
        return ()
    return tuple(
        definition.handler
        for definition in definitions
        if callable(getattr(definition, "handler", None))
    )


def _get_realtime_service_discussion_visibility_resolvers():
    service = _get_realtime_service()
    if service is None or not hasattr(service, "get_discussion_visibility_resolvers"):
        return ()
    try:
        definitions = service.get_discussion_visibility_resolvers()
    except Exception:
        return ()
    return tuple(
        definition.callback
        for definition in sorted(definitions, key=lambda item: int(getattr(item, "order", 100) or 100))
        if callable(getattr(definition, "callback", None))
    )


def _get_realtime_service_discussion_transports():
    service = _get_realtime_service()
    if service is None or not hasattr(service, "get_discussion_transports"):
        return ()
    try:
        definitions = service.get_discussion_transports()
    except Exception:
        return ()
    return tuple(
        definition.handler
        for definition in definitions
        if callable(getattr(definition, "handler", None))
    )
