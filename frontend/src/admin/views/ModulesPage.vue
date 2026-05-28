<template>
  <AdminPage
    class-name="ModulesPage"
    icon="fas fa-cubes"
    :title="modulesCopy?.pageTitle || '模块中心'"
    :description="modulesCopy?.pageDescription || '围绕注册中心查看模块边界、依赖健康、扩展注入面与后台入口。'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">{{ modulesCopy?.loadingText || '加载模块信息中...' }}</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>
    <div v-else class="ModulesPage-content">
      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.moduleListTitle || '模块列表' }}</h3>
          <p>{{ modulesCopy?.moduleListDescription || '这里展示内置模块注册结果。当前重点是注册覆盖面、依赖健康和后台接入，不再只是静态清单。' }}</p>
        </div>

        <div v-if="routeBackTarget || focusedModule" class="ModulesPage-contextBar">
          <router-link v-if="routeBackTarget" :to="routeBackTarget" class="ModulesPage-contextBack">
            <i class="fas fa-arrow-left"></i>
            <span>{{ routeBackLabel }}</span>
          </router-link>
          <p v-if="focusedModule" class="ModulesPage-contextHint">
            当前已聚焦模块
            <strong>{{ focusedModule.name }}</strong>
            <code>{{ focusedModule.id }}</code>
          </p>
        </div>

        <div class="ModulesPage-overview">
          <div class="ModulesPage-overviewStats">
            <span class="ModulesPage-overviewItem">
              <strong>{{ summary?.module_count ?? modules.length }}</strong>
              <span>{{ modulesCopy?.moduleCountLabel || '已注册模块' }}</span>
            </span>
            <span class="ModulesPage-overviewItem">
              <strong>{{ summary?.enabled_count ?? modules.filter(item => item.enabled).length }}</strong>
              <span>{{ modulesCopy?.enabledStatusLabel || '已启用' }}</span>
            </span>
            <span class="ModulesPage-overviewItem">
              <strong>{{ moduleAttentionCount }}</strong>
              <span>{{ modulesCopy?.runtimeDependencyWarningLabel || '需关注' }}</span>
            </span>
          </div>
          <div v-if="overviewHighlights.length" class="ModulesPage-overviewAlerts">
            <article
              v-for="highlight in overviewHighlights"
              :key="highlight.key"
              class="ModulesPage-overviewAlert"
            >
              <strong>{{ highlight.title }}</strong>
              <p>{{ highlight.description }}</p>
            </article>
          </div>
        </div>

        <AdminToolbar class="ModulesPage-toolbar" align="between">
          <div class="ModulesPage-toolbarGroup">
            <AdminFilterTabs v-model="categoryFilter" :options="categoryFilterOptions" />
            <AdminFilterTabs v-model="statusFilter" :options="statusFilterOptions" />
          </div>
          <label class="ModulesPage-search">
            <span class="sr-only">{{ modulesCopy?.searchLabel || '搜索模块' }}</span>
            <input
              v-model.trim="searchQuery"
              class="FormControl"
              type="search"
              :placeholder="modulesCopy?.searchPlaceholder || '搜索模块名、ID、能力或依赖'"
            />
          </label>
        </AdminToolbar>

        <div v-if="displayedModules.length" class="ModuleShelf">
          <article
            v-for="module in displayedModules"
            :key="module.id"
            class="ModuleRow"
            :class="{ 'is-expanded': isModuleExpanded(module.id), 'is-attention': moduleNeedsAttention(module) }"
          >
            <div class="ModuleRow-main">
              <button
                type="button"
                class="ModuleRow-expander"
                :aria-expanded="isModuleExpanded(module.id)"
                @click="toggleModuleExpand(module.id)"
              >
                <i class="fas fa-chevron-right"></i>
              </button>

              <span class="ModuleRow-icon" :class="module.is_core ? 'ModuleRow-icon--core' : 'ModuleRow-icon--feature'">
                <i :class="resolveModuleIcon(module)"></i>
              </span>

              <div class="ModuleRow-content">
                <div class="ModuleRow-titleLine">
                  <h4>{{ module.name }}</h4>
                  <span class="ModuleBadge" :class="module.is_core ? 'ModuleBadge--core' : 'ModuleBadge--feature'">
                    {{ module.is_core ? (modulesCopy?.coreCategoryLabel || '核心') : module.category_label }}
                  </span>
                  <span
                    v-if="moduleNeedsAttention(module)"
                    class="ModuleStatus ModuleStatus--warning"
                  >
                    {{ moduleAttentionLabel(module) }}
                  </span>
                </div>

                <p class="ModuleRow-description">{{ module.description }}</p>

                <div class="ModuleRow-meta">
                  <span><strong>{{ modulesCopy?.versionLabel || '版本' }}</strong> {{ module.version }}</span>
                  <span v-if="module.dependencies.length"><strong>{{ modulesCopy?.dependenciesLabel || '依赖' }}</strong> {{ formatPreviewList(module.dependencies, 3) }}</span>
                  <span v-if="module.settings?.groups?.length"><strong>{{ modulesCopy?.settingsGroupLabel || '设置组' }}</strong> {{ formatPreviewList(module.settings.groups, 1) }}</span>
                  <span><strong>{{ modulesCopy?.bootModeLabel || '启动方式' }}</strong> {{ module.runtime?.boot_mode_label || modulesCopy?.staticBootModeLabel || '静态注册' }}</span>
                </div>

                <div v-if="buildModuleInlineStats(module).length" class="ModuleRow-stats">
                  <span
                    v-for="item in buildModuleInlineStats(module)"
                    :key="`${module.id}-${item.label}`"
                    class="ModuleRow-stat"
                  >
                    <strong>{{ item.value }}</strong>
                    <span>{{ item.label }}</span>
                  </span>
                </div>

                <div v-if="module.missing_dependencies.length || module.disabled_dependencies.length || module.health_issues.length" class="ModuleRow-warningLine">
                  <span v-if="module.missing_dependencies.length">
                    {{ modulesCopy?.missingDependenciesPrefix || '缺少依赖' }}: {{ formatPreviewList(module.missing_dependencies, 3) }}
                  </span>
                  <span v-else-if="module.disabled_dependencies.length">
                    {{ modulesCopy?.disabledDependenciesPrefix || '未启用依赖' }}: {{ formatPreviewList(module.disabled_dependencies, 3) }}
                  </span>
                  <span v-else-if="module.health_issues.length">
                    {{ module.health_issues[0] }}
                  </span>
                </div>
              </div>

              <div class="ModuleRow-actions">
                <span class="ModuleStatus" :class="module.enabled ? 'ModuleStatus--enabled' : 'ModuleStatus--disabled'">
                  {{ module.enabled ? (modulesCopy?.enabledStatusLabel || '已启用') : (modulesCopy?.disabledStatusLabel || '未启用') }}
                </span>
                <router-link
                  v-if="resolveModulePrimaryTarget(module)"
                  class="ModuleActionLink ModuleActionLink--primary"
                  :to="resolveModulePrimaryTarget(module)"
                >
                  {{ resolveModulePrimaryLabel(module) }}
                </router-link>
                <a
                  v-else-if="module.documentation_url"
                  class="ModuleActionLink ModuleActionLink--primary"
                  :href="module.documentation_url"
                >
                  {{ modulesCopy?.documentationEntryActionLabel || '模块文档' }}
                </a>

                <button type="button" class="ModuleActionLink" @click="toggleModuleExpand(module.id)">
                  {{ isModuleExpanded(module.id) ? '收起详情' : '查看详情' }}
                </button>
              </div>
            </div>

            <div v-if="isModuleExpanded(module.id)" class="ModuleRow-panel">
              <div class="ModuleRow-panelGrid">
                <section class="ModulePanelCard">
                  <h5>{{ modulesCopy?.lifecycleTitle || '生命周期' }}</h5>
                  <dl class="ModulePanelMeta">
                    <div class="ModulePanelMeta-row">
                      <dt>{{ modulesCopy?.readinessProbeLabel || '就绪判定' }}</dt>
                      <dd>{{ module.runtime?.readiness_probe || module.lifecycle?.readiness_probe || (modulesCopy?.noValueText || '无') }}</dd>
                    </div>
                    <div class="ModulePanelMeta-row">
                      <dt>{{ modulesCopy?.lifecycleLabel || '生命周期' }}</dt>
                      <dd>{{ formatLifecycleLabels(module) }}</dd>
                    </div>
                    <div class="ModulePanelMeta-row">
                      <dt>{{ modulesCopy?.supportsDisableLabel || '可停用' }}</dt>
                      <dd>{{ module.lifecycle?.supports_disable ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</dd>
                    </div>
                    <div class="ModulePanelMeta-row">
                      <dt>{{ modulesCopy?.supportsTeardownLabel || '可回收' }}</dt>
                      <dd>{{ module.lifecycle?.supports_teardown ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</dd>
                    </div>
                  </dl>
                </section>

                <section class="ModulePanelCard">
                  <h5>{{ modulesCopy?.adminEntriesTitle || '后台入口' }}</h5>
                  <ul v-if="module.admin_pages.length" class="ModuleCompactList">
                    <li v-for="page in module.admin_pages" :key="`${module.id}-${page.path}`">
                      <router-link :to="page.path">{{ page.label }}</router-link>
                      <small>{{ page.path }}</small>
                    </li>
                  </ul>
                  <p v-else class="ModuleEmpty">{{ modulesCopy?.noAdminEntriesText || '暂无后台入口' }}</p>
                </section>

                <section class="ModulePanelCard">
                  <h5>{{ modulesCopy?.settingsRuntimeTitle || '设置与运行时' }}</h5>
                  <div class="ModulePanelSummary">
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.settingsGroupItemLabel || '设置组' }}</span>
                      <strong>{{ module.settings?.groups?.length ? formatPreviewList(module.settings.groups, 3) : (modulesCopy?.noValueText || '无') }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.configuredKeyCountLabel || '已配置键' }}</span>
                      <strong>{{ module.settings?.configured_key_count ?? 0 }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.migrationStatusLabel || '迁移状态' }}</span>
                      <strong>{{ module.runtime?.migration_label || (modulesCopy?.noValueText || '无') }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.documentationLabel || '文档' }}</span>
                      <strong>{{ module.documentation_url ? '可查看' : (modulesCopy?.noValueText || '无') }}</strong>
                    </div>
                  </div>
                </section>

                <section class="ModulePanelCard">
                  <h5>{{ modulesCopy?.permissionsTitle || '权限注册' }}</h5>
                  <div class="ModulePanelSummary">
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.permissionsTitle || '权限注册' }}</span>
                      <strong>{{ formatPreviewList(module.permissions.map(item => item.label || item.code), 3) }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.notificationTypesTitle || '通知类型' }}</span>
                      <strong>{{ formatPreviewList(module.notification_types.map(item => item.label || item.code), 3) }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.resourceFieldsTitle || '资源字段' }}</span>
                      <strong>{{ formatPreviewList(module.resource_fields.map(item => `${item.resource}.${item.field}`), 2) }}</strong>
                    </div>
                    <div class="ModulePanelSummary-row">
                      <span>{{ modulesCopy?.eventListenersTitle || '事件监听' }}</span>
                      <strong>{{ module.event_listeners.length ? `${module.event_listeners.length} 项` : (modulesCopy?.noValueText || '无') }}</strong>
                    </div>
                  </div>
                </section>
              </div>

              <div v-if="module.capabilities.length" class="ModuleTokens">
                <span v-for="capability in module.capabilities" :key="`${module.id}-${capability}`" class="ModuleToken">
                  {{ capability }}
                </span>
              </div>
            </div>
          </article>
        </div>
        <AdminStateBlock v-else tone="subtle">{{ modulesCopy?.emptyFilteredModulesText || '当前筛选下没有匹配的模块。' }}</AdminStateBlock>
      </section>

      <details class="ModulesPage-archive">
        <summary class="ModulesPage-archiveSummary">
          <span>开发快照</span>
          <small>保留模块注册明细，默认收起</small>
        </summary>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.adminEntriesSectionTitle || '后台注册入口' }}</h3>
          <p>{{ modulesCopy?.adminEntriesSectionDescription || '按当前筛选结果列出后台页面，便于检查导航是否已经真正从模块注册元数据派生。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.adminPageHeader || '页面' }}</th>
                <th>{{ modulesCopy?.pathHeader || '路径' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.navSectionHeader || '导航分组' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="page in filteredAdminPages" :key="page.path">
                <td>
                  <router-link :to="page.path">{{ page.label }}</router-link>
                </td>
                <td><code>{{ page.path }}</code></td>
                <td>{{ moduleNameMap[page.module_id] || page.module_id }}</td>
                <td>{{ page.nav_section === 'core' ? (modulesCopy?.coreNavLabel || '核心') : (modulesCopy?.featureNavLabel || '功能') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.notificationEventsSectionTitle || '通知类型与事件监听' }}</h3>
          <p>{{ modulesCopy?.notificationEventsSectionDescription || '用于校验模块通知协议和领域事件挂接是否持续沿统一机制注册。' }}</p>
        </div>

        <div class="ModulesPage-grid ModulesPage-grid--secondary">
          <article class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>{{ modulesCopy?.notificationTypesCardTitle || '通知类型' }}</h4>
                </div>
                <p>{{ modulesCopy?.notificationTypesCardDescription || '所有已在注册中心声明的站内通知类型。' }}</p>
              </div>
            </div>

            <ul v-if="filteredNotificationTypes.length" class="ModuleList ModuleList--dense">
              <li v-for="notificationType in filteredNotificationTypes" :key="notificationType.code">
                <code>{{ notificationType.code }}</code>
                <span>{{ notificationType.label }}</span>
                <small>{{ moduleNameMap[notificationType.module_id] || notificationType.module_id }}</small>
              </li>
            </ul>
            <p v-else class="ModuleEmpty">{{ modulesCopy?.noNotificationTypesText || '暂无通知类型' }}</p>
          </article>

          <article class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>{{ modulesCopy?.notificationRenderersCardTitle || '通知渲染器' }}</h4>
                </div>
                <p>{{ modulesCopy?.notificationRenderersCardDescription || '当前前端已注册的通知展示与跳转 renderer。' }}</p>
              </div>
            </div>

            <ul v-if="filteredNotificationRenderers.length" class="ModuleList ModuleList--dense">
              <li v-for="renderer in filteredNotificationRenderers" :key="`${renderer.module_id}:${renderer.code}`">
                <code>{{ renderer.code }}</code>
                <span>{{ renderer.label }}</span>
                <small>{{ moduleNameMap[renderer.module_id] || renderer.module_id }} · {{ renderer.navigation_scope }}</small>
              </li>
            </ul>
            <p v-else class="ModuleEmpty">{{ modulesCopy?.noNotificationRenderersText || '暂无通知渲染器' }}</p>
          </article>

          <article class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>{{ modulesCopy?.eventListenersCardTitle || '事件监听器' }}</h4>
                </div>
                <p>{{ modulesCopy?.eventListenersCardDescription || '当前模块通过事件总线挂接的监听入口。' }}</p>
              </div>
            </div>

            <ul v-if="filteredEventListeners.length" class="ModuleList ModuleList--dense">
              <li
                v-for="listener in filteredEventListeners"
                :key="`${listener.event}:${listener.listener}:${listener.module_id}`"
              >
                <code>{{ listener.event }}</code>
                <span>{{ listener.listener }}</span>
                <small>{{ moduleNameMap[listener.module_id] || listener.module_id }}</small>
              </li>
            </ul>
            <p v-else class="ModuleEmpty">{{ modulesCopy?.noEventListenersCardText || '暂无事件监听器' }}</p>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.languagePacksSectionTitle || '语言包注册' }}</h3>
          <p>{{ modulesCopy?.languagePacksSectionDescription || '列出模块通过注册中心声明的语言包，作为阶段 6 国际化准备的最小快照。' }}</p>
        </div>

        <table class="AdminTable">
          <thead>
            <tr>
              <th>{{ modulesCopy?.nameHeader || '名称' }}</th>
              <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
              <th>{{ modulesCopy?.defaultHeader || '默认' }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="languagePack in filteredLanguagePacks" :key="`${languagePack.module_id}:${languagePack.code}`">
              <td><code>{{ languagePack.code }}</code></td>
              <td>{{ languagePack.native_label ? `${languagePack.native_label} (${languagePack.label})` : languagePack.label }}</td>
              <td>{{ moduleNameMap[languagePack.module_id] || languagePack.module_id }}</td>
              <td>{{ languagePack.is_default ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.userPreferencesSectionTitle || '用户偏好注册' }}</h3>
          <p>{{ modulesCopy?.userPreferencesSectionDescription || '这里检查模块是否通过统一注册协议声明通知和个性化偏好，而不是散落在页面局部状态中。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.preferenceKeyHeader || '偏好键' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.preferenceCategoryHeader || '分类' }}</th>
                <th>{{ modulesCopy?.preferenceDefaultHeader || '默认值' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="preference in filteredUserPreferences" :key="`${preference.module_id}:${preference.key}`">
                <td><code>{{ preference.key }}</code></td>
                <td>{{ moduleNameMap[preference.module_id] || preference.module_id }}</td>
                <td><code>{{ preference.category }}</code></td>
                <td>{{ preference.default_value ? (modulesCopy?.enabledToggleText || '开启') : (modulesCopy?.disabledToggleText || '关闭') }}</td>
                <td>{{ preference.description || preference.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.postTypesSectionTitle || '帖子类型注册' }}</h3>
          <p>{{ modulesCopy?.postTypesSectionDescription || '用于承接系统事件帖、状态变更帖和普通回复的统一协议。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.postTypeCodeHeader || '类型' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.capabilitiesHeader || '能力' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="postType in filteredPostTypes" :key="`${postType.module_id}:${postType.code}`">
                <td><code>{{ postType.code }}</code></td>
                <td>{{ moduleNameMap[postType.module_id] || postType.module_id }}</td>
                <td>{{ formatPostTypeCapabilities(postType) }}</td>
                <td>{{ postType.description || postType.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.resourceFieldsSectionTitle || '资源字段注册' }}</h3>
          <p>{{ modulesCopy?.resourceFieldsSectionDescription || '汇总 Discussion、Post、Tag、Search 等资源上的扩展字段，作为统一 Resource 协议快照。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.resourceHeader || '资源' }}</th>
                <th>{{ modulesCopy?.fieldHeader || '字段' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="resourceField in filteredResourceFields"
                :key="`${resourceField.resource}:${resourceField.field}:${resourceField.module_id}`"
              >
                <td><code>{{ resourceField.resource }}</code></td>
                <td><code>{{ resourceField.field }}</code></td>
                <td>{{ moduleNameMap[resourceField.module_id] || resourceField.module_id }}</td>
                <td>{{ resourceField.description || modulesCopy?.resourceFieldFallbackText || '已注册资源扩展字段' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.searchFiltersSectionTitle || '搜索过滤器注册' }}</h3>
          <p>{{ modulesCopy?.searchFiltersSectionDescription || '列出模块通过注册中心声明的搜索过滤语法，帮助检查搜索扩展点的覆盖度。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.syntaxHeader || '语法' }}</th>
                <th>{{ modulesCopy?.targetHeader || '目标资源' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="searchFilter in filteredSearchFilters"
                :key="`${searchFilter.module_id}:${searchFilter.target}:${searchFilter.code}`"
              >
                <td><code>{{ searchFilter.syntax || searchFilter.code }}</code></td>
                <td><code>{{ searchFilter.target }}</code></td>
                <td>{{ moduleNameMap[searchFilter.module_id] || searchFilter.module_id }}</td>
                <td>{{ searchFilter.description || searchFilter.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.discussionSortsSectionTitle || '讨论排序注册' }}</h3>
          <p>{{ modulesCopy?.discussionSortsSectionDescription || '列出模块通过注册中心声明的讨论列表排序能力，便于检查论坛首页和标签页的扩展面。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.sortCodeHeader || '排序码' }}</th>
                <th>{{ modulesCopy?.nameHeader || '名称' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.defaultHeader || '默认' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="discussionSort in filteredDiscussionSorts"
                :key="`${discussionSort.module_id}:${discussionSort.code}`"
              >
                <td><code>{{ discussionSort.code }}</code></td>
                <td>{{ discussionSort.label }}</td>
                <td>{{ moduleNameMap[discussionSort.module_id] || discussionSort.module_id }}</td>
                <td>{{ discussionSort.is_default ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</td>
                <td>{{ discussionSort.description || discussionSort.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.discussionListFiltersSectionTitle || '讨论列表过滤注册' }}</h3>
          <p>{{ modulesCopy?.discussionListFiltersSectionDescription || '列出模块通过注册中心声明的讨论列表过滤能力，帮助检查首页、关注页和用户列表是否正在共用统一协议。' }}</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>{{ modulesCopy?.filterCodeHeader || '过滤码' }}</th>
                <th>{{ modulesCopy?.nameHeader || '名称' }}</th>
                <th>{{ modulesCopy?.moduleHeader || '归属模块' }}</th>
                <th>{{ modulesCopy?.requiresAuthHeader || '需登录' }}</th>
                <th>{{ modulesCopy?.defaultHeader || '默认' }}</th>
                <th>{{ modulesCopy?.descriptionHeader || '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="discussionListFilter in filteredDiscussionListFilters"
                :key="`${discussionListFilter.module_id}:${discussionListFilter.code}`"
              >
                <td><code>{{ discussionListFilter.code }}</code></td>
                <td>{{ discussionListFilter.label }}</td>
                <td>{{ moduleNameMap[discussionListFilter.module_id] || discussionListFilter.module_id }}</td>
                <td>{{ discussionListFilter.requires_authenticated_user ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</td>
                <td>{{ discussionListFilter.is_default ? (modulesCopy?.yesText || '是') : (modulesCopy?.noText || '否') }}</td>
                <td>{{ discussionListFilter.description || discussionListFilter.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      </details>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'
import api from '../../api'
import { getResolvedNotificationTypes } from '../../forum/notificationTypes'
import {
  buildExtensionDetailRouteTarget,
  buildExtensionRouteTarget,
  resolveExtensionNavigationSource,
} from '../extensions/diagnostics'
import {
  getAdminModulesPageActionMeta,
  getAdminModulesPageConfig,
  getAdminModulesPageCopy,
} from '../registry'

const route = useRoute()
const loading = ref(true)
const errorMessage = ref('')
const summary = ref({})
const modules = ref([])
const categorySummaries = ref([])
const dependencyAttention = ref([])
const adminPages = ref([])
const notificationTypes = ref([])
const languagePacks = ref([])
const notificationRenderers = computed(() => {
  const moduleIdsByCode = Object.fromEntries(
    notificationTypes.value.map(item => [item.code, item.module_id])
  )

  return getResolvedNotificationTypes()
    .map(item => {
      const code = String(item.type || item.code || item.key || '').trim()
      const moduleId = normalizeModuleId(item.moduleId || item.module_id || moduleIdsByCode[code])
      if (!code || !moduleId) {
        return null
      }

      return {
        code,
        label: item.label || code,
        module_id: moduleId,
        icon: item.icon || 'fas fa-bell',
        navigation_scope: item.navigationScope || item.navigation_scope || 'notifications',
        group_label: item.groupLabel || '',
      }
    })
    .filter(Boolean)
})
const userPreferences = ref([])
const eventListeners = ref([])
const postTypes = ref([])
const resourceFields = ref([])
const searchFilters = ref([])
const discussionSorts = ref([])
const discussionListFilters = ref([])
const categoryFilter = ref('all')
const statusFilter = ref('all')
const searchQuery = ref('')
const expandedModuleIds = ref([])
const modulesCopy = computed(() => getAdminModulesPageCopy())
const modulesConfig = computed(() => getAdminModulesPageConfig())
const modulesActionMeta = computed(() => getAdminModulesPageActionMeta())

const categoryFilterOptions = computed(() => {
  const base = [modulesConfig.value?.categoryFilterBase || { value: 'all', label: '全部分类', icon: 'fas fa-layer-group' }]
  return base.concat(
    categorySummaries.value.map(category => ({
      value: category.id,
      label: category.label,
      icon: category.id === 'core'
        ? (modulesConfig.value?.coreCategoryIcon || 'fas fa-shield-alt')
        : (modulesConfig.value?.featureCategoryIcon || 'fas fa-puzzle-piece'),
    }))
  )
})

const statusFilterOptions = computed(() => modulesConfig.value?.statusFilterOptions || [])

const filteredModules = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  return modules.value.filter(module => {
    if (categoryFilter.value !== 'all' && module.category !== categoryFilter.value) {
      return false
    }

    if (statusFilter.value === 'healthy' && module.health_status !== 'healthy') {
      return false
    }
    if (statusFilter.value === 'attention' && module.health_status === 'healthy') {
      return false
    }
    if (statusFilter.value === 'enabled' && !module.enabled) {
      return false
    }

    if (!keyword) {
      return true
    }

    const haystacks = [
      module.name,
      module.id,
      module.description,
      ...module.capabilities,
      ...module.dependencies,
      ...module.permissions.map(item => item.code),
      ...module.admin_pages.map(item => item.path),
      ...module.notification_renderers.map(item => item.code),
      ...module.notification_renderers.map(item => item.label),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystacks.includes(keyword)
  })
})

const displayedModules = computed(() => (
  [...filteredModules.value].sort((left, right) => {
    const leftAttention = moduleNeedsAttention(left) ? 0 : 1
    const rightAttention = moduleNeedsAttention(right) ? 0 : 1
    if (leftAttention !== rightAttention) return leftAttention - rightAttention
    if (Boolean(left.enabled) !== Boolean(right.enabled)) return left.enabled ? -1 : 1
    if (Boolean(left.is_core) !== Boolean(right.is_core)) return left.is_core ? -1 : 1
    return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
  })
))

const filteredModuleIds = computed(() => new Set(filteredModules.value.map(item => item.id)))
const runtimeDependencyModules = computed(() => (
  filteredModules.value.filter(module => module.runtime_dependency_summary?.status !== 'healthy')
))

const filteredAdminPages = computed(() => adminPages.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredNotificationTypes = computed(() => notificationTypes.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredNotificationRenderers = computed(() => notificationRenderers.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredLanguagePacks = computed(() => languagePacks.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredUserPreferences = computed(() => userPreferences.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredEventListeners = computed(() => eventListeners.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredPostTypes = computed(() => postTypes.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredResourceFields = computed(() => resourceFields.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredSearchFilters = computed(() => searchFilters.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredDiscussionSorts = computed(() => discussionSorts.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredDiscussionListFilters = computed(() => discussionListFilters.value.filter(item => filteredModuleIds.value.has(item.module_id)))

const moduleAttentionCount = computed(() => displayedModules.value.filter(moduleNeedsAttention).length)

const overviewHighlights = computed(() => {
  const items = []

  if (dependencyAttention.value.length) {
    const firstIssue = dependencyAttention.value[0]
    items.push({
      key: `dependency-${firstIssue.module_id}`,
      title: firstIssue.module_name,
      description: firstIssue.missing?.length
        ? `${modulesCopy.value?.missingDependenciesPrefix || '缺少依赖'}: ${firstIssue.missing.join('、')}`
        : `${modulesCopy.value?.disabledDependenciesPrefix || '未启用依赖'}: ${(firstIssue.disabled || []).join('、')}`,
    })
  }

  if (runtimeDependencyModules.value.length) {
    const firstRuntimeModule = runtimeDependencyModules.value[0]
    items.push({
      key: `runtime-${firstRuntimeModule.id}`,
      title: firstRuntimeModule.name,
      description: firstRuntimeModule.runtime_dependency_summary?.issues?.[0]
        || firstRuntimeModule.health_issues?.[0]
        || (modulesCopy.value?.runtimeDependencyDescription || '存在运行依赖健康风险'),
    })
  }

  return items.slice(0, 2)
})

const moduleNameMap = computed(() => Object.fromEntries(modules.value.map(item => [item.id, item.name])))
const focusedModuleId = computed(() => normalizeModuleId(route.query.module))
const focusedModule = computed(() => {
  if (!focusedModuleId.value) {
    return null
  }
  return modules.value.find(item => item.id === focusedModuleId.value) || null
})
const routeSource = computed(() => resolveExtensionNavigationSource(route))
const routeBackTarget = computed(() => {
  if (routeSource.value !== 'extensions') {
    return ''
  }

  const extensionId = normalizeModuleId(route.query.extension)
  if (extensionId) {
    return buildExtensionDetailRouteTarget(extensionId, {
      query: {
        from: 'extensions',
      },
    })
  }

  return buildExtensionRouteTarget('/admin/extensions', 'extensions')
})
const routeBackLabel = computed(() => (
  normalizeModuleId(route.query.extension) ? '返回扩展详情' : '返回扩展中心'
))

function resolveCategoryLabel(category) {
  if (category === 'core') return modulesCopy.value?.coreCategoryLabel || '核心'
  if (category === 'infrastructure') return '基础设施'
  return '功能模块'
}

function normalizeModuleId(value) {
  return String(value || '').trim()
}

function normalizeModule(module) {
  const moduleId = normalizeModuleId(module.id)
  return {
    ...module,
    category_label: module.category_label || resolveCategoryLabel(module.category),
    capabilities: module.capabilities || [],
    dependencies: module.dependencies || [],
    permissions: module.permissions || [],
    admin_pages: module.admin_pages || [],
    notification_types: module.notification_types || [],
    notification_renderers: notificationRenderers.value.filter(item => item.module_id === moduleId),
    language_packs: module.language_packs || [],
    user_preferences: module.user_preferences || [],
    event_listeners: module.event_listeners || [],
    post_types: module.post_types || [],
    resource_fields: module.resource_fields || [],
    search_filters: module.search_filters || [],
    discussion_sorts: module.discussion_sorts || [],
    discussion_list_filters: module.discussion_list_filters || [],
    missing_dependencies: module.missing_dependencies || [],
    disabled_dependencies: module.disabled_dependencies || [],
    dependency_status: module.dependency_status || 'healthy',
    dependency_status_label: module.dependency_status_label || '依赖正常',
    registration_counts: module.registration_counts || {},
    health_issues: module.health_issues || [],
    health_status: module.health_status || 'healthy',
    health_status_label: module.health_status_label || '健康',
    runtime_dependency_summary: module.runtime_dependency_summary || null,
    settings: module.settings || { groups: [], group_count: 0, configured_key_count: 0, has_settings: false },
    lifecycle: module.lifecycle || { phases: [], supports_disable: false, supports_teardown: false, readiness_probe: '' },
    runtime: module.runtime || {},
    documentation_url: module.documentation_url || '',
  }
}

function syncRouteModuleFocus() {
  const targetModuleId = normalizeModuleId(route.query.module)
  if (!targetModuleId) {
    return
  }

  const matchedModule = modules.value.find(item => item.id === targetModuleId)
  if (!matchedModule) {
    return
  }

  searchQuery.value = matchedModule.name || matchedModule.id
  categoryFilter.value = matchedModule.category || 'all'
  statusFilter.value = 'all'
  if (!expandedModuleIds.value.includes(targetModuleId)) {
    expandedModuleIds.value = [...expandedModuleIds.value, targetModuleId]
  }
}

onMounted(async () => {
  await loadModules()
  syncRouteModuleFocus()
})

watch(
  () => route.query.module,
  () => {
    syncRouteModuleFocus()
  }
)

async function loadModules() {
  loading.value = true
  errorMessage.value = ''

  try {
    const data = await api.get('/admin/modules')
    summary.value = data.summary || {}
    categorySummaries.value = data.category_summaries || []
    dependencyAttention.value = data.dependency_attention || []
    adminPages.value = data.admin_pages || []
    notificationTypes.value = data.notification_types || []
    languagePacks.value = data.language_packs || []
    modules.value = (data.modules || []).map(normalizeModule)
    userPreferences.value = data.user_preferences || []
    eventListeners.value = data.event_listeners || []
    postTypes.value = data.post_types || []
    resourceFields.value = data.resource_fields || []
    searchFilters.value = data.search_filters || []
    discussionSorts.value = data.discussion_sorts || []
    discussionListFilters.value = data.discussion_list_filters || []
  } catch (error) {
    console.error('加载模块信息失败:', error)
    errorMessage.value = error.response?.data?.error || modulesActionMeta.value?.loadErrorText || '加载模块信息失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function toggleModuleExpand(moduleId) {
  expandedModuleIds.value = expandedModuleIds.value.includes(moduleId)
    ? expandedModuleIds.value.filter(item => item !== moduleId)
    : [...expandedModuleIds.value, moduleId]
}

function isModuleExpanded(moduleId) {
  return expandedModuleIds.value.includes(moduleId)
}

function moduleNeedsAttention(module) {
  return (
    module.dependency_status !== 'healthy'
    || module.health_status !== 'healthy'
    || module.missing_dependencies.length > 0
    || module.disabled_dependencies.length > 0
    || module.health_issues.length > 0
  )
}

function moduleAttentionLabel(module) {
  if (module.health_status !== 'healthy') {
    return module.health_status_label || modulesCopy.value?.runtimeDependencyWarningLabel || '需关注'
  }
  return module.dependency_status_label || modulesCopy.value?.runtimeDependencyWarningLabel || '需关注'
}

function resolveModuleIcon(module) {
  if (module.is_core) return 'fas fa-shield-alt'
  if (module.category === 'infrastructure') return 'fas fa-server'
  if (module.category === 'moderation') return 'fas fa-gavel'
  if (module.category === 'communication') return 'fas fa-bell'
  return 'fas fa-puzzle-piece'
}

function formatPreviewList(items, limit = 3) {
  if (!Array.isArray(items) || !items.length) {
    return modulesCopy.value?.noValueText || '无'
  }

  if (items.length <= limit) {
    return items.join('、')
  }

  return `${items.slice(0, limit).join('、')} 等 ${items.length} 项`
}

function buildModuleInlineStats(module) {
  const counts = module.registration_counts || {}
  return [
    { label: '权限', value: counts.permissions ?? module.permissions?.length ?? 0 },
    { label: '后台页', value: counts.admin_pages ?? module.admin_pages?.length ?? 0 },
    { label: '通知', value: counts.notification_types ?? module.notification_types?.length ?? 0 },
    { label: '字段', value: counts.resource_fields ?? module.resource_fields?.length ?? 0 },
  ].filter(item => Number(item.value) > 0)
}

function resolveModulePrimaryTarget(module) {
  const settingsPath = String(module.runtime?.settings_entry_path || '').trim()
  if (settingsPath) {
    return buildExtensionRouteTarget(settingsPath, {
      query: {
        from: 'modules',
        module: module.id,
      },
    })
  }

  const permissionsPath = String(module.runtime?.permissions_entry_path || '').trim()
  if (permissionsPath) {
    return buildExtensionRouteTarget(permissionsPath, {
      query: {
        from: 'modules',
        module: module.id,
      },
    })
  }

  const operationsPath = String(module.runtime?.operations_entry_path || '').trim()
  if (operationsPath) {
    return buildExtensionRouteTarget(operationsPath, {
      query: {
        from: 'modules',
        module: module.id,
      },
    })
  }

  const detailPath = String(module.runtime?.detail_entry_path || module.extension?.action_links?.detail_page || '').trim()
  if (!detailPath) {
    return ''
  }

  return buildExtensionRouteTarget(detailPath, {
    query: {
      from: 'modules',
      module: module.id,
    },
  })
}

function resolveModulePrimaryLabel(module) {
  if (String(module.runtime?.settings_entry_path || '').trim()) {
    return modulesCopy.value?.settingsEntryActionLabel || '配置入口'
  }
  if (String(module.runtime?.permissions_entry_path || '').trim()) {
    return modulesCopy.value?.permissionsEntryActionLabel || '权限入口'
  }
  if (String(module.runtime?.operations_entry_path || '').trim()) {
    return '操作入口'
  }
  return '扩展详情'
}

function formatPostTypeCapabilities(postType) {
  const labels = []
  if (postType.is_default) labels.push(modulesCopy.value?.defaultCapabilityLabel || '默认')
  if (postType.is_stream_visible) labels.push(modulesCopy.value?.streamVisibleCapabilityLabel || '帖流可见')
  if (postType.counts_toward_discussion) labels.push(modulesCopy.value?.countsDiscussionCapabilityLabel || '计入讨论')
  if (postType.counts_toward_user) labels.push(modulesCopy.value?.countsUserCapabilityLabel || '计入用户')
  if (postType.searchable) labels.push(modulesCopy.value?.searchableCapabilityLabel || '可搜索')
  return labels.join(' / ') || modulesCopy.value?.noValueText || '无'
}

function formatLifecycleLabels(module) {
  const phases = module.lifecycle?.phases || []
  if (!phases.length) {
    return modulesCopy.value?.noValueText || '无'
  }
  return phases.map(item => item.label).join(' -> ')
}
</script>

<style scoped>
.ModulesPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ModulesPage-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ModulesPage-sectionHeader h3 {
  margin: 0 0 6px;
  color: var(--forum-text-color);
  font-size: 18px;
}

.ModulesPage-sectionHeader p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ModulesPage-contextBar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.ModulesPage-contextBack {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.ModulesPage-contextHint {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  color: var(--forum-text-muted);
}

.ModulesPage-contextHint strong,
.ModulesPage-contextHint code {
  color: var(--forum-text-color);
}

.ModulesPage-overview {
  display: grid;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--forum-border-color);
  border-radius: 18px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ModulesPage-overviewStats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ModulesPage-overviewItem {
  min-width: 120px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--forum-bg-subtle);
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
}

.ModulesPage-overviewItem strong {
  color: var(--forum-text-color);
  font-size: 20px;
}

.ModulesPage-overviewItem span:last-child {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.ModulesPage-overviewAlerts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.ModulesPage-overviewAlert {
  padding: 12px 14px;
  border-radius: 14px;
  background: #fff7e8;
  border: 1px solid #f1ddb2;
}

.ModulesPage-overviewAlert strong {
  display: block;
  color: #8d5d07;
  font-size: 13px;
}

.ModulesPage-overviewAlert p {
  margin: 6px 0 0;
  color: #9b660d;
  font-size: 13px;
  line-height: 1.6;
}

.ModulesPage-toolbar {
  gap: 16px;
}

.ModulesPage-toolbarGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ModulesPage-search {
  min-width: min(320px, 100%);
}

.ModulesPage-search .FormControl {
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
}

.ModulesPage-alerts,
.CategorySummaryGrid,
.ModulesPage-grid {
  display: grid;
  gap: 16px;
}

.ModulesPage-alerts,
.CategorySummaryGrid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.ModulesPage-grid {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}

.ModuleShelf {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ModuleRow {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
  overflow: hidden;
}

.ModuleRow.is-attention {
  border-color: #ead29f;
}

.ModuleRow-main {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 18px;
}

.ModuleRow-expander {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--forum-text-soft);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}

.ModuleRow.is-expanded .ModuleRow-expander i {
  transform: rotate(90deg);
}

.ModuleRow-expander i {
  transition: transform 0.18s ease;
}

.ModuleRow-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex: 0 0 auto;
}

.ModuleRow-icon--core {
  background: #eaf1fb;
  color: #315f9a;
}

.ModuleRow-icon--feature {
  background: #eef5fb;
  color: #4b698a;
}

.ModuleRow-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ModuleRow-titleLine {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ModuleRow-titleLine h4 {
  margin: 0;
  color: var(--forum-text-color);
  font-size: 17px;
}

.ModuleRow-description {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.55;
}

.ModuleRow-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--forum-text-soft);
  font-size: 13px;
}

.ModuleRow-meta strong {
  color: var(--forum-text-muted);
  font-weight: 600;
  margin-right: 4px;
}

.ModuleRow-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ModuleRow-stat {
  min-width: 64px;
  padding: 7px 10px;
  border-radius: 999px;
  background: #f5f8fb;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ModuleRow-stat strong {
  color: var(--forum-text-color);
  font-size: 14px;
}

.ModuleRow-stat span {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.ModuleRow-warningLine {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #9b660d;
  font-size: 13px;
}

.ModuleRow-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  min-width: 132px;
}

.ModuleRow-panel {
  padding: 0 18px 18px;
  border-top: 1px solid var(--forum-border-soft);
  background: #fafbfd;
}

.ModuleRow-panelGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding-top: 16px;
}

.ModulePanelCard {
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-soft);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
}

.ModulePanelCard h5 {
  margin: 0 0 12px;
  color: var(--forum-text-color);
  font-size: 14px;
}

.ModulePanelMeta,
.ModulePanelSummary {
  display: grid;
  gap: 10px;
  margin: 0;
}

.ModulePanelMeta-row,
.ModulePanelSummary-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.ModulePanelMeta-row dt,
.ModulePanelSummary-row span {
  color: var(--forum-text-soft);
  font-size: 13px;
}

.ModulePanelMeta-row dd,
.ModulePanelSummary-row strong {
  margin: 0;
  color: var(--forum-text-color);
  text-align: right;
  overflow-wrap: anywhere;
}

.ModuleCompactList {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ModuleCompactList small {
  display: block;
  margin-top: 4px;
  color: var(--forum-text-soft);
}

.ModulesPage-archive {
  border: 1px solid var(--forum-border-color);
  border-radius: 18px;
  background: #fcfcfd;
  padding: 14px 16px 18px;
}

.ModulesPage-archiveSummary {
  cursor: pointer;
  color: var(--forum-text-muted);
  font-size: 14px;
  font-weight: 700;
  list-style: none;
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
}

.ModulesPage-archiveSummary small {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 500;
}

.ModulesPage-archiveSummary::-webkit-details-marker {
  display: none;
}

.ModuleAttentionCard,
.CategorySummaryCard,
.ModuleCard {
  min-width: 0;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
  box-shadow: var(--forum-shadow-sm);
}

.ModuleAttentionCard,
.CategorySummaryCard {
  padding: 16px 18px;
}

.ModuleCard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
}

.ModuleAttentionCard-header,
.CategorySummaryCard-header,
.ModuleCard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ModuleAttentionCard p,
.CategorySummaryCard-meta,
.ModuleCard p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.CategorySummaryCard h4,
.ModuleCard h4 {
  margin: 0;
  color: var(--forum-text-color);
  font-size: 18px;
}

.CategorySummaryCard-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 13px;
}

.ModuleCard-titleRow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.ModuleBadge,
.ModuleStatus,
.ModuleToken {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.ModuleBadge {
  padding: 5px 9px;
}

.ModuleBadge--core {
  background: #eaf1fb;
  color: #315f9a;
}

.ModuleBadge--feature {
  background: #edf8f2;
  color: #25704d;
}

.ModuleStatus {
  padding: 5px 10px;
  white-space: nowrap;
}

.ModuleStatus--enabled {
  background: #edf8f2;
  color: #25704d;
}

.ModuleStatus--disabled {
  background: #f5f7fa;
  color: #6c7988;
}

.ModuleStatus--warning {
  background: #fff4df;
  color: #9b660d;
}

.ModuleMeta {
  display: grid;
  gap: 10px;
}

.ModuleMeta-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  color: var(--forum-text-muted);
}

.ModuleMeta-row span {
  font-size: 13px;
  color: var(--forum-text-soft);
}

.ModuleMeta-row strong {
  min-width: 0;
  text-align: right;
  color: var(--forum-text-color);
  overflow-wrap: anywhere;
}

.ModuleWarnings {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid #f2d29b;
  border-radius: 12px;
  background: #fff9ef;
}

.ModuleWarnings--neutral {
  border-color: var(--forum-border-color);
  background: var(--forum-bg-subtle);
}

.ModuleWarnings p {
  margin: 0;
}

.ModuleActionBar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ModuleActionLink {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  justify-content: center;
}

.ModuleActionLink--primary {
  background: #edf4fb;
  border-color: #d6e4f3;
  color: #325b85;
}

.ModuleActionLink:hover {
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-color);
}

.ModuleTokens {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ModuleToken {
  padding: 5px 9px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.ModuleLists {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.ModuleLists h5 {
  margin: 0 0 10px;
  color: var(--forum-text-color);
  font-size: 14px;
}

.ModuleList {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--forum-text-muted);
}

.ModuleList li {
  overflow-wrap: anywhere;
}

.ModuleList small {
  display: block;
  color: var(--forum-text-soft);
  line-height: 1.5;
}

.ModuleList li small {
  display: block;
  margin-top: 4px;
  color: var(--forum-text-soft);
}

.ModuleList--dense {
  gap: 10px;
}

.ModuleList--dense li {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ModuleList--dense small {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.ModuleList code {
  margin-right: 8px;
}

.ModuleEmpty {
  margin: 0;
  color: var(--forum-text-soft);
  font-size: 13px;
}

.AdminTableWrap {
  overflow-x: auto;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-elevated);
}

.AdminTable {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
}

.AdminTable th,
.AdminTable td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--forum-border-soft);
  text-align: left;
  color: var(--forum-text-muted);
}

.AdminTable th {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 13px;
}

.AdminTable td code {
  color: var(--forum-text-color);
}

.ModulesPage-grid--secondary {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 768px) {
  .ModulesPage-overview {
    padding: 16px;
  }

  .ModulesPage-toolbarGroup {
    flex-direction: column;
  }

  .ModuleAttentionCard-header,
  .CategorySummaryCard-header,
  .ModuleCard-header,
  .ModuleLists {
    grid-template-columns: 1fr;
    display: flex;
    flex-direction: column;
  }

  .ModuleMeta-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .ModuleRow-main {
    grid-template-columns: auto auto minmax(0, 1fr);
  }

  .ModuleRow-actions {
    grid-column: 1 / -1;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    min-width: 0;
  }

  .ModuleRow-panelGrid {
    grid-template-columns: 1fr;
  }
}
</style>
