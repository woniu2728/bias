<template>
  <AdminPage
    className="ApprovalQueuePage"
    icon="fas fa-user-check"
    title="审核队列"
    description="审核未验证邮箱用户提交的讨论和回复"
  >
    <AdminFilterTabs v-model="contentType" :options="filters" @change="loadItems" />

    <div class="ApprovalQueue-list">
      <AdminStateBlock v-if="loading" class="ApprovalQueue-empty" tone="subtle">加载中...</AdminStateBlock>
      <AdminStateBlock v-else-if="loadError" class="ApprovalQueue-empty" tone="danger">
        {{ loadError }}
      </AdminStateBlock>
      <AdminStateBlock v-else-if="items.length === 0" class="ApprovalQueue-empty">当前没有待审核内容</AdminStateBlock>
      <div v-else class="ApprovalList">
        <article v-for="item in items" :key="`${item.type}-${item.id}`" class="ApprovalCard">
          <div class="ApprovalCard-header">
            <div>
              <div class="ApprovalCard-title">
                <span class="ApprovalType" :class="`ApprovalType--${item.type}`">
                  {{ item.type === 'discussion' ? '讨论' : '回复' }}
                </span>
                {{ item.title }}
              </div>
              <div class="ApprovalCard-meta">
                作者：{{ item.author?.display_name || item.author?.username || '未知' }}
                · 提交于 {{ formatDate(item.created_at) }}
                <span v-if="item.post?.number"> · 楼层 #{{ item.post.number }}</span>
              </div>
            </div>
            <a :href="itemLink(item)" class="ApprovalCard-link">查看内容</a>
          </div>

          <div class="ApprovalCard-body">
            <p>{{ item.content || '暂无正文内容' }}</p>
          </div>

          <div class="ApprovalCard-actions">
            <button type="button" @click="openAction(item, 'approve')" class="Button Button--primary">审核通过</button>
            <button type="button" @click="openAction(item, 'reject')" class="Button Button--secondary">拒绝并隐藏</button>
          </div>
        </article>
      </div>
    </div>

    <AdminActionNoteModal
      :show="showModal"
      :title="pendingAction === 'approve' ? '审核通过' : '拒绝内容'"
      :description="pendingAction === 'approve' ? '通过后内容会对有权限的用户可见。' : '拒绝后作者仍可看到审核反馈。'"
      note-label="审核备注"
      v-model:note="actionNote"
      :placeholder="pendingAction === 'approve' ? '例如：内容符合社区规范，已放行' : '例如：内容质量不足，已拒绝'"
      :confirm-text="pendingAction === 'approve' ? '通过审核' : '拒绝并隐藏'"
      :confirm-tone="pendingAction === 'approve' ? 'primary' : 'danger'"
      :saving="saving"
      @close="closeModal"
      @submit="submitAction"
    />
  </AdminPage>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AdminActionNoteModal from '../components/AdminActionNoteModal.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import api from '../../api'
import { useModalStore } from '../../stores/modal'

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const items = ref([])
const contentType = ref('all')
const showModal = ref(false)
const selectedItem = ref(null)
const pendingAction = ref('approve')
const actionNote = ref('')
const modalStore = useModalStore()

const filters = [
  { value: 'all', label: '全部', icon: 'fas fa-layer-group' },
  { value: 'discussion', label: '讨论', icon: 'fas fa-comments' },
  { value: 'post', label: '回复', icon: 'fas fa-reply' },
]

onMounted(() => {
  loadItems()
})

async function loadItems() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await api.get('/admin/approval-queue', {
      params: { content_type: contentType.value }
    })
    items.value = data.data || []
  } catch (error) {
    console.error('加载审核队列失败:', error)
    loadError.value = error.response?.data?.error || error.message || '加载审核队列失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function itemLink(item) {
  if (item.type === 'discussion') {
    return `/d/${item.discussion.id}`
  }
  return `/d/${item.discussion.id}?near=${item.post.number}`
}

function openAction(item, action) {
  selectedItem.value = item
  pendingAction.value = action
  actionNote.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedItem.value = null
  pendingAction.value = 'approve'
  actionNote.value = ''
  saving.value = false
}

async function submitAction() {
  if (!selectedItem.value) return

  const action = pendingAction.value
  saving.value = true
  try {
    await api.post(
      `/admin/approval-queue/${selectedItem.value.type}/${selectedItem.value.id}/${action}`,
      { note: actionNote.value }
    )
    closeModal()
    await loadItems()
    await modalStore.alert({
      title: action === 'approve' ? '审核已通过' : '内容已拒绝',
      message: action === 'approve' ? '内容已放行，用户现在可以正常查看。' : '内容已拒绝并隐藏。',
      tone: 'success'
    })
  } catch (error) {
    console.error('审核提交失败:', error)
    await modalStore.alert({
      title: '提交失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    saving.value = false
  }
}

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.ApprovalQueue-empty {
  box-shadow: var(--forum-shadow-sm);
}

.ApprovalList {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ApprovalCard {
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  padding: 18px 20px;
  box-shadow: var(--forum-shadow-sm);
}

.ApprovalCard-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;
}

.ApprovalCard-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--forum-text-color);
}

.ApprovalType {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--forum-radius-pill);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.ApprovalType--discussion {
  background: var(--forum-info-bg);
  color: var(--forum-info-color);
}

.ApprovalType--post {
  background: #f3ecff;
  color: #7046a3;
}

.ApprovalCard-meta {
  margin-top: 6px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.ApprovalCard-link {
  color: var(--forum-primary-color);
  white-space: nowrap;
}

.ApprovalCard-body {
  background: var(--forum-bg-elevated-strong);
  border-radius: var(--forum-radius-sm);
  padding: 14px;
}

.ApprovalCard-body p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.7;
  white-space: pre-wrap;
}

.ApprovalCard-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .ApprovalCard {
    border-radius: 16px;
    padding: 16px;
  }

  .ApprovalCard-header,
  .ApprovalCard-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .ApprovalCard-title {
    align-items: flex-start;
    flex-wrap: wrap;
    font-size: 16px;
  }

  .ApprovalCard-link,
  .ApprovalCard-actions .Button {
    width: 100%;
    justify-content: center;
    text-align: center;
  }

}
</style>
