from __future__ import annotations

from typing import Dict, List, Tuple

from apps.core.forum_registry_builtin import _register_builtin_modules
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


class ForumRegistry:
    def __init__(self):
        self._modules: Dict[str, ForumModuleDefinition] = {}
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
            self._permissions[permission.code] = permission
            for alias in permission.aliases:
                self._permission_aliases[alias] = permission.code

        for page in module.admin_pages:
            self._admin_pages.append(page)

        for notification_type in module.notification_types:
            self._notification_types[notification_type.code] = notification_type

        for preference in module.user_preferences:
            self._user_preferences[preference.key] = preference

        for language_pack in module.language_packs:
            self._language_packs[(language_pack.module_id, language_pack.code)] = language_pack

        for event_listener in module.event_listeners:
            self._event_listeners.append(event_listener)

        for post_type in module.post_types:
            self._post_types[post_type.code] = post_type

        for search_filter in module.search_filters:
            self._search_filters.append(search_filter)

        for discussion_sort in module.discussion_sorts:
            self._discussion_sorts[discussion_sort.code] = discussion_sort

        for discussion_list_filter in module.discussion_list_filters:
            self._discussion_list_filters[discussion_list_filter.code] = discussion_list_filter

        self._admin_pages.sort(key=lambda item: (item.nav_section, item.label, item.path))
        self._event_listeners.sort(key=lambda item: (item.event, item.module_id, item.listener))
        self._search_filters.sort(key=lambda item: (item.target, item.module_id, item.code))
        return module

    def get_modules(self) -> List[ForumModuleDefinition]:
        return sorted(
            self._modules.values(),
            key=lambda item: (
                int(not item.is_core),
                item.category,
                item.name.lower(),
                item.module_id,
            ),
        )

    def get_module(self, module_id: str) -> ForumModuleDefinition | None:
        return self._modules.get(module_id)

    def get_permission(self, code: str) -> PermissionDefinition | None:
        return self._permissions.get(code)

    def get_permission_aliases(self) -> Dict[str, str]:
        return dict(sorted(self._permission_aliases.items()))

    def get_valid_permission_codes(self) -> set[str]:
        return set(self._permissions.keys())

    def normalize_permission_code(self, permission: str) -> str | None:
        normalized = self._permission_aliases.get(permission, permission)
        if normalized in self._permissions:
            return normalized
        return None

    def get_admin_pages(self) -> List[AdminPageDefinition]:
        return list(self._admin_pages)

    def get_notification_types(self) -> List[NotificationTypeDefinition]:
        return sorted(
            self._notification_types.values(),
            key=lambda item: (item.module_id, item.label, item.code),
        )

    def get_notification_type(self, code: str) -> NotificationTypeDefinition | None:
        return self._notification_types.get(code)

    def get_user_preferences(self, category: str | None = None) -> List[UserPreferenceDefinition]:
        preferences = list(self._user_preferences.values())
        if category is not None:
            preferences = [item for item in preferences if item.category == category]
        return sorted(
            preferences,
            key=lambda item: (item.category, item.module_id, item.label, item.key),
        )

    def get_language_packs(self, module_id: str | None = None) -> List[LanguagePackDefinition]:
        language_packs = list(self._language_packs.values())
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
        return list(self._event_listeners)

    def get_post_types(self) -> List[PostTypeDefinition]:
        return sorted(
            self._post_types.values(),
            key=lambda item: (item.module_id, item.label, item.code),
        )

    def get_post_type(self, code: str) -> PostTypeDefinition | None:
        return self._post_types.get(code)

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
        filters = list(self._search_filters)
        if target is not None:
            filters = [definition for definition in filters if definition.target == target]
        return filters

    def get_discussion_sorts(self) -> List[DiscussionSortDefinition]:
        return sorted(
            self._discussion_sorts.values(),
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
        return sorted(
            self._discussion_list_filters.values(),
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
        for permission in self._permissions.values():
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
    global _registry
    if _registry is None:
        _registry = ForumRegistry()
        _register_builtin_modules(_registry)
    return _registry


def get_registry_permission_codes_by_prefix(prefix: str) -> Tuple[str, ...]:
    normalized_prefix = str(prefix or "").strip()
    if not normalized_prefix:
        return ()

    registry = get_forum_registry()
    return tuple(sorted(
        code for code in registry.get_valid_permission_codes()
        if code.startswith(normalized_prefix)
    ))
