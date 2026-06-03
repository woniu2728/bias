from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResourceValidationError:
    field: str
    message: str
    section: str = "attributes"

    @property
    def pointer(self) -> str:
        field = str(self.field or "").strip()
        if field.startswith("/"):
            return field
        section = str(self.section or "attributes").strip() or "attributes"
        return f"/data/{section}/{field}" if field else f"/data/{section}"

    def as_jsonapi_error(self) -> dict:
        return {"source": {"pointer": self.pointer}, "detail": self.message}


class ResourceValidator:
    def __init__(self, errors: list[ResourceValidationError | dict] | None = None) -> None:
        self.errors = list(errors or [])

    def fails(self) -> bool:
        return bool(self.errors)

    def messages(self) -> dict[str, list[str]]:
        output: dict[str, list[str]] = {}
        for error in self.errors:
            if isinstance(error, ResourceValidationError):
                output.setdefault(error.field, []).append(error.message)
            elif isinstance(error, dict):
                pointer = str((error.get("source") or {}).get("pointer") or "")
                field = pointer.rsplit("/", 1)[-1] if pointer else "value"
                output.setdefault(field, []).append(str(error.get("detail") or "Validation failed"))
        return output

    def jsonapi_errors(self, section: str | None = None) -> list[dict]:
        output = []
        for error in self.errors:
            if isinstance(error, ResourceValidationError):
                if section and not str(error.field or "").startswith("/"):
                    error = ResourceValidationError(error.field, error.message, section=section)
                output.append(error.as_jsonapi_error())
            else:
                output.append(dict(error))
        return output


class ResourceValidatorFactory:
    def make(
        self,
        data: dict,
        rules: dict,
        messages: dict | None = None,
        attributes: dict | None = None,
        section: str = "attributes",
    ) -> ResourceValidator:
        messages = messages or {}
        attributes = attributes or {}
        errors: list[ResourceValidationError] = []
        for field, field_rules in (rules or {}).items():
            for resolved_field, value in self._field_values(data or {}, str(field)):
                for rule in field_rules or ():
                    message = self._validate_rule(resolved_field, value, rule, messages, attributes, data or {})
                    if message:
                        errors.append(ResourceValidationError(field=str(resolved_field), message=message, section=section))
        return ResourceValidator(errors)

    def _validate_rule(self, field: str, value: Any, rule: Any, messages: dict, attributes: dict, data: dict) -> str:
        if callable(rule):
            try:
                rule(value, {})
            except ValueError as exc:
                return str(exc)
            return ""
        if isinstance(rule, str):
            name, separator, raw_argument = rule.partition(":")
            argument = raw_argument if separator else None
        elif isinstance(rule, (tuple, list)) and rule:
            name = str(rule[0] or "")
            argument = rule[1] if len(rule) > 1 else None
        else:
            return ""
        label = attributes.get(field, field)
        custom = messages.get(field) or messages.get(f"{field}.{name}")
        if name == "nullable" and value is None:
            return ""
        if name == "required" and self._is_empty(value):
            return custom or f"{label} is required"
        if name == "required_without":
            missing = True
            for dependency in self._as_iterable(argument):
                dependency_value = self._lookup_dependency(data, dependency)
                if not self._is_empty(dependency_value):
                    missing = False
                    break
            if missing and self._is_empty(value):
                return custom or f"{label} is required"
        if name == "required_with":
            present = False
            for dependency in self._as_iterable(argument):
                dependency_value = self._lookup_dependency(data, dependency)
                if not self._is_empty(dependency_value):
                    present = True
                    break
            if present and self._is_empty(value):
                return custom or f"{label} is required"
        if self._is_empty(value):
            return ""
        if name == "string" and not isinstance(value, str):
            return custom or f"{label} must be a string"
        if name == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return custom or f"{label} must be an integer"
        if name == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            return custom or f"{label} must be a number"
        if name == "boolean" and not isinstance(value, bool):
            return custom or f"{label} must be a boolean"
        if name == "array" and not isinstance(value, list):
            return custom or f"{label} must be an array"
        if name == "object" and not isinstance(value, dict):
            return custom or f"{label} must be an object"
        if name == "email" and (not isinstance(value, str) or "@" not in value):
            return custom or f"{label} must be a valid email"
        if name == "size" and value is not None:
            try:
                actual = len(value) if hasattr(value, "__len__") and not isinstance(value, (int, float)) else value
                failed = actual != self._numeric_argument(argument)
            except (TypeError, ValueError):
                return ""
            if failed:
                return custom or f"{label} size must be {argument}"
        if name == "min" and value is not None:
            try:
                actual = len(value) if hasattr(value, "__len__") and not isinstance(value, (int, float)) else value
                failed = actual < self._numeric_argument(argument)
            except (TypeError, ValueError):
                return ""
            if failed:
                return custom or f"{label} must be at least {argument}"
        if name == "max" and value is not None:
            try:
                actual = len(value) if hasattr(value, "__len__") and not isinstance(value, (int, float)) else value
                failed = actual > self._numeric_argument(argument)
            except (TypeError, ValueError):
                return ""
            if failed:
                return custom or f"{label} must be at most {argument}"
        if name == "min_length" and value is not None and len(value) < int(argument):
            return custom or f"{label} length must be at least {argument}"
        if name == "max_length" and value is not None and len(value) > int(argument):
            return custom or f"{label} length must be at most {argument}"
        compared_value = self._comparable_value(value)
        if name == "in" and compared_value not in set(argument or ()):
            return custom or f"{label} is invalid"
        if name in {"not_in", "notIn"} and compared_value in set(argument or ()):
            return custom or f"{label} is invalid"
        if name == "same" and compared_value != self._comparable_value(self._lookup_dependency(data, argument)):
            return custom or f"{label} must match {argument}"
        if name == "different" and compared_value == self._comparable_value(self._lookup_dependency(data, argument)):
            return custom or f"{label} must be different from {argument}"
        if name in {"unique", "exists"}:
            message = self._validate_queryset_rule(name, field, value, argument, custom, label)
            if message:
                return message
        if name == "regex":
            import re

            if not isinstance(value, str) or re.search(str(argument or ""), value) is None:
                return custom or f"{label} format is invalid"
        return ""

    @staticmethod
    def _numeric_argument(argument: Any) -> Any:
        if isinstance(argument, str):
            try:
                return int(argument)
            except ValueError:
                return float(argument)
        return argument

    def _validate_queryset_rule(
        self,
        name: str,
        field: str,
        value: Any,
        argument: Any,
        custom: str | None,
        label: str,
    ) -> str:
        model = None
        lookup_field = field
        ignore_value = None
        if isinstance(argument, dict):
            model = argument.get("model")
            lookup_field = argument.get("field") or lookup_field
            ignore_value = argument.get("ignore")
        elif isinstance(argument, (tuple, list)):
            model = argument[0] if len(argument) > 0 else None
            lookup_field = argument[1] if len(argument) > 1 and argument[1] else lookup_field
            ignore_value = argument[2] if len(argument) > 2 else None
        if model is None:
            return ""
        objects = getattr(model, "objects", None)
        filter_method = getattr(objects, "filter", None)
        if not callable(filter_method):
            return ""
        try:
            queryset = filter_method(**{str(lookup_field): self._comparable_value(value)})
            if ignore_value is not None:
                exclude = getattr(queryset, "exclude", None)
                if callable(exclude):
                    queryset = exclude(pk=ignore_value)
            exists = getattr(queryset, "exists", None)
            present = bool(exists()) if callable(exists) else bool(queryset)
        except Exception:
            return ""
        if name == "unique" and present:
            return custom or f"{label} has already been taken"
        if name == "exists" and not present:
            return custom or f"{label} is invalid"
        return ""

    @staticmethod
    def _comparable_value(value: Any) -> Any:
        if isinstance(value, dict) and "data" in value:
            return ResourceValidatorFactory._comparable_value(value["data"])
        if isinstance(value, dict) and "type" in value and "id" in value:
            return str(value["id"])
        return value

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @staticmethod
    def _as_iterable(value: Any):
        if value is None:
            return ()
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, (tuple, list, set)):
            return tuple(value)
        return (value,)

    @staticmethod
    def _lookup_dependency(data: dict, dependency: Any) -> Any:
        current = data or {}
        path = str(dependency or "").strip()
        if not path:
            return None
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if index >= len(current):
                    return None
                current = current[index]
            else:
                return None
        return current

    @classmethod
    def _field_values(cls, data: dict, field: str):
        if "*" not in field:
            return ((field, cls._lookup_dependency(data, field)),)
        output: list[tuple[str, Any]] = []

        def walk(current: Any, parts: list[str], path: list[str]) -> None:
            if not parts:
                output.append((".".join(path), current))
                return
            part = parts[0]
            rest = parts[1:]
            if part == "*":
                if isinstance(current, list):
                    for index, item in enumerate(current):
                        walk(item, rest, [*path, str(index)])
                elif isinstance(current, dict):
                    for key, item in current.items():
                        walk(item, rest, [*path, str(key)])
                else:
                    output.append((".".join([*path, "*"]), None))
                return
            if isinstance(current, dict):
                walk(current.get(part), rest, [*path, part])
                return
            if isinstance(current, list) and part.isdigit():
                index = int(part)
                walk(current[index] if index < len(current) else None, rest, [*path, part])
                return
            walk(None, rest, [*path, part])

        walk(data or {}, field.split("."), [])
        return tuple(output)
