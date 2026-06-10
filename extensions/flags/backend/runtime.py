from __future__ import annotations


def flag_service_provider() -> dict:
    from extensions.flags.backend.models import PostFlag
    from extensions.flags.backend.services import (
        delete_post_flags,
        get_flag_list,
        report_post,
        resolve_flag,
        resolve_post_flags,
    )

    return {
        "model": PostFlag,
        "status_open": PostFlag.STATUS_OPEN,
        "status_resolved": PostFlag.STATUS_RESOLVED,
        "status_ignored": PostFlag.STATUS_IGNORED,
        "report_post": report_post,
        "get_flag_list": get_flag_list,
        "resolve_flag": resolve_flag,
        "resolve_post_flags": resolve_post_flags,
        "delete_post_flags": delete_post_flags,
    }

