# Bias 拆分完整度评估

> 评估日期：2026-06-25
> 评估对象：`bias_core` / `bias_site` / `bias-ext-users` 三个已拆分产物
> 对照文档：`docs/bias-extension-development-after-split.md`、`docs/bias-independent-package-architecture.md`、`docs/bias-new-project-split-development-plan.md`
> 冻结源（只读参考）：`/mnt/project/code/bias/apps/core/`、`/mnt/project/code/bias/extensions/`

## 总体结论

**骨架已搭起来、主路径能 import，但还没拆干净，也还没拆完。** 三个产物的"形"都有了（包结构、entry points、settings 组装、扩展发现都符合文档），但 `bias_core` 内部有明显的**重复模块未去重**、**核心迁移和测试未补齐**，`bias-ext-users` 的**测试还带着旧仓路径**，部署链路和边界保护也未闭环。按文档的里程碑对照，目前大约在 **M2（bias-core 可加载测试扩展）和 M3（空宿主可运行）之间**，离 M5（第一个真实扩展迁移成功）的验收还有距离。

---

## 一、bias_core —— 后端核心包

### ✅ 已达标
- **包骨架与依赖**：`pyproject.toml` 依赖列表与文档 Phase C0 基本一致，`packages.find where=["src"]` 正确。
- **AppConfig 符合文档**：`apps.py` 里 `name = "bias_core"`、`label = "core"`（Phase C1 / §5 的关键要求），表名/迁移 label 稳定。
- **扩展 SDK 公共导出完整**：`extensions/__init__.py` 导出了文档点名的 `SettingsExtender`、`ApiResourceExtender`、`ResourceDefinition`、`ThemeExtender`（Phase C4.1 主题协议预留）、`PermissionDefinition` 等，且 `extensions/` 子系统与旧仓 `apps/core/extensions/` **1:1 完整复制**（仅多了 `discovery.py`）。
- **配置工具到位**：`conf/bootstrap.py`、`conf/defaults.py`、`conf/extension_discovery.py` 都在，`bias_site/settings.py` 正确通过 `load_site_bootstrap` + `discover_installed_extension_django_apps` 组装。
- **清单项 1/2/3 已补完**：`bias_core/docs/completion-checklist.md` 列的 `registry/` 子包（7 文件齐）、`management/command_utils.py` 都已存在；残留检查 `apps.core` 计数=**0**、`from bias_core.bootstrap_config` 计数=**0**。

### 🔴 仍存在的问题

#### 1. 顶层扁平文件与子目录文件大量重复（最脏的点）
`api/`、`resources/`、`services/` 三个**新建**子目录里的文件，和顶层同名文件**逐字节相同**（不是门面 re-export）：

| 顶层（被实际引用） | 子目录副本（死代码） | diff |
|---|---|---|
| `api_errors.py` | `api/errors.py` | SAME |
| `api.py` | `api/api.py` | SAME |
| `api_runtime.py` | `api/runtime.py` | SAME |
| `auth.py` / `jwt_auth.py` | `api/auth.py` / `api/jwt_auth.py` | SAME |
| `audit.py` | `services/audit.py` | SAME |
| `authorization.py` | `services/authorization.py` | SAME |
| `settings_service.py` | `services/settings.py` | SAME |
| `resource_registry.py` | `resources/registry.py` | SAME |
| `resource_dispatcher.py` | `resources/dispatcher.py` | SAME |
| …还有约 20 对 | | SAME |

实际 import 都走顶层（如 `extensions/__init__.py` 用 `from bias_core.authorization import ...`、`services/audit.py` 自己也 `from bias_core.models import AuditLog`），子目录副本目前**无人引用**。文档（`bias-independent-package-architecture.md` §2/§5）说的是过渡期门面应 **re-export**，不是复制两份。现状是"两份相同实现并存"，改一边忘另一边就会行为分裂。另外还有个 `services_old.py` 是重组残留。`realtime/` 子目录只放了 1 行的 `routing.py` shim、缺 `websocket_auth.py`，也没迁完。

#### 3. 核心测试大量被 `.skip`（行为一致性未验证）
`tests/` 里 **11 个激活 vs 18 个 `.skip`**。被跳过的恰恰是文档 Phase C9 点名要求的核心测试：

```
test_extension_boundary / test_extension_validation / test_extension_registry
test_resource_registry / test_settings_fallback
test_admin_permissions / test_admin_settings_api / test_admin_extensions_api
test_extension_loader / test_extension_middleware / test_extension_policy
test_extension_service / test_extension_commands / test_queue
test_runtime_cache / test_management / test_production_runtime / test_runner
```

这意味着拆分后**没有任何机制保证行为和旧仓一致**——文档"先复制、用测试收敛边界"这条主线没走完。

#### 4. import-linter 边界规则未配置
`pyproject.toml` 声明了 `import-linter` dev 依赖，但**没有 `.importlinter` 配置文件、也没有 `[tool.importlinter]` 段**。文档 Phase C10 / 风险 1 要求的两条硬规则（`bias_core` 不得 import `bias_ext_*`；扩展不得 import `bias_core` 内部模块）没有落地，公共 API 边界目前靠自觉。

### 🟡 小问题
- **版本号三处不一致**：`VERSION`=0.1.0-dev、`pyproject.toml`=0.1.1、提交进 site 的 whl=0.1.1。
- `__init__.py` 仍在用 `default_app_config`（Django 4.2 已移除，靠 `apps.py` 自动发现即可）。

---

## 二、bias_site —— 网站工程

### ✅ 已达标
- Django 配置（`config/settings.py`/`urls.py`/`asgi`/`wsgi`/`celery`）齐全，settings 通过 `bias_core.conf.bootstrap` 组装，INSTALLED_APPS/MIDDLEWARE/TEST_RUNNER 全指向 `bias_core.*`，符合 Phase S1。
- 前端宿主从旧仓完整迁来，`src/` 目录与旧仓 `frontend/src/` **文件一一对应**。
- **主题目录按文档落了**：`frontend/src/theme/default/` 下 `tokens.css`/`forum.css`/`admin.css`/`slots.js` 四件齐，完全符合 Phase S7。
- 扩展加载链路文件（`extensionImportMapPlugin.mjs`、`extensionSdkAliases.mjs`）已迁。

### 🟡 问题
- **前端 SDK 包名未收敛到文档目标**。alias 同时支持 `@bias/core`、`@bias/forum`、`@bias/admin`、`@bias/admin/components` 四套并列包名；文档目标是统一到 `@bias/core/*`（`@bias/core/forum`、`@bias/core/admin`）。`bias-ext-users` 前端实际用的是 `@bias/forum` + `@bias/users`。Phase S4 方案 A 允许先用 alias，但命名空间和目标不一致，将来抽 `@bias/core` 独立包时要回改。
- **部署链路未闭环**：`Dockerfile` 里 `pip install bias-ext-users==0.1.0`（从 pip 源装），但该扩展未发布到任何源，本地 `docker build` 会失败；`bias_core` 靠提交进仓的 `bias_core-0.1.1-py3-none-any.whl` 安装——把构建产物提交进 git 不规范且会过期。
- **`settings.py` 有 `os` 模块级 NameError 隐患**：底部 `ENABLE_DEBUG_TOOLBAR = DEBUG and os.getenv(...)` 用了 `os`，但 `os` 只在 `env_int()` 函数内部 `import` 过，模块级未导入。DEBUG=True 且开启 toolbar 分支时会 `NameError`。
- `config/urls.py` 的 `ExtensionRouter` 用 `importlib.import_module("bias_ext_%s.backend.%s" % ...)` 直接 import 扩展的 router 模块，这与文档"扩展通过 `ApiRoutesExtender` 声明 routes"的机制是**两套并存**，后者才是目标形态。

---

## 三、bias-ext-users —— 第一个扩展

### ✅ 已达标
- 包形态正确：`pyproject.toml` 有 `entry-points."bias.extensions"`、`extension.json` 有 django app_config/backend entry/frontend entry、`apps.py` `name="bias_ext_users.backend"`/`label="users"`。
- 后端文件与旧仓 `extensions/users/backend/` **1:1 齐全**，`django_migrations` 0001+0002 都在。
- `ext.py` 全部用新路径（`bias_core.extensions` / `.platform` / `.runtime` / `.forum`），**无 `apps.core` 残留**。

### 🟡 问题
- **`tests.py` 仍带旧仓路径**（4 处 `apps.core` + 4 处 `extensions.testing`）：
  - `from extensions.testing import ...`（依赖旧仓 `extensions/testing.py`，独立包不该依赖）
  - `patch("apps.core.resource_dispatcher.get_runtime_resource_registry"...)`、`patch("apps.core.extensions.system_runtime...")`、`patch("apps.core.domain_events...")`——这些 mock patch 指向 `apps.core.*`，在 `bias_core` 下**patch 不到目标模块**，测试会失效。
- `ext.py` 的 `FrontendExtender(admin_entry="extensions/users/frontend/admin/index.js", ...)` 用的是旧仓内**源码路径**风格，和 `extension.json` 里的 `frontend/dist/...` **不一致**；测试还断言这个源码路径。说明当前前端 entry 用源码路径加载，与文档"`frontend/dist/forum/index.js`"的产物路径约定不同（可能是阶段选择，但要明确）。
- `extension.json` 缺文档示例里的 `bias` 版本兼容声明（`"bias": {"core": ">=…", "frontend": ">=…"}`），无法做兼容范围校验。
- 前端无 `dist/`（开发态可接受，但 `extension.json` 已指向 dist，需构建步骤补上）。

---

## 四、"是否拆完整"的判断

**没有拆完整。** 按文档里程碑对照：

| 里程碑 | 状态 |
|---|---|
| M1 bias-core 可安装 | ✅ |
| M2 可加载测试扩展 | 🟡 能 import，但核心测试 .skip、未实跑验证 |
| M3 空宿主可运行 | 🟡 settings 组装 OK，但 migrations 缺 0002–0005、`os` bug |
| M4 前端扩展加载跑通 | 🟡 alias 在，但包名未收敛、ext entry 路径不一致 |
| M5 第一个扩展迁移成功 | 🟡 users 代码迁完，但**测试带旧路径会失效**，不算"成功" |
| M6/M7 核心链路 / 替代旧项目 | ❌ posts/discussions/tags… 仍在旧仓（16 个扩展待迁，按文档顺序排在 users 之后） |



---

## 五、建议的修补优先级

1. **去重 `bias_core` 的 `api/`、`resources/`、`services/` 三个子目录副本**：确定主路径（当前是顶层），把子目录改成 re-export 或直接删，消灭两份相同实现。
2. **恢复 `.skip` 的核心测试**：至少先点亮 `test_extension_boundary`、`test_extension_validation`、`test_extension_registry`、`test_resource_registry`、`test_settings_fallback`，否则行为对齐是空话。
3. **修 `bias-ext-users/tests.py` 的旧路径**：`apps.core.*` → `bias_core.*`、`extensions.testing` → `bias_core` 提供的测试 helper，让扩展测试能在新包下跑通。
4. **配 import-linter 规则**（`.importlinter` 或 `[tool.importlinter]`），把文档两条边界变成 CI 硬约束。
5. **闭环部署**：Dockerfile 改成本地 editable/源码安装扩展，或搭私有源；移除提交进仓的 whl；统一版本号。
6. **小修**：`settings.py` 的 `os` import、`__init__.py` 的 `default_app_config`、`extension.json` 加 `bias` 兼容声明。

---

*本评估基于 2026-06-25 的代码快照。`bias_core/docs/completion-checklist.md`（2026-06-22 创建）是此前抽包补全的进行中清单，其中项 1/2/3 已完成、项 4（migrations 0002–0005）仍未完成。*

---

# 二轮复查（2026-06-25，commit `b9e1015` 之后）

> 用户照 eval.md 做了一轮修复（`9af5edd` services 包冲突重命名 + `b9e1015` Fix: eval.md 指出的问题）。以下为复查结果。

## 本轮已修复 ✅

1. **重复副本删除**——`resources/` 13→1、`services/` 16→1、`api/` 顶层 6 个副本（`api.py`/`auth.py`/`errors.py`/`jwt_auth.py`/`runtime.py`/`admin_auth.py`）删除。
2. **版本号统一 0.1.1**——`VERSION`/`pyproject.toml`/`version.py(APP_VERSION)` 三处一致。
3. **import-linter 落地**——`[tool.importlinter]` 两条 forbidden 契约配置完成。
4. **`api.py` → `api_main.py`**——消除包/文件名冲突。
5. **`default_app_config` 变量删除**（`apps.py` 靠 AppConfig 自动发现）。

## 🔴 仍存在的架构问题

### 1. 目录归类方向走偏，停在半成品（最该决策的点）
文档目标是「子目录为主路径 + 顶层 shim 兼容」（§2 / Phase C5-C7），实际做成了**「顶层扁平为主 + 子目录空壳」**：

- `bias_core/resources/` 只剩一句 docstring，文档承诺的 `bias_core.resources.registry` 路径**已不存在**；
- `bias_core/services/` 只剩 docstring + 从 `services_old` 重导出 `PaginationService`；
- `bias_core/api/` 只剩 `admin/` 子目录 + `__init__` re-export `api_runtime`/`api_main`。

调用者看到 `bias_core.resources` 包会以为有实现，import 才发现是空的——**接口不清晰**。必须二选一做到位：
- **方案 A（文档目标）**：把顶层扁平文件真正搬进 `api/`/`resources/`/`services/` 子目录，顶层留 re-export shim 兼容一个大版本后删；
- **方案 B（承认扁平）**：顶层扁平就是最终结构，删掉 `resources/`/`services/`/`api/` 这几个空壳包（或只保留 namespace 用途）。

现在是两边好处都没拿到的中间态，最差。

### 2. `api/admin/` 子目录漏删，仍 1:1 重复顶层
`b9e1015` 删了 `api/` 顶层副本，但漏了 `api/admin/` 下 11 个文件。抽样 6 对全部逐字节 SAME：

```
api/admin/admin_api.py        == admin_api.py
api/admin/admin_audit_api.py  == admin_audit_api.py
api/admin/admin_auth.py       == admin_auth.py
api/admin/admin_content_api.py== admin_content_api.py
api/admin/admin_settings_api.py == admin_settings_api.py
api/admin/admin_stats_api.py  == admin_stats_api.py
```

且 `api/__init__.py` 只 re-export `api_runtime`/`api_main`，根本不碰 `admin/`——纯死代码。

### 4. 核心测试仍 18 个 `.skip`
11 激活 / 18 跳过，`test_extension_boundary`/`test_extension_validation`/`test_extension_registry`/`test_resource_registry`/`test_settings_fallback` 等仍被跳过。行为一致性零验证。

## 🟡 残留小问题

5. **import-linter 规则可绕过**：forbidden 列了 `bias_core.services`（已空壳）和部分 `resource_*`，但顶层 `resource_dispatcher`/`resource_api`/`audit`/`authorization`/`forum_registry` 等真正内部实现路径没列全，扩展可绕过。需把所有「内部」顶层模块补进 forbidden。
6. **`__all__` 残留 `default_app_config`**：变量删了，`__all__ = ["__version__", "default_app_config"]` 仍引用（`hasattr(bias_core,'default_app_config')` = False）。
7. **`services_old.py` 临时命名**：`_old` 后缀不该留在正式架构，`PaginationService` 应有正式归属（如 `services/pagination.py` 或 `platform`）。
8. **`bias-ext-users/tests.py` 仍 8 处旧路径**（`apps.core` / `extensions.testing`），patch 不到 `bias_core` 目标模块，扩展测试跑不通。
9. **`Dockerfile` 未闭环**：仍 `pip install bias-ext-users==0.1.0`（未发布到任何源）+ 提交进仓的 `bias_core-0.1.1-py3-none-any.whl`（354KB）。
10. **`settings.py` 的 `os` bug 仍在**：`os` 只在 `env_int()` 内 import，模块级 `os.getenv`（line 243）会 `NameError`。
11. **前端 SDK 包名未收敛** `@bias/core/*`（仍 `@bias/forum`/`@bias/admin` 并列，未动）。
12. **SDK import 有 settings 副作用**：`from bias_core.extensions import SettingsExtender` 在无 Django settings 的裸进程里报 `ImproperlyConfigured`——导入链在 import 时触发了 settings 访问，限制了「扩展可独立 import SDK」的纯粹性和可测试性，建议查根因（疑似 `authorization` 或某 extender 模块 import 时触发）。

## 更新后的修补优先级

1. **决策目录归类最终方向**（A 搬进子目录 / B 扁平删空壳），并删 `api/admin/` 重复死代码。
3. **恢复 `.skip` 核心测试**（至少 5 个 boundary/validation/registry/resource/settings_fallback）。
4. **收紧 import-linter forbidden 列表**：覆盖所有顶层扁平内部模块，并实跑 `lint-imports` 进 CI。
5. **修 `bias-ext-users/tests.py` 旧路径**：`apps.core.*` → `bias_core.*`、`extensions.testing` → `bias_core` 测试 helper。
6. **小修**：`__all__` 去 `default_app_config`；`services_old` 正式归属；`settings.py` 模块级 `import os`；SDK import 副作用查根因。
7. **闭环部署**：Dockerfile 改本地 editable/源码装扩展或搭私有源；移除进仓 whl。
8. **前端 SDK 包名收敛** `@bias/core/*`。

## 里程碑对照（更新）

| 里程碑 | 状态（二轮后） |
|---|---|
| M1 bias-core 可安装 | ✅ |
| M2 可加载测试扩展 | 🟡 能 import，但 SDK import 有 settings 副作用、核心测试仍 .skip |
| M3 空宿主可运行 | 🟡 settings 组装 OK，但 migrations 缺 0002–0005、`os` bug |
| M4 前端扩展加载跑通 | 🟡 alias 在，但包名未收敛、ext entry 源码路径与文档不一致 |
| M5 第一个扩展迁移成功 | 🟡 users 代码迁完，但测试带旧路径跑不通，不算「成功」 |
| M6/M7 核心链路 / 替代旧项目 | ❌ 16 个扩展仍在旧仓 |

---

*二轮复查基于 2026-06-25 `b9e1015` 之后的代码快照。本轮修掉重复副本/版本号/import-linter 配置/包名冲突/default_app_config 五项；目录归类方向、migrations、核心测试三项为主要剩余缺口。*
