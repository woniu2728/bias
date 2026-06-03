from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Callable, Iterable, Tuple


ResourceContext = dict[str, Any]


@dataclass(frozen=True)
class ResourceField:
    name: str
    resolver: Callable[[Any, ResourceContext], Any]
    module_id: str = "core"
    description: str = ""
    select_related: Tuple[str, ...] = ()
    prefetch_related: Tuple[Any, ...] = ()
    preload_resolver: Callable[[ResourceContext], tuple[tuple[str, ...], tuple[Any, ...]]] | None = None
    visible: Callable[[Any, ResourceContext], bool] | bool = True
    writable: Callable[[Any, ResourceContext], bool] | bool = False
    required_on_create: bool = False
    required_on_update: bool = False
    nullable: bool = False
    value_type: str = ""
    validation_rules: Tuple[Any, ...] = ()
    has_validation_rules: bool = False
    setter: Callable[[Any, Any, ResourceContext], None] | None = None
    validator: Callable[[Any, ResourceContext], None] | None = None

    @property
    def field(self) -> str:
        return self.name

    def resolve(self, instance: Any, context: ResourceContext) -> Any:
        return self.resolver(instance, context)

    def get_value(self, context: ResourceContext) -> Any:
        return self.resolve(context.get("model"), context)

    def is_visible(self, instance: Any, context: ResourceContext) -> bool:
        if callable(self.visible):
            return bool(self.visible(instance, context))
        return bool(self.visible)

    def is_visible_for(self, context: ResourceContext) -> bool:
        return self.is_visible(context.get("model"), context)

    def is_writable(self, context: ResourceContext) -> bool:
        writable = self.writable
        if callable(writable):
            return bool(writable(context.get("model"), context))
        return bool(writable)

    def serialize_value(self, value: Any, context: ResourceContext) -> Any:
        return value

    def with_resolver(self, resolver: Callable[[Any, ResourceContext], Any]) -> "ResourceField":
        return replace(self, resolver=resolver)

    def visible_when(self, condition: Callable[[Any, ResourceContext], bool] | bool) -> "ResourceField":
        return replace(self, visible=condition)

    def writable_when(self, condition: Callable[[Any, ResourceContext], bool] | bool = True) -> "ResourceField":
        return replace(self, writable=condition)

    def required_on_create_field(self, required: bool = True) -> "ResourceField":
        return replace(self, required_on_create=bool(required))

    def required_on_update_field(self, required: bool = True) -> "ResourceField":
        return replace(self, required_on_update=bool(required))

    def nullable_field(self, nullable: bool = True) -> "ResourceField":
        return replace(self, nullable=bool(nullable))

    def type(self, value_type: str) -> "ResourceField":
        return replace(self, value_type=str(value_type or "").strip().lower())

    def string(self) -> "ResourceField":
        return self.type("string")

    def number(self) -> "ResourceField":
        return self.type("number")

    def integer(self) -> "ResourceField":
        return self.type("integer")

    def boolean(self) -> "ResourceField":
        return self.type("boolean")

    def array(self) -> "ResourceField":
        return self.type("array")

    def object(self) -> "ResourceField":
        return self.type("object")

    def rule(self, rule: Any, condition: Callable[[ResourceContext, Any], bool] | bool = True) -> "ResourceField":
        return replace(
            self,
            validation_rules=tuple([*self.validation_rules, {"rule": rule, "condition": condition}]),
            has_validation_rules=True,
        )

    def rules(
        self,
        rules: Iterable[Any] | str,
        condition: Callable[[ResourceContext, Any], bool] | bool = True,
        *,
        override: bool = True,
    ) -> "ResourceField":
        normalized = tuple(str(rules).split("|")) if isinstance(rules, str) else tuple(rules or ())
        entries = tuple({"rule": item, "condition": condition} for item in normalized)
        return replace(
            self,
            validation_rules=entries if override else tuple([*self.validation_rules, *entries]),
            has_validation_rules=True,
        )

    def required(self, condition: Callable[[ResourceContext, Any], bool] | bool = True) -> "ResourceField":
        return self.rule("required", condition)

    def required_on_create_rule(self) -> "ResourceField":
        return self.required(lambda context, model=None: bool(context.get("creating")))

    def required_on_update_rule(self) -> "ResourceField":
        return self.required(lambda context, model=None: not bool(context.get("creating")))

    def required_without(
        self,
        fields: Iterable[str],
        condition: Callable[[ResourceContext, Any], bool] | bool = True,
    ) -> "ResourceField":
        return self.rule(f"required_without:{','.join(str(item) for item in fields)}", condition)

    def required_with(
        self,
        fields: Iterable[str],
        condition: Callable[[ResourceContext, Any], bool] | bool = True,
    ) -> "ResourceField":
        return self.rule(f"required_with:{','.join(str(item) for item in fields)}", condition)

    def min(self, value: int | float) -> "ResourceField":
        return self.rule(("min", value))

    def max(self, value: int | float) -> "ResourceField":
        return self.rule(("max", value))

    def min_length(self, value: int) -> "ResourceField":
        return self.rule(("min_length", value))

    def max_length(self, value: int) -> "ResourceField":
        return self.rule(("max_length", value))

    def in_values(self, values: Iterable[Any]) -> "ResourceField":
        return self.rule(("in", tuple(values)))

    def not_in_values(self, values: Iterable[Any]) -> "ResourceField":
        return self.rule(("not_in", tuple(values)))

    def size(self, value: int | float) -> "ResourceField":
        return self.rule(("size", value))

    def same(self, field: str) -> "ResourceField":
        return self.rule(("same", field))

    def different(self, field: str) -> "ResourceField":
        return self.rule(("different", field))

    def unique(self, model: Any, field: str | None = None, *, ignore: Any = None) -> "ResourceField":
        return self.rule(("unique", {"model": model, "field": field or self.name, "ignore": ignore}))

    def exists(self, model: Any, field: str | None = None) -> "ResourceField":
        return self.rule(("exists", {"model": model, "field": field or self.name}))

    def regex(self, pattern: str) -> "ResourceField":
        return self.rule(("regex", pattern))

    def email(self) -> "ResourceField":
        return self.rule("email")

    def set_with(self, setter: Callable[[Any, Any, ResourceContext], None]) -> "ResourceField":
        return replace(self, setter=setter)

    def validate_with(self, validator: Callable[[Any, ResourceContext], None]) -> "ResourceField":
        return replace(self, validator=validator, has_validation_rules=True)

    def with_validation_rules(self, enabled: bool = True) -> "ResourceField":
        return replace(self, has_validation_rules=bool(enabled))

    def get_validation_rules(self, context: ResourceContext) -> dict[str, tuple[Any, ...]]:
        if not self.has_validation_rules:
            return {}
        rules = tuple(
            self._evaluate_rule_entry(entry, context)
            for entry in self.validation_rules or ()
            if self._rule_entry_applies(entry, context)
        )
        if not rules:
            return {}
        return {self.name: rules}

    def get_validation_messages(self, context: ResourceContext) -> dict[str, str]:
        return {}

    def get_validation_attributes(self, context: ResourceContext) -> dict[str, str]:
        return {}

    def _rule_entry_applies(self, entry: Any, context: ResourceContext) -> bool:
        if isinstance(entry, dict) and "rule" in entry:
            condition = entry.get("condition", True)
            if callable(condition):
                return bool(condition(context, context.get("model")))
            return bool(condition)
        return True

    def _evaluate_rule_entry(self, entry: Any, context: ResourceContext) -> Any:
        if isinstance(entry, dict) and "rule" in entry:
            rule = entry.get("rule")
            if callable(rule):
                return rule(context, context.get("model"))
            return rule
        return entry

    def deserialize(self, value: Any, context: ResourceContext) -> Any:
        if value is None:
            return None
        value_type = str(self.value_type or "").strip().lower()
        if value_type in {"", "any"}:
            return value
        if value_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"{self.name} must be a string")
            return value
        if value_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{self.name} must be a number")
            return value
        if value_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{self.name} must be an integer")
            return value
        if value_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{self.name} must be a boolean")
            return value
        if value_type == "array":
            if not isinstance(value, list):
                raise ValueError(f"{self.name} must be an array")
            return value
        if value_type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"{self.name} must be an object")
            return value
        return value

    def validate(self, value: Any, context: ResourceContext) -> None:
        if value is None:
            if not self.nullable:
                raise ValueError(f"{self.name} cannot be null")
            return
        for rule in self.validation_rules:
            self._validate_rule(rule, value, context)
        if self.validator is not None:
            self.validator(value, context)

    def set_value(self, instance: Any, value: Any, context: ResourceContext) -> None:
        if self.setter is not None:
            self.setter(instance, value, context)
        else:
            setattr(instance, self.name, value)

    def _validate_rule(self, rule: Any, value: Any, context: ResourceContext) -> None:
        if isinstance(rule, dict) and "rule" in rule:
            if not self._rule_entry_applies(rule, context):
                return
            rule = self._evaluate_rule_entry(rule, context)
        if callable(rule):
            rule(value, context)
            return
        if isinstance(rule, str):
            self._validate_named_rule(rule, value)
            return
        if not isinstance(rule, (tuple, list)) or not rule:
            return
        name = str(rule[0] or "").strip()
        argument = rule[1] if len(rule) > 1 else None
        self._validate_named_rule(name, value, argument)

    def _validate_named_rule(self, name: str, value: Any, argument: Any = None) -> None:
        if name == "email":
            if not isinstance(value, str) or "@" not in value:
                raise ValueError(f"{self.name} must be a valid email")
            return
        if name == "min":
            if value < argument:
                raise ValueError(f"{self.name} must be at least {argument}")
            return
        if name == "max":
            if value > argument:
                raise ValueError(f"{self.name} must be at most {argument}")
            return
        if name == "min_length":
            if len(value) < int(argument):
                raise ValueError(f"{self.name} length must be at least {argument}")
            return
        if name == "max_length":
            if len(value) > int(argument):
                raise ValueError(f"{self.name} length must be at most {argument}")
            return
        if name == "in":
            if value not in set(argument or ()):
                raise ValueError(f"{self.name} is invalid")
            return
        if name == "regex":
            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                raise ValueError(f"{self.name} format is invalid")


@dataclass(frozen=True)
class ResourceRelationship(ResourceField):
    resource_type: str = ""
    many: bool = False
    inverse: str = ""
    includable: bool = True
    linkage: Callable[[Any, ResourceContext], Any] | bool = True
    relationship_setter: Callable[[Any, Any, ResourceContext], None] | None = None

    @property
    def relationship(self) -> str:
        return self.name

    @property
    def field(self) -> str:
        return self.name

    @property
    def is_relationship(self) -> bool:
        return True

    def collections(self) -> tuple[str, ...]:
        return (self.resource_type,) if self.resource_type else ()

    def is_includable(self, context: ResourceContext) -> bool:
        if callable(self.includable):
            return bool(self.includable(context))
        return bool(self.includable)

    def include_when(self, condition: Callable[[ResourceContext], bool] | bool) -> "ResourceRelationship":
        return replace(self, includable=condition)

    def to_one(self, resource_type: str = "") -> "ResourceRelationship":
        return replace(self, resource_type=str(resource_type or self.resource_type or "").strip(), many=False)

    def to_many(self, resource_type: str = "") -> "ResourceRelationship":
        return replace(self, resource_type=str(resource_type or self.resource_type or "").strip(), many=True)

    def with_linkage(self, linkage: Callable[[Any, ResourceContext], Any] | bool) -> "ResourceRelationship":
        return replace(self, linkage=linkage)

    def set_relationship_with(self, setter: Callable[[Any, Any, ResourceContext], None]) -> "ResourceRelationship":
        return replace(self, relationship_setter=setter, writable=True)

    def set_value(self, instance: Any, value: Any, context: ResourceContext) -> None:
        setter = self.relationship_setter or self.setter
        if setter is not None:
            setter(instance, value, context)
        else:
            setattr(instance, self.name, value)

    def linkage_value(self, value: Any, context: ResourceContext) -> Any:
        if callable(self.linkage):
            return self.linkage(value, context)
        if self.linkage is False:
            return None
        return value


@dataclass(frozen=True)
class ResourceFilter:
    name: str
    handler: Callable[[Any, Any, ResourceContext], Any]
    module_id: str = "core"
    description: str = ""
    visible: Callable[[ResourceContext], bool] | bool = True

    @property
    def filter(self) -> str:
        return self.name

    def is_visible(self, context: ResourceContext) -> bool:
        if callable(self.visible):
            return bool(self.visible(context))
        return bool(self.visible)

    def apply(self, queryset, value: Any, context: ResourceContext):
        return self.handler(queryset, value, context)


@dataclass(frozen=True)
class ResourceSearchCriteria:
    user: Any = None
    filters: dict[str, Any] | None = None
    limit: int | None = None
    offset: int = 0
    sort: str = ""
    default_sort: bool = False
    query: str = ""
    resource: str = ""

    @property
    def is_fulltext(self) -> bool:
        return bool((self.filters or {}).get("q") or self.query)


@dataclass(frozen=True)
class ResourceSearchResults:
    results: Any
    total: int | None = None
    sort_applied: bool = False
    pagination_applied: bool = False
    active_filters: Tuple[Any, ...] = ()


@dataclass(frozen=True)
class ResourceEndpoint:
    name: str
    handler: Callable[[ResourceContext], Any] | None = None
    methods: Tuple[str, ...] = ("GET",)
    path: str = ""
    absolute_path: bool = False
    module_id: str = "core"
    description: str = ""
    auth_required: bool = False
    default_include: Tuple[str, ...] = ()
    eager_load: Tuple[Any, ...] = ()
    eager_load_when_included_rules: Tuple[tuple[str, Tuple[Any, ...]], ...] = ()
    eager_load_where_rules: Tuple[tuple[str, Callable[[Any, ResourceContext], Any]], ...] = ()
    default_sort: str = ""
    paginate: bool = False
    pagination_default_limit: int = 20
    pagination_max_limit: int = 50
    permission: str = ""
    ability: Any = None
    forum_permission: str = ""
    kind: str = ""
    before_hook: Callable[[ResourceContext], Any] | None = None
    after_hook: Callable[[ResourceContext, Any], Any] | None = None
    meta_resolver: Callable[[ResourceContext, Any], dict] | None = None
    links_resolver: Callable[[ResourceContext, Any], dict] | None = None
    query_callback: Callable[[ResourceContext], ResourceContext | dict | None] | None = None
    action_callback: Callable[[ResourceContext], Any] | None = None
    before_serialization_callback: Callable[[ResourceContext, Any], Any] | None = None
    response_callback: Callable[[ResourceContext, Any], Any] | None = None

    @property
    def endpoint(self) -> str:
        return self.name

    @staticmethod
    def index(name: str = "index") -> "ResourceEndpoint":
        return ResourceEndpoint(name=name, methods=("GET",), path="/", kind="index")

    @staticmethod
    def show(name: str = "show") -> "ResourceEndpoint":
        return ResourceEndpoint(name=name, methods=("GET",), path="/{object_id}", kind="show")

    @staticmethod
    def create(name: str = "create") -> "ResourceEndpoint":
        return ResourceEndpoint(name=name, methods=("POST",), path="/", kind="create")

    @staticmethod
    def update(name: str = "update") -> "ResourceEndpoint":
        return ResourceEndpoint(name=name, methods=("PATCH", "PUT"), path="/{object_id}", kind="update")

    @staticmethod
    def delete(name: str = "delete") -> "ResourceEndpoint":
        return ResourceEndpoint(name=name, methods=("DELETE",), path="/{object_id}", kind="delete")

    def authenticated(self) -> "ResourceEndpoint":
        return replace(self, auth_required=True)

    def for_module(self, module_id: str) -> "ResourceEndpoint":
        return replace(self, module_id=str(module_id or "").strip() or self.module_id)

    def add_default_include(self, includes: Iterable[str]) -> "ResourceEndpoint":
        output = list(self.default_include)
        seen = set(output)
        for include in includes:
            normalized = str(include or "").strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                output.append(normalized)
        return replace(self, default_include=tuple(output))

    def eager_load_with(self, *items: Any) -> "ResourceEndpoint":
        return replace(self, eager_load=tuple([*self.eager_load, *items]))

    def eager_load_when_included(self, include: str, *items: Any) -> "ResourceEndpoint":
        normalized = str(include or "").strip()
        if not normalized:
            return self
        return replace(
            self,
            eager_load_when_included_rules=tuple([
                *self.eager_load_when_included_rules,
                (normalized, tuple(items or ())),
            ]),
        )

    def eager_load_where(self, relation: str, callback: Callable[[Any, ResourceContext], Any]) -> "ResourceEndpoint":
        normalized = str(relation or "").strip()
        if not normalized or not callable(callback):
            return self
        return replace(
            self,
            eager_load_where_rules=tuple([
                *self.eager_load_where_rules,
                (normalized, callback),
            ]),
        )

    def with_handler(self, handler: Callable[[ResourceContext], Any]) -> "ResourceEndpoint":
        return replace(self, handler=handler)

    def with_default_sort(self, sort: str) -> "ResourceEndpoint":
        return replace(self, default_sort=str(sort or "").strip())

    def with_pagination(
        self,
        enabled: bool = True,
        *,
        default_limit: int = 20,
        max_limit: int = 50,
    ) -> "ResourceEndpoint":
        return replace(
            self,
            paginate=bool(enabled),
            pagination_default_limit=int(default_limit),
            pagination_max_limit=int(max_limit),
        )

    def can(self, ability: Any) -> "ResourceEndpoint":
        return replace(self, ability=ability, permission=str(ability or "").strip() if ability is not None else "")

    def requires_permission(self, permission: str) -> "ResourceEndpoint":
        return replace(self, forum_permission=str(permission or "").strip(), permission=str(permission or "").strip())

    def as_kind(self, kind: str) -> "ResourceEndpoint":
        return replace(self, kind=str(kind or "").strip())

    def before(self, hook: Callable[[ResourceContext], Any]) -> "ResourceEndpoint":
        return replace(self, before_hook=hook)

    def after(self, hook: Callable[[ResourceContext, Any], Any]) -> "ResourceEndpoint":
        return replace(self, after_hook=hook)

    def meta(self, resolver: Callable[[ResourceContext, Any], dict]) -> "ResourceEndpoint":
        return replace(self, meta_resolver=resolver)

    def links(self, resolver: Callable[[ResourceContext, Any], dict]) -> "ResourceEndpoint":
        return replace(self, links_resolver=resolver)

    def query(self, callback: Callable[[ResourceContext], ResourceContext | dict | None]) -> "ResourceEndpoint":
        return replace(self, query_callback=callback)

    def action(self, callback: Callable[[ResourceContext], Any]) -> "ResourceEndpoint":
        return replace(self, action_callback=callback)

    def before_serialization(self, callback: Callable[[ResourceContext, Any], Any]) -> "ResourceEndpoint":
        return replace(self, before_serialization_callback=callback)

    def response(self, callback: Callable[[ResourceContext, Any], Any]) -> "ResourceEndpoint":
        return replace(self, response_callback=callback)


@dataclass(frozen=True)
class ResourceSort:
    name: str
    handler: Any = None
    module_id: str = "core"
    description: str = ""

    @property
    def sort(self) -> str:
        return self.name


class Resource:
    module_id = "core"
    _endpoint_modifiers: dict[type, list[Callable[[list[Any], "Resource"], list[Any]]]] = {}
    _field_modifiers: dict[type, list[Callable[[list[Any], "Resource"], list[Any]]]] = {}
    _sort_modifiers: dict[type, list[Callable[[list[Any], "Resource"], list[Any]]]] = {}
    _filter_modifiers: dict[type, list[Callable[[list[Any], "Resource"], list[Any]]]] = {}

    def __init__(self) -> None:
        self._cached_endpoints = None
        self._cached_fields = None
        self._cached_sorts = None
        self._cached_filters = None

    @classmethod
    def mutate_endpoints(cls, modifier: Callable[[list[Any], "Resource"], list[Any]]) -> None:
        if callable(modifier):
            cls._endpoint_modifiers.setdefault(cls, []).append(modifier)

    @classmethod
    def mutate_fields(cls, modifier: Callable[[list[Any], "Resource"], list[Any]]) -> None:
        if callable(modifier):
            cls._field_modifiers.setdefault(cls, []).append(modifier)

    @classmethod
    def mutate_sorts(cls, modifier: Callable[[list[Any], "Resource"], list[Any]]) -> None:
        if callable(modifier):
            cls._sort_modifiers.setdefault(cls, []).append(modifier)

    @classmethod
    def mutate_filters(cls, modifier: Callable[[list[Any], "Resource"], list[Any]]) -> None:
        if callable(modifier):
            cls._filter_modifiers.setdefault(cls, []).append(modifier)

    @classmethod
    def reset_modifiers(cls, kind: str = "") -> None:
        modifier_maps = {
            "endpoints": cls._endpoint_modifiers,
            "fields": cls._field_modifiers,
            "sorts": cls._sort_modifiers,
            "filters": cls._filter_modifiers,
        }
        if kind:
            modifier_maps.get(str(kind or "").strip(), {}).pop(cls, None)
            return
        for modifiers in modifier_maps.values():
            modifiers.pop(cls, None)

    def type(self) -> str:
        raise NotImplementedError

    def base(self, instance: Any, context: ResourceContext) -> dict[str, Any]:
        return {}

    def endpoints(self) -> list[ResourceEndpoint]:
        return []

    def fields(self) -> list[ResourceField | ResourceRelationship]:
        return []

    def sorts(self) -> list[ResourceSort]:
        return []

    def filters(self) -> list[ResourceFilter]:
        return []

    def resolve_endpoints(self, *, early_resolution: bool = False) -> list[ResourceEndpoint]:
        self._ensure_resolve_cache()
        if self._cached_endpoints is not None and not early_resolution:
            return list(self._cached_endpoints)
        self._cached_endpoints = self._resolve_items("endpoints", list(self.endpoints()))
        return list(self._cached_endpoints)

    def resolve_fields(self) -> list[ResourceField | ResourceRelationship]:
        self._ensure_resolve_cache()
        if self._cached_fields is None:
            self._cached_fields = self._resolve_items("fields", list(self.fields()))
        return list(self._cached_fields)

    def resolve_sorts(self) -> list[ResourceSort]:
        self._ensure_resolve_cache()
        if self._cached_sorts is None:
            self._cached_sorts = self._resolve_items("sorts", list(self.sorts()))
        return list(self._cached_sorts)

    def resolve_filters(self) -> list[ResourceFilter]:
        self._ensure_resolve_cache()
        if self._cached_filters is None:
            self._cached_filters = self._resolve_items("filters", list(self.filters()))
        return list(self._cached_filters)

    def clear_resolved_cache(self) -> None:
        self._ensure_resolve_cache()
        self._cached_endpoints = None
        self._cached_fields = None
        self._cached_sorts = None
        self._cached_filters = None

    def _ensure_resolve_cache(self) -> None:
        if not hasattr(self, "_cached_endpoints"):
            self._cached_endpoints = None
        if not hasattr(self, "_cached_fields"):
            self._cached_fields = None
        if not hasattr(self, "_cached_sorts"):
            self._cached_sorts = None
        if not hasattr(self, "_cached_filters"):
            self._cached_filters = None

    def _resolve_items(self, kind: str, items: list[Any]) -> list[Any]:
        modifier_map = {
            "endpoints": self._endpoint_modifiers,
            "fields": self._field_modifiers,
            "sorts": self._sort_modifiers,
            "filters": self._filter_modifiers,
        }.get(kind, {})
        output = list(items or [])
        for cls in reversed(type(self).mro()):
            for modifier in modifier_map.get(cls, ()):
                output = modifier(output, self)
        return output

    def search(self, criteria: ResourceSearchCriteria, context: ResourceContext):
        return None

    def validation_messages(self) -> dict[str, str]:
        return {}

    def validation_attributes(self) -> dict[str, str]:
        return {}

    def validation_factory(self):
        return None

    def mutate_data_before_validation(self, context: ResourceContext, data: dict) -> dict:
        return data

    def boot(self, registry: Any) -> "Resource":
        return self

    def serialize(self, instance: Any, context: ResourceContext) -> dict[str, Any]:
        return self.base(instance, context)

    def get_id(self, instance: Any, context: ResourceContext) -> str | None:
        value = getattr(instance, "id", None)
        if value is None:
            value = getattr(instance, "pk", None)
        if value is None:
            value = self.base(instance, context).get("id")
        if value is None:
            return None
        return str(value)

    def resource_for(self, instance: Any, context: ResourceContext) -> str | None:
        return None

    def can(self, user: Any, ability: str, instance: Any | None, context: ResourceContext) -> bool:
        return True


class DatabaseResource(Resource):
    model = None

    def query(self, context: ResourceContext):
        if self.model is None:
            raise NotImplementedError("DatabaseResource.model must be set")
        return self.model.objects.all()

    def resource_for(self, instance: Any, context: ResourceContext) -> str | None:
        if self.model is None:
            return None
        try:
            if isinstance(instance, self.model):
                return self.type()
        except TypeError:
            return None
        return None

    def new_model(self, context: ResourceContext):
        if self.model is None:
            raise NotImplementedError("DatabaseResource.model must be set")
        return self.model()

    def scope(self, queryset, context: ResourceContext):
        return queryset

    def find(self, object_id: str, context: ResourceContext):
        return self.scope(self.query(context), context).filter(pk=object_id).first()

    def results(self, queryset, context: ResourceContext):
        return queryset

    def count(self, queryset, context: ResourceContext) -> int | None:
        count = getattr(queryset, "count", None)
        if callable(count):
            try:
                return count()
            except TypeError:
                pass
        try:
            return len(queryset)
        except TypeError:
            return None

    def paginate(self, queryset, context: ResourceContext):
        pagination = context.get("pagination") if isinstance(context, dict) else None
        if not isinstance(pagination, dict):
            return queryset
        limit = int(pagination.get("limit") or 20)
        offset = int(pagination.get("offset") or 0)
        take = getattr(queryset, "take", None)
        skip = getattr(queryset, "skip", None)
        if callable(take) and callable(skip):
            return skip(offset).take(limit)
        limit_method = getattr(queryset, "limit", None)
        offset_method = getattr(queryset, "offset", None)
        if callable(limit_method) and callable(offset_method):
            return limit_method(limit).offset(offset)
        try:
            return queryset[offset:offset + limit]
        except TypeError:
            return queryset

    def creating(self, instance: Any, context: ResourceContext):
        return instance

    def updating(self, instance: Any, context: ResourceContext):
        return instance

    def saving(self, instance: Any, context: ResourceContext):
        return instance

    def saved(self, instance: Any, context: ResourceContext):
        return instance

    def created(self, instance: Any, context: ResourceContext):
        return instance

    def updated(self, instance: Any, context: ResourceContext):
        return instance

    def deleting(self, instance: Any, context: ResourceContext) -> None:
        return None

    def deleted(self, instance: Any, context: ResourceContext) -> None:
        return None

    def create_action(self, instance: Any, context: ResourceContext):
        instance = self.creating(instance, context) or instance
        instance = self.saving(instance, context) or instance
        save = getattr(instance, "save", None)
        if callable(save):
            save()
        instance = self.saved(instance, context) or instance
        return self.created(instance, context) or instance

    def update_action(self, instance: Any, context: ResourceContext):
        instance = self.updating(instance, context) or instance
        instance = self.saving(instance, context) or instance
        save = getattr(instance, "save", None)
        if callable(save):
            save()
        instance = self.saved(instance, context) or instance
        return self.updated(instance, context) or instance

    def delete_action(self, instance: Any, context: ResourceContext) -> None:
        self.deleting(instance, context)
        delete = getattr(instance, "delete", None)
        if callable(delete):
            delete()
        self.deleted(instance, context)
