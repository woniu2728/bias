<template>
  <AdminPage
    class-name="ExtensionsPage"
    icon="fas fa-plug"
    title="扩展中心"
    description="查看扩展清单、状态、依赖与后台入口，为后续启停和独立设置页打底。"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展信息中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else class="ExtensionsPage-content">
      <AdminStateBlock v-if="recoveryNotice" :tone="recoveryNotice.tone">
        {{ recoveryNotice.text }}
      </AdminStateBlock>

      <section class="ExtensionsPage-summary">
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.extension_count ?? extensions.length }}</strong>
          <span>扩展总数</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.enabled_count ?? 0 }}</strong>
          <span>已启用</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.healthy_count ?? 0 }}</strong>
          <span>健康</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.blocking_count ?? 0 }}</strong>
          <span>阻断项</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.warning_count ?? 0 }}</strong>
          <span>告警项</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.frontend_bundle_count ?? 0 }}</strong>
          <span>前端交付</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.migration_bundle_count ?? 0 }}</strong>
          <span>迁移交付</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.filesystem_count ?? 0 }}</strong>
          <span>目录扩展</span>
        </article>
      </section>

      <AdminToolbar class="ExtensionsPage-toolbar" align="between">
        <div class="ExtensionsPage-toolbarGroup">
          <AdminFilterTabs v-model="sourceFilter" :options="sourceOptions" />
          <AdminFilterTabs v-model="statusFilter" :options="statusOptions" />
        </div>
        <div class="ExtensionsPage-toolbarActions">
          <button
            type="button"
            class="ExtensionAction ExtensionAction--subtle"
            :disabled="syncLoading"
            @click="syncExtensionPackages"
          >
            <i class="fas fa-rotate"></i>
            <span>{{ syncLoading ? '同步中...' : '同步扩展' }}</span>
          </button>
          <button
            type="button"
            class="ExtensionAction ExtensionAction--subtle"
            :disabled="orderSyncLoading"
            @click="syncEnabledOrder"
          >
            <i class="fas fa-arrow-down-short-wide"></i>
            <span>{{ orderSyncLoading ? '排序中...' : '同步顺序' }}</span>
          </button>
          <button
            type="button"
            class="ExtensionAction ExtensionAction--subtle"
            :disabled="frontendRebuildLoading"
            @click="rebuildFrontendAssets"
          >
            <i class="fas fa-screwdriver-wrench"></i>
            <span>{{ frontendRebuildLoading ? '重建中...' : '重建前端' }}</span>
          </button>
          <label class="ExtensionsPage-search">
            <span class="sr-only">搜索扩展</span>
            <input
              v-model.trim="searchQuery"
              class="FormControl"
              type="search"
              placeholder="搜索扩展名、ID、能力或依赖"
            />
          </label>
        </div>
      </AdminToolbar>

      <AdminStateBlock v-if="packageLockNotice" :tone="packageLockNotice.tone">
        {{ packageLockNotice.text }}
      </AdminStateBlock>

      <div v-if="filteredExtensions.length" class="ExtensionsPage-list">
        <article
          v-for="extension in filteredExtensions"
          :key="extension.id"
          class="ExtensionCard"
          :class="{ 'is-disabled': !extension.enabled, 'is-busy': isExtensionActionLoading(extension) }"
        >
          <div v-if="isExtensionActionLoading(extension)" class="ExtensionCard-progress" aria-hidden="true"></div>
          <div class="ExtensionCard-main">
            <span class="ExtensionCard-icon">
              <i :class="extension.icon || 'fas fa-puzzle-piece'"></i>
            </span>

            <div class="ExtensionCard-content">
              <div class="ExtensionCard-title">
                <h3>{{ extension.name }}</h3>
                <span class="ExtensionBadge">{{ extension.id }}</span>
                <span class="ExtensionStatus" :class="resolveRuntimeStatusClass(extension)">
                  {{ extension.runtime_status?.label || (extension.enabled ? '已启用' : '未启用') }}
                </span>
                <span
                  v-if="isExtensionActionLoading(extension)"
                  class="ExtensionStatus is-working"
                >
                  {{ resolveRuntimeActionProgressLabel(extension) }}
                </span>
                <span
                  v-if="extension.distribution?.abandoned"
                  class="ExtensionStatus is-warning"
                >
                  已废弃
                </span>
                <span
                  v-if="hasMigrationPlan(extension)"
                  class="ExtensionStatus"
                  :class="resolveMigrationStatusClass(extension)"
                >
                  {{ resolveExtensionMigrationState(extension) }}
                </span>
                <span
                  v-for="badge in resolveDiagnosticsBadges(extension)"
                  :key="`${extension.id}-${badge.key}`"
                  class="ExtensionStatus"
                  :class="resolveDiagnosticsBadgeClass(badge)"
                >
                  {{ badge.label }}
                </span>
                <span
                  v-if="resolveRecoveryBadge(extension)"
                  class="ExtensionStatus"
                  :class="resolveRecoveryBadge(extension).className"
                >
                  {{ resolveRecoveryBadge(extension).label }}
                </span>
                <span
                  v-if="resolveFrontendAssetBadge(extension)"
                  class="ExtensionStatus"
                  :class="resolveFrontendAssetBadge(extension).className"
                >
                  {{ resolveFrontendAssetBadge(extension).label }}
                </span>
              </div>

              <p class="ExtensionCard-description">{{ extension.description || '暂无描述' }}</p>

              <ul v-if="resolveDiagnosticsPreview(extension).length" class="ExtensionCard-diagnostics">
                <li
                  v-for="item in resolveDiagnosticsPreview(extension)"
                  :key="item.key"
                  :class="resolveDiagnosticsItemClass(item)"
                >
                  {{ item.text }}
                </li>
              </ul>

              <div class="ExtensionCard-meta">
                <span><strong>版本</strong> {{ extension.version }}</span>
                <span><strong>来源</strong> {{ extension.source }}</span>
                <span><strong>前台</strong> {{ resolveExtensionForumEntryState(extension) }}</span>
                <span v-if="hasMigrationPlan(extension)"><strong>迁移</strong> {{ resolveMigrationMetaText(extension) }}</span>
                <span v-if="extension.dependencies.length"><strong>依赖</strong> {{ extension.dependencies.join('、') }}</span>
                <span v-if="extension.module_ids.length"><strong>模块</strong> {{ extension.module_ids.join('、') }}</span>
              </div>

              <div v-if="extension.provides.length" class="ExtensionCard-tokens">
                <span v-for="capability in extension.provides" :key="`${extension.id}-${capability}`" class="ExtensionToken">
                  {{ capability }}
                </span>
              </div>

              <div v-if="resolveAdminPageLinks(extension).length" class="ExtensionCard-adminPages">
                <span class="ExtensionCard-adminPagesLabel">后台页</span>
                <div class="ExtensionCard-adminPagesList">
                  <router-link
                    v-for="page in resolveAdminPageLinks(extension).slice(0, 2)"
                    :key="`${extension.id}-page-${page.key}`"
                    :to="buildRouteTarget(page.target)"
                    class="ExtensionToken"
                  >
                    {{ page.label }}
                  </router-link>
                  <span
                    v-if="resolveAdminPageLinks(extension).length > 2"
                    class="ExtensionToken"
                  >
                    +{{ resolveAdminPageLinks(extension).length - 2 }}
                  </span>
                </div>
              </div>
            </div>

            <div class="ExtensionCard-side">
              <template v-for="action in getVisibleAdminActions(extension)" :key="`${extension.id}-${action.key}`">
                <router-link
                  v-if="action.kind === 'route'"
                  :to="buildRouteTarget(action.target)"
                  class="ExtensionAction"
                  :class="resolveActionToneClass(action)"
                >
                  <i v-if="action.icon" :class="action.icon"></i>
                  <span>{{ action.label }}</span>
                </router-link>
                <a
                  v-else
                  :href="action.target"
                  class="ExtensionAction"
                  :class="resolveActionToneClass(action)"
                  :target="action.opens_in_new_tab ? '_blank' : null"
                  :rel="action.opens_in_new_tab ? 'noreferrer noopener' : null"
                >
                  <i v-if="action.icon" :class="action.icon"></i>
                  <span>{{ action.label }}</span>
                </a>
              </template>

              <span class="ExtensionLifecycle">
                {{ extension.lifecycle?.registration_mode_label || '静态注册' }}
              </span>

              <button
                v-for="action in getRuntimeActions(extension)"
                :key="`${extension.id}-runtime-${action.key}`"
                type="button"
                class="ExtensionAction"
                :class="[resolveActionToneClass(action), { 'is-loading': isRuntimeActionLoading(extension, action) }]"
                :disabled="isExtensionActionLoading(extension)"
                @click="runRuntimeAction(extension, action)"
              >
                <span v-if="isRuntimeActionLoading(extension, action)" class="ExtensionAction-spinner" aria-hidden="true"></span>
                <span>{{ resolveRuntimeActionButtonLabel(extension, action) }}</span>
              </button>
            </div>
          </div>
        </article>
      </div>

      <AdminStateBlock v-else tone="subtle">当前筛选下没有匹配的扩展。</AdminStateBlock>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../../api'
import { useAdminRegistryStore } from '../../stores/adminRegistry'
import { useModalStore } from '../../stores/modal'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'
import {
  buildExtensionRouteTarget,
  resolveExtensionAdminPageCards,
  resolveExtensionDiagnosticsBadges,
  resolveExtensionDiagnosticsPreview,
  resolveExtensionForumEntryState,
  resolveExtensionMigrationState,
  resolveExtensionPrimaryAdminAction,
} from '../extensions/diagnostics'

const adminRegistryStore = useAdminRegistryStore()
const modalStore = useModalStore()
const loading = ref(true)
const errorMessage = ref('')
const summary = ref({})
const runtime = ref({})
const extensions = ref([])
const sourceFilter = ref('all')
const statusFilter = ref('all')
const searchQuery = ref('')
const actionLoadingId = ref('')
const actionLoadingKey = ref('')
const syncLoading = ref(false)
const orderSyncLoading = ref(false)
const frontendRebuildLoading = ref(false)

const packageLock = computed(() => runtime.value?.package_lock || {})

const frontendAssetSummary = computed(() => {
  const states = extensions.value
    .map(item => item?.frontend_asset_state || {})
    .filter(state => state.has_frontend)
  return {
    total: states.length,
    requiresRebuild: states.filter(state => state.requires_rebuild).length,
    missing: states.filter(state => !state.manifest_exists || !state.compiled).length,
  }
})

const packageLockNotice = computed(() => {
  const summary = packageLock.value?.summary || {}
  const missing = Number(summary.missing_count || 0)
  const versionDrift = Number(summary.version_drift_count || 0)
  const sourceDrift = Number(summary.source_drift_count || 0)
  const unmanaged = Number(summary.unmanaged_discovered_count || 0)
  const locked = Number(summary.locked_count || 0)
  const enabledOrder = packageLock.value?.enabled_order || {}
  const orderDrift = Boolean(enabledOrder.drift)
  const staleOrderCount = Array.isArray(enabledOrder.stale) ? enabledOrder.stale.length : 0
  if (missing || versionDrift || sourceDrift || unmanaged || orderDrift) {
    const parts = []
    if (missing) parts.push(`缺失 ${missing}`)
    if (versionDrift) parts.push(`版本漂移 ${versionDrift}`)
    if (sourceDrift) parts.push(`来源漂移 ${sourceDrift}`)
    if (unmanaged) parts.push(`未安装发现 ${unmanaged}`)
    if (orderDrift) parts.push(staleOrderCount ? `启用顺序漂移 ${staleOrderCount} 个过期项` : '启用顺序漂移')
    return {
      tone: 'warning',
      text: `扩展包状态需要关注：${parts.join('、')}。`,
    }
  }
  const frontend = frontendAssetSummary.value
  if (frontend.requiresRebuild || frontend.missing) {
    const parts = []
    if (frontend.requiresRebuild) parts.push(`待重建 ${frontend.requiresRebuild}`)
    if (frontend.missing) parts.push(`未生成 ${frontend.missing}`)
    return {
      tone: 'warning',
      text: `扩展前端资源需要处理：${parts.join('、')}。`,
    }
  }
  if (locked) {
    return {
      tone: 'subtle',
      text: `扩展包锁定已同步，共 ${locked} 个包记录。`,
    }
  }
  return null
})

const recoveryNotice = computed(() => {
  const recovery = runtime.value?.recovery || {}
  if (recovery?.bisect?.active) {
    const current = Array.isArray(recovery.bisect.current) ? recovery.bisect.current.join('、') : ''
    return {
      tone: 'warning',
      text: current
        ? `扩展二分排查进行中，当前只启动：${current}`
        : '扩展二分排查进行中，当前启用集合已被临时调整。',
    }
  }
  if (recovery.safe_mode) {
    const allowed = Array.isArray(recovery.safe_mode_extensions) ? recovery.safe_mode_extensions.join('、') : ''
    return {
      tone: 'warning',
      text: allowed
        ? `扩展恢复模式已启用，只启动核心能力和白名单扩展：${allowed}`
        : '扩展恢复模式已启用，当前只启动核心能力。',
    }
  }
  return null
})

const sourceOptions = [
  { value: 'all', label: '全部来源', icon: 'fas fa-layer-group' },
  { value: 'filesystem', label: '目录扩展', icon: 'fas fa-folder-open' },
]

const statusOptions = [
  { value: 'all', label: '全部状态', icon: 'fas fa-border-all' },
  { value: 'enabled', label: '已启用', icon: 'fas fa-toggle-on' },
  { value: 'disabled', label: '未启用', icon: 'fas fa-toggle-off' },
]

const filteredExtensions = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()

  return [...extensions.value]
    .filter(item => {
      if (sourceFilter.value !== 'all' && item.source !== sourceFilter.value) {
        return false
      }
      if (statusFilter.value === 'enabled' && !item.enabled) {
        return false
      }
      if (statusFilter.value === 'disabled' && item.enabled) {
        return false
      }

      if (!keyword) return true

      const haystack = [
        item.id,
        item.name,
        item.description,
        item.distribution?.abandoned ? '已废弃 abandoned deprecated' : '',
        item.distribution?.replacement,
        ...(item.dependencies || []),
        ...(item.provides || []),
        ...(item.module_ids || []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return haystack.includes(keyword)
    })
    .sort((left, right) => {
      if (Boolean(left.enabled) !== Boolean(right.enabled)) return left.enabled ? -1 : 1
      return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
    })
})

onMounted(async () => {
  await loadExtensions()
})

async function loadExtensions() {
  loading.value = true
  errorMessage.value = ''

  try {
    const data = await api.get('/admin/extensions')
    applyPayload(data)
  } catch (error) {
    console.error('加载扩展信息失败:', error)
    errorMessage.value = error.response?.data?.error || '加载扩展信息失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function applyPayload(data) {
  if (data.summary) {
    summary.value = data.summary
  }
  if (data.runtime) {
    runtime.value = data.runtime
  }
  if (Array.isArray(data.extensions)) {
    extensions.value = data.extensions.filter(item => item?.product_visible !== false)
  } else if (data.extension && typeof data.extension === 'object') {
    applySingleExtensionUpdate(data.extension)
  }
  const moduleEntries = extensions.value.flatMap(extension => {
    const moduleIds = Array.isArray(extension.module_ids) ? extension.module_ids : []
    return moduleIds.map(moduleId => ({
      id: moduleId,
      enabled: extension.enabled !== false,
    }))
  })
  if (moduleEntries.length) {
    adminRegistryStore.applyExtensionScopes(moduleEntries)
  }
}

function applySingleExtensionUpdate(extension) {
  const currentExtensions = Array.isArray(extensions.value) ? extensions.value : []
  const extensionId = String(extension.id || '').trim()
  if (!extensionId) {
    return
  }

  const index = currentExtensions.findIndex(item => String(item?.id || '').trim() === extensionId)
  const nextExtension = {
    ...(index >= 0 ? currentExtensions[index] : {}),
    ...extension,
  }

  if (nextExtension.product_visible === false) {
    extensions.value = currentExtensions.filter(item => String(item?.id || '').trim() !== extensionId)
    return
  }

  if (index >= 0) {
    extensions.value = currentExtensions.map((item, itemIndex) => (
      itemIndex === index ? nextExtension : item
    ))
  } else {
    extensions.value = [...currentExtensions, nextExtension]
  }
}

async function runRuntimeAction(extension, action) {
  if (!extension?.id || !action?.action) return

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

  actionLoadingId.value = extension.id
  actionLoadingKey.value = String(action.key || action.action || '')
  errorMessage.value = ''

  try {
    const data = action.action.startsWith('hook:')
      ? await api.post(`/admin/extensions/${extension.id}/runtime-hooks/${action.action.slice(5)}`)
      : await api.post(`/admin/extensions/${extension.id}/${action.action}`)
    applyPayload(data)
    if (action.success_message) {
      await modalStore.alert({
        title: action.label,
        message: action.success_message,
        tone: 'success',
      })
    }
  } catch (error) {
    console.error('切换扩展状态失败:', error)
    errorMessage.value = error.response?.data?.error || '切换扩展状态失败，请稍后重试'
  } finally {
    actionLoadingId.value = ''
    actionLoadingKey.value = ''
  }
}

function isExtensionActionLoading(extension) {
  return Boolean(extension?.id) && actionLoadingId.value === extension.id
}

function isRuntimeActionLoading(extension, action) {
  if (!isExtensionActionLoading(extension)) {
    return false
  }
  const key = String(action?.key || action?.action || '')
  return !actionLoadingKey.value || actionLoadingKey.value === key
}

function resolveRuntimeActionProgressLabel(extension) {
  const action = getRuntimeActions(extension).find(item => {
    const key = String(item?.key || item?.action || '')
    return key && key === actionLoadingKey.value
  })
  return resolveRuntimeActionLoadingText(action)
}

function resolveRuntimeActionButtonLabel(extension, action) {
  if (!isRuntimeActionLoading(extension, action)) {
    return action?.label || '执行'
  }
  return resolveRuntimeActionLoadingText(action)
}

function resolveRuntimeActionLoadingText(action) {
  const actionName = String(action?.action || '').trim()
  if (actionName === 'enable') {
    return '正在启用'
  }
  if (actionName === 'disable') {
    return '正在停用'
  }
  if (actionName === 'install') {
    return '正在安装'
  }
  if (actionName === 'uninstall') {
    return '正在卸载'
  }
  if (actionName === 'migrations') {
    return '执行迁移'
  }
  if (actionName.startsWith('hook:')) {
    return '执行操作'
  }
  return '处理中'
}

async function syncExtensionPackages() {
  syncLoading.value = true
  errorMessage.value = ''

  try {
    const data = await api.post('/admin/extensions/sync', { prune_missing: true })
    applyPayload(data)
  } catch (error) {
    console.error('同步扩展包状态失败:', error)
    errorMessage.value = error.response?.data?.error || '同步扩展包状态失败，请稍后重试'
  } finally {
    syncLoading.value = false
  }
}

async function syncEnabledOrder() {
  orderSyncLoading.value = true
  errorMessage.value = ''

  try {
    const data = await api.post('/admin/extensions/sync-order')
    applyPayload(data)
  } catch (error) {
    console.error('同步扩展启用顺序失败:', error)
    errorMessage.value = error.response?.data?.error || '同步扩展启用顺序失败，请稍后重试'
  } finally {
    orderSyncLoading.value = false
  }
}

async function rebuildFrontendAssets() {
  frontendRebuildLoading.value = true
  errorMessage.value = ''

  try {
    const data = await api.post('/admin/extensions/rebuild-frontend', {
      run_build: true,
      include_disabled: false,
      publish: false,
    })
    applyPayload(data)
  } catch (error) {
    console.error('重建扩展前端资源失败:', error)
    errorMessage.value = error.response?.data?.error || '重建扩展前端资源失败，请稍后重试'
  } finally {
    frontendRebuildLoading.value = false
  }
}

function getVisibleAdminActions(extension) {
  const actions = Array.isArray(extension?.admin_actions) ? extension.admin_actions : []
  const pageTargets = new Set(resolveAdminPageLinks(extension).map(item => item.target))
  const primaryAction = resolveExtensionPrimaryAdminAction(extension)

  return actions.filter((action) => {
    if (action?.kind !== 'route') {
      return true
    }
    if (primaryAction && action.key === primaryAction.key) {
      return true
    }
    if (action?.key === 'details' || action?.key === 'documentation') {
      return true
    }
    return !pageTargets.has(String(action?.target || '').trim())
  })
}

function getRuntimeActions(extension) {
  return Array.isArray(extension?.runtime_actions) ? extension.runtime_actions : []
}

function buildRouteTarget(path) {
  return buildExtensionRouteTarget(path, 'extensions')
}

function resolveActionToneClass(action) {
  if (action?.tone === 'primary') {
    return 'ExtensionAction--primary'
  }
  if (action?.tone === 'danger') {
    return 'ExtensionAction--danger'
  }
  if (action?.tone === 'subtle') {
    return 'ExtensionAction--subtle'
  }
  return ''
}

function resolveRuntimeStatusClass(extension) {
  const key = extension?.runtime_status?.key
  if (key === 'active') return 'is-enabled'
  if (key === 'pending_install') return 'is-pending'
  return 'is-disabled'
}

function hasMigrationPlan(extension) {
  return Boolean(extension?.migration_plan)
}

function resolveMigrationStatusClass(extension) {
  const state = resolveExtensionMigrationState(extension)
  if (state === '已同步') return 'is-enabled'
  if (state === '待执行' || state === '有更新') return 'is-pending'
  return 'is-disabled'
}

function resolveDiagnosticsBadges(extension) {
  return resolveExtensionDiagnosticsBadges(extension)
}

function resolveDiagnosticsPreview(extension) {
  return resolveExtensionDiagnosticsPreview(extension)
}

function resolveDiagnosticsBadgeClass(item) {
  if (item?.tone === 'danger') {
    return 'is-danger'
  }
  if (item?.tone === 'warning') {
    return 'is-warning'
  }
  return 'is-disabled'
}

function resolveRecoveryBadge(extension) {
  const status = extension?.recovery_status || {}
  if (status.bisect_culprit) {
    return { label: '二分命中', className: 'is-danger' }
  }
  if (status.bisect_active && status.bisect_candidate) {
    return status.bisect_current
      ? { label: '二分启用', className: 'is-warning' }
      : { label: '二分停用', className: 'is-disabled' }
  }
  if (status.safe_mode && !status.safe_mode_allowed) {
    return { label: '恢复模式停用', className: 'is-warning' }
  }
  return null
}

function resolveFrontendAssetBadge(extension) {
  const state = extension?.frontend_asset_state || {}
  if (!state.has_frontend) {
    return null
  }
  if (state.requires_rebuild) {
    return { label: '前端待重建', className: 'is-warning' }
  }
  if (!state.manifest_exists || !state.compiled) {
    return { label: '前端未生成', className: 'is-warning' }
  }
  return { label: '前端已生成', className: 'is-enabled' }
}

function resolveDiagnosticsItemClass(item) {
  return item?.tone === 'danger' ? 'is-danger' : 'is-warning'
}

function resolveMigrationMetaText(extension) {
  const plan = extension?.migration_plan || {}
  const declaredFiles = Array.isArray(plan.declared_files) ? plan.declared_files : []
  const appliedFiles = Array.isArray(plan.applied_files) ? plan.applied_files : []
  const pendingFiles = Array.isArray(plan.pending_files) ? plan.pending_files : []

  if (pendingFiles.length) {
    return `${pendingFiles.length} 个待执行`
  }
  if (appliedFiles.length) {
    return `${appliedFiles.length} 个已执行`
  }
  if (declaredFiles.length) {
    return `${declaredFiles.length} 个已声明`
  }
  return '未声明'
}

function resolveAdminPageLinks(extension) {
  return resolveExtensionAdminPageCards(extension)
}
</script>

<style scoped>
.ExtensionsPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ExtensionsPage-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.ExtensionsPage-summaryCard {
  padding: 16px 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-subtle);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ExtensionsPage-summaryCard strong {
  color: var(--forum-text-color);
  font-size: 22px;
}

.ExtensionsPage-summaryCard span {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.ExtensionsPage-toolbar {
  gap: 16px;
}

.ExtensionsPage-toolbarGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ExtensionsPage-toolbarActions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.ExtensionsPage-search {
  min-width: min(320px, 100%);
}

.ExtensionsPage-search .FormControl {
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
}

.ExtensionsPage-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ExtensionCard {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionCard.is-disabled {
  opacity: 0.8;
}

.ExtensionCard.is-busy {
  border-color: #cfe0f2;
  box-shadow: 0 10px 24px rgb(50 91 133 / 12%);
}

.ExtensionCard-progress {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  overflow: hidden;
  background: #e7f0f9;
}

.ExtensionCard-progress::after {
  content: "";
  position: absolute;
  top: 0;
  left: -35%;
  width: 35%;
  height: 100%;
  border-radius: 999px;
  background: #3b73a8;
  animation: extension-progress 1.1s ease-in-out infinite;
}

.ExtensionCard-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  align-items: flex-start;
  padding: 18px;
}

.ExtensionCard-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #eef5fb;
  color: #426789;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}

.ExtensionCard-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ExtensionCard-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ExtensionCard-title h3 {
  margin: 0;
  color: var(--forum-text-color);
  font-size: 17px;
}

.ExtensionBadge,
.ExtensionStatus,
.ExtensionToken {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.ExtensionBadge {
  padding: 5px 9px;
  background: #eef2f6;
  color: #5c6b7c;
}

.ExtensionStatus {
  padding: 5px 10px;
}

.ExtensionStatus.is-enabled {
  background: #edf8f2;
  color: #25704d;
}

.ExtensionStatus.is-disabled {
  background: #f5f7fa;
  color: #6c7988;
}

.ExtensionStatus.is-pending {
  background: #fff6e8;
  color: #9a5b00;
}

.ExtensionStatus.is-danger {
  background: #fff1f1;
  color: #b54747;
}

.ExtensionStatus.is-warning {
  background: #fff6e8;
  color: #9a5b00;
}

.ExtensionStatus.is-working {
  background: #edf4fb;
  color: #325b85;
}

.ExtensionCard-description {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionCard-diagnostics {
  display: grid;
  gap: 6px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.ExtensionCard-diagnostics li {
  padding: 8px 10px;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.ExtensionCard-diagnostics li.is-danger {
  border-color: #f2d4d4;
  background: #fff7f7;
  color: #b54747;
}

.ExtensionCard-diagnostics li.is-warning {
  border-color: #f4e1bc;
  background: #fffaf1;
  color: #9a5b00;
}

.ExtensionCard-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--forum-text-soft);
  font-size: 13px;
}

.ExtensionCard-meta strong {
  margin-right: 4px;
  color: var(--forum-text-muted);
}

.ExtensionCard-tokens {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ExtensionCard-adminPages {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ExtensionCard-adminPagesLabel {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 700;
}

.ExtensionCard-adminPagesList {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ExtensionToken {
  padding: 5px 9px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.ExtensionCard-side {
  min-width: 132px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.ExtensionAction {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
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

.ExtensionAction.is-loading {
  min-width: 92px;
  cursor: wait;
}

.ExtensionAction-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 999px;
  animation: extension-spin 0.75s linear infinite;
}

.ExtensionAction--primary {
  background: #edf4fb;
  border-color: #d6e4f3;
  color: #325b85;
}

.ExtensionAction--subtle {
  background: transparent;
}

.ExtensionAction--danger {
  background: #fff4f4;
  border-color: #f0d0d0;
  color: #b54747;
}

.ExtensionLifecycle {
  color: var(--forum-text-soft);
  font-size: 12px;
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

@keyframes extension-progress {
  0% {
    transform: translateX(0);
  }

  100% {
    transform: translateX(390%);
  }
}

@keyframes extension-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ExtensionCard-progress::after,
  .ExtensionAction-spinner {
    animation-duration: 1.8s;
  }
}

@media (max-width: 768px) {
  .ExtensionsPage-toolbarGroup {
    flex-direction: column;
  }

  .ExtensionCard-main {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .ExtensionCard-side {
    grid-column: 1 / -1;
    min-width: 0;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
