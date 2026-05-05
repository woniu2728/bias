from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple
from django.db import models

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
    event_listeners: Tuple[EventListenerDefinition, ...] = ()
    post_types: Tuple[PostTypeDefinition, ...] = ()
    search_filters: Tuple[SearchFilterDefinition, ...] = ()
    discussion_sorts: Tuple[DiscussionSortDefinition, ...] = ()
    discussion_list_filters: Tuple[DiscussionListFilterDefinition, ...] = ()


class ForumRegistry:
    def __init__(self):
        self._modules: Dict[str, ForumModuleDefinition] = {}
        self._permissions: Dict[str, PermissionDefinition] = {}
        self._permission_aliases: Dict[str, str] = {}
        self._admin_pages: List[AdminPageDefinition] = []
        self._notification_types: Dict[str, NotificationTypeDefinition] = {}
        self._user_preferences: Dict[str, UserPreferenceDefinition] = {}
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


_registry: ForumRegistry | None = None


def get_forum_registry() -> ForumRegistry:
    global _registry
    if _registry is None:
        _registry = ForumRegistry()
        _register_builtin_modules(_registry)
    return _registry


def _register_builtin_modules(registry: ForumRegistry) -> None:
    registry.register_module(
        ForumModuleDefinition(
            module_id="core",
            name="Core",
            description="论坛核心配置、权限、外观与高级设置底座。",
            category="core",
            is_core=True,
            admin_pages=(
                AdminPageDefinition(
                    path="/admin",
                    label="仪表盘",
                    icon="fas fa-chart-bar",
                    module_id="core",
                    nav_section="core",
                    description="查看论坛概况和系统状态。",
                ),
                AdminPageDefinition(
                    path="/admin/modules",
                    label="模块中心",
                    icon="fas fa-cubes",
                    module_id="core",
                    nav_section="core",
                    description="查看内置模块、依赖、权限和后台入口。",
                ),
                AdminPageDefinition(
                    path="/admin/basics",
                    label="基础设置",
                    icon="fas fa-pencil-alt",
                    module_id="core",
                    nav_section="core",
                    description="维护论坛标题、公告与 SEO 基础信息。",
                ),
                AdminPageDefinition(
                    path="/admin/permissions",
                    label="权限管理",
                    icon="fas fa-key",
                    module_id="core",
                    nav_section="core",
                    description="配置用户组权限矩阵。",
                ),
                AdminPageDefinition(
                    path="/admin/appearance",
                    label="外观设置",
                    icon="fas fa-paint-brush",
                    module_id="core",
                    nav_section="core",
                    description="维护主题色、Logo 与自定义样式。",
                ),
                AdminPageDefinition(
                    path="/admin/mail",
                    label="邮件设置",
                    icon="fas fa-envelope",
                    module_id="core",
                    nav_section="feature",
                    description="配置邮件驱动与测试投递。",
                ),
                AdminPageDefinition(
                    path="/admin/advanced",
                    label="高级设置",
                    icon="fas fa-cog",
                    module_id="core",
                    nav_section="feature",
                    description="管理缓存、队列、存储和维护模式。",
                ),
                AdminPageDefinition(
                    path="/admin/audit-logs",
                    label="审计日志",
                    icon="fas fa-clipboard-list",
                    module_id="core",
                    nav_section="feature",
                    description="查看后台关键管理操作审计记录。",
                ),
            ),
            capabilities=(
                "settings",
                "permissions",
                "appearance",
                "mail",
                "advanced",
                "audit-log",
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="discussions",
            name="Discussions",
            description="讨论、回复与内容管理的核心论坛能力。",
            category="feature",
            permissions=(
                PermissionDefinition(
                    code="viewForum",
                    label="查看论坛",
                    section="view",
                    section_label="查看权限",
                    module_id="discussions",
                    icon="fas fa-eye",
                    description="允许访问论坛讨论流和讨论详情。",
                ),
                PermissionDefinition(
                    code="startDiscussion",
                    label="发起讨论",
                    section="start",
                    section_label="发帖权限",
                    module_id="discussions",
                    icon="fas fa-edit",
                    description="允许创建新讨论。",
                ),
                PermissionDefinition(
                    code="startDiscussionWithoutApproval",
                    label="发起讨论免审核",
                    section="start",
                    section_label="发帖权限",
                    module_id="discussions",
                    icon="fas fa-user-check",
                    description="发起讨论后直接公开，无需进入审核队列。",
                    required_permissions=("startDiscussion",),
                ),
                PermissionDefinition(
                    code="discussion.reply",
                    label="回复讨论",
                    section="reply",
                    section_label="回复权限",
                    module_id="discussions",
                    icon="fas fa-reply",
                    description="允许在讨论中发布回复。",
                    aliases=("reply",),
                    required_permissions=("viewForum",),
                ),
                PermissionDefinition(
                    code="replyWithoutApproval",
                    label="回复免审核",
                    section="reply",
                    section_label="回复权限",
                    module_id="discussions",
                    icon="fas fa-user-check",
                    description="回复后直接公开，无需进入审核队列。",
                    required_permissions=("discussion.reply",),
                ),
                PermissionDefinition(
                    code="discussion.editOwn",
                    label="编辑自己的帖子",
                    section="reply",
                    section_label="回复权限",
                    module_id="discussions",
                    icon="fas fa-pencil-alt",
                    description="允许作者编辑自己的讨论首帖或回复。",
                    aliases=("editOwnPosts",),
                ),
                PermissionDefinition(
                    code="discussion.deleteOwn",
                    label="删除自己的帖子",
                    section="reply",
                    section_label="回复权限",
                    module_id="discussions",
                    icon="fas fa-times",
                    description="允许作者删除自己的讨论或回复。",
                    aliases=("deleteOwnPosts",),
                ),
                PermissionDefinition(
                    code="discussion.edit",
                    label="编辑任意帖子",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-pencil-alt",
                    description="允许管理任意讨论首帖与回复。",
                    aliases=("editPosts",),
                    required_permissions=("viewForum",),
                ),
                PermissionDefinition(
                    code="discussion.delete",
                    label="删除任意帖子",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-trash",
                    description="允许删除任意讨论或回复。",
                    aliases=("deletePosts",),
                    required_permissions=("discussion.hide",),
                ),
                PermissionDefinition(
                    code="discussion.hide",
                    label="隐藏内容",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-eye-slash",
                    description="允许隐藏或恢复讨论内容。",
                    aliases=("hideDiscussions",),
                    required_permissions=("viewForum",),
                ),
                PermissionDefinition(
                    code="discussion.rename",
                    label="重命名讨论",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-heading",
                    description="允许修改讨论标题。",
                    required_permissions=("viewForum",),
                ),
                PermissionDefinition(
                    code="discussion.lock",
                    label="锁定讨论",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-lock",
                    description="允许锁定或解锁讨论。",
                    aliases=("lockDiscussions",),
                    required_permissions=("viewForum",),
                ),
                PermissionDefinition(
                    code="discussion.sticky",
                    label="置顶讨论",
                    section="moderate",
                    section_label="内容管理",
                    module_id="discussions",
                    icon="fas fa-thumbtack",
                    description="允许置顶或取消置顶讨论。",
                    aliases=("stickyDiscussions",),
                    required_permissions=("viewForum",),
                ),
            ),
            capabilities=("discussion-list", "discussion-detail", "composer", "moderation"),
            dependencies=("posts",),
            discussion_sorts=(
                DiscussionSortDefinition(
                    code="latest",
                    label="最新活跃",
                    module_id="discussions",
                    applier=_apply_discussion_latest_sort,
                    description="按最后活跃时间排序，优先展示最近有新回复的讨论。",
                    icon="fas fa-clock",
                    is_default=True,
                    order=10,
                ),
                DiscussionSortDefinition(
                    code="newest",
                    label="新主题",
                    module_id="discussions",
                    applier=_apply_discussion_newest_sort,
                    description="按讨论创建时间倒序，优先展示最新发布的主题。",
                    icon="fas fa-sparkles",
                    order=20,
                ),
                DiscussionSortDefinition(
                    code="top",
                    label="热门",
                    module_id="discussions",
                    applier=_apply_discussion_top_sort,
                    description="按回复数和浏览量综合排序，优先展示热门讨论。",
                    icon="fas fa-fire",
                    order=30,
                ),
                DiscussionSortDefinition(
                    code="unanswered",
                    label="零回复",
                    module_id="discussions",
                    applier=_apply_discussion_unanswered_sort,
                    description="优先展示还没有收到其他回复的讨论，便于发现待回应主题。",
                    icon="fas fa-comment-slash",
                    order=40,
                ),
                DiscussionSortDefinition(
                    code="oldest",
                    label="最早发布",
                    module_id="discussions",
                    applier=_apply_discussion_oldest_sort,
                    description="按讨论创建时间正序排序。",
                    icon="fas fa-hourglass-start",
                    order=50,
                ),
            ),
            discussion_list_filters=(
                DiscussionListFilterDefinition(
                    code="all",
                    label="全部讨论",
                    module_id="discussions",
                    applier=_apply_all_discussion_list_filter,
                    description="显示当前可见的全部讨论。",
                    icon="far fa-comments",
                    is_default=True,
                    order=10,
                ),
                DiscussionListFilterDefinition(
                    code="following",
                    label="关注中",
                    module_id="discussions",
                    applier=_apply_following_discussion_list_filter,
                    description="仅显示当前用户已关注的讨论。",
                    icon="fas fa-bell",
                    requires_authenticated_user=True,
                    order=20,
                ),
                DiscussionListFilterDefinition(
                    code="my",
                    label="我发起的",
                    module_id="discussions",
                    applier=_apply_my_discussions_list_filter,
                    description="仅显示当前用户自己发起的讨论。",
                    icon="fas fa-user",
                    requires_authenticated_user=True,
                    order=30,
                ),
                DiscussionListFilterDefinition(
                    code="unread",
                    label="未读",
                    module_id="discussions",
                    applier=_apply_unread_discussions_list_filter,
                    description="仅显示当前用户仍有未读回复的讨论。",
                    icon="fas fa-circle",
                    requires_authenticated_user=True,
                    order=40,
                ),
            ),
            search_filters=(
                SearchFilterDefinition(
                    code="author",
                    label="按作者过滤",
                    module_id="discussions",
                    target="discussion",
                    parser=_parse_author_search_filter,
                    applier=_apply_discussion_author_search_filter,
                    syntax="author:<username>",
                    description="按讨论作者用户名过滤搜索结果。",
                ),
                SearchFilterDefinition(
                    code="author",
                    label="按作者过滤",
                    module_id="discussions",
                    target="post",
                    parser=_parse_author_search_filter,
                    applier=_apply_post_author_search_filter,
                    syntax="author:<username>",
                    description="按回复作者用户名过滤搜索结果。",
                ),
                SearchFilterDefinition(
                    code="is_sticky",
                    label="仅置顶讨论",
                    module_id="discussions",
                    target="discussion",
                    parser=_parse_sticky_search_filter,
                    applier=_apply_discussion_sticky_search_filter,
                    syntax="is:sticky",
                    description="仅返回已置顶的讨论。",
                ),
                SearchFilterDefinition(
                    code="is_locked",
                    label="仅锁定讨论",
                    module_id="discussions",
                    target="discussion",
                    parser=_parse_locked_search_filter,
                    applier=_apply_discussion_locked_search_filter,
                    syntax="is:locked",
                    description="仅返回已锁定的讨论。",
                ),
                SearchFilterDefinition(
                    code="is_following",
                    label="仅关注讨论",
                    module_id="discussions",
                    target="discussion",
                    parser=_parse_following_search_filter,
                    applier=_apply_discussion_following_search_filter,
                    syntax="is:following",
                    description="仅返回当前用户已关注的讨论。",
                ),
                SearchFilterDefinition(
                    code="is_unread",
                    label="仅未读讨论",
                    module_id="discussions",
                    target="discussion",
                    parser=_parse_unread_search_filter,
                    applier=_apply_discussion_unread_search_filter,
                    syntax="is:unread",
                    description="仅返回当前用户还有未读回复的讨论。",
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="posts",
            name="Posts",
            description="帖子流、回复实体、帖子类型与楼层内容输出。",
            category="feature",
            dependencies=("users",),
            capabilities=("post-stream", "post-detail", "post-types"),
            post_types=(
                PostTypeDefinition(
                    code="comment",
                    label="普通回复",
                    module_id="posts",
                    description="默认的讨论回复帖子类型，会参与回复统计、帖子流与全文搜索。",
                    icon="far fa-comment",
                    is_default=True,
                    is_stream_visible=True,
                    counts_toward_discussion=True,
                    counts_toward_user=True,
                    searchable=True,
                ),
                PostTypeDefinition(
                    code="discussionRenamed",
                    label="讨论改标题",
                    module_id="discussions",
                    description="记录讨论标题被修改的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-heading",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionLocked",
                    label="讨论锁定状态变更",
                    module_id="discussions",
                    description="记录讨论被锁定或解除锁定的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-lock",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionSticky",
                    label="讨论置顶状态变更",
                    module_id="discussions",
                    description="记录讨论被置顶或取消置顶的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-thumbtack",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionTagged",
                    label="讨论标签变更",
                    module_id="tags",
                    description="记录讨论标签被调整的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-tags",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionHidden",
                    label="讨论隐藏状态变更",
                    module_id="discussions",
                    description="记录讨论被隐藏或恢复显示的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-eye-slash",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionApproved",
                    label="讨论审核通过",
                    module_id="approval",
                    description="记录讨论被管理员审核通过的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-check-circle",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionRejected",
                    label="讨论审核拒绝",
                    module_id="approval",
                    description="记录讨论被管理员审核拒绝的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-ban",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="discussionResubmitted",
                    label="讨论重新提交审核",
                    module_id="approval",
                    description="记录作者修改被拒讨论后重新提交审核的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-rotate-right",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="postApproved",
                    label="回复审核通过",
                    module_id="approval",
                    description="记录回复被管理员审核通过的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-check",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="postRejected",
                    label="回复审核拒绝",
                    module_id="approval",
                    description="记录回复被管理员审核拒绝的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-comment-slash",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="postResubmitted",
                    label="回复重新提交审核",
                    module_id="approval",
                    description="记录作者修改被拒回复后重新提交审核的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-reply",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
                PostTypeDefinition(
                    code="postHidden",
                    label="回复隐藏状态变更",
                    module_id="posts",
                    description="记录回复被隐藏或恢复显示的系统事件帖，不计入回复统计和全文搜索。",
                    icon="fas fa-eye-slash",
                    is_default=False,
                    is_stream_visible=True,
                    counts_toward_discussion=False,
                    counts_toward_user=False,
                    searchable=False,
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="users",
            name="Users",
            description="用户资料、用户组、权限分配与封禁管理。",
            category="feature",
            permissions=(
                PermissionDefinition(
                    code="viewUserList",
                    label="查看用户列表",
                    section="view",
                    section_label="查看权限",
                    module_id="users",
                    icon="fas fa-users",
                    description="允许浏览用户列表与公开资料。",
                ),
                PermissionDefinition(
                    code="searchUsers",
                    label="搜索用户",
                    section="view",
                    section_label="查看权限",
                    module_id="users",
                    icon="fas fa-search",
                    description="允许在论坛搜索中查询用户。",
                ),
                PermissionDefinition(
                    code="user.edit",
                    label="编辑用户资料",
                    section="user",
                    section_label="用户管理",
                    module_id="users",
                    icon="fas fa-user-edit",
                    description="允许管理员编辑任意用户资料与用户组。",
                ),
                PermissionDefinition(
                    code="user.suspend",
                    label="封禁用户",
                    section="user",
                    section_label="用户管理",
                    module_id="users",
                    icon="fas fa-user-slash",
                    description="允许暂停用户发言能力。",
                ),
            ),
            admin_pages=(
                AdminPageDefinition(
                    path="/admin/users",
                    label="用户管理",
                    icon="fas fa-users",
                    module_id="users",
                    nav_section="core",
                    description="查看、编辑、分组与封禁论坛用户。",
                ),
            ),
            capabilities=("profiles", "groups", "suspension"),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="tags",
            name="Tags",
            description="讨论标签、层级标签、标签可见性与标签权限。",
            category="feature",
            admin_pages=(
                AdminPageDefinition(
                    path="/admin/tags",
                    label="标签管理",
                    icon="fas fa-tags",
                    module_id="tags",
                    nav_section="feature",
                    description="维护标签结构、排序与访问范围。",
                ),
            ),
            capabilities=("tagging", "tag-permissions", "tag-hierarchy"),
            search_filters=(
                SearchFilterDefinition(
                    code="tag",
                    label="按标签过滤",
                    module_id="tags",
                    target="discussion",
                    parser=_parse_tag_search_filter,
                    applier=_apply_discussion_tag_search_filter,
                    syntax="tag:<slug>",
                    description="按标签 slug 过滤讨论搜索结果。",
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="approval",
            name="Approval",
            description="讨论与回复审核队列、审核通知和审核流程。",
            category="feature",
            dependencies=("discussions", "notifications"),
            admin_pages=(
                AdminPageDefinition(
                    path="/admin/approval",
                    label="审核队列",
                    icon="fas fa-user-check",
                    module_id="approval",
                    nav_section="feature",
                    description="处理待审核讨论与回复。",
                ),
            ),
            capabilities=("discussion-approval", "post-approval"),
            notification_types=(
                NotificationTypeDefinition(
                    code="discussionApproved",
                    label="讨论审核通过",
                    module_id="approval",
                    description="通知作者其讨论已通过审核。",
                    icon="fas fa-circle-check",
                    navigation_scope="discussion",
                    preference_key="notify_discussion_approval",
                    preference_label="讨论审核结果通知",
                    preference_description="当你的讨论被审核通过或拒绝时通知你。",
                ),
                NotificationTypeDefinition(
                    code="discussionRejected",
                    label="讨论审核拒绝",
                    module_id="approval",
                    description="通知作者其讨论未通过审核。",
                    icon="fas fa-circle-xmark",
                    navigation_scope="discussion",
                    preference_key="notify_discussion_approval",
                    preference_label="讨论审核结果通知",
                    preference_description="当你的讨论被审核通过或拒绝时通知你。",
                ),
                NotificationTypeDefinition(
                    code="postApproved",
                    label="回复审核通过",
                    module_id="approval",
                    description="通知作者其回复已通过审核。",
                    icon="fas fa-check",
                    navigation_scope="post",
                    preference_key="notify_post_approval",
                    preference_label="回复审核结果通知",
                    preference_description="当你的回复被审核通过或拒绝时通知你。",
                ),
                NotificationTypeDefinition(
                    code="postRejected",
                    label="回复审核拒绝",
                    module_id="approval",
                    description="通知作者其回复未通过审核。",
                    icon="fas fa-xmark",
                    navigation_scope="post",
                    preference_key="notify_post_approval",
                    preference_label="回复审核结果通知",
                    preference_description="当你的回复被审核通过或拒绝时通知你。",
                ),
            ),
            user_preferences=(
                UserPreferenceDefinition(
                    key="notify_discussion_approval",
                    label="讨论审核结果通知",
                    module_id="approval",
                    description="当你的讨论被审核通过或拒绝时通知你。",
                    category="notification",
                    default_value=True,
                ),
                UserPreferenceDefinition(
                    key="notify_post_approval",
                    label="回复审核结果通知",
                    module_id="approval",
                    description="当你的回复被审核通过或拒绝时通知你。",
                    category="notification",
                    default_value=True,
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="flags",
            name="Flags",
            description="帖子举报、处理状态和管理后台举报流。",
            category="feature",
            dependencies=("discussions", "users"),
            admin_pages=(
                AdminPageDefinition(
                    path="/admin/flags",
                    label="举报管理",
                    icon="fas fa-flag",
                    module_id="flags",
                    nav_section="feature",
                    description="查看并处理帖子举报。",
                ),
            ),
            capabilities=("post-flags", "flag-resolution"),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="subscriptions",
            name="Subscriptions",
            description="讨论关注、关注流与关注后通知逻辑。",
            category="feature",
            dependencies=("discussions", "notifications"),
            capabilities=("follow-discussion", "following-feed"),
            user_preferences=(
                UserPreferenceDefinition(
                    key="follow_after_reply",
                    label="回复后自动关注",
                    module_id="subscriptions",
                    description="参与讨论后自动把该讨论加入关注列表。",
                    category="behavior",
                    default_value=False,
                ),
                UserPreferenceDefinition(
                    key="follow_after_create",
                    label="发起讨论后自动关注",
                    module_id="subscriptions",
                    description="你创建的新讨论默认加入关注列表。",
                    category="behavior",
                    default_value=False,
                ),
                UserPreferenceDefinition(
                    key="notify_new_post",
                    label="关注讨论有新回复时通知我",
                    module_id="subscriptions",
                    description="关闭后仍保留关注状态，但不再接收关注讨论的新回复通知。",
                    category="notification",
                    default_value=True,
                ),
            ),
            event_listeners=(
                EventListenerDefinition(
                    event="PostCreatedEvent",
                    listener="handle_post_created",
                    module_id="subscriptions",
                    description="已发布回复后为讨论作者和关注者派发讨论回复通知。",
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="likes",
            name="Likes",
            description="帖子点赞与点赞通知。",
            category="feature",
            dependencies=("discussions", "notifications"),
            capabilities=("post-likes",),
            notification_types=(
                NotificationTypeDefinition(
                    code="postLiked",
                    label="回复被点赞",
                    module_id="likes",
                    description="通知回复作者其内容被点赞。",
                    icon="fas fa-thumbs-up",
                    navigation_scope="post",
                    preference_key="notify_post_liked",
                    preference_label="回复被点赞通知",
                    preference_description="当你的回复被其他用户点赞时通知你。",
                ),
            ),
            user_preferences=(
                UserPreferenceDefinition(
                    key="notify_post_liked",
                    label="回复被点赞通知",
                    module_id="likes",
                    description="当你的回复被其他用户点赞时通知你。",
                    category="notification",
                    default_value=True,
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="mentions",
            name="Mentions",
            description="用户提及与提及通知。",
            category="feature",
            dependencies=("discussions", "notifications", "users"),
            capabilities=("user-mentions",),
            search_filters=(
                SearchFilterDefinition(
                    code="mentioned_me",
                    label="提及我的回复",
                    module_id="mentions",
                    target="post",
                    parser=_parse_mentioned_me_search_filter,
                    applier=_apply_post_mentioned_me_search_filter,
                    syntax="mentioned:me",
                    description="仅返回提及当前用户的回复。",
                ),
            ),
            notification_types=(
                NotificationTypeDefinition(
                    code="userMentioned",
                    label="@提及通知",
                    module_id="mentions",
                    description="通知用户其在回复中被提及。",
                    icon="fas fa-at",
                    navigation_scope="post",
                    preference_key="notify_user_mentioned",
                    preference_label="@提及通知",
                    preference_description="当其他用户在回复中提及你时通知你。",
                ),
            ),
            user_preferences=(
                UserPreferenceDefinition(
                    key="notify_user_mentioned",
                    label="@提及通知",
                    module_id="mentions",
                    description="当其他用户在回复中提及你时通知你。",
                    category="notification",
                    default_value=True,
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="notifications",
            name="Notifications",
            description="站内通知、未读状态、通知列表与通知投递。",
            category="feature",
            dependencies=("users",),
            capabilities=("in-app-notifications", "notification-stats", "notification-websocket"),
            notification_types=(
                NotificationTypeDefinition(
                    code="discussionReply",
                    label="讨论新回复",
                    module_id="notifications",
                    description="通知讨论作者和关注者有新回复。",
                    icon="fas fa-reply",
                    navigation_scope="post",
                    preference_key="notify_new_post",
                    preference_label="关注讨论有新回复时通知我",
                    preference_description="关闭后仍保留关注状态，但不再接收关注讨论的新回复通知。",
                ),
                NotificationTypeDefinition(
                    code="postReply",
                    label="回复被回应",
                    module_id="notifications",
                    description="通知被回复的楼层作者。",
                    icon="fas fa-comment-dots",
                    navigation_scope="post",
                    preference_key="notify_post_reply",
                    preference_label="回复被回应通知",
                    preference_description="当其他用户直接回复你的某条帖子时通知你。",
                ),
                NotificationTypeDefinition(
                    code="userSuspended",
                    label="账号封禁通知",
                    module_id="notifications",
                    description="通知用户账号已被管理员封禁。",
                    icon="fas fa-user-lock",
                    navigation_scope="profile",
                    preference_key="notify_account_status",
                    preference_label="账号状态通知",
                    preference_description="当你的账号被封禁或解除封禁时通知你。",
                ),
                NotificationTypeDefinition(
                    code="userUnsuspended",
                    label="账号解除封禁",
                    module_id="notifications",
                    description="通知用户账号已恢复正常。",
                    icon="fas fa-user-check",
                    navigation_scope="profile",
                    preference_key="notify_account_status",
                    preference_label="账号状态通知",
                    preference_description="当你的账号被封禁或解除封禁时通知你。",
                ),
            ),
            user_preferences=(
                UserPreferenceDefinition(
                    key="notify_post_reply",
                    label="回复被回应通知",
                    module_id="notifications",
                    description="当其他用户直接回复你的某条帖子时通知你。",
                    category="notification",
                    default_value=True,
                ),
                UserPreferenceDefinition(
                    key="notify_account_status",
                    label="账号状态通知",
                    module_id="notifications",
                    description="当你的账号被封禁或解除封禁时通知你。",
                    category="notification",
                    default_value=True,
                ),
            ),
            event_listeners=(
                EventListenerDefinition(
                    event="DiscussionApprovedEvent",
                    listener="handle_discussion_approved",
                    module_id="notifications",
                    description="讨论审核通过后通知作者。",
                ),
                EventListenerDefinition(
                    event="PostApprovedEvent",
                    listener="handle_post_approved",
                    module_id="notifications",
                    description="回复审核通过后通知作者。",
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="realtime",
            name="Realtime",
            description="WebSocket 连接、通知实时推送和论坛实时信号。",
            category="infrastructure",
            dependencies=("notifications",),
            capabilities=("websocket", "presence", "typing"),
            event_listeners=(
                EventListenerDefinition(
                    event="NotificationCreated",
                    listener="dispatch_notification_batch",
                    module_id="realtime",
                    description="通知创建后通过 WebSocket 批量推送到前端。",
                ),
            ),
        )
    )

    registry.register_module(
        ForumModuleDefinition(
            module_id="tag-stats",
            name="Tag Stats",
            description="标签统计刷新与讨论标签侧的聚合更新。",
            category="infrastructure",
            dependencies=("tags", "discussions"),
            capabilities=("tag-stats-refresh",),
            event_listeners=(
                EventListenerDefinition(
                    event="DiscussionCreatedEvent",
                    listener="handle_discussion_created",
                    module_id="tag-stats",
                    description="讨论创建后刷新标签统计。",
                ),
                EventListenerDefinition(
                    event="DiscussionApprovedEvent",
                    listener="handle_discussion_approved",
                    module_id="tag-stats",
                    description="讨论审核通过后刷新标签统计。",
                ),
                EventListenerDefinition(
                    event="PostCreatedEvent",
                    listener="handle_post_created",
                    module_id="tag-stats",
                    description="回复发布后刷新标签最后活跃时间。",
                ),
                EventListenerDefinition(
                    event="PostApprovedEvent",
                    listener="handle_post_approved",
                    module_id="tag-stats",
                    description="待审核回复通过后刷新标签统计。",
                ),
            ),
        )
    )


def _parse_tag_search_filter(token: str) -> str | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "tag":
        return None

    normalized = value.strip().lower()
    return normalized or None


def _apply_discussion_tag_search_filter(queryset, tag_slug: str, context: dict):
    return queryset.filter(discussion_tags__tag__slug=tag_slug)


def _parse_author_search_filter(token: str) -> str | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "author":
        return None

    normalized = value.strip()
    return normalized or None


def _apply_discussion_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def _apply_post_author_search_filter(queryset, username: str, context: dict):
    return queryset.filter(user__username__iexact=username)


def _parse_sticky_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="sticky")


def _apply_discussion_sticky_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_sticky=enabled)


def _parse_locked_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="locked")


def _apply_discussion_locked_search_filter(queryset, enabled: bool, context: dict):
    return queryset.filter(is_locked=enabled)


def _parse_following_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="following")


def _apply_discussion_following_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)


def _parse_unread_search_filter(token: str) -> bool | None:
    return _parse_is_search_filter(token, expected="unread")


def _apply_discussion_unread_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )


def _parse_mentioned_me_search_filter(token: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "mentioned":
        return None

    return True if value.strip().lower() == "me" else None


def _apply_post_mentioned_me_search_filter(queryset, enabled: bool, context: dict):
    user = context.get("user")
    if not enabled:
        return queryset
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(mentions__mentions_user=user)


def _apply_discussion_latest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-last_posted_at", "-id")


def _apply_discussion_top_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-comment_count", "-view_count", "-last_posted_at", "-id")


def _apply_discussion_oldest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "created_at", "id")


def _apply_discussion_newest_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "-created_at", "-id")


def _apply_discussion_unanswered_sort(queryset, context: dict):
    return queryset.order_by("-is_sticky", "comment_count", "-created_at", "-id")


def _apply_all_discussion_list_filter(queryset, context: dict):
    return queryset


def _apply_following_discussion_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user_states__user=user, user_states__is_subscribed=True)


def _apply_my_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(user=user)


def _apply_unread_discussions_list_filter(queryset, context: dict):
    user = context.get("user")
    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    return queryset.filter(last_post_number__gt=0).filter(
        models.Q(user_states__user=user, last_post_number__gt=models.F("user_states__last_read_post_number"))
        | models.Q(user_states__user__isnull=True)
    )


def _parse_is_search_filter(token: str, expected: str) -> bool | None:
    if not token or ":" not in token:
        return None

    prefix, value = token.split(":", 1)
    if prefix.lower() != "is":
        return None

    return True if value.strip().lower() == expected else None
