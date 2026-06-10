<template>
  <AdminPage
    class-name="DashboardPage"
    icon="fas fa-chart-bar"
    :title="dashboardCopy?.pageTitle || '仪表盘'"
    :description="dashboardCopy?.pageDescription || '查看论坛概况和系统状态'"
  >
    <div class="DashboardPage-widgets">
      <AdminInlineMessage
        v-for="alert in dashboardAlerts"
        :key="alert.key"
        :tone="alert.tone"
      >
        <strong>{{ alert.title }}</strong>
        {{ alert.text }}
      </AdminInlineMessage>

      <!-- 状态小部件 -->
      <div class="Widget StatusWidget">
        <div class="Widget-header">
          <h3>{{ dashboardCopy?.statusWidgetTitle || '系统状态' }}</h3>
        </div>
        <AdminStateBlock v-if="loading" class="Widget-state" tone="subtle">{{ dashboardCopy?.loadingText || '加载中...' }}</AdminStateBlock>
        <AdminStateBlock v-else-if="loadError" class="Widget-state" tone="danger">{{ loadError }}</AdminStateBlock>
        <div v-else class="Widget-content">
          <div
            v-for="summary in dashboardStatusSummaries"
            :key="summary.key"
            class="StatusWidget-summary"
          >
            <div class="StatusWidget-runtime">
              <div class="StatusWidget-runtimeLabel">{{ summary.label }}</div>
              <div class="StatusWidget-runtimeValue">
                {{ summary.value }}
                <span v-if="summary.meta" class="StatusWidget-runtimeMeta">{{ summary.meta }}</span>
              </div>
            </div>
            <div class="StatusWidget-flags">
              <span
                v-for="badge in dashboardStatusBadges"
                :key="badge.key"
                class="StatusBadge"
                :class="`StatusBadge--${badge.tone}`"
              >
                {{ badge.text }}
              </span>
            </div>
          </div>
          <div class="StatusWidget-items">
            <div
              v-for="item in dashboardStatusItems"
              :key="item.key"
              class="StatusWidget-item"
            >
              <div class="StatusWidget-label">{{ item.label }}</div>
              <div class="StatusWidget-value">
                {{ item.value }}
                <span v-if="item.help" class="StatusWidget-help">{{ item.help }}</span>
              </div>
            </div>
          </div>

          <div v-if="showQueueMetrics" class="QueueMetrics">
            <div
              v-for="item in dashboardQueueMetrics"
              :key="item.key"
              :class="item.variant === 'detail' ? 'QueueMetrics-last' : 'QueueMetrics-item'"
            >
              <span class="QueueMetrics-label">{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <span v-if="item.error" class="QueueMetrics-error">
                {{ item.error }}
              </span>
            </div>
            <div class="QueueMetrics-actions">
              <button
                type="button"
                class="QueueMetrics-reset"
                :disabled="resettingQueueMetrics"
                @click="resetQueueMetrics"
              >
                <i class="fas fa-redo-alt"></i>
                <span>{{ resettingQueueMetrics ? queueResetPendingText : queueResetIdleText }}</span>
              </button>
              <span
                v-if="queueMetricsMessage"
                class="QueueMetrics-message"
                :class="{ 'QueueMetrics-message--error': queueMetricsMessageTone === 'error' }"
              >
                {{ queueMetricsMessage }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计小部件 -->
      <div class="Widget StatsWidget">
        <div class="Widget-header">
          <h3>{{ dashboardCopy?.statsWidgetTitle || '论坛统计' }}</h3>
        </div>
        <div v-if="!loading && !loadError" class="Widget-content">
          <div class="StatsWidget-items">
            <div
              v-for="item in dashboardStats"
              :key="item.key"
              class="StatsWidget-item"
            >
              <div class="StatsWidget-icon" :class="item.iconClass">
                <i :class="item.icon"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ item.value }}</div>
                <div class="StatsWidget-label">{{ item.label }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作 -->
      <div class="Widget ActionsWidget">
        <div class="Widget-header">
          <h3>{{ dashboardCopy?.actionsWidgetTitle || '快速操作' }}</h3>
        </div>
        <div class="Widget-content">
          <div class="ActionsWidget-items">
            <router-link
              v-for="action in dashboardActions"
              :key="action.key"
              :to="action.to"
              class="ActionsWidget-item"
            >
              <i :class="action.icon"></i>
              <span>{{ action.label }}</span>
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import { useAdminRegistryStore } from '../../stores/adminRegistry'
import {
  getAdminDashboardAlerts,
  getAdminDashboardAction,
  getAdminDashboardActions,
  getAdminDashboardActionMeta,
  getAdminDashboardConfig,
  getAdminDashboardCopy,
  getAdminDashboardQueueMetrics,
  getAdminDashboardStats,
  getAdminDashboardStatusBadges,
  getAdminDashboardStatusItems,
  getAdminDashboardStatusSummaries,
} from '../registry'

const stats = ref({})
const loading = ref(true)
const loadError = ref('')
const resettingQueueMetrics = ref(false)
const queueMetricsMessage = ref('')
const queueMetricsMessageTone = ref('success')
const modalStore = useModalStore()
const adminRegistryStore = useAdminRegistryStore()
const dashboardContext = computed(() => ({
  isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
}))
const dashboardActionMeta = computed(() => getAdminDashboardActionMeta(dashboardContext.value))
const dashboardCopy = computed(() => getAdminDashboardCopy(dashboardContext.value))
const dashboardConfig = computed(() => getAdminDashboardConfig(dashboardContext.value))
const dashboardAlerts = computed(() => getAdminDashboardAlerts({
  stats: stats.value,
  copy: dashboardCopy.value,
}))
const dashboardActions = computed(() => getAdminDashboardActions({
  isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
}))
const dashboardStats = computed(() => getAdminDashboardStats({
  stats: stats.value,
  copy: dashboardCopy.value,
  isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
}))
const dashboardQueueMetrics = computed(() => getAdminDashboardQueueMetrics({
  stats: stats.value,
  copy: dashboardCopy.value,
  ...dashboardContext.value,
}))
const dashboardStatusSummaries = computed(() => getAdminDashboardStatusSummaries({
  stats: stats.value,
  copy: dashboardCopy.value,
}))
const dashboardStatusBadges = computed(() => getAdminDashboardStatusBadges({
  stats: stats.value,
  copy: dashboardCopy.value,
}))
const dashboardStatusItems = computed(() => getAdminDashboardStatusItems({
  stats: stats.value,
  copy: dashboardCopy.value,
}))
const queueResetIdleText = computed(() => dashboardActionMeta.value?.queueResetIdleText || '重置指标')
const queueResetPendingText = computed(() => dashboardActionMeta.value?.queueResetPendingText || '重置中...')
const queueResetAction = computed(() => getAdminDashboardAction({
  api,
  modalStore,
  stats: stats.value,
  copy: dashboardActionMeta.value,
  ...dashboardContext.value,
  setStats: value => {
    stats.value = value
  },
  setMessage: value => {
    queueMetricsMessage.value = value
  },
  setMessageTone: value => {
    queueMetricsMessageTone.value = value
  },
  setPending: value => {
    resettingQueueMetrics.value = value
  },
}, 'reset-queue-metrics'))
const showQueueMetrics = computed(() => dashboardQueueMetrics.value.length > 0 || Boolean(queueResetAction.value?.run))

async function loadStats() {
  try {
    loadError.value = ''
    const data = await api.get('/admin/stats')
    stats.value = {
      ...(dashboardConfig.value?.defaultStats || {}),
      ...data,
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    loadError.value = dashboardActionMeta.value?.loadingErrorText || '加载统计数据失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function resetQueueMetrics() {
  if (resettingQueueMetrics.value) {
    return
  }

  if (!queueResetAction.value?.run) {
    return
  }

  await queueResetAction.value.run()
}

onMounted(async () => {
  stats.value = {
    ...(dashboardConfig.value?.defaultStats || {}),
  }
  await loadStats()
})
</script>

<style scoped>
.DashboardPage-widgets {
  display: flex;
  flex-direction: column;
  gap: var(--forum-space-5);
}

.Widget {
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  box-shadow: var(--forum-shadow-sm);
}

.Widget-header {
  padding: 15px 20px;
  border-bottom: 1px solid var(--forum-border-soft);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.92) 100%);
}

.Widget-header h3 {
  margin: 0;
  font-size: var(--forum-font-size-lg);
  font-weight: 600;
  color: var(--forum-text-color);
}

.Widget-state {
  margin: 16px;
}

.Widget-content {
  padding: var(--forum-space-5);
}

/* 状态小部件 */
.StatusWidget-summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  margin: -20px -20px 20px;
  background: linear-gradient(135deg, #f5f8fa 0%, #edf4fb 100%);
  border-bottom: 1px solid #e3e8ed;
}

.StatusWidget-runtime {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.StatusWidget-runtimeLabel {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #7c8795;
}

.StatusWidget-runtimeValue {
  font-size: 24px;
  font-weight: 700;
  color: #223245;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.StatusWidget-runtimeMeta {
  font-size: 14px;
  font-weight: 500;
  color: #4d698e;
}

.StatusWidget-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
}

.StatusBadge {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.StatusBadge--success {
  background: #e8f6ee;
  color: #24724c;
}

.StatusBadge--warning {
  background: #fff4df;
  color: #a95d00;
}

.StatusBadge--neutral {
  background: #eef2f6;
  color: #5b6776;
}

.StatusWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.StatusWidget-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.StatusWidget-label {
  font-size: 13px;
  color: #999;
}

.StatusWidget-value {
  min-width: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  overflow-wrap: anywhere;
}

.StatusWidget-help {
  display: block;
  margin-top: 4px;
  color: #7c8795;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
}

.QueueMetrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(110px, 0.5fr)) minmax(220px, 1.5fr) minmax(150px, 0.6fr);
  gap: 12px;
  margin-top: 20px;
  padding: 14px;
  border: 1px solid var(--forum-border-soft);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated-strong);
}

.QueueMetrics-item,
.QueueMetrics-last {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.QueueMetrics-label {
  color: #7c8795;
  font-size: 12px;
}

.QueueMetrics strong {
  color: #25364a;
  font-size: 15px;
  overflow-wrap: anywhere;
}

.QueueMetrics-error {
  color: var(--forum-danger-color);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.QueueMetrics-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6px;
  min-width: 0;
}

.QueueMetrics-reset {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 11px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
  font-size: 13px;
  font-weight: 600;
}

.QueueMetrics-reset:hover:not(:disabled) {
  border-color: var(--forum-border-strong);
  background: #eef3f7;
}

.QueueMetrics-message {
  color: var(--forum-success-color);
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.QueueMetrics-message--error {
  color: var(--forum-danger-color);
}

/* 统计小部件 */
.StatsWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.StatsWidget-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f5f8fa;
  border-radius: 3px;
}

.StatsWidget-icon {
  width: 50px;
  height: 50px;
  background: #4d698e;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.StatsWidget-icon i {
  font-size: 20px;
  color: white;
}

.StatsWidget-icon--warning {
  background: #e67e22;
}

.StatsWidget-icon--info {
  background: #3498db;
}

.StatsWidget-info {
  flex: 1;
}

.StatsWidget-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin-bottom: 3px;
}

.StatsWidget-label {
  font-size: 13px;
  color: #666;
}

/* 快速操作 */
.ActionsWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.ActionsWidget-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  background: #f5f8fa;
  border-radius: 3px;
  color: #555;
  text-decoration: none;
  transition: all 0.2s;
}

.ActionsWidget-item:hover {
  background: #e8eef5;
  color: #4d698e;
  text-decoration: none;
}

.ActionsWidget-item i {
  font-size: 18px;
  width: 24px;
  text-align: center;
}

@media (max-width: 768px) {
  .Widget {
    border-radius: 16px;
  }

  .Widget-header,
  .Widget-content {
    padding: 16px;
  }

  .StatusWidget-summary {
    padding: 16px;
    margin: -16px -16px 16px;
    border-radius: 16px 16px 0 0;
  }

  .StatusWidget-runtimeValue {
    font-size: 20px;
  }

  .StatusWidget-items,
  .QueueMetrics,
  .StatsWidget-items,
  .ActionsWidget-items {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .StatsWidget-item,
  .ActionsWidget-item {
    border-radius: 14px;
  }
}
</style>
