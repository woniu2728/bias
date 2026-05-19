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
      <AdminSummaryGrid :items="summaryItems" />

      <section v-if="dependencyAttention.length" class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.dependencyAttentionTitle || '依赖关注项' }}</h3>
          <p>{{ modulesCopy?.dependencyAttentionDescription || '模块依赖状态会直接影响后续扩展启用与注册结果，这里优先暴露需要处理的项。' }}</p>
        </div>

        <div class="ModulesPage-alerts">
          <article
            v-for="issue in dependencyAttention"
            :key="issue.module_id"
            class="ModuleAttentionCard"
          >
            <div class="ModuleAttentionCard-header">
              <strong>{{ issue.module_name }}</strong>
              <span class="ModuleStatus ModuleStatus--warning">{{ issue.label }}</span>
            </div>
            <p v-if="issue.missing?.length">
              {{ modulesCopy?.missingDependenciesPrefix || '缺少依赖' }}: <code>{{ issue.missing.join(', ') }}</code>
            </p>
            <p v-if="issue.disabled?.length">
              {{ modulesCopy?.disabledDependenciesPrefix || '未启用依赖' }}: <code>{{ issue.disabled.join(', ') }}</code>
            </p>
          </article>
        </div>
      </section>

      <section v-if="runtimeDependencyModules.length" class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.runtimeDependencyTitle || '运行依赖健康' }}</h3>
          <p>{{ modulesCopy?.runtimeDependencyDescription || '这里汇总模块运行时依赖的真实健康状态，优先暴露配置已存在但服务不可达的风险。' }}</p>
        </div>

        <div class="ModulesPage-alerts">
          <article
            v-for="module in runtimeDependencyModules"
            :key="`${module.id}-runtime-dependency`"
            class="ModuleAttentionCard"
          >
            <div class="ModuleAttentionCard-header">
              <strong>{{ module.name }}</strong>
              <span class="ModuleStatus ModuleStatus--warning">
                {{ module.runtime_dependency_summary?.label || (modulesCopy?.runtimeDependencyWarningLabel || '需关注') }}
              </span>
            </div>
            <p
              v-for="issue in module.runtime_dependency_summary?.issues || []"
              :key="issue"
            >
              {{ issue }}
            </p>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.categorySummaryTitle || '分类概览' }}</h3>
          <p>{{ modulesCopy?.categorySummaryDescription || '按模块类别查看当前注册规模，优先识别哪些能力已经模块化，哪些区域仍需继续收口。' }}</p>
        </div>

        <div class="CategorySummaryGrid">
          <article
            v-for="category in categorySummaries"
            :key="category.id"
            class="CategorySummaryCard"
          >
            <div class="CategorySummaryCard-header">
              <h4>{{ category.label }}</h4>
              <span class="ModuleBadge" :class="category.id === 'core' ? 'ModuleBadge--core' : 'ModuleBadge--feature'">
                {{ modulesCopy?.categoryModuleCountText?.(category.module_count) || `${category.module_count} 个模块` }}
              </span>
            </div>
            <div class="CategorySummaryCard-meta">
              <span>{{ modulesCopy?.categoryEnabledText?.(category.enabled_count) || `已启用 ${category.enabled_count}` }}</span>
              <span v-if="category.attention_count">{{ modulesCopy?.categoryAttentionText?.(category.attention_count) || `需关注 ${category.attention_count}` }}</span>
              <span v-else>{{ modulesCopy?.categoryHealthyText || '依赖健康' }}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>{{ modulesCopy?.moduleListTitle || '模块列表' }}</h3>
          <p>{{ modulesCopy?.moduleListDescription || '这里展示内置模块注册结果。当前重点是注册覆盖面、依赖健康和后台接入，不再只是静态清单。' }}</p>
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

        <div v-if="filteredModules.length" class="ModulesPage-grid">
          <article v-for="module in filteredModules" :key="module.id" class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>{{ module.name }}</h4>
                  <span class="ModuleBadge" :class="module.is_core ? 'ModuleBadge--core' : 'ModuleBadge--feature'">
                    {{ module.is_core ? (modulesCopy?.coreCategoryLabel || '核心') : module.category_label }}
                  </span>
                  <span
                    class="ModuleStatus"
                    :class="module.dependency_status === 'healthy' ? 'ModuleStatus--enabled' : 'ModuleStatus--warning'"
                  >
                    {{ module.dependency_status_label }}
                  </span>
                  <span
                    class="ModuleStatus"
                    :class="module.health_status === 'healthy' ? 'ModuleStatus--enabled' : 'ModuleStatus--warning'"
                  >
                    {{ module.health_status_label }}
                  </span>
                </div>
                <p>{{ module.description }}</p>
              </div>
              <span class="ModuleStatus" :class="module.enabled ? 'ModuleStatus--enabled' : 'ModuleStatus--disabled'">
                {{ module.enabled ? (modulesCopy?.enabledStatusLabel || '已启用') : (modulesCopy?.disabledStatusLabel || '未启用') }}
              </span>
            </div>

            <AdminSummaryGrid :items="buildModuleSummary(module)" />

            <div class="ModuleMeta">
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.moduleIdLabel || '模块 ID' }}</span>
                <strong>{{ module.id }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.versionLabel || '版本' }}</span>
                <strong>{{ module.version }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.dependenciesLabel || '依赖' }}</span>
                <strong>{{ module.dependencies.length ? module.dependencies.join(', ') : (modulesCopy?.noValueText || '无') }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.bootModeLabel || '启动方式' }}</span>
                <strong>{{ module.runtime?.boot_mode_label || modulesCopy?.staticBootModeLabel || '静态注册' }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.settingsGroupLabel || '设置组' }}</span>
                <strong>{{ module.settings?.groups?.length ? module.settings.groups.join(', ') : (modulesCopy?.noValueText || '无') }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>{{ modulesCopy?.documentationLabel || '文档' }}</span>
                <strong>
                  <a :href="module.documentation_url">{{ module.documentation_url }}</a>
                </strong>
              </div>
            </div>

            <div class="ModuleActionBar">
              <router-link
                v-if="module.runtime?.settings_entry_path"
                class="ModuleActionLink"
                :to="module.runtime.settings_entry_path"
              >
                {{ modulesCopy?.settingsEntryActionLabel || '配置入口' }}
              </router-link>
              <router-link
                v-if="module.runtime?.permissions_entry_path"
                class="ModuleActionLink"
                :to="module.runtime.permissions_entry_path"
              >
                {{ modulesCopy?.permissionsEntryActionLabel || '权限入口' }}
              </router-link>
              <router-link
                v-if="module.runtime?.module_center_path"
                class="ModuleActionLink"
                :to="module.runtime.module_center_path"
              >
                {{ modulesCopy?.debugEntryActionLabel || '调试视图' }}
              </router-link>
              <a
                v-if="module.documentation_url"
                class="ModuleActionLink"
                :href="module.documentation_url"
              >
                {{ modulesCopy?.documentationEntryActionLabel || '模块文档' }}
              </a>
            </div>

            <div v-if="module.missing_dependencies.length || module.disabled_dependencies.length" class="ModuleWarnings">
              <p v-if="module.missing_dependencies.length">
                {{ modulesCopy?.missingDependenciesPrefix || '缺少依赖' }}: <code>{{ module.missing_dependencies.join(', ') }}</code>
              </p>
              <p v-if="module.disabled_dependencies.length">
                {{ modulesCopy?.disabledDependenciesPrefix || '未启用依赖' }}: <code>{{ module.disabled_dependencies.join(', ') }}</code>
              </p>
            </div>
            <div v-if="module.health_issues.length" class="ModuleWarnings ModuleWarnings--neutral">
              <p v-for="issue in module.health_issues" :key="issue">
                {{ issue }}
              </p>
            </div>

            <div v-if="module.capabilities.length" class="ModuleTokens">
              <span v-for="capability in module.capabilities" :key="capability" class="ModuleToken">
                {{ capability }}
              </span>
            </div>

            <div class="ModuleLists">
              <div>
                <h5>{{ modulesCopy?.adminEntriesTitle || '后台入口' }}</h5>
                <ul v-if="module.admin_pages.length" class="ModuleList">
                  <li v-for="page in module.admin_pages" :key="page.path">
                    <router-link :to="page.path">{{ page.label }}</router-link>
                    <small v-if="page.settings_group">{{ modulesCopy?.pageSettingsGroupText?.(page.settings_group) || `设置组: ${page.settings_group}` }}</small>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noAdminEntriesText || '暂无后台入口' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.permissionsTitle || '权限注册' }}</h5>
                <ul v-if="module.permissions.length" class="ModuleList">
                  <li v-for="permission in module.permissions" :key="permission.code">
                    <code>{{ permission.code }}</code>
                    <span>{{ permission.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noPermissionsText || '暂无权限声明' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.settingsRuntimeTitle || '设置与运行时' }}</h5>
                <ul v-if="module.settings?.has_settings || module.runtime" class="ModuleList">
                  <li v-if="module.settings?.groups?.length">
                    <span>{{ modulesCopy?.settingsGroupItemLabel || '设置组' }}</span>
                    <code>{{ module.settings.groups.join(', ') }}</code>
                  </li>
                  <li v-if="module.settings?.has_settings">
                    <span>{{ modulesCopy?.configuredKeyCountLabel || '已配置键' }}</span>
                    <code>{{ module.settings.configured_key_count }}</code>
                  </li>
                  <li v-if="module.runtime?.migration_label">
                    <span>{{ modulesCopy?.migrationStatusLabel || '迁移状态' }}</span>
                    <code>{{ module.runtime.migration_label }}</code>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noSettingsRuntimeText || '暂无设置或运行时元数据' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.debugInfoTitle || '调试信息' }}</h5>
                <ul v-if="module.runtime?.debug_items?.length" class="ModuleList">
                  <li v-for="item in module.runtime.debug_items" :key="item.key">
                    <span>{{ item.label }}</span>
                    <code>{{ item.value }}</code>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noDebugInfoText || '暂无调试信息' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.notificationTypesTitle || '通知类型' }}</h5>
                <ul v-if="module.notification_types.length" class="ModuleList">
                  <li v-for="notificationType in module.notification_types" :key="notificationType.code">
                    <code>{{ notificationType.code }}</code>
                    <span>{{ notificationType.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noNotificationTypesText || '暂无通知类型' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.notificationRenderersTitle || '通知渲染器' }}</h5>
                <ul v-if="module.notification_renderers.length" class="ModuleList">
                  <li v-for="renderer in module.notification_renderers" :key="renderer.code">
                    <code>{{ renderer.code }}</code>
                    <span>{{ renderer.label }}</span>
                    <small>{{ renderer.navigation_scope }}</small>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noNotificationRenderersText || '暂无通知渲染器' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.userPreferencesTitle || '用户偏好' }}</h5>
                <ul v-if="module.user_preferences.length" class="ModuleList">
                  <li v-for="preference in module.user_preferences" :key="preference.key">
                    <code>{{ preference.key }}</code>
                    <span>{{ preference.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noUserPreferencesText || '暂无用户偏好' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.languagePacksTitle || '语言包' }}</h5>
                <ul v-if="module.language_packs.length" class="ModuleList">
                  <li v-for="languagePack in module.language_packs" :key="languagePack.code">
                    <code>{{ languagePack.code }}</code>
                    <span>{{ languagePack.native_label || languagePack.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noLanguagePacksText || '暂无语言包' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.eventListenersTitle || '事件监听' }}</h5>
                <ul v-if="module.event_listeners.length" class="ModuleList">
                  <li v-for="listener in module.event_listeners" :key="`${listener.event}:${listener.listener}`">
                    <code>{{ listener.event }}</code>
                    <span>{{ listener.listener }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noEventListenersText || '暂无事件监听' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.postTypesTitle || '帖子类型' }}</h5>
                <ul v-if="module.post_types.length" class="ModuleList">
                  <li v-for="postType in module.post_types" :key="postType.code">
                    <code>{{ postType.code }}</code>
                    <span>{{ postType.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noPostTypesText || '暂无帖子类型' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.resourceFieldsTitle || '资源字段' }}</h5>
                <ul v-if="module.resource_fields.length" class="ModuleList">
                  <li
                    v-for="resourceField in module.resource_fields"
                    :key="`${resourceField.resource}:${resourceField.field}`"
                  >
                    <code>{{ resourceField.resource }}.{{ resourceField.field }}</code>
                    <span>{{ resourceField.description || modulesCopy?.resourceFieldFallbackText || '已注册资源扩展字段' }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noResourceFieldsText || '暂无资源字段' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.searchFiltersTitle || '搜索过滤器' }}</h5>
                <ul v-if="module.search_filters.length" class="ModuleList">
                  <li v-for="searchFilter in module.search_filters" :key="`${searchFilter.target}:${searchFilter.code}`">
                    <code>{{ searchFilter.syntax || searchFilter.code }}</code>
                    <span>{{ searchFilter.description || searchFilter.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noSearchFiltersText || '暂无搜索过滤器' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.discussionSortsTitle || '讨论排序' }}</h5>
                <ul v-if="module.discussion_sorts.length" class="ModuleList">
                  <li v-for="discussionSort in module.discussion_sorts" :key="discussionSort.code">
                    <code>{{ discussionSort.code }}</code>
                    <span>{{ discussionSort.description || discussionSort.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noDiscussionSortsText || '暂无讨论排序' }}</p>
              </div>

              <div>
                <h5>{{ modulesCopy?.discussionListFiltersTitle || '讨论列表过滤' }}</h5>
                <ul v-if="module.discussion_list_filters.length" class="ModuleList">
                  <li v-for="discussionListFilter in module.discussion_list_filters" :key="discussionListFilter.code">
                    <code>{{ discussionListFilter.code }}</code>
                    <span>{{ discussionListFilter.description || discussionListFilter.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">{{ modulesCopy?.noDiscussionListFiltersText || '暂无讨论列表过滤' }}</p>
              </div>
            </div>
          </article>
        </div>
        <AdminStateBlock v-else tone="subtle">{{ modulesCopy?.emptyFilteredModulesText || '当前筛选下没有匹配的模块。' }}</AdminStateBlock>
      </section>

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
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminSummaryGrid from '../components/AdminSummaryGrid.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'
import api from '../../api'
import { getResolvedNotificationTypes } from '../../forum/notificationTypes'
import {
  getAdminModulesPageActionMeta,
  getAdminModulesPageConfig,
  getAdminModulesPageCopy,
} from '../registry'

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

const summaryItems = computed(() => {
  const labels = modulesConfig.value?.summaryLabels || {}
  return [
    { label: labels.module_count || '模块总数', value: String(summary.value.module_count ?? modules.value.length) },
    { label: labels.core_count || '核心模块', value: String(summary.value.core_count ?? modules.value.filter(item => item.is_core).length) },
    { label: labels.enabled_count || '已启用', value: String(summary.value.enabled_count ?? modules.value.filter(item => item.enabled).length) },
    { label: labels.dependency_issue_count || '依赖关注', value: String(summary.value.dependency_issue_count ?? dependencyAttention.value.length) },
    { label: labels.permission_count || '权限声明', value: String(summary.value.permission_count ?? 0) },
    { label: labels.admin_page_count || '后台入口', value: String(summary.value.admin_page_count ?? adminPages.value.length) },
    { label: labels.notification_type_count || '通知类型', value: String(summary.value.notification_type_count ?? notificationTypes.value.length) },
    { label: labels.notification_renderer_count || '通知渲染器', value: String(notificationRenderers.value.length) },
    { label: labels.language_pack_count || '语言包', value: String(summary.value.language_pack_count ?? languagePacks.value.length) },
    { label: labels.user_preference_count || '用户偏好', value: String(summary.value.user_preference_count ?? userPreferences.value.length) },
    { label: labels.event_listener_count || '事件监听', value: String(summary.value.event_listener_count ?? eventListeners.value.length) },
    { label: labels.post_type_count || '帖子类型', value: String(summary.value.post_type_count ?? postTypes.value.length) },
    { label: labels.resource_field_count || '资源字段', value: String(summary.value.resource_field_count ?? resourceFields.value.length) },
    { label: labels.search_filter_count || '搜索过滤', value: String(summary.value.search_filter_count ?? searchFilters.value.length) },
    { label: labels.discussion_sort_count || '讨论排序', value: String(summary.value.discussion_sort_count ?? discussionSorts.value.length) },
    { label: labels.discussion_list_filter_count || '列表过滤', value: String(summary.value.discussion_list_filter_count ?? discussionListFilters.value.length) },
    { label: labels.settings_group_count || '设置组', value: String(summary.value.settings_group_count ?? 0) },
    { label: labels.health_attention_count || '健康关注', value: String(summary.value.health_attention_count ?? 0) },
    { label: labels.runtime_dependency_attention_count || '运行依赖关注', value: String(summary.value.runtime_dependency_attention_count ?? runtimeDependencyModules.value.length) },
  ]
})

const moduleNameMap = computed(() => Object.fromEntries(modules.value.map(item => [item.id, item.name])))

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
    runtime: module.runtime || {},
    documentation_url: module.documentation_url || '',
  }
}

onMounted(async () => {
  await loadModules()
})

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

function buildModuleSummary(module) {
  const counts = module.registration_counts || {}
  const labels = modulesConfig.value?.moduleSummaryLabels || {}
  return [
    { label: labels.permissions || '权限数', value: String(counts.permissions ?? module.permissions?.length ?? 0) },
    { label: labels.admin_pages || '后台页数', value: String(counts.admin_pages ?? module.admin_pages?.length ?? 0) },
    { label: labels.dependencies || '依赖数', value: String(module.dependencies?.length || 0) },
    { label: labels.capabilities || '能力项', value: String(module.capabilities?.length || 0) },
    { label: labels.notification_types || '通知数', value: String(counts.notification_types ?? module.notification_types?.length ?? 0) },
    { label: labels.notification_renderers || '渲染器', value: String(module.notification_renderers?.length ?? 0) },
    { label: labels.language_packs || '语言包', value: String(counts.language_packs ?? module.language_packs?.length ?? 0) },
    { label: labels.user_preferences || '偏好项', value: String(counts.user_preferences ?? module.user_preferences?.length ?? 0) },
    { label: labels.event_listeners || '监听器', value: String(counts.event_listeners ?? module.event_listeners?.length ?? 0) },
    { label: labels.post_types || '帖子类型', value: String(counts.post_types ?? module.post_types?.length ?? 0) },
    { label: labels.resource_fields || '资源字段', value: String(counts.resource_fields ?? module.resource_fields?.length ?? 0) },
    { label: labels.search_filters || '搜索过滤', value: String(counts.search_filters ?? module.search_filters?.length ?? 0) },
    { label: labels.discussion_sorts || '讨论排序', value: String(counts.discussion_sorts ?? module.discussion_sorts?.length ?? 0) },
    { label: labels.discussion_list_filters || '列表过滤', value: String(counts.discussion_list_filters ?? module.discussion_list_filters?.length ?? 0) },
  ]
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
</script>

<style scoped>
.ModulesPage-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
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
  padding: 6px 10px;
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
  .ModulesPage-toolbarGroup {
    flex-direction: column;
  }

  .ModulesPage-grid {
    grid-template-columns: 1fr;
  }

  .ModuleCard {
    padding: 16px;
    border-radius: 14px;
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
}
</style>
