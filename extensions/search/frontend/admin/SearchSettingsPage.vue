<template>
  <section class="SearchSettingsPage">
    <div class="SearchSettingsPage-grid">
      <article class="SearchSettingsPage-card">
        <span class="SearchSettingsPage-label">当前状态</span>
        <strong>{{ status?.label || loadingText }}</strong>
        <p>{{ status?.message || statusError || '查看当前索引与队列运行状态。' }}</p>
      </article>

      <article class="SearchSettingsPage-card">
        <span class="SearchSettingsPage-label">当前数据库</span>
        <strong>{{ status?.databaseLabel || loadingText }}</strong>
      </article>

      <article class="SearchSettingsPage-card">
        <span class="SearchSettingsPage-label">最近重建</span>
        <strong>{{ formatRebuildTime(status?.lastRebuild?.created_at) }}</strong>
        <p v-if="status?.lastRebuild?.duration_ms">{{ formatRebuildDuration(status.lastRebuild.duration_ms) }}</p>
      </article>

      <article class="SearchSettingsPage-card">
        <span class="SearchSettingsPage-label">索引队列状态</span>
        <strong>{{ status?.queueWorkerLabel || loadingText }}</strong>
        <p>{{ status?.queueWorkerMessage || '重建操作会读取当前队列运行状态。' }}</p>
      </article>
    </div>

    <div
      v-if="Array.isArray(status?.missing_indexes) && status.missing_indexes.length > 0"
      class="SearchSettingsPage-tags"
    >
      <span>缺失索引</span>
      <code
        v-for="indexName in status.missing_indexes"
        :key="indexName"
      >
        {{ indexName }}
      </code>
    </div>

    <AdminInlineMessage v-if="statusError" tone="danger">
      {{ statusError }}
    </AdminInlineMessage>

    <div class="SearchSettingsPage-actions">
      <button
        type="button"
        class="Button Button--primary"
        :disabled="rebuilding || loading || status?.supported === false"
        @click="rebuildSearchIndexes"
      >
        <span v-if="rebuilding" class="SearchSettingsPage-spinner" aria-hidden="true"></span>
        <span>{{ rebuilding ? '重建中...' : '重建搜索索引' }}</span>
      </button>
      <button
        type="button"
        class="Button"
        :disabled="loading || rebuilding"
        @click="loadStatus"
      >
        刷新状态
      </button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from '@bias/core'
import { adminApi, AdminInlineMessage, useModalStore } from '@bias/admin/components'

const modalStore = useModalStore()
const loading = ref(false)
const rebuilding = ref(false)
const status = ref(null)
const statusError = ref('')
const loadingText = '加载中...'

onMounted(async () => {
  await loadStatus()
})

async function loadStatus() {
  loading.value = true
  statusError.value = ''
  try {
    status.value = await adminApi.get('/admin/search-indexes/status')
  } catch (error) {
    console.error('加载搜索索引状态失败:', error)
    statusError.value = error.response?.data?.error || '加载搜索索引状态失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function rebuildSearchIndexes() {
  const confirmed = await modalStore.confirm({
    title: '重建搜索索引',
    message: '确定在后台重建 PostgreSQL 全文搜索索引吗？数据量较大时可能耗时较长，建议在低峰期执行。',
    confirmText: '重建',
    cancelText: '取消',
    tone: 'warning',
  })
  if (!confirmed) {
    return
  }

  rebuilding.value = true
  try {
    const response = await adminApi.post('/admin/search-indexes/rebuild')
    await loadStatus()
    await modalStore.alert({
      title: '搜索索引已重建',
      message: `已重建 ${Array.isArray(response?.indexes) ? response.indexes.length : 0} 个搜索索引。`,
      tone: 'success',
    })
  } catch (error) {
    await modalStore.alert({
      title: '重建搜索索引失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger',
    })
  } finally {
    rebuilding.value = false
  }
}

function formatRebuildTime(value) {
  if (!value) {
    return '尚未重建'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatRebuildDuration(durationMs) {
  const normalized = Number(durationMs || 0)
  if (!normalized) {
    return '最近一次重建未记录耗时。'
  }
  return `最近一次耗时 ${normalized} ms`
}
</script>

<style scoped>
.SearchSettingsPage {
  display: grid;
  gap: 16px;
}

.SearchSettingsPage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.SearchSettingsPage-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 8px;
  background: var(--forum-bg-elevated);
}

.SearchSettingsPage-label {
  display: block;
  margin-bottom: 6px;
  color: var(--forum-text-muted);
  font-size: 12px;
}

.SearchSettingsPage-card strong {
  display: block;
  color: var(--forum-text-color);
  font-size: 15px;
  word-break: break-word;
}

.SearchSettingsPage-card p {
  margin: 6px 0 0;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

.SearchSettingsPage-tags,
.SearchSettingsPage-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.SearchSettingsPage-tags span {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
}

.SearchSettingsPage-tags code {
  padding: 4px 8px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  font-size: 12px;
}

.SearchSettingsPage-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 999px;
  animation: search-settings-spin 0.8s linear infinite;
}

@keyframes search-settings-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .SearchSettingsPage-grid {
    grid-template-columns: 1fr;
  }
}
</style>
