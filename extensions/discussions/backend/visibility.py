from __future__ import annotations

from django.db.models import Q, Subquery

from apps.core.extensions.runtime_access import (
    apply_runtime_model_visibility,
    can_view_runtime_model_private,
    has_runtime_model_visibility,
)
from apps.core.visibility import apply_model_visibility_scope, apply_related_model_visibility_subquery
from extensions.discussions.backend.models import Discussion
from apps.core.extensions.runtime_access import (
    get_runtime_post_approval_approved,
    get_runtime_post_approval_pending,
    get_runtime_post_approval_rejected,
    get_runtime_post_model,
)
from apps.core.extensions.runtime_access import (
    has_runtime_forum_permission,
)


def _field(prefix: str, name: str) -> str:
    return f"{prefix}{name}" if prefix else name


def build_discussion_visibility_q(user=None, prefix: str = "") -> Q:
    can_view_private = can_view_runtime_model_private(Discussion, user=user)
    return _build_discussion_visibility_q(user=user, prefix=prefix, include_private=can_view_private)


def apply_discussion_visibility_scope(queryset, user=None):
    return apply_model_visibility_scope(Discussion, queryset, user=user, ability="view")


def scope_discussion_view(queryset, context: dict):
    user = context.get("user")
    if not _can_view_forum(user, context):
        return queryset.none()
    base_q = _build_discussion_visibility_q(user=user, include_private=True, include_hidden=True)
    if _is_staff_user(user):
        return queryset.filter(base_q)

    public_queryset = queryset.filter(base_q, is_private=False)
    private_queryset = _apply_private_visibility_branch(
        Discussion,
        queryset.filter(base_q, is_private=True),
        user=user,
    )
    queryset = (public_queryset | private_queryset).distinct()
    queryset = _apply_discussion_hidden_visibility_branch(queryset, user=user)
    return _apply_discussion_edit_posts_visibility_branch(queryset, user=user)


def _build_discussion_visibility_q(
    user=None,
    prefix: str = "",
    *,
    include_private: bool = False,
    include_hidden: bool = False,
) -> Q:
    approved_q = Q(
        **{
            _field(prefix, "approval_status"): Discussion.APPROVAL_APPROVED,
        }
    )
    if not include_hidden:
        approved_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        approved_q &= Q(**{_field(prefix, "is_private"): False})

    if not user or not getattr(user, "is_authenticated", False):
        return approved_q

    if _is_staff_user(user):
        return Q()

    own_pending_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): Discussion.APPROVAL_PENDING,
        }
    )
    if not include_hidden:
        own_pending_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        own_pending_q &= Q(**{_field(prefix, "is_private"): False})
    own_rejected_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): Discussion.APPROVAL_REJECTED,
        }
    )
    if not include_private:
        own_rejected_q &= Q(**{_field(prefix, "is_private"): False})
    return approved_q | own_pending_q | own_rejected_q


def build_post_visibility_q(user=None, prefix: str = "") -> Q:
    Post = get_runtime_post_model()
    can_view_private = can_view_runtime_model_private(Post, user=user)
    return _build_post_visibility_q(user=user, prefix=prefix, include_private=can_view_private)


def apply_post_visibility_scope(queryset, user=None):
    Post = get_runtime_post_model()
    return apply_model_visibility_scope(Post, queryset, user=user, ability="view")


def scope_post_view(queryset, context: dict):
    user = context.get("user")
    base_q = _build_post_visibility_q(user=user, include_private=True, include_hidden=True)
    if _is_staff_user(user):
        return queryset.filter(base_q)

    visible_discussion_ids = apply_related_model_visibility_subquery(
        Discussion,
        user=user,
        ability="view",
        context=context,
    )

    scoped_queryset = queryset.filter(
        base_q,
        discussion_id__in=Subquery(visible_discussion_ids),
    )
    public_queryset = scoped_queryset.filter(is_private=False)
    Post = get_runtime_post_model()
    private_queryset = _apply_private_visibility_branch(
        Post,
        scoped_queryset.filter(is_private=True),
        user=user,
    )
    queryset = (public_queryset | private_queryset).distinct()
    return _apply_post_hidden_visibility_branch(queryset, user=user)


def _build_post_visibility_q(
    user=None,
    prefix: str = "",
    *,
    include_private: bool = False,
    include_hidden: bool = False,
) -> Q:
    approved_q = Q(
        **{
            _field(prefix, "approval_status"): get_runtime_post_approval_approved(),
        }
    )
    if not include_hidden:
        approved_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        approved_q &= Q(**{_field(prefix, "is_private"): False})

    if not user or not getattr(user, "is_authenticated", False):
        return approved_q

    if _is_staff_user(user):
        return Q()

    own_pending_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): get_runtime_post_approval_pending(),
        }
    )
    if not include_hidden:
        own_pending_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        own_pending_q &= Q(**{_field(prefix, "is_private"): False})
    own_rejected_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): get_runtime_post_approval_rejected(),
        }
    )
    if not include_private:
        own_rejected_q &= Q(**{_field(prefix, "is_private"): False})
    return approved_q | own_pending_q | own_rejected_q


def _apply_private_visibility_branch(model, queryset, *, user=None):
    if can_view_runtime_model_private(model, user=user):
        return queryset
    if not has_runtime_model_visibility(model, ability="viewPrivate"):
        return queryset.none()
    return apply_runtime_model_visibility(
        model,
        queryset,
        {"user": user, "ability": "viewPrivate"},
    )


def _apply_discussion_hidden_visibility_branch(queryset, *, user=None):
    if _is_staff_user(user) or _has_forum_permission(user, "discussion.hide"):
        return queryset
    visible_queryset = queryset.filter(hidden_at__isnull=True)
    if user and getattr(user, "is_authenticated", False):
        visible_queryset = visible_queryset | queryset.filter(hidden_at__isnull=False, user=user)
    if has_runtime_model_visibility(Discussion, ability="hide"):
        visible_queryset = visible_queryset | apply_runtime_model_visibility(
            Discussion,
            queryset.filter(hidden_at__isnull=False),
            {"user": user, "ability": "hide"},
        )
    return visible_queryset.distinct()


def _apply_discussion_edit_posts_visibility_branch(queryset, *, user=None):
    if _is_staff_user(user) or _has_forum_permission(user, "discussion.edit"):
        return queryset
    visible_queryset = queryset.filter(comment_count__gt=0)
    if user and getattr(user, "is_authenticated", False):
        visible_queryset = visible_queryset | queryset.filter(user=user)
    if has_runtime_model_visibility(Discussion, ability="editPosts"):
        visible_queryset = visible_queryset | apply_runtime_model_visibility(
            Discussion,
            queryset.filter(comment_count__lte=0),
            {"user": user, "ability": "editPosts"},
        )
    return visible_queryset.distinct()


def _apply_post_hidden_visibility_branch(queryset, *, user=None):
    if _is_staff_user(user) or _has_forum_permission(user, ("discussion.hidePosts", "discussion.hide")):
        return queryset
    visible_queryset = queryset.filter(hidden_at__isnull=True)
    if user and getattr(user, "is_authenticated", False):
        visible_queryset = visible_queryset | queryset.filter(hidden_at__isnull=False, user=user)
    if has_runtime_model_visibility(Discussion, ability="hidePosts"):
        visible_discussion_ids = apply_related_model_visibility_subquery(
            Discussion,
            user=user,
            ability="hidePosts",
        )
        visible_queryset = visible_queryset | queryset.filter(
            hidden_at__isnull=False,
            discussion_id__in=Subquery(visible_discussion_ids),
        )
    return visible_queryset.distinct()


def _is_staff_user(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _has_forum_permission(user, permission_names) -> bool:
    return has_runtime_forum_permission(user, permission_names)


def _can_view_forum(user, context: dict | None = None) -> bool:
    if context and context.get("skip_view_forum_gate"):
        return True
    if not user or not getattr(user, "is_authenticated", False):
        return True
    return _has_forum_permission(user, "viewForum")


