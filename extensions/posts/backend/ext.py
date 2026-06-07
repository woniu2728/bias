from apps.core.extensions import ForumCapabilitiesExtender, LifecycleExtender, ModelExtender
from apps.core.forum_registry_types import PostTypeDefinition
from extensions.posts.backend.models import Post


EXTENSION_ID = "posts"


def extend():
    return [
        ForumCapabilitiesExtender(
            post_types=post_type_definitions(),
        ),
        ModelExtender().owns(
            Post,
            description="帖子流与回复记录由 posts 扩展拥有。",
        ),
        LifecycleExtender(
            install=install,
            enable=enable,
            disable=disable,
            uninstall=uninstall,
        ),
    ]


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


def install(context):
    return {
        "status": "ok",
        "status_label": "已安装",
        "message": "Posts 扩展已安装。",
        "details": {
            "extension_id": context.extension_id,
        },
    }


def enable(context):
    return {
        "status": "ok",
        "status_label": "已启用",
        "message": "Posts 扩展已启用。",
    }


def disable(context):
    return {
        "status": "ok",
        "status_label": "已停用",
        "message": "Posts 扩展已停用。",
    }


def uninstall(context):
    return {
        "status": "ok",
        "status_label": "已卸载",
        "message": "Posts 扩展已卸载。",
    }


def run_migrations(context):
    return _migration_hook_result(context, "run_migrations", "Posts 扩展迁移已执行。")


def rollback_migrations(context):
    return _migration_hook_result(context, "rollback_migrations", "Posts 扩展迁移已回滚。")


def _migration_hook_result(context, hook: str, message: str):
    return {
        "hook": hook,
        "status": "ok",
        "status_label": "已执行",
        "message": message,
        "details": {
            "migration_namespace": context.migration_namespace,
        },
    }
