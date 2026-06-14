from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from apps.core.extensions.types import (
    ExtensionMailDefinition,
    ExtensionSignalDefinition,
    ExtensionSystemHookDefinition,
    ExtensionValidatorDefinition,
    ExtensionViewNamespaceDefinition,
)


class ApplicationValidatorService:
    def __init__(self, host) -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionValidatorDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionValidatorDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).validators = definitions

    def get_definitions(self, *, extension_id: str | None = None, target: Any = "") -> list[ExtensionValidatorDefinition]:
        if extension_id is not None:
            definitions = list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._definitions_by_extension.values():
                definitions.extend(items)
        target_keys = self._target_keys(target)
        if target_keys:
            definitions = [definition for definition in definitions if definition.target in target_keys]
        return definitions

    def run(self, target: Any, payload: dict, context: dict | None = None) -> list[Any]:
        resolved_context = dict(context or {})
        results = []
        for definition in self.get_definitions(target=target):
            results.append(definition.callback(payload, resolved_context))
        return results

    @staticmethod
    def _target_keys(target: Any) -> set[str]:
        if target is None:
            return set()
        if isinstance(target, str):
            return {target.strip()} if target.strip() else set()
        keys = {
            str(target).strip(),
            str(getattr(target, "__name__", "") or "").strip(),
            str(getattr(target, "__qualname__", "") or "").strip(),
            f"{getattr(target, '__module__', '')}.{getattr(target, '__qualname__', '')}".strip("."),
        }
        return {key for key in keys if key}


class ApplicationMailService:
    def __init__(self, host) -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionMailDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionMailDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).mailers = definitions

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionMailDefinition]:
        if extension_id is not None:
            return list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionMailDefinition] = []
        for items in self._definitions_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_driver(self, key: str) -> ExtensionMailDefinition | None:
        normalized = str(key or "").strip().lower()
        if not normalized:
            return None
        for definition in self.get_definitions():
            if str(definition.key or "").strip().lower() == normalized:
                return definition
        return None

    def send(self, key: str, message: dict, context: dict | None = None) -> Any:
        definition = self.get_driver(key)
        if definition is None or not callable(definition.callback):
            return None
        return definition.callback(message, dict(context or {}))


class ApplicationViewService:
    def __init__(self, host) -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionViewNamespaceDefinition, ...]] = {}

    def namespace(self, extension_id: str, definition: ExtensionViewNamespaceDefinition) -> None:
        normalized = str(extension_id or "").strip()
        namespace = str(definition.namespace or "").strip()
        hints = tuple(str(item or "").strip() for item in definition.hints if str(item or "").strip())
        if not normalized or not namespace or not hints:
            return
        definition = replace(
            definition,
            namespace=namespace,
            hints=tuple(self._normalize_hint(item, extension_id=normalized) for item in hints),
            module_id=definition.module_id or normalized,
        )
        current = tuple(
            item for item in self._definitions_by_extension.get(normalized, ())
            if not (
                item.namespace == definition.namespace
                and item.module_id == definition.module_id
                and bool(getattr(item, "prepend", False)) == bool(getattr(definition, "prepend", False))
            )
        )
        definitions = tuple([*current, definition])
        self._definitions_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).view_namespaces = tuple(
            self.get_namespaces(extension_id=normalized)
        )

    def get_namespaces(self, *, extension_id: str | None = None) -> list[ExtensionViewNamespaceDefinition]:
        if extension_id is not None:
            definitions = list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._definitions_by_extension.values():
                definitions.extend(items)
        return sorted(
            definitions,
            key=lambda item: (
                not bool(getattr(item, "prepend", False)),
                int(item.order or 100),
                item.module_id,
                item.namespace,
            ),
        )

    def get_namespace_hints(self, namespace: str) -> list[str]:
        normalized = str(namespace or "").strip()
        if not normalized:
            return []
        hints: list[str] = []
        for definition in self.get_namespaces():
            if definition.namespace == normalized:
                hints.extend(definition.hints)
        return list(dict.fromkeys(hints))

    def resolve_template_path(self, template_name: str) -> Path:
        namespace, name = self._split_template_name(template_name)
        for hint in self.get_namespace_hints(namespace):
            candidate = (Path(hint) / name).resolve()
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(f"扩展模板不存在: {template_name}")

    def get_template(self, template_name: str):
        from django.template.loader import get_template

        return get_template(template_name)

    def render(self, template_name: str, context: dict | None = None, *, request: Any = None) -> str:
        return self.get_template(template_name).render(context=dict(context or {}), request=request)

    def _normalize_hint(self, hint: str, *, extension_id: str) -> str:
        path = Path(str(hint or "").strip())
        if path.is_absolute():
            return str(path)

        extension_view = self._host.get_runtime_view(extension_id)
        extension_path = str(getattr(extension_view, "path", "") or "").strip()
        if extension_path:
            candidate = Path(extension_path) / path
            if candidate.exists():
                return str(candidate.resolve())

        from django.conf import settings

        return str((Path(settings.BASE_DIR) / path).resolve())

    def _split_template_name(self, template_name: str) -> tuple[str, str]:
        raw = str(template_name or "").strip()
        if "::" not in raw:
            raise ValueError("扩展模板名必须使用 namespace::template 格式")
        namespace, name = raw.split("::", 1)
        namespace = namespace.strip()
        name = name.strip().lstrip("/\\")
        if not namespace or not name or ".." in Path(name).parts:
            raise ValueError("扩展模板名非法")
        return namespace, name


class ApplicationSystemHookService:
    def __init__(self, host, view_field: str) -> None:
        self._host = host
        self._view_field = view_field
        self._definitions_by_extension: dict[str, tuple[ExtensionSystemHookDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionSystemHookDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        setattr(self._host._get_or_create_runtime_view(normalized), self._view_field, definitions)

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionSystemHookDefinition]:
        if extension_id is not None:
            definitions = list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._definitions_by_extension.values():
                definitions.extend(items)
        return sorted(definitions, key=lambda item: (int(item.order or 100), item.module_id, item.key))

    def run(self, key: str, payload: dict | None = None, context: dict | None = None) -> list[Any]:
        normalized = str(key or "").strip()
        results = []
        for definition in self.get_definitions():
            if definition.key != normalized or not callable(definition.callback):
                continue
            results.append(definition.callback(dict(payload or {}), dict(context or {})))
        return results

    def get_payloads(self, key: str) -> list[Any]:
        normalized = str(key or "").strip()
        return [
            definition.callback
            for definition in self.get_definitions()
            if definition.key == normalized and not callable(definition.callback)
        ]


class ApplicationSignalService:
    def __init__(self, host) -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionSignalDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionSignalDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized or definition.signal is None or not callable(definition.receiver):
            return

        from apps.core.extensions.signal_runtime import connect_runtime_signal

        registered_uid = connect_runtime_signal(normalized, definition)
        if registered_uid:
            definition = replace(definition, dispatch_uid=registered_uid)

        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).signal_handlers = definitions

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionSignalDefinition]:
        if extension_id is not None:
            return list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionSignalDefinition] = []
        for items in self._definitions_by_extension.values():
            definitions.extend(items)
        return sorted(definitions, key=lambda item: (int(item.order or 100), item.module_id, item.dispatch_uid))


class ApplicationPostEventDataService:
    def __init__(self, host) -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionSystemHookDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionSystemHookDefinition) -> None:
        normalized = str(extension_id or "").strip()
        post_type = str(definition.key or "").strip()
        if not normalized or not post_type or not callable(definition.callback):
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions

    def get_definitions(self, *, extension_id: str | None = None, post_type: str = "") -> list[ExtensionSystemHookDefinition]:
        if extension_id is not None:
            definitions = list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._definitions_by_extension.values():
                definitions.extend(items)
        normalized_post_type = str(post_type or "").strip()
        if normalized_post_type:
            definitions = [definition for definition in definitions if definition.key == normalized_post_type]
        return sorted(definitions, key=lambda item: (int(item.order or 100), item.module_id, item.key))

    def resolve(self, post, context: dict | None = None) -> dict | None:
        post_type = str(getattr(post, "type", "") or "").strip()
        if not post_type:
            return None
        resolved_context = dict(context or {})
        for definition in self.get_definitions(post_type=post_type):
            result = definition.callback(post, resolved_context)
            if result is not None:
                return result
        return None
