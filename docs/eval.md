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
