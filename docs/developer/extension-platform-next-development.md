# 扩展平台下一阶段开发计划

## 目标

下一阶段不继续优先增加扩展点，而是把已经存在的扩展平台能力收敛成更清晰、更稳定、更容易开发的产品化接口。

核心目标：

1. 保持 `bias`、`bias_core`、`bias-content`、`bias-ext-*` 的多仓库边界清晰。
2. 收敛扩展后端 API，减少重复入口和历史兼容接口对新开发者的干扰。
3. 补齐官方扩展的边界检查，确保扩展不直接依赖 core 内部实现。
4. 降低简单扩展的开发成本，让开发者可以按模板完成常见场景。
5. 修正本地安装和交付链路，使 README、脚本、依赖仓库要求和实际构建行为一致。

非目标：

1. 不重写扩展系统。
2. 不引入外部插件市场。
3. 不一次性删除旧 runtime facade。
4. 不把所有官方扩展重构成同一种文件布局。
5. 不为了抽象统一牺牲已有功能稳定性。

## 当前判断

当前架构已经具备平台化基础：

- `bias` 是站点壳，负责部署、配置、前端宿主和运行入口。
- `bias_core` 是平台核心，负责扩展发现、生命周期、资源注册、运行时服务、后台管理和公开 SDK。
- `bias-content` 是基础内容域，不应被安装脚本遗漏。
- `bias-ext-*` 是官方功能扩展，通过 manifest、entry point、Extender、runtime service contract 和前端 SDK 接入。

当前主要问题不是方向错误，而是 API 面开始膨胀：

- `bias_core.extensions.runtime` 同时存在推荐的 service contract 调用和大量旧式 `get_runtime_*` / `create_runtime_*` / `list_runtime_*` facade。
- Extender 数量较多，简单扩展也容易被迫理解过多概念。
- 官方扩展仍有少量生产代码直接 import core 内部实现。
- 安装脚本只检查 `bias_core` 和 `bias-ext-*`，但实际 wheel 构建也依赖 `bias-content`。
- 前端 SDK 已有边界检查，但 SDK 同步机制需要继续区分公开 API 和宿主内部实现。

## 目标架构

### 后端公开入口

新扩展后端只推荐使用以下入口：

```python
from bias_core.extensions import ...
from bias_core.extensions.runtime import call_runtime_service, get_runtime_service, require_runtime_service
from bias_core.extensions.platform import ...
from bias_core.extensions.forum import ...
from bias_core.extensions.contracts import ...
```

`bias_core.extensions.runtime` 中的专用 facade 保留兼容，但应标注为 legacy，并停止在新文档和新模板中使用。

目标调用方式：

```python
call_runtime_service("posts.service", "create", payload)
```

而不是：

```python
create_runtime_post(...)
get_runtime_post_service()
```

### 扩展声明模型

普通扩展只需要理解 5 类核心能力：

1. `FrontendExtender`
2. `SettingsExtender`
3. `ApiResourceExtender`
4. `ServiceProviderExtender`
5. `RuntimeServiceContractExtender`

高级能力单独进阶：

- `PolicyExtender`
- `ModelExtender`
- `ModelVisibilityExtender`
- `RealtimeExtender`
- `LifecycleExtender`
- `SearchDriverExtender`
- `SearchIndexExtender`
- `AdminSurfaceExtender`
- `EventListenersExtender`

文档和脚手架要先覆盖普通扩展，不让简单需求一开始就接触高级扩展点。

### 前端公开入口

扩展前端只允许使用：

```js
import { ... } from '@bias/core'
import { ... } from '@bias/core/common'
import { ... } from '@bias/core/forum'
import { ... } from '@bias/core/admin'
import { ... } from '@bias/core/components/admin'
```

禁止扩展直接 import：

- 宿主 `frontend/src/*`
- 其他扩展的 `frontend/*`
- `vue`、`pinia`、`vue-router` 等宿主运行时依赖

如果扩展确实缺少能力，优先补 `@bias/core` SDK，而不是绕过边界。

## 阶段 1：安装链路和工作区约束收口

### 背景

当前 Docker 安装脚本通过 workspace root 查找源码包，但只要求：

```text
bias_core
bias-ext-*
```

实际完整本地源码安装还需要：

```text
bias-content
```

否则构建可能从包源拉取旧版本，或者在没有发布包时失败。

### 任务

1. 修改 `scripts/docker-install.sh`。
2. 修改 `scripts/docker-upgrade.sh`。
3. workspace root 检查必须同时要求：

```text
bias_core/
bias-content/
bias-ext-*/
```

4. wheel 构建顺序固定为：

```text
bias_core
bias-content
bias-ext-*
```

5. 错误信息要明确列出缺失项，例如：

```text
Error: workspace root is missing required package directories:
- bias_core
- bias-content
- at least one bias-ext-*
```

6. 更新 README 首次部署说明，明确站点源码需要和 core/content/extensions 放在同级目录。

### 验收

1. 缺少 `bias-content` 时，脚本在构建前失败，并给出明确提示。
2. 存在 `bias-content` 时，脚本构建本地 `bias-content` wheel。
3. README 的目录示例和脚本行为一致。

## 阶段 2：Runtime API 收敛

### 背景

当前 `bias_core.extensions.runtime` 既导出通用 service contract API，也导出大量领域 facade。新扩展很难判断应该使用哪套接口。

### 任务

1. 把 `runtime-facade-migration.md` 升级为正式迁移规范。
2. 在文档中明确：

```text
新扩展只能使用 call_runtime_service / get_runtime_service / require_runtime_service。
旧式 get_runtime_* / create_runtime_* / list_runtime_* 仅用于兼容官方历史扩展。
```

3. 在 `extension-api.md` 中把旧式 facade 移到 legacy 章节。
4. 为常用 service key 建立索引表：

```text
users.service
posts.service
discussions.service
tags.service
notifications.service
search.service
approval.service
```

5. 给每个 service contract 补最小示例：

```python
call_runtime_service("users.service", "resolve_by_username", username)
```

6. 新增检查规则：新扩展模板和新扩展代码不得新增旧式 runtime facade import。

### 验收

1. 新生成扩展不 import 旧式 runtime facade。
2. 文档中普通路径只出现 service contract 调用。
3. 官方扩展允许暂时保留旧式 facade，但检查报告要能标出 legacy 使用点。

## 阶段 3：官方扩展边界检查全覆盖

### 背景

当前已有 import-linter 和自定义检查，但覆盖还不够均匀。抽样发现生产扩展中仍有直接 import core 内部实现的情况，例如资源 endpoint runner 这类内部对象。

### 任务

1. 建立官方扩展统一边界检查命令：

```bash
python manage.py check_extension_workspace --extensions-path <workspace> --strict --format json
```

2. 规则覆盖所有 `bias-ext-*` 和 `bias-content`。
3. 生产代码禁止 import：

```text
bias_core.models
bias_core.resource_registry
bias_core.resource_objects
bias_core.resource_serializer
bias_core.resource_endpoint_runner
bias_core.settings_service
bias_core.services
bias_core.conf
bias_core.release
bias_core.middleware
bias_core.jwt_auth
bias_core.websocket_auth
bias_core.db
bias_core.schemas
```

4. 测试代码可以有受控例外，但必须集中声明。
5. 对每个违规点做三选一处理：

```text
补公开 facade
调整扩展实现
声明临时豁免和移除期限
```

### 验收

1. 官方扩展生产代码边界检查为 0 violation。
2. 所有临时豁免都有 owner、原因和移除条件。
3. CI 或发布 gate 可以消费 JSON 输出并阻断新增违规。

## 阶段 4：扩展模板分层

### 背景

当前 `create_extension` 已经能生成可运行脚手架，但默认模板偏“全能力示例”，对简单扩展仍显得重。

### 任务

为 `create_extension` 增加模板类型：

```bash
python manage.py create_extension demo-settings --template settings
python manage.py create_extension demo-admin-page --template admin-page
python manage.py create_extension demo-forum-widget --template forum-widget
python manage.py create_extension demo-resource --template resource
python manage.py create_extension demo-full --template full
```

模板定义：

1. `settings`
   - 只生成 `SettingsExtender`
   - 不生成 runtime service contract
   - 不生成资源 endpoint

2. `admin-page`
   - 生成后台入口
   - 生成 `AdminSurfaceExtender`
   - 生成最小权限定义

3. `forum-widget`
   - 生成前台入口
   - 生成 frontend registry 示例
   - 不生成后端资源

4. `resource`
   - 生成 `ApiResourceExtender`
   - 生成一个只读 endpoint
   - 生成 service contract 示例

5. `full`
   - 保留当前完整示例
   - 用于高级扩展开发

### 验收

1. 每个模板生成后可以通过 `validate_extensions`。
2. 每个模板都有 README，说明下一步如何启用。
3. 简单模板生成的文件数明显少于 full 模板。
4. Quickstart 默认使用 `forum-widget` 或 `settings`，而不是 full。

## 阶段 5：Extender 文档重排

### 背景

当前扩展 API 文档完整但偏宽。下一阶段需要按开发者路径重排，而不是按系统能力罗列。

### 新文档结构

1. `extension-quickstart.md`
   - 只讲 15 分钟内创建并启用一个扩展。

2. `extension-api.md`
   - 只讲公开入口和稳定规则。

3. `extension-cookbook.md`
   - 按场景给配方：
     - 增加设置项
     - 增加后台页面
     - 增加前台 widget
     - 增加资源字段
     - 增加资源 endpoint
     - 监听事件
     - 调用其他扩展服务

4. `extension-advanced.md`
   - 高级能力：
     - lifecycle
     - realtime
     - model visibility
     - search index
     - custom route
     - package audit

5. `runtime-facade-migration.md`
   - 只保留迁移说明和 legacy 对照表。

### 验收

1. 新扩展开发者不需要阅读 `extension-system-roadmap.md` 才能开始。
2. 每个 cookbook 示例都能直接复制到脚手架。
3. 文档中公开 API 和 legacy API 分区明确。

## 阶段 6：前端 SDK 稳定化

### 背景

前端 SDK 已经有 `@bias/core` 包和边界检查，但 SDK 目前从宿主源码同步，长期要避免把内部实现误认为公开 API。

### 任务

1. 为 `@bias/core` 建立公开导出基线。
2. 每次新增导出必须说明稳定性：

```text
stable
experimental
internal
```

3. `check:sdk-package` 阻断未声明稳定性的新增导出。
4. `check:extension-boundary` 保持禁止扩展直接 import 宿主源码。
5. 为常用前端扩展场景补 cookbook：

```text
注册后台页面
注册论坛导航
注册讨论操作
注册帖子类型组件
注册搜索过滤器
注册 composer 扩展
```

### 验收

1. `npm run check:platform` 通过。
2. 新增 SDK 导出会更新基线。
3. 扩展前端不需要直接 import `vue` / `pinia` / `vue-router`。

## 阶段 7：运行时和启停体验补强

### 背景

后台扩展启停已经可用，但启停后触发的 runtime rebuild、frontend manifest rebuild、static asset 写入等路径需要更稳。

### 任务

1. 启停扩展后统一返回：

```json
{
  "extension": {},
  "runtime": {
    "requires_rebuild": false,
    "frontend_manifest_status": "ok"
  },
  "warnings": []
}
```

2. 权限错误、前端构建错误、依赖错误要使用不同 code。
3. 后台 UI 对不同错误给出明确动作：

```text
权限错误：提示检查容器 /app/static 权限
构建错误：展示 build stderr
依赖错误：展示需要启用的依赖扩展
```

4. `doctor` 增加扩展资产目录可写检查：

```text
/app/static/extensions writable by web user
```

### 验收

1. `/api/admin/extensions/{id}/enable` 和 `/disable` 不暴露裸异常字符串。
2. `doctor` 能提前发现 static/extensions 权限问题。
3. 后台扩展页面能显示可执行的修复建议。

## 阶段 8：发布 Gate 收口

### 背景

现有发布前命令很多，能力强但不够聚合。下一阶段应提供一个站点级 gate。

### 任务

新增或收敛一个命令：

```bash
python manage.py check_platform_release --format json
```

它聚合：

```text
inspect_extensions
validate_extensions
inspect_extension_imports
check_extension_workspace
inspect_extension_packages
doctor
frontend check:platform
```

输出结构：

```json
{
  "status": "ok",
  "blocking_count": 0,
  "checks": {
    "extensions": {},
    "imports": {},
    "packages": {},
    "frontend": {},
    "doctor": {}
  }
}
```

### 验收

1. 单条命令可以作为发布阻断入口。
2. JSON 输出稳定，可被 CI 使用。
3. 失败项包含文件、扩展 ID、原因和建议动作。

## 推荐实施顺序

优先级从高到低：

1. 安装链路补齐 `bias-content`。
2. 修复官方扩展生产代码的 core 内部 import。
3. 文档中把旧 runtime facade 标为 legacy。
4. 增加 simple templates。
5. 扩展 `doctor`，检查 `/app/static/extensions` 可写。
6. 前端 SDK 导出基线和稳定性标签。
7. 聚合发布 gate。

## 每阶段完成定义

每个阶段必须满足：

1. 文档更新。
2. 至少一个正向测试。
3. 至少一个失败路径测试。
4. 官方扩展示例同步。
5. 安装或升级脚本不回归。
6. `doctor` 或检查命令能暴露关键风险。

## 风险和控制

### 风险：过早删除旧 facade

控制：

- 只标 legacy，不立即删除。
- 给迁移表和检查报告。
- 官方扩展分批迁移。

### 风险：模板过多导致维护成本上升

控制：

- 模板共享生成函数。
- 每个模板只覆盖一个明确场景。
- full 模板保留为高级参考。

### 风险：边界检查误伤测试代码

控制：

- 生产代码和测试代码分开检查。
- 测试例外集中声明。
- JSON 输出标明 violation 类型。

### 风险：前端 SDK 公开面继续膨胀

控制：

- 新导出必须有稳定性标签。
- 新导出必须有使用场景。
- 未被扩展使用的导出不默认公开。

## 近期任务清单

第一批建议直接落地：

1. `scripts/docker-install.sh` / `docker-upgrade.sh` 检查和构建 `bias-content`。
2. `README.md` 增加 workspace 目录示例。
3. `doctor` 增加 `/app/static/extensions` 可写检查。
4. `bias-ext-tags` 移除生产代码对 `bias_core.resource_endpoint_runner` 的直接 import，改走公开 facade。
5. `extension-api.md` 增加 legacy runtime facade 标识。
6. `create_extension` 增加 `--template settings` 和 `--template forum-widget` 两个最小模板。

第一批完成后，再推进：

1. 所有官方扩展生产边界检查归零。
2. 前端 SDK export baseline 加稳定性标签。
3. `check_platform_release` 聚合命令。

## 判断标准

下一阶段完成后，应达到以下状态：

1. 新开发者能在不读 core 源码的情况下完成简单扩展。
2. 复杂扩展有清晰进阶路径，不需要直接 import core 内部模块。
3. 安装脚本、README 和实际多仓库依赖一致。
4. 后台启停扩展的错误能被明确诊断。
5. 发布前 gate 能阻断边界违规、依赖缺失、包构建失败和前端 SDK 违规。

