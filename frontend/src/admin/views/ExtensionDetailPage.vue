<template>
  <AdminPage
    class-name="ExtensionDetailPage"
    :icon="extension?.icon || 'fas fa-puzzle-piece'"
    :title="extension?.name || '扩展详情'"
    :description="extension?.description || '查看扩展运行状态、后台入口、依赖与能力摘要。'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展详情中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else-if="extension" class="ExtensionDetailPage-content">
      <section class="ExtensionDetailPage-topbar">
        <router-link to="/admin/extensions" class="ExtensionDetailPage-back">
          <i class="fas fa-arrow-left"></i>
          <span>返回扩展中心</span>
        </router-link>
        <span class="ExtensionDetailPage-status" :class="runtimeStatusClass">
          {{ extension.runtime_status?.label || (extension.enabled ? '已启用' : '未启用') }}
        </span>
      </section>

      <section class="ExtensionDetailPage-summary">
        <article class="ExtensionDetailPage-summaryCard">
          <small>扩展 ID</small>
          <strong>{{ extension.id }}</strong>
        </article>
        <article class="ExtensionDetailPage-summaryCard">
          <small>版本</small>
          <strong>{{ extension.version }}</strong>
        </article>
        <article class="ExtensionDetailPage-summaryCard">
          <small>来源</small>
          <strong>{{ extension.source }}</strong>
        </article>
        <article class="ExtensionDetailPage-summaryCard">
          <small>依赖状态</small>
          <strong>{{ extension.dependency_state_label || '依赖正常' }}</strong>
        </article>
      </section>

      <section class="ExtensionDetailPage-actions">
        <template v-for="action in adminActions" :key="action.key">
          <router-link
            v-if="action.kind === 'route'"
            :to="action.target"
            class="ExtensionDetailAction"
            :class="resolveActionToneClass(action)"
          >
            <i v-if="action.icon" :class="action.icon"></i>
            <span>{{ action.label }}</span>
          </router-link>
          <a
            v-else
            :href="action.target"
            class="ExtensionDetailAction"
            :class="resolveActionToneClass(action)"
            :target="action.opens_in_new_tab ? '_blank' : null"
            :rel="action.opens_in_new_tab ? 'noreferrer noopener' : null"
          >
            <i v-if="action.icon" :class="action.icon"></i>
            <span>{{ action.label }}</span>
          </a>
        </template>
        <button
          v-for="action in runtimeActions"
          :key="`runtime-${action.key}`"
          type="button"
          class="ExtensionDetailAction"
          :class="resolveActionToneClass(action)"
          :disabled="actionLoading"
          @click="runRuntimeAction(action)"
        >
          {{ actionLoading ? '处理中...' : action.label }}
        </button>
      </section>

      <component
        :is="detailComponent"
        v-if="detailComponent"
        :extension="extension"
        surface="detail"
        class="ExtensionDetailPage-pluginDetail"
      />

      <div class="ExtensionDetailPage-grid">
        <section class="ExtensionDetailCard">
          <h3>生命周期</h3>
          <dl class="ExtensionDetailMeta">
            <div>
              <dt>注册模式</dt>
              <dd>{{ extension.lifecycle?.registration_mode_label || '静态注册' }}</dd>
            </div>
            <div>
              <dt>就绪判定</dt>
              <dd>{{ extension.lifecycle?.readiness_probe || '无' }}</dd>
            </div>
            <div>
              <dt>可停用</dt>
              <dd>{{ extension.lifecycle?.supports_disable ? '是' : '否' }}</dd>
            </div>
            <div>
              <dt>可回收</dt>
              <dd>{{ extension.lifecycle?.supports_teardown ? '是' : '否' }}</dd>
            </div>
          </dl>

          <ul v-if="extension.lifecycle?.phases?.length" class="ExtensionDetailPills">
            <li v-for="phase in extension.lifecycle.phases" :key="phase.key">
              {{ phase.label }}
            </li>
          </ul>
        </section>

        <section class="ExtensionDetailCard">
          <h3>后台入口</h3>
          <ul class="ExtensionDetailLinks">
            <li v-for="item in actionItems" :key="item.label">
              <span>{{ item.label }}</span>
              <code>{{ item.value }}</code>
            </li>
          </ul>
        </section>

        <section class="ExtensionDetailCard">
          <h3>依赖与能力</h3>
          <div class="ExtensionDetailStack">
            <div>
              <small>必需依赖</small>
              <strong>{{ formatList(extension.dependencies) }}</strong>
            </div>
            <div>
              <small>可选依赖</small>
              <strong>{{ formatList(extension.optional_dependencies) }}</strong>
            </div>
            <div>
              <small>冲突扩展</small>
              <strong>{{ formatList(extension.conflicts) }}</strong>
            </div>
            <div>
              <small>提供能力</small>
              <strong>{{ formatList(extension.provides) }}</strong>
            </div>
          </div>
        </section>

        <section class="ExtensionDetailCard">
          <h3>运行时</h3>
          <div class="ExtensionDetailStack">
            <div>
              <small>运行状态</small>
              <strong>{{ extension.runtime_status?.label || '未知' }}</strong>
            </div>
            <div>
              <small>安装状态</small>
              <strong>{{ extension.installed ? '已安装' : '未安装' }}</strong>
            </div>
            <div>
              <small>引导状态</small>
              <strong>{{ extension.booted ? '已引导' : '未引导' }}</strong>
            </div>
            <div>
              <small>健康状态</small>
              <strong>{{ extension.healthy ? '健康' : '异常' }}</strong>
            </div>
            <div>
              <small>迁移状态</small>
              <strong>{{ extension.migration_label || '无' }}</strong>
            </div>
            <div>
              <small>可执行操作</small>
              <strong>{{ runtimeActions.length }}</strong>
            </div>
          </div>
          <p v-if="extension.runtime_issues?.length" class="ExtensionDetailIssues">
            {{ extension.runtime_issues.join('；') }}
          </p>
        </section>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../../api'
import { useAdminRegistryStore } from '../../stores/adminRegistry'
import { useModalStore } from '../../stores/modal'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { resolveExtensionAdminComponent } from '../extensions/entryResolver'
import ApprovalQueuePage from './ApprovalQueuePage.vue'
import FlagsPage from './FlagsPage.vue'
import TagsPage from './TagsPage.vue'
import UsersPage from './UsersPage.vue'

const route = useRoute()
const adminRegistryStore = useAdminRegistryStore()
const modalStore = useModalStore()
const loading = ref(true)
const actionLoading = ref(false)
const errorMessage = ref('')
const extension = ref(null)
const detailComponent = ref(null)

const adminEntryModules = import.meta.glob('../../../../extensions/*/frontend/admin/index.js')
const builtinAdminEntries = {
  'builtin:approval': {
    resolveOperationsPage: () => ApprovalQueuePage,
  },
  'builtin:flags': {
    resolveOperationsPage: () => FlagsPage,
  },
  'builtin:tags': {
    resolveSettingsPage: () => TagsPage,
  },
  'builtin:users': {
    resolveOperationsPage: () => UsersPage,
  },
}

const actionItems = computed(() => {
  if (!extension.value) return []

  return [
    { label: '详情页', value: extension.value.action_links?.detail_page || '' },
    { label: '后台入口文件', value: extension.value.frontend_admin_entry || '' },
    { label: '设置入口', value: extension.value.action_links?.settings_page || '' },
    { label: '权限入口', value: extension.value.action_links?.permissions_page || '' },
    { label: '操作入口', value: extension.value.action_links?.operations_page || '' },
  ].filter(item => item.value)
})

const adminActions = computed(() => {
  return Array.isArray(extension.value?.admin_actions) ? extension.value.admin_actions : []
})

const runtimeActions = computed(() => {
  return Array.isArray(extension.value?.runtime_actions) ? extension.value.runtime_actions : []
})

const runtimeStatusClass = computed(() => {
  const key = extension.value?.runtime_status?.key
  if (key === 'active') return 'is-enabled'
  if (key === 'pending_install') return 'is-pending'
  return 'is-disabled'
})

onMounted(async () => {
  await loadExtension()
})

watch(
  () => route.params.extensionId,
  async () => {
    await loadExtension()
  }
)

async function loadExtension() {
  loading.value = true
  errorMessage.value = ''
  detailComponent.value = null

  try {
    const extensionId = String(route.params.extensionId || '').trim()
    const data = await api.get(`/admin/extensions/${extensionId}`)
    extension.value = data.extension || null
    detailComponent.value = await resolveExtensionAdminComponent(extension.value, 'detail', {
      importers: adminEntryModules,
      builtins: builtinAdminEntries,
    })
    syncModulesFromExtension(extension.value)
  } catch (error) {
    console.error('加载扩展详情失败:', error)
    errorMessage.value = error.response?.data?.error || '加载扩展详情失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function runRuntimeAction(action) {
  if (!extension.value || !action?.action) return

  if (action.confirm_message) {
    const confirmed = await modalStore.confirm({
      title: action.confirm_title || action.label,
      message: action.confirm_message,
      confirmText: action.confirm_text || action.label,
      cancelText: '取消',
      tone: action.tone === 'danger' ? 'danger' : 'primary',
    })
    if (!confirmed) {
      return
    }
  }

  actionLoading.value = true
  errorMessage.value = ''

  try {
    await api.post(`/admin/extensions/${extension.value.id}/${action.action}`)
    await loadExtension()
    if (action.success_message) {
      await modalStore.alert({
        title: action.label,
        message: action.success_message,
        tone: 'success',
      })
    }
  } catch (error) {
    console.error('执行扩展运行操作失败:', error)
    errorMessage.value = error.response?.data?.error || '执行扩展运行操作失败，请稍后重试'
  } finally {
    actionLoading.value = false
  }
}

function formatList(items) {
  return Array.isArray(items) && items.length ? items.join('、') : '无'
}

function resolveActionToneClass(action) {
  if (action?.tone === 'primary') {
    return 'ExtensionDetailAction--primary'
  }
  if (action?.tone === 'danger') {
    return 'ExtensionDetailAction--danger'
  }
  if (action?.tone === 'subtle') {
    return 'ExtensionDetailAction--subtle'
  }
  return ''
}

function syncModulesFromExtension(currentExtension) {
  if (!currentExtension || !Array.isArray(currentExtension.module_ids) || !currentExtension.module_ids.length) {
    return
  }

  adminRegistryStore.applyModules(
    currentExtension.module_ids.map(moduleId => ({
      id: moduleId,
      enabled: currentExtension.enabled !== false,
    }))
  )
}
</script>

<style scoped>
.ExtensionDetailPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ExtensionDetailPage-topbar,
.ExtensionDetailPage-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.ExtensionDetailPage-back,
.ExtensionDetailAction {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  text-decoration: none;
}

.ExtensionDetailAction {
  cursor: pointer;
  gap: 8px;
}

.ExtensionDetailAction--primary {
  border-color: var(--forum-primary-color);
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
}

.ExtensionDetailAction--subtle {
  background: transparent;
}

.ExtensionDetailAction--danger {
  border-color: #f0d0d0;
  background: #fff4f4;
  color: #b54747;
}

.ExtensionDetailPage-status {
  margin-left: auto;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}

.ExtensionDetailPage-status.is-enabled {
  background: rgba(40, 167, 69, 0.12);
  color: #1d7a36;
}

.ExtensionDetailPage-status.is-disabled {
  background: rgba(220, 53, 69, 0.12);
  color: #b02a37;
}

.ExtensionDetailPage-status.is-pending {
  background: rgba(245, 158, 11, 0.14);
  color: #9a5b00;
}

.ExtensionDetailPage-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.ExtensionDetailPage-summaryCard,
.ExtensionDetailCard {
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionDetailPage-pluginDetail {
  width: 100%;
}

.ExtensionDetailPage-summaryCard {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionDetailPage-summaryCard small,
.ExtensionDetailStack small,
.ExtensionDetailLinks span,
.ExtensionDetailMeta dt {
  color: var(--forum-text-soft);
}

.ExtensionDetailPage-summaryCard strong,
.ExtensionDetailStack strong,
.ExtensionDetailMeta dd {
  margin: 0;
  color: var(--forum-text-color);
}

.ExtensionDetailPage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.ExtensionDetailCard {
  padding: 18px;
}

.ExtensionDetailCard h3 {
  margin: 0 0 14px;
  font-size: 17px;
}

.ExtensionDetailMeta {
  display: grid;
  gap: 12px;
  margin: 0;
}

.ExtensionDetailMeta div {
  display: grid;
  gap: 4px;
}

.ExtensionDetailPills,
.ExtensionDetailLinks {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
  margin: 16px 0 0;
  list-style: none;
}

.ExtensionDetailPills li {
  display: inline-flex;
  align-self: flex-start;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--forum-bg-subtle);
}

.ExtensionDetailLinks li,
.ExtensionDetailStack div {
  display: grid;
  gap: 6px;
}

.ExtensionDetailLinks code {
  overflow-wrap: anywhere;
}

.ExtensionDetailStack {
  display: grid;
  gap: 14px;
}

.ExtensionDetailIssues {
  margin: 16px 0 0;
  color: #b02a37;
}

@media (max-width: 900px) {
  .ExtensionDetailPage-grid {
    grid-template-columns: 1fr;
  }

  .ExtensionDetailPage-status {
    margin-left: 0;
  }
}
</style>
