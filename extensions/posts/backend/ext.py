from apps.core.extensions import (
    AdminSurfaceExtender,
    ApiResourceExtender,
    FrontendExtender,
    ForumCapabilitiesExtender,
    LifecycleExtender,
    ModelExtender,
    SearchIndexExtender,
    ServiceProviderExtender,
)
from apps.core.forum_registry_types import PermissionDefinition, PostTypeDefinition
from extensions.posts.backend.handlers import post_resource_endpoints
from extensions.posts.backend.models import Post
from extensions.posts.backend.resources import (
    admin_stats_resource_field_definitions,
    post_resource_definitions,
    post_resource_field_definitions,
)
from extensions.posts.backend.runtime import post_service_provider


EXTENSION_ID = "posts"


def extend():
    return [
        FrontendExtender(
            admin_entry="extensions/posts/frontend/admin/index.js",
            forum_entry="extensions/posts/frontend/forum/index.js",
        ),
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
        ),
        AdminSurfaceExtender(
            permissions=permission_definitions(),
        ),
        ApiResourceExtender("post")
        .endpoints_with(*post_resource_endpoints())
        .fields(post_resource_field_definitions),
        ApiResourceExtender("admin_stats").fields(admin_stats_resource_field_definitions),
        *[
            ApiResourceExtender(definition)
            for definition in post_resource_definitions()
        ],
        ModelExtender().owns(
            Post,
            description="帖子流与回复记录由 posts 扩展拥有。",
        ),
        ServiceProviderExtender(
            key="posts.service",
            provider=post_service_provider,
        ),
        SearchIndexExtender().postgres_index(
            "posts_content_fts_idx",
            drop="DROP INDEX CONCURRENTLY IF EXISTS posts_content_fts_idx",
            create=build_posts_content_search_index_sql,
            description="为可搜索帖子类型的正文提供 PostgreSQL 全文搜索索引。",
        ),
        LifecycleExtender(),
    ]


def build_posts_content_search_index_sql() -> str:
    searchable_post_types = ", ".join(
        f"'{definition.code}'"
        for definition in post_type_definitions()
        if definition.searchable
    ) or "'comment'"
    return f"""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS posts_content_fts_idx
        ON posts
        USING GIN (to_tsvector('simple', coalesce(content, '')))
        WHERE type IN ({searchable_post_types})
    """


def post_type_definitions():
    return (
        PostTypeDefinition(
            code="comment",
            label="普通回复",
            module_id=EXTENSION_ID,
            description="默认的讨论回复帖子类型，会参与回复统计、帖子流与全文搜索。",
            icon="far fa-comment",
            is_default=True,
            is_stream_visible=True,
            counts_toward_discussion=True,
            counts_toward_user=True,
            searchable=True,
        ),
        PostTypeDefinition(
            code="postHidden",
            label="回复隐藏状态变更",
            module_id=EXTENSION_ID,
            description="记录回复被隐藏或恢复显示的系统事件帖，不计入回复统计和全文搜索。",
            icon="fas fa-eye-slash",
            is_default=False,
            is_stream_visible=True,
            counts_toward_discussion=False,
            counts_toward_user=False,
            searchable=False,
        ),
    )


def permission_definitions():
    return (
        PermissionDefinition(
            code="post.editOwn",
            label="编辑自己的回复",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许作者编辑自己的普通回复。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="post.deleteOwn",
            label="删除自己的回复",
            section="reply",
            section_label="回复权限",
            module_id=EXTENSION_ID,
            icon="fas fa-times",
            description="允许作者删除自己的普通回复。",
            required_permissions=("discussion.reply",),
        ),
        PermissionDefinition(
            code="post.edit",
            label="编辑任意回复",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-pencil-alt",
            description="允许管理任意普通回复内容。",
            required_permissions=("viewForum",),
        ),
        PermissionDefinition(
            code="post.delete",
            label="删除任意回复",
            section="moderate",
            section_label="内容管理",
            module_id=EXTENSION_ID,
            icon="fas fa-trash",
            description="允许删除任意普通回复。",
            required_permissions=("discussion.hide",),
        ),
    )
