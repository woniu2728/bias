from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    ApiRoutesExtender,
    AuthorizationPolicy,
    ConsoleExtender,
    ConditionalExtender,
    DiscussionLifecycleExtender,
    EventListenersExtender,
    ForumCapabilitiesExtender,
    FrontendExtender,
    LifecycleExtender,
    ModelExtender,
    ModelUrlExtender,
    ModelVisibilityExtender,
    PolicyExtender,
    PostEventExtender,
    RealtimeExtender,
    RuntimeModel,
    SearchDriverExtender,
    ServiceProviderExtender,
    SettingsExtender,
)
from apps.core.extensions.backend import _build_setting_field_definition
from apps.core.extensions.types import (
    ExtensionEventListenerDefinition,
    ExtensionModelDefinition,
    ExtensionModelRelationDefinition,
    ExtensionModelVisibilityDefinition,
    ExtensionSearchDriverDefinition,
)
from apps.core.forum_registry_types import AdminPageDefinition, DiscussionListQueryDefinition, PostTypeDefinition, SearchFilterDefinition
from apps.core.resource_registry import ResourceDefinition, ResourceEndpointDefinition, ResourceFieldDefinition, ResourceRelationshipDefinition
from extensions.tags.backend.models import DiscussionTag, Tag
from extensions.tags.backend.handlers import (
    dispatch_tag_create,
    dispatch_tag_delete,
    dispatch_tag_index,
    dispatch_tag_popular,
    dispatch_tag_show,
    dispatch_tag_show_by_slug,
    dispatch_tag_update,
)
from extensions.tags.backend.listeners import (
    enrich_realtime_tags_included_payload,
    handle_discussion_approved_tag_stats,
    handle_discussion_tag_stats_refresh,
    handle_discussion_tagged,
    handle_post_approved_tag_stats,
    handle_post_created_tag_stats,
    handle_post_deleted_tag_stats,
    handle_post_hidden_tag_stats,
    handle_post_rejected_tag_stats,
    handle_tag_stats_refresh_requested,
)
from extensions.tags.backend.events import (
    DiscussionTaggedEvent,
    DiscussionTagStatsRefreshEvent,
    TagStatsRefreshRequestedEvent,
)
from extensions.tags.backend.admin_api import router as admin_tags_router
from extensions.tags.backend.discussion_lifecycle import (
    apply_discussion_approved,
    apply_discussion_delete,
    apply_discussion_hidden,
    apply_discussion_rejected,
    prepare_discussion_delete,
)
from extensions.tags.backend.discussion_relationships import set_discussion_tags_relationship
from extensions.tags.backend.tag_relationships import get_discussion_tags
from extensions.tags.backend.resources import (
    resolve_discussion_tags,
    resolve_discussion_tagged_event_data,
    resolve_forum_can_bypass_tag_counts,
    resolve_forum_tags,
    resolve_post_event_mentions_tags,
    resolve_tag_can_reply,
    resolve_tag_can_start_discussion,
    resolve_tag_last_posted_discussion,
    serialize_tag_base,
)
from extensions.tags.backend.search import (
    apply_discussion_tag_list_query,
    apply_discussion_tag_search_filter,
    parse_tag_search_filter,
)
from extensions.tags.backend.services import TagService
from extensions.tags.backend.slug import TagSlugDriver
from extensions.tags.backend.runtime import tag_service_provider
from extensions.tags.backend import tasks as tag_tasks  # noqa: F401


EXTENSION_ID = "tags"
DISCUSSION_MODEL = RuntimeModel("discussions.service", description="discussions 扩展提供的讨论模型。")
POST_MODEL = RuntimeModel("posts.service", description="posts 扩展提供的帖子模型。")


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/tags/frontend/admin/index.js",
            forum_entry="extensions/tags/frontend/forum/index.js",
        )
        .route(
            "/tags",
            "tags",
            "./TagsView.vue",
            title="全部标签",
            description="浏览论坛标签，按主题发现相关讨论。",
            preloads=(
                {
                    "href": "/api/tags?include_children=true",
                    "as": "fetch",
                    "crossorigin": "anonymous",
                },
            ),
            order=30,
        )
        .route(
            "/t/:slug",
            "tag-detail",
            "extensions/discussions/frontend/forum/DiscussionListView.vue",
            title="标签讨论",
            description="查看该标签下的论坛讨论。",
            preloads=(
                {
                    "href": "/api/tags/slug/:slug",
                    "as": "fetch",
                    "crossorigin": "anonymous",
                },
                {
                    "href": "/api/tags?include_children=true",
                    "as": "fetch",
                    "crossorigin": "anonymous",
                },
            ),
            order=31,
        ),
        AdminSurfaceExtender(
            admin_pages=admin_page_definitions(),
        ),
        ConsoleExtender().command(
            "tags.refresh_stats",
            refresh_tag_stats_console_command,
            description="重新计算标签讨论数和最后发帖讨论。",
        ),
        ApiRoutesExtender(
            mounts=(("/admin", admin_tags_router),),
            tags=("Admin",),
        ),
        SettingsExtender(
            fields=setting_field_definitions(),
            expose_to_forum=(
                "min_primary_tags",
                "max_primary_tags",
                "min_secondary_tags",
                "max_secondary_tags",
            ),
        ),
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
            discussion_list_queries=discussion_list_query_definitions(),
            search_filters=search_filter_definitions(),
        ),
        PostEventExtender().type(
            "discussionTagged",
            resolve_discussion_tagged_event_data,
            description="标签变更事件帖的结构化 payload。",
        ),
        ModelExtender(
            definitions=model_definitions(),
            relations=model_relation_definitions(),
        ).owns(
            Tag,
            description="标签模型由 tags 扩展拥有。",
        ).owns(
            DiscussionTag,
            description="讨论标签关系由 tags 扩展拥有。",
        ),
        ModelUrlExtender(Tag).add_slug_driver(
            "default",
            TagSlugDriver,
            field="slug",
            source_field="name",
            max_length=100,
            description="标签 URL slug 生成器。",
        ),
        ModelVisibilityExtender(
            definitions=model_visibility_definitions(),
        ),
        SearchDriverExtender(
            drivers=search_driver_definitions(),
        ),
        PolicyExtender()
        .policy(DISCUSSION_MODEL, DiscussionPolicy)
        .policy(POST_MODEL, PostPolicy)
        .policy(Tag, TagPolicy),
        ApiResourceExtender("discussion")
        .fields(discussion_resource_field_definitions)
        .relationships(discussion_resource_relationship_definitions)
        .add_default_include(("index", "show", "create"), ("tags",)),
        ApiResourceExtender("forum")
        .fields(forum_resource_field_definitions)
        .relationships(forum_resource_relationship_definitions),
        ApiResourceExtender("post")
        .model_relationship(
            "eventPostMentionsTags",
            resource_type="tag",
            many=True,
            description="标签变更事件帖中涉及的标签关系。",
        )
        .add_default_include(("index",), ("eventPostMentionsTags",)),
        ApiResourceExtender(tag_resource_definition())
        .fields(tag_resource_field_definitions)
        .relationships(tag_resource_relationship_definitions)
        .endpoints(tag_resource_endpoints),
        ConditionalExtender().when_extension_enabled("flags", flag_resource_extenders),
        EventListenersExtender(
            listeners=tag_event_listener_definitions(),
        ),
        DiscussionLifecycleExtender().handler(
            "tags",
            prepare_delete=prepare_discussion_delete,
            apply_delete=apply_discussion_delete,
            apply_hidden=apply_discussion_hidden,
            apply_approved=apply_discussion_approved,
            apply_rejected=apply_discussion_rejected,
            description="讨论创建、编辑、删除和状态变化时维护标签关系与统计刷新。",
        ),
        RealtimeExtender().included_payload(
            "tags",
            enrich_realtime_tags_included_payload,
            description="实时讨论事件 payload 中补充讨论关联标签。",
        ).broadcast_discussion_event(
            DiscussionTaggedEvent,
            "discussion.tagged",
            include_discussion=True,
            extension_context=lambda event: {"tags": {"tag_ids": list(event.tag_ids)}} if event.tag_ids else None,
            description="讨论标签变更后向讨论实时流广播标签状态变更。",
        ),
        ServiceProviderExtender(
            key="tags.service",
            provider=tag_service_provider,
        ),
        LifecycleExtender(),
    ]


def admin_page_definitions():
    return (
        AdminPageDefinition(
            path="/admin/tags",
            label="标签管理",
            icon="fas fa-tags",
            module_id=EXTENSION_ID,
            nav_section="feature",
            description="维护标签结构、排序与访问范围。",
        ),
    )


def post_type_definitions():
    return (
        PostTypeDefinition(
            code="discussionTagged",
            label="讨论标签变更",
            module_id=EXTENSION_ID,
            description="记录讨论标签被调整的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-tags",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
    )


def setting_field_definitions():
    return (
        _build_setting_field_definition({
            "key": "min_primary_tags",
            "label": "最少主标签数",
            "type": "number",
            "default": 0,
            "help_text": "发起讨论时要求选择的最少主标签数。",
            "order": 10,
        }),
        _build_setting_field_definition({
            "key": "max_primary_tags",
            "label": "最多主标签数",
            "type": "number",
            "default": 1,
            "help_text": "发起讨论时允许选择的最多主标签数。",
            "order": 20,
        }),
        _build_setting_field_definition({
            "key": "min_secondary_tags",
            "label": "最少次标签数",
            "type": "number",
            "default": 0,
            "help_text": "发起讨论时要求选择的最少次标签数。",
            "order": 30,
        }),
        _build_setting_field_definition({
            "key": "max_secondary_tags",
            "label": "最多次标签数",
            "type": "number",
            "default": 1,
            "help_text": "发起讨论时允许选择的最多次标签数。",
            "order": 40,
        }),
    )


def search_filter_definitions():
    return (
        SearchFilterDefinition(
            code="tag",
            label="按标签过滤",
            module_id=EXTENSION_ID,
            target="discussion",
            parser=parse_tag_search_filter,
            applier=apply_discussion_tag_search_filter,
            syntax="tag:<slug>",
            description="按标签 slug 过滤讨论搜索结果。",
        ),
    )


def discussion_list_query_definitions():
    return (
        DiscussionListQueryDefinition(
            key="tag",
            module_id=EXTENSION_ID,
            applier=apply_discussion_tag_list_query,
            description="按标签 slug 过滤讨论列表。",
            order=40,
        ),
    )


def model_definitions():
    return (
        ExtensionModelDefinition(
            model=DISCUSSION_MODEL,
            key="tags",
            handler=DiscussionTag,
            kind="manyToMany",
            description="讨论关联标签。",
        ),
        ExtensionModelDefinition(
            model=POST_MODEL,
            key="eventPostMentionsTags",
            handler=Tag,
            kind="relationship",
            description="标签变更事件帖中涉及的标签。",
        ),
    )


def model_relation_definitions():
    return (
        ExtensionModelRelationDefinition(
            model=DISCUSSION_MODEL,
            name="tags",
            resolver=get_discussion_tags,
            relation_type="belongsToMany",
            related_model=Tag,
            description="讨论关联标签。",
            inject_attribute=False,
        ),
        ExtensionModelRelationDefinition(
            model=Tag,
            name="parent",
            resolver=lambda tag: tag.parent,
            relation_type="belongsTo",
            related_model=Tag,
            description="标签父级。",
        ),
        ExtensionModelRelationDefinition(
            model=Tag,
            name="children",
            resolver=lambda tag: tag.children.all(),
            relation_type="hasMany",
            related_model=Tag,
            description="标签子级。",
        ),
        ExtensionModelRelationDefinition(
            model=POST_MODEL,
            name="eventPostMentionsTags",
            resolver=resolve_post_event_mentions_tags,
            relation_type="relationship",
            related_model=Tag,
            description="标签变更事件帖中涉及的标签。",
        ),
    )


def model_visibility_definitions():
    return (
        ExtensionModelVisibilityDefinition(
            model=DISCUSSION_MODEL,
            ability="view",
            scope=lambda queryset, context: TagService.filter_discussions_for_user(
                queryset,
                context.get("user"),
            ),
            description="隐藏当前用户不可查看标签下的讨论。",
        ),
        ExtensionModelVisibilityDefinition(
            model=POST_MODEL,
            ability="view",
            scope=lambda queryset, context: TagService.filter_posts_for_user(
                queryset,
                context.get("user"),
            ),
            description="隐藏当前用户不可查看标签下的帖子。",
        ),
        ExtensionModelVisibilityDefinition(
            model=Tag,
            ability="view",
            scope=lambda queryset, context: TagService.filter_tags_for_user(
                queryset,
                context.get("user"),
                action="view",
            ),
            description="隐藏当前用户不可查看的标签。",
        ),
    )


def search_driver_definitions():
    return (
        ExtensionSearchDriverDefinition(
            target="discussion",
            driver="database",
            filters=search_filter_definitions(),
            description="按标签过滤讨论搜索。",
        ),
    )


def tag_resource_definition():
    return ResourceDefinition(
        resource="tag",
        module_id=EXTENSION_ID,
        resolver=serialize_tag_base,
        description="论坛标签主资源。",
    )


def tag_resource_definitions():
    return (tag_resource_definition(),)


def discussion_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="discussion",
            field="tags",
            module_id=EXTENSION_ID,
            resolver=resolve_discussion_tags,
            description="讨论关联的标签列表。",
            prefetch_related=("discussion_tags__tag",),
        ),
    )


def discussion_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="discussion",
            relationship="tags",
            module_id=EXTENSION_ID,
            resolver=resolve_discussion_tags,
            description="讨论关联标签关系。",
            prefetch_related=("discussion_tags__tag",),
            resource_type="tag",
            many=True,
            writable=True,
            value_type="array",
            setter=set_discussion_tags_relationship,
        ),
    )


def forum_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="forum",
            field="tags",
            module_id=EXTENSION_ID,
            resolver=resolve_forum_tags,
            description="论坛首页可见标签树。",
            prefetch_related=("children",),
        ),
        ResourceFieldDefinition(
            resource="forum",
            field="can_bypass_tag_counts",
            module_id=EXTENSION_ID,
            resolver=resolve_forum_can_bypass_tag_counts,
            description="当前用户是否可绕过发帖标签数量限制。",
        ),
    )


def forum_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="forum",
            relationship="tags",
            module_id=EXTENSION_ID,
            resolver=resolve_forum_tags,
            description="论坛首页可见标签关系。",
            resource_type="tag",
            many=True,
        ),
    )


class DiscussionPolicy(AuthorizationPolicy):
    def view(self, user, model, **context):
        return TagService.can_view_discussion_tags(model, user)

    def reply(self, user, model, **context):
        return TagService.can_reply_in_discussion(model, user)


class PostPolicy(AuthorizationPolicy):
    def view(self, user, model, **context):
        discussion = getattr(model, "discussion", None)
        if discussion is None:
            return None
        return TagService.can_view_discussion_tags(discussion, user)


class TagPolicy(AuthorizationPolicy):
    def view(self, user, model, **context):
        return TagService.can_view_tag(model, user)

    def start_discussion(self, user, model, **context):
        return TagService.can_start_discussion_in_tag(model, user)

    def reply(self, user, model, **context):
        return TagService.can_reply_in_tag(model, user)


def tag_resource_field_definitions():
    return (
        ResourceFieldDefinition(
            resource="tag",
            field="can_start_discussion",
            module_id=EXTENSION_ID,
            resolver=resolve_tag_can_start_discussion,
            description="当前用户是否可以在该标签下发起讨论。",
        ),
        ResourceFieldDefinition(
            resource="tag",
            field="can_reply",
            module_id=EXTENSION_ID,
            resolver=resolve_tag_can_reply,
            description="当前用户是否可以在该标签下回复。",
        ),
        ResourceFieldDefinition(
            resource="tag",
            field="last_posted_discussion",
            module_id=EXTENSION_ID,
            resolver=resolve_tag_last_posted_discussion,
            description="标签下最后活跃讨论摘要。",
            select_related=("last_posted_discussion",),
        ),
    )


def tag_resource_relationship_definitions():
    return (
        ResourceRelationshipDefinition(
            resource="tag",
            relationship="last_posted_discussion",
            module_id=EXTENSION_ID,
            resolver=resolve_tag_last_posted_discussion,
            description="标签下最后活跃讨论摘要。",
            select_related=("last_posted_discussion",),
        ),
    )


def tag_resource_endpoints():
    return (
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="create",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_create,
            methods=("POST",),
            path="/tags",
            absolute_path=True,
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="index",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_index,
            methods=("GET",),
            path="/tags",
            absolute_path=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="popular",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_popular,
            methods=("GET",),
            path="/tags/popular",
            absolute_path=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="show",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_show,
            methods=("GET",),
            path="/tags/{object_id}",
            absolute_path=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="show-by-slug",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_show_by_slug,
            methods=("GET",),
            path="/tags/slug/{object_id}",
            absolute_path=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="update",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_update,
            methods=("PATCH",),
            path="/tags/{object_id}",
            absolute_path=True,
            auth_required=True,
        ),
        ResourceEndpointDefinition(
            resource="tag",
            endpoint="delete",
            module_id=EXTENSION_ID,
            handler=dispatch_tag_delete,
            methods=("DELETE",),
            path="/tags/{object_id}",
            absolute_path=True,
            auth_required=True,
        ),
    )


def flag_resource_extenders():
    return [
        ApiResourceExtender("flag").eager_load_when_included(
            "index",
            "post",
            "post__discussion__discussion_tags__tag",
        ),
    ]


def refresh_tag_stats_console_command(options: dict | None = None) -> dict:
    tag_ids = (options or {}).get("tag_ids")
    if tag_ids is None:
        tag_ids = (options or {}).get("tag_id")
    if tag_ids is None:
        normalized_tag_ids = None
    elif isinstance(tag_ids, (list, tuple, set)):
        normalized_tag_ids = [int(item) for item in tag_ids if item is not None]
    else:
        normalized_tag_ids = [int(tag_ids)]

    TagService.refresh_tag_stats(normalized_tag_ids)
    refreshed_count = None if normalized_tag_ids is None else len(set(normalized_tag_ids))
    return {
        "status": "ok",
        "message": "已刷新全部标签统计" if refreshed_count is None else f"已刷新 {refreshed_count} 个标签统计",
        "details": {
            "tag_ids": normalized_tag_ids or [],
            "refreshed_count": refreshed_count,
        },
    }


def tag_event_listener_definitions():
    return (
        ExtensionEventListenerDefinition(
            event_type="extensions.discussions.backend.events.DiscussionApprovedEvent",
            handler=handle_discussion_approved_tag_stats,
            description="讨论审核通过后刷新关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionTaggedEvent,
            handler=handle_discussion_tagged,
            description="刷新标签统计并写入标签变更事件帖。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostCreatedEvent",
            handler=handle_post_created_tag_stats,
            description="回复发布后刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostApprovedEvent",
            handler=handle_post_approved_tag_stats,
            description="回复审核通过后刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostDeletedEvent",
            handler=handle_post_deleted_tag_stats,
            description="回复删除后刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostHiddenEvent",
            handler=handle_post_hidden_tag_stats,
            description="回复隐藏状态变更后刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type="extensions.posts.backend.events.PostRejectedEvent",
            handler=handle_post_rejected_tag_stats,
            description="回复审核拒绝后刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type=DiscussionTagStatsRefreshEvent,
            handler=handle_discussion_tag_stats_refresh,
            description="刷新讨论关联标签统计。",
        ),
        ExtensionEventListenerDefinition(
            event_type=TagStatsRefreshRequestedEvent,
            handler=handle_tag_stats_refresh_requested,
            description="调度标签统计刷新任务。",
        ),
    )
