"""ResourceValidator — 校验流水线"""
from __future__ import annotations
from typing import Any
from apps.core.resource_errors import JsonApiValidationError
from apps.core.resource_objects import Resource
from apps.core.resource_validation import ResourceValidationError, ResourceValidatorFactory

class ResourceValidator:
    def __init__(self, store: Any):
        self._store = store


    def _run_validation_factory(self, resource_object: Resource | None, context: dict, data: dict) -> None:
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

    def _build_validation_payload(self, resource_object: Resource, context: dict, data: dict) -> dict:
        collected = self._collect_validation_state(resource_object, context)
        return {
            "attributes": data.get("attributes") or {},
            "relationships": data.get("relationships") or {},
            "rules": collected["rules"],
            "messages": collected["messages"],
            "validation_attributes": collected["validation_attributes"],
        }

    def _collect_validation_rules(self, resource_object: Resource, context: dict) -> dict:
        return self._collect_validation_state(resource_object, context)["rules"]

    def _collect_validation_state(self, resource_object: Resource, context: dict) -> dict:
        rules = {"attributes": {}, "relationships": {}}
        messages = dict(getattr(resource_object, "validation_messages", lambda: {})() or {})
        attributes = dict(getattr(resource_object, "validation_attributes", lambda: {})() or {})
        for definition in self._store.get_effective_fields(resource_object.type(), context):
            if not self._store._is_field_writable(definition, context.get("model"), context):
                continue
            self._merge_definition_validation_state(
                rules["attributes"],
                messages,
                attributes,
                definition,
                definition.field,
                context,
            )
        for definition in self._store.get_effective_relationships(resource_object.type(), context):
            if not self._store._is_field_writable(definition, context.get("model"), context):
                continue
            self._merge_definition_validation_state(
                rules["relationships"],
                messages,
                attributes,
                definition,
                definition.relationship,
                context,
            )
        return {
            "rules": rules,
            "messages": messages,
            "validation_attributes": attributes,
        }

    @staticmethod
    def _merge_definition_validation_state(
        rules: dict,
        messages: dict,
        attributes: dict,
        definition: Any,
        name: str,
        context: dict,
    ) -> None:
        field_object = getattr(definition, "field_object", None)
        object_rules = {}
        has_validation_rules = bool(getattr(definition, "has_validation_rules", False))
        used_field_object_rules = False
        if field_object is not None and has_validation_rules:
            get_rules = getattr(field_object, "get_validation_rules", None)
            if callable(get_rules):
                used_field_object_rules = True
                object_rules = get_rules(context) or {}
            get_messages = getattr(field_object, "get_validation_messages", None)
            if callable(get_messages):
                messages.update(get_messages(context) or {})
            get_attributes = getattr(field_object, "get_validation_attributes", None)
            if callable(get_attributes):
                attributes.update(get_attributes(context) or {})

        if object_rules:
            for key, values in object_rules.items():
                rules[str(key)] = tuple(values or ())
            return

        if used_field_object_rules:
            return

        if not has_validation_rules:
            return
        values = tuple(getattr(definition, "validation_rules", ()) or ())
        if values:
            rules[name] = values

    @staticmethod
    def _invoke_validation_factory_object(factory: Any, validation_payload: dict, data: dict, context: dict):
        make = getattr(factory, "make", None)
        if callable(make):
            errors = []
            for section in ("attributes", "relationships"):
                section_data = dict(validation_payload[section])
                other_section = "relationships" if section == "attributes" else "attributes"
                section_data[other_section] = validation_payload[other_section]
                try:
                    validator = make(
                        section_data,
                        validation_payload["rules"][section],
                        validation_payload["messages"],
                        validation_payload["validation_attributes"],
                        section=section,
                    )
                except TypeError:
                    validator = make(
                        section_data,
                        validation_payload["rules"][section],
                        validation_payload["messages"],
                        validation_payload["validation_attributes"],
                    )
                errors.extend(ResourceValidator._validator_errors(section, validator))
            return errors
        validate = getattr(factory, "validate", None)
        if callable(validate):
            try:
                return validate(validation_payload, context)
            except TypeError:
                return validate(data, context)
        return None

    @staticmethod
    def _validator_errors(section: str, validator: Any) -> list[dict]:
        if validator is None:
            return []
        if isinstance(validator, ResourceValidator):
            return validator.jsonapi_errors()
        fails = getattr(validator, "fails", None)
        if callable(fails) and not fails():
            return []
        jsonapi_errors = getattr(validator, "jsonapi_errors", None)
        if callable(jsonapi_errors):
            try:
                return list(jsonapi_errors(section=section))
            except TypeError:
                return list(jsonapi_errors())
        messages = getattr(validator, "messages", None)
        if callable(messages):
            output = []
            for field, values in (messages() or {}).items():
                if isinstance(values, str):
                    values = [values]
                output.append(ResourceValidationError(
                    field=str(field),
                    message=" ".join(str(item) for item in values),
                    section=section,
                ).as_jsonapi_error())
            return output
        if isinstance(validator, (list, tuple)):
            return ResourceValidator._normalize_validation_factory_errors(validator)
        if isinstance(validator, dict):
            return ResourceValidator._normalize_validation_factory_errors(validator)
        return []

    def _collect_payload_validation_errors(self, resource_object: Resource, context: dict, data: dict) -> list[dict]:
        errors: list[dict] = []
        validation_state = self._collect_validation_state(resource_object, context)
        messages = validation_state["messages"]
        attributes = validation_state["validation_attributes"]
        for definition in self._store.get_effective_fields(resource_object.type(), context):
            attributes_payload = data.get("attributes") or {}
            if definition.field not in attributes_payload:
                continue
            value = attributes_payload.get(definition.field)
            try:
                value = self._deserialize_resource_value(definition, value, context)
                self._validate_resource_value(definition, value, context)
            except JsonApiValidationError as exc:
                errors.append(ResourceValidator._validation_error_to_document(exc, definition, messages, attributes))
        for definition in self._store.get_effective_relationships(resource_object.type(), context):
            relationships_payload = data.get("relationships") or {}
            if definition.relationship not in relationships_payload:
                continue
            value = relationships_payload.get(definition.relationship)
            if isinstance(value, dict) and "data" in value:
                value = value["data"]
            try:
                value = self._deserialize_resource_value(definition, value, context)
                self._validate_resource_value(definition, value, context)
            except JsonApiValidationError as exc:
                errors.append(ResourceValidator._validation_error_to_document(exc, definition, messages, attributes))
        return errors

    @staticmethod
    def _validation_error_to_document(exc: JsonApiValidationError, definition: Any, messages: dict, attributes: dict) -> dict:
        pointer = getattr(exc, "pointer", "") or ResourceValidator._validation_pointer(definition)
        key = pointer.removeprefix("/data/attributes/").removeprefix("/data/relationships/")
        label = attributes.get(key, key)
        detail = messages.get(key) or messages.get(pointer) or str(exc)
        if label and key and label != key:
            detail = detail.replace(key, str(label))
        return {"source": {"pointer": pointer}, "detail": detail}

    @staticmethod
    def _normalize_validation_factory_errors(result: Any) -> list[dict]:
        errors = []
        if isinstance(result, dict):
            iterable = result.items()
        else:
            iterable = result
        for item in iterable:
            if isinstance(item, tuple) and len(item) == 2:
                field, message = item
                pointer = str(field)
                if not pointer.startswith("/"):
                    pointer = f"/data/attributes/{pointer}"
                errors.append({"source": {"pointer": pointer}, "detail": str(message)})
            elif isinstance(item, dict):
                errors.append(item)
            elif isinstance(item, ResourceValidationError):
                errors.append(item.as_jsonapi_error())
        return errors

    @staticmethod
    def _validate_resource_value(definition: Any, value: Any, context: dict) -> None:
        name = str(
            getattr(definition, "field", "")
            or getattr(definition, "relationship", "")
            or "value"
        )
        if value is None:
            if not bool(getattr(definition, "nullable", False)):
                raise JsonApiValidationError(f"{name} cannot be null", pointer=ResourceValidator._validation_pointer(definition))
            return
        field_object = getattr(definition, "field_object", None)
        validate = getattr(field_object, "validate", None)
        if callable(validate):
            try:
                validate(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceValidator._validation_pointer(definition)) from exc
            return
        for rule in getattr(definition, "validation_rules", ()) or ():
            ResourceValidator._validate_resource_rule(name, rule, value, context, definition)
        validator = getattr(definition, "validator", None)
        if validator is not None:
            try:
                validator(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(str(exc), pointer=ResourceValidator._validation_pointer(definition)) from exc

    @staticmethod
    def _validate_resource_rule(name: str, rule: Any, value: Any, context: dict, definition: Any = None) -> None:
        if callable(rule):
            try:
                rule(value, context)
            except ValueError as exc:
                raise JsonApiValidationError(
                    str(exc),
                    pointer=ResourceValidator._validation_pointer(definition),
                ) from exc
            return
        if isinstance(rule, str):
            ResourceValidator._validate_named_resource_rule(name, rule, value, definition=definition)
            return
        if not isinstance(rule, (tuple, list)) or not rule:
            return
        rule_name = str(rule[0] or "").strip()
        argument = rule[1] if len(rule) > 1 else None
        ResourceValidator._validate_named_resource_rule(name, rule_name, value, argument, definition=definition)

    @staticmethod
    def _validate_named_resource_rule(name: str, rule_name: str, value: Any, argument: Any = None, definition: Any = None) -> None:
        pointer = ResourceValidator._validation_pointer(definition)
        if rule_name == "email":
            if not isinstance(value, str) or "@" not in value:
                raise JsonApiValidationError(f"{name} must be a valid email", pointer=pointer)
            return
        if rule_name == "min":
            if value < argument:
                raise JsonApiValidationError(f"{name} must be at least {argument}", pointer=pointer)
            return
        if rule_name == "max":
            if value > argument:
                raise JsonApiValidationError(f"{name} must be at most {argument}", pointer=pointer)
            return
        if rule_name == "min_length":
            if len(value) < int(argument):
                raise JsonApiValidationError(f"{name} length must be at least {argument}", pointer=pointer)
            return
        if rule_name == "max_length":
            if len(value) > int(argument):
                raise JsonApiValidationError(f"{name} length must be at most {argument}", pointer=pointer)
            return
        if rule_name == "in":
            compared_value = str(value["id"]) if ResourceValidator._is_jsonapi_identifier(value) else value
            if compared_value not in set(argument or ()):
                raise JsonApiValidationError(f"{name} is invalid", pointer=pointer)
            return
        if rule_name == "regex":
            import re

            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                raise JsonApiValidationError(f"{name} format is invalid", pointer=pointer)

    @staticmethod
    def _validation_pointer(definition: Any) -> str:
        field = str(getattr(definition, "field", "") or "")
        if field:
            return f"/data/attributes/{field}"
        relationship = str(getattr(definition, "relationship", "") or "")
        if relationship:
            return f"/data/relationships/{relationship}"
        return "/data"
    @staticmethod
    def _is_jsonapi_identifier(value):
        return isinstance(value, dict) and "id" in value and "type" in value

