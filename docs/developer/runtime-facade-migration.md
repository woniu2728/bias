# Runtime Facade 迁移说明

日期：2026-07-01

## 目标

旧的 `bias_core.extensions.runtime` 专用 facade 仍保留兼容期入口，但新扩展和新功能必须通过 runtime service contract 访问跨扩展能力。

本文件是正式迁移规范。除 `call_runtime_service`、`get_runtime_service`、`require_runtime_service`、`get_runtime_service_value`、`get_runtime_model`、`get_runtime_resource_registry` 等平台级入口外，`get_runtime_*`、`create_runtime_*`、`list_runtime_*`、`*_runtime_*` 形式的领域 facade 都视为 legacy。

推荐写法：

```python
from bias_core.extensions.runtime import get_runtime_service


users = get_runtime_service("users.service")
user = users.get_by_id(user_id)
```

或：

```python
from bias_core.extensions.runtime import call_runtime_service


payload = call_runtime_service("notifications.service", "notify_post_liked_from_event", event)
```

## 迁移规则

- 不要直接 import 其他扩展的 `backend.*` model/service。
- 不要在新代码中新增 `get_runtime_*`、`*_runtime_*` 专用 facade 依赖。
- 需要跨扩展能力时，在 manifest 中声明 `dependencies` 或 `optional_dependencies`。
- 服务提供方必须声明 `RuntimeServiceContractExtender().service(...)`。
- 调用方只依赖服务 key 和契约方法，不依赖提供方内部模块路径。

## 推荐 service key

| service key | 领域 | 示例 |
| --- | --- | --- |
| `users.service` | 用户、权限、资料 | `call_runtime_service("users.service", "get_by_id", user_id)` |
| `posts.service` | 帖子读写、序列化、审核 | `call_runtime_service("posts.service", "serialize_by_id", post_id, user)` |
| `discussions.service` | 讨论读写、可见性、订阅 | `call_runtime_service("discussions.service", "get_visible_ids", user=user)` |
| `tags.service` | 标签、标签统计、阅读状态 | `call_runtime_service("tags.service", "summaries_by_slugs", slugs)` |
| `notifications.service` | 通知创建、同步、删除 | `call_runtime_service("notifications.service", "sync_notifications", user)` |
| `search.service` | 搜索、建议、过滤器 | `call_runtime_service("search.service", "search_all", query, user=user)` |
| `approval.service` | 审核队列和处理 | `call_runtime_service("approval.service", "list_queue", actor=user)` |

## 常用映射

| 旧 facade | 新 service contract |
| --- | --- |
| `ensure_runtime_user_not_suspended(user, label)` | `get_runtime_service("users.service").ensure_not_suspended(user, label)` |
| `ensure_runtime_user_email_confirmed(user, label)` | `get_runtime_service("users.service").ensure_email_confirmed(user, label)` |
| `ensure_runtime_forum_permission(user, names, message)` | `get_runtime_service("users.service").ensure_forum_permission(user, names, message)` |
| `has_runtime_forum_permission(user, names)` | `get_runtime_service("users.service").has_forum_permission(user, names)` |
| `requires_runtime_content_approval(user, permission)` | `get_runtime_service("users.service").requires_content_approval(user, permission)` |
| `get_runtime_user_by_id(user_id)` | `get_runtime_service("users.service").get_by_id(user_id)` |
| `list_runtime_users_by_usernames(names)` | `get_runtime_service("users.service").list_by_usernames(names)` |
| `get_runtime_username_id_map(names)` | `get_runtime_service("users.service").username_id_map(names)` |
| `increment_runtime_user_comment_count(user_id, delta)` | `get_runtime_service("users.service").increment_comment_count(user_id, delta)` |
| `increment_runtime_user_discussion_count(user_id, delta)` | `get_runtime_service("users.service").increment_discussion_count(user_id, delta)` |
| `apply_runtime_user_comment_count_deltas(deltas)` | `get_runtime_service("users.service").apply_comment_count_deltas(deltas)` |
| `get_runtime_post_action_context(post_id, user, ...)` | `get_runtime_service("content.posts").get_action_context(post_id, user, ...)` |
| `get_runtime_visible_post_ids(user, ...)` | `get_runtime_service("content.posts").get_visible_ids(user, ...)` |
| `can_runtime_view_post(post, user)` | `get_runtime_service("content.posts").can_view(post, user)` |
| `serialize_runtime_post(post, user, ...)` | `get_runtime_service("content.posts").serialize(post, user, ...)` |
| `get_runtime_post_notification_context(post_id)` | `get_runtime_service("content.posts").notification_context(post_id)` |
| `get_runtime_post_reply_notification_context(reply_to, post, user)` | `get_runtime_service("content.posts").reply_notification_context(reply_to, post, user)` |
| `count_runtime_post_pending_approvals()` | `get_runtime_service("content.posts").count_pending_approvals()` |
| `list_runtime_post_approval_queue_items()` | `get_runtime_service("content.posts").list_approval_queue()` |
| `process_runtime_post_approval_item(...)` | `get_runtime_service("content.posts").process_approval(...)` |
| `get_runtime_visible_discussion_ids(user, ...)` | `get_runtime_service("content.discussions").get_visible_ids(user, ...)` |
| `has_runtime_discussion_visibility(...)` | `get_runtime_service("content.discussions").has_visibility(...)` |
| `validate_runtime_replyable_discussion(...)` | `get_runtime_service("content.discussions").validate_replyable(...)` |
| `mark_runtime_discussion_read(...)` | `get_runtime_service("content.discussions").mark_read(...)` |
| `clamp_runtime_discussion_read_states(...)` | `get_runtime_service("content.discussions").clamp_read_states(...)` |
| `lock_runtime_discussion_for_post_number(id)` | `get_runtime_service("content.discussions").lock_for_post_number(id)` |
| `refresh_runtime_discussion_approved_stats(...)` | `get_runtime_service("content.discussions").refresh_approved_stats(...)` |
| `list_runtime_pending_discussion_first_post_ids()` | `get_runtime_service("content.discussions").pending_first_post_ids()` |
| `count_runtime_discussion_pending_approvals()` | `get_runtime_service("content.discussions").count_pending_approvals()` |
| `list_runtime_discussion_approval_queue_items()` | `get_runtime_service("content.discussions").list_approval_queue()` |
| `process_runtime_discussion_approval_item(...)` | `get_runtime_service("content.discussions").process_approval(...)` |
| `create_runtime_timeline_from_builder(...)` | `get_runtime_service("discussions.timeline").create_from_builder(...)` |
| `notify_runtime_notification(method, ...)` | `call_runtime_service("notifications.service", method, ...)` |
| `create_runtime_notification(...)` | `get_runtime_service("notifications.service").create(...)` |
| `sync_runtime_notifications(...)` | `get_runtime_service("notifications.service").sync(...)` |
| `delete_runtime_notifications(...)` | `get_runtime_service("notifications.service").delete(...)` |
| `delete_runtime_discussion_reply_notifications_for_post(post_id)` | `get_runtime_service("notifications.service").delete_discussion_reply_for_post(post_id)` |
| `delete_runtime_user_mentioned_notifications_for_post(...)` | `get_runtime_service("notifications.service").delete_user_mentioned_for_post(...)` |
| `get_runtime_tag_summaries_by_slugs(slugs)` | `get_runtime_service("tags.service").summaries_by_slugs(slugs)` |
| `refresh_runtime_tag_stats(...)` | `get_runtime_service("tags.service").refresh_stats(...)` |
| `refresh_runtime_discussion_tag_stats(...)` | `get_runtime_service("tags.service").refresh_discussion_stats(...)` |
| `mark_runtime_tag_read(...)` | `get_runtime_service("tags.service").mark_read(...)` |

## 允许继续使用的入口

这些属于平台级 runtime 能力，不表示对某个业务扩展的旧 facade 依赖：

- `get_runtime_service`
- `call_runtime_service`
- `get_runtime_service_value`
- `get_runtime_model`
- `get_runtime_resource_registry`
- `refresh_runtime_model_private`
- runtime policy / model visibility 相关平台入口

## 门禁

发布前执行：

```powershell
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --check-runtime-facades --fail-on-warnings --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
```

要求：

- `runtime_facade_dependency_graph.runtime_edges=[]`。
- `legacy_runtime_facade_import` warning 为 0。
- `runtime_facade_top_level_import` warning 为 0。
