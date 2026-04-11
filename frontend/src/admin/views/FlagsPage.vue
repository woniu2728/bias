<template>
  <AdminPage
    className="FlagsPage"
    icon="fas fa-flag"
    title="举报管理"
    description="处理用户提交的帖子举报"
  >
    <div class="FlagsPage-toolbar">
      <button
        v-for="option in filters"
        :key="option.value"
        @click="changeStatus(option.value)"
        class="FilterButton"
        :class="{ active: status === option.value }"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="FlagsPage-list">
      <div v-if="loading" class="FlagsPage-empty">加载中...</div>
      <div v-else-if="flags.length === 0" class="FlagsPage-empty">暂无举报记录</div>
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
            <button @click="openResolve(flag, 'resolved')" class="Button Button--primary">标记已处理</button>
            <button @click="openResolve(flag, 'ignored')" class="Button Button--secondary">忽略举报</button>
          </div>
          <div v-else class="FlagCard-footer">
            处理人：{{ flag.resolved_by?.display_name || flag.resolved_by?.username || '未知' }}
            <span v-if="flag.resolution_note"> · 备注：{{ flag.resolution_note }}</span>
          </div>
        </article>
      </div>
    </div>

    <div v-if="showResolveModal" class="Modal" @click.self="closeResolveModal">
      <div class="Modal-content">
        <div class="Modal-header">
          <h3>{{ pendingStatus === 'resolved' ? '标记举报已处理' : '忽略举报' }}</h3>
          <button @click="closeResolveModal" class="Modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="Modal-body">
          <div class="Form-group">
            <label>处理备注</label>
            <textarea
              v-model="resolutionNote"
              class="FormControl"
              rows="4"
              :placeholder="pendingStatus === 'resolved' ? '例如：已隐藏帖子并警告用户' : '例如：举报理由不足，暂不处理'"
            ></textarea>
          </div>
        </div>
        <div class="Modal-footer">
          <button @click="closeResolveModal" class="Button Button--secondary">取消</button>
          <button @click="resolveFlag" class="Button Button--primary" :disabled="saving">
            {{ saving ? '提交中...' : '确认' }}
          </button>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const loading = ref(true)
const saving = ref(false)
const flags = ref([])
const status = ref('open')
const showResolveModal = ref(false)
const pendingStatus = ref('resolved')
const selectedFlag = ref(null)
const resolutionNote = ref('')

const filters = [
  { value: 'open', label: '待处理' },
  { value: 'resolved', label: '已处理' },
  { value: 'ignored', label: '已忽略' },
]

onMounted(() => {
  loadFlags()
})

async function loadFlags() {
  loading.value = true
  try {
    const data = await api.get('/admin/flags', {
      params: { status: status.value }
    })
    flags.value = data.data || []
  } catch (error) {
    console.error('加载举报失败:', error)
  } finally {
    loading.value = false
  }
}

function changeStatus(nextStatus) {
  if (status.value === nextStatus) return
  status.value = nextStatus
  loadFlags()
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

  saving.value = true
  try {
    await api.post(`/admin/flags/${selectedFlag.value.id}/resolve`, {
      status: pendingStatus.value,
      resolution_note: resolutionNote.value,
    })
    closeResolveModal()
    await loadFlags()
  } catch (error) {
    console.error('处理举报失败:', error)
    alert('处理失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.FlagsPage-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.FilterButton,
.Button {
  border-radius: 3px;
  transition: all 0.2s;
}

.FilterButton {
  border: 1px solid #dbe2ea;
  background: white;
  padding: 8px 14px;
  cursor: pointer;
}

.FilterButton.active {
  background: #4d698e;
  border-color: #4d698e;
  color: white;
}

.FlagsPage-empty {
  padding: 40px;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  text-align: center;
  color: #999;
}

.FlagList {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.FlagCard {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  padding: 18px 20px;
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
  color: #2f3c4d;
}

.FlagCard-meta {
  margin-top: 6px;
  color: #7f8c8d;
  font-size: 13px;
}

.FlagStatus {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.FlagStatus--open {
  background: #fff3cd;
  color: #856404;
}

.FlagStatus--resolved {
  background: #d4edda;
  color: #155724;
}

.FlagStatus--ignored {
  background: #e9ecef;
  color: #495057;
}

.FlagCard-link {
  color: #4d698e;
  white-space: nowrap;
}

.FlagCard-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.FlagBlock {
  background: #f8fafc;
  border-radius: 3px;
  padding: 14px;
}

.FlagBlock strong {
  display: block;
  margin-bottom: 8px;
  color: #44515e;
}

.FlagBlock p {
  margin: 0;
  color: #556270;
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
  color: #7f8c8d;
  font-size: 13px;
}

.Button {
  border: 1px solid transparent;
  padding: 8px 14px;
  cursor: pointer;
}

.Button--primary {
  background: #4d698e;
  color: white;
}

.Button--secondary {
  background: #f5f8fa;
  border-color: #dbe2ea;
}

.Modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.Modal-content {
  width: min(520px, calc(100vw - 32px));
  background: white;
  border-radius: 3px;
}

.Modal-header,
.Modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px;
}

.Modal-header {
  border-bottom: 1px solid #e3e8ed;
}

.Modal-footer {
  justify-content: flex-end;
  border-top: 1px solid #e3e8ed;
}

.Modal-header h3 {
  margin: 0;
}

.Modal-close {
  border: 0;
  background: transparent;
  color: #999;
  font-size: 20px;
  cursor: pointer;
}

.Modal-body {
  padding: 20px;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.FormControl {
  display: block;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  resize: vertical;
}

@media (max-width: 768px) {
  .FlagCard-header,
  .FlagCard-actions,
  .FlagCard-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .FlagCard-body {
    grid-template-columns: 1fr;
  }
}
</style>
