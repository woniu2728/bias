<template>
  <AdminPage
    class-name="AuditLogsPage"
    icon="fas fa-clipboard-list"
    :title="auditCopy?.pageTitle || '审计日志'"
    :description="auditCopy?.pageDescription || '查看管理员关键操作记录'"
  >
    <AdminToolbar class="AuditLogsPage-toolbar">
      <AdminSelectMenu
        input-id="audit-action-filter"
        v-model="filters.action"
        :options="auditActionFilterOptions"
        :placeholder="auditCopy?.allActionsLabel || '全部操作'"
        :aria-label="auditCopy?.actionFilterLabel || '筛选操作'"
        @change="reloadFromFirstPage"
      />
      <AdminSelectMenu
        input-id="audit-target-type-filter"
        v-model="filters.target_type"
        :options="auditTargetFilterOptions"
        :placeholder="auditCopy?.allTargetsLabel || '全部对象'"
        :aria-label="auditCopy?.targetFilterLabel || '筛选对象'"
        @change="reloadFromFirstPage"
      />
      <button type="button" class="Button" :disabled="loading" @click="loadLogs">
        <i class="fas fa-sync-alt"></i>
        <span>{{ auditCopy?.refreshLabel || '刷新' }}</span>
      </button>
    </AdminToolbar>

    <div class="AuditLogsPage-list">
      <AdminStateBlock v-if="loading" tone="subtle">{{ auditCopy?.loadingText || '加载中...' }}</AdminStateBlock>
      <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
      <AdminStateBlock v-else-if="logs.length === 0">{{ auditCopy?.emptyText || '暂无审计日志' }}</AdminStateBlock>

      <div v-else class="AuditLogTable-wrap">
        <table class="AuditLogTable">
          <thead>
            <tr>
              <th>{{ auditCopy?.tableTimeHeader || '时间' }}</th>
              <th>{{ auditCopy?.tableUserHeader || '管理员' }}</th>
              <th>{{ auditCopy?.tableActionHeader || '操作' }}</th>
              <th>{{ auditCopy?.tableTargetHeader || '对象' }}</th>
              <th>{{ auditCopy?.tableSourceHeader || '来源' }}</th>
              <th>{{ auditCopy?.tableDetailHeader || '详情' }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td :data-label="auditCopy?.timeLabel || '时间'">{{ formatDate(log.created_at) }}</td>
              <td :data-label="auditCopy?.userLabel || '管理员'">
                <strong>{{ log.user?.display_name || log.user?.username || auditCopy?.systemUserLabel || '系统' }}</strong>
              </td>
              <td :data-label="auditCopy?.actionLabel || '操作'">
                <span class="AuditAction">{{ getActionLabel(log.action) }}</span>
                <code>{{ log.action }}</code>
              </td>
              <td :data-label="auditCopy?.targetLabel || '对象'">
                <span>{{ getTargetLabel(log.target_type) }}</span>
                <small v-if="log.target_id">#{{ log.target_id }}</small>
              </td>
              <td :data-label="auditCopy?.sourceLabel || '来源'">
                <span>{{ log.ip_address || '-' }}</span>
              </td>
              <td :data-label="auditCopy?.detailLabel || '详情'">
                <pre>{{ formatData(log.data) }}</pre>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <AdminPagination
      :page="page"
      :total="total"
      :limit="limit"
      :disabled="loading"
      @change="changePage"
    />
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import AdminPagination from '../components/AdminPagination.vue'
import AdminSelectMenu from '../components/AdminSelectMenu.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import api from '../../api'
import { getAdminAuditLogsPageConfig, getAdminAuditLogsPageCopy } from '../registry'

const logs = ref([])
const loading = ref(false)
const loadError = ref('')
const page = ref(1)
const limit = ref(20)
const total = ref(0)
const filters = reactive({
  action: '',
  target_type: '',
})
const auditCopy = computed(() => getAdminAuditLogsPageCopy())
const auditConfig = computed(() => getAdminAuditLogsPageConfig())
const actionLabels = computed(() => auditConfig.value?.actionLabels || {})
const targetLabels = computed(() => auditConfig.value?.targetLabels || {})
const actionOptions = computed(() => Object.entries(actionLabels.value).map(([value, label]) => ({ value, label })))
const targetOptions = computed(() => Object.entries(targetLabels.value).map(([value, label]) => ({ value, label })))
const auditActionFilterOptions = computed(() => [
  { value: '', label: auditCopy.value?.allActionsLabel || '全部操作' },
  ...actionOptions.value,
])
const auditTargetFilterOptions = computed(() => [
  { value: '', label: auditCopy.value?.allTargetsLabel || '全部对象' },
  ...targetOptions.value,
])

onMounted(() => {
  loadLogs()
})

async function loadLogs() {
  loading.value = true
  loadError.value = ''
  try {
    const payload = await api.get('/admin/audit-logs', {
      params: {
        page: page.value,
        limit: limit.value,
        action: filters.action || undefined,
        target_type: filters.target_type || undefined,
      }
    })
    logs.value = payload.data || []
    total.value = payload.total || 0
  } catch (error) {
    loadError.value = error.response?.data?.error || error.message || auditCopy.value?.loadErrorText || '加载审计日志失败'
  } finally {
    loading.value = false
  }
}

function reloadFromFirstPage() {
  page.value = 1
  loadLogs()
}

function changePage(nextPage) {
  page.value = nextPage
  loadLogs()
}

function getActionLabel(action) {
  return actionLabels.value[action] || auditCopy.value?.unknownActionLabel || '未知操作'
}

function getTargetLabel(targetType) {
  return targetLabels.value[targetType] || targetType || '-'
}

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function formatData(data) {
  if (!data || Object.keys(data).length === 0) return '-'
  return JSON.stringify(data, null, 2)
}
</script>

<style scoped>
.AuditLogsPage-toolbar {
  margin-bottom: 18px;
}

.AuditLogsPage-toolbar .FormControl {
  width: min(100%, 220px);
}

.AuditLogTable-wrap {
  overflow-x: auto;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
}

.AuditLogTable {
  width: 100%;
  border-collapse: collapse;
  min-width: 880px;
}

.AuditLogTable th,
.AuditLogTable td {
  padding: 13px 14px;
  border-bottom: 1px solid var(--forum-border-soft);
  text-align: left;
  vertical-align: top;
  min-width: 0;
  overflow-wrap: anywhere;
}

.AuditLogTable th {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
  font-size: 13px;
  font-weight: 600;
}

.AuditLogTable tr:last-child td {
  border-bottom: 0;
}

.AuditAction {
  display: block;
  margin-bottom: 4px;
  color: var(--forum-text-color);
  font-weight: 600;
}

.AuditLogTable code {
  color: var(--forum-text-muted);
  font-size: 12px;
  word-break: break-word;
}

.AuditLogTable small {
  display: block;
  margin-top: 4px;
  color: var(--forum-text-muted);
}

.AuditLogTable pre {
  max-width: 300px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--forum-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .AuditLogTable-wrap {
    border: 0;
    overflow: visible;
  }

  .AuditLogTable,
  .AuditLogTable thead,
  .AuditLogTable tbody,
  .AuditLogTable tr,
  .AuditLogTable th,
  .AuditLogTable td {
    display: block;
    min-width: 0;
  }

  .AuditLogTable thead {
    display: none;
  }

  .AuditLogTable tr {
    border: 1px solid var(--forum-border-color);
    border-radius: var(--forum-radius-sm);
    margin-bottom: 12px;
    overflow: hidden;
  }

  .AuditLogTable td {
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr);
    gap: 10px;
    border-bottom: 1px solid var(--forum-border-soft);
    align-items: start;
  }

  .AuditLogTable td::before {
    content: attr(data-label);
    color: var(--forum-text-muted);
    font-weight: 600;
    min-width: 0;
  }

  .AuditLogTable pre {
    max-width: none;
  }

}
</style>
