# Bias vs Flarum 架构对比分析

> 分析日期：2026-06-19
> Bias：Django 5 + Vue 3，扩展优先架构
> Flarum：PHP + Mithril.js，Composer 包管理扩展体系

---

## 一、代码规模对比

### 总量

| 维度 | Flarum | Bias | 比例 |
|------|--------|------|------|
| **后端代码**（不含测试/migration） | **66,152 行**（PHP） | **75,110 行**（Python 40,143 + JS/Vue 34,967） | Bias 略大 |
| 后端测试代码 | — | **15,571 行** | Bias 有完整测试 |
| **前端代码** | Mithril.js（含在 PHP 包中） | **33,153 行**（Vue 3 + JS） | Bias 独立前端 |
| **模块数** | 1 core + 19 扩展包 | 1 core + 18 扩展 | 接近 |

### 后端分层

| 层 | Flarum | Bias |
|----|--------|------|
| **Core 逻辑** | `core/src/` = 19 子模块，**39,316 行** | `apps/core/`，**40,143 行** |
| **扩展** | 19 个包，**24,248 行** | 18 个扩展，**34,967 行** |
| **Core 内部** | API(8k) + Extend(3.8k) + Foundation(3k) + Frontend(2.6k) + Http(2.5k) + User(3.7k) + Install(2k) + Discussion(1.7k) + Forum(1.9k) | `apps/core/` 内部模块数量更多但单体更大 |

### 核心模块对比

```
Flarum Core 模块分布                      Bias Core 模块分布
────────────────────                      ────────────────────
Api            8,002 行  (19.4%)          扩展系统(~15k)   (37.5%)
Extend         3,787 行  ( 9.6%)          资源注册(~4k)    (10.0%)
User           3,736 行  ( 9.5%)          middleware        547 行
Foundation     3,070 行  ( 7.8%)          forum_registry    553 行
Frontend       2,606 行  ( 6.6%)          runtime_diag      548 行
Http           2,542 行  ( 6.5%)          settings_svc      589 行
Install        2,062 行  ( 5.2%)          
Extension      2,182 行  ( 5.5%)          
Forum          1,866 行  ( 4.7%)          
Discussion     1,669 行  ( 4.2%)          
Post           1,266 行  ( 3.2%)          
Notification   1,290 行  ( 3.3%)          
Search           997 行  ( 2.5%)          
...
```

---

## 二、架构哲学对比

| 维度 | Flarum | Bias | 评价 |
|------|--------|------|------|
| **扩展机制** | Composer 包 + PHP ServiceProvider | 文件系统扫描 + Python 注册式 Extender | 各有利弊 |
| **扩展边界** | 真正的包边界（Composer autoload） | import-linter 文本规则（~约定~） | Flarum 更强 |
| **API 风格** | JSON:API 规范（通过 `json-api-server` 包 4,963 行实现） | JSON:API 规范（通过 `apps/core/` 自实现） | 方向一致 |
| **认证** | session + 令牌 | JWT（access + refresh cookie）+ Bearer header | Bias 更现代 |
| **ORM** | Laravel Eloquent | Django ORM | 各有优劣 |
| **前端** | Mithril.js（轻量虚拟 DOM） | Vue 3 + Pinia + Vue Router | Bias 更主流 |
| **实时通信** | WebSocket（通过 `realtime` 扩展包 3,631 行） | WebSocket（Channels + 内置 realtime） | 目标一致 |
| **异步任务** | Laravel Queue | Celery | Flarum 原生集成更深 |

---

## 三、关键差异分析

### 1. 扩展系统

**Flarum**：真正的包架构
- 每个扩展是一个 Composer 包，有独立 `composer.json`
- 通过 `composer require flarum/tags` 安装
- 通过 `ServiceProvider::register()` / `boot()` 声明钩子
- `Extend` 模块（3,787 行）定义了 35 个 Extender 类

**Bias**：文件系统扫描架构
- 扩展放在 `extensions/` 目录下，启动时扫描发现
- 通过 `extend()` 函数返回 Extender 列表
- 通过 `ExtensionInstallation` 模型持久化启停状态
- 通过 `reset_extension_runtime_state()` 22 步手动清理

**关键差距**：Flarum 的 Composer 包体系天然解决了以下问题：
- ✅ 版本管理（composer.json + semver）
- ✅ 依赖解析（自动计算依赖树）
- ✅ 第三方发布（通过 Packagist）
- ✅ 真正的类加载隔离（autoload 路径）

Bias 在这些方面全部靠约定而非系统。

### 2. API 层

**Flarum**：
- `Api` 模块 8,002 行，99 个文件，是 core 中最大的模块
- 以 Serializer + Resource 模式组织
- 有独立的 `json-api-server` 包（4,963 行）

**Bias**：
- ResourceRegistry 1,693 行 + resource_objects 856 行 + resource_serializer 338 行 ≈ 2,887 行
- 加上 registry/ 子模块：preload_planner 311 + endpoint_context 421 + resource_validator 338 + definition_mutator 293 + search_bridge 188 + jsonapi_serializer 160 = 1,711 行
- 核心 API 代码约 **4,598 行**

两者都实现了 JSON:API 风格，Bias 的代码更集中，Flarum 更分散。

### 3. 扩展 Backend 规模对比

```
Flarum 扩展              Bias 扩展
─────────────────        ─────────────────
tags       2,184 行      tags       4,289 行  (1.97x)
mentions   1,651 行      mentions     919 行  (0.56x)
likes        470 行      likes        984 行  (2.09x)
flags        648 行      flags      2,165 行  (3.34x)
subscriptions 570 行     subscriptions 726 行  (1.27x)
──────                         ──────
基本功能扩展平均 ~1,105 行      基本功能扩展平均 ~2,617 行

特殊包：                     特殊扩展：
realtime     3,631 行        realtime       790 行
messages     1,635 行        notifications 2,460 行
gdpr         5,495 行        ai              766 行
```

Bias 的 tags、flags、likes 等扩展比 Flarum 大 2-3 倍，主要因为：
- Bias 使用 Django ORM，模型定义 + migration + 序列化代码更多
- Bias 的扩展同时包含前后端（Flarum 前后端分离在不同的包中）
- Bias 有更多的测试代码（统计中已排除测试数据）

### 4. 扩展支持的功能齐全度

| 功能 | Flarum | Bias |
|------|--------|------|
| 审核 | approval (414行) ✅ | approval (2,008行) ✅ |
| AI | ❌ | ai (766行) ✅ **Bias 独有** |
| BBCode | bbcode (107行) ✅ | ❌ **Flarum 独有** |
| Emoji | emoji (40行) ✅ | emoji (154行) ✅ |
| GDPR | gdpr (5,495行) ✅ | ❌ **Flarum 独有** |
| Markdown | markdown (32行) ✅ | ❌ **通过 marked.js 在前端渲染** |
| 昵称 | nicknames (329行) ✅ | ❌（有 display_name） |
| 积分 | ❌ | points (986行) ✅ **Bias 独有** |
| 文件上传 | ❌ | uploads (620行) ✅ **Bias 独有** |
| 安全/验证 | ❌ | security (229行) ✅ **Bias 独有** |
| 实时统计 | statistics (189行) ✅ | ✅（内置于 realtime） |
| 置顶 | sticky (392行) ✅ | ✅（is_sticky 字段） |
| 锁定 | lock (384行) ✅ | ✅（is_locked 字段） |
| 私信 | messages (1,635行) ✅ | ❌ **Flarum 独有** |
| 英文语言包 | lang-english (10行) | ❌（中文为主） |

---

## 四、架构差距总结

### Flarum 做得更好的

1. **包管理** — Composer 体系是真正的包边界，Bias 的文件扫描只是约定
2. **扩展发布** — Flarum 扩展可通过 Packagist 发布，Bias 需要 git 子模块或 pip
3. **核心规模控制** — Flarum 将 JSON:API 协议实现放在独立 `json-api-server` 包中，core 本身的 39k 行对等
4. **扩展粒度** — 将 bbcode、markdown 等小型功能拆成独立包（即使只有 32 行），Bias 倾向于合并到 core

### Bias 做得更好的

1. **现代技术栈** — Python 3 + Django 5 + Vue 3 + JWT
2. **测试覆盖** — Bias 有 15,571 行测试代码，Flarum 没有独立测试目录
3. **安全性** — CSP 头、HttpOnly Cookie、secrets.token_urlsafe、无 `shell=True`
4. **前端架构** — Vue 3 组件化 + Pinia 状态管理，比 Mithril.js 更主流
5. **扩展性基础设施** — 18 个 Extender 类型、ResourceRegistry 门面拆分、forum_registry 注册中心
6. **运行时诊断** — `doctor` 命令、production runtime 检查

### 最关键的架构风险

**Bias 最需要解决的问题不是拆包，而是扩展边界的系统化。** 当前 `extensions/` 有 118 个文件直接 import `apps.core.xxx`，其中 327 次引用 `apps.core.extensions`。这本质上是内部包的非公共 API 依赖。Flarum 通过 Composer 的 autoload 机制和 `Extend` 门面类避免了这个问题。

---

## 五、改进建议（按优先级）

1. **短期（已进行中）**：建立 `apps.public` API 门面层，让扩展只依赖公共接口
2. **中期**：参考 Flarum 的 `Extend/` 模块模式，统一 Extender 接口文档化
3. **长期**：当需要支持第三方扩展时，将扩展机制改为真正的 Python 包（`pyproject.toml` + pip install）而非文件系统扫描
