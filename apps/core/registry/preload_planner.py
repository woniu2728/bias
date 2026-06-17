"""
PreloadPlanner — 资源预加载计划

职责：分析 resource/endpoint 定义，生成 Django ORM 预加载计划
（select_related / prefetch_related / annotations）。

依赖：RegistryStore（或过渡期 ResourceRegistry）的 getter + 可见性谓词，
      以 store 参数注入。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from apps.core.resource_definitions import (
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    ResourcePreloadPlan,
    ResourceRelationshipDefinition,
)


class PreloadPlanner:
    """预加载计划生成器"""

    def __init__(self, store: Any):
        self._store = store

    # ── 公共入口 ──────────────────────────────────────────────

    def build_preload_plan(
        self,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = context or {}
        select_related: list[str] = []
        prefetch_related: list[Any] = []
        prefetch_where: list[tuple[str, Callable[[Any, dict], Any]]] = []
        annotations: list[tuple[str, Any]] = []
        seen_select: set[str] = set()
        seen_prefetch: set[str] = set()
        seen_annotations: set[str] = set()

        selected_fields = set(only or [])
        for definition in self._store.get_effective_fields(resource, resolved_context):
            if selected_fields and definition.field not in selected_fields:
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
                prefetch_where,
                annotations,
                seen_annotations,
            )

        include_tree = self._build_include_tree(include or ())
        include_set = set(include_tree.keys())
        for definition in self._store.get_effective_relationships(resource, resolved_context):
            if include_set and definition.relationship not in include_set:
                continue
            if not include_set and definition.relationship not in set():
                continue
            if not self._store._is_relationship_includable(definition, resolved_context):
                continue
            self._merge_preload_definition(
                definition,
                resolved_context,
                select_related,
                prefetch_related,
                seen_select,
                seen_prefetch,
                prefetch_where,
                annotations,
                seen_annotations,
                include=include,
            )
            nested_include = include_tree.get(definition.relationship) or {}
            if nested_include and definition.resource_type:
                nested_plan = self.build_preload_plan(
                    definition.resource_type,
                    resolved_context,
                    include=tuple(self._flatten_include_tree(nested_include)),
                )
                for item in nested_plan.select_related:
                    nested_item = f"{definition.relationship}__{item}"
                    if nested_item not in seen_select:
                        seen_select.add(nested_item)
                        select_related.append(nested_item)
                for item in nested_plan.prefetch_related:
                    nested_item = self._prefix_prefetch(definition.relationship, item)
                    prefetch_key = self._prefetch_key(nested_item)
                    if prefetch_key and prefetch_key not in seen_prefetch:
                        seen_prefetch.add(prefetch_key)
                        prefetch_related.append(nested_item)
                for relation, callback in nested_plan.prefetch_where:
                    prefetch_where.append((f"{definition.relationship}__{relation}", callback))

        return ResourcePreloadPlan(
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
            prefetch_where=tuple(prefetch_where),
            annotations=tuple(annotations),
        )

    def apply_preload_plan(
        self,
        queryset,
        resource: str,
        context: dict | None = None,
        *,
        only: Tuple[str, ...] | List[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ):
        plan = self.build_preload_plan(
            resource,
            context,
            only=only,
            include=include,
        )
        if plan.select_related:
            queryset = queryset.select_related(*plan.select_related)
        if plan.prefetch_related:
            queryset = queryset.prefetch_related(*plan.prefetch_related)
        if plan.annotations:
            queryset = queryset.annotate(**dict(plan.annotations))
        return queryset

    def build_endpoint_preload_plan(
        self,
        resource: str,
        endpoint: str,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = dict(context or {})
        definition = self._store.get_dispatch_endpoint(
            resource,
            endpoint,
            str(resolved_context.get("method") or "GET"),
            resolved_context,
        )
        if definition is None:
            return ResourcePreloadPlan()

        return self.build_endpoint_definition_preload_plan(definition, resolved_context)

    def build_endpoint_definition_preload_plan(
        self,
        definition: ResourceEndpointDefinition,
        context: dict | None = None,
    ) -> ResourcePreloadPlan:
        resolved_context = dict(context or {})
        include = tuple(resolved_context.get("include") or definition.default_include or ())
        plan = self.build_preload_plan(definition.resource, resolved_context, include=include)
        select_related = list(plan.select_related)
        prefetch_related = list(plan.prefetch_related)
        prefetch_where = list(plan.prefetch_where)
        annotations = list(plan.annotations)
        seen_select = set(select_related)
        seen_prefetch = {self._prefetch_key(item) for item in prefetch_related}
        seen_annotations = {name for name, _value in annotations}

        self._merge_preload_definition(
            definition,
            resolved_context,
            select_related,
            prefetch_related,
            seen_select,
            seen_prefetch,
            prefetch_where,
            annotations,
            seen_annotations,
            include=include,
        )

        return ResourcePreloadPlan(
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
            prefetch_where=tuple(prefetch_where),
            annotations=tuple(annotations),
        )

    # ── 内部 ──────────────────────────────────────────────────

    def _merge_preload_definition(
        self,
        definition,
        context: dict,
        select_related: list[str],
        prefetch_related: list[Any],
        seen_select: set[str],
        seen_prefetch: set[str],
        prefetch_where: list[tuple[str, Callable[[Any, dict], Any]]] | None = None,
        annotations: list[tuple[str, Any]] | None = None,
        seen_annotations: set[str] | None = None,
        include: Tuple[str, ...] | List[str] | None = None,
    ) -> None:
        for item in getattr(definition, "select_related", ()) or ():
            if item and item not in seen_select:
                seen_select.add(item)
                select_related.append(item)

        for item in getattr(definition, "prefetch_related", ()) or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

        preload_resolver = getattr(definition, "preload_resolver", None)
        if preload_resolver is not None:
            extra_select, extra_prefetch = preload_resolver(context)
            for item in extra_select or ():
                if item and item not in seen_select:
                    seen_select.add(item)
                    select_related.append(item)

            for item in extra_prefetch or ():
                prefetch_key = self._prefetch_key(item)
                if prefetch_key and prefetch_key not in seen_prefetch:
                    seen_prefetch.add(prefetch_key)
                    prefetch_related.append(item)

        annotate_resolver = getattr(definition, "annotate_resolver", None)
        if annotate_resolver is not None and annotations is not None and seen_annotations is not None:
            for name, expression in (annotate_resolver(context) or {}).items():
                normalized = str(name or "").strip()
                if not normalized or normalized in seen_annotations:
                    continue
                seen_annotations.add(normalized)
                annotations.append((normalized, expression))

        for item in getattr(definition, "eager_load", ()) or ():
            prefetch_key = self._prefetch_key(item)
            if prefetch_key and prefetch_key not in seen_prefetch:
                seen_prefetch.add(prefetch_key)
                prefetch_related.append(item)

        include_set = set(str(item or "").strip() for item in include or () if str(item or "").strip())
        when_included_rules = (
            getattr(definition, "eager_load_when_included_rules", ())
            or getattr(definition, "eager_load_when_included", ())
            or ()
        )
        for included, items in when_included_rules:
            if str(included or "").strip() not in include_set:
                continue
            for item in items or ():
                prefetch_key = self._prefetch_key(item)
                if prefetch_key and prefetch_key not in seen_prefetch:
                    seen_prefetch.add(prefetch_key)
                    prefetch_related.append(item)

        where_rules = (
            getattr(definition, "eager_load_where_rules", ())
            or getattr(definition, "eager_load_where", ())
            or ()
        )
        for relation, callback in where_rules:
            normalized = str(relation or "").strip()
            if not normalized or not callable(callback):
                continue
            if prefetch_where is not None:
                prefetch_where.append((normalized, callback))
            if normalized not in seen_prefetch:
                seen_prefetch.add(normalized)
                prefetch_related.append(normalized)

    # ── 静态工具 ──────────────────────────────────────────────

    @staticmethod
    def _build_include_tree(include: Tuple[str, ...] | List[str]) -> dict[str, dict]:
        tree: dict[str, dict] = {}
        for item in include or ():
            current = tree
            for part in str(item or "").split("."):
                normalized = part.strip()
                if not normalized:
                    continue
                current = current.setdefault(normalized, {})
        return tree

    @staticmethod
    def _flatten_include_tree(tree: dict[str, dict], prefix: str = "") -> list[str]:
        output: list[str] = []
        for name, children in tree.items():
            path = f"{prefix}.{name}" if prefix else name
            output.append(path)
            output.extend(PreloadPlanner._flatten_include_tree(children, path))
        return output

    @staticmethod
    def _prefix_prefetch(prefix: str, item: Any) -> Any:
        if isinstance(item, str):
            return f"{prefix}__{item}"
        return item

    @staticmethod
    def _prefetch_key(item: Any) -> str:
        if isinstance(item, str):
            return item
        lookup = getattr(item, "prefetch_to", None) or getattr(item, "lookup", None)
        if lookup:
            return str(lookup)
        return repr(item)
