<template>
  <AdminPage
    class-name="ExtensionDetailPage"
    :icon="extension?.icon || 'fas fa-puzzle-piece'"
    :title="extension?.name || '扩展详情'"
    :description="extension?.description || '查看扩展设置、权限与运行状态。'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展详情中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage && !extension" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else-if="extension" class="ExtensionDetailPage-content">
      <div v-if="actionLoading" class="ExtensionDetailProgress" aria-hidden="true"></div>
      <AdminStateBlock v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

      <AdminStateBlock v-if="recoveryNotice" :tone="recoveryNotice.tone">
        {{ recoveryNotice.text }}
      </AdminStateBlock>
      <AdminStateBlock v-if="distributionNotice" tone="warning">
        {{ distributionNotice }}
      </AdminStateBlock>

      <section class="ExtensionDetailPage-header" :class="{ 'is-busy': actionLoading }">
        <div class="ExtensionDetailPage-summaryBar">
          <div class="ExtensionDetailPage-summaryMain">
            <button
              v-if="primaryToggleAction"
              type="button"
              class="ExtensionDetailToggle"
              :class="[
                extension.enabled ? 'is-enabled' : 'is-disabled',
                { 'is-loading': actionLoading },
              ]"
              :disabled="actionLoading"
              @click="runRuntimeAction(primaryToggleAction)"
            >
              <span class="ExtensionDetailToggle-track">
                <span class="ExtensionDetailToggle-thumb"></span>
              </span>
              <span v-if="actionLoading" class="ExtensionDetailAction-spinner" aria-hidden="true"></span>
              <span>{{ actionLoading ? currentRuntimeActionLoadingText : (extension.enabled ? '已启用' : '未启用') }}</span>
            </button>

            <span v-else class="ExtensionDetailPage-status" :class="runtimeStatusClass">
              {{ extension.runtime_status?.label || (extension.enabled ? '已启用' : '未启用') }}
            </span>
          </div>

          <div class="ExtensionDetailPage-summaryMeta">
            <span class="ExtensionDetailPage-version">v{{ extension.version || '0.0.0' }}</span>

            <div v-if="infoLinks.length" class="ExtensionDetailPage-links">
              <a
                v-for="link in infoLinks"
                :key="link.key"
                :href="link.target"
                class="ExtensionDetailPage-link"
                target="_blank"
                rel="noreferrer noopener"
              >
                <i :class="link.icon"></i>
                <span>{{ link.label }}</span>
              </a>
            </div>
          </div>
        </div>
      </section>

      <AdminStateBlock
        v-if="!extension.enabled"
        tone="subtle"
      >
        启用扩展后可查看设置和权限。
      </AdminStateBlock>

      <component
        :is="detailComponent"
        v-if="extension.enabled && detailComponent"
        :extension="extension"
        surface="detail"
        class="ExtensionDetailPage-pluginDetail"
      />

      <section v-if="extension.readme?.available && extension.readme?.html" class="ExtensionDetailSection">
        <div class="ExtensionDetailSection-header">
          <h3>文档</h3>
        </div>
        <article class="ExtensionDetailPage-readme" v-html="extension.readme.html"></article>
      </section>

      <section v-if="extension.enabled && settingsComponent" class="ExtensionDetailSection">
        <div class="ExtensionDetailSection-header">
          <h3>设置</h3>
          <router-link
            v-if="extension.action_links?.settings_page && !inlineSettings"
            :to="buildExtensionRouteTarget(extension.action_links.settings_page, route)"
            class="ExtensionDetailSection-link"
          >
            打开设置页
          </router-link>
        </div>
        <component
          :is="settingsComponent"
          :extension="extension"
          host-kind="settings"
          @extension-updated="handleExtensionUpdated"
        />
        <p v-if="!inlineSettings" class="ExtensionDetailSection-empty">
          当前扩展没有可内嵌的设置项。
        </p>
      </section>

      <section v-if="extension.enabled && permissionsComponent" class="ExtensionDetailSection">
        <div class="ExtensionDetailSection-header">
          <h3>权限</h3>
          <router-link
            v-if="extension.action_links?.permissions_page && !inlinePermissions"
            :to="buildExtensionRouteTarget(extension.action_links.permissions_page, route)"
            class="ExtensionDetailSection-link"
          >
            打开权限页
          </router-link>
        </div>
        <component
          :is="permissionsComponent"
          :extension="extension"
          host-kind="permissions"
          @extension-updated="handleExtensionUpdated"
        />
      </section>

      <section v-if="visibleActions.length" class="ExtensionDetailSection">
        <div class="ExtensionDetailSection-header">
          <h3>操作</h3>
        </div>

        <div class="ExtensionDetailPage-actions">
          <template v-for="action in visibleAdminActions" :key="action.key">
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
            v-for="action in visibleRuntimeActions"
            :key="`runtime-${action.key}`"
            type="button"
            class="ExtensionDetailAction"
            :class="[resolveActionToneClass(action), { 'is-loading': isRuntimeActionLoading(action) }]"
            :disabled="actionLoading"
            @click="runRuntimeAction(action)"
          >
            <span v-if="isRuntimeActionLoading(action)" class="ExtensionDetailAction-spinner" aria-hidden="true"></span>
            <span>{{ isRuntimeActionLoading(action) ? currentRuntimeActionLoadingText : action.label }}</span>
          </button>
        </div>
      </section>
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
import { resolveFallbackExtensionPermissionsPage, resolveFallbackExtensionSettingsPage } from '../extensions/fallbacks'
import { buildExtensionRouteTarget } from '../extensions/diagnostics'
import { generatedAdminExtensionModules } from 'virtual:bias-extension-import-map'

const route = useRoute()
const adminRegistryStore = useAdminRegistryStore()
const modalStore = useModalStore()
const loading = ref(true)
const actionLoading = ref(false)
const currentActionKey = ref('')
const currentActionName = ref('')
const errorMessage = ref('')
const extension = ref(null)
const detailComponent = ref(null)
const settingsComponent = ref(null)
const permissionsComponent = ref(null)

const adminEntryModules = {
  ...import.meta.glob('../../../../extensions/*/frontend/admin/index.js'),
  ...generatedAdminExtensionModules,
}

const infoLinks = computed(() => {
  const standardLinks = extension.value?.links && typeof extension.value.links === 'object'
    ? extension.value.links
    : {}
  const labels = {
    documentation: '文档',
    website: '网站',
    discuss: '讨论',
    support: '支持',
    source: '源码',
    donate: '赞助',
  }
  const icons = {
    documentation: 'fas fa-book',
    website: 'fas fa-globe',
    discuss: 'fas fa-comments',
    support: 'fas fa-life-ring',
    source: 'fas fa-code-branch',
    donate: 'fas fa-heart',
  }
  const links = Object.entries(standardLinks)
    .filter(([key, target]) => labels[key] && typeof target === 'string' && target)
    .map(([key, target]) => ({
      key,
      label: labels[key],
      target,
      icon: icons[key] || 'fas fa-link',
    }))
  const actions = Array.isArray(extension.value?.admin_actions) ? extension.value.admin_actions : []
  const allowedKeys = new Set(['documentation', 'website', 'discuss', 'support', 'source', 'donate'])
  const actionLinks = actions
    .filter(action => action?.kind === 'link' && action?.target && allowedKeys.has(action.key))
    .filter(action => !links.some(link => link.key === action.key))
    .map(action => ({
      key: action.key,
      label: action.label,
      target: action.target,
      icon: action.icon || 'fas fa-link',
    }))
  return [...links, ...actionLinks]
})

const adminActions = computed(() => {
  const actions = Array.isArray(extension.value?.admin_actions) ? extension.value.admin_actions : []
  return actions.map((action) => {
    if (action?.kind !== 'route') {
      return action
    }
    return {
      ...action,
      target: buildExtensionRouteTarget(action.target, route),
    }
  })
})

const runtimeActions = computed(() => (
  Array.isArray(extension.value?.runtime_actions) ? extension.value.runtime_actions : []
))

const inlineSettings = computed(() => (
  isInlineSurfaceSupported(extension.value, 'settings')
  || hasExtensionSettingsPage(extension.value)
))

const inlinePermissions = computed(() => (
  isInlineSurfaceSupported(extension.value, 'permissions')
))

const primaryToggleAction = computed(() => (
  runtimeActions.value.find(action => ['enable', 'disable'].includes(action?.action)) || null
))

const currentRuntimeActionLoadingText = computed(() => {
  if (currentActionName.value) {
    return resolveRuntimeActionLoadingText({ action: currentActionName.value })
  }
  const action = runtimeActions.value.find(item => {
    const key = String(item?.key || item?.action || '')
    return key && key === currentActionKey.value
  }) || primaryToggleAction.value
  return resolveRuntimeActionLoadingText(action)
})

const visibleRuntimeActions = computed(() => (
  runtimeActions.value.filter(action => action !== primaryToggleAction.value)
))

const visibleAdminActions = computed(() => (
  adminActions.value.filter(action => {
    if (action?.kind === 'link' && infoLinks.value.some(link => link.key === action.key)) {
      return false
    }
    if (action?.key === 'details') {
      return false
    }
    if (action?.key === 'settings' && inlineSettings.value) {
      return false
    }
    if (action?.key === 'permissions' && inlinePermissions.value) {
      return false
    }
    return true
  })
))

const visibleActions = computed(() => (
  [...visibleAdminActions.value, ...visibleRuntimeActions.value]
))

const runtimeStatusClass = computed(() => {
  const key = extension.value?.runtime_status?.key
  if (key === 'active') return 'is-enabled'
  if (key === 'pending_install') return 'is-pending'
  return 'is-disabled'
})

const recoveryNotice = computed(() => {
  const status = extension.value?.recovery_status || {}
  if (status.bisect_culprit) {
    return { tone: 'danger', text: '扩展二分排查已命中该扩展，请检查其运行时能力和最近变更。' }
  }
  if (status.bisect_active && status.bisect_candidate) {
    return {
      tone: 'warning',
      text: status.bisect_current
        ? '扩展二分排查进行中，该扩展当前被临时启用。'
        : '扩展二分排查进行中，该扩展当前被临时停用。',
    }
  }
  if (status.safe_mode && !status.safe_mode_allowed) {
    return { tone: 'warning', text: '扩展恢复模式已启用，该扩展不在白名单中，当前不会进入运行时装配。' }
  }
  if (status.safe_mode) {
    return { tone: 'warning', text: '扩展恢复模式已启用，该扩展在当前恢复集合内。' }
  }
  return null
})

const distributionNotice = computed(() => {
  const distribution = extension.value?.distribution || {}
  if (!distribution.abandoned) {
    return ''
  }
  const replacement = String(distribution.replacement || '').trim()
  if (replacement) {
    return `该扩展已标记为废弃，建议迁移到 ${replacement}。`
  }
  return '该扩展已标记为废弃，建议评估替代方案。'
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

async function loadExtension(options = {}) {
  const { showLoading = true, clearError = true } = options
  if (showLoading) {
    loading.value = true
  }
  if (clearError) {
    errorMessage.value = ''
  }
  if (showLoading) {
    detailComponent.value = null
    settingsComponent.value = null
    permissionsComponent.value = null
  }

  try {
    const extensionId = String(route.params.extensionId || '').trim()
    const data = await api.get(`/admin/extensions/${extensionId}`)
    extension.value = data.extension || null
    detailComponent.value = await resolveExtensionAdminComponent(extension.value, 'detail', {
      importers: adminEntryModules,
    })
    settingsComponent.value = inlineSettings.value
      ? await resolveExtensionAdminComponent(extension.value, 'settings', {
        importers: adminEntryModules,
        fallbacks: [resolveFallbackExtensionSettingsPage],
      })
      : null
    permissionsComponent.value = inlinePermissions.value
      ? await resolveExtensionAdminComponent(extension.value, 'permissions', {
        importers: adminEntryModules,
        fallbacks: [resolveFallbackExtensionPermissionsPage],
      })
      : null
    syncExtensionScopesFromExtension(extension.value)
  } catch (error) {
    console.error('加载扩展详情失败:', error)
    errorMessage.value = extractApiErrorMessage(error, '加载扩展详情失败，请稍后重试')
  } finally {
    if (showLoading) {
      loading.value = false
    }
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

  const previousExtension = cloneExtensionState(extension.value)
  actionLoading.value = true
  currentActionKey.value = String(action.key || action.action || '')
  currentActionName.value = String(action.action || '')
  errorMessage.value = ''
  applyRuntimeActionState(action)

  try {
    let data = null
    if (action.action.startsWith('hook:')) {
      data = await api.post(`/admin/extensions/${extension.value.id}/runtime-hooks/${action.action.slice(5)}`)
    } else {
      data = await api.post(`/admin/extensions/${extension.value.id}/${action.action}`)
    }
    handleExtensionUpdated(data)
    applyRuntimeActionState(action)
    refreshExtensionDetailsSilently(action)
    if (action.success_message) {
      await modalStore.alert({
        title: action.label,
        message: action.success_message,
        tone: 'success',
      })
    }
  } catch (error) {
    if (previousExtension) {
      extension.value = previousExtension
      syncExtensionScopesFromExtension(extension.value)
    }
    console.error('执行扩展运行操作失败:', error)
    errorMessage.value = extractApiErrorMessage(error, '执行扩展运行操作失败，请稍后重试')
  } finally {
    actionLoading.value = false
    currentActionKey.value = ''
    currentActionName.value = ''
  }
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

function isRuntimeActionLoading(action) {
  if (!actionLoading.value) {
    return false
  }
  const key = String(action?.key || action?.action || '')
  return !currentActionKey.value || currentActionKey.value === key
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
  if (actionName.startsWith('hook:')) {
    return '执行操作'
  }
  return '处理中'
}

function syncExtensionScopesFromExtension(currentExtension) {
  if (!currentExtension || !Array.isArray(currentExtension.module_ids) || !currentExtension.module_ids.length) {
    return
  }

  adminRegistryStore.applyExtensionScopes(
    currentExtension.module_ids.map(moduleId => ({
      id: moduleId,
      enabled: currentExtension.enabled !== false,
    }))
  )
  adminRegistryStore.applyExtensionUpdate(currentExtension.id, {
    id: currentExtension.id,
    name: currentExtension.name,
    description: currentExtension.description,
    icon: currentExtension.icon,
    enabled: currentExtension.enabled !== false,
    installed: currentExtension.installed,
    booted: currentExtension.booted,
    healthy: currentExtension.healthy,
    runtime_status: currentExtension.runtime_status,
    module_ids: Array.isArray(currentExtension.module_ids) ? [...currentExtension.module_ids] : [],
    product_visible: currentExtension.product_visible,
    protected: currentExtension.protected,
  })
}

function handleExtensionUpdated(payload) {
  if (!payload || typeof payload !== 'object') {
    return
  }
  if (payload.extension && typeof payload.extension === 'object') {
    extension.value = mergeExtensionUpdate(extension.value, payload.extension)
    syncExtensionScopesFromExtension(extension.value)
    return
  }
  if (Array.isArray(payload.extensions) && extension.value?.id) {
    const updated = payload.extensions.find(item => item.id === extension.value.id)
    if (updated) {
      extension.value = mergeExtensionUpdate(extension.value, updated)
      syncExtensionScopesFromExtension(extension.value)
    }
  }
}

function mergeExtensionUpdate(currentExtension, updatedExtension) {
  if (!currentExtension || !updatedExtension || typeof updatedExtension !== 'object') {
    return updatedExtension || currentExtension
  }
  return {
    ...currentExtension,
    ...updatedExtension,
    links: updatedExtension.links || currentExtension.links,
    readme: updatedExtension.readme || currentExtension.readme,
    settings_schema: updatedExtension.settings_schema || currentExtension.settings_schema,
    settings_values: updatedExtension.settings_values || currentExtension.settings_values,
    permission_sections: updatedExtension.permission_sections || currentExtension.permission_sections,
    permissions: updatedExtension.permissions || currentExtension.permissions,
    admin_actions: updatedExtension.admin_actions || currentExtension.admin_actions,
    runtime_actions: updatedExtension.runtime_actions || currentExtension.runtime_actions,
  }
}

function applyRuntimeActionState(action) {
  if (!extension.value || !['enable', 'disable', 'install', 'uninstall'].includes(action?.action)) {
    return
  }

  const nextExtension = {
    ...extension.value,
  }
  if (action.action === 'enable' || action.action === 'install') {
    nextExtension.installed = true
    nextExtension.enabled = true
    nextExtension.booted = true
    nextExtension.runtime_status = { key: 'active', label: '已启用' }
    nextExtension.runtime_actions = buildRuntimeActionsForEnabledState(nextExtension, true)
  } else if (action.action === 'disable') {
    nextExtension.enabled = false
    nextExtension.booted = false
    nextExtension.runtime_status = { key: 'disabled', label: '已停用' }
    nextExtension.runtime_actions = buildRuntimeActionsForEnabledState(nextExtension, false)
  } else if (action.action === 'uninstall') {
    nextExtension.installed = false
    nextExtension.enabled = false
    nextExtension.booted = false
    nextExtension.runtime_status = { key: 'pending_install', label: '未安装' }
    nextExtension.runtime_actions = [{
      key: 'install',
      label: '安装扩展',
      action: 'install',
      tone: 'primary',
      confirm_title: '安装扩展',
      confirm_message: `确定安装 ${nextExtension.name || '该扩展'} 吗？当前版本会登记为已安装并默认启用。`,
      confirm_text: '安装',
      success_message: '扩展已安装并启用。',
      requires_installed: false,
      order: 10,
    }]
  }

  extension.value = nextExtension
  syncExtensionScopesFromExtension(extension.value)
}

function buildRuntimeActionsForEnabledState(currentExtension, enabled) {
  const actions = Array.isArray(currentExtension.runtime_actions)
    ? currentExtension.runtime_actions.filter(item => !['enable', 'disable', 'install', 'uninstall'].includes(item?.action))
    : []
  if (enabled) {
    if (!currentExtension.protected) {
      actions.push({
        key: 'disable',
        label: '停用扩展',
        action: 'disable',
        tone: 'danger',
        confirm_title: '停用扩展',
        confirm_message: `确定停用 ${currentExtension.name || '该扩展'} 吗？相关后台入口和运行能力会立即隐藏。`,
        confirm_text: '停用',
        success_message: '扩展已停用。',
        requires_installed: true,
        order: 20,
      })
    }
  } else {
    actions.push({
      key: 'enable',
      label: '启用扩展',
      action: 'enable',
      tone: 'primary',
      confirm_title: '启用扩展',
      confirm_message: `确定启用 ${currentExtension.name || '该扩展'} 吗？依赖校验通过后会立即恢复能力。`,
      confirm_text: '启用',
      success_message: '扩展已启用。',
      requires_installed: true,
      order: 10,
    })
    if (!currentExtension.protected) {
      actions.push({
        key: 'uninstall',
        label: '卸载扩展',
        action: 'uninstall',
        tone: 'danger',
        confirm_title: '卸载扩展',
        confirm_message: `确定卸载 ${currentExtension.name || '该扩展'} 吗？扩展会从当前站点移除，相关运行能力会停用。`,
        confirm_text: '卸载',
        success_message: '扩展已卸载。',
        requires_installed: true,
        order: 30,
      })
    }
  }
  return actions.sort((left, right) => (left.order || 0) - (right.order || 0))
}

async function refreshExtensionDetailsSilently(action) {
  const extensionId = String(extension.value?.id || '').trim()
  if (!extensionId) {
    return
  }

  try {
    const data = await api.get(`/admin/extensions/${extensionId}`)
    handleExtensionUpdated(data)
    applyRuntimeActionState(action)
  } catch (error) {
    console.warn('后台刷新扩展详情失败:', error)
  }
}

function cloneExtensionState(currentExtension) {
  if (!currentExtension || typeof currentExtension !== 'object') {
    return currentExtension
  }
  return {
    ...currentExtension,
    links: currentExtension.links ? { ...currentExtension.links } : currentExtension.links,
    readme: currentExtension.readme ? { ...currentExtension.readme } : currentExtension.readme,
    runtime_status: currentExtension.runtime_status ? { ...currentExtension.runtime_status } : currentExtension.runtime_status,
    action_links: currentExtension.action_links ? { ...currentExtension.action_links } : currentExtension.action_links,
    runtime_actions: Array.isArray(currentExtension.runtime_actions)
      ? currentExtension.runtime_actions.map(item => ({ ...item }))
      : currentExtension.runtime_actions,
    admin_actions: Array.isArray(currentExtension.admin_actions)
      ? currentExtension.admin_actions.map(item => ({ ...item }))
      : currentExtension.admin_actions,
    module_ids: Array.isArray(currentExtension.module_ids)
      ? [...currentExtension.module_ids]
      : currentExtension.module_ids,
  }
}

function isInlineSurfaceSupported(currentExtension, surface) {
  if (!currentExtension) {
    return false
  }
  if (surface === 'settings') {
    return Array.isArray(currentExtension.settings_schema) && currentExtension.settings_schema.length > 0
  }
  if (surface === 'permissions') {
    return Array.isArray(currentExtension.permission_sections) && currentExtension.permission_sections.length > 0
  }
  return false
}

function hasExtensionSettingsPage(currentExtension) {
  return Array.isArray(currentExtension?.settings_pages) && currentExtension.settings_pages.length > 0
}

function extractApiErrorMessage(error, fallback) {
  const data = error?.response?.data
  const directMessage = data?.error || data?.detail || data?.message || error?.message
  if (directMessage) {
    return String(directMessage)
  }
  const fieldErrors = data?.field_errors || data?.errors
  if (fieldErrors && typeof fieldErrors === 'object') {
    const first = Object.values(fieldErrors)
      .flatMap(value => Array.isArray(value) ? value : [value])
      .find(Boolean)
    if (first) {
      return String(first)
    }
  }
  return fallback
}
</script>

<style scoped>
.ExtensionDetailPage-content {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ExtensionDetailProgress {
  position: sticky;
  top: 0;
  z-index: 3;
  width: 100%;
  height: 3px;
  overflow: hidden;
  border-radius: 999px;
  background: #e7f0f9;
}

.ExtensionDetailProgress::after {
  content: "";
  position: absolute;
  top: 0;
  left: -35%;
  width: 35%;
  height: 100%;
  border-radius: 999px;
  background: #3b73a8;
  animation: extension-detail-progress 1.1s ease-in-out infinite;
}

.ExtensionDetailPage-header,
.ExtensionDetailSection {
  width: 100%;
}

.ExtensionDetailSection {
  padding: 10px 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.ExtensionDetailPage-header {
  padding: 18px 20px;
  border: 1px solid var(--forum-border-soft);
  border-radius: 8px;
  background: color-mix(in srgb, var(--forum-bg-subtle) 80%, white);
}

.ExtensionDetailPage-header.is-busy {
  border-color: #cfe0f2;
  box-shadow: 0 10px 24px rgb(50 91 133 / 10%);
}

.ExtensionDetailPage-summaryBar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 42px;
}

.ExtensionDetailPage-summaryMain,
.ExtensionDetailPage-summaryMeta,
.ExtensionDetailPage-links,
.ExtensionDetailPage-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
}

.ExtensionDetailPage-summaryMeta {
  justify-content: flex-end;
  margin-left: auto;
}

.ExtensionDetailPage-version {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  color: var(--forum-text-soft);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.ExtensionDetailPage-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.ExtensionDetailPage-status.is-enabled {
  background: #edf8f2;
  color: #25704d;
}

.ExtensionDetailPage-status.is-disabled {
  background: #f5f7fa;
  color: #6c7988;
}

.ExtensionDetailPage-status.is-pending {
  background: #fff6e8;
  color: #9a5b00;
}

.ExtensionDetailToggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--forum-text-color);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.ExtensionDetailToggle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ExtensionDetailToggle.is-loading {
  cursor: wait;
}

.ExtensionDetailToggle-track {
  position: relative;
  width: 46px;
  height: 28px;
  border-radius: 999px;
  background: #d5dde7;
  transition: background 0.2s ease;
}

.ExtensionDetailToggle.is-enabled .ExtensionDetailToggle-track {
  background: #5d7695;
}

.ExtensionDetailToggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 3px 10px rgba(31, 54, 82, 0.18);
  transition: transform 0.2s ease;
}

.ExtensionDetailToggle.is-enabled .ExtensionDetailToggle-thumb {
  transform: translateX(18px);
}

.ExtensionDetailPage-link,
.ExtensionDetailAction,
.ExtensionDetailSection-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: transparent;
  color: var(--forum-text-muted);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}

.ExtensionDetailAction {
  cursor: pointer;
}

.ExtensionDetailAction.is-loading {
  min-width: 92px;
  cursor: wait;
}

.ExtensionDetailAction-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 999px;
  animation: extension-detail-spin 0.75s linear infinite;
}

.ExtensionDetailPage-link {
  color: var(--forum-text-soft);
}

.ExtensionDetailPage-link:hover,
.ExtensionDetailAction:hover,
.ExtensionDetailSection-link:hover {
  border-color: #c9d7e6;
  background: #f7fafd;
  color: #365a7b;
  text-decoration: none;
}

.ExtensionDetailAction--primary,
.ExtensionDetailSection-link {
  border-color: #dbe5f0;
  background: #f6f9fc;
  color: #446583;
}

.ExtensionDetailAction--subtle {
  background: transparent;
}

.ExtensionDetailAction--danger {
  border-color: #f0d0d0;
  background: #fff4f4;
  color: #b54747;
}

.ExtensionDetailSection-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ExtensionDetailSection-header h3 {
  margin: 0;
  color: var(--forum-text-muted);
  font-size: 18px;
  font-weight: 600;
}

.ExtensionDetailSection-empty {
  margin: 8px 0 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionDetailPage-readme {
  color: var(--forum-text-color);
  font-size: 14px;
  line-height: 1.7;
}

.ExtensionDetailPage-readme :deep(h1),
.ExtensionDetailPage-readme :deep(h2),
.ExtensionDetailPage-readme :deep(h3) {
  margin: 0 0 10px;
  color: var(--forum-text-color);
  font-size: 18px;
}

.ExtensionDetailPage-readme :deep(p),
.ExtensionDetailPage-readme :deep(ul),
.ExtensionDetailPage-readme :deep(ol),
.ExtensionDetailPage-readme :deep(pre) {
  margin: 0 0 12px;
}

.ExtensionDetailPage-readme :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--forum-bg-subtle);
  font-size: 12px;
}

.ExtensionDetailPage-readme :deep(pre) {
  overflow-x: auto;
  padding: 12px;
  background: var(--forum-bg-subtle);
}

.ExtensionDetailPage-pluginDetail {
  width: 100%;
}

@keyframes extension-detail-progress {
  0% {
    transform: translateX(0);
  }

  100% {
    transform: translateX(390%);
  }
}

@keyframes extension-detail-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ExtensionDetailProgress::after,
  .ExtensionDetailAction-spinner {
    animation-duration: 1.8s;
  }
}

@media (max-width: 700px) {
  .ExtensionDetailPage-summaryBar {
    flex-direction: column;
    align-items: flex-start;
  }

  .ExtensionDetailPage-summaryMeta {
    width: 100%;
    justify-content: space-between;
    margin-left: 0;
  }

  .ExtensionDetailPage-links {
    justify-content: flex-end;
  }
}

:deep(.ExtensionGeneratedSurface-panel),
:deep(.DiscussionsExtensionHost-panel) {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

:deep(.ExtensionGeneratedSettings-hero),
:deep(.ExtensionGeneratedSettings-grid),
:deep(.ExtensionGeneratedSettings-sideCard),
:deep(.ExtensionGeneratedPermissions-hero),
:deep(.ExtensionGeneratedPermissions-grid),
:deep(.ExtensionGeneratedPermissions-actions) {
  display: none;
}

:deep(.ExtensionGeneratedSettings),
:deep(.ExtensionGeneratedPermissions) {
  gap: 0;
}

:deep(.ExtensionGeneratedSurface-panels),
:deep(.DiscussionsExtensionHost-groups),
:deep(.DiscussionsExtensionHost-sections) {
  gap: 0;
}

:deep(.ExtensionGeneratedSettings-form),
:deep(.ExtensionGeneratedPermissions-section + .ExtensionGeneratedPermissions-section),
:deep(.DiscussionsExtensionHost-section + .DiscussionsExtensionHost-section) {
  margin-top: 0;
}

:deep(.ExtensionGeneratedSettings-form) {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0;
}

:deep(.ExtensionGeneratedSettings-fieldsCard),
:deep(.ExtensionGeneratedPermissions-item) {
  border-radius: 0;
}

:deep(.ExtensionGeneratedSurface-sectionHead),
:deep(.DiscussionsExtensionHost-sectionHead) {
  margin-bottom: 12px;
}

:deep(.ExtensionGeneratedSurface-sectionHead h3),
:deep(.DiscussionsExtensionHost-sectionHead h3) {
  color: var(--forum-text-muted);
  font-size: 26px;
  font-weight: 600;
}

:deep(.DiscussionsExtensionHost-link) {
  min-height: 32px;
  padding: 0 12px;
  border-color: #dbe5f0;
  background: #f6f9fc;
  color: #446583;
  font-size: 12px;
}
</style>
