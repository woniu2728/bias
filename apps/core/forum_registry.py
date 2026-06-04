from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from django.db import OperationalError, ProgrammingError

from apps.core.forum_registry_core import _register_core_modules
from apps.core.forum_registry_types import (
    AdminPageDefinition,
    DiscussionListFilterDefinition,
    DiscussionListFilterApplier,
    DiscussionSortApplier,
    DiscussionSortDefinition,
    EventListenerDefinition,
    ForumModuleDefinition,
    LanguagePackDefinition,
    NotificationTypeDefinition,
    PermissionDefinition,
    PostTypeDefinition,
    SearchFilterApplier,
    SearchFilterDefinition,
    SearchFilterParser,
    UserPreferenceDefinition,
)
from apps.core.models import ExtensionInstallation


class ForumRegistry:
    def __init__(self):
        self._modules: Dict[str, ForumModuleDefinition] = {}
        self._external_enabled_module_ids: set[str] = set()
        self._permissions: Dict[str, PermissionDefinition] = {}
        self._permission_aliases: Dict[str, str] = {}
        self._admin_pages: List[AdminPageDefinition] = []
        self._notification_types: Dict[str, NotificationTypeDefinition] = {}
        self._user_preferences: Dict[str, UserPreferenceDefinition] = {}
        self._language_packs: Dict[tuple[str, str], LanguagePackDefinition] = {}
        self._event_listeners: List[EventListenerDefinition] = []
        self._post_types: Dict[str, PostTypeDefinition] = {}
        self._search_filters: List[SearchFilterDefinition] = []
        self._discussion_sorts: Dict[str, DiscussionSortDefinition] = {}
        self._discussion_list_filters: Dict[str, DiscussionListFilterDefinition] = {}

    def register_module(self, module: ForumModuleDefinition) -> ForumModuleDefinition:
        self._modules[module.module_id] = module

        for permission in module.permissions:
            self.register_permission(permission)

        for page in module.admin_pages:
            self.register_admin_page(page)

        for notification_type in module.notification_types:
            self.register_notification_type(notification_type)

        for preference in module.user_preferences:
            self.register_user_preference(preference)

        for language_pack in module.language_packs:
            self.register_language_pack(language_pack)

        for event_listener in module.event_listeners:
            self.register_event_listener(event_listener)

        for post_type in module.post_types:
            self.register_post_type(post_type)

        for search_filter in module.search_filters:
            self.register_search_filter(search_filter)

        for discussion_sort in module.discussion_sorts:
            self.register_discussion_sort(discussion_sort)

        for discussion_list_filter in module.discussion_list_filters:
            self.register_discussion_list_filter(discussion_list_filter)
        return module

    def register_permission(self, definition: PermissionDefinition) -> None:
        self._append_to_module(definition.module_id, "permissions", definition, key=lambda item: item.code)
        self._permissions[definition.code] = definition
        for alias in definition.aliases:
            self._permission_aliases[alias] = definition.code

    def register_external_module_id(self, module_id: str) -> None:
        normalized = str(module_id or "").strip()
        if normalized:
            self._external_enabled_module_ids.add(normalized)

    def register_extension_module(self, extension) -> ForumModuleDefinition:
        return self.register_module(ForumModuleDefinition(
            module_id=extension.id,
            name=extension.name,
            version=extension.version,
            description=extension.description,
            category=extension.manifest.category,
            is_core=False,
            enabled=bool(extension.runtime.enabled),
            dependencies=tuple(extension.manifest.dependencies),
            capabilities=tuple(extension.manifest.provides or extension.capabilities),
            documentation_url=extension.manifest.documentation_url,
        ))

    def register_admin_page(self, definition: AdminPageDefinition) -> None:
        self._append_to_module(definition.module_id, "admin_pages", definition, key=lambda item: item.path)
        self._admin_pages = [
            item for item in self._admin_pages
            if not (item.path == definition.path and item.module_id == definition.module_id)
        ]
        self._admin_pages.append(definition)
        self._admin_pages.sort(key=lambda item: (item.nav_section, item.label, item.path))

    def register_notification_type(self, definition: NotificationTypeDefinition) -> None:
        self._append_to_module(definition.module_id, "notification_types", definition, key=lambda item: item.code)
        self._notification_types[definition.code] = definition

    def register_user_preference(self, definition: UserPreferenceDefinition) -> None:
        self._append_to_module(definition.module_id, "user_preferences", definition, key=lambda item: item.key)
        self._user_preferences[definition.key] = definition

    def register_language_pack(self, definition: LanguagePackDefinition) -> None:
        self._append_to_module(definition.module_id, "language_packs", definition, key=lambda item: item.code)
        self._language_packs[(definition.module_id, definition.code)] = definition

    def register_event_listener(self, definition: EventListenerDefinition) -> None:
        self._append_to_module(definition.module_id, "event_listeners", definition, key=lambda item: (item.event, item.listener))
        self._event_listeners = [
            item for item in self._event_listeners
            if not (
                item.event == definition.event
                and item.listener == definition.listener
                and item.module_id == definition.module_id
            )
        ]
        self._event_listeners.append(definition)

    def register_post_type(self, definition: PostTypeDefinition) -> None:
        self._append_to_module(definition.module_id, "post_types", definition, key=lambda item: item.code)
        self._post_types[definition.code] = definition

    def register_search_filter(self, definition: SearchFilterDefinition) -> None:
        self._append_to_module(definition.module_id, "search_filters", definition, key=lambda item: (item.target, item.code))
        self._search_filters = [
            item for item in self._search_filters
            if not (
                item.code == definition.code
                and item.target == definition.target
                and item.module_id == definition.module_id
            )
        ]
        self._search_filters.append(definition)
        self._search_filters.sort(key=lambda item: (item.target, item.module_id, item.code))

    def register_discussion_sort(self, definition: DiscussionSortDefinition) -> None:
        self._append_to_module(definition.module_id, "discussion_sorts", definition, key=lambda item: item.code)
        self._discussion_sorts[definition.code] = definition

    def register_discussion_list_filter(self, definition: DiscussionListFilterDefinition) -> None:
        self._append_to_module(definition.module_id, "discussion_list_filters", definition, key=lambda item: item.code)
        self._discussion_list_filters[definition.code] = definition

    def _append_to_module(self, module_id: str, field_name: str, definition, *, key) -> None:
        module = self._modules.get(str(module_id or "").strip())
        if module is None:
            return
        definition_key = key(definition)
        current = tuple(getattr(module, field_name, ()) or ())
        updated = tuple(item for item in current if key(item) != definition_key)
        self._modules[module.module_id] = replace(module, **{
            field_name: tuple([*updated, definition]),
        })

    def _get_extension_state_overrides(self) -> Dict[str, bool]:
        try:
            return {
                item["extension_id"]: bool(item["enabled"])
                for item in ExtensionInstallation.objects.filter(source="filesystem").values("extension_id", "enabled")
            }
        except (OperationalError, ProgrammingError, RuntimeError):
            return {}

    def _apply_module_runtime_state(self, module: ForumModuleDefinition, enabled_overrides: Dict[str, bool]) -> ForumModuleDefinition:
        if module.module_id not in enabled_overrides:
            return module
        return replace(module, enabled=enabled_overrides[module.module_id])

    def _get_runtime_modules(self) -> List[ForumModuleDefinition]:
        enabled_overrides = self._get_extension_state_overrides()
        return [
            self._apply_module_runtime_state(module, enabled_overrides)
            for module in self._modules.values()
        ]

    def _get_enabled_module_ids(self) -> set[str]:
        enabled_overrides = self._get_extension_state_overrides()
        external_enabled_module_ids = {
            module_id
            for module_id in self._external_enabled_module_ids
            if enabled_overrides.get(module_id, True)
        }
        return {
            module.module_id
            for module in self._get_runtime_modules()
            if module.enabled
        } | external_enabled_module_ids

    def get_modules(self) -> List[ForumModuleDefinition]:
        return sorted(
            self._get_runtime_modules(),
            key=lambda item: (
                int(not item.is_core),
                item.category,
                item.name.lower(),
                item.module_id,
            ),
        )

    def get_module(self, module_id: str) -> ForumModuleDefinition | None:
        enabled_overrides = self._get_extension_state_overrides()
        module = self._modules.get(module_id)
        if module is None:
            return None
        return self._apply_module_runtime_state(module, enabled_overrides)

    def get_permission(self, code: str) -> PermissionDefinition | None:
        definitions = {
            item.code: item
            for item in self.get_all_permissions()
        }
        return definitions.get(code)

    def get_permission_aliases(self) -> Dict[str, str]:
        aliases = dict(self._permission_aliases)
        for definition in self.get_all_permissions():
            for alias in definition.aliases:
                aliases[alias] = definition.code
        return dict(sorted(aliases.items()))

    def get_valid_permission_codes(self) -> set[str]:
        return {definition.code for definition in self.get_all_permissions()}

    def normalize_permission_code(self, permission: str) -> str | None:
        normalized = self._permission_aliases.get(permission, permission)
        if normalized in self.get_valid_permission_codes():
            return normalized
        return None

    def get_admin_pages(self) -> List[AdminPageDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            page
            for page in self._admin_pages
            if page.module_id in enabled_module_ids
        ]

    def get_all_permissions(self) -> List[PermissionDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return sorted(
            [
                item
                for item in self._permissions.values()
                if item.module_id in enabled_module_ids
            ],
            key=lambda item: (item.section, item.module_id, item.label, item.code),
        )

    def get_notification_types(self) -> List[NotificationTypeDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return sorted(
            [
                item
                for item in self._notification_types.values()
                if item.module_id in enabled_module_ids
            ],
            key=lambda item: (item.module_id, item.label, item.code),
        )

    def get_notification_type(self, code: str) -> NotificationTypeDefinition | None:
        definitions = {item.code: item for item in self.get_notification_types()}
        return definitions.get(code)

    def get_user_preferences(self, category: str | None = None) -> List[UserPreferenceDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        preferences_list = [
            item
            for item in self._user_preferences.values()
            if item.module_id in enabled_module_ids
        ]
        if category is not None:
            preferences_list = [item for item in preferences_list if item.category == category]
        return sorted(
            preferences_list,
            key=lambda item: (item.category, item.module_id, item.label, item.key),
        )

    def get_language_packs(self, module_id: str | None = None) -> List[LanguagePackDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        language_packs = [
            item
            for item in self._language_packs.values()
            if item.module_id in enabled_module_ids
        ]
        if module_id is not None:
            language_packs = [item for item in language_packs if item.module_id == module_id]
        return sorted(
            language_packs,
            key=lambda item: (
                int(not item.is_default),
                item.module_id,
                item.label.lower(),
                item.code,
            ),
        )

    def get_event_listeners(self) -> List[EventListenerDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return [
            listener
            for listener in self._event_listeners
            if listener.module_id in enabled_module_ids
        ]

    def get_post_types(self) -> List[PostTypeDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return sorted(
            [
                item
                for item in self._post_types.values()
                if item.module_id in enabled_module_ids
            ],
            key=lambda item: (item.module_id, item.label, item.code),
        )

    def get_post_type(self, code: str) -> PostTypeDefinition | None:
        definitions = {item.code: item for item in self.get_post_types()}
        return definitions.get(code)

    def get_default_post_type_code(self) -> str:
        for definition in self.get_post_types():
            if definition.is_default:
                return definition.code
        return "comment"

    def get_stream_post_type_codes(self) -> Tuple[str, ...]:
        return tuple(
            definition.code
            for definition in self.get_post_types()
            if definition.is_stream_visible
        )

    def get_searchable_post_type_codes(self) -> Tuple[str, ...]:
        return tuple(
            definition.code
            for definition in self.get_post_types()
            if definition.searchable
        )

    def get_discussion_counted_post_type_codes(self) -> Tuple[str, ...]:
        return tuple(
            definition.code
            for definition in self.get_post_types()
            if definition.counts_toward_discussion
        )

    def get_user_counted_post_type_codes(self) -> Tuple[str, ...]:
        return tuple(
            definition.code
            for definition in self.get_post_types()
            if definition.counts_toward_user
        )

    def get_search_filters(self, target: str | None = None) -> List[SearchFilterDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        filters = [
            definition
            for definition in self._search_filters
            if definition.module_id in enabled_module_ids
        ]
        if target is not None:
            filters = [definition for definition in filters if definition.target == target]
        return sorted(filters, key=lambda item: (item.target, item.module_id, item.code))

    def get_discussion_sorts(self) -> List[DiscussionSortDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return sorted(
            [
                item
                for item in self._discussion_sorts.values()
                if item.module_id in enabled_module_ids
            ],
            key=lambda item: (item.order, item.module_id, item.label, item.code),
        )

    def get_discussion_sort(self, code: str) -> DiscussionSortDefinition | None:
        normalized = (code or "").strip()
        if normalized in self._discussion_sorts:
            return self._discussion_sorts[normalized]

        for definition in self.get_discussion_sorts():
            if definition.is_default:
                return definition
        return None

    def get_default_discussion_sort_code(self) -> str:
        for definition in self.get_discussion_sorts():
            if definition.is_default:
                return definition.code
        return "latest"

    def get_discussion_list_filters(self) -> List[DiscussionListFilterDefinition]:
        enabled_module_ids = self._get_enabled_module_ids()
        return sorted(
            [
                item
                for item in self._discussion_list_filters.values()
                if item.module_id in enabled_module_ids
            ],
            key=lambda item: (item.order, item.module_id, item.label, item.code),
        )

    def get_discussion_list_filter(self, code: str) -> DiscussionListFilterDefinition | None:
        normalized = (code or "").strip()
        if normalized in self._discussion_list_filters:
            return self._discussion_list_filters[normalized]

        for definition in self.get_discussion_list_filters():
            if definition.is_default:
                return definition
        return None

    def get_default_discussion_list_filter_code(self) -> str:
        for definition in self.get_discussion_list_filters():
            if definition.is_default:
                return definition.code
        return "all"

    def get_permission_sections(self) -> List[dict]:
        sections: Dict[str, dict] = {}
        for permission in self.get_all_permissions():
            section = sections.setdefault(
                permission.section,
                {
                    "name": permission.section,
                    "label": permission.section_label,
                    "permissions": [],
                },
            )
            section["permissions"].append(
                {
                    "name": permission.code,
                    "label": permission.label,
                    "icon": permission.icon,
                    "description": permission.description,
                    "module_id": permission.module_id,
                    "required_permissions": list(permission.required_permissions),
                    "aliases": list(permission.aliases),
                }
            )

        return [
            {
                **section,
                "permissions": sorted(section["permissions"], key=lambda item: (item["module_id"], item["label"])),
            }
            for section in sorted(sections.values(), key=lambda item: item["label"])
        ]

    def expand_permissions(self, permission_codes: List[str] | Tuple[str, ...]) -> List[str]:
        resolved: List[str] = []
        visited: set[str] = set()

        def visit(code: str) -> None:
            normalized = self.normalize_permission_code(code)
            if not normalized or normalized in visited:
                return
            visited.add(normalized)
            definition = self.get_permission(normalized)
            if definition:
                for dependency in definition.required_permissions:
                    visit(dependency)
            resolved.append(normalized)

        for permission_code in permission_codes or []:
            visit(permission_code)

        return resolved


_registry: ForumRegistry | None = None


def get_forum_registry() -> ForumRegistry:
    from apps.core.extensions.bootstrap_state import is_extension_host_bootstrapped

    global _registry
    if is_extension_host_bootstrapped():
        try:
            from apps.core.extensions.bootstrap import get_extension_host

            host = get_extension_host()
            if host is not None:
                return host.forum
        except Exception:
            pass
    if _registry is None:
        _registry = ForumRegistry()
        _register_core_modules(_registry)
    return _registry


def get_core_module_ids() -> Tuple[str, ...]:
    registry = ForumRegistry()
    _register_core_modules(registry)
    return tuple(sorted(registry._modules.keys()))


def get_registry_permission_codes_by_prefix(prefix: str) -> Tuple[str, ...]:
    normalized_prefix = str(prefix or "").strip()
    if not normalized_prefix:
        return ()

    registry = get_forum_registry()
    return tuple(sorted(
        code for code in registry.get_valid_permission_codes()
        if code.startswith(normalized_prefix)
    ))


def get_registry_staff_managed_admin_permission_codes() -> Tuple[str, ...]:
    registry = get_forum_registry()
    return tuple(sorted(
        definition.code
        for definition in registry.get_all_permissions()
        if definition.code.startswith("admin.")
    ))
