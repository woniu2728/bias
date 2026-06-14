from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    DiscussionListFilterDefinition,
    DiscussionSortDefinition,
    EventListenersExtender,
    ExtensionEventListenerDefinition,
    ForumCapabilitiesExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    ModelVisibilityExtender,
    PermissionDefinition,
    PostTypeDefinition,
    RealtimeExtender,
    RuntimeModel,
    SearchIndexExtender,
    ServiceProviderExtender,
)
from extensions.discussions.backend.events import (
    DiscussionCreatedEvent,
    DiscussionHiddenEvent,
    DiscussionLockedEvent,
    DiscussionRenamedEvent,
    DiscussionStickyChangedEvent,
)
from extensions.discussions.backend.listeners import (
    handle_discussion_hidden,
    handle_discussion_locked,
    handle_discussion_renamed,
    handle_discussion_sticky_changed,
    handle_post_hidden,
)
from extensions.discussions.backend.registry import (
    apply_all_discussion_list_filter,
    apply_discussion_latest_sort,
    apply_discussion_newest_sort,
    apply_discussion_oldest_sort,
    apply_discussion_top_sort,
    apply_discussion_unanswered_sort,
    apply_my_discussions_list_filter,
    apply_unread_discussions_list_filter,
)
from extensions.discussions.backend.handlers import discussion_resource_endpoints
from extensions.discussions.backend.models import Discussion, DiscussionUser
from extensions.discussions.backend.resources import (
    admin_stats_resource_field_definitions,
    discussion_resource_definitions,
    discussion_resource_field_definitions,
)
from extensions.discussions.backend.realtime import discussion_realtime_broadcaster_provider, resolve_visible_discussion_ids
from extensions.discussions.backend.runtime import discussion_service_provider, discussion_timeline_provider
from extensions.discussions.backend.search_targets import discussion_search_target_provider, post_search_target_provider
from extensions.discussions.backend.visibility import scope_discussion_view, scope_post_view


EXTENSION_ID = "discussions"
POST_MODEL = RuntimeModel("posts.service", description="posts 扩展提供的帖子模型。")


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/discussions/frontend/admin/index.js",
            forum_entry="extensions/discussions/frontend/forum/index.js",
        )
        .route(
            "/",
            "home",
            "./DiscussionListView.vue",
            title="全部讨论",
            description="浏览论坛最新讨论、热门主题和社区回复。",
            order=0,
        )
        .route(
            "/d/:id",
            "discussion-detail",
            "./DiscussionDetailView.vue",
            title="讨论详情",
            description="查看讨论内容和回复。",
            order=1,
        )
        .route(
            "/discussions/create",
            "discussion-create",
            "./DiscussionCreateView.vue",
            title="发起讨论",
            description="创建新的论坛讨论。",
            requires_auth=True,
            order=2,
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
            permissions_pages=("/admin/extensions/discussions/permissions",),
            generated_permissions_page=True,
        ),
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
            discussion_sorts=discussion_sort_definitions(),
            discussion_list_filters=discussion_list_filter_definitions(),
        ),
        EventListenersExtender(
            listeners=event_listener_definitions(),
        ),
        RealtimeExtender().discussion_visibility(
            resolve_visible_discussion_ids,
            description="根据讨论可见性规则解析实时订阅可见讨论。",
        )
        .broadcast_discussion_event(
            DiscussionCreatedEvent,
            "discussion.created",
            include_discussion=True,
            include_post=True,
            post_id_getter=lambda discussion: discussion.first_post_id,
            condition=lambda event: event.is_approved,
            description="审核通过的讨论创建后广播实时讨论和首帖资源。",
        )
        .broadcast_discussion_event(
            DiscussionRenamedEvent,
            "discussion.renamed",
            include_discussion=True,
            description="讨论重命名后广播实时讨论资源。",
        )
        .broadcast_discussion_event(
            DiscussionLockedEvent,
            "discussion.locked",
            include_discussion=True,
            description="讨论锁定状态变化后广播实时讨论资源。",
        )
        .broadcast_discussion_event(
            DiscussionStickyChangedEvent,
            "discussion.sticky_changed",
            include_discussion=True,
            description="讨论置顶状态变化后广播实时讨论资源。",
        )
        .broadcast_discussion_event(
            DiscussionHiddenEvent,
            "discussion.hidden",
            description="讨论隐藏状态变化后广播实时事件。",
        )
        .broadcast_discussion_event(
            "extensions.posts.backend.events.PostCreatedEvent",
            "post.created",
            include_discussion=True,
            include_post=True,
            post_id="post_id",
            condition=lambda event: event.is_approved,
            description="审核通过的回复创建后广播实时讨论和帖子资源。",
        )
        .broadcast_discussion_event(
            "extensions.posts.backend.events.PostHiddenEvent",
            "post.hidden",
            description="回复隐藏状态变化后广播实时事件。",
        ),
        ApiResourceExtender("discussion")
        .endpoints_with(*discussion_resource_endpoints())
        .fields(discussion_resource_field_definitions),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        *[
            ApiResourceExtender(definition)
            for definition in discussion_resource_definitions()
        ],
        ModelExtender()
        .owns(Discussion, description="讨论主题由 discussions 扩展拥有。")
        .owns(DiscussionUser, description="讨论用户阅读和订阅状态由 discussions 扩展拥有。"),
        ModelVisibilityExtender()
        .scope(
            Discussion,
            scope_discussion_view,
            description="限制当前用户只能查看有权限访问的讨论。",
        )
        .scope(
            POST_MODEL,
            scope_post_view,
            description="限制当前用户只能查看有权限访问的讨论帖子。",
        ),
        ServiceProviderExtender(
            key="discussions.service",
            provider=discussion_service_provider,
        ),
        ServiceProviderExtender(
            key="discussions.timeline",
            provider=discussion_timeline_provider,
        ),
        ServiceProviderExtender(
            key="search.target.discussion",
            provider=discussion_search_target_provider,
        ),
        ServiceProviderExtender(
            key="search.target.post",
            provider=post_search_target_provider,
        ),
        ServiceProviderExtender(
            key="realtime.discussion_broadcaster",
            provider=discussion_realtime_broadcaster_provider,
        ),
        SearchIndexExtender().postgres_index(
            "discussions_title_slug_fts_idx",
            drop="DROP INDEX CONCURRENTLY IF EXISTS discussions_title_slug_fts_idx",
            create="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS discussions_title_slug_fts_idx
                ON discussions
                USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(slug, '')))
            """,
            description="为讨论标题和 slug 提供 PostgreSQL 全文搜索索引。",
        ),
        LifecycleExtender(),
    ]


def permission_definitions():
    return (
        PermissionDefinition(
            code="viewForum",
            label="查看论坛",
            section="view",
            section_label="查看权限",
            module_id=EXTENSION_ID,
            icon="fas fa-eye",
            description="允许访问论坛讨论流和讨论详情。",
        ),
        PermissionDefinition(
            code="startDiscussion",
            label="发起讨论",
            section="start",
            section_label="发帖权限",
            module_id=EXTENSION_ID,
            icon="fas fa-edit",
            description="允许创建新讨论。",
        ),
        PermissionDefinition(
            code="startDiscussionWithoutApproval",
            label="发起讨论免审核",
            section="start",
            section_label="发帖权限",
            module_id=EXTENSION_ID,
            icon="fas fa-user-check",
            description="发起讨论后直接公开，无需进入审核队列。",
            required_permissions=("startDiscussion",),
        ),
        PermissionDefinition(
            code="discussion.reply",
            label="回复讨论",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-reply",
            description="允许在讨论中发布回复。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="replyWithoutApproval",
            label="回复免审核",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-user-check",
            description="回复后直接公开，无需进入审核队列。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="discussion.typing",
            label="发送输入提示",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-keyboard",
            description="允许在讨论实时流里向其他用户显示“正在输入”提示。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="discussion.editOwn",
            label="编辑自己的帖子",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许作者编辑自己的讨论首帖或回复。",
        ),
        PermissionDefinition(
            code="discussion.deleteOwn",
            label="删除自己的帖子",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-times",
            description="允许作者删除自己的讨论或回复。",
        ),
        PermissionDefinition(
            code="discussion.edit",
            label="编辑任意帖子",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许管理任意讨论首帖与回复。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="discussion.delete",
            label="删除任意帖子",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-trash",
            description="允许删除任意讨论或回复。",
            required_permissions=("discussion.hide",),
        ),
        PermissionDefinition(
            code="discussion.hide",
            label="隐藏内容",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-eye-slash",
            description="允许隐藏或恢复讨论内容。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="discussion.rename",
            label="重命名讨论",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-heading",
            description="允许修改讨论标题。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="discussion.lock",
            label="锁定讨论",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-lock",
            description="允许锁定或解锁讨论。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="discussion.sticky",
            label="置顶讨论",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-thumbtack",
            description="允许置顶或取消置顶讨论。",
            required_permissions=("viewForum",),
        ),
    )


def post_type_definitions():
    return (
        PostTypeDefinition(
            code="discussionRenamed",
            label="讨论改标题",
            module_id=EXTENSION_ID,
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
            module_id=EXTENSION_ID,
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
            module_id=EXTENSION_ID,
            description="记录讨论被置顶或取消置顶的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-thumbtack",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
        PostTypeDefinition(
            code="discussionHidden",
            label="讨论隐藏状态变更",
            module_id=EXTENSION_ID,
            description="记录讨论被隐藏或恢复显示的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-eye-slash",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
    )


def discussion_sort_definitions():
    return (
        DiscussionSortDefinition(
            code="latest",
            label="最新活跃",
            module_id=EXTENSION_ID,
            applier=apply_discussion_latest_sort,
            description="按最后活跃时间排序，优先展示最近有新回复的讨论。",
            icon="fas fa-clock",
            is_default=True,
            order=10,
            toolbar_visible=True,
        ),
        DiscussionSortDefinition(
            code="newest",
            label="新主题",
            module_id=EXTENSION_ID,
            applier=apply_discussion_newest_sort,
            description="按讨论创建时间倒序，优先展示最新发布的主题。",
            icon="fas fa-file-alt",
            order=20,
            toolbar_visible=True,
        ),
        DiscussionSortDefinition(
            code="top",
            label="热门",
            module_id=EXTENSION_ID,
            applier=apply_discussion_top_sort,
            description="按回复数和浏览量综合排序，优先展示热门讨论。",
            icon="fas fa-fire",
            order=30,
            toolbar_visible=True,
        ),
        DiscussionSortDefinition(
            code="unanswered",
            label="零回复",
            module_id=EXTENSION_ID,
            applier=apply_discussion_unanswered_sort,
            description="优先展示还没有收到其他回复的讨论，便于发现待回应主题。",
            icon="fas fa-comment-slash",
            order=40,
            toolbar_visible=False,
        ),
        DiscussionSortDefinition(
            code="oldest",
            label="最早发布",
            module_id=EXTENSION_ID,
            applier=apply_discussion_oldest_sort,
            description="按讨论创建时间正序排序。",
            icon="fas fa-hourglass-start",
            order=50,
            toolbar_visible=False,
        ),
    )


def discussion_list_filter_definitions():
    return (
        DiscussionListFilterDefinition(
            code="all",
            label="全部讨论",
            module_id=EXTENSION_ID,
            applier=apply_all_discussion_list_filter,
            description="显示当前可见的全部讨论。",
            icon="far fa-comments",
            is_default=True,
            order=10,
            route_path="/",
        ),
        DiscussionListFilterDefinition(
            code="my",
            label="我发起的",
            module_id=EXTENSION_ID,
            applier=apply_my_discussions_list_filter,
            description="仅显示当前用户自己发起的讨论。",
            icon="fas fa-user",
            requires_authenticated_user=True,
            order=30,
            sidebar_visible=False,
        ),
        DiscussionListFilterDefinition(
            code="unread",
            label="未读",
            module_id=EXTENSION_ID,
            applier=apply_unread_discussions_list_filter,
            description="仅显示当前用户仍有未读回复的讨论。",
            icon="fas fa-circle",
            requires_authenticated_user=True,
            order=40,
            sidebar_visible=False,
        ),
    )


def event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type=DiscussionRenamedEvent,
            handler=handle_discussion_renamed,
            description="讨论重命名后写入时间线事件帖。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionLockedEvent,
            handler=handle_discussion_locked,
            description="讨论锁定状态变化后写入时间线事件帖。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionStickyChangedEvent,
            handler=handle_discussion_sticky_changed,
            description="讨论置顶状态变化后写入时间线事件帖。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionHiddenEvent,
            handler=handle_discussion_hidden,
            description="讨论隐藏状态变化后写入时间线事件帖。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostHiddenEvent",
            handler=handle_post_hidden,
            description="回复隐藏状态变化后写入时间线事件帖。",
        ),
    )
