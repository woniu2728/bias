# Bias 扩展开发快速开始

目标：不阅读 Bias 内部源码，也能生成、测试、打包并启用一个扩展。

## 1. 生成扩展

```powershell
cd D:\files\project\tmp\bias
python manage.py create_extension demo-widget --target D:\files\project\tmp --template forum-widget
```

生成目录类似：

```text
D:\files\project\tmp\bias-ext-demo-widget
```

`forum-widget` 模板默认包含：

- `extension.json`
- 后端 `ext.py`
- forum frontend entry
- Python package metadata

其他常用模板：

```powershell
python manage.py create_extension demo-settings --target D:\files\project\tmp --template settings
python manage.py create_extension demo-admin --target D:\files\project\tmp --template admin-page
python manage.py create_extension demo-resource --target D:\files\project\tmp --template resource
python manage.py create_extension demo-full --target D:\files\project\tmp --template full
```

## 2. 校验扩展

```powershell
python manage.py validate_extensions --extensions-path D:\files\project\tmp
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --check-runtime-facades --format json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
```

必须保持：

- 扩展不能 import `bias_core` 内部非公开模块。
- 跨扩展调用必须通过 runtime service contract；不要在新代码里新增旧 `get_runtime_*` / `*_runtime_*` facade 依赖。
- frontend 只能从 `@bias/core` 公开 SDK 导入。

## 3. 安装和启用

```powershell
python manage.py sync_extensions
python manage.py extension_enable demo-widget
python manage.py build_extension_frontend --rebuild
```

如果要发布静态资源：

```powershell
python manage.py build_extension_frontend --rebuild --publish
python manage.py collectstatic --noinput
```

## 4. 打包检查

```powershell
python manage.py check_platform_release --extensions-path D:\files\project\tmp --skip-frontend --format json
python manage.py inspect_extension_packages --extensions-path D:\files\project\tmp --build --install-smoke --install-set-smoke --lifecycle-smoke --format json
```

`check_platform_release` 是后端发布聚合 gate，会汇总 workspace 边界、扩展诊断、包构建、doctor 和前端平台检查。正式发布不应跳过 frontend 或 doctor；本地只验证后端扩展时可临时使用 `--skip-frontend` / `--skip-doctor`。

`inspect_extensions` 的 JSON 输出包含 `compatibility_matrix`，按扩展列出 manifest `schema_version`、Bias 版本范围、API 版本和稳定性、依赖/冲突/能力声明、分发签名/abandoned 状态，以及发布 gate 策略。发布流水线应阻断 `compatibility_matrix.summary.bias_version_incompatible_count > 0` 或 `compatibility_matrix.summary.blocking_count > 0` 的扩展；`prepare_release` 已内置同一阻断检查。

JSON 输出中的 `install_plan` 是安装前计划，不会执行真实站点安装；它列出扩展依赖顺序、wheel 构建/选择、archive inspection、install smoke、install-set smoke、migration smoke 和 lifecycle smoke 步骤，并标记 `executes_install=false`。`upgrade_risk` 是升级前风险摘要，包含 Bias 版本兼容、缺失依赖、依赖环、experimental/beta API 和 abandoned distribution 等风险；发布流水线应阻断 `blocking_risk_count > 0` 的扩展，`prepare_release` 已内置同一阻断检查。

正式发布时，`prepare_release` 会执行同一包审计并追加 `--migration-smoke --lifecycle-smoke`，因此扩展必须能通过迁移 smoke 和 enable/disable 生命周期 smoke。

## 5. 后端 API 边界

详细参考见 [extension-api.md](extension-api.md)。

优先使用公开包：

- `bias_core.extensions.runtime`
- `bias_core.extensions.platform`
- `bias_core.extensions.resources`
- `bias_core.extensions.notifications`
- `bias_core.extensions.permissions`

不要从其他扩展直接 import model/service。需要能力时声明 service contract，并通过 `get_runtime_service()` 或 `call_runtime_service()` 获取。

旧的专用 runtime facade 只保留兼容期入口，例如 `get_runtime_user_by_id`、`notify_runtime_notification`、`get_runtime_tag_service`。新扩展和新功能不要继续使用这些入口；迁移映射见 `docs/developer/runtime-facade-migration.md`。

## 6. 前端 SDK 边界

详细参考见 [frontend-injection-points.md](frontend-injection-points.md)。

优先从以下入口导入：

- `@bias/core`
- `@bias/core/common`
- `@bias/core/forum`
- `@bias/core/admin`
- `@bias/core/components/admin`

新增注入点、admin page、forum widget、resource normalizer 时，优先使用 `extendForum` / `extendAdmin` 和 registry slot，不要修改宿主内部组件。

## 7. 发布前检查清单

```powershell
python manage.py check_platform_release --extensions-path D:\files\project\tmp --format json
python manage.py inspect_extensions --contract-baseline-only --output extension-contract-baseline.json
python manage.py check_extension_workspace --extensions-path D:\files\project\tmp --format json
python manage.py inspect_performance_baseline --format json --strict

cd D:\files\project\tmp\bias\frontend
npm run check:platform
npm run build
```

发布前必须补齐扩展自己的后端测试和前端 smoke 测试。

## 8. 示例扩展

仓库内提供 6 个可参考的最小示例：

- `bias-ext-demo-settings`
- `bias-ext-demo-resource`
- `bias-ext-demo-forum-widget`
- `bias-ext-demo-admin-page`
- `bias-ext-demo-notification`
- `bias-ext-demo-upload`

这些示例只使用公开后端 SDK 和 `@bias/core/*` 前端 SDK，可作为新增扩展的起点。
