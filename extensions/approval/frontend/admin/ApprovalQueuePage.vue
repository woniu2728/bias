<template>
  <AdminPage
    class-name="ApprovalQueuePage"
    icon="fas fa-user-check"
    :title="approvalCopy?.pageTitle || '审核队列'"
    :description="approvalCopy?.pageDescription || '审核未验证邮箱用户提交的讨论和回复'"
  >
    <AdminFilterTabs v-model="contentType" :options="approvalFilters" @change="loadItems" />

    <div class="ApprovalQueue-list">
      <div v-if="selectionState.hasSelection" class="ApprovalBulkBar">
        <div class="ApprovalBulkBar-summary">
          {{ approvalCopy?.bulkSelectionSummary?.(selectionState.selectedCount) || `已选择 ${selectionState.selectedCount} 项` }}
        </div>
        <div class="ApprovalBulkBar-actions">
          <button type="button" class="Button Button--primary" @click="openBulkAction('approve')">
            {{ approvalCopy?.bulkApproveLabel || '批量通过' }}
          </button>
          <button type="button" class="Button Button--secondary" @click="openBulkAction('reject')">
            {{ approvalCopy?.bulkRejectLabel || '批量拒绝' }}
          </button>
          <button type="button" class="Button Button--ghost" @click="clearSelection">
            {{ approvalCopy?.clearSelectionLabel || '清空选择' }}
          </button>
        </div>
      </div>

      <AdminStateBlock v-if="loading" class="ApprovalQueue-empty" tone="subtle">{{ approvalCopy?.loadingText || '加载中...' }}</AdminStateBlock>
      <AdminStateBlock v-else-if="loadError" class="ApprovalQueue-empty" tone="danger">
        {{ loadError }}
      </AdminStateBlock>
      <AdminStateBlock v-else-if="items.length === 0" class="ApprovalQueue-empty">{{ approvalCopy?.emptyText || '当前没有待审核内容' }}</AdminStateBlock>
      <div v-else class="ApprovalList">
        <div class="ApprovalList-toolbar">
          <label class="ApprovalSelectAll">
            <input
              type="checkbox"
              :checked="selectionState.allSelected"
              @change="toggleSelectAll"
            >
            <span>{{ approvalCopy?.selectAllLabel || '全选当前列表' }}</span>
          </label>
        </div>
        <article v-for="item in items" :key="`${item.type}-${item.id}`" class="ApprovalCard">
          <div class="ApprovalCard-select">
            <label class="ApprovalSelect">
              <input
                type="checkbox"
                :checked="isSelected(item)"
                @change="toggleItemSelection(item, $event)"
              >
              <span>{{ approvalCopy?.selectItemLabel || '选择此项' }}</span>
            </label>
          </div>
          <div class="ApprovalCard-header">
            <div>
              <div class="ApprovalCard-title">
                <span class="ApprovalType" :class="`ApprovalType--${item.type}`">
                  {{ item.type === 'discussion' ? (approvalCopy?.discussionTypeLabel || '讨论') : (approvalCopy?.postTypeLabel || '回复') }}
                </span>
                {{ item.title }}
              </div>
              <div class="ApprovalCard-meta">
                {{ approvalCopy?.authorPrefix || '作者' }}：{{ item.author?.display_name || item.author?.username || approvalCopy?.unknownAuthorLabel || '未知' }}
                · {{ approvalCopy?.submittedAtPrefix || '提交于' }} {{ formatDate(item.created_at) }}
                <span v-if="item.post?.number"> · {{ approvalCopy?.floorPrefix || '楼层' }} #{{ item.post.number }}</span>
              </div>
            </div>
            <a :href="itemLink(item)" class="ApprovalCard-link">{{ approvalCopy?.viewContentLabel || '查看内容' }}</a>
          </div>

          <div class="ApprovalCard-body">
            <p>{{ item.content || approvalCopy?.emptyContentText || '暂无正文内容' }}</p>
          </div>

          <div class="ApprovalCard-actions">
            <button type="button" class="Button Button--primary" @click="openAction(item, 'approve')">{{ approvalCopy?.approveLabel || '审核通过' }}</button>
            <button type="button" class="Button Button--secondary" @click="openAction(item, 'reject')">{{ approvalCopy?.rejectLabel || '拒绝并隐藏' }}</button>
          </div>
        </article>
      </div>
    </div>

    <AdminActionNoteModal
      v-model:note="actionNote"
      :show="showModal"
      :title="pendingAction === 'approve' ? (approvalCopy?.modalApproveTitle || '审核通过') : (approvalCopy?.modalRejectTitle || '拒绝内容')"
      :description="pendingAction === 'approve' ? (approvalCopy?.modalApproveDescription || '通过后内容会对有权限的用户可见。') : (approvalCopy?.modalRejectDescription || '拒绝后作者仍可看到审核反馈。')"
      :note-label="approvalCopy?.noteLabel || '审核备注'"
      :templates-label="approvalCopy?.noteTemplatesLabel || '常用模板'"
      :templates-hint="approvalCopy?.noteTemplatesHint || ''"
      :templates="noteTemplates"
      :placeholder="pendingAction === 'approve' ? (approvalCopy?.approveNotePlaceholder || '例如：内容符合社区规范，已放行') : (approvalCopy?.rejectNotePlaceholder || '例如：内容质量不足，已拒绝')"
      :confirm-text="pendingAction === 'approve' ? (approvalCopy?.confirmApproveText || '通过审核') : (approvalCopy?.confirmRejectText || '拒绝并隐藏')"
      :confirm-tone="pendingAction === 'approve' ? 'primary' : 'danger'"
      :saving="saving"
      @close="closeModal"
      @select-template="applyNoteTemplate"
      @submit="submitAction"
    />
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from '@bias/core'
import {
  AdminActionNoteModal,
  AdminFilterTabs,
  AdminPage,
  AdminStateBlock,
  adminApi,
  getAdminPageActionMeta,
  getAdminPageConfig,
  getAdminPageCopy,
  resolveApprovalSelectionState,
  resolveApprovalTemplateOptions,
  useModalStore,
} from '@bias/admin/components'

const PAGE_KEY = 'approval.queue'
const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const items = ref([])
const contentType = ref('all')
const showModal = ref(false)
const selectedItem = ref(null)
const selectedKeys = ref(new Set())
const pendingAction = ref('approve')
const actionNote = ref('')
const modalStore = useModalStore()
const approvalCopy = computed(() => getAdminPageCopy(PAGE_KEY))
const approvalConfig = computed(() => getAdminPageConfig(PAGE_KEY))
const approvalActionMeta = computed(() => getAdminPageActionMeta(PAGE_KEY))
const approvalFilters = computed(() => approvalConfig.value?.filters || [])
const selectionState = computed(() => resolveApprovalSelectionState(items.value, selectedKeys.value))
const selectedItemTypes = computed(() => {
  const types = selectionState.value.selectedItems.map(item => item.type).filter(Boolean)
  return [...new Set(types)]
})
const isBulkMode = computed(() => !selectedItem.value && selectionState.value.selectedCount > 0)
const noteTemplates = computed(() => resolveApprovalTemplateOptions(approvalConfig.value, {
  action: pendingAction.value,
  itemType: selectedItem.value?.type || '',
  itemTypes: isBulkMode.value ? selectedItemTypes.value : [],
}))

onMounted(() => {
  loadItems()
})

async function loadItems() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await adminApi.get('/admin/approval-queue', {
      params: { content_type: contentType.value }
    })
    items.value = data.data || []
    selectedKeys.value = new Set(
      [...selectedKeys.value].filter(key => items.value.some(item => `${item.type}-${item.id}` === key))
    )
  } catch (error) {
    console.error('加载审核队列失败:', error)
    loadError.value = error.response?.data?.error || error.message || approvalActionMeta.value?.loadErrorText || '加载审核队列失败，请稍后重试'
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

function openBulkAction(action) {
  if (!selectionState.value.hasSelection) return
  selectedItem.value = null
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

function applyNoteTemplate(value) {
  actionNote.value = value || ''
}

function getItemKey(item) {
  return `${item.type}-${item.id}`
}

function isSelected(item) {
  return selectedKeys.value.has(getItemKey(item))
}

function toggleItemSelection(item, event) {
  const next = new Set(selectedKeys.value)
  const key = getItemKey(item)
  if (event.target.checked) {
    next.add(key)
  } else {
    next.delete(key)
  }
  selectedKeys.value = next
}

function toggleSelectAll(event) {
  if (event.target.checked) {
    selectedKeys.value = new Set(selectionState.value.selectableKeys)
    return
  }
  clearSelection()
}

function clearSelection() {
  selectedKeys.value = new Set()
}

async function submitAction() {
  if (!selectedItem.value && !selectionState.value.hasSelection) return

  const action = pendingAction.value
  const bulkMode = !selectedItem.value && selectionState.value.hasSelection
  const selectedCount = selectionState.value.selectedCount
  saving.value = true
  try {
    if (selectedItem.value) {
      await adminApi.post(
        `/admin/approval-queue/${selectedItem.value.type}/${selectedItem.value.id}/${action}`,
        { note: actionNote.value }
      )
    } else {
      const confirmed = await modalStore.confirm({
        title: action === 'approve'
          ? (approvalCopy.value?.bulkApproveConfirmTitle || '批量通过审核')
          : (approvalCopy.value?.bulkRejectConfirmTitle || '批量拒绝内容'),
        message: action === 'approve'
          ? (approvalCopy.value?.bulkApproveConfirmMessage?.(selectedCount) || `确定批量通过这 ${selectedCount} 条待审核内容吗？`)
          : (approvalCopy.value?.bulkRejectConfirmMessage?.(selectedCount) || `确定批量拒绝这 ${selectedCount} 条待审核内容吗？`),
        confirmText: action === 'approve'
          ? (approvalCopy.value?.bulkApproveConfirmText || '批量通过')
          : (approvalCopy.value?.bulkRejectConfirmText || '批量拒绝'),
        cancelText: approvalCopy.value?.bulkActionCancelText || '取消',
        tone: action === 'approve' ? 'warning' : 'danger'
      })
      if (!confirmed) {
        return
      }

      await adminApi.post(`/admin/approval-queue/bulk/${action}`, {
        note: actionNote.value,
        items: selectionState.value.selectedItems.map(item => ({
          type: item.type,
          id: item.id,
        })),
      })
    }

    closeModal()
    clearSelection()
    await loadItems()
    await modalStore.alert({
      title: bulkMode
        ? (action === 'approve'
          ? (approvalActionMeta.value?.bulkApproveSuccessTitle || '批量审核已通过')
          : (approvalActionMeta.value?.bulkRejectSuccessTitle || '批量拒绝已完成'))
        : (action === 'approve'
          ? (approvalActionMeta.value?.approveSuccessTitle || '审核已通过')
          : (approvalActionMeta.value?.rejectSuccessTitle || '内容已拒绝')),
      message: bulkMode
        ? (action === 'approve'
          ? (approvalActionMeta.value?.bulkApproveSuccessMessage?.(selectedCount) || `已批量通过 ${selectedCount} 条内容。`)
          : (approvalActionMeta.value?.bulkRejectSuccessMessage?.(selectedCount) || `已批量拒绝 ${selectedCount} 条内容。`))
        : (action === 'approve'
          ? (approvalActionMeta.value?.approveSuccessMessage || '内容已放行，用户现在可以正常查看。')
          : (approvalActionMeta.value?.rejectSuccessMessage || '内容已拒绝并隐藏。')),
      tone: 'success'
    })
  } catch (error) {
    console.error('审核提交失败:', error)
    await modalStore.alert({
      title: approvalActionMeta.value?.submitFailedTitle || '提交失败',
      message: error.response?.data?.error || error.message || approvalActionMeta.value?.submitFailedMessage || '未知错误',
      tone: 'danger'
    })
  } finally {
    saving.value = false
  }
}

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return approvalCopy.value?.unknownTimeText || '未知时间'
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

.ApprovalList-toolbar,
.ApprovalBulkBar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ApprovalBulkBar {
  margin-bottom: 16px;
}

.ApprovalBulkBar-summary {
  color: var(--forum-text-color);
  font-weight: 600;
}

.ApprovalBulkBar-actions,
.ApprovalSelectAll,
.ApprovalSelect {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ApprovalCard {
  position: relative;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  padding: 18px 20px;
  box-shadow: var(--forum-shadow-sm);
}

.ApprovalCard-select {
  margin-bottom: 12px;
}

.ApprovalSelect,
.ApprovalSelectAll {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
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
  .ApprovalList-toolbar,
  .ApprovalBulkBar,
  .ApprovalCard {
    border-radius: 16px;
  }

  .ApprovalList-toolbar,
  .ApprovalBulkBar,
  .ApprovalCard {
    padding: 16px;
  }

  .ApprovalList-toolbar,
  .ApprovalBulkBar,
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

  .ApprovalBulkBar-actions {
    width: 100%;
    flex-direction: column;
  }

  .ApprovalBulkBar-actions .Button {
    width: 100%;
    justify-content: center;
  }
}
</style>
