from __future__ import annotations


def discussion_search_target_provider() -> dict:
    from apps.core.extensions.runtime_access import get_runtime_post_model
    from extensions.discussions.backend.models import Discussion
    from extensions.discussions.backend.visibility import apply_discussion_visibility_scope

    return {
        "model": Discussion,
        "first_post_model": get_runtime_post_model(),
        "apply_visibility": apply_discussion_visibility_scope,
    }


def post_search_target_provider() -> dict:
    from apps.core.extensions.runtime_access import get_runtime_post_model
    from extensions.discussions.backend.visibility import apply_post_visibility_scope

    return {
        "model": get_runtime_post_model(),
        "apply_visibility": apply_post_visibility_scope,
    }

