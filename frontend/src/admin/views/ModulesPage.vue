<template>
  <AdminPage
    className="ModulesPage"
    icon="fas fa-cubes"
    title="模块中心"
    description="围绕注册中心查看模块边界、依赖健康、扩展注入面与后台入口。"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载模块信息中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>
    <div v-else class="ModulesPage-content">
      <AdminSummaryGrid :items="summaryItems" />

      <section v-if="dependencyAttention.length" class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>依赖关注项</h3>
          <p>模块依赖状态会直接影响后续扩展启用与注册结果，这里优先暴露需要处理的项。</p>
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
              缺少依赖: <code>{{ issue.missing.join(', ') }}</code>
            </p>
            <p v-if="issue.disabled?.length">
              未启用依赖: <code>{{ issue.disabled.join(', ') }}</code>
            </p>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>分类概览</h3>
          <p>按模块类别查看当前注册规模，优先识别哪些能力已经模块化，哪些区域仍需继续收口。</p>
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
                {{ category.module_count }} 个模块
              </span>
            </div>
            <div class="CategorySummaryCard-meta">
              <span>已启用 {{ category.enabled_count }}</span>
              <span v-if="category.attention_count">需关注 {{ category.attention_count }}</span>
              <span v-else>依赖健康</span>
            </div>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>模块列表</h3>
          <p>这里展示内置模块注册结果。当前重点是注册覆盖面、依赖健康和后台接入，不再只是静态清单。</p>
        </div>

        <AdminToolbar class="ModulesPage-toolbar" align="between">
          <div class="ModulesPage-toolbarGroup">
            <AdminFilterTabs v-model="categoryFilter" :options="categoryFilterOptions" />
            <AdminFilterTabs v-model="statusFilter" :options="statusFilterOptions" />
          </div>
          <label class="ModulesPage-search">
            <span class="sr-only">搜索模块</span>
            <input
              v-model.trim="searchQuery"
              class="FormControl"
              type="search"
              placeholder="搜索模块名、ID、能力或依赖"
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
                    {{ module.is_core ? '核心' : module.category_label }}
                  </span>
                  <span
                    class="ModuleStatus"
                    :class="module.dependency_status === 'healthy' ? 'ModuleStatus--enabled' : 'ModuleStatus--warning'"
                  >
                    {{ module.dependency_status_label }}
                  </span>
                </div>
                <p>{{ module.description }}</p>
              </div>
              <span class="ModuleStatus" :class="module.enabled ? 'ModuleStatus--enabled' : 'ModuleStatus--disabled'">
                {{ module.enabled ? '已启用' : '未启用' }}
              </span>
            </div>

            <AdminSummaryGrid :items="buildModuleSummary(module)" />

            <div class="ModuleMeta">
              <div class="ModuleMeta-row">
                <span>模块 ID</span>
                <strong>{{ module.id }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>版本</span>
                <strong>{{ module.version }}</strong>
              </div>
              <div class="ModuleMeta-row">
                <span>依赖</span>
                <strong>{{ module.dependencies.length ? module.dependencies.join(', ') : '无' }}</strong>
              </div>
            </div>

            <div v-if="module.missing_dependencies.length || module.disabled_dependencies.length" class="ModuleWarnings">
              <p v-if="module.missing_dependencies.length">
                缺少依赖: <code>{{ module.missing_dependencies.join(', ') }}</code>
              </p>
              <p v-if="module.disabled_dependencies.length">
                未启用依赖: <code>{{ module.disabled_dependencies.join(', ') }}</code>
              </p>
            </div>

            <div v-if="module.capabilities.length" class="ModuleTokens">
              <span v-for="capability in module.capabilities" :key="capability" class="ModuleToken">
                {{ capability }}
              </span>
            </div>

            <div class="ModuleLists">
              <div>
                <h5>后台入口</h5>
                <ul v-if="module.admin_pages.length" class="ModuleList">
                  <li v-for="page in module.admin_pages" :key="page.path">
                    <router-link :to="page.path">{{ page.label }}</router-link>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无后台入口</p>
              </div>

              <div>
                <h5>权限注册</h5>
                <ul v-if="module.permissions.length" class="ModuleList">
                  <li v-for="permission in module.permissions" :key="permission.code">
                    <code>{{ permission.code }}</code>
                    <span>{{ permission.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无权限声明</p>
              </div>

              <div>
                <h5>通知类型</h5>
                <ul v-if="module.notification_types.length" class="ModuleList">
                  <li v-for="notificationType in module.notification_types" :key="notificationType.code">
                    <code>{{ notificationType.code }}</code>
                    <span>{{ notificationType.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无通知类型</p>
              </div>

              <div>
                <h5>用户偏好</h5>
                <ul v-if="module.user_preferences.length" class="ModuleList">
                  <li v-for="preference in module.user_preferences" :key="preference.key">
                    <code>{{ preference.key }}</code>
                    <span>{{ preference.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无用户偏好</p>
              </div>

              <div>
                <h5>事件监听</h5>
                <ul v-if="module.event_listeners.length" class="ModuleList">
                  <li v-for="listener in module.event_listeners" :key="`${listener.event}:${listener.listener}`">
                    <code>{{ listener.event }}</code>
                    <span>{{ listener.listener }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无事件监听</p>
              </div>

              <div>
                <h5>帖子类型</h5>
                <ul v-if="module.post_types.length" class="ModuleList">
                  <li v-for="postType in module.post_types" :key="postType.code">
                    <code>{{ postType.code }}</code>
                    <span>{{ postType.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无帖子类型</p>
              </div>

              <div>
                <h5>资源字段</h5>
                <ul v-if="module.resource_fields.length" class="ModuleList">
                  <li
                    v-for="resourceField in module.resource_fields"
                    :key="`${resourceField.resource}:${resourceField.field}`"
                  >
                    <code>{{ resourceField.resource }}.{{ resourceField.field }}</code>
                    <span>{{ resourceField.description || '已注册资源扩展字段' }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无资源字段</p>
              </div>

              <div>
                <h5>搜索过滤器</h5>
                <ul v-if="module.search_filters.length" class="ModuleList">
                  <li v-for="searchFilter in module.search_filters" :key="`${searchFilter.target}:${searchFilter.code}`">
                    <code>{{ searchFilter.syntax || searchFilter.code }}</code>
                    <span>{{ searchFilter.description || searchFilter.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无搜索过滤器</p>
              </div>

              <div>
                <h5>讨论排序</h5>
                <ul v-if="module.discussion_sorts.length" class="ModuleList">
                  <li v-for="discussionSort in module.discussion_sorts" :key="discussionSort.code">
                    <code>{{ discussionSort.code }}</code>
                    <span>{{ discussionSort.description || discussionSort.label }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无讨论排序</p>
              </div>
            </div>
          </article>
        </div>
        <AdminStateBlock v-else tone="subtle">当前筛选下没有匹配的模块。</AdminStateBlock>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>后台注册入口</h3>
          <p>按当前筛选结果列出后台页面，便于检查导航是否已经真正从模块注册元数据派生。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>页面</th>
                <th>路径</th>
                <th>归属模块</th>
                <th>导航分组</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="page in filteredAdminPages" :key="page.path">
                <td>
                  <router-link :to="page.path">{{ page.label }}</router-link>
                </td>
                <td><code>{{ page.path }}</code></td>
                <td>{{ moduleNameMap[page.module_id] || page.module_id }}</td>
                <td>{{ page.nav_section === 'core' ? '核心' : '功能' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>通知类型与事件监听</h3>
          <p>用于校验模块通知协议和领域事件挂接是否持续沿统一机制注册。</p>
        </div>

        <div class="ModulesPage-grid ModulesPage-grid--secondary">
          <article class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>通知类型</h4>
                </div>
                <p>所有已在注册中心声明的站内通知类型。</p>
              </div>
            </div>

            <ul v-if="filteredNotificationTypes.length" class="ModuleList ModuleList--dense">
              <li v-for="notificationType in filteredNotificationTypes" :key="notificationType.code">
                <code>{{ notificationType.code }}</code>
                <span>{{ notificationType.label }}</span>
                <small>{{ moduleNameMap[notificationType.module_id] || notificationType.module_id }}</small>
              </li>
            </ul>
            <p v-else class="ModuleEmpty">暂无通知类型</p>
          </article>

          <article class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>事件监听器</h4>
                </div>
                <p>当前模块通过事件总线挂接的监听入口。</p>
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
            <p v-else class="ModuleEmpty">暂无事件监听器</p>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>用户偏好注册</h3>
          <p>这里检查模块是否通过统一注册协议声明通知和个性化偏好，而不是散落在页面局部状态中。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>偏好键</th>
                <th>归属模块</th>
                <th>分类</th>
                <th>默认值</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="preference in filteredUserPreferences" :key="`${preference.module_id}:${preference.key}`">
                <td><code>{{ preference.key }}</code></td>
                <td>{{ moduleNameMap[preference.module_id] || preference.module_id }}</td>
                <td><code>{{ preference.category }}</code></td>
                <td>{{ preference.default_value ? '开启' : '关闭' }}</td>
                <td>{{ preference.description || preference.label }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>帖子类型注册</h3>
          <p>用于承接系统事件帖、状态变更帖和普通回复的统一协议。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>类型</th>
                <th>归属模块</th>
                <th>能力</th>
                <th>说明</th>
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
          <h3>资源字段注册</h3>
          <p>汇总 Discussion、Post、Tag、Search 等资源上的扩展字段，作为统一 Resource 协议快照。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>资源</th>
                <th>字段</th>
                <th>归属模块</th>
                <th>说明</th>
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
                <td>{{ resourceField.description || '已注册资源扩展字段' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>搜索过滤器注册</h3>
          <p>列出模块通过注册中心声明的搜索过滤语法，帮助检查搜索扩展点的覆盖度。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>语法</th>
                <th>目标资源</th>
                <th>归属模块</th>
                <th>说明</th>
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
          <h3>讨论排序注册</h3>
          <p>列出模块通过注册中心声明的讨论列表排序能力，便于检查论坛首页和标签页的扩展面。</p>
        </div>

        <div class="AdminTableWrap">
          <table class="AdminTable">
            <thead>
              <tr>
                <th>排序码</th>
                <th>名称</th>
                <th>归属模块</th>
                <th>默认</th>
                <th>说明</th>
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
                <td>{{ discussionSort.is_default ? '是' : '否' }}</td>
                <td>{{ discussionSort.description || discussionSort.label }}</td>
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

const loading = ref(true)
const errorMessage = ref('')
const summary = ref({})
const modules = ref([])
const categorySummaries = ref([])
const dependencyAttention = ref([])
const adminPages = ref([])
const notificationTypes = ref([])
const userPreferences = ref([])
const eventListeners = ref([])
const postTypes = ref([])
const resourceFields = ref([])
const searchFilters = ref([])
const discussionSorts = ref([])
const categoryFilter = ref('all')
const statusFilter = ref('all')
const searchQuery = ref('')

const categoryFilterOptions = computed(() => {
  const base = [{ value: 'all', label: '全部分类', icon: 'fas fa-layer-group' }]
  return base.concat(
    categorySummaries.value.map(category => ({
      value: category.id,
      label: category.label,
      icon: category.id === 'core' ? 'fas fa-shield-alt' : 'fas fa-puzzle-piece',
    }))
  )
})

const statusFilterOptions = [
  { value: 'all', label: '全部状态', icon: 'fas fa-border-all' },
  { value: 'healthy', label: '依赖正常', icon: 'fas fa-check-circle' },
  { value: 'attention', label: '需关注', icon: 'fas fa-exclamation-triangle' },
  { value: 'enabled', label: '仅已启用', icon: 'fas fa-toggle-on' },
]

const filteredModules = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  return modules.value.filter(module => {
    if (categoryFilter.value !== 'all' && module.category !== categoryFilter.value) {
      return false
    }

    if (statusFilter.value === 'healthy' && module.dependency_status !== 'healthy') {
      return false
    }
    if (statusFilter.value === 'attention' && module.dependency_status === 'healthy') {
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
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystacks.includes(keyword)
  })
})

const filteredModuleIds = computed(() => new Set(filteredModules.value.map(item => item.id)))

const filteredAdminPages = computed(() => adminPages.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredNotificationTypes = computed(() => notificationTypes.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredUserPreferences = computed(() => userPreferences.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredEventListeners = computed(() => eventListeners.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredPostTypes = computed(() => postTypes.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredResourceFields = computed(() => resourceFields.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredSearchFilters = computed(() => searchFilters.value.filter(item => filteredModuleIds.value.has(item.module_id)))
const filteredDiscussionSorts = computed(() => discussionSorts.value.filter(item => filteredModuleIds.value.has(item.module_id)))

const summaryItems = computed(() => [
  { label: '模块总数', value: String(summary.value.module_count ?? modules.value.length) },
  { label: '核心模块', value: String(summary.value.core_count ?? modules.value.filter(item => item.is_core).length) },
  { label: '已启用', value: String(summary.value.enabled_count ?? modules.value.filter(item => item.enabled).length) },
  { label: '依赖关注', value: String(summary.value.dependency_issue_count ?? dependencyAttention.value.length) },
  { label: '权限声明', value: String(summary.value.permission_count ?? 0) },
  { label: '后台入口', value: String(summary.value.admin_page_count ?? adminPages.value.length) },
  { label: '通知类型', value: String(summary.value.notification_type_count ?? notificationTypes.value.length) },
  { label: '用户偏好', value: String(summary.value.user_preference_count ?? userPreferences.value.length) },
  { label: '事件监听', value: String(summary.value.event_listener_count ?? eventListeners.value.length) },
  { label: '帖子类型', value: String(summary.value.post_type_count ?? postTypes.value.length) },
  { label: '资源字段', value: String(summary.value.resource_field_count ?? resourceFields.value.length) },
  { label: '搜索过滤', value: String(summary.value.search_filter_count ?? searchFilters.value.length) },
  { label: '讨论排序', value: String(summary.value.discussion_sort_count ?? discussionSorts.value.length) },
])

const moduleNameMap = computed(() => Object.fromEntries(modules.value.map(item => [item.id, item.name])))

function resolveCategoryLabel(category) {
  if (category === 'core') return '核心'
  if (category === 'infrastructure') return '基础设施'
  return '功能模块'
}

function normalizeModule(module) {
  return {
    ...module,
    category_label: module.category_label || resolveCategoryLabel(module.category),
    capabilities: module.capabilities || [],
    dependencies: module.dependencies || [],
    permissions: module.permissions || [],
    admin_pages: module.admin_pages || [],
    notification_types: module.notification_types || [],
    user_preferences: module.user_preferences || [],
    event_listeners: module.event_listeners || [],
    post_types: module.post_types || [],
    resource_fields: module.resource_fields || [],
    search_filters: module.search_filters || [],
    discussion_sorts: module.discussion_sorts || [],
    missing_dependencies: module.missing_dependencies || [],
    disabled_dependencies: module.disabled_dependencies || [],
    dependency_status: module.dependency_status || 'healthy',
    dependency_status_label: module.dependency_status_label || '依赖正常',
    registration_counts: module.registration_counts || {},
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
    modules.value = (data.modules || []).map(normalizeModule)
    categorySummaries.value = data.category_summaries || []
    dependencyAttention.value = data.dependency_attention || []
    adminPages.value = data.admin_pages || []
    notificationTypes.value = data.notification_types || []
    userPreferences.value = data.user_preferences || []
    eventListeners.value = data.event_listeners || []
    postTypes.value = data.post_types || []
    resourceFields.value = data.resource_fields || []
    searchFilters.value = data.search_filters || []
    discussionSorts.value = data.discussion_sorts || []
  } catch (error) {
    console.error('加载模块信息失败:', error)
    errorMessage.value = error.response?.data?.error || '加载模块信息失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function buildModuleSummary(module) {
  const counts = module.registration_counts || {}
  return [
    { label: '权限数', value: String(counts.permissions ?? module.permissions?.length ?? 0) },
    { label: '后台页数', value: String(counts.admin_pages ?? module.admin_pages?.length ?? 0) },
    { label: '依赖数', value: String(module.dependencies?.length || 0) },
    { label: '能力项', value: String(module.capabilities?.length || 0) },
    { label: '通知数', value: String(counts.notification_types ?? module.notification_types?.length ?? 0) },
    { label: '偏好项', value: String(counts.user_preferences ?? module.user_preferences?.length ?? 0) },
    { label: '监听器', value: String(counts.event_listeners ?? module.event_listeners?.length ?? 0) },
    { label: '帖子类型', value: String(counts.post_types ?? module.post_types?.length ?? 0) },
    { label: '资源字段', value: String(counts.resource_fields ?? module.resource_fields?.length ?? 0) },
    { label: '搜索过滤', value: String(counts.search_filters ?? module.search_filters?.length ?? 0) },
    { label: '讨论排序', value: String(counts.discussion_sorts ?? module.discussion_sorts?.length ?? 0) },
  ]
}

function formatPostTypeCapabilities(postType) {
  const labels = []
  if (postType.is_default) labels.push('默认')
  if (postType.is_stream_visible) labels.push('帖流可见')
  if (postType.counts_toward_discussion) labels.push('计入讨论')
  if (postType.counts_toward_user) labels.push('计入用户')
  if (postType.searchable) labels.push('可搜索')
  return labels.join(' / ') || '无'
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

.ModuleWarnings p {
  margin: 0;
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
