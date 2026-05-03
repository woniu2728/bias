<template>
  <AdminPage
    className="AuditLogsPage"
    icon="fas fa-clipboard-list"
    title="审计日志"
    description="查看管理员关键操作记录"
  >
    <div class="AuditLogsPage-toolbar">
      <select v-model="filters.action" class="FormControl" @change="reloadFromFirstPage">
        <option value="">全部操作</option>
        <option v-for="option in actionOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <select v-model="filters.target_type" class="FormControl" @change="reloadFromFirstPage">
        <option value="">全部对象</option>
        <option v-for="option in targetOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <button type="button" class="Button" :disabled="loading" @click="loadLogs">
        <i class="fas fa-sync-alt"></i>
        <span>刷新</span>
      </button>
    </div>

    <div class="AuditLogsPage-list">
      <AdminStateBlock v-if="loading" tone="subtle">加载中...</AdminStateBlock>
      <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
      <AdminStateBlock v-else-if="logs.length === 0">暂无审计日志</AdminStateBlock>

      <div v-else class="AuditLogTable-wrap">
        <table class="AuditLogTable">
          <thead>
            <tr>
              <th>时间</th>
              <th>管理员</th>
              <th>操作</th>
              <th>对象</th>
              <th>来源</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td data-label="时间">{{ formatDate(log.created_at) }}</td>
              <td data-label="管理员">
                <strong>{{ log.user?.display_name || log.user?.username || '系统' }}</strong>
              </td>
              <td data-label="操作">
                <span class="AuditAction">{{ getActionLabel(log.action) }}</span>
                <code>{{ log.action }}</code>
              </td>
              <td data-label="对象">
                <span>{{ getTargetLabel(log.target_type) }}</span>
                <small v-if="log.target_id">#{{ log.target_id }}</small>
              </td>
              <td data-label="来源">
                <span>{{ log.ip_address || '-' }}</span>
              </td>
              <td data-label="详情">
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
import { onMounted, reactive, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import AdminPagination from '../components/AdminPagination.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import api from '../../api'

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

const actionLabels = {
  'admin.appearance_asset.upload': '上传外观资源',
  'admin.approval.approve': '审核通过',
  'admin.approval.reject': '审核拒绝',
  'admin.cache.clear': '清除缓存',
  'admin.discussion.delete': '删除讨论',
  'admin.discussion.hide': '隐藏讨论',
  'admin.discussion.lock': '锁定讨论',
  'admin.discussion.restore': '恢复讨论',
  'admin.discussion.sticky': '置顶讨论',
  'admin.discussion.unlock': '解锁讨论',
  'admin.discussion.unsticky': '取消置顶',
  'admin.flag.resolve': '处理举报',
  'admin.group.create': '创建用户组',
  'admin.group.delete': '删除用户组',
  'admin.group.update': '更新用户组',
  'admin.mail.test': '发送测试邮件',
  'admin.permissions.update': '更新权限',
  'admin.post.delete': '删除回复',
  'admin.queue_metrics.reset': '重置队列指标',
  'admin.search_indexes.rebuild': '重建搜索索引',
  'admin.settings.update': '更新设置',
  'admin.tag.create': '创建标签',
  'admin.tag.delete': '删除标签',
  'admin.tag.move': '移动标签',
  'admin.tag.refresh_stats': '刷新标签统计',
  'admin.tag.update': '更新标签',
  'admin.user.delete': '删除用户',
  'admin.user.update': '更新用户',
}

const targetLabels = {
  appearance_asset: '外观资源',
  cache: '缓存',
  discussion: '讨论',
  group: '用户组',
  mail: '邮件',
  search_index: '搜索索引',
  permissions: '权限',
  post: '回复',
  post_flag: '举报',
  settings: '设置',
  tag: '标签',
  user: '用户',
}

const actionOptions = Object.entries(actionLabels).map(([value, label]) => ({ value, label }))
const targetOptions = Object.entries(targetLabels).map(([value, label]) => ({ value, label }))
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
    loadError.value = error.response?.data?.error || error.message || '加载审计日志失败'
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
  return actionLabels[action] || '未知操作'
}

function getTargetLabel(targetType) {
  return targetLabels[targetType] || targetType || '-'
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
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
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
  .AuditLogsPage-toolbar {
    flex-direction: column;
  }

  .AuditLogsPage-toolbar .FormControl,
  .AuditLogsPage-toolbar .Button {
    width: 100%;
  }

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
  }

  .AuditLogTable td::before {
    content: attr(data-label);
    color: var(--forum-text-muted);
    font-weight: 600;
  }

  .AuditLogTable pre {
    max-width: none;
  }

}
</style>
