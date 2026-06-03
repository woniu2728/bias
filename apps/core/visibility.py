from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q, Subquery

from apps.core.extensions.runtime_access import (
    apply_runtime_model_visibility,
    can_view_runtime_model_private,
    evaluate_runtime_model_policy,
    evaluate_runtime_query_model_policy,
    has_runtime_model_visibility,
)
from apps.discussions.models import Discussion
from apps.posts.models import Post


@dataclass(frozen=True)
class _CoreModelVisibilityScoper:
    model: object
    ability: str
    scope: object
    order: int
    sequence: int


_CORE_MODEL_VISIBILITY_SCOPERS: list[_CoreModelVisibilityScoper] = []


def _field(prefix: str, name: str) -> str:
    return f"{prefix}{name}" if prefix else name


def register_core_model_visibility_scoper(model, scope, *, ability: str = "view", order: int = 100) -> None:
    if model is None or not callable(scope):
        return
    normalized_ability = str(ability or "*")
    _CORE_MODEL_VISIBILITY_SCOPERS.append(_CoreModelVisibilityScoper(
        model=model,
        ability=normalized_ability,
        scope=scope,
        order=int(order or 100),
        sequence=len(_CORE_MODEL_VISIBILITY_SCOPERS),
    ))


def get_core_model_visibility_scopers(model, *, ability: str = "view") -> list:
    requested_ability = str(ability or "view")
    matches = []
    for scoper in _CORE_MODEL_VISIBILITY_SCOPERS:
        if not _model_matches(scoper.model, model):
            continue
        if scoper.ability not in {"*", requested_ability}:
            continue
        matches.append((_visibility_scoper_sort_key(scoper, model), scoper.scope))
    return [scope for _key, scope in sorted(matches, key=lambda item: item[0])]


def apply_model_visibility_scope(model, queryset, *, user=None, ability: str = "view", context: dict | None = None):
    resolved_context = {
        "user": user,
        "ability": ability,
        **(context or {}),
    }
    if _evaluate_query_model_policy(model, resolved_context) is False:
        return queryset.none()
    output = queryset
    for scoper in get_core_model_visibility_scopers(model, ability=ability):
        output = scoper(output, resolved_context)
    return apply_runtime_model_visibility(
        model,
        output,
        resolved_context,
    )


def apply_related_model_visibility_subquery(
    model,
    queryset=None,
    *,
    user=None,
    ability: str = "view",
    field: str = "id",
    context: dict | None = None,
):
    base_queryset = queryset if queryset is not None else model.objects.all()
    return apply_model_visibility_scope(
        model,
        base_queryset,
        user=user,
        ability=ability,
        context=context,
    ).values(field)


def can_view_model_instance(model, instance, *, user=None, ability: str = "view", context: dict | None = None) -> bool:
    if instance is None:
        return False
    model_class = _model_class(model) or _model_class(instance)
    object_id = getattr(instance, "pk", None)
    if model_class is None or object_id is None:
        return False

    resolved_context = {
        **(context or {}),
        "user": user,
        "ability": ability,
        "model": instance,
        "instance": instance,
    }
    if model_class is Discussion:
        resolved_context.setdefault("discussion", instance)
    if model_class is Post:
        resolved_context.setdefault("post", instance)
        resolved_context.setdefault("discussion", getattr(instance, "discussion", None))

    policy_context = {
        key: value
        for key, value in resolved_context.items()
        if key not in {"ability", "model", "user"}
    }
    if evaluate_runtime_model_policy(
        ability,
        user=user,
        model=instance,
        default=True,
        **policy_context,
    ) is False:
        return False

    return apply_model_visibility_scope(
        model_class,
        model_class.objects.filter(pk=object_id),
        user=user,
        ability=ability,
        context=resolved_context,
    ).exists()


def build_discussion_visibility_q(user=None, prefix: str = "") -> Q:
    can_view_private = can_view_runtime_model_private(Discussion, user=user)
    return _build_discussion_visibility_q(user=user, prefix=prefix, include_private=can_view_private)


def apply_discussion_visibility_scope(queryset, user=None):
    return apply_model_visibility_scope(Discussion, queryset, user=user, ability="view")


def _scope_discussion_view(queryset, context: dict):
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
    can_view_private = can_view_runtime_model_private(Post, user=user)
    return _build_post_visibility_q(user=user, prefix=prefix, include_private=can_view_private)


def apply_post_visibility_scope(queryset, user=None):
    return apply_model_visibility_scope(Post, queryset, user=user, ability="view")


def _scope_post_view(queryset, context: dict):
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
            _field(prefix, "approval_status"): Post.APPROVAL_APPROVED,
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
            _field(prefix, "approval_status"): Post.APPROVAL_PENDING,
        }
    )
    if not include_hidden:
        own_pending_q &= Q(**{_field(prefix, "hidden_at__isnull"): True})
    if not include_private:
        own_pending_q &= Q(**{_field(prefix, "is_private"): False})
    own_rejected_q = Q(
        **{
            _field(prefix, "user"): user,
            _field(prefix, "approval_status"): Post.APPROVAL_REJECTED,
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


def _scope_discussion_hide(queryset, context: dict):
    return _apply_discussion_hidden_visibility_branch(queryset, user=context.get("user"))


def _scope_discussion_edit_posts(queryset, context: dict):
    return _apply_discussion_edit_posts_visibility_branch(queryset, user=context.get("user"))


def _scope_discussion_hide_posts(queryset, context: dict):
    return _apply_discussion_hidden_posts_visibility_branch(queryset, user=context.get("user"))


def _scope_post_hide_posts(queryset, context: dict):
    return _apply_post_hidden_visibility_branch(queryset, user=context.get("user"))


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


def _apply_discussion_hidden_posts_visibility_branch(queryset, *, user=None):
    if _is_staff_user(user) or _has_forum_permission(user, ("discussion.hidePosts", "discussion.hide")):
        return queryset
    if has_runtime_model_visibility(Discussion, ability="hidePosts"):
        return apply_runtime_model_visibility(
            Discussion,
            queryset,
            {"user": user, "ability": "hidePosts"},
        )
    return queryset.none()


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
    try:
        from apps.users.services import UserService

        return UserService.has_forum_permission(user, permission_names)
    except Exception:
        return False


def _can_view_forum(user, context: dict | None = None) -> bool:
    if context and context.get("skip_view_forum_gate"):
        return True
    if not user or not getattr(user, "is_authenticated", False):
        return True
    return _has_forum_permission(user, "viewForum")


def _model_matches(registered_model, model) -> bool:
    registered_class = _model_class(registered_model)
    model_class = _model_class(model)
    if registered_class is None or model_class is None:
        return registered_model == model
    return issubclass(model_class, registered_class)


def _model_class(model):
    if isinstance(model, type):
        return model
    return getattr(model, "__class__", None)


def _model_lineage(model) -> list[type]:
    model_class = _model_class(model)
    if model_class is None:
        return []
    return [item for item in reversed(model_class.__mro__) if item is not object]


def _visibility_scoper_sort_key(scoper: _CoreModelVisibilityScoper, model) -> tuple[int, int, int, int]:
    lineage = _model_lineage(model)
    registered_class = _model_class(scoper.model)
    try:
        lineage_index = lineage.index(registered_class) if registered_class in lineage else len(lineage)
    except ValueError:
        lineage_index = len(lineage)
    ability_index = 0 if scoper.ability == "*" else 1
    return (lineage_index, ability_index, scoper.order, scoper.sequence)


def _evaluate_query_model_policy(model, context: dict):
    model_class = _model_class(model)
    if model_class is None:
        return True
    policy_context = {
        key: value
        for key, value in context.items()
        if key not in {"ability", "model", "user", "instance", "discussion", "post"}
    }
    return evaluate_runtime_query_model_policy(
        str(context.get("ability") or "view"),
        user=context.get("user"),
        model=model_class,
        default=True,
        model_class=model_class,
        queryset=context.get("queryset"),
        **policy_context,
    )


register_core_model_visibility_scoper(Discussion, _scope_discussion_view, ability="view")
register_core_model_visibility_scoper(Discussion, _scope_discussion_hide, ability="hide")
register_core_model_visibility_scoper(Discussion, _scope_discussion_edit_posts, ability="editPosts")
register_core_model_visibility_scoper(Discussion, _scope_discussion_hide_posts, ability="hidePosts")
register_core_model_visibility_scoper(Post, _scope_post_view, ability="view")
register_core_model_visibility_scoper(Post, _scope_post_hide_posts, ability="hidePosts")
