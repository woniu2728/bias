# 待推进的复杂优化项

> 以下事项已评估，但需要更深入的架构讨论或较大的重构工作量。
> 标注了风险等级、预估工作量、建议方案，供决策参考。

---

## 🔴 待修复缺陷（2026-06-17 第三轮评估发现，非"可选优化"）

> 这些是已确认或疑似的缺陷，区别于下文的"可选优化"，建议优先处理。

### D1. flag 删除回归 — 删除举报对所有人失效 (P1，会让 CI 红灯)
- **现状**: `extensions/flags/backend/services.py:151` `delete_post_flags` 校验 `admin.flag.delete`，但该权限**从未注册**——`extensions/flags/backend/ext.py` 只注册 `admin.flag.view`(:151) 与 `admin.flag.resolve`(:160)；`handlers.py:152` 的 `admin.flag.delete` 只是审计日志 action 名，不是权限。
- **影响**: 权限不可授予，`has_runtime_forum_permission(user,"admin.flag.delete")` 恒 False。实测 `test_staff_can_delete_post_flags_through_flags_extension_endpoint` 返回 403「无权查看举报」(应 204)，flags 测试 3 红 → `python manage.py test` / CI 失败。
- **方案**(二选一): ① 在 `ext.py` 注册 `admin.flag.delete` 权限并加入默认管理/版主组 + 测试 setup 授予 + 错误文案改"无权删除举报"；② 退回使用已注册的写权限 `admin.flag.resolve`。
- **风险**: 低　**预估**: 0.5 天

### D2. superuser 护栏 staff/superuser 语义不符 (P3)
- **现状**: `extensions/users/backend/admin_api.py` `update_admin_user` 新增护栏查 `User.objects.filter(is_staff=True)`（最后一个 **staff**），但错误文案写"不能移除最后一位**超级管理员**(superuser)"；且只在 payload 改 `is_staff` 时触发，改 `is_superuser` 不受约束，`delete_admin_user` 路径也未覆盖。
- **影响**: 实现护的是 staff，文案/意图是 superuser，二者不一致。
- **方案**: 按 `is_superuser` 判定并覆盖删除路径，或将文案改为"管理员(staff)"以对齐实现。
- **风险**: 低　**预估**: 0.5 天　（原 #10 已部分实现，本条为遗留语义问题）

### D3. forgot_password 邮件失败处理 — 已落地，留小尾巴 (P3)
- **现状**: `extensions/users/backend/services.py` 已加 `logger.warning` 且生产仍 raise（原 #9 已实现）。
- **小尾巴**: `import logging` 写在函数体内，建议提到模块级。
- **风险**: 极低　**预估**: 5 分钟

### D4. 疑似既有测试失败 — 待确认是否环境性 (P2，待确认)
- **现象**: `extensions.users.backend.tests.AdminMailTestEmailApiTests.test_mail_*` 4 个失败 + flags `test_inspect_reports_flags_model_as_extension_native`、`test_flag_visibility_uses_post_view_private_scoper` 2 个失败。
- **分析**: 均在第二轮(fd37ca0)diff 范围之外（不碰被改的行），按代码范围推断非本次引入；mail 类疑似 `instance/site.json` 配了真实 SMTP 后端导致测试环境发信失败。
- **待办**: bisect 确认是否环境性；若属代码缺陷需单独立项。

---

## 架构拆分（高风险，大工作量）

### 1. ResourceRegistry 上帝类拆分 (P1)
- **现状**: `apps/core/resource_registry.py` 单类 163 方法 / 2750 行
- **方案**: 拆为 RegistryStore / Validator / JsonApiSerializer / PreloadPlanner / SearchBridge
- **风险**: 高（内部调用链复杂，需要保持 API 兼容）
- **预估**: 3-5 天
- **详细方案**: 见文末 **附录 A**

### 2. admin_extension_detail.py 拆分 (P1)
- **现状**: 1864 行 / 70 个模块级函数
- **方案**: 按子域拆分：前端路由 / 权限矩阵 / 设置 / 主题 / 调试
- **风险**: 中（函数间耦合度低于 ResourceRegistry）
- **预估**: 1-2 天
- **详细方案**: 见文末 **附录 B**

### 3. RuntimeServiceProxy 落地使用 (P2)
- **现状**: `runtime_core.py` 已定义 `RuntimeServiceProxy` 但无消费方
- **方案**: 逐步替换 runtime_*.py 中的简单转发函数为代理调用
- **风险**: 低（API 兼容，渐进式替换）
- **预估**: 1 天

### 13. 扩展框架物理隔离为独立包 (P2)
- **现状**: 整个扩展框架与论坛领域代码混居 `apps/core/extensions/`（~90 个 .py，含 `manager.py` 56KB、`application.py` 46KB），框架边界仅靠约定 + import 校验，无物理隔离与独立版本号，core 业务改动易波及框架稳定性
- **方案**: 抽为同仓独立包（如 `bias_extension_framework/`），独立测试集 + 框架版本号 + `import-linter` 强制单向边界
- **风险**: 高（文件多、互依赖深、被广泛 import；为所有重构中最重一项）
- **预估**: 5-8 天（建议排在 #3 RuntimeServiceProxy 收敛与论坛领域下沉之后）
- **详细方案**: 见文末 **附录 C**

---

## 性能优化

### 4. 全文搜索 GIN 索引 (P1)
- **现状**: `extensions/search/backend/services.py` 用 `SearchVector(...)` 实时算 `to_tsvector`，无 `GinIndex`
- **方案**: 加 `SearchVectorField` + `GinIndex`，或 PG 函数索引
- **风险**: 中（需要数据库迁移、验证查询计划）
- **预估**: 1-2 天

### 5. web 多 worker + LocMem 不一致报警 (P2)
- **现状**: gunicorn 2 worker，无 Redis 时限流/在线状态/缓存不一致
- **方案**: `doctor` 在"生产+多worker+LocMem"组合显式报警
- **风险**: 低
- **预估**: 0.5 天

---

## 安全加固

### 6. JWT 吊销机制 (P2)
- **现状**: 无 blacklist/rotation，登出仅清 cookie
- **方案**: token_blacklist app + token version
- **风险**: 中（影响登录态管理，需兼容现有 token）
- **预估**: 1-2 天

### 7. /api/search 路由层 viewForum 闸门 (P2)
- **现状**: 匿名可搜索，仅靠逐行可见性兜底
- **方案**: 路由层加论坛查看权限门槛
- **风险**: 低
- **预估**: 0.5 天

### 8. 限流 check/record 非原子 TOCTOU (P3)
- **现状**: `auth_rate_limit.py` check 和 record 之间有竞态窗口
- **方案**: 用 Redis Lua 脚本或 `cache.incr` 原子化
- **风险**: 低
- **预估**: 0.5 天

### 9. forgot_password 吞掉邮件发送失败 (P3) — ✅ 已实现（见 D3 小尾巴）
- **现状**: 邮件发送失败仍返回"已发送"
- **方案**: 捕获异常并返回具体错误
- **风险**: 低
- **预估**: 0.5 天

### 10. admin_user 最后 superuser 护栏 (P3) — ⚠️ 部分实现（语义瑕疵见 D2）
- **现状**: 无"保留最后一个超级管理员"检查
- **方案**: `update_admin_user`/`delete_admin_user` 加检查
- **风险**: 低
- **预估**: 0.5 天

---

## 整洁度

### 11. Runtime_* facade 样板收敛 (P2)
- **现状**: 约 116 个薄封装转发函数，与 SDK 重复
- **方案**: 用 RuntimeServiceProxy 逐步收敛
- **风险**: 低
- **预估**: 1 天

### 12. SDK 文件重复 (P3)
- **现状**: 17 个扩展中 9 个 `frontend/forum/sdk.js` 与 `nodeSdk.js` 完全相同
- **方案**: 单一 `sdk.js` + 打包层约定
- **风险**: 中（影响前端构建）
- **预估**: 1 天

---

---

## 附录 A：ResourceRegistry 拆分详细方案

> 目标：把 `apps/core/resource_registry.py` 的 163 方法上帝类拆成若干高内聚协作者，由一个**薄 Facade `ResourceRegistry`** 组合；对外公共面（`get_resource_registry()` 单例、`reset_resource_registry_state()` 及现有公共方法签名）完全不变，外部调用方零改动。

### A.1 目标分层与方法归属（按现有方法实测归类）

| 目标模块 | 职责 | 归入的现有方法（节选，均来自实测符号表） |
| --- | --- | --- |
| **RegistryStore**`registry_store.py` | 唯一持有可变状态 + 注册 + 查询 + 启用判定 + 可见性谓词 | `__init__` 的全部 `_definitions/_resource_objects/_fields/_field_mutators/_relationships/_endpoints/_sorts/_filters/_core_endpoint_keys/_resolved_resource_cache/_resource_modifiers/_enabled_module_ids_cache`；`register_resource/_object/_modifier`、`reset_resource_modifiers`、`clear_resource_modifier_cache`、`_clear_resource_object_resolve_caches`、`register_field/relationship/endpoint/core_endpoint/_register_endpoint/field_mutator/sort/filter`；`get_resource/_object/resolve_resource/get_resources`、`get_fields/effective/all`、`get_field_mutators/all`、`get_relationships/effective/all`、`get_endpoints/all`、`get_filters/effective/all`、`get_sorts/effective/all`、`get_dispatch_endpoint(s)`；`_get_enabled_module_ids/_invalidate_enabled_module_ids_cache/_is_module_enabled`；可见性谓词 `_is_applicable/_is_field_visible/_is_relationship_visible/_is_relationship_includable/_is_filter_visible/_is_field_writable` |
| **DefinitionMutator**`definition_mutator.py` | 扩展驱动的定义改写/合并 | `apply_field_definitions/apply_sort_definitions/apply_endpoint_definitions/apply_endpoint_mutators`；`_field/_relationship/_sort/_filter/_external_sort_mutator_result`、`_mutator_kind`、`_sort_definition_value`；`_is_*_definition_like`(field/sort/relationship/filter/resource)、`_is_resource_definition_mutation`；`_item_name/_insert_before/_insert_after/_find_item_index/_endpoint_definition_matches/_mutate_endpoint_definition`、`_normalize_endpoint_*`、`_endpoint_operation/_endpoint_registration_key`；`_*_to_definition`、`_resolve_resource_items`、`_resource_fields/relationships/endpoints/sorts/filters`、`_set_resource_value` |
| **ResourceValidator**`resource_validator.py` | 校验流水线 | `_run_extension_validators/_run_validation_factory/_build_validation_payload/_collect_validation_rules/_collect_validation_state/_merge_definition_validation_state/_invoke_validation_factory_object/_validator_errors/_collect_payload_validation_errors/_validation_error_to_document/_normalize_validation_factory_errors/_validate_resource_value/_validate_resource_rule/_validate_named_resource_rule/_validation_pointer/_deserialize_resource_value/apply_payload_field_mutators` |
| **JsonApiSerializer**`jsonapi_serializer.py` | 序列化 + JSON:API 文档拼装 | `serialize/serialize_jsonapi_document/serialize_jsonapi_resource/_serialize_jsonapi_resource_internal/_serialize_plain_relationship/_serialize_plain_related_item`；`_set_jsonapi_value/_set_jsonapi_relationship/_add_jsonapi_included/_relationship_linkage/_relationship_values/_resource_identifier(_payload)/_resource_self_link/_resolve_related_resource_type/_resolve_jsonapi_deferred/_is_jsonapi_identifier`；`_build_include_tree/_flatten_include_tree/_prefix_prefetch` |
| **PreloadPlanner**`preload_planner.py` | 预加载计划 | `build_preload_plan/build_endpoint_preload_plan/build_endpoint_definition_preload_plan/apply_preload_plan/_merge_preload_definition/_prefetch_key` |
| **SearchBridge**`search_bridge.py` | 资源搜索桥接 | `_search_resource_index/_runtime_search_manager/_sync_resource_filters_to_search_manager/_register_search_filter/_normalize_search_result/_invoke_resource_searcher/_apply_default_fulltext_filter` |
| **EndpointContextResolver**`endpoint_context_resolver.py` | 端点上下文解析（兼修 round1 "ResourceEndpointRunner 泄漏式抽取"） | `dispatch_resource_endpoint`、`_resolve_endpoint_include/sort/filters/pagination`、`_call_endpoint_before/after`、`_resolve_endpoint_meta/links`、`_merge_endpoint_document_meta_links`、`_ensure_resource_ability`、`_parse_non_negative_int`；`apply_resource_payload/apply_resource_filters/apply_named_sort/has_named_sort/_sort_order_fields/_extract_relationship_payload`、`_parse_jsonapi_data/_extract_resource_payload` |

### A.2 先决清理
- **删除死代码 `_dispatch_index/_dispatch_show/_dispatch_create/_dispatch_update/_dispatch_delete`**（约 133 行，`resource_registry.py:1044-1173`）。grep 确认实际分发走 `dispatch_resource_endpoint → ResourceEndpointRunner`，这 5 个方法无调用方。删除前再次确认无反射/字符串调用。

### A.3 迁移步骤（每步保持测试全绿，建议逐 PR）
1. 删 A.2 死代码（隔离、零风险，立竿见影瘦身）。
2. 抽 **PreloadPlanner**、**SearchBridge**（最自包含、跨依赖最少），registry 改为委托。
3. 抽 **JsonApiSerializer**（依赖 store 的 getter + 可见性谓词 → 以 store 作为协作者注入，不复制状态）。
4. 抽 **ResourceValidator**。
5. 抽 **EndpointContextResolver**，并让 `ResourceEndpointRunner` 依赖它而非 `registry._resolve_*` 私有方法 —— 同时关闭 round1 的"泄漏式抽取/双向耦合"。
6. 抽 **DefinitionMutator**。
7. 剩余即 **RegistryStore**；把 `ResourceRegistry` 收敛为薄 Facade，逐方法委托，保留全部公共签名。

### A.4 兼容与风险
- **公共面冻结**：`ResourceRegistry` 类名、`get_resource_registry()`、`reset_resource_registry_state()` 及现有公共方法保持不变；内部组合协作者。
- **单一状态源**：可变状态只留在 RegistryStore，协作者无状态、以 store 为入参；缓存失效（`_invalidate_enabled_module_ids_cache` 等）统一回调 store。
- **隐藏顺序依赖**（注册 → 缓存失效）：迁移前先把私有依赖显式化为接口（store getter + 可见性谓词对象）。
- **验证**：以 `apps/core/tests/test_resource_registry.py`(4703 行) 为安全网，每步必跑；对 serialize/dispatch 输出补特征化测试以防回归。
- **工作量**：3–5 天，按"一协作者一 PR"渐进推进。

---

## 附录 B：admin_extension_detail.py 拆分详细方案

> 目标：把 ~70 函数 / 1864 行拆进包 `apps/core/extension_detail/`，对外稳定入口 `serialize_admin_extension` / `serialize_admin_extensions_payload` 不变。

### B.1 目标模块与函数归属（按实测符号表）

| 目标文件 | 职责 | 归入的现有函数（节选） |
| --- | --- | --- |
| `__init__.py` | 稳定 API 再导出（顺带收敛 round1 的"三跳 shim"） | `serialize_admin_extension`、`serialize_admin_extensions_payload` |
| `orchestrator.py` | 编排/装配 | `_serialize_admin_extension`(161-395 的 234 行装配器)、`_serialize_admin_extension_summary`、`_serialize_admin_extensions_payload`、`_serialize_admin_extension_action_payload`、`_serialize_extension_admin_actions`、`_build_default_extension_admin_actions`、`_resolve_extension_runtime_record`、`_serialize_extension_recovery_status`、`_resolve_api_stability_label`、`_resolve_distribution_channel_label` |
| `models.py`（最大簇，~21 个） | 模型与迁移分析 | `_build_extension_model_definitions/_owned_models/_model_ownership_audit/_model_relations/_model_visibility`、`_resolve_display_model`、`_model_name/_label/_module/_app_label/_db_table/_storage_origin`、`_extension_app_label(_source)`、`_model_package_migration_required/_model_app_label_migration_required/_model_migration_risk/_model_migration_recommended_steps/_build_model_app_label_migration_item`、`_serialize_extension_migration_plan/_execution` |
| `resources.py` | 资源面 | `_build_extension_resource_definitions/relationships/endpoints/sorts/filters/fields`、`_build_extension_search_drivers/_search_filters` |
| `forum_domain.py` | 论坛领域面（亦为 round1 "core 去论坛化"的物理隔离第一步） | `_build_extension_discussion_list_filters/_discussion_sorts/_post_types/_post_lifecycle/_notification_types/_user_preferences/_event_listeners/_realtime_broadcasts/_language_packs` |
| `permissions.py` | 权限矩阵 | `_build_extension_permission_sections/_summary/_modules`、`_flatten_extension_permissions`、`_build_extension_admin_page_details` |
| `frontend.py` | 前端/路由/交付 | `_build_extension_frontend_routes/_frontend_document`、`_resolve_extension_frontend_outputs/_forum_entry/_admin_entry`、`_resolve_extension_settings_pages/_permissions_pages/_operations_pages`、`_build_runtime_surface_view`、`_build_extension_delivery_assets` |
| `settings_theme.py` | 设置/主题运行时 | `_build_extension_settings_runtime/_theme_runtime/_system_hooks`、`_serialize_extension_backend_hooks`、`_build_extension_capability_summary` |
| `debug.py` | 调试诊断 | `_build_extension_debug_info`(142 行)、`_serialize_debug_value`、`_serialize_extension_runtime_rebuild_state`、`_serialize_extension_frontend_asset_state_for_extension` |
| `_shared.py` | 公共助手 | `_serialize_callable_or_value`；并把 `_serialize_debug_value` 与 `extensions` 侧 `frontend_serialization.serialize_frontend_value` 合并为单一 `serialize_value(value, *, none_as=...)`（round1 重复实现 #8） |

### B.2 迁移步骤
1. 建包，先迁叶子簇 `models.py`/`debug.py`/`permissions.py`（互相依赖少），orchestrator 改为 import。
2. 迁 `resources.py`/`forum_domain.py`/`frontend.py`/`settings_theme.py`。
3. 把 orchestrator 收敛为纯装配。
4. 收敛"三跳 shim"：`extension_serialization → admin_content_api → admin_extension_detail` 改为调用方直接 import `extension_detail` 包；`extension_serialization` 留作弃用再导出或删除。
5. 合并 `_serialize_debug_value` 与 `serialize_frontend_value` 进 `_shared.py`。

### B.3 兼容与风险
- 入口 `serialize_admin_extension(s)_payload` 签名不变；其余下划线函数为模块私有，迁移安全。
- **迁移前先 grep 下划线私有函数的跨模块/测试 import**（重点 `apps/core/tests/test_admin_extensions_api.py` 816 行是否引用私有），有引用则同步更新。
- 风险：中（多为纯函数 builder，耦合低于 ResourceRegistry）。工作量：1–2 天。
- 验证：`apps/core/tests/test_admin_extensions_api.py` + 扩展详情相关测试。

---

## 附录 C：扩展框架物理隔离为独立包 详细方案

> 来源：optimization-plan.md 1.6（本文档此前遗漏，现补入）。目标：把 `apps/core/extensions/` 中**可复用的扩展内核**抽成同仓独立包（如仓库根 `bias_extension_framework/` 或 `packages/bias-extension-framework/`），具备独立测试集、独立框架版本号、强制的单向 API 边界，使 core/论坛业务的改动不再波及框架稳定性。

### C.1 现状与问题
- `apps/core/extensions/` 约 90 个模块、合计 ~400KB，既含**框架内核**（加载、manifest、校验、生命周期、恢复、扩展点机制、前端编译、IoC 容器、版本兼容），又含**论坛领域绑定**（`runtime_posts/tags/discussions/users/moderation/notifications`、`forum.py`、`application_forum.py`、`extenders_forum_admin.py`）。
- 边界仅靠约定与 import 校验，没有物理隔离、没有独立版本号；框架与业务双向可见，core 业务改动可能破坏框架稳定性。

### C.2 候选边界划分（须以 C.3 依赖审计校准，下表为按文件名初判）

| 分类 | 候选模块 |
| --- | --- |
| **框架内核（移入新包）** | 加载/生命周期: `module_loader, lifecycle, bootstrap, bootstrap_state, signal_bootstrap, signal_runtime`；manifest/校验: `manifest, admin_manifest, validation, validation_manifest, validation_rules, validation_source, validation_inspection, validation_types, contracts, compatibility_guard, version_compatibility`；扩展点机制: `extenders, extender_helpers, extender_values, definition_assembler, site_extenders, extenders_runtime, extenders_resources, extenders_routes_policy, extenders_system, extenders_model_search, extenders_frontend`；装配/IoC: `container, application*, assembly_service, product, registry, backend, sdk`；运行时基建: `extension_runtime, system_runtime, runtime, runtime_probe, runtime_services, runtime_service, runtime_access, runtime_models, runtime_search, recovery`；前端管线: `frontend_compiler, frontend_runtime_service, frontend_serialization, application_frontend, assets, admin_assets, template_loader`；迁移/事件/杂项基建: `migrations, migration_repository, model_references, application_models, events, event_bus, application_events, application_event_helpers, exceptions, types, application_types, formatter_service, locale_service, manager*, module_extension_view, platform` |
| **论坛领域绑定（留业务侧 / 下沉扩展）** | `runtime_posts, runtime_tags, runtime_discussions, runtime_users, runtime_moderation, runtime_notifications`（与 #3 RuntimeServiceProxy 同源）、`forum.py, application_forum.py, extenders_forum_admin.py`、可能含 `application_search.py` |
| **待定（依赖审计判定）** | `runtime_core.py, runtime_event_listeners, settings_runtime_service, policy_runtime_service` 等可能含领域泄漏 |

> 精确归属必须以 C.3 依赖审计为准。框架隔离与"论坛领域下沉"是同一枚硬币的两面：若不先剥离领域绑定，会把业务代码错带进框架。

### C.3 分阶段方案（每阶段保持测试绿，多 PR）
1. **依赖审计（先决）**: 用 `import-linter` 或 `pydeps`/`grep` 构建 `apps/core/extensions/*` 的模块依赖图，给每个模块打标 framework/domain/glue，列出**非法边**（framework → domain、framework → `apps.core` 业务）。这是定边界的事实依据。
2. **就地立边界（先不挪文件）**: 把框架对外**公共 API 收敛到单一门面**（即现有 SDK 面：`sdk.py`/`platform.py` 暴露的契约），并在 CI 加 `import-linter` 合同禁止 framework → domain/business；用依赖倒置消除违例（框架定义 `Protocol`/hook，领域注册进去）。
3. **领域剥离**: 把论坛领域绑定迁出框架候选集到业务/论坛扩展层（与 #3、论坛领域下沉协同），使框架候选集变为领域无关。
4. **物理抽包**: 框架内核迁到仓库根独立包（如 `bias_extension_framework/`），`apps/core/extensions/` 保留**薄再导出 shim** 维持现有 import 路径，平滑过渡。
5. **独立版本号 + 独立测试集 + CI job**: 新包带 `__version__`/框架 API 版本（接入现有 `version_compatibility` 与 manifest 的框架版本校验）；把 `test_extension_loader/_middleware` 等框架测试迁入新包独立运行。
6. **翻转 import、移除 shim**: 全仓 import 切到新包路径，删除过渡 shim。

### C.4 兼容与风险
- **公共面冻结**: 17 个扩展通过 SDK（`apps.core.extensions.sdk` / `platform`）接入，整个过渡期保持该 import 路径稳定（靠 shim）。
- **边界守护**: `import-linter` 合同进 CI，防止隔离后被业务"反向 import"再次污染——这是隔离能长期成立的关键。
- **风险**: 高——90 文件、`manager.py`(56KB)/`application.py`(46KB) 体量大、互依赖深、被广泛引用，是所有重构里最重的一项。
- **排序建议**: 放在 #3 RuntimeServiceProxy 收敛与论坛领域下沉之后；与附录 A/B 不冲突，可在其后推进。
- **验证**: 新包独立测试集 + `import-linter` 边界合同 + 现有 `apps/core/tests/test_extension_loader.py`(3842)/`test_extension_middleware.py`(1361) 作为安全网。
- **工作量**: 5–8 天，强制多 PR、每步可回滚。

---

*创建于：2026-06-17，基于 round2.md 第二轮评估*
