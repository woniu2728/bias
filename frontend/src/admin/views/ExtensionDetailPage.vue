<template>
  <AdminPage
    class-name="ExtensionDetailPage"
    :icon="extension?.icon || 'fas fa-puzzle-piece'"
    :title="extension?.name || '扩展详情'"
    :description="extension?.description || '查看扩展设置、权限与运行状态。'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展详情中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else-if="extension" class="ExtensionDetailPage-content">
      <AdminStateBlock v-if="recoveryNotice" :tone="recoveryNotice.tone">
        {{ recoveryNotice.text }}
      </AdminStateBlock>

      <section class="ExtensionDetailPage-header">
        <div class="ExtensionDetailPage-headerTitleRow">
          <div class="ExtensionDetailPage-headerTopItems">
            <span class="ExtensionDetailPage-version">{{ extension.version || '0.0.0' }}</span>
          </div>
        </div>

        <div class="ExtensionDetailPage-headerItems">
          <button
            v-if="primaryToggleAction"
            type="button"
            class="ExtensionDetailToggle"
            :class="extension.enabled ? 'is-enabled' : 'is-disabled'"
            :disabled="actionLoading"
            @click="runRuntimeAction(primaryToggleAction)"
          >
            <span class="ExtensionDetailToggle-track">
              <span class="ExtensionDetailToggle-thumb"></span>
            </span>
            <span>{{ extension.enabled ? '已启用' : '未启用' }}</span>
          </button>

          <span v-else class="ExtensionDetailPage-status" :class="runtimeStatusClass">
            {{ extension.runtime_status?.label || (extension.enabled ? '已启用' : '未启用') }}
          </span>

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
            :class="resolveActionToneClass(action)"
            :disabled="actionLoading"
            @click="runRuntimeAction(action)"
          >
            {{ actionLoading ? '处理中...' : action.label }}
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
import { generatedAdminExtensionModules } from '../../generated/extensionImportMap'

const route = useRoute()
const adminRegistryStore = useAdminRegistryStore()
const modalStore = useModalStore()
const loading = ref(true)
const actionLoading = ref(false)
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
  const actions = Array.isArray(extension.value?.admin_actions) ? extension.value.admin_actions : []
  const allowedKeys = new Set(['documentation', 'website', 'discuss', 'support', 'source', 'donate'])
  return actions
    .filter(action => action?.kind === 'link' && action?.target && allowedKeys.has(action.key))
    .map(action => ({
      key: action.key,
      label: action.label,
      target: action.target,
      icon: action.icon || 'fas fa-link',
    }))
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
))

const inlinePermissions = computed(() => (
  isInlineSurfaceSupported(extension.value, 'permissions')
))

const primaryToggleAction = computed(() => (
  runtimeActions.value.find(action => ['enable', 'disable'].includes(action?.action)) || null
))

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
  settingsComponent.value = null
  permissionsComponent.value = null

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
    if (action.action.startsWith('hook:')) {
      await api.post(`/admin/extensions/${extension.value.id}/runtime-hooks/${action.action.slice(5)}`)
    } else {
      await api.post(`/admin/extensions/${extension.value.id}/${action.action}`)
    }
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

function handleExtensionUpdated(payload) {
  if (!payload || typeof payload !== 'object') {
    return
  }
  if (payload.extension && typeof payload.extension === 'object') {
    extension.value = payload.extension
    syncModulesFromExtension(extension.value)
    return
  }
  if (Array.isArray(payload.extensions) && extension.value?.id) {
    const updated = payload.extensions.find(item => item.id === extension.value.id)
    if (updated) {
      extension.value = updated
      syncModulesFromExtension(extension.value)
    }
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
</script>

<style scoped>
.ExtensionDetailPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
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
  padding: 18px 20px 16px;
  background: var(--forum-bg-subtle);
}

.ExtensionDetailPage-headerTitleRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.ExtensionDetailPage-headerItems,
.ExtensionDetailPage-links,
.ExtensionDetailPage-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
}

.ExtensionDetailPage-headerTopItems {
  margin-left: auto;
}

.ExtensionDetailPage-version {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  color: var(--forum-text-soft);
  font-size: 13px;
  font-weight: 600;
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

.ExtensionDetailPage-link {
  color: var(--forum-text-soft);
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
  font-size: 26px;
  font-weight: 600;
}

.ExtensionDetailSection-empty {
  margin: 8px 0 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionDetailPage-pluginDetail {
  width: 100%;
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
