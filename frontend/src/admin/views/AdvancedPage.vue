<template>
  <AdminPage
    class-name="AdvancedPage"
    icon="fas fa-cog"
    :title="advancedCopy?.pageTitle || '高级设置'"
    :description="advancedCopy?.pageDescription || '配置缓存、队列、维护模式与扩展恢复'"
  >
    <div class="AdvancedPage-content">
      <div class="RuntimeNotice">
        <h3 class="Section-title">{{ advancedCopy?.runtimeNoticeTitle || '运行时说明' }}</h3>
        <div class="RuntimeNotice-grid">
          <div>
            <h4>{{ advancedCopy?.immediateEffectTitle || '即时生效' }}</h4>
            <p>{{ advancedCopy?.immediateEffectDescription || '`maintenance_mode`、`maintenance_message`、`cache_lifetime`、`log_queries` 会在保存后直接影响请求层行为。' }}</p>
          </div>
          <div>
            <h4>{{ advancedCopy?.deploymentRequiredTitle || '需额外部署或重启' }}</h4>
            <p>{{ advancedCopy?.deploymentRequiredDescription || '`debug_mode` 由 Django 配置文件或环境变量控制；`queue_enabled` / `queue_driver` 会控制已接入队列入口的任务，新 worker 配置需重启服务后生效。' }}</p>
          </div>
        </div>
      </div>

      <div v-if="extensionRuntimeErrors.length || extensionRecoveryNotice" class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.extensionDiagnosticsTitle || '扩展恢复与诊断' }}</h3>

        <AdminInlineMessage v-if="extensionRecoveryNotice" tone="warning">
          {{ extensionRecoveryNotice }}
        </AdminInlineMessage>

        <div v-if="extensionRuntimeErrors.length" class="RuntimeSnapshot">
          <div class="RuntimeSnapshot-tags">
            <span class="RuntimeSnapshot-tagsLabel">{{ advancedCopy?.extensionRuntimeErrorsLabel || '运行时错误' }}</span>
            <button type="button" class="Button Button--small" @click="clearRuntimeErrors">
              {{ advancedCopy?.clearRuntimeErrorsLabel || '清除记录' }}
            </button>
          </div>
          <div class="RuntimeErrorList">
            <div
              v-for="item in extensionRuntimeErrors"
              :key="`${item.extensionId}-${item.operation}-${item.occurredAt}`"
              class="RuntimeErrorList-item"
            >
              <strong>{{ item.extensionId || 'unknown' }}</strong>
              <span>{{ item.operation || 'runtime' }}</span>
              <p>{{ item.message || '扩展运行时错误' }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="runtimeDependencyChecks.length || runtimeDependencyActions.length" class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.dependencyHealthTitle || '依赖健康' }}</h3>

        <div class="RuntimeSnapshot">
          <div class="RuntimeSnapshot-grid">
            <div
              v-for="item in runtimeDependencyChecks"
              :key="item.key"
              class="RuntimeSnapshot-item"
            >
              <div class="RuntimeSnapshot-label">{{ item.label }}</div>
              <div class="RuntimeSnapshot-value">{{ item.status_label || advancedCopy?.dependencyStatusLoadingText || '加载中...' }}</div>
              <p class="RuntimeSnapshot-help">
                {{ item.message || advancedCopy?.dependencyHealthHelpText || '查看当前依赖运行状态与修复建议。' }}
              </p>
            </div>
          </div>

          <div
            v-if="runtimeDependencyActions.length > 0"
            class="RuntimeSnapshot-tags"
          >
            <span class="RuntimeSnapshot-tagsLabel">{{ advancedCopy?.dependencyActionLabel || '建议处理' }}</span>
            <div
              v-for="item in runtimeDependencyActions"
              :key="item.key"
              class="RuntimeRemediation"
            >
              <strong>{{ item.label }}</strong>
              <span>{{ item.recommended_action }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.cacheSectionTitle || '缓存设置' }}</h3>

        <div class="Form-group">
          <label for="advanced-cache-driver">{{ advancedCopy?.cacheDriverLabel || '缓存驱动' }}</label>
          <AdminSelectMenu
            input-id="advanced-cache-driver"
            v-model="settings.cache_driver"
            :options="cacheDriverOptions"
            :aria-label="advancedCopy?.cacheDriverLabel || '缓存驱动'"
          />
          <p class="Form-help">{{ advancedCopy?.cacheDriverHelpText || '选择缓存存储方式' }}</p>
        </div>

        <div class="Form-group">
          <label for="advanced-cache-lifetime">{{ advancedCopy?.cacheLifetimeLabel || '缓存时间（秒）' }}</label>
          <input
            id="advanced-cache-lifetime"
            v-model.number="settings.cache_lifetime"
            name="cache_lifetime"
            type="number"
            class="FormControl"
            :placeholder="advancedConfig?.placeholders?.cacheLifetime || '3600'"
          />
          <p class="Form-help">{{ advancedCopy?.cacheLifetimeHelpText || '当前已接入公开论坛设置缓存。填 0 表示禁用该缓存，保存基础/外观/高级设置时会自动清理。' }}</p>
        </div>

        <div class="Form-actions">
          <button type="button" class="Button" :disabled="clearing" @click="clearCache">
            {{ clearing ? (advancedCopy?.clearingCacheLabel || '清除中...') : (advancedCopy?.clearCacheLabel || '清除缓存') }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.queueSectionTitle || '队列设置' }}</h3>

        <div class="Form-group">
          <label for="advanced-queue-driver">{{ advancedCopy?.queueDriverLabel || '队列驱动' }}</label>
          <AdminSelectMenu
            input-id="advanced-queue-driver"
            v-model="settings.queue_driver"
            :options="queueDriverOptions"
            :aria-label="advancedCopy?.queueDriverLabel || '队列驱动'"
          />
          <p class="Form-help">{{ advancedCopy?.queueDriverHelpText || '当前通知实时投递已接入统一队列入口。选择 Redis 并部署 worker 后会尝试异步投递。' }}</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-queue-enabled"
              v-model="settings.queue_enabled"
              name="queue_enabled"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.queueEnabledLabel || '启用队列处理' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.queueEnabledHelpText || '关闭时强制同步执行。开启后，已接入任务会入队执行；入队失败时会同步回退，避免影响主流程。' }}</p>
        </div>

      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.maintenanceSectionTitle || '维护模式' }}</h3>

        <div class="Form-group">
          <label for="advanced-maintenance-mode-key">{{ advancedCopy?.maintenanceModeKeyLabel || '维护级别' }}</label>
          <AdminSelectMenu
            input-id="advanced-maintenance-mode-key"
            v-model="settings.maintenance_mode_key"
            :options="maintenanceModeOptions"
            :aria-label="advancedCopy?.maintenanceModeKeyLabel || '维护级别'"
          />
          <p class="Form-help">{{ advancedCopy?.maintenanceModeKeyHelpText || '低维护只阻断写操作，高维护阻断普通前台请求，恢复模式用于扩展排障。' }}</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-maintenance-mode"
              v-model="maintenanceEnabled"
              name="maintenance_mode"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.maintenanceEnabledLabel || '启用维护模式' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.maintenanceEnabledHelpText || '启用后，普通用户访问论坛 API 将收到 503；`/api/forum`、登录接口和后台入口保留豁免。' }}</p>
        </div>

        <div class="Form-group">
          <label for="advanced-maintenance-message">{{ advancedCopy?.maintenanceMessageLabel || '维护提示信息' }}</label>
          <textarea
            id="advanced-maintenance-message"
            v-model="settings.maintenance_message"
            name="maintenance_message"
            class="FormControl"
            rows="3"
            :placeholder="advancedConfig?.placeholders?.maintenanceMessage || '论坛正在维护中，请稍后再试...'"
          ></textarea>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-extension-safe-mode"
              v-model="settings.extension_safe_mode"
              name="extension_safe_mode"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.extensionSafeModeLabel || '启用扩展恢复模式' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.extensionSafeModeHelpText || '启用后只启动核心能力和白名单扩展，用于排查扩展导致的启动或运行异常。' }}</p>
        </div>

        <div class="Form-group">
          <label for="advanced-extension-safe-mode-extensions">{{ advancedCopy?.extensionSafeModeExtensionsLabel || '恢复模式扩展白名单' }}</label>
          <input
            id="advanced-extension-safe-mode-extensions"
            v-model="extensionSafeModeExtensionsText"
            name="extension_safe_mode_extensions"
            type="text"
            class="FormControl"
            :placeholder="advancedConfig?.placeholders?.extensionSafeModeExtensions || 'tags, notifications'"
          />
          <p class="Form-help">{{ advancedCopy?.extensionSafeModeExtensionsHelpText || '填写扩展 ID，多个扩展用英文逗号分隔。留空时只启动核心能力。' }}</p>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.debugSectionTitle || '调试设置' }}</h3>

        <div class="Form-group">
          <label>
            <input
              id="advanced-debug-mode"
              v-model="settings.debug_mode"
              name="debug_mode"
              type="checkbox"
              class="FormControl-checkbox"
              disabled
            />
            {{ advancedCopy?.debugModeLabel || '调试模式（只读）' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.debugModeHelpText || '当前运行值来自 Django 配置文件或环境变量，保存这里不会热切换服务端 DEBUG。' }}</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-log-queries"
              v-model="settings.log_queries"
              name="log_queries"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.logQueriesLabel || '记录数据库查询' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.logQueriesHelpText || '保存后即时生效。会把每个 HTTP 请求触发的 SQL 记录到服务器日志。' }}</p>
        </div>
      </div>

      <div class="Form-actions">
        <button
          type="button"
          class="Button Button--primary"
          :disabled="saving"
          @click="saveSettings"
        >
          {{ saving ? (advancedCopy?.savingLabel || '保存中...') : (advancedCopy?.saveLabel || '保存设置') }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">{{ advancedCopy?.saveSuccessText || '保存成功' }}</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">{{ saveErrorMessage || advancedCopy?.saveErrorText || '保存失败，请重试' }}</AdminInlineMessage>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminSelectMenu from '../components/AdminSelectMenu.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { clearExtensionRuntimeErrors, getExtensionRuntimeErrors } from '../../common/extensionRuntime'
import { useModalStore } from '../../stores/modal'
import {
  getAdminAdvancedPageActionMeta,
  getAdminAdvancedPageConfig,
  getAdminAdvancedPageCopy,
} from '../registry'

const advancedCopy = computed(() => getAdminAdvancedPageCopy())
const advancedConfig = computed(() => getAdminAdvancedPageConfig())
const advancedActionMeta = computed(() => getAdminAdvancedPageActionMeta())
const settings = ref({})
const adminStats = ref(null)
const extensionRuntimeErrors = ref([])

const saving = ref(false)
const clearing = ref(false)
const loadedSettingsSnapshot = ref(null)
const modalStore = useModalStore()
const { saveSuccess, saveError, saveErrorMessage, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const cacheDriverOptions = computed(() => advancedConfig.value?.cacheDriverOptions || [])
const queueDriverOptions = computed(() => advancedConfig.value?.queueDriverOptions || [])
const maintenanceModeOptions = computed(() => advancedConfig.value?.maintenanceModeOptions || [
  { value: 'none', label: '关闭' },
  { value: 'low', label: '低维护' },
  { value: 'high', label: '高维护' },
  { value: 'safe', label: '恢复模式' },
])
const runtimeDependencyChecks = computed(() => (
  Array.isArray(adminStats.value?.runtimeDependencyChecks)
    ? adminStats.value.runtimeDependencyChecks
    : (advancedConfig.value?.defaultRuntimeDependencyChecks || [])
))
const runtimeDependencyActions = computed(() => (
  runtimeDependencyChecks.value.filter(item => item?.recommended_action)
))
const extensionRecoveryNotice = computed(() => {
  if (settings.value.extension_safe_mode) {
    const allowed = extensionSafeModeExtensionsText.value
    return allowed
      ? `扩展恢复模式已启用，只启动核心能力和白名单扩展：${allowed}`
      : '扩展恢复模式已启用，当前只启动核心能力。'
  }
  return ''
})
const extensionSafeModeExtensionsText = computed({
  get() {
    return Array.isArray(settings.value.extension_safe_mode_extensions)
      ? settings.value.extension_safe_mode_extensions.join(', ')
      : String(settings.value.extension_safe_mode_extensions || '')
  },
  set(value) {
    settings.value.extension_safe_mode_extensions = String(value || '')
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
  },
})
const maintenanceEnabled = computed({
  get() {
    return String(settings.value.maintenance_mode_key || 'none') !== 'none'
  },
  set(value) {
    settings.value.maintenance_mode_key = value ? 'high' : 'none'
    settings.value.maintenance_mode = Boolean(value)
  },
})

function defaultSettings() {
  return {
    cache_driver: 'file',
    cache_lifetime: 3600,
    queue_driver: 'sync',
    queue_enabled: false,
    maintenance_mode: false,
    maintenance_mode_key: 'none',
    maintenance_message: '',
    extension_safe_mode: false,
    extension_safe_mode_extensions: [],
    debug_mode: false,
    log_queries: false,
    ...(advancedConfig.value?.defaultSettings || {}),
  }
}

onMounted(async () => {
  settings.value = defaultSettings()
  await Promise.all([
    loadAdvancedSettings(),
    loadAdminStats(),
  ])
  refreshRuntimeErrors()
})

async function loadAdvancedSettings() {
  try {
    const data = await api.get('/admin/advanced')
    settings.value = normalizeAdvancedSettings({ ...settings.value, ...data })
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
  } catch (error) {
    console.error('加载高级设置失败:', error)
  }
}

async function loadAdminStats() {
  try {
    adminStats.value = await api.get('/admin/stats')
  } catch (error) {
    console.error('加载后台运行状态失败:', error)
  }
}

function refreshRuntimeErrors() {
  extensionRuntimeErrors.value = getExtensionRuntimeErrors()
}

function clearRuntimeErrors() {
  clearExtensionRuntimeErrors()
  refreshRuntimeErrors()
}

async function saveSettings() {
  const sensitiveChanges = getSensitiveSettingChanges()
  if (sensitiveChanges.length > 0) {
    const confirmed = await modalStore.confirm({
      title: advancedActionMeta.value?.saveConfirmTitle || '保存高级设置',
      message: advancedActionMeta.value?.saveConfirmMessage?.(sensitiveChanges) || `以下设置会影响运行时行为：${sensitiveChanges.join('、')}。确定保存当前配置吗？`,
      confirmText: advancedActionMeta.value?.saveConfirmText || '保存',
      cancelText: advancedActionMeta.value?.saveCancelText || '取消',
      tone: 'warning'
    })
    if (!confirmed) {
      return
    }
  }

  saving.value = true
  resetSaveFeedback()

  try {
    const response = await api.post('/admin/advanced', normalizeAdvancedSettings(settings.value))
    if (response?.settings) {
      settings.value = normalizeAdvancedSettings({ ...settings.value, ...response.settings })
    }
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
    await loadAdminStats()
    showSaveSuccess()
  } catch (error) {
    console.error('保存高级设置失败:', error)
    showSaveError(error.response?.data?.message || error.response?.data?.error || '')
  } finally {
    saving.value = false
  }
}

async function clearCache() {
  const confirmed = await modalStore.confirm({
    title: advancedActionMeta.value?.clearCacheConfirmTitle || '清除缓存',
    message: advancedActionMeta.value?.clearCacheConfirmMessage || '确定清除运行时缓存吗？短时间内部分页面可能重新读取配置和数据。',
    confirmText: advancedActionMeta.value?.clearCacheConfirmText || '清除',
    cancelText: advancedActionMeta.value?.clearCacheCancelText || '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  clearing.value = true
  try {
    await api.post('/admin/cache/clear')
    await loadAdminStats()
    await modalStore.alert({
      title: advancedActionMeta.value?.clearCacheSuccessTitle || '缓存已清除',
      message: advancedActionMeta.value?.clearCacheSuccessMessage || '运行时缓存已成功清理。',
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: advancedActionMeta.value?.clearCacheFailedTitle || '清除缓存失败',
      message: error.response?.data?.error || error.message || advancedActionMeta.value?.unknownErrorText || '未知错误',
      tone: 'danger'
    })
  } finally {
    clearing.value = false
  }
}

function createSettingsSnapshot(value) {
  const normalized = normalizeAdvancedSettings(value)
  return {
    maintenance_mode: normalized.maintenance_mode_key !== 'none',
    maintenance_mode_key: normalized.maintenance_mode_key,
    extension_safe_mode: Boolean(value.extension_safe_mode),
    extension_safe_mode_extensions: Array.isArray(value.extension_safe_mode_extensions)
      ? value.extension_safe_mode_extensions.join(',')
      : String(value.extension_safe_mode_extensions || ''),
    queue_enabled: Boolean(value.queue_enabled),
    queue_driver: value.queue_driver,
    log_queries: Boolean(value.log_queries),
  }
}

function normalizeAdvancedSettings(value) {
  const payload = { ...(value || {}) }
  const key = String(payload.maintenance_mode_key || '').trim().toLowerCase()
  const fallback = payload.maintenance_mode ? 'high' : 'none'
  payload.maintenance_mode_key = ['none', 'low', 'high', 'safe'].includes(key) ? key : fallback
  payload.maintenance_mode = payload.maintenance_mode_key !== 'none'
  return payload
}

function getSensitiveSettingChanges() {
  const previous = loadedSettingsSnapshot.value
  if (!previous) {
    return []
  }

  const current = createSettingsSnapshot(settings.value)
  const labels = advancedConfig.value?.sensitiveLabels || {}

  return Object.keys(labels).filter(key => previous[key] !== current[key]).map(key => labels[key])
}

</script>

<style scoped>
.AdvancedPage-content {
  max-width: 920px;
}

.RuntimeNotice {
  background: linear-gradient(135deg, var(--forum-bg-elevated-strong) 0%, var(--forum-bg-subtle) 100%);
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.RuntimeNotice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeNotice h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--forum-text-color);
}

.RuntimeNotice p {
  margin: 0;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  line-height: 1.7;
}

.Section-title {
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--forum-border-soft);
}

.RuntimeSnapshot {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--forum-bg-elevated) 0%, var(--forum-bg-subtle) 100%);
}

.RuntimeSnapshot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeSnapshot-item {
  min-width: 0;
}

.RuntimeSnapshot-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--forum-text-muted);
}

.RuntimeSnapshot-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--forum-text-color);
  word-break: break-word;
}

.RuntimeSnapshot-help {
  margin: 6px 0 0;
  font-size: var(--forum-font-size-sm);
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.RuntimeSnapshot-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.RuntimeSnapshot-tagsLabel {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
}

.RuntimeSnapshot-tag {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  border: 1px solid var(--forum-border-color);
  font-size: 12px;
}

.Form-grid {
  gap: 0 16px;
}

.Form-group--checkbox label {
  margin-bottom: 6px;
}

.Form-section--nested {
  margin: 4px 0 22px;
  padding: 16px;
  background: var(--forum-bg-elevated-strong);
  box-shadow: none;
}

.Form-section--nested .Form-sectionHeader {
  margin-bottom: 14px;
}

.Form-section--nested h4 {
  margin: 0 0 6px;
  color: var(--forum-text-color);
  font-size: 15px;
}

.Form-section--nested p {
  margin: 0;
}

.Form-warning {
  margin: 0;
  color: var(--forum-warning-color);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .RuntimeNotice-grid,
  .RuntimeSnapshot-grid,
  .Form-grid {
    grid-template-columns: 1fr;
  }

  .AdvancedPage-content {
    max-width: none;
  }

  .RuntimeNotice {
    padding: 16px;
    border-radius: 14px;
  }
}
</style>
