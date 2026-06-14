# Extension API

Bias 的扩展后端开发只使用这些公开模块：

```python
from apps.core.extensions import ...
from apps.core.extensions.runtime import ...
from apps.core.extensions.platform import ...
from apps.core.extensions.forum import ...
```

扩展定义类也会通过公开 contract 层稳定导出：

```python
from apps.core.extensions.contracts import ...
```

约束：

- `apps.core.extensions`：扩展声明入口，提供 Extender、资源定义、权限定义和 helper。
- `apps.core.extensions.runtime`：论坛运行时能力，提供用户、帖子、讨论、标签、通知、审核、搜索等领域操作。
- `apps.core.extensions.platform`：通用平台能力，提供 API 响应、鉴权、设置、队列、存储、文件、邮件、Markdown、可见性、策略等基础服务。
- `apps.core.extensions.forum`：论坛宿主能力，提供注册表、实时广播、在线用户、搜索索引、审计、上传 schema 等宿主级服务。
- `apps.core.extensions.contracts`：只导出定义类和资源运行时构造器，适合类型标注或 contract-first 代码。
- 扩展声明层不要直接 import：
  - `apps.core.extensions.types`
  - `apps.core.forum_registry_types`
  - `apps.core.resource_registry`
  - `apps.core.extensions.runtime_access`
- 扩展代码不要直接 import `apps.core.*` 内部实现；如果现有 SDK 缺能力，应先补公开 facade。
- 扩展运行时能力统一从 `apps.core.extensions.runtime` 获取
- 扩展通用平台工具统一从 `apps.core.extensions.platform` 获取，例如 API 错误响应、分页、资源查询参数、扩展设置、鉴权、审计、领域事件、可见性、策略判断、队列、存储、文件上传、邮件和 Markdown 渲染
- 扩展论坛领域宿主能力统一从 `apps.core.extensions.forum` 获取，例如论坛注册表、实时广播、在线用户、搜索索引、上传 schema、审计记录和 SQLite 写重试
- Core 内部如果继续拆分 runtime、resource、admin 等实现，必须保持以上公开入口稳定

常用能力：

```python
from apps.core.extensions import (
    ApiResourceExtender,
    EventListenersExtender,
    PermissionDefinition,
    ResourceEndpointDefinition,
    ResourceFieldDefinition,
    admin_action,
    event_listener,
    runtime_action,
    setting_field,
)

from apps.core.extensions.runtime import (
    get_runtime_user_by_id,
    get_runtime_resource_registry,
    notify_runtime_notification,
)

from apps.core.extensions.platform import (
    AccessTokenAuth,
    AuthorizationPolicy,
    DomainEvent,
    FileUploadService,
    MarkdownService,
    PaginationService,
    QueueService,
    ResourceQueryOptions,
    api_error,
    dispatch_forum_event_after_commit,
    evaluate_extension_policy,
    get_extension_settings,
    log_admin_action,
    parse_resource_query_options,
)

from apps.core.extensions.forum import (
    SearchIndexService,
    get_forum_registry,
    sqlite_write_retry,
)
```

如果开发扩展时发现必须直接修改 core，优先判断是否只是缺少新的扩展点；应先补公开 API 或 facade，而不是让扩展直接耦合到 core 内部实现文件。
