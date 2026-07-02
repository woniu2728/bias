# Extension API

Bias 的扩展后端开发只使用这些公开模块：

```python
from bias_core.extensions import ...
from bias_core.extensions.runtime import ...
from bias_core.extensions.platform import ...
from bias_core.extensions.forum import ...
```

扩展定义类也会通过公开 contract 层稳定导出：

```python
from bias_core.extensions.contracts import ...
```

约束：

- `bias_core.extensions`：扩展声明入口，提供 Extender、资源定义、权限定义和 helper。
- `bias_core.extensions.runtime`：论坛运行时能力，提供用户、帖子、讨论、标签、通知、审核、搜索等领域操作。
- `bias_core.extensions.platform`：通用平台能力，提供 API 响应、鉴权、设置、队列、存储、文件、邮件、Markdown、可见性、策略等基础服务。
- `bias_core.extensions.forum`：论坛宿主能力，提供注册表、实时广播、在线用户、搜索索引、审计、上传 schema 等宿主级服务。
- `bias_core.extensions.contracts`：只导出定义类和资源运行时构造器，适合类型标注或 contract-first 代码。
- 扩展声明层不要直接 import：
  - `bias_core.extensions.types`
  - `bias_core.forum_registry_types`
  - `bias_core.resource_registry`
  - `bias_core.extensions.runtime_access`
- 扩展代码不要直接 import `bias_core.*` 内部实现；如果现有 SDK 缺能力，应先补公开 facade。
- 扩展运行时能力统一从 `bias_core.extensions.runtime` 获取
- 扩展通用平台工具统一从 `bias_core.extensions.platform` 获取，例如 API 错误响应、分页、资源查询参数、扩展设置、鉴权、审计、领域事件、可见性、策略判断、队列、存储、文件上传、邮件和 Markdown 渲染
- 扩展论坛领域宿主能力统一从 `bias_core.extensions.forum` 获取，例如论坛注册表、实时广播、在线用户、搜索索引、上传 schema、审计记录和 SQLite 写重试
- Core 内部如果继续拆分 runtime、resource、admin 等实现，必须保持以上公开入口稳定

## 推荐后端入口结构

新扩展的 `backend/ext.py` 应只组装 extender，不在模块顶层执行数据库读写、网络请求或导入宿主内部实现：

```python
from __future__ import annotations

from .frontend import frontend_extender
from .resources import resource_extender
from .runtime import service_contract_extender, service_provider_extender


def extend():
    return [
        frontend_extender(),
        service_provider_extender(),
        service_contract_extender(),
        resource_extender(),
    ]
```

可以从 `bias_core.extensions` 直接导入 extender 和 definition；可以从 `bias_core.extensions.runtime` 调用已声明的 runtime service；可以从 `bias_core.extensions.platform` 使用通用服务。不要从 `bias_core.models`、`bias_core.resource_registry`、`bias_core.forum_registry`、`bias_core.extensions.types` 或其他扩展的 Python 包直接导入。

常用能力：

```python
from bias_core.extensions import (
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

from bias_core.extensions.runtime import (
    call_runtime_service,
    get_runtime_service,
    require_runtime_service,
)

from bias_core.extensions.platform import (
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

from bias_core.extensions.forum import (
    SearchIndexService,
    get_forum_registry,
    sqlite_write_retry,
)
```

## Runtime Service Contract

跨扩展调用必须先声明 service contract，再通过 `get_runtime_service(...)` 或 `call_runtime_service(...)` 调用。新代码不要新增旧式 `get_runtime_*` / `*_runtime_*` facade 依赖；兼容映射见 `runtime-facade-migration.md`。

```python
from __future__ import annotations

from bias_core.extensions import RuntimeServiceContractExtender, ServiceProviderExtender
from bias_core.extensions.runtime import call_runtime_service

EXTENSION_ID = "alpha-tools"


class StatusService:
    model = "extension-status"

    def status_payload(self):
        return {
            "data": {
                "type": self.model,
                "id": EXTENSION_ID,
                "attributes": {"ok": True},
            }
        }


def service_provider_extender():
    return ServiceProviderExtender(
        key=f"{EXTENSION_ID}.status",
        provider=lambda: StatusService(),
    )


def service_contract_extender():
    return RuntimeServiceContractExtender().service(
        f"{EXTENSION_ID}.status",
        version="1.0",
        required_methods=("status_payload",),
        required_values=("model",),
    )


def read_status():
    return call_runtime_service(f"{EXTENSION_ID}.status", "status_payload")
```

Contract 规则：

- `service_key` 使用 `<extension-id>.<capability>`，保持稳定。
- `version` 使用主次版本，例如 `1.0`；breaking change 必须升版本并在发布说明中写迁移路径。
- `required_methods` / `required_values` 是消费者可依赖的最小契约，不能无公告移除。
- Provider 应返回服务对象或可调用服务；服务方法返回 JSON-serializable 数据。
- `check_extension_workspace --format json` 会检查 runtime service contract 和 core fallback 风险。

## API Resource Endpoint

扩展 API 端点通过 `ApiResourceExtender` 声明，不直接注册 Django URLConf 或 Ninja router：

```python
from __future__ import annotations

from bias_core.extensions import ApiResourceExtender, ExtensionResourceEndpointDefinition
from bias_core.extensions.runtime import call_runtime_service

EXTENSION_ID = "alpha-tools"


def status_endpoint(context):
    return call_runtime_service(f"{EXTENSION_ID}.status", "status_payload")


def resource_extender():
    return ApiResourceExtender("forum").endpoint(
        ExtensionResourceEndpointDefinition(
            resource="forum",
            endpoint=f"{EXTENSION_ID}.status",
            module_id=EXTENSION_ID,
            handler=status_endpoint,
            path=f"{EXTENSION_ID}/status",
            methods=("GET",),
            description="Generated extension status endpoint.",
        )
    )
```

Endpoint 规则：

- `module_id` 必须是扩展 ID 或扩展拥有的模块 ID。
- `resource` 应指向被扩展的 JSON:API resource，例如 `forum`、`discussion`、`post`。
- `endpoint` 使用稳定 key，避免与其他扩展冲突。
- Handler 接收 `context`，从公开 runtime/platform API 获取能力，不直接穿透访问宿主 internals。
- 字段、关系、排序和过滤器也应使用 `ApiResourceExtender(...).fields(...)`、`.relationships(...)`、`.sorts(...)`、`.filters(...)` 声明。

## Frontend 和 Manifest

后端用 `FrontendExtender` 只声明资源入口：

```python
from bias_core.extensions import FrontendExtender


def frontend_extender():
    return (
        FrontendExtender()
        .admin("frontend/admin/index.js")
        .forum("frontend/forum/index.js")
    )
```

`extension.json` 至少应包含：

```json
{
  "schema_version": 1,
  "id": "alpha-tools",
  "name": "Alpha Tools",
  "version": "0.1.0",
  "dependencies": ["core"],
  "backend": {"entry": "bias_ext_alpha_tools.backend.ext"},
  "compatibility": {
    "bias_version": ">=0.1.0 <0.2.0",
    "api_version": "1.0",
    "api_stability": "experimental"
  }
}
```

`pyproject.toml` 必须声明 `bias-core` 依赖、`bias.extensions` entry point、扩展资源 data-files，以及共享测试 settings：

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "bias_core.extension_test_settings"
```

## 发布前 Gate

```powershell
python manage.py inspect_extensions --format json
python manage.py inspect_extensions --contract-baseline-only --output extension-contract-baseline.json
python manage.py validate_extensions --extensions-path D:\files\project\tmp\.tmp-extension-dx --strict --format json
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp\.tmp-extension-dx --check-runtime-facades --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp\.tmp-extension-dx --skip-inspect-extensions --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp\.tmp-extension-dx --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
```

`inspect_extensions` 的 JSON 输出包含：

- `compatibility_matrix`：按扩展输出 manifest `schema_version`、Bias 兼容范围、当前 Bias 版本兼容结果、API 版本和稳定性、依赖/可选依赖/冲突/能力声明、分发签名/abandoned 状态，以及 release policy gate 名称。
- `summary.compatibility_blocking_count`、`summary.bias_version_incompatible_count`、`summary.unstable_api_count`、`summary.abandoned_distribution_count`：发布流水线可直接消费的兼容矩阵计数；`prepare_release` 会阻断兼容矩阵阻断项和 Bias 版本不兼容扩展。
- `--contract-baseline-only`：生成 `prepare_release --contract-baseline` 可消费的契约基线，用于阻断 public resource、runtime service、frontend route 等破坏性变化。

`inspect_extension_packages` 的 JSON 输出包含：

- `install_plan`：安装前计划，`executes_install=false`，列出依赖顺序、构建/审计/install smoke/lifecycle smoke 步骤。
- `upgrade_risk`：升级前风险摘要，覆盖缺失依赖、依赖环、Bias 版本不兼容、experimental/beta API 和 abandoned distribution。
- `summary.blocking_risk_count`：发布流水线应把非 0 值当作阻断项；`prepare_release` 已内置同一阻断检查。

`prepare_release` 的扩展包 gate 会以 JSON 方式执行 `inspect_extension_packages --build --install-smoke --install-set-smoke --migration-smoke --lifecycle-smoke`，因此发布前必须同时满足 wheel 交付、安装态发现、整组依赖顺序、迁移 smoke 和 enable/disable 生命周期 smoke。

使用 `prepare_release --extension-report <path>` 归档发布扩展报告时，报告会保留 `inspect_extensions` 的诊断快照，并额外写入 `release_gate` 和 `package_audit`；`package_audit` 包含本次包审计的 `install_plan`、`upgrade_risk`、install-set/migration/lifecycle smoke 结果和阻断风险计数。

如果开发扩展时发现必须直接修改 core，优先判断是否只是缺少新的扩展点；应先补公开 API 或 facade，而不是让扩展直接耦合到 core 内部实现文件。

