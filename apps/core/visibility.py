from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.core.extensions.runtime_access import (
    apply_runtime_model_visibility,
    evaluate_runtime_model_policy,
    evaluate_runtime_query_model_policy,
)


@dataclass(frozen=True)
class _CoreModelVisibilityScoper:
    model: object
    ability: str
    scope: object
    order: int
    sequence: int


_CORE_MODEL_VISIBILITY_SCOPERS: list[_CoreModelVisibilityScoper] = []


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
