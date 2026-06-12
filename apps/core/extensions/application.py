from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from apps.core.domain_events import DomainEventBus
from apps.core.extensions.container import import_string, resolve_container_value
from apps.core.extensions.model_references import model_class, model_matches, resolve_model_reference
from apps.core.extensions.types import (
    ExtensionAdminActionDefinition,
    ExtensionDiscussionLifecycleDefinition,
    ExtensionEventListenerDefinition,
    ExtensionFrontendRouteDefinition,
    ExtensionFormatterCallback,
    ExtensionFormatterDefinition,
    ExtensionManifestRuntimeActionDefinition,
    ExtensionManifestSettingFieldDefinition,
    ExtensionSettingDefaultDefinition,
    ExtensionSettingForumSerializationDefinition,
    ExtensionSettingResetDefinition,
    ExtensionSettingThemeVariableDefinition,
    ExtensionModelDefinition,
    ExtensionModelCastDefinition,
    ExtensionModelDefaultDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelSlugDriverDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionPostLifecycleDefinition,
    ExtensionResourceDefinition,
    ExtensionResourceEndpointDefinition,
    ExtensionResourceFieldMutatorDefinition,
    ExtensionResourceFieldDefinition,
    ExtensionResourceFilterDefinition,
    ExtensionResourceRelationshipDefinition,
    ExtensionResourceSortDefinition,
    ExtensionRealtimeDiscussionBroadcastDefinition,
    ExtensionRealtimeDiscussionTransportDefinition,
    ExtensionRealtimeIncludedDefinition,
    ExtensionSearchDriverDefinition,
    ExtensionSearchIndexDefinition,
    ExtensionSystemHookDefinition,
    ExtensionValidatorDefinition,
    ExtensionMailDefinition,
    ExtensionViewNamespaceDefinition,
    ExtensionSignalDefinition,
)
from apps.core.extensions.exceptions import ExtensionBootError
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionListQueryDefinition,
    DiscussionSortDefinition,
    EventListenerDefinition,
    LanguagePackDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterDefinition,
    UserPreferenceDefinition,
)


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.core.extensions.extension_runtime import Extension
    from apps.core.forum_registry import ForumRegistry
    from apps.core.resource_registry import ResourceRegistry


UNSET = object()
ContainerResolver = Callable[["ExtensionHost"], Any]
ContainerExtender = Callable[["ExtensionHost", Any], Any]
ResolvingCallback = Callable[[Any, "ExtensionHost"], Any]
LifecycleCallback = Callable[["ExtensionHost"], None]
PolicyCallback = Callable[..., bool]


@dataclass
class ApplicationRouteMount:
    prefix: str
    router: Any
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationNamedRoute:
    app_name: str
    method: str
    path: str
    name: str
    handler: Any
    module_id: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationWebSocketRoute:
    path: str
    name: str
    consumer: Any
    module_id: str = ""


@dataclass
class ApplicationMiddlewareMount:
    target: str
    middleware: Any
    order: int = 100


@dataclass
class ApplicationPolicyMount:
    key: str
    handler: PolicyCallback
    model: Any = None
    global_policy: bool = False
    query_policy: bool = False


@dataclass(frozen=True)
class ApplicationForumPermissionChecker:
    key: str
    handler: Any
    description: str = ""
    module_id: str = ""


class ApplicationValidatorService:
    def __init__(self, host: "ExtensionHost") -> None:
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
    def __init__(self, host: "ExtensionHost") -> None:
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
    def __init__(self, host: "ExtensionHost") -> None:
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
    def __init__(self, host: "ExtensionHost", view_field: str) -> None:
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
    def __init__(self, host: "ExtensionHost") -> None:
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
    def __init__(self, host: "ExtensionHost") -> None:
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


@dataclass
class ApplicationModelExtension:
    extension_id: str
    definition: ExtensionModelDefinition


class ApplicationModelRelationDescriptor:
    def __init__(self, definition: ExtensionModelRelationDefinition) -> None:
        self.definition = definition

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return self.definition.resolver(instance)


class ApplicationModelService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._definitions_by_extension: dict[str, tuple[ExtensionModelDefinition, ...]] = {}
        self._visibility_by_extension: dict[str, tuple[ExtensionModelVisibilityDefinition, ...]] = {}
        self._relations_by_extension: dict[str, tuple[ExtensionModelRelationDefinition, ...]] = {}
        self._casts_by_extension: dict[str, tuple[ExtensionModelCastDefinition, ...]] = {}
        self._defaults_by_extension: dict[str, tuple[ExtensionModelDefaultDefinition, ...]] = {}
        self._private_checkers_by_extension: dict[str, tuple[ExtensionModelDefinition, ...]] = {}

    def register(self, extension_id: str, definition: ExtensionModelDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._definitions_by_extension.get(normalized, ()), definition])
        self._definitions_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_definitions = definitions

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        if extension_id is not None:
            return list(self._definitions_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelDefinition] = []
        for items in self._definitions_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_definitions_for_model(self, model: Any, *, kind: str | None = None) -> list[ExtensionModelDefinition]:
        definitions = [
            definition
            for definition in self.get_definitions()
            if self._model_matches(definition.model, model)
        ]
        if kind is not None:
            definitions = [definition for definition in definitions if definition.kind == kind]
        return definitions

    def get_owned_models(self, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        return [
            definition
            for definition in self.get_definitions(extension_id=extension_id)
            if definition.kind == "owner"
        ]

    def get_model_owner(self, model: Any) -> str:
        owners = [
            extension_id
            for extension_id, definitions in self._definitions_by_extension.items()
            for definition in definitions
            if definition.kind == "owner" and self._model_matches(definition.model, model)
        ]
        return owners[-1] if owners else ""

    def register_visibility(self, extension_id: str, definition: ExtensionModelVisibilityDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._visibility_by_extension.get(normalized, ()), definition])
        self._visibility_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_visibility = definitions

    def get_visibility(self, *, extension_id: str | None = None) -> list[ExtensionModelVisibilityDefinition]:
        if extension_id is not None:
            return list(self._visibility_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelVisibilityDefinition] = []
        for items in self._visibility_by_extension.values():
            definitions.extend(items)
        return definitions

    def has_visibility(self, model: Any, *, ability: str | None = None) -> bool:
        return any(
            True
            for _definition in self._get_visibility_for_model(model, ability=ability)
        )

    def apply_visibility(self, model: Any, queryset, context: dict | None = None):
        output = queryset
        resolved_context = dict(context or {})
        requested_ability = str(resolved_context.get("ability") or "view")
        for definition in self._get_visibility_for_model(model, ability=requested_ability):
            output = definition.scope(output, resolved_context)
        return output

    def _get_visibility_for_model(self, model: Any, *, ability: str | None = None) -> list[ExtensionModelVisibilityDefinition]:
        requested_ability = str(ability or "view")
        definitions = []
        for sequence, definition in enumerate(self.get_visibility()):
            if not self._model_matches(definition.model, model):
                continue
            definition_ability = str(definition.ability or "*")
            if definition_ability not in {"*", requested_ability}:
                continue
            definitions.append((self._visibility_sort_key(definition, model, requested_ability, sequence), definition))
        return [definition for _key, definition in sorted(definitions, key=lambda item: item[0])]

    def _visibility_sort_key(
        self,
        definition: ExtensionModelVisibilityDefinition,
        model: Any,
        requested_ability: str,
        sequence: int,
    ) -> tuple[int, int, int, int]:
        lineage = self._model_lineage(model)
        registered_class = self._model_class(definition.model)
        try:
            lineage_index = lineage.index(registered_class) if registered_class in lineage else len(lineage)
        except ValueError:
            lineage_index = len(lineage)
        ability = str(definition.ability or "*")
        ability_index = 0 if ability == "*" else 1
        return (lineage_index, ability_index, int(getattr(definition, "order", 100) or 100), sequence)

    def _model_matches(self, registered_model: Any, model: Any) -> bool:
        return model_matches(registered_model, model, self._host)

    def _model_class(self, model: Any) -> type | None:
        return model_class(model, self._host)

    def _model_lineage(self, model: Any) -> list[type]:
        resolved_model_class = self._model_class(model)
        if resolved_model_class is None:
            return []
        return [item for item in reversed(resolved_model_class.__mro__) if item is not object]

    def register_relation(self, extension_id: str, definition: ExtensionModelRelationDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._relations_by_extension.get(normalized, ()), definition])
        self._relations_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_relations = definitions
        self._install_relation_descriptor(definition)

    def get_relations(self, *, extension_id: str | None = None) -> list[ExtensionModelRelationDefinition]:
        if extension_id is not None:
            return list(self._relations_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelRelationDefinition] = []
        for items in self._relations_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_relations_for_model(self, model: Any) -> list[ExtensionModelRelationDefinition]:
        return [
            definition
            for definition in self.get_relations()
            if self._model_matches(definition.model, model)
        ]

    def get_relation(self, model: Any, name: str) -> ExtensionModelRelationDefinition | None:
        normalized = str(name or "").strip()
        if not normalized:
            return None
        for definition in self.get_relations_for_model(model):
            if definition.name == normalized:
                return definition
        return None

    def resolve_relation(self, model: Any, name: str, instance: Any):
        definition = self.get_relation(model, name)
        if definition is None:
            return None
        return definition.resolver(instance)

    def _install_relation_descriptor(self, definition: ExtensionModelRelationDefinition) -> None:
        if not bool(getattr(definition, "inject_attribute", True)):
            return
        model_class = self._model_class(definition.model)
        relation_name = str(definition.name or "").strip()
        if model_class is None or not relation_name:
            return
        existing = getattr(model_class, relation_name, None)
        if existing is not None and not isinstance(existing, ApplicationModelRelationDescriptor):
            return
        setattr(model_class, relation_name, ApplicationModelRelationDescriptor(definition))

    def register_cast(self, extension_id: str, definition: ExtensionModelCastDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._casts_by_extension.get(normalized, ()), definition])
        self._casts_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_casts = definitions

    def get_casts(self, *, extension_id: str | None = None) -> list[ExtensionModelCastDefinition]:
        if extension_id is not None:
            return list(self._casts_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelCastDefinition] = []
        for items in self._casts_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_casts_for_model(self, model: Any) -> dict[str, Any]:
        casts: dict[str, Any] = {}
        for definition in self.get_casts():
            if self._model_matches(definition.model, model):
                casts[definition.attribute] = definition.cast
        return casts

    def register_default(self, extension_id: str, definition: ExtensionModelDefaultDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._defaults_by_extension.get(normalized, ()), definition])
        self._defaults_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_defaults = definitions

    def get_defaults(self, *, extension_id: str | None = None) -> list[ExtensionModelDefaultDefinition]:
        if extension_id is not None:
            return list(self._defaults_by_extension.get(str(extension_id or "").strip(), ()))
        definitions: list[ExtensionModelDefaultDefinition] = []
        for items in self._defaults_by_extension.values():
            definitions.extend(items)
        return definitions

    def get_defaults_for_model(self, model: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for definition in self.get_defaults():
            if not self._model_matches(definition.model, model):
                continue
            value = definition.value
            defaults[definition.attribute] = value() if callable(value) else value
        return defaults

    def register_private_checker(self, extension_id: str, definition: ExtensionModelDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definitions = tuple([*self._private_checkers_by_extension.get(normalized, ()), definition])
        self._private_checkers_by_extension[normalized] = definitions
        view = self._host._get_or_create_runtime_view(normalized)
        view.model_definitions = tuple([*view.model_definitions, definition])
        self._ensure_private_save_hook(definition.model)

    def get_private_checkers(self, model: Any | None = None, *, extension_id: str | None = None) -> list[ExtensionModelDefinition]:
        if extension_id is not None:
            definitions = list(self._private_checkers_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._private_checkers_by_extension.values():
                definitions.extend(items)
        if model is not None:
            definitions = [definition for definition in definitions if self._model_matches(definition.model, model)]
        return definitions

    def is_private(self, model: Any, instance: Any, *, default: bool = False) -> bool:
        result = bool(default)
        for definition in self.get_private_checkers(model):
            checker = definition.handler
            if not callable(checker):
                continue
            checked = checker(instance)
            if checked is True:
                return True
            if checked is False:
                result = False
        return result

    def _ensure_private_save_hook(self, model: Any) -> None:
        resolved_model = resolve_model_reference(model, self._host)
        if resolved_model is None or not hasattr(resolved_model, "_meta"):
            return
        from django.db.models.signals import pre_save

        model_label = f"{getattr(resolved_model, '__module__', '')}.{getattr(resolved_model, '__qualname__', getattr(resolved_model, '__name__', ''))}"

        def refresh_private_flag(sender, instance, **kwargs):
            if instance is None or not hasattr(instance, "is_private"):
                return
            from apps.core.extensions.runtime_access import is_runtime_model_private

            instance.is_private = is_runtime_model_private(instance, model=sender, default=False)

        pre_save.connect(
            refresh_private_flag,
            sender=resolved_model,
            weak=False,
            dispatch_uid=f"bias.model_private.pre_save.{model_label}",
        )


class ApplicationModelUrlService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._slug_drivers_by_extension: dict[str, tuple[ExtensionModelSlugDriverDefinition, ...]] = {}

    def register_slug_driver(self, extension_id: str, definition: ExtensionModelSlugDriverDefinition) -> None:
        normalized = str(extension_id or "").strip()
        identifier = str(getattr(definition, "identifier", "") or "").strip()
        if not normalized or not identifier or getattr(definition, "model", None) is None:
            return
        definitions = tuple([
            *(
                item
                for item in self._slug_drivers_by_extension.get(normalized, ())
                if not (
                    item.model == definition.model
                    and str(item.identifier or "").strip() == identifier
                )
            ),
            definition,
        ])
        self._slug_drivers_by_extension[normalized] = definitions
        self._host._get_or_create_runtime_view(normalized).model_slug_drivers = definitions

    def get_slug_drivers(self, model: Any | None = None, *, extension_id: str | None = None) -> list[ExtensionModelSlugDriverDefinition]:
        if extension_id is not None:
            definitions = list(self._slug_drivers_by_extension.get(str(extension_id or "").strip(), ()))
        else:
            definitions = []
            for items in self._slug_drivers_by_extension.values():
                definitions.extend(items)
        if model is not None:
            definitions = [definition for definition in definitions if definition.model == model]
        return definitions

    def get_slug_driver(self, model: Any, identifier: str = "default") -> ExtensionModelSlugDriverDefinition | None:
        normalized_identifier = str(identifier or "default").strip() or "default"
        for definition in reversed(self.get_slug_drivers(model)):
            if str(definition.identifier or "").strip() == normalized_identifier:
                return definition
        return None

    def generate_slug(
        self,
        model: Any,
        source: Any,
        *,
        identifier: str = "default",
        explicit_slug: str = "",
        exclude_id: int | None = None,
        context: dict | None = None,
    ) -> str:
        definition = self.get_slug_driver(model, identifier)
        if definition is None:
            raise KeyError(f"slug driver not registered: {model}.{identifier}")

        resolved_context = {
            **dict(context or {}),
            "model": model,
            "identifier": str(identifier or "default").strip() or "default",
            "field": definition.field,
            "source_field": definition.source_field,
            "exclude_id": exclude_id,
        }
        driver = resolve_container_value(definition.driver, self._host)
        base_slug = self._invoke_slug_driver(driver, source, explicit_slug, resolved_context)
        return self._unique_slug(
            model,
            base_slug,
            field=definition.field,
            exclude_id=exclude_id,
            max_length=definition.max_length,
        )

    @staticmethod
    def _invoke_slug_driver(driver: Any, source: Any, explicit_slug: str, context: dict) -> str:
        if hasattr(driver, "generate"):
            return str(driver.generate(source, explicit_slug=explicit_slug, context=context) or "").strip()
        if callable(driver):
            try:
                return str(driver(source, explicit_slug=explicit_slug, context=context) or "").strip()
            except TypeError:
                try:
                    return str(driver(source, explicit_slug) or "").strip()
                except TypeError:
                    return str(driver(source) or "").strip()
        return str(explicit_slug or source or "").strip()

    @staticmethod
    def _unique_slug(
        model: Any,
        slug: str,
        *,
        field: str = "slug",
        exclude_id: int | None = None,
        max_length: int | None = None,
    ) -> str:
        import uuid

        normalized = str(slug or "").strip() or str(uuid.uuid4())[:8]
        if max_length is not None and max_length > 0:
            normalized = normalized[:max_length].strip("-_ ") or str(uuid.uuid4())[:8]

        original = normalized
        counter = 1
        manager = getattr(model, "objects", None)
        if manager is None:
            return normalized

        while True:
            queryset = manager.filter(**{field: normalized})
            if exclude_id is not None:
                queryset = queryset.exclude(id=exclude_id)
            if not queryset.exists():
                return normalized
            counter += 1
            suffix = f"-{counter}"
            if max_length is not None and max_length > 0:
                base = original[: max(1, max_length - len(suffix))].rstrip("-_ ")
                normalized = f"{base}{suffix}"
            else:
                normalized = f"{original}{suffix}"


class ApplicationSearchService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._drivers_by_extension: dict[str, tuple[ExtensionSearchDriverDefinition, ...]] = {}
        self._indexes_by_extension: dict[str, tuple[ExtensionSearchIndexDefinition, ...]] = {}
        from apps.core.resource_search import ResourceSearchManager

        self.manager = ResourceSearchManager(container=host)

    def register_driver(self, extension_id: str, definition: ExtensionSearchDriverDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        drivers = tuple([*self._drivers_by_extension.get(normalized, ()), definition])
        self._drivers_by_extension[normalized] = drivers
        view = self._host._get_or_create_runtime_view(normalized)
        view.search_drivers = drivers
        self._register_resource_search_driver(definition)

    def get_drivers(self, *, extension_id: str | None = None) -> list[ExtensionSearchDriverDefinition]:
        if extension_id is not None:
            return list(self._drivers_by_extension.get(str(extension_id or "").strip(), ()))
        drivers: list[ExtensionSearchDriverDefinition] = []
        for items in self._drivers_by_extension.values():
            drivers.extend(items)
        return drivers

    def get_drivers_for_target(self, target: str) -> list[ExtensionSearchDriverDefinition]:
        normalized = str(target or "").strip()
        return [
            driver
            for driver in self.get_drivers()
            if driver.target == normalized
        ]

    def register_index_definition(self, extension_id: str, definition: ExtensionSearchIndexDefinition) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        definition = replace(definition, module_id=definition.module_id or normalized)
        indexes = tuple([*self._indexes_by_extension.get(normalized, ()), definition])
        self._indexes_by_extension[normalized] = indexes
        view = self._host._get_or_create_runtime_view(normalized)
        view.search_indexes = indexes

    def get_index_definitions(self, *, extension_id: str | None = None) -> list[ExtensionSearchIndexDefinition]:
        if extension_id is not None:
            return list(self._indexes_by_extension.get(str(extension_id or "").strip(), ()))
        indexes: list[ExtensionSearchIndexDefinition] = []
        for items in self._indexes_by_extension.values():
            indexes.extend(items)
        return indexes

    def apply_filters(self, target: str, queryset, query: str, context: dict | None = None):
        text_query, parsed_filters = self.extract_filter_tokens(query, targets=(target,))
        output = queryset
        resolved_context = {
            **dict(context or {}),
            "query": query,
            "text_query": text_query,
            "target": target,
        }
        for definition, parsed_value in parsed_filters.get(target, []):
            output = definition.applier(output, parsed_value, resolved_context)
        return output

    def extract_filter_tokens(
        self,
        query: str,
        targets: tuple[str, ...] | None = None,
    ) -> tuple[str, dict[str, list]]:
        text_tokens: list[str] = []
        filters: dict[str, list] = {}
        allowed_targets = set(targets or ())

        for raw_token in (query or "").split():
            matched = False
            for definition in self.get_available_filters(targets=targets):
                if allowed_targets and definition.target not in allowed_targets:
                    continue
                parsed_value = definition.parser(raw_token)
                if parsed_value is None:
                    continue
                filters.setdefault(definition.target, []).append((definition, parsed_value))
                matched = True
                break

            if not matched:
                text_tokens.append(raw_token)

        return " ".join(text_tokens).strip(), filters

    def get_available_filters(self, *, targets: tuple[str, ...] | None = None):
        allowed_targets = set(targets or ())
        definitions = list(self._host.forum_registry.get_search_filters())
        for driver in self.get_drivers():
            if allowed_targets and driver.target not in allowed_targets:
                continue
            definitions.extend(driver.filters)
        if targets is not None:
            definitions = [item for item in definitions if item.target in allowed_targets]
        return definitions

    def apply_mutators(self, target: str, queryset, context: dict | None = None):
        output = queryset
        resolved_context = dict(context or {})
        for driver in self.get_drivers_for_target(target):
            for mutator in driver.mutators:
                output = self._invoke_search_callable(mutator, output, resolved_context)
        return output

    def get_searchers(self, target: str) -> list[Any]:
        searchers: list[Any] = []
        for driver in self.get_drivers_for_target(target):
            searchers.extend(driver.searchers)
        return searchers

    def get_fulltext_handlers(self, target: str) -> list[Any]:
        return [
            driver.fulltext
            for driver in self.get_drivers_for_target(target)
            if driver.fulltext is not None
        ]

    def searchable(self, model: Any) -> bool:
        return self.manager.searchable(model)

    def query(self, model: Any, queryset, criteria, context: dict):
        return self.manager.query(model, queryset, criteria, context)

    def filters_for(self, model: Any, *, resource: str = ""):
        return self.manager.filters_for(model, resource=resource)

    def register_filter(self, resource: str, definition) -> None:
        self.manager.register_filter(resource, definition)

    def register_searcher(self, model: Any, searcher: Any, *, driver: str = "database") -> None:
        self.manager.register_searcher(model, searcher, driver=driver)

    def register_indexer(self, model: Any, indexer: Any) -> None:
        self.manager.register_indexer(model, indexer)

    def indexers(self, model: Any):
        return self.manager.indexers(model)

    def indexable(self, model: Any) -> bool:
        return self.manager.indexable(model)

    def index(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self.manager.index(model, instance, context or {})

    def unindex(self, model: Any, instance: Any, context: dict | None = None) -> None:
        self.manager.unindex(model, instance, context or {})

    def reindex(self, model: Any, instances: Any = None, context: dict | None = None) -> None:
        self.manager.reindex(model, instances, context or {})

    def _invoke_search_callable(self, callback, queryset, context: dict):
        if callable(callback):
            return callback(queryset, context)
        return queryset

    def _register_resource_search_driver(self, definition: ExtensionSearchDriverDefinition) -> None:
        target = str(definition.target or "").strip()
        from apps.core.resource_search import ResourceSearchFilter

        for item in definition.filters or ():
            name = str(getattr(item, "code", "") or getattr(item, "name", "") or "").strip()
            applier = getattr(item, "applier", None)
            if target and name and callable(applier):
                self.manager.register_filter(
                    target,
                    ResourceSearchFilter(
                        name=name,
                        handler=lambda state, value, context, item=item: item.applier(state.queryset, value, context),
                        module_id=getattr(item, "module_id", "") or target,
                    ),
                )
        for searcher in definition.searchers or ():
            model = getattr(searcher, "model", None)
            if model is not None:
                self.manager.register_searcher(
                    model,
                    searcher,
                    driver=str(definition.driver or "database"),
                    searcher_key=searcher,
                )
        if definition.model is not None and definition.searcher is not None:
            self.manager.register_searcher(
                definition.model,
                definition.searcher,
                driver=str(definition.driver or "database"),
                searcher_key=definition.searcher,
            )
        for indexer in getattr(definition, "indexers", ()) or ():
            model = getattr(indexer, "model", None) or definition.model
            if model is not None:
                self.manager.register_indexer(model, indexer)
        driver_indexers = getattr(definition.driver, "indexers", None)
        if isinstance(driver_indexers, dict):
            for model, indexers in driver_indexers.items():
                for indexer in indexers if isinstance(indexers, (list, tuple, set)) else (indexers,):
                    self.manager.register_indexer(model, indexer)
        searcher_key = definition.searcher if definition.searcher is not None else definition.model
        if searcher_key is not None and definition.fulltext is not None:
            self.manager.set_driver_fulltext(str(definition.driver or "database"), searcher_key, definition.fulltext)
        for item in definition.driver_filters or ():
            if searcher_key is None:
                continue
            filter_definition = self._to_resource_search_filter(item, target=target)
            if filter_definition is not None:
                self.manager.register_driver_filter(str(definition.driver or "database"), searcher_key, filter_definition)
        for replace, item in definition.replace_filters or ():
            if searcher_key is None:
                continue
            filter_definition = self._to_resource_search_filter(item, target=target)
            if filter_definition is not None:
                self.manager.register_driver_filter(
                    str(definition.driver or "database"),
                    searcher_key,
                    filter_definition,
                    replace=str(replace or "").strip(),
                )
        for mutator in definition.driver_mutators or ():
            if searcher_key is not None:
                self.manager.add_driver_mutator(str(definition.driver or "database"), searcher_key, mutator)

    @staticmethod
    def _to_resource_search_filter(item: Any, *, target: str = ""):
        from apps.core.resource_search import ResourceSearchFilter

        if isinstance(item, ResourceSearchFilter):
            return item
        name = str(
            getattr(item, "name", "")
            or getattr(item, "code", "")
            or getattr(item, "filter", "")
            or ""
        ).strip()
        if not name and isinstance(item, tuple) and len(item) == 2:
            name = str(item[0] or "").strip()
            handler = item[1]
        else:
            handler = getattr(item, "handler", None) or getattr(item, "applier", None)
        if not name or not callable(handler):
            return None

        def apply(state, value, context, handler=handler):
            try:
                return handler(state, value, context)
            except TypeError:
                return handler(state.queryset, value, context)

        return ResourceSearchFilter(
            name=name,
            handler=apply,
            module_id=getattr(item, "module_id", "") or target or "extension",
        )


@dataclass
class ApplicationFrontendExtension:
    extension_id: str
    admin_entry: str = ""
    forum_entry: str = ""
    common_entry: str = ""
    css: tuple[str, ...] = ()
    js_directories: tuple[str, ...] = ()
    preloads: tuple[Any, ...] = ()
    content_callbacks: tuple[Any, ...] = ()
    document_attributes: tuple[Any, ...] = ()
    head_tags: tuple[Any, ...] = ()
    theme_variables: tuple[Any, ...] = ()
    title_driver: Any = None
    routes: tuple[ExtensionFrontendRouteDefinition, ...] = ()
    settings_pages: tuple[str, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()


@dataclass
class ApplicationServiceProvider:
    key: str
    target: Any
    singleton: bool = True
    _resolved_target: Any = field(default=None, init=False, repr=False)

    def register(self, host: "ExtensionHost") -> None:
        target = self._resolve_target()
        register = getattr(target, "register", None)
        if callable(register):
            register(host)
            return
        if callable(target):
            if self.singleton:
                host.singleton(self.key, target)
            else:
                host.bind(self.key, target)

    def boot(self, host: "ExtensionHost") -> None:
        target = self._resolve_target()
        boot = getattr(target, "boot", None)
        if callable(boot):
            boot(host)

    def _resolve_target(self) -> Any:
        if self._resolved_target is not None:
            return self._resolved_target

        target = resolve_container_value(self.target, None, _skip_container_lookup=True)
        if isinstance(target, type):
            target = target()
        self._resolved_target = target
        return target


class ApplicationRouteService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._mounts_by_extension: dict[str, tuple[ApplicationRouteMount, ...]] = {}
        self._routes_by_app: dict[str, tuple[ApplicationNamedRoute, ...]] = {}
        self._route_names_by_extension: dict[str, tuple[tuple[str, str], ...]] = {}
        self._removed_by_app: dict[str, tuple[str, ...]] = {}

    def mount(
        self,
        extension_id: str,
        prefix: str,
        router: Any,
        *,
        tags=(),
    ) -> ApplicationRouteMount | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_prefix = str(prefix or "").strip()
        if not normalized_extension_id or router is None:
            return None

        mount = ApplicationRouteMount(
            prefix=normalized_prefix,
            router=router,
            tags=tuple(tags or ()),
        )
        mounts = list(self._mounts_by_extension.get(normalized_extension_id, ()))
        mounts.append(mount)
        self._mounts_by_extension[normalized_extension_id] = tuple(mounts)
        self._host._get_or_create_runtime_view(normalized_extension_id).route_mounts = tuple(
            self.get_mounts(extension_id=normalized_extension_id)
        )
        return mount

    def get_mounts(self, *, extension_id: str | None = None) -> list[ApplicationRouteMount]:
        if extension_id is not None:
            return list(self._mounts_by_extension.get(str(extension_id or "").strip(), ()))

        mounts: list[ApplicationRouteMount] = []
        for items in self._mounts_by_extension.values():
            mounts.extend(items)
        return mounts

    def remove_mounts(self, extension_id: str) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        self._mounts_by_extension.pop(normalized, None)
        self._host._get_or_create_runtime_view(normalized).route_mounts = ()

    def add_route(
        self,
        extension_id: str,
        app_name: str,
        method: str,
        path: str,
        name: str,
        handler: Any,
        *,
        tags=(),
    ) -> ApplicationNamedRoute | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_app = str(app_name or "api").strip() or "api"
        normalized_method = str(method or "GET").strip().upper() or "GET"
        normalized_path = "/" + str(path or "").strip().strip("/")
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_name or handler is None:
            return None

        route = ApplicationNamedRoute(
            app_name=normalized_app,
            method=normalized_method,
            path=normalized_path,
            name=normalized_name,
            handler=handler,
            module_id=normalized_extension_id,
            tags=tuple(tags or ()),
        )
        routes = [
            item
            for item in self._routes_by_app.get(normalized_app, ())
            if item.name != normalized_name
        ]
        routes.append(route)
        self._routes_by_app[normalized_app] = tuple(routes)
        removed = [
            item
            for item in self._removed_by_app.get(normalized_app, ())
            if item != normalized_name
        ]
        self._removed_by_app[normalized_app] = tuple(removed)
        route_keys = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != (normalized_app, normalized_name)
        ]
        route_keys.append((normalized_app, normalized_name))
        self._route_names_by_extension[normalized_extension_id] = tuple(route_keys)
        self._sync_route_view(normalized_extension_id)
        return route

    def remove_route(self, extension_id: str, app_name: str, name: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_app = str(app_name or "api").strip() or "api"
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_name:
            return

        self._routes_by_app[normalized_app] = tuple(
            item
            for item in self._routes_by_app.get(normalized_app, ())
            if item.name != normalized_name
        )
        removed = list(self._removed_by_app.get(normalized_app, ()))
        if normalized_name not in removed:
            removed.append(normalized_name)
        self._removed_by_app[normalized_app] = tuple(removed)
        route_keys = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != (normalized_app, normalized_name)
        ]
        route_keys.append((normalized_app, normalized_name))
        self._route_names_by_extension[normalized_extension_id] = tuple(route_keys)
        self._sync_route_view(normalized_extension_id)

    def get_routes(self, *, app_name: str | None = None) -> list[ApplicationNamedRoute]:
        if app_name is not None:
            normalized_app = str(app_name or "").strip()
            removed = set(self._removed_by_app.get(normalized_app, ()))
            return [
                route
                for route in self._routes_by_app.get(normalized_app, ())
                if route.name not in removed
            ]

        routes: list[ApplicationNamedRoute] = []
        for normalized_app in sorted(self._routes_by_app.keys()):
            routes.extend(self.get_routes(app_name=normalized_app))
        return routes

    def get_removed_route_names(self, app_name: str) -> tuple[str, ...]:
        return tuple(self._removed_by_app.get(str(app_name or "").strip(), ()))

    def _sync_route_view(self, extension_id: str) -> None:
        view = self._host._get_or_create_runtime_view(extension_id)
        route_keys = set(self._route_names_by_extension.get(extension_id, ()))
        view.named_routes = tuple(
            route
            for route in self.get_routes()
            if (route.app_name, route.name) in route_keys
        )


class ApplicationWebSocketRouteService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._routes: dict[str, ApplicationWebSocketRoute] = {}
        self._route_names_by_extension: dict[str, tuple[str, ...]] = {}

    def add_route(
        self,
        extension_id: str,
        path: str,
        name: str,
        consumer: Any,
    ) -> ApplicationWebSocketRoute | None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_path = str(path or "").strip()
        normalized_name = str(name or "").strip()
        if not normalized_extension_id or not normalized_path or not normalized_name or consumer is None:
            return None

        route = ApplicationWebSocketRoute(
            path=normalized_path,
            name=normalized_name,
            consumer=consumer,
            module_id=normalized_extension_id,
        )
        self._routes[normalized_name] = route
        route_names = [
            item
            for item in self._route_names_by_extension.get(normalized_extension_id, ())
            if item != normalized_name
        ]
        route_names.append(normalized_name)
        self._route_names_by_extension[normalized_extension_id] = tuple(route_names)
        self._sync_route_view(normalized_extension_id)
        return route

    def remove_routes(self, extension_id: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return
        for name in self._route_names_by_extension.pop(normalized_extension_id, ()):
            self._routes.pop(name, None)
        self._sync_route_view(normalized_extension_id)

    def get_routes(self, *, extension_id: str | None = None) -> list[ApplicationWebSocketRoute]:
        if extension_id is not None:
            route_names = self._route_names_by_extension.get(str(extension_id or "").strip(), ())
            return [
                self._routes[name]
                for name in route_names
                if name in self._routes
            ]
        return [
            self._routes[name]
            for name in sorted(self._routes.keys())
        ]

    def _sync_route_view(self, extension_id: str) -> None:
        view = self._host._get_or_create_runtime_view(extension_id)
        view.websocket_routes = tuple(self.get_routes(extension_id=extension_id))


class ApplicationFrontendService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._extensions: dict[str, ApplicationFrontendExtension] = {}

    def register_entries(
        self,
        extension_id: str,
        *,
        admin_entry: str = "",
        forum_entry: str = "",
        common_entry: str = "",
        css=(),
        js_directories=(),
        preloads=(),
        content_callbacks=(),
        document_attributes=(),
        head_tags=(),
        theme_variables=(),
        title_driver=None,
        routes=(),
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        if admin_entry:
            frontend.admin_entry = str(admin_entry).strip()
        if forum_entry:
            frontend.forum_entry = str(forum_entry).strip()
        if common_entry:
            frontend.common_entry = str(common_entry).strip()
        frontend.css = self._merge_pages(frontend.css, css)
        frontend.js_directories = self._merge_pages(frontend.js_directories, js_directories)
        frontend.preloads = tuple([*frontend.preloads, *(preloads or ())])
        frontend.content_callbacks = tuple([*frontend.content_callbacks, *(content_callbacks or ())])
        frontend.document_attributes = tuple([*frontend.document_attributes, *(document_attributes or ())])
        frontend.head_tags = tuple([*frontend.head_tags, *(head_tags or ())])
        frontend.theme_variables = tuple([*frontend.theme_variables, *(theme_variables or ())])
        if title_driver is not None:
            frontend.title_driver = title_driver
        frontend.routes = self._merge_routes(frontend.routes, routes)
        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry
        view.frontend_css = frontend.css
        view.frontend_js_directories = frontend.js_directories
        view.frontend_preloads = frontend.preloads
        view.frontend_content_callbacks = frontend.content_callbacks
        view.frontend_document_attributes = frontend.document_attributes
        view.frontend_head_tags = frontend.head_tags
        view.frontend_theme_variables = frontend.theme_variables
        view.frontend_title_driver = frontend.title_driver
        view.frontend_routes = frontend.routes
        return frontend

    def register_pages(
        self,
        extension_id: str,
        *,
        settings_pages=(),
        permissions_pages=(),
        operations_pages=(),
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        frontend.settings_pages = self._merge_pages(frontend.settings_pages, settings_pages)
        frontend.permissions_pages = self._merge_pages(frontend.permissions_pages, permissions_pages)
        frontend.operations_pages = self._merge_pages(frontend.operations_pages, operations_pages)
        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages
        return frontend

    def get_extension(self, extension_id: str) -> ApplicationFrontendExtension | None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._extensions.get(normalized)

    def get_extensions(self) -> list[ApplicationFrontendExtension]:
        return list(self._extensions.values())

    def set_extension(
        self,
        extension_id: str,
        *,
        admin_entry: str | None = None,
        forum_entry: str | None = None,
        common_entry: str | None = None,
        css=None,
        js_directories=None,
        preloads=None,
        content_callbacks=None,
        document_attributes=None,
        head_tags=None,
        theme_variables=None,
        title_driver=UNSET,
        routes=None,
        settings_pages=None,
        permissions_pages=None,
        operations_pages=None,
    ) -> ApplicationFrontendExtension:
        frontend = self._get_or_create_extension(extension_id)
        if admin_entry is not None:
            frontend.admin_entry = str(admin_entry or "").strip()
        if forum_entry is not None:
            frontend.forum_entry = str(forum_entry or "").strip()
        if common_entry is not None:
            frontend.common_entry = str(common_entry or "").strip()
        if css is not None:
            frontend.css = tuple(css or ())
        if js_directories is not None:
            frontend.js_directories = tuple(js_directories or ())
        if preloads is not None:
            frontend.preloads = tuple(preloads or ())
        if content_callbacks is not None:
            frontend.content_callbacks = tuple(content_callbacks or ())
        if document_attributes is not None:
            frontend.document_attributes = tuple(document_attributes or ())
        if head_tags is not None:
            frontend.head_tags = tuple(head_tags or ())
        if theme_variables is not None:
            frontend.theme_variables = tuple(theme_variables or ())
        if title_driver is not UNSET:
            frontend.title_driver = title_driver
        if routes is not None:
            frontend.routes = tuple(routes or ())
        if settings_pages is not None:
            frontend.settings_pages = tuple(settings_pages or ())
        if permissions_pages is not None:
            frontend.permissions_pages = tuple(permissions_pages or ())
        if operations_pages is not None:
            frontend.operations_pages = tuple(operations_pages or ())

        view = self._host._get_or_create_runtime_view(frontend.extension_id)
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry
        view.frontend_css = frontend.css
        view.frontend_js_directories = frontend.js_directories
        view.frontend_preloads = frontend.preloads
        view.frontend_content_callbacks = frontend.content_callbacks
        view.frontend_document_attributes = frontend.document_attributes
        view.frontend_head_tags = frontend.head_tags
        view.frontend_theme_variables = frontend.theme_variables
        view.frontend_title_driver = frontend.title_driver
        view.frontend_routes = frontend.routes
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages
        return frontend

    def _get_or_create_extension(self, extension_id: str) -> ApplicationFrontendExtension:
        normalized = str(extension_id or "").strip()
        if normalized not in self._extensions:
            self._extensions[normalized] = ApplicationFrontendExtension(extension_id=normalized)
        return self._extensions[normalized]

    def _merge_pages(self, current: tuple[str, ...], additions) -> tuple[str, ...]:
        merged = list(current)
        for value in additions or ():
            normalized = str(value or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        return tuple(merged)

    def _merge_routes(
        self,
        current: tuple[ExtensionFrontendRouteDefinition, ...],
        additions,
    ) -> tuple[ExtensionFrontendRouteDefinition, ...]:
        merged = list(current)
        seen = {(item.frontend, item.name, item.path) for item in merged}
        for route in additions or ():
            if route is None:
                continue
            key = (route.frontend, route.name, route.path)
            if key in seen:
                continue
            merged.append(route)
            seen.add(key)
        return tuple(sorted(merged, key=lambda item: (item.frontend, item.order, item.name)))


class ApplicationServiceProviderRegistry:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._providers_by_extension: dict[str, tuple[ApplicationServiceProvider, ...]] = {}
        self._registered_provider_keys: set[str] = set()
        self._booted_provider_keys: set[str] = set()

    def register(
        self,
        extension_id: str,
        provider: ApplicationServiceProvider,
    ) -> str:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(provider, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return ""

        providers = list(self._providers_by_extension.get(normalized_extension_id, ()))
        if any(item.key == normalized_key for item in providers):
            return normalized_key

        providers.append(provider)
        self._providers_by_extension[normalized_extension_id] = tuple(providers)
        if normalized_key not in self._registered_provider_keys:
            provider.register(self._host)
            self._registered_provider_keys.add(normalized_key)
        self._host._get_or_create_runtime_view(normalized_extension_id).service_providers = tuple(
            self.get_provider_keys(extension_id=normalized_extension_id)
        )
        return normalized_key

    def register_provider(
        self,
        extension_id: str,
        key: str,
        provider: Any,
        *,
        singleton: bool = True,
    ) -> str:
        return self.register(
            extension_id,
            ApplicationServiceProvider(
                key=key,
                target=provider,
                singleton=singleton,
            ),
        )

    def boot(self) -> None:
        for provider in self.get_providers():
            if provider.key in self._booted_provider_keys:
                continue
            provider.boot(self._host)
            self._booted_provider_keys.add(provider.key)

    def get_providers(self, *, extension_id: str | None = None) -> list[ApplicationServiceProvider]:
        if extension_id is not None:
            return list(self._providers_by_extension.get(str(extension_id or "").strip(), ()))

        providers: list[ApplicationServiceProvider] = []
        for items in self._providers_by_extension.values():
            providers.extend(items)
        return providers

    def get_provider_keys(self, *, extension_id: str | None = None) -> list[str]:
        return [provider.key for provider in self.get_providers(extension_id=extension_id)]


class ApplicationLocaleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_path(self, extension_id: str, path: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_path = str(path or "").strip()
        if not normalized_extension_id or not normalized_path:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        if normalized_path not in view.locale_paths:
            view.locale_paths = tuple([*view.locale_paths, normalized_path])

    def get_paths(self, *, extension_id: str | None = None) -> list[str]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.locale_paths)

        paths: list[str] = []
        for view in self._host.get_runtime_views():
            paths.extend(view.locale_paths)
        return paths


class ApplicationFormatterService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_transform(self, extension_id: str, callback) -> None:
        self.register_render(extension_id, callback)

    def register_configure(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "configure", callback, description=description)

    def register_parse(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "parse", callback, description=description)

    def register_render(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "render", callback, description=description)

    def register_unparse(self, extension_id: str, callback, *, description: str = "") -> None:
        self.register_phase(extension_id, "unparse", callback, description=description)

    def register_phase(self, extension_id: str, phase: str, callback, *, description: str = "") -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_phase = str(phase or "").strip().lower()
        if normalized_phase == "transform":
            normalized_phase = "render"
        if normalized_phase not in {"configure", "parse", "render", "unparse"}:
            return
        if not normalized_extension_id or not callable(callback):
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        definition = ExtensionFormatterDefinition(
            phase=normalized_phase,
            callback=callback,
            module_id=normalized_extension_id,
            description=str(description or "").strip(),
        )
        view.formatter_callbacks = tuple([*view.formatter_callbacks, definition])
        if normalized_phase == "render":
            view.formatter_pipeline = tuple([*view.formatter_pipeline, callback])

    def get_pipeline(self, *, extension_id: str | None = None, phase: str = "render") -> list[ExtensionFormatterCallback]:
        normalized_phase = str(phase or "render").strip().lower() or "render"
        if normalized_phase == "transform":
            normalized_phase = "render"
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            if normalized_phase == "render" and not view.formatter_callbacks:
                return list(view.formatter_pipeline)
            return [
                definition.callback
                for definition in view.formatter_callbacks
                if definition.phase == normalized_phase
            ]

        pipeline: list[ExtensionFormatterCallback] = []
        for view in self._host.get_runtime_views():
            if normalized_phase == "render" and not view.formatter_callbacks:
                pipeline.extend(view.formatter_pipeline)
                continue
            pipeline.extend(
                definition.callback
                for definition in view.formatter_callbacks
                if definition.phase == normalized_phase
            )
        return pipeline


class ApplicationSettingsService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_fields(
        self,
        extension_id: str,
        fields,
        *,
        expose_to_forum=(),
        generated_page: bool = True,
        defaults=(),
        reset_when=(),
        reset_frontend_cache_for=(),
        theme_variables=(),
        forum_serializations=(),
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        fields_collection = list(view.settings_schema)
        for field in fields or ():
            fields_collection.append(field)
        view.settings_schema = tuple(fields_collection)

        default_collection = list(view.settings_defaults)
        for definition in defaults or ():
            if getattr(definition, "key", ""):
                default_collection.append(definition)
        view.settings_defaults = tuple(default_collection)

        reset_collection = list(view.settings_reset_rules)
        for definition in reset_when or ():
            if getattr(definition, "key", "") and callable(getattr(definition, "callback", None)):
                reset_collection.append(definition)
        view.settings_reset_rules = tuple(reset_collection)

        cache_keys = list(view.settings_frontend_cache_keys)
        for key in reset_frontend_cache_for or ():
            normalized_key = str(key or "").strip()
            if normalized_key and normalized_key not in cache_keys:
                cache_keys.append(normalized_key)
        view.settings_frontend_cache_keys = tuple(cache_keys)

        theme_collection = list(view.settings_theme_variables)
        for definition in theme_variables or ():
            if getattr(definition, "name", "") and getattr(definition, "key", ""):
                theme_collection.append(definition)
        view.settings_theme_variables = tuple(theme_collection)

        forum_serialization_collection = list(view.settings_forum_serializations)
        for definition in forum_serializations or ():
            if getattr(definition, "attribute", "") and getattr(definition, "key", ""):
                forum_serialization_collection.append(definition)
        view.settings_forum_serializations = tuple(forum_serialization_collection)

        forum_keys = list(view.forum_settings_keys)
        for key in expose_to_forum or ():
            normalized_key = str(key or "").strip()
            if normalized_key and normalized_key not in forum_keys:
                forum_keys.append(normalized_key)
        view.forum_settings_keys = tuple(forum_keys)

        if generated_page:
            view.use_generated_settings_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                settings_pages=(f"/admin/extensions/{normalized_extension_id}/settings",),
            )


class ApplicationAdminActionService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_runtime_actions(
        self,
        extension_id: str,
        actions,
        *,
        generated_page: bool = False,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        collection = list(view.runtime_actions)
        for action in actions or ():
            collection.append(action)
        view.runtime_actions = tuple(collection)

        if generated_page:
            view.use_generated_operations_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                operations_pages=(f"/admin/extensions/{normalized_extension_id}/operations",),
            )

    def register_admin_actions(
        self,
        extension_id: str,
        actions,
        *,
        generated_permissions_page: bool = False,
        generated_operations_page: bool = False,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        collection = list(view.admin_actions)
        for action in actions or ():
            collection.append(action)
        view.admin_actions = tuple(collection)

        if generated_permissions_page:
            view.use_generated_permissions_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                permissions_pages=(f"/admin/extensions/{normalized_extension_id}/permissions",),
            )
        if generated_operations_page:
            view.use_generated_operations_page = True
            self._host.frontend.register_pages(
                normalized_extension_id,
                operations_pages=(f"/admin/extensions/{normalized_extension_id}/operations",),
            )

    def mark_generated_permissions_page(self, extension_id: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.use_generated_permissions_page = True
        self._host.frontend.register_pages(
            normalized_extension_id,
            permissions_pages=(f"/admin/extensions/{normalized_extension_id}/permissions",),
        )


class ApplicationMiddlewareService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def mount(
        self,
        extension_id: str,
        target: str,
        middleware,
        *,
        order: int = 100,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or middleware is None:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.middleware_mounts = tuple([*view.middleware_mounts, ApplicationMiddlewareMount(
            target=str(target or "").strip() or "api",
            middleware=middleware,
            order=int(order),
        )])

    def get_mounts(self, *, target: str | None = None) -> list[ApplicationMiddlewareMount]:
        mounts: list[ApplicationMiddlewareMount] = []
        for view in self._host.get_runtime_views():
            mounts.extend(view.middleware_mounts)
        if target is not None:
            mounts = [item for item in mounts if item.target == target]
        return sorted(mounts, key=lambda item: (item.target, item.order))


class ApplicationPolicyService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def mount(self, extension_id: str, key: str, handler) -> None:
        self.mount_key(extension_id, key, handler)

    def mount_key(self, extension_id: str, key: str, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key=normalized_key,
            handler=handler,
        )])

    def global_policy(self, extension_id: str, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            global_policy=True,
        )])

    def model_policy(self, extension_id: str, model, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or model is None or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            model=model,
        )])

    def query_model_policy(self, extension_id: str, model, handler) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or model is None or not callable(handler):
            return
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
            key="",
            handler=handler,
            model=model,
            query_policy=True,
        )])

    def get_mounts(self) -> list[ApplicationPolicyMount]:
        mounts: list[ApplicationPolicyMount] = []
        for view in self._host.get_runtime_views():
            mounts.extend(view.policy_mounts)
        return mounts


class ApplicationEventService:
    def __init__(self, host: "ExtensionHost", event_bus: DomainEventBus) -> None:
        self._host = host
        self._event_bus = event_bus

    def register_listener(self, extension_id: str, definition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return
        event_type = self._resolve_event_type(getattr(definition, "event_type", None))
        if event_type is None:
            raise RuntimeError(f"无法解析扩展事件类型: {getattr(definition, 'event_type', None)}")
        definition = replace(definition, event_type=event_type)

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.event_listeners = tuple([*view.event_listeners, definition])
        self._host.forum.register_event_listener(self._build_forum_event_listener_definition(normalized_extension_id, definition))
        self._event_bus.register(
            event_type,
            definition.handler,
            listener_key=self._build_event_bus_listener_key(normalized_extension_id, definition),
        )

    @staticmethod
    def _resolve_event_type(event_type: Any):
        if isinstance(event_type, str):
            try:
                resolved = import_string(event_type)
            except Exception:
                return None
            return resolved if isinstance(resolved, type) else None
        return event_type if isinstance(event_type, type) else None

    @staticmethod
    def _build_forum_event_listener_definition(extension_id: str, definition) -> EventListenerDefinition:
        event_type = getattr(definition, "event_type", None)
        handler = getattr(definition, "handler", None)
        event_name = str(getattr(event_type, "__name__", "") or event_type or "").strip()
        handler_name = str(getattr(handler, "__name__", "") or handler or "").strip()
        return EventListenerDefinition(
            event=event_name,
            listener=handler_name,
            module_id=extension_id,
            description=str(getattr(definition, "description", "") or "").strip(),
        )

    @staticmethod
    def _build_event_bus_listener_key(extension_id: str, definition) -> tuple[str, str, str]:
        event_type = getattr(definition, "event_type", None)
        handler = getattr(definition, "handler", None)
        event_key = ":".join(
            item
            for item in (
                str(getattr(event_type, "__module__", "") or "").strip(),
                str(getattr(event_type, "__qualname__", "") or "").strip(),
            )
            if item
        ) or str(event_type)
        handler_key = ":".join(
            item
            for item in (
                str(getattr(handler, "__module__", "") or "").strip(),
                str(getattr(handler, "__qualname__", "") or "").strip(),
            )
            if item
        ) or str(handler)
        return (extension_id, event_key, handler_key)

    def get_listeners(self, *, extension_id: str | None = None) -> list[ExtensionEventListenerDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.event_listeners)

        listeners: list[ExtensionEventListenerDefinition] = []
        for view in self._host.get_runtime_views():
            listeners.extend(view.event_listeners)
        return listeners


class ApplicationRealtimeService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host
        self._discussion_transports_by_extension: dict[str, tuple[ExtensionRealtimeDiscussionTransportDefinition, ...]] = {}

    def register_included_enricher(self, extension_id: str, definition: ExtensionRealtimeIncludedDefinition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        handler = getattr(definition, "handler", None)
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.realtime_included = tuple([
            *(
                item
                for item in view.realtime_included
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def register_discussion_visibility_resolver(self, extension_id: str, definition: ExtensionSystemHookDefinition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        handler = getattr(definition, "callback", None)
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        definition = replace(definition, module_id=definition.module_id or normalized_extension_id)
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.realtime_discussion_visibility = tuple([
            *(
                item
                for item in view.realtime_discussion_visibility
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def register_discussion_transport(
        self,
        extension_id: str,
        definition: ExtensionRealtimeDiscussionTransportDefinition,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        handler = getattr(definition, "handler", None)
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        current = tuple(
            item
            for item in self._discussion_transports_by_extension.get(normalized_extension_id, ())
            if str(getattr(item, "key", "") or "").strip() != normalized_key
        )
        definitions = tuple([*current, definition])
        self._discussion_transports_by_extension[normalized_extension_id] = definitions
        self._host._get_or_create_runtime_view(normalized_extension_id).realtime_discussion_transports = definitions

    def register_discussion_broadcast(
        self,
        extension_id: str,
        definition: ExtensionRealtimeDiscussionBroadcastDefinition,
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return

        event_type = self._resolve_event_type(definition.event_type)
        event_name_key = self._event_value_key(definition.event_name)
        if event_type is None or not event_name_key:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.realtime_discussion_broadcasts = tuple([
            *(
                item
                for item in view.realtime_discussion_broadcasts
                if not (
                    self._resolve_event_type(item.event_type) == event_type
                    and self._event_value_key(item.event_name) == event_name_key
                )
            ),
            replace(definition, event_type=event_type),
        ])

        handler = self._build_discussion_broadcast_handler(definition)
        self._host.event_bus.register(
            event_type,
            handler,
            listener_key=(
                "realtime.discussion",
                normalized_extension_id,
                self._event_type_key(event_type),
                event_name_key,
            ),
        )

    def get_included_enrichers(self, *, extension_id: str | None = None) -> list[ExtensionRealtimeIncludedDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.realtime_included)

        definitions: list[ExtensionRealtimeIncludedDefinition] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.realtime_included)
        return definitions

    def get_discussion_visibility_resolvers(self, *, extension_id: str | None = None) -> list[ExtensionSystemHookDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.realtime_discussion_visibility)

        definitions: list[ExtensionSystemHookDefinition] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.realtime_discussion_visibility)
        return definitions

    def get_discussion_transports(
        self,
        *,
        extension_id: str | None = None,
    ) -> list[ExtensionRealtimeDiscussionTransportDefinition]:
        if extension_id is not None:
            return list(self._discussion_transports_by_extension.get(str(extension_id or "").strip(), ()))

        definitions: list[ExtensionRealtimeDiscussionTransportDefinition] = []
        for items in self._discussion_transports_by_extension.values():
            definitions.extend(items)
        return definitions

    def broadcast_discussion_event(self, discussion_id: int, event_type: str, payload: dict) -> None:
        for definition in self.get_discussion_transports():
            handler = getattr(definition, "handler", None)
            if callable(handler):
                handler(discussion_id, event_type, payload)

    def get_discussion_broadcasts(
        self,
        *,
        extension_id: str | None = None,
    ) -> list[ExtensionRealtimeDiscussionBroadcastDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.realtime_discussion_broadcasts)

        definitions: list[ExtensionRealtimeDiscussionBroadcastDefinition] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.realtime_discussion_broadcasts)
        return definitions

    @staticmethod
    def _resolve_event_type(event_type: Any):
        if isinstance(event_type, str):
            try:
                resolved = import_string(event_type)
            except Exception:
                return None
            return resolved if isinstance(resolved, type) else None
        return event_type if isinstance(event_type, type) else None

    @staticmethod
    def _event_type_key(event_type: Any) -> str:
        return ":".join(
            item
            for item in (
                str(getattr(event_type, "__module__", "") or "").strip(),
                str(getattr(event_type, "__qualname__", "") or "").strip(),
            )
            if item
        ) or str(event_type)

    @staticmethod
    def _event_value_key(value: Any) -> str:
        if callable(value):
            return ":".join(
                item
                for item in (
                    str(getattr(value, "__module__", "") or "").strip(),
                    str(getattr(value, "__qualname__", "") or "").strip(),
                )
                if item
            ) or str(value)
        return str(value or "").strip()

    @staticmethod
    def _resolve_event_value(source: Any, event: Any, *, default: Any = None) -> Any:
        if source is None:
            return default
        if callable(source):
            try:
                return source(event)
            except TypeError:
                return source()
        if isinstance(source, str):
            return getattr(event, source, default)
        return source

    def _build_discussion_broadcast_handler(self, definition: ExtensionRealtimeDiscussionBroadcastDefinition):
        def handle(event) -> None:
            condition = getattr(definition, "condition", None)
            if condition is not None and not bool(self._resolve_event_value(condition, event, default=True)):
                return

            discussion_id = self._resolve_event_value(definition.discussion_id, event)
            try:
                normalized_discussion_id = int(discussion_id)
            except (TypeError, ValueError):
                return
            if normalized_discussion_id <= 0:
                return

            event_name = self._resolve_event_name(definition.event_name, event)
            normalized_event_name = str(event_name or "").strip()
            if not normalized_event_name:
                return

            post_id = self._resolve_event_value(definition.post_id, event)
            if post_id is None and definition.include_post:
                post_id = getattr(event, "post_id", None)
            try:
                normalized_post_id = int(post_id) if post_id is not None else None
            except (TypeError, ValueError):
                normalized_post_id = None

            extension_context = self._resolve_event_value(definition.extension_context, event, default=None)
            broadcaster = self._host.make("realtime.discussion_broadcaster", None)
            if not callable(broadcaster):
                raise RuntimeError("扩展运行时服务未注册: realtime.discussion_broadcaster")

            broadcaster(
                normalized_discussion_id,
                normalized_event_name,
                include_discussion=definition.include_discussion,
                include_post=definition.include_post,
                post_id=normalized_post_id,
                post_id_getter=definition.post_id_getter,
                extension_context=extension_context,
            )

        return handle

    @staticmethod
    def _resolve_event_name(source: Any, event: Any) -> Any:
        if callable(source):
            try:
                return source(event)
            except TypeError:
                return source()
        return source


class ApplicationForumPermissionService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register_checker(
        self,
        extension_id: str,
        key: str,
        handler,
        *,
        description: str = "",
    ) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(key or "").strip()
        if not normalized_extension_id or not normalized_key or not callable(handler):
            return

        definition = ApplicationForumPermissionChecker(
            key=normalized_key,
            handler=handler,
            description=str(description or "").strip(),
            module_id=normalized_extension_id,
        )
        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.forum_permission_checkers = tuple([
            *(
                item
                for item in view.forum_permission_checkers
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

        from apps.core.forum_permissions import register_forum_permission_checker

        register_forum_permission_checker(f"{normalized_extension_id}:{normalized_key}", handler)

    def get_checkers(self, *, extension_id: str | None = None) -> list[ApplicationForumPermissionChecker]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.forum_permission_checkers)

        definitions: list[ApplicationForumPermissionChecker] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.forum_permission_checkers)
        return definitions


class ApplicationDiscussionLifecycleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register(self, extension_id: str, definition: ExtensionDiscussionLifecycleDefinition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.discussion_lifecycle = tuple([
            *(
                item
                for item in view.discussion_lifecycle
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def prepare_create(self, *, user, payload: dict, context: dict | None = None) -> dict:
        return self._run_phase("prepare_create", user=user, payload=payload, context=context)

    def apply_create(self, *, discussion, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_create", discussion=discussion, states=states, context=context)

    def prepare_update(self, *, discussion, user, payload: dict, context: dict | None = None) -> dict:
        return self._run_phase("prepare_update", discussion=discussion, user=user, payload=payload, context=context)

    def apply_update(self, *, discussion, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_update", discussion=discussion, states=states, context=context)

    def prepare_delete(self, *, discussion, user, context: dict | None = None) -> dict:
        return self._run_phase("prepare_delete", discussion=discussion, user=user, context=context)

    def apply_delete(self, *, states: dict, context: dict | None = None) -> dict:
        return self._apply_phase("apply_delete", states=states, context=context)

    def apply_hidden(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_hidden", discussion=discussion, states={}, context=context)

    def apply_approved(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_approved", discussion=discussion, states={}, context=context)

    def apply_rejected(self, *, discussion, context: dict | None = None) -> dict:
        return self._apply_phase("apply_rejected", discussion=discussion, states={}, context=context)

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionDiscussionLifecycleDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.discussion_lifecycle)

        definitions: list[ExtensionDiscussionLifecycleDefinition] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.discussion_lifecycle)
        return definitions

    def _run_phase(self, phase: str, **kwargs) -> dict:
        states = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            result = handler(**kwargs)
            if result is not None:
                states[definition.key] = result
        return states

    def _apply_phase(self, phase: str, *, states: dict, **kwargs) -> dict:
        results = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            state = states.get(definition.key)
            result = handler(state=state, **kwargs)
            if isinstance(result, dict):
                results[definition.key] = result
        return results


class ApplicationPostLifecycleService:
    def __init__(self, host: "ExtensionHost") -> None:
        self._host = host

    def register(self, extension_id: str, definition: ExtensionPostLifecycleDefinition) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_key = str(getattr(definition, "key", "") or "").strip()
        if not normalized_extension_id or not normalized_key:
            return

        view = self._host._get_or_create_runtime_view(normalized_extension_id)
        view.post_lifecycle = tuple([
            *(
                item
                for item in view.post_lifecycle
                if str(getattr(item, "key", "") or "").strip() != normalized_key
            ),
            definition,
        ])

    def apply_created(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_created", post=post, context=context)

    def apply_updated(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_updated", post=post, context=context)

    def apply_approved(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_approved", post=post, context=context)

    def apply_hidden(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("apply_hidden", post=post, context=context)

    def prepare_delete(self, *, post, context: dict | None = None) -> dict:
        return self._apply_phase("prepare_delete", post=post, context=context)

    def apply_deleted(self, *, context: dict | None = None) -> dict:
        return self._apply_phase("apply_deleted", context=context)

    def get_definitions(self, *, extension_id: str | None = None) -> list[ExtensionPostLifecycleDefinition]:
        if extension_id is not None:
            view = self._host.get_runtime_view(extension_id)
            if view is None:
                return []
            return list(view.post_lifecycle)

        definitions: list[ExtensionPostLifecycleDefinition] = []
        for view in self._host.get_runtime_views():
            definitions.extend(view.post_lifecycle)
        return definitions

    def _apply_phase(self, phase: str, **kwargs) -> dict:
        results = {}
        for definition in self.get_definitions():
            handler = getattr(definition, phase, None)
            if not callable(handler):
                continue
            result = handler(**kwargs)
            if isinstance(result, dict):
                results[definition.key] = result
        return results


class ApplicationForumService:
    def __init__(self, host: "ExtensionHost", registry: "ForumRegistry") -> None:
        self._host = host
        self._registry = registry

    def register_permission(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_permission(definition)
        self._append_extension_tuple(extension_id, "permissions", definition)

    def register_admin_page(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_admin_page(definition)
        self._append_extension_tuple(extension_id, "admin_pages", definition)

    def register_notification_type(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_notification_type(definition)
        self._append_extension_tuple(extension_id, "notification_types", definition)

    def register_user_preference(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_user_preference(definition)
        self._append_extension_tuple(extension_id, "user_preferences", definition)

    def register_language_pack(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_language_pack(definition)
        self._append_extension_tuple(extension_id, "language_packs", definition)

    def register_post_type(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_post_type(definition)
        self._append_extension_tuple(extension_id, "post_types", definition)

    def register_search_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_search_filter(definition)
        self._append_extension_tuple(extension_id, "search_filters", definition)

    def register_discussion_list_query(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_list_query(definition)
        self._append_extension_tuple(extension_id, "discussion_list_queries", definition)

    def register_discussion_sort(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_sort(definition)
        self._append_extension_tuple(extension_id, "discussion_sorts", definition)

    def register_discussion_list_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_discussion_list_filter(definition)
        self._append_extension_tuple(extension_id, "discussion_list_filters", definition)

    def register_external_module_id(self, module_id: str) -> None:
        self._registry.register_external_module_id(module_id)

    def _append_extension_tuple(self, extension_id: str, field_name: str, definition: Any) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        view = self._host._get_or_create_runtime_view(normalized)
        setattr(view, field_name, tuple([*getattr(view, field_name), definition]))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._registry, item)


class ApplicationResourceService:
    def __init__(self, host: "ExtensionHost", registry: "ResourceRegistry") -> None:
        self._host = host
        self._registry = registry

    def register_resource(self, definition, *, extension_id: str = "") -> None:
        registered = self._registry.register_resource(definition)
        self._append_extension_tuple(extension_id, "resource_definitions", registered)

    def register_field(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_field(definition)
        self._append_extension_tuple(extension_id, "resource_fields", definition)

    def register_field_mutator(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_field_mutator(definition)
        self._append_extension_tuple(extension_id, "resource_field_mutators", definition)

    def register_relationship(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_relationship(definition)
        self._append_extension_tuple(extension_id, "resource_relationships", definition)

    def register_endpoint(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_endpoint(definition)
        self._append_extension_tuple(extension_id, "resource_endpoints", definition)

    def register_sort(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_sort(definition)
        self._append_extension_tuple(extension_id, "resource_sorts", definition)

    def register_filter(self, definition, *, extension_id: str = "") -> None:
        self._registry.register_filter(definition)
        self._append_extension_tuple(extension_id, "resource_filters", definition)

    def _append_extension_tuple(self, extension_id: str, field_name: str, definition: Any) -> None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return
        view = self._host._get_or_create_runtime_view(normalized)
        setattr(view, field_name, tuple([*getattr(view, field_name), definition]))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._registry, item)


@dataclass
class ExtensionApplicationRecord:
    extension_id: str
    name: str = ""
    source: str = ""
    module_ids: list[str] = field(default_factory=list)
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    frontend_common_entry: str = ""
    frontend_css: list[str] = field(default_factory=list)
    frontend_js_directories: list[str] = field(default_factory=list)
    frontend_preloads: list[Any] = field(default_factory=list)
    frontend_content_callbacks: list[Any] = field(default_factory=list)
    frontend_document_attributes: list[Any] = field(default_factory=list)
    frontend_head_tags: list[Any] = field(default_factory=list)
    frontend_theme_variables: list[Any] = field(default_factory=list)
    frontend_title_driver: Any = None
    frontend_routes: list[ExtensionFrontendRouteDefinition] = field(default_factory=list)
    settings_pages: list[str] = field(default_factory=list)
    permissions_pages: list[str] = field(default_factory=list)
    operations_pages: list[str] = field(default_factory=list)
    settings_schema: list[ExtensionManifestSettingFieldDefinition] = field(default_factory=list)
    settings_defaults: list[ExtensionSettingDefaultDefinition] = field(default_factory=list)
    settings_reset_rules: list[ExtensionSettingResetDefinition] = field(default_factory=list)
    settings_frontend_cache_keys: list[str] = field(default_factory=list)
    settings_theme_variables: list[ExtensionSettingThemeVariableDefinition] = field(default_factory=list)
    settings_forum_serializations: list[ExtensionSettingForumSerializationDefinition] = field(default_factory=list)
    forum_settings_keys: list[str] = field(default_factory=list)
    permissions: list[PermissionDefinition] = field(default_factory=list)
    admin_pages: list[AdminPageDefinition] = field(default_factory=list)
    notification_types: list[NotificationTypeDefinition] = field(default_factory=list)
    user_preferences: list[UserPreferenceDefinition] = field(default_factory=list)
    language_packs: list[LanguagePackDefinition] = field(default_factory=list)
    post_types: list[PostTypeDefinition] = field(default_factory=list)
    search_filters: list[SearchFilterDefinition] = field(default_factory=list)
    discussion_list_queries: list[DiscussionListQueryDefinition] = field(default_factory=list)
    discussion_sorts: list[DiscussionSortDefinition] = field(default_factory=list)
    discussion_list_filters: list[DiscussionListFilterDefinition] = field(default_factory=list)
    locale_paths: list[str] = field(default_factory=list)
    view_namespaces: list[ExtensionViewNamespaceDefinition] = field(default_factory=list)
    formatter_pipeline: list[ExtensionFormatterCallback] = field(default_factory=list)
    formatter_callbacks: list[ExtensionFormatterDefinition] = field(default_factory=list)
    resource_definitions: list[ExtensionResourceDefinition] = field(default_factory=list)
    resource_fields: list[ExtensionResourceFieldDefinition] = field(default_factory=list)
    resource_field_mutators: list[ExtensionResourceFieldMutatorDefinition] = field(default_factory=list)
    resource_relationships: list[ExtensionResourceRelationshipDefinition] = field(default_factory=list)
    resource_endpoints: list[ExtensionResourceEndpointDefinition] = field(default_factory=list)
    resource_sorts: list[ExtensionResourceSortDefinition] = field(default_factory=list)
    resource_filters: list[ExtensionResourceFilterDefinition] = field(default_factory=list)
    model_definitions: list[ExtensionModelDefinition] = field(default_factory=list)
    model_visibility: list[ExtensionModelVisibilityDefinition] = field(default_factory=list)
    model_relations: list[ExtensionModelRelationDefinition] = field(default_factory=list)
    model_casts: list[ExtensionModelCastDefinition] = field(default_factory=list)
    model_defaults: list[ExtensionModelDefaultDefinition] = field(default_factory=list)
    model_slug_drivers: list[ExtensionModelSlugDriverDefinition] = field(default_factory=list)
    search_drivers: list[ExtensionSearchDriverDefinition] = field(default_factory=list)
    search_indexes: list[ExtensionSearchIndexDefinition] = field(default_factory=list)
    validators: list[ExtensionValidatorDefinition] = field(default_factory=list)
    mailers: list[ExtensionMailDefinition] = field(default_factory=list)
    error_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    auth_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    csrf_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    filesystem_drivers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    console_commands: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    session_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    theme_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    throttle_api_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    user_handlers: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    signal_handlers: list[ExtensionSignalDefinition] = field(default_factory=list)
    event_listeners: list[ExtensionEventListenerDefinition] = field(default_factory=list)
    realtime_included: list[ExtensionRealtimeIncludedDefinition] = field(default_factory=list)
    realtime_discussion_visibility: list[ExtensionSystemHookDefinition] = field(default_factory=list)
    realtime_discussion_transports: list[ExtensionRealtimeDiscussionTransportDefinition] = field(default_factory=list)
    realtime_discussion_broadcasts: list[ExtensionRealtimeDiscussionBroadcastDefinition] = field(default_factory=list)
    forum_permission_checkers: list[ApplicationForumPermissionChecker] = field(default_factory=list)
    discussion_lifecycle: list[ExtensionDiscussionLifecycleDefinition] = field(default_factory=list)
    post_lifecycle: list[ExtensionPostLifecycleDefinition] = field(default_factory=list)
    runtime_actions: list[ExtensionManifestRuntimeActionDefinition] = field(default_factory=list)
    admin_actions: list[ExtensionAdminActionDefinition] = field(default_factory=list)
    route_mounts: list[ApplicationRouteMount] = field(default_factory=list)
    named_routes: list[ApplicationNamedRoute] = field(default_factory=list)
    websocket_routes: list[ApplicationWebSocketRoute] = field(default_factory=list)
    middleware_mounts: list[ApplicationMiddlewareMount] = field(default_factory=list)
    policy_mounts: list[ApplicationPolicyMount] = field(default_factory=list)
    service_providers: list[str] = field(default_factory=list)
    extender_keys: list[str] = field(default_factory=list)
    lifecycle_extender_keys: list[str] = field(default_factory=list)
    lifecycle_phase_keys: list[str] = field(default_factory=list)
    use_generated_settings_page: bool = False
    use_generated_permissions_page: bool = False
    use_generated_operations_page: bool = False

    @property
    def id(self) -> str:
        return self.extension_id


@dataclass
class ExtensionRuntimeView:
    extension_id: str
    name: str = ""
    source: str = ""
    path: str = ""
    module_ids: tuple[str, ...] = ()
    frontend_admin_entry: str = ""
    frontend_forum_entry: str = ""
    frontend_common_entry: str = ""
    frontend_css: tuple[str, ...] = ()
    frontend_js_directories: tuple[str, ...] = ()
    frontend_preloads: tuple[Any, ...] = ()
    frontend_content_callbacks: tuple[Any, ...] = ()
    frontend_document_attributes: tuple[Any, ...] = ()
    frontend_head_tags: tuple[Any, ...] = ()
    frontend_theme_variables: tuple[Any, ...] = ()
    frontend_title_driver: Any = None
    frontend_routes: tuple[ExtensionFrontendRouteDefinition, ...] = ()
    settings_pages: tuple[str, ...] = ()
    permissions_pages: tuple[str, ...] = ()
    operations_pages: tuple[str, ...] = ()
    settings_schema: tuple[ExtensionManifestSettingFieldDefinition, ...] = ()
    settings_defaults: tuple[ExtensionSettingDefaultDefinition, ...] = ()
    settings_reset_rules: tuple[ExtensionSettingResetDefinition, ...] = ()
    settings_frontend_cache_keys: tuple[str, ...] = ()
    settings_theme_variables: tuple[ExtensionSettingThemeVariableDefinition, ...] = ()
    settings_forum_serializations: tuple[ExtensionSettingForumSerializationDefinition, ...] = ()
    forum_settings_keys: tuple[str, ...] = ()
    permissions: tuple[PermissionDefinition, ...] = ()
    admin_pages: tuple[AdminPageDefinition, ...] = ()
    notification_types: tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: tuple[UserPreferenceDefinition, ...] = ()
    language_packs: tuple[LanguagePackDefinition, ...] = ()
    post_types: tuple[PostTypeDefinition, ...] = ()
    search_filters: tuple[SearchFilterDefinition, ...] = ()
    discussion_list_queries: tuple[DiscussionListQueryDefinition, ...] = ()
    discussion_sorts: tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: tuple[DiscussionListFilterDefinition, ...] = ()
    locale_paths: tuple[str, ...] = ()
    view_namespaces: tuple[ExtensionViewNamespaceDefinition, ...] = ()
    formatter_pipeline: tuple[ExtensionFormatterCallback, ...] = ()
    formatter_callbacks: tuple[ExtensionFormatterDefinition, ...] = ()
    resource_definitions: tuple[ExtensionResourceDefinition, ...] = ()
    resource_fields: tuple[ExtensionResourceFieldDefinition, ...] = ()
    resource_field_mutators: tuple[ExtensionResourceFieldMutatorDefinition, ...] = ()
    resource_relationships: tuple[ExtensionResourceRelationshipDefinition, ...] = ()
    resource_endpoints: tuple[ExtensionResourceEndpointDefinition, ...] = ()
    resource_sorts: tuple[ExtensionResourceSortDefinition, ...] = ()
    resource_filters: tuple[ExtensionResourceFilterDefinition, ...] = ()
    model_definitions: tuple[ExtensionModelDefinition, ...] = ()
    model_visibility: tuple[ExtensionModelVisibilityDefinition, ...] = ()
    model_relations: tuple[ExtensionModelRelationDefinition, ...] = ()
    model_casts: tuple[ExtensionModelCastDefinition, ...] = ()
    model_defaults: tuple[ExtensionModelDefaultDefinition, ...] = ()
    model_slug_drivers: tuple[ExtensionModelSlugDriverDefinition, ...] = ()
    search_drivers: tuple[ExtensionSearchDriverDefinition, ...] = ()
    search_indexes: tuple[ExtensionSearchIndexDefinition, ...] = ()
    validators: tuple[ExtensionValidatorDefinition, ...] = ()
    mailers: tuple[ExtensionMailDefinition, ...] = ()
    error_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    auth_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    csrf_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    filesystem_drivers: tuple[ExtensionSystemHookDefinition, ...] = ()
    console_commands: tuple[ExtensionSystemHookDefinition, ...] = ()
    session_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    theme_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    throttle_api_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    user_handlers: tuple[ExtensionSystemHookDefinition, ...] = ()
    signal_handlers: tuple[ExtensionSignalDefinition, ...] = ()
    event_listeners: tuple[ExtensionEventListenerDefinition, ...] = ()
    realtime_included: tuple[ExtensionRealtimeIncludedDefinition, ...] = ()
    realtime_discussion_visibility: tuple[ExtensionSystemHookDefinition, ...] = ()
    realtime_discussion_transports: tuple[ExtensionRealtimeDiscussionTransportDefinition, ...] = ()
    realtime_discussion_broadcasts: tuple[ExtensionRealtimeDiscussionBroadcastDefinition, ...] = ()
    forum_permission_checkers: tuple[ApplicationForumPermissionChecker, ...] = ()
    discussion_lifecycle: tuple[ExtensionDiscussionLifecycleDefinition, ...] = ()
    post_lifecycle: tuple[ExtensionPostLifecycleDefinition, ...] = ()
    runtime_actions: tuple[ExtensionManifestRuntimeActionDefinition, ...] = ()
    admin_actions: tuple[ExtensionAdminActionDefinition, ...] = ()
    route_mounts: tuple[ApplicationRouteMount, ...] = ()
    named_routes: tuple[ApplicationNamedRoute, ...] = ()
    websocket_routes: tuple[ApplicationWebSocketRoute, ...] = ()
    middleware_mounts: tuple[ApplicationMiddlewareMount, ...] = ()
    policy_mounts: tuple[ApplicationPolicyMount, ...] = ()
    service_providers: tuple[str, ...] = ()
    extender_keys: tuple[str, ...] = ()
    lifecycle_extender_keys: tuple[str, ...] = ()
    lifecycle_phase_keys: tuple[str, ...] = ()
    use_generated_settings_page: bool = False
    use_generated_permissions_page: bool = False
    use_generated_operations_page: bool = False

    @property
    def id(self) -> str:
        return self.extension_id


class ExtensionApplication:
    def __init__(
        self,
        *,
        extensions_to_boot: tuple["Extension", ...] | list["Extension"] = (),
        extensions_to_catalog: tuple["Extension", ...] | list["Extension"] = (),
        forum_registry: "ForumRegistry | None" = None,
        resource_registry: "ResourceRegistry | None" = None,
        event_bus: DomainEventBus | None = None,
    ) -> None:
        if forum_registry is None:
            from apps.core.forum_registry import ForumRegistry

            forum_registry = ForumRegistry()
        if resource_registry is None:
            from apps.core.resource_registry import ResourceRegistry

            resource_registry = ResourceRegistry()

        self.extensions_to_boot = tuple(extensions_to_boot or ())
        self.extensions_to_catalog = tuple(extensions_to_catalog or self.extensions_to_boot)
        self.forum_registry = forum_registry
        self.resource_registry = resource_registry
        self.event_bus = event_bus or DomainEventBus()

        self._runtime_views: dict[str, ExtensionRuntimeView] = {}
        self._booted_extensions: dict[str, Extension] = {
            extension.id: extension
            for extension in self.extensions_to_boot
        }
        self._bindings: dict[str, ContainerResolver] = {}
        self._singletons: dict[str, ContainerResolver] = {}
        self._instances: dict[str, Any] = {}
        self._aliases: dict[str, str] = {}
        self._tags: dict[str, list[str]] = {}
        self._service_extenders: dict[str, list[ContainerExtender]] = {}
        self._resolving_callbacks: dict[str, list[ResolvingCallback]] = {}
        self._lifecycle_extenders: dict[str, list[Any]] = {}
        self._booting_callbacks: list[LifecycleCallback] = []
        self._booted_callbacks: list[LifecycleCallback] = []
        self._booted = False
        self._booting = False
        self.forum = ApplicationForumService(self, self.forum_registry)
        self.resources = ApplicationResourceService(self, self.resource_registry)
        self.models = ApplicationModelService(self)
        self.model_urls = ApplicationModelUrlService(self)
        self.search = ApplicationSearchService(self)
        self.validators = ApplicationValidatorService(self)
        self.mail = ApplicationMailService(self)
        self.views = ApplicationViewService(self)
        self.error_handling = ApplicationSystemHookService(self, "error_handlers")
        self.auth = ApplicationSystemHookService(self, "auth_handlers")
        self.csrf = ApplicationSystemHookService(self, "csrf_handlers")
        self.filesystem = ApplicationSystemHookService(self, "filesystem_drivers")
        self.console = ApplicationSystemHookService(self, "console_commands")
        self.sessions = ApplicationSystemHookService(self, "session_handlers")
        self.theme = ApplicationSystemHookService(self, "theme_handlers")
        self.throttle_api = ApplicationSystemHookService(self, "throttle_api_handlers")
        self.user = ApplicationSystemHookService(self, "user_handlers")
        self.signals = ApplicationSignalService(self)
        self.routes = ApplicationRouteService(self)
        self.websocket_routes = ApplicationWebSocketRouteService(self)
        self.frontend = ApplicationFrontendService(self)
        self.providers = ApplicationServiceProviderRegistry(self)
        self.locales = ApplicationLocaleService(self)
        self.formatters = ApplicationFormatterService(self)
        self.settings = ApplicationSettingsService(self)
        self.actions = ApplicationAdminActionService(self)
        self.middleware = ApplicationMiddlewareService(self)
        self.policies = ApplicationPolicyService(self)
        self.events = ApplicationEventService(self, self.event_bus)
        self.realtime = ApplicationRealtimeService(self)
        self.forum_permissions = ApplicationForumPermissionService(self)
        self.discussion_lifecycle = ApplicationDiscussionLifecycleService(self)
        self.post_lifecycle = ApplicationPostLifecycleService(self)
        self.post_events = ApplicationPostEventDataService(self)

        self.instance("app", self)
        self.instance("host", self)
        self.instance("extensions.app", self)
        self.instance("extensions.host", self)
        self.instance("forum", self.forum)
        self.instance("extensions.forum", self.forum)
        self.instance("routes", self.routes)
        self.instance("extensions.routes", self.routes)
        self.instance("websocket.routes", self.websocket_routes)
        self.instance("extensions.websocket.routes", self.websocket_routes)
        self.instance("frontend", self.frontend)
        self.instance("extensions.frontend", self.frontend)
        self.instance("resources", self.resources)
        self.instance("extensions.resources", self.resources)
        self.instance("models", self.models)
        self.instance("extensions.models", self.models)
        self.instance("model.urls", self.model_urls)
        self.instance("extensions.model.urls", self.model_urls)
        self.instance("search", self.search)
        self.instance("extensions.search", self.search)
        self.instance("validators", self.validators)
        self.instance("extensions.validators", self.validators)
        self.instance("mail", self.mail)
        self.instance("extensions.mail", self.mail)
        self.instance("views", self.views)
        self.instance("extensions.views", self.views)
        self.instance("error.handling", self.error_handling)
        self.instance("extensions.error.handling", self.error_handling)
        self.instance("auth", self.auth)
        self.instance("extensions.auth", self.auth)
        self.instance("csrf", self.csrf)
        self.instance("extensions.csrf", self.csrf)
        self.instance("filesystem", self.filesystem)
        self.instance("extensions.filesystem", self.filesystem)
        self.instance("console", self.console)
        self.instance("extensions.console", self.console)
        self.instance("session", self.sessions)
        self.instance("extensions.session", self.sessions)
        self.instance("theme", self.theme)
        self.instance("extensions.theme", self.theme)
        self.instance("throttle.api", self.throttle_api)
        self.instance("extensions.throttle.api", self.throttle_api)
        self.instance("user", self.user)
        self.instance("extensions.user", self.user)
        self.instance("signals", self.signals)
        self.instance("extensions.signals", self.signals)
        self.instance("providers", self.providers)
        self.instance("extensions.providers", self.providers)
        self.instance("locales", self.locales)
        self.instance("extensions.locales", self.locales)
        self.instance("formatters", self.formatters)
        self.instance("extensions.formatters", self.formatters)
        self.instance("settings", self.settings)
        self.instance("extensions.settings", self.settings)
        self.instance("actions", self.actions)
        self.instance("extensions.actions", self.actions)
        self.instance("middleware", self.middleware)
        self.instance("extensions.middleware", self.middleware)
        self.instance("policies", self.policies)
        self.instance("extensions.policies", self.policies)
        self.instance("events", self.events)
        self.instance("extensions.events", self.events)
        self.instance("realtime", self.realtime)
        self.instance("extensions.realtime", self.realtime)
        self.instance("forum.permissions", self.forum_permissions)
        self.instance("extensions.forum.permissions", self.forum_permissions)
        self.instance("discussion.lifecycle", self.discussion_lifecycle)
        self.instance("extensions.discussion.lifecycle", self.discussion_lifecycle)
        self.instance("post.lifecycle", self.post_lifecycle)
        self.instance("extensions.post.lifecycle", self.post_lifecycle)
        self.instance("post.events", self.post_events)
        self.instance("extensions.post.events", self.post_events)
        self.instance("forum.registry", self.forum_registry)
        self.instance("resource.registry", self.resource_registry)
        self.instance("event.bus", self.event_bus)
        self.instance("bias.api.resources", [])
        self.singleton("api.application", lambda host: _build_api_application_from_host(host))
        try:
            from apps.core.forum_runtime import set_realtime_service

            set_realtime_service(self.realtime)
        except Exception:
            logger.warning("Failed to bind extension realtime service to forum runtime.", exc_info=True)

    def booting(self, callback: LifecycleCallback) -> None:
        if callable(callback):
            self._booting_callbacks.append(callback)

    def booted(self, callback: LifecycleCallback) -> None:
        if callable(callback):
            self._booted_callbacks.append(callback)

    def is_booted(self) -> bool:
        return self._booted

    def boot(self) -> "ExtensionApplication":
        if self._booted or self._booting:
            return self

        self._booting = True
        try:
            self._run_booting_callbacks()
            self._register_extensions()
            self._boot_extension_providers()
            self._mark_extensions_ready()
        finally:
            self._booting = False

        return self

    def _run_booting_callbacks(self) -> None:
        for callback in list(self._booting_callbacks):
            callback(self)

    def _register_extensions(self) -> None:
        for extension in self.extensions_to_catalog:
            if extension.source != "site":
                self.forum.register_extension_module(extension)
        for extension in self.extensions_to_boot:
            if extension.source != "site":
                self.forum.register_external_module_id(extension.id)
            self._mark_extension_lifecycle_phase(extension.id, "register")
            extension.register(self)

    def _boot_extension_providers(self) -> None:
        self.providers.boot()
        self.make("validators")
        self.make("mail")
        self.make("error.handling")
        self.make("auth")
        self.make("csrf")
        self.make("filesystem")
        self.make("console")
        self.make("session")
        self.make("theme")
        self.make("throttle.api")
        self.make("signals")
        for extension in self.extensions_to_boot:
            self._mark_extension_lifecycle_phase(extension.id, "boot")

    def _mark_extensions_ready(self) -> None:
        self._booted = True
        for callback in list(self._booted_callbacks):
            callback(self)
        for extension in self.extensions_to_boot:
            self._mark_extension_lifecycle_phase(extension.id, "ready")

    def apply_extension_extenders(
        self,
        extension,
        extenders,
    ) -> ExtensionRuntimeView:
        from apps.core.extensions.extender_values import flatten_extenders

        runtime_view = self.get_or_create_runtime_view(
            extension.id,
            name=extension.name,
            source=extension.source,
            path=getattr(getattr(extension, "manifest", None), "path", ""),
            module_ids=extension.module_ids or (extension.id,),
        )
        normalized_extenders = flatten_extenders(extenders)
        for extender in normalized_extenders:
            extend_fn = getattr(extender, "extend", None)
            if not callable(extend_fn):
                continue
            self._mark_extension_extender(extension.id, extender)
            try:
                extend_fn(self, runtime_view)
            except Exception as exc:
                raise ExtensionBootError(extension.id, extender, exc) from exc
        return runtime_view

    def register_lifecycle_extender(self, extension_id: str, extender: Any) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id or extender is None:
            return

        current = self._lifecycle_extenders.setdefault(normalized_extension_id, [])
        if extender not in current:
            current.append(extender)

        extender_key = extender.__class__.__name__
        view = self._get_or_create_runtime_view(normalized_extension_id)
        if extender_key and extender_key not in view.lifecycle_extender_keys:
            view.lifecycle_extender_keys = tuple([*view.lifecycle_extender_keys, extender_key])

    def get_lifecycle_extenders(self, extension_id: str) -> list[Any]:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return []
        return list(self._lifecycle_extenders.get(normalized_extension_id, ()))

    def register(self, provider: Any, *, key: str = "", extension_id: str = "core", singleton: bool = True) -> str:
        resolved_key = str(key or "").strip()
        if not resolved_key:
            if isinstance(provider, str):
                resolved_key = provider
            else:
                provider_class = provider if isinstance(provider, type) else type(provider)
                resolved_key = f"{provider_class.__module__}.{provider_class.__name__}"
        return self.providers.register_provider(
            extension_id,
            resolved_key,
            provider,
            singleton=singleton,
        )

    def bind(self, key: str, resolver: ContainerResolver) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        self._bindings[normalized] = resolver
        self._instances.pop(normalized, None)

    def singleton(self, key: str, resolver: ContainerResolver) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        self._singletons[normalized] = resolver
        self._instances.pop(normalized, None)

    def instance(self, key: str, value: Any) -> None:
        normalized = self._container_key(key)
        if not normalized:
            return
        normalized = self._resolve_alias(normalized)
        resolved = self._apply_service_extenders(normalized, value)
        self._instances[normalized] = self._apply_resolving_callbacks(normalized, resolved)

    def extend(self, key: str, extender: ContainerExtender) -> None:
        normalized = self._container_key(key)
        if not normalized or not callable(extender):
            return
        normalized = self._resolve_alias(normalized)
        self._service_extenders.setdefault(normalized, []).append(extender)
        if normalized in self._instances:
            self._instances[normalized] = self._apply_service_extenders(normalized, self._instances[normalized])
            self._instances[normalized] = self._apply_resolving_callbacks(normalized, self._instances[normalized])

    def resolving(self, key: str, callback: ResolvingCallback) -> None:
        normalized = self._container_key(key)
        if not normalized or not callable(callback):
            return
        normalized = self._resolve_alias(normalized)
        self._resolving_callbacks.setdefault(normalized, []).append(callback)
        if normalized in self._instances:
            self._instances[normalized] = callback(self._instances[normalized], self)

    def alias(self, abstract: Any, alias: str) -> None:
        target = self._container_key(abstract)
        normalized_alias = self._container_key(alias)
        if target and normalized_alias and target != normalized_alias:
            self._aliases[normalized_alias] = self._resolve_alias(target)

    def tag(self, keys, tag: str) -> None:
        normalized_tag = self._container_key(tag)
        if not normalized_tag:
            return
        current = self._tags.setdefault(normalized_tag, [])
        iterable = keys if isinstance(keys, (list, tuple, set)) else (keys,)
        for key in iterable:
            normalized = self._resolve_alias(self._container_key(key))
            if normalized and normalized not in current:
                current.append(normalized)

    def tagged(self, tag: str) -> list[Any]:
        normalized_tag = self._container_key(tag)
        return [self.make(key) for key in self._tags.get(normalized_tag, ())]

    def has(self, key: str) -> bool:
        normalized = self._resolve_alias(self._container_key(key))
        return (
            normalized in self._instances
            or normalized in self._singletons
            or normalized in self._bindings
            or self._is_class_key(normalized)
        )

    def make(self, key: str, default: Any = UNSET) -> Any:
        normalized = self._resolve_alias(self._container_key(key))
        if normalized in self._instances:
            return self._instances[normalized]

        if normalized in self._singletons:
            resolved = self._resolve_service(self._singletons[normalized])
            resolved = self._apply_service_extenders(normalized, resolved)
            self._instances[normalized] = self._apply_resolving_callbacks(normalized, resolved)
            return self._instances[normalized]

        if normalized in self._bindings:
            resolved = self._resolve_service(self._bindings[normalized])
            resolved = self._apply_service_extenders(normalized, resolved)
            return self._apply_resolving_callbacks(normalized, resolved)

        if default is not UNSET:
            return default

        if self._is_class_key(normalized):
            return self._make_class(normalized)

        raise KeyError(f"服务未注册: {normalized}")

    def get(self, key: str, default: Any = UNSET) -> Any:
        return self.make(key, default)

    def register_service(self, key: str, value: Any) -> None:
        self.instance(key, value)

    def get_service(self, key: str, default: Any = None) -> Any:
        return self.make(key, default)

    def get_or_create_runtime_view(
        self,
        extension_id: str,
        *,
        name: str = "",
        source: str = "",
        path: str = "",
        module_ids: tuple[str, ...] | list[str] = (),
    ) -> ExtensionRuntimeView:
        normalized = str(extension_id or "").strip()
        return self._get_or_create_runtime_view(
            normalized,
            name=name,
            source=source,
            path=path,
            module_ids=module_ids,
        )

    def get_records(self) -> list[ExtensionApplicationRecord]:
        return [
            self._build_application_record(view)
            for view in self.get_runtime_views()
        ]

    def get_runtime_views(self) -> list[ExtensionRuntimeView]:
        return list(self._runtime_views.values())

    def get_runtime_view(self, extension_id: str) -> ExtensionRuntimeView | None:
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._runtime_views.get(normalized)

    def get_extension_views(self) -> list[ExtensionRuntimeView]:
        return self.get_runtime_views()

    def get_extension_view(self, extension_id: str) -> ExtensionRuntimeView | None:
        return self.get_runtime_view(extension_id)

    def get_booted_extensions(self) -> list["Extension"]:
        return list(self._booted_extensions.values())

    def get_booted_extension(self, extension_id: str) -> "Extension | None":
        normalized = str(extension_id or "").strip()
        if not normalized:
            return None
        return self._booted_extensions.get(normalized)

    def get_runtime_extensions(self) -> list["Extension"]:
        return self.get_booted_extensions()

    def get_runtime_extension(self, extension_id: str) -> "Extension | None":
        return self.get_booted_extension(extension_id)

    def register_frontend_entry(
        self,
        extension: ExtensionRuntimeView,
        *,
        admin_entry: str = "",
        forum_entry: str = "",
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        frontend = self.frontend.register_entries(
            extension.extension_id,
            admin_entry=admin_entry,
            forum_entry=forum_entry,
        )
        view.frontend_admin_entry = frontend.admin_entry
        view.frontend_forum_entry = frontend.forum_entry
        view.frontend_common_entry = frontend.common_entry

    def register_admin_surface_pages(
        self,
        extension: ExtensionRuntimeView,
        *,
        settings_pages=(),
        permissions_pages=(),
        operations_pages=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        frontend = self.frontend.register_pages(
            extension.extension_id,
            settings_pages=settings_pages,
            permissions_pages=permissions_pages,
            operations_pages=operations_pages,
        )
        view.settings_pages = frontend.settings_pages
        view.permissions_pages = frontend.permissions_pages
        view.operations_pages = frontend.operations_pages

    def register_locale_path(self, extension: ExtensionRuntimeView, path: str) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(path or "").strip()
        if normalized and normalized not in view.locale_paths:
            view.locale_paths = tuple([*view.locale_paths, normalized])

    def register_formatter(self, extension: ExtensionRuntimeView, callback) -> None:
        self.formatters.register_render(extension.extension_id, callback)

    def register_settings_fields(
        self,
        extension: ExtensionRuntimeView,
        fields,
        *,
        expose_to_forum=(),
        generated_page: bool = True,
        defaults=(),
        reset_when=(),
        reset_frontend_cache_for=(),
        theme_variables=(),
        forum_serializations=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        fields_collection = list(view.settings_schema)
        for field in fields or ():
            fields_collection.append(field)
        view.settings_schema = tuple(fields_collection)
        view.settings_defaults = tuple([*view.settings_defaults, *(defaults or ())])
        view.settings_reset_rules = tuple([*view.settings_reset_rules, *(reset_when or ())])
        cache_keys = list(view.settings_frontend_cache_keys)
        for key in reset_frontend_cache_for or ():
            normalized = str(key or "").strip()
            if normalized and normalized not in cache_keys:
                cache_keys.append(normalized)
        view.settings_frontend_cache_keys = tuple(cache_keys)
        view.settings_theme_variables = tuple([*view.settings_theme_variables, *(theme_variables or ())])
        view.settings_forum_serializations = tuple([
            *view.settings_forum_serializations,
            *(forum_serializations or ()),
        ])
        forum_keys = list(view.forum_settings_keys)
        for key in expose_to_forum or ():
            normalized = str(key or "").strip()
            if normalized and normalized not in forum_keys:
                forum_keys.append(normalized)
        view.forum_settings_keys = tuple(forum_keys)
        if generated_page:
            view.use_generated_settings_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/settings"
            self.register_admin_surface_pages(extension, settings_pages=(generated_path,))

    def register_runtime_actions(
        self,
        extension: ExtensionRuntimeView,
        actions,
        *,
        generated_page: bool = False,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        collection = list(view.runtime_actions)
        for action in actions or ():
            collection.append(action)
        view.runtime_actions = tuple(collection)
        if generated_page:
            view.use_generated_operations_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/operations"
            self.register_admin_surface_pages(extension, operations_pages=(generated_path,))

    def register_admin_actions(
        self,
        extension: ExtensionRuntimeView,
        actions,
        *,
        generated_permissions_page: bool = False,
        generated_operations_page: bool = False,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        collection = list(view.admin_actions)
        for action in actions or ():
            collection.append(action)
        view.admin_actions = tuple(collection)
        if generated_permissions_page:
            view.use_generated_permissions_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/permissions"
            self.register_admin_surface_pages(extension, permissions_pages=(generated_path,))
        if generated_operations_page:
            view.use_generated_operations_page = True
            generated_path = f"/admin/extensions/{extension.extension_id}/operations"
            self.register_admin_surface_pages(extension, operations_pages=(generated_path,))

    def mark_generated_permissions_page(self, extension: ExtensionRuntimeView) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.use_generated_permissions_page = True
        generated_path = f"/admin/extensions/{extension.extension_id}/permissions"
        self.register_admin_surface_pages(extension, permissions_pages=(generated_path,))

    def register_forum_module_id(self, extension: ExtensionRuntimeView, module_id: str) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(module_id or "").strip()
        if normalized:
            self.forum_registry.register_external_module_id(normalized)
            if normalized not in view.module_ids:
                view.module_ids = tuple([*view.module_ids, normalized])

    def register_permission(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.permissions = tuple([*view.permissions, definition])
        self.forum.register_permission(definition)

    def register_admin_page(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.admin_pages = tuple([*view.admin_pages, definition])
        self.forum.register_admin_page(definition)

    def register_notification_type(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.notification_types = tuple([*view.notification_types, definition])
        self.forum.register_notification_type(definition)

    def register_user_preference(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.user_preferences = tuple([*view.user_preferences, definition])
        self.forum.register_user_preference(definition)

    def register_language_pack(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.language_packs = tuple([*view.language_packs, definition])
        self.forum.register_language_pack(definition)

    def register_post_type(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.post_types = tuple([*view.post_types, definition])
        self.forum.register_post_type(definition)

    def register_search_filter(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.search_filters = tuple([*view.search_filters, definition])
        self.forum.register_search_filter(definition)

    def register_discussion_list_query(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_list_queries = tuple([*view.discussion_list_queries, definition])
        self.forum.register_discussion_list_query(definition)

    def register_discussion_sort(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_sorts = tuple([*view.discussion_sorts, definition])
        self.forum.register_discussion_sort(definition)

    def register_discussion_list_filter(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.discussion_list_filters = tuple([*view.discussion_list_filters, definition])
        self.forum.register_discussion_list_filter(definition)

    def register_resource(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_definitions = tuple([*view.resource_definitions, definition])
        self.resources.register_resource(definition)

    def register_resource_field(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_fields = tuple([*view.resource_fields, definition])
        self.resources.register_field(definition)

    def register_resource_relationship(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.resource_relationships = tuple([*view.resource_relationships, definition])
        self.resources.register_relationship(definition)

    def register_event_listener(self, extension: ExtensionRuntimeView, definition) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.event_listeners = tuple([*view.event_listeners, definition])
        self.event_bus.register(definition.event_type, definition.handler)

    def register_route_mount(
        self,
        extension: ExtensionRuntimeView,
        prefix: str,
        router,
        *,
        tags=(),
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        mount = self.routes.mount(extension.extension_id, prefix, router, tags=tags)
        if mount is None:
            return
        view.route_mounts = tuple(self.routes.get_mounts(extension_id=extension.extension_id))

    def register_service_provider(
        self,
        extension: ExtensionRuntimeView,
        provider_name: str,
        provider: Any | None = None,
        *,
        singleton: bool = True,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(provider_name or "").strip()
        if not normalized or provider is None:
            return
        registered_key = self.providers.register(
            extension.extension_id,
            ApplicationServiceProvider(
                key=normalized,
                target=provider,
                singleton=singleton,
            ),
        )
        if registered_key:
            view.service_providers = tuple(self.providers.get_provider_keys(extension_id=extension.extension_id))

    def register_middleware_mount(
        self,
        extension: ExtensionRuntimeView,
        target: str,
        middleware,
        *,
        order: int = 100,
    ) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        view.middleware_mounts = tuple([*view.middleware_mounts, ApplicationMiddlewareMount(
            target=str(target or "").strip() or "api",
            middleware=middleware,
            order=int(order),
        )])

    def register_policy_mount(self, extension: ExtensionRuntimeView, key: str, handler) -> None:
        view = self._get_or_create_runtime_view(extension.extension_id)
        normalized = str(key or "").strip()
        if normalized and callable(handler):
            view.policy_mounts = tuple([*view.policy_mounts, ApplicationPolicyMount(
                key=normalized,
                handler=handler,
            )])

    def get_route_mounts(self) -> list[ApplicationRouteMount]:
        return self.routes.get_mounts()

    def get_named_routes(self, *, app_name: str | None = None) -> list[ApplicationNamedRoute]:
        return self.routes.get_routes(app_name=app_name)

    def get_websocket_routes(self) -> list[ApplicationWebSocketRoute]:
        return self.websocket_routes.get_routes()

    def get_frontend_extension(self, extension_id: str) -> ApplicationFrontendExtension | None:
        return self.frontend.get_extension(extension_id)

    def get_frontend_extensions(self) -> list[ApplicationFrontendExtension]:
        return self.frontend.get_extensions()

    def get_service_provider_keys(self, *, extension_id: str | None = None) -> list[str]:
        return self.providers.get_provider_keys(extension_id=extension_id)

    def get_middleware_mounts(self, *, target: str | None = None) -> list[ApplicationMiddlewareMount]:
        mounts: list[ApplicationMiddlewareMount] = []
        for view in self.get_runtime_views():
            mounts.extend(view.middleware_mounts)
        if target is not None:
            mounts = [item for item in mounts if item.target == target]
        return sorted(mounts, key=lambda item: (item.target, item.order))

    def get_policy_mounts(self) -> list[ApplicationPolicyMount]:
        mounts: list[ApplicationPolicyMount] = []
        for view in self.get_runtime_views():
            mounts.extend(view.policy_mounts)
        return mounts

    @staticmethod
    def _container_key(key: Any) -> str:
        if isinstance(key, type):
            return f"{key.__module__}.{key.__name__}"
        return str(key or "").strip()

    def _resolve_alias(self, key: str) -> str:
        normalized = str(key or "").strip()
        seen = set()
        while normalized in self._aliases and normalized not in seen:
            seen.add(normalized)
            normalized = self._aliases[normalized]
        return normalized

    @staticmethod
    def _is_class_key(key: str) -> bool:
        return "." in str(key or "").strip()

    def _make_class(self, key: str) -> Any:
        try:
            cls = import_string(key)
        except (ImportError, AttributeError):
            short = key.rsplit(".", 1)[-1]
            if short and short in self._instances:
                return self._instances[short]
            raise KeyError(f"服务未注册: {key}")
        resolved = resolve_container_value(cls, self)
        resolved = self._apply_service_extenders(key, resolved)
        return self._apply_resolving_callbacks(key, resolved)

    def _resolve_service(self, resolver: ContainerResolver | Any) -> Any:
        resolver = resolve_container_value(resolver, self, _skip_container_lookup=True)
        if callable(resolver):
            try:
                return resolver(self)
            except TypeError:
                return resolver()
        return resolver

    def _get_or_create_runtime_view(
        self,
        extension_id: str,
        *,
        name: str = "",
        source: str = "",
        path: str = "",
        module_ids: tuple[str, ...] | list[str] = (),
    ) -> ExtensionRuntimeView:
        normalized = str(extension_id or "").strip()
        if normalized not in self._runtime_views:
            self._runtime_views[normalized] = ExtensionRuntimeView(
                extension_id=normalized,
                name=str(name or "").strip(),
                source=str(source or "").strip(),
                path=str(path or "").strip(),
                module_ids=tuple(
                    item for item in dict.fromkeys(str(item).strip() for item in module_ids)
                    if item
                ),
            )
        view = self._runtime_views[normalized]
        if name:
            view.name = str(name).strip()
        if source:
            view.source = str(source).strip()
        if path:
            view.path = str(path).strip()
        if module_ids:
            view.module_ids = tuple(
                item for item in dict.fromkeys(str(item).strip() for item in module_ids)
                if item
            )
        return view

    def _mark_extension_lifecycle_phase(self, extension_id: str, phase_key: str) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        normalized_phase_key = str(phase_key or "").strip()
        if not normalized_extension_id or not normalized_phase_key:
            return

        view = self._get_or_create_runtime_view(normalized_extension_id)
        if normalized_phase_key in view.lifecycle_phase_keys:
            return
        view.lifecycle_phase_keys = tuple([*view.lifecycle_phase_keys, normalized_phase_key])

    def _mark_extension_extender(self, extension_id: str, extender: Any) -> None:
        normalized_extension_id = str(extension_id or "").strip()
        if not normalized_extension_id:
            return
        extender_key = extender.__class__.__name__
        if not extender_key:
            return
        view = self._get_or_create_runtime_view(normalized_extension_id)
        if extender_key in view.extender_keys:
            return
        view.extender_keys = tuple([*view.extender_keys, extender_key])

    def _build_application_record(self, view: ExtensionRuntimeView) -> ExtensionApplicationRecord:
        return ExtensionApplicationRecord(
            extension_id=view.extension_id,
            name=view.name,
            source=view.source,
            module_ids=list(view.module_ids),
            frontend_admin_entry=view.frontend_admin_entry,
            frontend_forum_entry=view.frontend_forum_entry,
            frontend_common_entry=view.frontend_common_entry,
            frontend_css=list(view.frontend_css),
            frontend_js_directories=list(view.frontend_js_directories),
            frontend_preloads=list(view.frontend_preloads),
            frontend_content_callbacks=list(view.frontend_content_callbacks),
            frontend_document_attributes=list(view.frontend_document_attributes),
            frontend_head_tags=list(view.frontend_head_tags),
            frontend_theme_variables=list(view.frontend_theme_variables),
            frontend_title_driver=view.frontend_title_driver,
            frontend_routes=list(view.frontend_routes),
            settings_pages=list(view.settings_pages),
            permissions_pages=list(view.permissions_pages),
            operations_pages=list(view.operations_pages),
            settings_schema=list(view.settings_schema),
            settings_defaults=list(view.settings_defaults),
            settings_reset_rules=list(view.settings_reset_rules),
            settings_frontend_cache_keys=list(view.settings_frontend_cache_keys),
            settings_theme_variables=list(view.settings_theme_variables),
            settings_forum_serializations=list(view.settings_forum_serializations),
            forum_settings_keys=list(view.forum_settings_keys),
            permissions=list(view.permissions),
            admin_pages=list(view.admin_pages),
            notification_types=list(view.notification_types),
            user_preferences=list(view.user_preferences),
            language_packs=list(view.language_packs),
            post_types=list(view.post_types),
            search_filters=list(view.search_filters),
            discussion_list_queries=list(view.discussion_list_queries),
            discussion_sorts=list(view.discussion_sorts),
            discussion_list_filters=list(view.discussion_list_filters),
            locale_paths=list(view.locale_paths),
            view_namespaces=list(view.view_namespaces),
            formatter_pipeline=list(view.formatter_pipeline),
            formatter_callbacks=list(view.formatter_callbacks),
            resource_definitions=list(view.resource_definitions),
            resource_fields=list(view.resource_fields),
            resource_field_mutators=list(view.resource_field_mutators),
            resource_relationships=list(view.resource_relationships),
            resource_endpoints=list(view.resource_endpoints),
            resource_sorts=list(view.resource_sorts),
            resource_filters=list(view.resource_filters),
            model_definitions=list(view.model_definitions),
            model_visibility=list(view.model_visibility),
            model_relations=list(view.model_relations),
            model_casts=list(view.model_casts),
            model_defaults=list(view.model_defaults),
            model_slug_drivers=list(view.model_slug_drivers),
            search_drivers=list(view.search_drivers),
            search_indexes=list(view.search_indexes),
            validators=list(view.validators),
            mailers=list(view.mailers),
            error_handlers=list(view.error_handlers),
            auth_handlers=list(view.auth_handlers),
            csrf_handlers=list(view.csrf_handlers),
            filesystem_drivers=list(view.filesystem_drivers),
            console_commands=list(view.console_commands),
            session_handlers=list(view.session_handlers),
            theme_handlers=list(view.theme_handlers),
            throttle_api_handlers=list(view.throttle_api_handlers),
            user_handlers=list(view.user_handlers),
            signal_handlers=list(view.signal_handlers),
            event_listeners=list(view.event_listeners),
            realtime_included=list(view.realtime_included),
            realtime_discussion_visibility=list(view.realtime_discussion_visibility),
            realtime_discussion_transports=list(view.realtime_discussion_transports),
            realtime_discussion_broadcasts=list(view.realtime_discussion_broadcasts),
            forum_permission_checkers=list(view.forum_permission_checkers),
            discussion_lifecycle=list(view.discussion_lifecycle),
            post_lifecycle=list(view.post_lifecycle),
            runtime_actions=list(view.runtime_actions),
            admin_actions=list(view.admin_actions),
            route_mounts=list(view.route_mounts),
            named_routes=list(view.named_routes),
            websocket_routes=list(view.websocket_routes),
            middleware_mounts=list(view.middleware_mounts),
            policy_mounts=list(view.policy_mounts),
            service_providers=list(view.service_providers),
            extender_keys=list(view.extender_keys),
            lifecycle_extender_keys=list(view.lifecycle_extender_keys),
            lifecycle_phase_keys=list(view.lifecycle_phase_keys),
            use_generated_settings_page=view.use_generated_settings_page,
            use_generated_permissions_page=view.use_generated_permissions_page,
            use_generated_operations_page=view.use_generated_operations_page,
        )

    def _apply_service_extenders(self, key: str, value: Any) -> Any:
        output = value
        for extender in self._service_extenders.get(key, []):
            output = extender(self, output)
        return output

    def _apply_resolving_callbacks(self, key: str, value: Any) -> Any:
        output = value
        for callback in self._resolving_callbacks.get(key, []):
            output = callback(output, self)
        return output


ExtensionHost = ExtensionApplication


def _build_api_application_from_host(host: ExtensionApplication):
    from apps.core.api_runtime import build_api_application

    return build_api_application(extension_host=host)
