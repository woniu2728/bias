from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Tuple

from apps.core.version import APP_VERSION


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    label: str
    section: str
    section_label: str
    module_id: str
    icon: str = "fas fa-key"
    description: str = ""
    aliases: Tuple[str, ...] = ()
    required_permissions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AdminPageDefinition:
    path: str
    label: str
    icon: str
    module_id: str
    nav_section: str = "feature"
    description: str = ""
    settings_group: str = ""


@dataclass(frozen=True)
class NotificationTypeDefinition:
    code: str
    label: str
    module_id: str
    description: str = ""
    icon: str = "fas fa-bell"
    navigation_scope: str = "notifications"
    preference_key: str = ""
    preference_label: str = ""
    preference_description: str = ""
    preference_default_enabled: bool = True


@dataclass(frozen=True)
class UserPreferenceDefinition:
    key: str
    label: str
    module_id: str
    description: str = ""
    category: str = "notification"
    default_value: bool = False


@dataclass(frozen=True)
class LanguagePackDefinition:
    code: str
    label: str
    module_id: str
    native_label: str = ""
    description: str = ""
    is_default: bool = False


@dataclass(frozen=True)
class EventListenerDefinition:
    event: str
    listener: str
    module_id: str
    description: str = ""


@dataclass(frozen=True)
class PostTypeDefinition:
    code: str
    label: str
    module_id: str
    description: str = ""
    icon: str = "far fa-comment"
    is_default: bool = False
    is_stream_visible: bool = True
    counts_toward_discussion: bool = True
    counts_toward_user: bool = True
    searchable: bool = True


SearchFilterParser = Callable[[str], Any | None]
SearchFilterApplier = Callable[[Any, Any, dict], Any]
DiscussionSortApplier = Callable[[Any, dict], Any]
DiscussionListFilterApplier = Callable[[Any, dict], Any]


@dataclass(frozen=True)
class SearchFilterDefinition:
    code: str
    label: str
    module_id: str
    target: str
    parser: SearchFilterParser
    applier: SearchFilterApplier
    syntax: str = ""
    description: str = ""


@dataclass(frozen=True)
class DiscussionSortDefinition:
    code: str
    label: str
    module_id: str
    applier: DiscussionSortApplier
    description: str = ""
    icon: str = "fas fa-sort"
    is_default: bool = False
    order: int = 100
    toolbar_visible: bool = True


@dataclass(frozen=True)
class DiscussionListFilterDefinition:
    code: str
    label: str
    module_id: str
    applier: DiscussionListFilterApplier
    description: str = ""
    icon: str = "fas fa-filter"
    is_default: bool = False
    requires_authenticated_user: bool = False
    order: int = 100
    sidebar_visible: bool = True
    route_path: str = "/"


@dataclass(frozen=True)
class ForumModuleDefinition:
    module_id: str
    name: str
    description: str
    version: str = APP_VERSION
    category: str = "feature"
    is_core: bool = False
    enabled: bool = True
    dependencies: Tuple[str, ...] = ()
    permissions: Tuple[PermissionDefinition, ...] = ()
    admin_pages: Tuple[AdminPageDefinition, ...] = ()
    capabilities: Tuple[str, ...] = ()
    notification_types: Tuple[NotificationTypeDefinition, ...] = ()
    user_preferences: Tuple[UserPreferenceDefinition, ...] = ()
    language_packs: Tuple[LanguagePackDefinition, ...] = ()
    event_listeners: Tuple[EventListenerDefinition, ...] = ()
    post_types: Tuple[PostTypeDefinition, ...] = ()
    search_filters: Tuple[SearchFilterDefinition, ...] = ()
    discussion_sorts: Tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: Tuple[DiscussionListFilterDefinition, ...] = ()
    settings_groups: Tuple[str, ...] = ()
    documentation_url: str = ""
