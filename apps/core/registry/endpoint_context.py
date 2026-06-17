"""
EndpointContextResolver — 端点上下文+验证
"""
from __future__ import annotations

from typing import Any

from apps.core.resource_context import ensure_resource_context
from apps.core.resource_definitions import ResourceEndpointDefinition
from apps.core.resource_errors import BadJsonApiRequest, JsonApiConflict, JsonApiForbidden, JsonApiValidationError


class EndpointContextResolver:
    def __init__(self, store: Any):
        self._store = store

    def dispatch_resource_endpoint(self, definition, context):
        from apps.core.resource_endpoint_runner import ResourceEndpointRunner
        return ResourceEndpointRunner(self._store).run(definition, ensure_resource_context(context))

    def apply_resource_payload(self, resource, instance, payload, context=None, *, creating=False):
        ctx = dict(context or {})
        ctx["creating"] = bool(creating)
        inp = dict(payload or {})
        self._run_extension_validators(resource, instance, inp, ctx)
        fields = {d.field: d for d in self._store.get_effective_fields(resource, ctx)}
        rels = {d.relationship: d for d in self._store.get_effective_relationships(resource, ctx)}
        missing = [d.field for d in fields.values() if ((creating and d.required_on_create) or (not creating and d.required_on_update)) and d.field not in inp]
        if missing:
            raise JsonApiValidationError(f"缺少必填字段: {', '.join(missing)}", pointer=f"/data/attributes/{missing[0]}")
        for fn, v in inp.items():
            d = fields.get(fn)
            if not d:
                continue
            if not self._store._is_field_writable(d, instance, ctx):
                raise JsonApiForbidden(f"字段不可写: {fn}", pointer=f"/data/attributes/{fn}")
            v = EndpointContextResolver._deserialize_value(d, v, ctx)
            EndpointContextResolver._validate_field(d, v, ctx)
            self._store._set_resource_value(d, instance, v, ctx)
        rp = EndpointContextResolver._extract_relationship_payload(context)
        mr = [d.relationship for d in rels.values() if ((creating and d.required_on_create) or (not creating and d.required_on_update)) and d.relationship not in rp]
        if mr:
            raise JsonApiValidationError(f"缺少必填关系: {', '.join(mr)}", pointer=f"/data/relationships/{mr[0]}")
        for rn, v in rp.items():
            d = rels.get(rn)
            if not d:
                continue
            if not self._store._is_field_writable(d, instance, ctx):
                raise JsonApiForbidden(f"关系不可写: {rn}", pointer=f"/data/relationships/{rn}")
            v = EndpointContextResolver._deserialize_value(d, v, ctx)
            EndpointContextResolver._validate_field(d, v, ctx)
            self._store._set_resource_value(d, instance, v, ctx)
        return instance

    def _run_extension_validators(self, resource, instance, payload, context):
        try:
            from apps.core.extensions.bootstrap import get_extension_host
        except Exception:
            return
        host = get_extension_host()
        if not host:
            return
        vd = getattr(host, "validators", None)
        if not vd:
            return
        tk = [resource]
        if instance is not None:
            tk.extend([instance.__class__, f"{instance.__class__.__module__}.{instance.__class__.__qualname__}"])
        seen = set()
        for t in tk:
            for d in vd.get_definitions(target=t):
                k = (d.module_id, d.key, d.target)
                if k not in seen:
                    seen.add(k)
                    try:
                        d.callback({"resource": resource, "instance": instance, "payload": payload, "context": context, "creating": bool(context.get("creating"))}, context)
                    except JsonApiValidationError:
                        raise
                    except ValueError as exc:
                        raise JsonApiValidationError(str(exc), pointer="/data/attributes") from exc

    def _parse_jsonapi_data(self, context, resource, creating=False, instance=None, resource_object=None):
        p = context.get("payload") or {}
        data = p.get("data") if isinstance(p, dict) else None
        jt = str(data.get("type") or "") if isinstance(data, dict) else ""
        if jt and jt != resource:
            raise JsonApiConflict(f"类型不匹配: 期望 {resource}，收到 {jt}")
        if not isinstance(data, dict):
            raise BadJsonApiRequest("请求体必须包含 data 对象")

    def apply_named_sort(self, resource, queryset, sort, context=None):
        normalized = str(sort or "").strip()
        if not normalized:
            return queryset
        ctx = dict(context or {})
        descending = normalized.startswith("-")
        sn = normalized[1:] if descending else normalized
        for d in self._store.get_effective_sorts(resource, ctx):
            if d.sort != sn:
                continue
            h = d.handler
            sc = {**ctx, "sort": sn, "descending": descending}
            if callable(h):
                return h(queryset, sc)
            if isinstance(h, (list, tuple)):
                return queryset.order_by(*EndpointContextResolver._sort_order_fields(h, descending))
            if isinstance(h, str) and h.strip():
                f = h.strip()
                if descending and not f.startswith("-"):
                    f = f"-{f}"
                return queryset.order_by(f)
        return queryset

    def has_named_sort(self, resource, sort, context=None):
        normalized = str(sort or "").strip()
        if not normalized:
            return False
        ctx = dict(context or {})
        for d in self._store.get_effective_sorts(resource, ctx):
            if d.sort != normalized:
                continue
            h = d.handler
            if callable(h):
                return True
            if isinstance(h, (list, tuple)) and h:
                return True
            if isinstance(h, str) and h.strip():
                return True
        return False

    def apply_resource_filters(self, resource, queryset, filters, context=None):
        if not filters:
            return queryset
        ctx = dict(context or {})
        av = {}
        for d in self._store.get_effective_filters(resource, ctx):
            if self._store._is_filter_visible(d, ctx):
                av[d.filter] = d
        output = queryset
        for name, value in (filters or {}).items():
            nm = str(name or "").strip()
            if nm == "q":
                output = self._apply_default_fulltext(resource, output, value, ctx)
                continue
            neg = nm.startswith("-")
            fn = nm[1:] if neg else nm
            d = av.get(fn)
            if not d:
                raise BadJsonApiRequest(f"无效的过滤条件: {fn}", parameter=f"filter[{fn}]")
            output = d.handler(output, value, {**ctx, "filter": fn, "negate": neg})
        return output

    def _apply_default_fulltext(self, resource, queryset, value, context):
        q = str(value or "").strip()
        if not q:
            return queryset
        fields = [d.field for d in self._store.get_effective_fields(resource, context) if str(getattr(d, "value_type", "") or "").strip().lower() in {"", "string"}]
        if not fields:
            return queryset
        try:
            from django.db.models import Q
        except Exception:
            return queryset
        c = Q()
        for f in fields:
            c |= Q(**{f"{f}__icontains": q})
        return queryset.filter(c) if c else queryset

    def _ensure_resource_ability(self, resource_object, definition, instance, context):
        ability = getattr(definition, "ability", None)
        if ability is not None:
            resource_object.ensure_ability(instance, ability, context)

    def _resolve_endpoint_filters(self, context):
        q = context.get("query") or {}
        r = context.get("resource", "")
        ctx = dict(context or {})
        av = {}
        for d in self._store.get_effective_filters(r, ctx):
            if self._store._is_filter_visible(d, ctx):
                av[d.filter] = d
        output = {}
        for name, value in (q.get("filter") or {}).items():
            nm = str(name or "").strip()
            if nm == "q":
                output[nm] = value
                continue
            neg = nm.startswith("-")
            fn = nm[1:] if neg else nm
            d = av.get(fn)
            if not d:
                raise BadJsonApiRequest(f"无效的过滤条件: {fn}", parameter=f"filter[{fn}]")
            output[nm] = d.handler(None, value, {**ctx, "filter": fn, "negate": neg})
        return output

    @staticmethod
    def _extract_resource_payload(context):
        context = context or {}
        payload = context.get("payload") or {}
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            if payload:
                raise BadJsonApiRequest("data must be an object", pointer="/data")
            return {}
        data = payload["data"]
        if isinstance(data.get("attributes"), dict):
            return dict(data["attributes"])
        return {}

    @staticmethod
    def _extract_relationship_payload(context):
        context = context or {}
        payload = context.get("payload") or {}
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return {}
        relationships = payload["data"].get("relationships")
        if not isinstance(relationships, dict):
            return {}
        output = {}
        for name, value in relationships.items():
            if isinstance(value, dict) and "data" in value:
                output[name] = value["data"]
            else:
                output[name] = value
        return output

    @staticmethod
    def _call_endpoint_before(definition, context):
        h = getattr(definition, "before_hook", None)
        if h is not None:
            h(context)

    @staticmethod
    def _call_endpoint_after(definition, context, value):
        h = getattr(definition, "after_hook", None)
        if h is not None:
            return h(context, value)
        return value

    @staticmethod
    def _resolve_endpoint_meta(definition, context, value):
        r = getattr(definition, "meta_resolver", None)
        return dict(r(context, value) or {}) if r is not None else {}

    @staticmethod
    def _resolve_endpoint_links(definition, context, value):
        r = getattr(definition, "links_resolver", None)
        return dict(r(context, value) or {}) if r is not None else {}

    @staticmethod
    def _merge_endpoint_document_meta_links(document, definition, context, instance):
        meta = EndpointContextResolver._resolve_endpoint_meta(definition, context, instance)
        links = EndpointContextResolver._resolve_endpoint_links(definition, context, instance)
        if meta:
            document.setdefault("meta", {}).update(meta)
        if links:
            document["links"] = links

    @staticmethod
    def _resolve_endpoint_include(definition, context):
        q = context.get("query") or {}
        inc = str(q.get("include") or "").strip()
        if inc:
            return tuple(i.strip() for i in inc.split(",") if i.strip())
        return tuple(definition.default_include or ())

    @staticmethod
    def _resolve_endpoint_sort(definition, context):
        q = context.get("query") or {}
        return str(q.get("sort") or definition.default_sort or "").strip()

    @staticmethod
    def _resolve_endpoint_pagination(definition, context):
        if not definition.paginate:
            return None
        query = context.get("query") if isinstance(context.get("query"), dict) else {}
        default_limit = max(1, int(definition.pagination_default_limit or 20))
        max_limit = max(1, int(definition.pagination_max_limit or default_limit))
        raw_limit = query.get("page[limit]", default_limit)
        raw_offset = query.get("page[offset]", None)
        raw_page_number = query.get("page[number]", None)

        limit = EndpointContextResolver._parse_non_negative_int(raw_limit, "page[limit]")
        if limit < 1:
            raise ValueError("page[limit] must be at least 1")
        limit = min(limit, max_limit)

        if raw_page_number not in (None, ""):
            page_number = EndpointContextResolver._parse_non_negative_int(raw_page_number, "page[number]")
            if page_number < 1:
                raise ValueError("page[number] must be at least 1")
            offset = (page_number - 1) * limit
        else:
            offset = EndpointContextResolver._parse_non_negative_int(raw_offset or 0, "page[offset]")
        return {"limit": limit, "offset": offset}

    @staticmethod
    def _parse_non_negative_int(value, name):
        try:
            output = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer")
        if output < 0:
            raise ValueError(f"{name} must be at least 0")
        return output

    @staticmethod
    def _sort_order_fields(fields, descending):
        output = []
        for field in fields:
            normalized = str(field or "").strip()
            if not normalized:
                continue
            if descending and not normalized.startswith("-"):
                normalized = f"-{normalized}"
            output.append(normalized)
        return output

    @staticmethod
    def _validate_field(definition, value, context):
        """Validate a field value against its definition."""
        if value is None:
            if not bool(getattr(definition, "nullable", False)):
                raise JsonApiValidationError(
                    f"{getattr(definition, 'field', 'value')} cannot be null",
                    pointer=EndpointContextResolver._validation_pointer(definition))
            return
        fo = getattr(definition, "field_object", None)
        vl = getattr(fo, "validate", None)
        if callable(vl):
            try:
                vl(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=EndpointContextResolver._validation_pointer(definition)) from exc
            return
        # Check value type
        vt = str(getattr(definition, "value_type", "") or "").strip().lower()
        name = str(getattr(definition, "field", "") or getattr(definition, "relationship", "") or "value")
        if vt in {"", "any"}:
            pass
        elif vt == "string" and not isinstance(value, str):
            raise JsonApiValidationError(f"{name} must be a string", pointer=EndpointContextResolver._validation_pointer(definition))
        elif vt == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise JsonApiValidationError(f"{name} must be a number", pointer=EndpointContextResolver._validation_pointer(definition))
        elif vt == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise JsonApiValidationError(f"{name} must be an integer", pointer=EndpointContextResolver._validation_pointer(definition))
        elif vt == "boolean" and not isinstance(value, bool):
            raise JsonApiValidationError(f"{name} must be a boolean", pointer=EndpointContextResolver._validation_pointer(definition))
        # Rules and validator
        for r in getattr(definition, "validation_rules", ()) or ():
            EndpointContextResolver._validate_rule(name, r, value, context, definition)
        v = getattr(definition, "validator", None)
        if v is not None:
            try:
                v(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=EndpointContextResolver._validation_pointer(definition)) from exc

    @staticmethod
    def _validate_rule(name, rule, value, context, definition=None):
        if callable(rule):
            try:
                rule(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=EndpointContextResolver._validation_pointer(definition)) from exc
            return
        if isinstance(rule, str):
            EndpointContextResolver._validate_named(name, rule, value, definition=definition)
            return
        if isinstance(rule, (tuple, list)) and rule:
            EndpointContextResolver._validate_named(name, str(rule[0] or "").strip(), value,
                                                     rule[1] if len(rule) > 1 else None, definition=definition)

    @staticmethod
    def _validate_named(name, rule_name, value, argument=None, definition=None):
        p = EndpointContextResolver._validation_pointer(definition)
        if rule_name == "email":
            if not isinstance(value, str) or "@" not in value:
                raise JsonApiValidationError(f"{name} must be a valid email", pointer=p)
        elif rule_name == "min" and value < argument:
            raise JsonApiValidationError(f"{name} must be at least {argument}", pointer=p)
        elif rule_name == "max" and value > argument:
            raise JsonApiValidationError(f"{name} must be at most {argument}", pointer=p)
        elif rule_name == "min_length" and len(value) < int(argument):
            raise JsonApiValidationError(f"{name} length must be at least {argument}", pointer=p)
        elif rule_name == "max_length" and len(value) > int(argument):
            raise JsonApiValidationError(f"{name} length must be at most {argument}", pointer=p)
        elif rule_name == "in":
            cv = str(value["id"]) if EndpointContextResolver._is_jsonapi_id(value) else value
            if cv not in set(argument or ()):
                raise JsonApiValidationError(f"{name} is invalid", pointer=p)
        elif rule_name == "regex":
            import re
            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                raise JsonApiValidationError(f"{name} format is invalid", pointer=p)

    @staticmethod
    def _validation_pointer(definition):
        f = str(getattr(definition, "field", "") or "")
        if f:
            return f"/data/attributes/{f}"
        r = str(getattr(definition, "relationship", "") or "")
        if r:
            return f"/data/relationships/{r}"
        return "/data"

    @staticmethod
    def _is_jsonapi_id(value):
        return isinstance(value, dict) and "id" in value and "type" in value

    @staticmethod
    def _deserialize_value(definition, value, context):
        if value is None:
            return None
        fo = getattr(definition, "field_object", None)
        ds = getattr(fo, "deserialize", None)
        if callable(ds):
            try:
                return ds(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=EndpointContextResolver._validation_pointer(definition)) from exc
        return value
