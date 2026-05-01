<template>
  <AdminPage
    className="DashboardPage"
    icon="fas fa-chart-bar"
    title="仪表盘"
    description="查看论坛概况和系统状态"
  >
    <div class="DashboardPage-widgets">
      <!-- 状态小部件 -->
      <div class="Widget StatusWidget">
        <div class="Widget-header">
          <h3>系统状态</h3>
        </div>
        <AdminStateBlock v-if="loading" class="Widget-state" tone="subtle">加载中...</AdminStateBlock>
        <AdminStateBlock v-else-if="loadError" class="Widget-state" tone="danger">{{ loadError }}</AdminStateBlock>
        <div v-else class="Widget-content">
          <div class="StatusWidget-summary">
            <div class="StatusWidget-runtime">
              <div class="StatusWidget-runtimeLabel">运行时</div>
              <div class="StatusWidget-runtimeValue">
                {{ stats.runtimeName || 'Python' }}
                <span class="StatusWidget-runtimeMeta">Python {{ stats.pythonVersion || '-' }}</span>
              </div>
            </div>
            <div class="StatusWidget-flags">
              <span class="StatusBadge" :class="stats.debugMode ? 'StatusBadge--warning' : 'StatusBadge--success'">
                {{ stats.debugMode ? 'DEBUG' : 'PRODUCTION' }}
              </span>
              <span class="StatusBadge" :class="stats.maintenanceMode ? 'StatusBadge--warning' : 'StatusBadge--neutral'">
                {{ stats.maintenanceMode ? '维护模式开启' : '维护模式关闭' }}
              </span>
              <span class="StatusBadge" :class="stats.redisEnabled ? 'StatusBadge--success' : 'StatusBadge--neutral'">
                {{ stats.redisEnabled ? 'Redis 已启用' : 'Redis 未启用' }}
              </span>
              <span class="StatusBadge" :class="queueWorkerBadgeClass">
                {{ stats.queueWorkerLabel || '队列未检测' }}
              </span>
            </div>
          </div>
          <div class="StatusWidget-items">
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">Python 版本</div>
              <div class="StatusWidget-value">{{ stats.pythonVersion || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">Django 版本</div>
              <div class="StatusWidget-value">{{ stats.djangoVersion || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">数据库</div>
              <div class="StatusWidget-value">{{ stats.databaseLabel || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">缓存驱动</div>
              <div class="StatusWidget-value">{{ stats.cacheDriver || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">实时层</div>
              <div class="StatusWidget-value">{{ stats.realtimeDriver || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">队列执行</div>
              <div class="StatusWidget-value">{{ stats.queueLabel || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">队列 Worker</div>
              <div class="StatusWidget-value">
                {{ stats.queueWorkerLabel || '-' }}
                <span v-if="stats.queueWorkerMessage" class="StatusWidget-help">{{ stats.queueWorkerMessage }}</span>
              </div>
            </div>
          </div>

          <div class="QueueMetrics">
            <div class="QueueMetrics-item">
              <span class="QueueMetrics-label">入队</span>
              <strong>{{ stats.queueMetrics?.enqueued_count || 0 }}</strong>
            </div>
            <div class="QueueMetrics-item">
              <span class="QueueMetrics-label">同步</span>
              <strong>{{ stats.queueMetrics?.sync_count || 0 }}</strong>
            </div>
            <div class="QueueMetrics-item">
              <span class="QueueMetrics-label">回退</span>
              <strong>{{ stats.queueMetrics?.fallback_count || 0 }}</strong>
            </div>
            <div class="QueueMetrics-last">
              <span class="QueueMetrics-label">最近任务</span>
              <strong>{{ stats.queueMetrics?.last_task || '-' }}</strong>
              <span v-if="stats.queueMetrics?.last_error" class="QueueMetrics-error">
                {{ stats.queueMetrics.last_error }}
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
                <span>{{ resettingQueueMetrics ? '重置中...' : '重置指标' }}</span>
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
          <h3>论坛统计</h3>
        </div>
        <div v-if="!loading && !loadError" class="Widget-content">
          <div class="StatsWidget-items">
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-users"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalUsers || 0 }}</div>
                <div class="StatsWidget-label">用户总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-comments"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalDiscussions || 0 }}</div>
                <div class="StatsWidget-label">讨论总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-comment"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalPosts || 0 }}</div>
                <div class="StatsWidget-label">帖子总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon StatsWidget-icon--info">
                <i class="fas fa-user-check"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.pendingApprovals || 0 }}</div>
                <div class="StatsWidget-label">待审核内容</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon StatsWidget-icon--warning">
                <i class="fas fa-flag"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.openFlags || 0 }}</div>
                <div class="StatsWidget-label">待处理举报</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作 -->
      <div class="Widget ActionsWidget">
        <div class="Widget-header">
          <h3>快速操作</h3>
        </div>
        <div class="Widget-content">
          <div class="ActionsWidget-items">
            <router-link to="/admin/basics" class="ActionsWidget-item">
              <i class="fas fa-pencil-alt"></i>
              <span>编辑基础设置</span>
            </router-link>
            <router-link to="/admin/permissions" class="ActionsWidget-item">
              <i class="fas fa-key"></i>
              <span>管理权限</span>
            </router-link>
            <router-link to="/admin/users" class="ActionsWidget-item">
              <i class="fas fa-users"></i>
              <span>管理用户</span>
            </router-link>
            <router-link to="/admin/approval" class="ActionsWidget-item">
              <i class="fas fa-user-check"></i>
              <span>处理审核</span>
            </router-link>
            <router-link to="/admin/flags" class="ActionsWidget-item">
              <i class="fas fa-flag"></i>
              <span>处理举报</span>
            </router-link>
            <router-link to="/admin/audit-logs" class="ActionsWidget-item">
              <i class="fas fa-clipboard-list"></i>
              <span>查看审计</span>
            </router-link>
            <router-link to="/admin/appearance" class="ActionsWidget-item">
              <i class="fas fa-paint-brush"></i>
              <span>自定义外观</span>
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
import AdminStateBlock from '../components/AdminStateBlock.vue'
import api from '../../api'

const stats = ref({
  runtimeName: 'Python',
  pythonVersion: null,
  djangoVersion: null,
  databaseLabel: null,
  cacheDriver: null,
  queueDriver: null,
  queueEnabled: false,
  queueLabel: null,
  queueWorkerStatus: 'disabled',
  queueWorkerLabel: null,
  queueWorkerAvailable: false,
  queueWorkerCount: 0,
  queueWorkerMessage: '',
  queueMetrics: {
    enqueued_count: 0,
    sync_count: 0,
    fallback_count: 0,
    last_task: '',
    last_error: '',
    last_event_at: '',
  },
  realtimeDriver: null,
  redisEnabled: false,
  debugMode: false,
  maintenanceMode: false,
  totalUsers: 0,
  totalDiscussions: 0,
  totalPosts: 0,
  pendingApprovals: 0,
  openFlags: 0,
})
const loading = ref(true)
const loadError = ref('')
const resettingQueueMetrics = ref(false)
const queueMetricsMessage = ref('')
const queueMetricsMessageTone = ref('success')
const queueWorkerBadgeClass = computed(() => {
  if (!stats.value.queueEnabled || ['disabled', 'sync'].includes(stats.value.queueWorkerStatus)) {
    return 'StatusBadge--neutral'
  }
  return stats.value.queueWorkerAvailable ? 'StatusBadge--success' : 'StatusBadge--warning'
})

async function loadStats() {
  try {
    loadError.value = ''
    const data = await api.get('/admin/stats')
    stats.value = data
  } catch (error) {
    console.error('加载统计数据失败:', error)
    loadError.value = '加载统计数据失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function resetQueueMetrics() {
  if (resettingQueueMetrics.value) {
    return
  }

  resettingQueueMetrics.value = true
  queueMetricsMessage.value = ''
  queueMetricsMessageTone.value = 'success'

  try {
    const data = await api.post('/admin/queue/metrics/reset')
    stats.value = {
      ...stats.value,
      queueMetrics: data.metrics || stats.value.queueMetrics
    }
    queueMetricsMessage.value = data.message || '队列运行指标已重置'
  } catch (error) {
    console.error('重置队列指标失败:', error)
    queueMetricsMessageTone.value = 'error'
    queueMetricsMessage.value = error.response?.data?.error || '重置失败，请稍后重试'
  } finally {
    resettingQueueMetrics.value = false
  }
}

onMounted(async () => {
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
  font-size: 16px;
  font-weight: 600;
  color: #333;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.QueueMetrics-error {
  color: var(--forum-danger-color);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
