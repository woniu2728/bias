<template>
  <AdminPage
    className="FlagsPage"
    icon="fas fa-flag"
    title="举报管理"
    description="处理用户提交的帖子举报"
  >
    <AdminFilterTabs v-model="status" :options="filters" @change="loadFlags" />

    <div class="FlagsPage-list">
      <AdminStateBlock v-if="loading" class="FlagsPage-empty" tone="subtle">加载中...</AdminStateBlock>
      <AdminStateBlock v-else-if="loadError" class="FlagsPage-empty" tone="danger">
        {{ loadError }}
      </AdminStateBlock>
      <AdminStateBlock v-else-if="flags.length === 0" class="FlagsPage-empty">暂无举报记录</AdminStateBlock>
      <div v-else class="FlagList">
        <article v-for="flag in flags" :key="flag.id" class="FlagCard">
          <div class="FlagCard-header">
            <div>
              <div class="FlagCard-title">
                {{ flag.reason }}
                <span class="FlagStatus" :class="`FlagStatus--${flag.status}`">
                  {{ statusLabel(flag.status) }}
                </span>
              </div>
              <div class="FlagCard-meta">
                举报人：{{ flag.user.display_name || flag.user.username }}
                · 讨论：{{ flag.post.discussion_title }}
                · 帖子 #{{ flag.post.number }}
              </div>
            </div>
            <a :href="`/d/${flag.post.discussion_id}?near=${flag.post.number}`" class="FlagCard-link">
              查看帖子
            </a>
          </div>

          <div class="FlagCard-body">
            <div class="FlagBlock">
              <strong>举报说明</strong>
              <p>{{ flag.message || '用户未填写补充说明' }}</p>
            </div>
            <div class="FlagBlock">
              <strong>帖子内容</strong>
              <p>{{ flag.post.content }}</p>
            </div>
          </div>

          <div v-if="flag.status === 'open'" class="FlagCard-actions">
            <button type="button" @click="openResolve(flag, 'resolved')" class="Button Button--primary">标记已处理</button>
            <button type="button" @click="openResolve(flag, 'ignored')" class="Button Button--secondary">忽略举报</button>
          </div>
          <div v-else class="FlagCard-footer">
            处理人：{{ flag.resolved_by?.display_name || flag.resolved_by?.username || '未知' }}
            <span v-if="flag.resolution_note"> · 备注：{{ flag.resolution_note }}</span>
          </div>
        </article>
      </div>
    </div>

    <AdminActionNoteModal
      :show="showResolveModal"
      :title="pendingStatus === 'resolved' ? '标记举报已处理' : '忽略举报'"
      :description="pendingStatus === 'resolved' ? '标记后这条举报会从待处理列表移出。' : '忽略后举报会进入已忽略列表，便于后续追溯。'"
      note-label="处理备注"
      v-model:note="resolutionNote"
      :placeholder="pendingStatus === 'resolved' ? '例如：已隐藏帖子并警告用户' : '例如：举报理由不足，暂不处理'"
      :confirm-text="pendingStatus === 'resolved' ? '标记已处理' : '忽略举报'"
      :saving="saving"
      @close="closeResolveModal"
      @submit="resolveFlag"
    />
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminActionNoteModal from '../components/AdminActionNoteModal.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import api from '../../api'
import { useModalStore } from '../../stores/modal'

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const flags = ref([])
const status = ref('open')
const showResolveModal = ref(false)
const pendingStatus = ref('resolved')
const selectedFlag = ref(null)
const resolutionNote = ref('')
const modalStore = useModalStore()

const filters = [
  { value: 'open', label: '待处理', icon: 'fas fa-inbox' },
  { value: 'resolved', label: '已处理', icon: 'fas fa-check-circle' },
  { value: 'ignored', label: '已忽略', icon: 'fas fa-ban' },
]

onMounted(() => {
  loadFlags()
})

async function loadFlags() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await api.get('/admin/flags', {
      params: { status: status.value }
    })
    flags.value = data.data || []
  } catch (error) {
    console.error('加载举报失败:', error)
    loadError.value = error.response?.data?.error || error.message || '加载举报失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function statusLabel(value) {
  if (value === 'resolved') return '已处理'
  if (value === 'ignored') return '已忽略'
  return '待处理'
}

function openResolve(flag, nextStatus) {
  selectedFlag.value = flag
  pendingStatus.value = nextStatus
  resolutionNote.value = ''
  showResolveModal.value = true
}

function closeResolveModal() {
  showResolveModal.value = false
  selectedFlag.value = null
  pendingStatus.value = 'resolved'
  resolutionNote.value = ''
  saving.value = false
}

async function resolveFlag() {
  if (!selectedFlag.value) return

  const nextStatus = pendingStatus.value
  saving.value = true
  try {
    await api.post(`/admin/flags/${selectedFlag.value.id}/resolve`, {
      status: nextStatus,
      resolution_note: resolutionNote.value,
    })
    closeResolveModal()
    await loadFlags()
    await modalStore.alert({
      title: nextStatus === 'resolved' ? '举报已处理' : '举报已忽略',
      message: nextStatus === 'resolved' ? '举报状态已更新为已处理。' : '举报状态已更新为已忽略。',
      tone: 'success'
    })
  } catch (error) {
    console.error('处理举报失败:', error)
    await modalStore.alert({
      title: '处理失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.FlagsPage-empty {
  box-shadow: var(--forum-shadow-sm);
}

.FlagList {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.FlagCard {
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  padding: 18px 20px;
  box-shadow: var(--forum-shadow-sm);
}

.FlagCard-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;
}

.FlagCard-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--forum-text-color);
}

.FlagCard-meta {
  margin-top: 6px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.FlagStatus {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--forum-radius-pill);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.FlagStatus--open {
  background: var(--forum-warning-bg-strong);
  color: var(--forum-warning-color);
}

.FlagStatus--resolved {
  background: color-mix(in srgb, var(--forum-success-color) 18%, white);
  color: #155724;
}

.FlagStatus--ignored {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.FlagCard-link {
  color: var(--forum-primary-color);
  white-space: nowrap;
}

.FlagCard-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.FlagBlock {
  background: var(--forum-bg-elevated-strong);
  border-radius: var(--forum-radius-sm);
  padding: 14px;
}

.FlagBlock strong {
  display: block;
  margin-bottom: 8px;
  color: var(--forum-text-muted);
}

.FlagBlock p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
  white-space: pre-wrap;
}

.FlagCard-actions,
.FlagCard-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.FlagCard-footer {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

@media (max-width: 768px) {
  .FlagCard {
    border-radius: 16px;
    padding: 16px;
  }

  .FlagCard-header,
  .FlagCard-actions,
  .FlagCard-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .FlagCard-body {
    grid-template-columns: 1fr;
  }

  .FlagCard-title {
    align-items: flex-start;
    flex-wrap: wrap;
    font-size: 16px;
  }

  .FlagCard-link,
  .FlagCard-actions .Button {
    width: 100%;
    justify-content: center;
    text-align: center;
  }

}
</style>
