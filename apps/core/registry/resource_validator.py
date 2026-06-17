"""
ResourceValidator — 校验流水线
"""
from __future__ import annotations

from typing import Any

from apps.core.resource_errors import JsonApiValidationError
from apps.core.resource_objects import Resource
from apps.core.resource_validation import ResourceValidatorFactory


class ResourceValidator:
    def __init__(self, store: Any):
        self._store = store

    def _run_validation_factory(self, resource_object, context, data):
        if resource_object is None:
            return
        errors = self._collect_payload_validation_errors(resource_object, context, data)
        factory = getattr(resource_object, "validation_factory", lambda: None)()
        if factory is None:
            factory = ResourceValidatorFactory()
        result = None
        validation_payload = self._build_validation_payload(resource_object, context, data)
        try:
            result = factory(data, context, validation_payload)
        except TypeError:
            try:
                result = factory(data, context)
            except TypeError:
                result = self._invoke_validation_factory_object(factory, validation_payload, data, context)
        if result:
            errors.extend(self._normalize_validation_factory_errors(result))
        if errors:
            raise JsonApiValidationError("Validation failed", errors=errors)

    def _build_validation_payload(self, resource_object, context, data):
        collected = self._collect_validation_state(resource_object, context)
        return {
            "attributes": data.get("attributes") or {},
            "relationships": data.get("relationships") or {},
            "rules": collected["rules"],
            "messages": collected["messages"],
            "validation_attributes": collected["validation_attributes"],
        }

    def _collect_validation_rules(self, resource_object, context):
        return self._collect_validation_state(resource_object, context)["rules"]

    def _collect_validation_state(self, resource_object, context):
        rules = {"attributes": {}, "relationships": {}}
        messages = dict(getattr(resource_object, "validation_messages", lambda: {})() or {})
        attrs = dict(getattr(resource_object, "validation_attributes", lambda: {})() or {})
        for d in self._store.get_effective_fields(resource_object.type(), context):
            if not self._store._is_field_writable(d, context.get("model"), context):
                continue
            self._merge_definition_validation_state(rules["attributes"], messages, attrs, d, d.field, context)
        for d in self._store.get_effective_relationships(resource_object.type(), context):
            if not self._store._is_field_writable(d, context.get("model"), context):
                continue
            self._merge_definition_validation_state(rules["relationships"], messages, attrs, d, d.relationship, context)
        return {"rules": rules, "messages": messages, "validation_attributes": attrs}

    @staticmethod
    def _merge_definition_validation_state(rules, messages, attributes, definition, name, context):
        fo = getattr(definition, "field_object", None)
        object_rules = {}
        has_rules = bool(getattr(definition, "has_validation_rules", False))
        used_fo = False
        if fo is not None and has_rules:
            gr = getattr(fo, "get_validation_rules", None)
            if callable(gr):
                used_fo = True
                object_rules = gr(context) or {}
            gm = getattr(fo, "get_validation_messages", None)
            if callable(gm):
                messages.update(gm(context) or {})
            ga = getattr(fo, "get_validation_attributes", None)
            if callable(ga):
                attributes.update(ga(context) or {})
        if object_rules:
            for key, values in object_rules.items():
                rules[str(key)] = tuple(values or ())
            return
        if used_fo:
            return
        if not has_rules:
            return
        for item in getattr(definition, "validation_rules", ()) or ():
            k = name
            v = rules.setdefault(k, [])
            if isinstance(item, (list, tuple)) and len(item) == 2:
                v.append(tuple(item))
            else:
                v.append(item)

    @staticmethod
    def _invoke_validation_factory_object(factory, validation_payload, data, context):
        if hasattr(factory, "validate"):
            try:
                return factory.validate(data, context, validation_payload)
            except TypeError:
                return factory.validate(data, context)
        if callable(factory):
            return factory(data, context, validation_payload)
        return None

    @staticmethod
    def _validator_errors(section, validator):
        if hasattr(validator, "validate"):
            try:
                result = validator.validate({})
            except Exception:
                return []
            if isinstance(result, list):
                return [dict(item) for item in result if isinstance(item, dict)]
            if isinstance(result, dict):
                return [dict(result)]
        return []

    def _collect_payload_validation_errors(self, resource_object, context, data):
        errors = []
        collected = self._collect_validation_state(resource_object, context)
        messages = collected["messages"]
        attributes = collected["validation_attributes"]
        for section in ("attributes", "relationships"):
            for name, rules in collected["rules"].get(section, {}).items():
                if not rules:
                    continue
                for rule in rules:
                    if isinstance(rule, (list, tuple)) and len(rule) >= 2:
                        rule_name, rule_args = rule[0], rule[1]
                        value = data.get(section, {}).get(name) if isinstance(data.get(section), dict) else None
                        try:
                            ResourceValidator._validate_resource_rule(name, rule, value, context)
                        except JsonApiValidationError as exc:
                            errors.append(ResourceValidator._validation_error_to_document(exc, None, messages, attributes))
        validator = getattr(resource_object, "validator", None)
        if validator is not None:
            for item in ResourceValidator._validator_errors(section, validator):
                if isinstance(item, dict):
                    errors.append(item)
        return errors

    @staticmethod
    def _validation_error_to_document(exc, definition, messages, attributes):
        pointer = getattr(exc, "pointer", "") or ""
        key = pointer.removeprefix("/data/attributes/").removeprefix("/data/relationships/")
        label = attributes.get(key, key)
        message = str(exc)
        msg_key = messages.get(key) or messages.get(label)
        if msg_key:
            message = msg_key
        return {"code": "validation_error", "detail": message, "source": {"pointer": pointer}}

    @staticmethod
    def _normalize_validation_factory_errors(result):
        if result is None:
            return []
        if isinstance(result, list):
            return [dict(item) if isinstance(item, dict) else {"detail": str(item)} for item in result]
        if isinstance(result, dict):
            return [dict(result)]
        return [{"detail": str(result)}]

    @staticmethod
    def _validate_resource_value(definition, value, context):
        name = str(getattr(definition, "field", "") or getattr(definition, "relationship", "") or "value")
        if value is None:
            if not bool(getattr(definition, "nullable", False)):
                raise JsonApiValidationError(f"{name} cannot be null", pointer=ResourceValidator._validation_pointer(definition))
            return
        fo = getattr(definition, "field_object", None)
        vl = getattr(fo, "validate", None)
        if callable(vl):
            try:
                vl(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceValidator._validation_pointer(definition)) from exc
            return
        for rule in getattr(definition, "validation_rules", ()) or ():
            ResourceValidator._validate_resource_rule(name, rule, value, context, definition)
        v = getattr(definition, "validator", None)
        if v is not None:
            try:
                v(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceValidator._validation_pointer(definition)) from exc

    @staticmethod
    def _validate_resource_rule(name, rule, value, context, definition=None):
        if callable(rule):
            try:
                rule(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc)) from exc
            return
        if isinstance(rule, str):
            ResourceValidator._validate_named_resource_rule(name, rule, value)
            return
        if isinstance(rule, (tuple, list)) and rule:
            rule_name = str(rule[0] or "").strip()
            argument = rule[1] if len(rule) > 1 else None
            ResourceValidator._validate_named_resource_rule(name, rule_name, value, argument)

    @staticmethod
    def _validate_named_resource_rule(name, rule_name, value, argument=None):
        if rule_name == "email":
            if not isinstance(value, str) or "@" not in value:
                raise JsonApiValidationError(f"{name} must be a valid email")
        elif rule_name == "min":
            if value < argument:
                raise JsonApiValidationError(f"{name} must be at least {argument}")
        elif rule_name == "max":
            if value > argument:
                raise JsonApiValidationError(f"{name} must be at most {argument}")
        elif rule_name == "min_length":
            if len(value) < int(argument):
                raise JsonApiValidationError(f"{name} length must be at least {argument}")
        elif rule_name == "max_length":
            if len(value) > int(argument):
                raise JsonApiValidationError(f"{name} length must be at most {argument}")
        elif rule_name == "in":
            compared = str(value["id"]) if isinstance(value, dict) and "id" in value and "type" in value else value
            if compared not in set(argument or ()):
                raise JsonApiValidationError(f"{name} is invalid")
        elif rule_name == "regex":
            import re
            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                raise JsonApiValidationError(f"{name} format is invalid")

    @staticmethod
    def _validation_pointer(definition):
        field = str(getattr(definition, "field", "") or "")
        if field:
            return f"/data/attributes/{field}"
        rel = str(getattr(definition, "relationship", "") or "")
        if rel:
            return f"/data/relationships/{rel}"
        return "/data"
