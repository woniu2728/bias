<template>
  <AdminPage
    className="ModulesPage"
    icon="fas fa-cubes"
    title="模块中心"
    description="查看内置模块、依赖关系、权限注册与后台入口，作为扩展体系的当前快照。"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载模块信息中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>
    <div v-else class="ModulesPage-content">
      <AdminSummaryGrid :items="summaryItems" />

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>模块列表</h3>
          <p>当前展示的是内置模块注册结果，后续这里会承载启用状态、依赖检查和配置入口。</p>
        </div>

        <div class="ModulesPage-grid">
          <article v-for="module in modules" :key="module.id" class="ModuleCard">
            <div class="ModuleCard-header">
              <div>
                <div class="ModuleCard-titleRow">
                  <h4>{{ module.name }}</h4>
                  <span class="ModuleBadge" :class="module.is_core ? 'ModuleBadge--core' : 'ModuleBadge--feature'">
                    {{ module.is_core ? '核心' : module.categoryLabel }}
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
                <h5>资源字段</h5>
                <ul v-if="module.resource_fields.length" class="ModuleList">
                  <li v-for="resourceField in module.resource_fields" :key="`${resourceField.resource}:${resourceField.field}`">
                    <code>{{ resourceField.resource }}.{{ resourceField.field }}</code>
                    <span>{{ resourceField.description || '已注册资源扩展字段' }}</span>
                  </li>
                </ul>
                <p v-else class="ModuleEmpty">暂无资源字段</p>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="ModulesPage-section">
        <div class="ModulesPage-sectionHeader">
          <h3>后台注册入口</h3>
          <p>这里列出当前所有通过注册中心声明的后台页面，便于核对导航来源。</p>
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
              <tr v-for="page in adminPages" :key="page.path">
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
          <p>这部分用于校验模块级通知协议和领域事件挂接情况，方便后续扩展继续沿统一机制注册。</p>
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

            <ul v-if="notificationTypes.length" class="ModuleList ModuleList--dense">
              <li v-for="notificationType in notificationTypes" :key="notificationType.code">
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
                <p>当前内置模块通过事件总线挂接的监听入口。</p>
              </div>
            </div>

            <ul v-if="eventListeners.length" class="ModuleList ModuleList--dense">
              <li v-for="listener in eventListeners" :key="`${listener.event}:${listener.listener}:${listener.module_id}`">
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
          <h3>资源字段注册</h3>
          <p>这里汇总 Discussion、Post、Tag、Search 等资源上的扩展字段，作为统一 Resource 协议的当前快照。</p>
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
              <tr v-for="resourceField in resourceFields" :key="`${resourceField.resource}:${resourceField.field}:${resourceField.module_id}`">
                <td><code>{{ resourceField.resource }}</code></td>
                <td><code>{{ resourceField.field }}</code></td>
                <td>{{ moduleNameMap[resourceField.module_id] || resourceField.module_id }}</td>
                <td>{{ resourceField.description || '已注册资源扩展字段' }}</td>
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
import api from '../../api'

const loading = ref(true)
const errorMessage = ref('')
const modules = ref([])
const adminPages = ref([])
const notificationTypes = ref([])
const eventListeners = ref([])
const resourceFields = ref([])

const summaryItems = computed(() => {
  const moduleList = modules.value
  const coreCount = moduleList.filter(item => item.is_core).length
  const permissionCount = moduleList.reduce((total, item) => total + (item.permissions?.length || 0), 0)
  const adminPageCount = adminPages.value.length

  return [
    { label: '模块总数', value: String(moduleList.length) },
    { label: '核心模块', value: String(coreCount) },
    { label: '权限声明', value: String(permissionCount) },
    { label: '后台入口', value: String(adminPageCount) },
    { label: '通知类型', value: String(notificationTypes.value.length) },
    { label: '事件监听', value: String(eventListeners.value.length) },
    { label: '资源字段', value: String(resourceFields.value.length) },
  ]
})

const moduleNameMap = computed(() => {
  return Object.fromEntries(modules.value.map(item => [item.id, item.name]))
})

onMounted(async () => {
  await loadModules()
})

async function loadModules() {
  loading.value = true
  errorMessage.value = ''

  try {
    const data = await api.get('/admin/modules')
    modules.value = (data.modules || []).map(module => ({
      ...module,
      categoryLabel: resolveCategoryLabel(module.category),
    }))
    adminPages.value = data.admin_pages || []
    notificationTypes.value = data.notification_types || []
    eventListeners.value = data.event_listeners || []
    resourceFields.value = data.resource_fields || []
  } catch (error) {
    console.error('加载模块信息失败:', error)
    errorMessage.value = error.response?.data?.error || '加载模块信息失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function resolveCategoryLabel(category) {
  if (category === 'core') return '核心'
  if (category === 'infrastructure') return '基础设施'
  return '功能模块'
}

function buildModuleSummary(module) {
  return [
    { label: '权限数', value: String(module.permissions?.length || 0) },
    { label: '后台页数', value: String(module.admin_pages?.length || 0) },
    { label: '依赖数', value: String(module.dependencies?.length || 0) },
    { label: '能力项', value: String(module.capabilities?.length || 0) },
    { label: '通知数', value: String(module.notification_types?.length || 0) },
    { label: '监听器', value: String(module.event_listeners?.length || 0) },
    { label: '资源字段', value: String(module.resource_fields?.length || 0) },
  ]
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

.ModulesPage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.ModuleCard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
  box-shadow: var(--forum-shadow-sm);
}

.ModuleCard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ModuleCard-titleRow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.ModuleCard h4 {
  margin: 0;
  color: var(--forum-text-color);
  font-size: 18px;
}

.ModuleCard p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
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

@media (max-width: 768px) {
  .ModulesPage-grid {
    grid-template-columns: 1fr;
  }

  .ModuleCard {
    padding: 16px;
    border-radius: 14px;
  }

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
