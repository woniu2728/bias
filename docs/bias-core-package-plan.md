# `bias_core` 独立成包 + 第三方扩展支持方案

> 目标：将 `apps.core` 独立为 pip 包 `bias_core`，其 `bias_core.extensions` 子模块作为扩展的公共 SDK

---

## 一、正确的关系

```
第三方扩展 → pip install bias_core → from bias_core.extensions import SettingsExtender
内置扩展   → 同仓库 → from apps.core.extensions import ... → 也改为 from bias_core.extensions import ...

apps.core/ 成为 bias_core/ 的内部实现细节
bias_core.extensions/ 是稳定的公共 API（SDK）
```

**这和拆 bias_sdk 和 bias_core 两个包不同**——只有一个包 `bias_core`：
- `bias_core` = 整个 `apps.core`（~40k 行 Python 代码）
- `bias_core.extensions` = 扩展 SDK（105+ 个公共符号）
- 第三方扩展 `pip install bias_core`，`from bias_core.extensions import xxx`

---

## 二、现状确认

### apps/core 依赖的外部包

```
django, ninja, ninja_jwt, channels, asgiref, django_redis
```

都不算重型依赖——Django 是 web 框架，ninja 是 API 框架，channels 是 WebSocket，django_redis 是缓存后端。

### apps/core 内部构成

| 类别 | 行数 | 是否属于公共 API |
|------|------|-----------------|
| `extensions/`（扩展系统 + SDK） | ~15k | 部分（extenders/types = SDK） |
| `resource_registry.py` + 相关 | ~4k | 否（内部实现） |
| `forum_registry.py` + 相关 | ~1k | 否 |
| `models.py` | ~80行 | 是（Setting/AuditLog/ExtensionInstallation） |
| `jwt_auth.py` / middleware.py | ~0.6k | 否（框架组件） |
| 管理命令 | ~2k | 否 |
| 其他零散模块 | ~5k | 混合 |

**核心问题**：`apps.core` 不是"纯 SDK"——它是完整的 Django 应用 + 扩展引擎 + API 框架。把它做成 pip 包意味着：

1. `bias_core` 依赖 Django —— 安装 bias_core 就会拉 Django
2. `bias_core` 需要 Django settings 配置才能工作
3. 第三方扩展只使用 `bias_core.extensions`（SDK 部分），但也得安装完整 Django

---

## 三、方案

### 核心思路

**`bias_core` 是一个完整的 Django app 包**，它包含了 SDK（`bias_core.extensions`）和所有内部实现。

```
bias_core/                    ← pip install bias_core
├── __init__.py
├── pyproject.toml            # name="bias-core", install_requires=["django>=5.0", ...]
│
├── extensions/               ← SDK（稳定的公共 API）
│   ├── __init__.py           # 导出所有 Extender、类型、辅助函数
│   ├── extenders/            # Extender 实现
│   ├── types.py              # 定义类型
│   ├── ...                   # SDK 部分（~15k 行中的一部分）
│
├── resource_registry.py      ← 内部实现（不导出）
├── forum_registry.py
├── middleware.py
├── jwt_auth.py
├── models.py
├── management/
└── ...
```

### 安装方式

```bash
# 安装 bias_core
pip install bias-core

# 创建 Django 项目（Bias 主项目）
django-admin startproject my_bias_site
cd my_bias_site
```

### 第三方扩展

第三方扩展只需在 `pyproject.toml` 声明：
```toml
[project]
dependencies = ["bias-core>=2.0"]
```

扩展代码：
```python
# my_extension/ext.py
from bias_core.extensions import (
    SettingsExtender,
    ServiceProviderExtender,
    setting_field,
)

def extend():
    return [
        SettingsExtender(fields=(setting_field(...),)),
        ServiceProviderExtender(key="my.service", provider=...),
    ]
```

---

## 四、实施路线图

### Phase 1：SDK 层稳定化（当前批次）

| 步骤 | 描述 | 改动 |
|------|------|------|
| 1 | 确认 `bias_core.extensions.__init__` 的导出范围 | 收集当前所有 105+ 个符号 |
| 2 | 给 Exporter 加 `@public_api` 标记或 `__sdk__` 白名单 | 定义什么算稳定 |
| 3 | 写 `test_sdk_exports.py` 验证所有导出可导入 | 测试 |
| 4 | 给 `apps/core` 加 `pyproject.toml` | 定义包名、版本、依赖 |
| 5 | CI 中 publish bias-core 到 PyPI | 发布脚本 |

### Phase 2：内置扩展迁移

| 步骤 | 描述 | 改动 |
|------|------|------|
| 6 | 内置扩展改为 `from bias_core.extensions import ...` | 18 个 `ext.py` |
| 7 | 添加 `from apps.core.extensions import ...` 兼容导入（可选） | 过渡期 |
| 8 | `config/settings.py` 改为固定的 `INSTALLED_APPS`，不再动态扫描 | 系统配置 |

### Phase 3：完全独立包

| 步骤 | 描述 |
|------|------|
| 9 | 在单独仓库中创建 `bias-core` 包，从当前仓库同步 |
| 10 | 内置扩展也独立为 pip 包（`bias-ext-discussions` 等） |
| 11 | 前端编译系统适配 pip 安装的扩展 |

---

## 五、关键问题

### Q1：`config/settings.py` 怎么办？

当前 `config/settings.py` 直接 import `apps.core` 内部模块。独立包后：
- `bias_core` 提供一个 `bias_core.settings.base` 或 `bias_core.conf.get_settings()`
- 用户项目的 `settings.py` 继承自 `bias_core.settings.base`
- 或者直接使用 `bias_core` 提供的默认配置

### Q2：开发体验变差了吗？

本地开发仍然使用 `apps/` 目录结构不变：
```python
# extensions/discussions/backend/ext.py
# 本地开发时：
from apps.core.extensions import SettingsExtender
# 改为：
from bias_core.extensions import SettingsExtender

# 本地通过 pip install -e 或 PYTHONPATH 指向 apps/
# 两种方式都指向同一份代码
```

### Q3：什么时候真的拆仓库？

三个条件同时满足时：
1. 有第三方扩展发布到 PyPI
2. 核心开发者有独立的 release 节奏需求
3. 构建/CI 时间过长

在此之前：**`bias_core` 和 Bias 主项目在同一个仓库**，`pyproject.toml` 描述包信息，CI 同步发布到 PyPI。
