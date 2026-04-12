<template>
  <Teleport to="body">
    <div
      v-if="composerStore.isOpen && authStore.isAuthenticated"
      class="floating-composer"
      :class="{ 'is-minimized': composerStore.isMinimized, 'is-expanded': composerStore.isExpanded }"
      :style="composerInlineStyle"
    >
      <div class="composer-handle" aria-hidden="true" @mousedown.prevent="startResize"></div>
      <div class="composer-header">
        <div class="composer-title">
          <span>发起讨论</span>
          <small>{{ composerStatusText }}</small>
        </div>
        <div class="composer-controls">
          <button type="button" title="保存草稿" :disabled="submitting" @click="saveDraft()">
            <i class="far fa-save"></i>
          </button>
          <button
            type="button"
            :title="composerStore.isMinimized ? '展开' : '最小化'"
            @click="toggleMinimized"
          >
            <i :class="composerStore.isMinimized ? 'far fa-window-restore' : 'fas fa-minus'"></i>
          </button>
          <button
            type="button"
            :title="composerStore.isExpanded ? '退出全屏' : '全屏'"
            @click="toggleExpanded"
          >
            <i :class="composerStore.isExpanded ? 'fas fa-compress' : 'fas fa-expand'"></i>
          </button>
          <button type="button" title="关闭" @click="closeComposer">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>

      <div v-show="!composerStore.isMinimized" class="composer-body">
        <div v-if="isSuspended" class="composer-notice composer-notice-warning">
          {{ suspensionNotice }}
        </div>
        <div v-else-if="draftMessage" class="composer-notice">
          {{ draftMessage }}
        </div>

        <input
          ref="titleInput"
          v-model="form.title"
          type="text"
          class="composer-field composer-title-input"
          maxlength="200"
          placeholder="讨论标题"
          :disabled="submitting || isSuspended"
          @keydown.enter.prevent="focusEditor"
          @keydown.esc.prevent="closeComposer"
        />

        <div class="composer-meta">
          <select
            v-model="form.tag_id"
            class="composer-field composer-tag-select"
            :disabled="submitting || loadingTags || isSuspended"
            @keydown.esc.prevent="closeComposer"
          >
            <option value="">{{ loadingTags ? '加载标签中...' : '选择标签' }}</option>
            <option v-for="tag in availableTags" :key="tag.id" :value="String(tag.id)">
              {{ tag.name }}
            </option>
          </select>
          <span class="composer-counter">{{ form.title.length }}/200</span>
        </div>

        <textarea
          ref="composerTextarea"
          v-model="form.content"
          class="composer-editor"
          rows="8"
          placeholder="输入讨论内容... 支持 Markdown、@用户名 和代码块"
          :disabled="submitting || isSuspended"
          @keydown.ctrl.enter.prevent="submitDiscussion"
          @keydown.meta.enter.prevent="submitDiscussion"
          @keydown.esc.prevent="closeComposer"
        ></textarea>

        <div class="composer-toolbar">
          <button
            type="button"
            class="composer-submit"
            :disabled="!canSubmit"
            @click="submitDiscussion"
          >
            <i class="fas fa-paper-plane"></i>
            {{ submitting ? '发布中...' : '发布讨论' }}
          </button>

          <div class="composer-formatting" aria-label="格式化工具栏">
            <button
              v-for="tool in composerTools"
              :key="tool.key"
              type="button"
              :title="tool.title"
              :disabled="submitting || isSuspended"
              @click="applyComposerTool(tool)"
            >
              <i v-if="tool.icon" :class="tool.icon"></i>
              <span v-else>{{ tool.label }}</span>
            </button>
          </div>

          <button type="button" class="composer-secondary" :disabled="submitting" @click="clearDraft">
            清除草稿
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import api from '@/api'
import { flattenTags, normalizeTag, unwrapList } from '@/utils/forum'

const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()

const form = ref({
  title: '',
  content: '',
  tag_id: ''
})
const tags = ref([])
const loadingTags = ref(false)
const submitting = ref(false)
const titleInput = ref(null)
const composerTextarea = ref(null)
const draftSavedAt = ref('')
const draftMessage = ref('')
let draftTimer = null
const composerHeight = ref(loadComposerHeight())
const resizing = ref(false)
let resizeStartY = 0
let resizeStartHeight = composerHeight.value

const composerTools = [
  { key: 'heading', title: '标题', label: 'H', before: '## ', after: '' },
  { key: 'bold', title: '加粗', label: 'B', before: '**', after: '**' },
  { key: 'italic', title: '斜体', label: 'I', before: '*', after: '*' },
  { key: 'quote', title: '引用', icon: 'fas fa-quote-left' },
  { key: 'code', title: '代码', icon: 'fas fa-code', before: '`', after: '`' },
  { key: 'link', title: '链接', icon: 'fas fa-link' },
  { key: 'image', title: '图片', icon: 'fas fa-image' },
  { key: 'bullets', title: '无序列表', icon: 'fas fa-list-ul' },
  { key: 'ordered', title: '有序列表', icon: 'fas fa-list-ol' },
  { key: 'mention', title: '@ 提及', icon: 'fas fa-at', before: '@', after: '' }
]

const availableTags = computed(() => flattenTags(tags.value))
const hasDraftContent = computed(() => {
  return Boolean(form.value.title.trim() || form.value.content.trim() || form.value.tag_id)
})
const canSubmit = computed(() => {
  return Boolean(
    authStore.isAuthenticated &&
    form.value.title.trim() &&
    form.value.content.trim() &&
    form.value.tag_id &&
    !submitting.value &&
    !loadingTags.value &&
    !isSuspended.value
  )
})
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
const selectedTagName = computed(() => {
  const tag = availableTags.value.find(item => String(item.id) === String(form.value.tag_id))
  return tag?.name || ''
})
const composerStatusText = computed(() => {
  if (draftMessage.value) return draftMessage.value
  if (draftSavedAt.value) return `草稿保存于 ${formatDraftTime(draftSavedAt.value)}`
  if (selectedTagName.value) return `将发布到 ${selectedTagName.value}`
  return '支持 Markdown，可最小化继续编辑。'
})
const composerInlineStyle = computed(() => {
  if (composerStore.isMinimized || composerStore.isExpanded) return {}
  return { height: `${composerHeight.value}px` }
})
const suspensionNotice = computed(() => {
  if (!isSuspended.value) return ''

  const user = authStore.user || {}
  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatDateTime(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatDateTime(user.suspended_until)}，暂时无法发布讨论。`
    : '账号当前已被封禁，暂时无法发布讨论。'
})

watch(
  () => composerStore.current.requestId,
  async () => {
    if (!composerStore.isOpen) return
    await prepareComposer()
  }
)

watch(
  form,
  () => {
    if (!composerStore.isOpen) return
    scheduleDraftSave()
  },
  { deep: true }
)

watch(
  () => authStore.isAuthenticated,
  isAuthenticated => {
    if (!isAuthenticated) {
      composerStore.closeComposer()
    }
  }
)

onBeforeUnmount(() => {
  if (draftTimer) {
    clearTimeout(draftTimer)
  }
  window.removeEventListener('mousemove', handleResizeMove)
  window.removeEventListener('mouseup', stopResize)
})

onMounted(() => {
  window.addEventListener('mousemove', handleResizeMove)
  window.addEventListener('mouseup', stopResize)
})

async function prepareComposer() {
  if (!authStore.isAuthenticated) {
    composerStore.closeComposer()
    router.push({
      name: 'login',
      query: {
        redirect: router.currentRoute.value.fullPath
      }
    })
    return
  }

  await ensureTagsLoaded()

  if (!hasDraftContent.value) {
    restoreDraft()
  } else {
    draftMessage.value = ''
  }

  applyRequestedTag()
  await focusPreferredField()
}

async function ensureTagsLoaded() {
  if (loadingTags.value || tags.value.length) return

  loadingTags.value = true
  try {
    const response = await api.get('/tags', {
      params: {
        include_children: true
      }
    })
    tags.value = unwrapList(response).map(normalizeTag)
  } catch (error) {
    console.error('加载标签失败:', error)
  } finally {
    loadingTags.value = false
  }
}

function applyRequestedTag() {
  const requestedTagId = composerStore.current.tagId
  if (!requestedTagId) return

  if (!form.value.tag_id || (!form.value.title.trim() && !form.value.content.trim())) {
    form.value.tag_id = String(requestedTagId)
  }
}

async function focusPreferredField() {
  if (composerStore.isMinimized) return

  await nextTick()
  if (!form.value.title.trim()) {
    titleInput.value?.focus()
    return
  }

  focusEditor()
}

function focusEditor() {
  composerTextarea.value?.focus()
}

function toggleMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    focusPreferredField()
  }
}

function toggleExpanded() {
  composerStore.toggleExpanded()
  focusPreferredField()
}

function startResize(event) {
  if (composerStore.isExpanded || composerStore.isMinimized || window.innerWidth <= 768) return

  resizing.value = true
  resizeStartY = event.clientY
  resizeStartHeight = composerHeight.value
}

function handleResizeMove(event) {
  if (!resizing.value) return

  const delta = resizeStartY - event.clientY
  composerHeight.value = clampComposerHeight(resizeStartHeight + delta)
}

function stopResize() {
  if (!resizing.value) return
  resizing.value = false
  persistComposerHeight(composerHeight.value)
}

function closeComposer() {
  saveDraft(false)
  composerStore.closeComposer()
}

function getDraftKey() {
  return `pyflarum:create-discussion-draft:${authStore.user?.id || 'guest'}`
}

function restoreDraft() {
  if (typeof window === 'undefined') return false

  const raw = window.localStorage.getItem(getDraftKey())
  if (!raw) return false

  try {
    const draft = JSON.parse(raw)
    form.value = {
      title: draft.title || '',
      content: draft.content || '',
      tag_id: draft.tag_id || ''
    }
    draftSavedAt.value = draft.updatedAt || ''
    draftMessage.value = draftSavedAt.value
      ? `已恢复你在 ${formatDraftTime(draftSavedAt.value)} 保存的讨论草稿。`
      : '已恢复本地讨论草稿。'
    return true
  } catch (error) {
    console.error('恢复讨论草稿失败:', error)
    return false
  }
}

function scheduleDraftSave() {
  if (draftTimer) {
    clearTimeout(draftTimer)
  }

  draftTimer = setTimeout(() => {
    saveDraft(false)
  }, 300)
}

function saveDraft(showMessage = true) {
  if (typeof window === 'undefined') return

  if (!hasDraftContent.value) {
    clearDraftStorage(showMessage ? '草稿已清空' : '')
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    getDraftKey(),
    JSON.stringify({
      title: form.value.title,
      content: form.value.content,
      tag_id: form.value.tag_id,
      updatedAt
    })
  )
  draftSavedAt.value = updatedAt
  draftMessage.value = showMessage ? '讨论草稿已保存。' : ''
}

function clearDraft() {
  if (hasDraftContent.value && !confirm('确定要清除当前讨论草稿吗？')) {
    return
  }

  form.value = {
    title: '',
    content: '',
    tag_id: ''
  }
  clearDraftStorage('已清除本地草稿。')
  focusPreferredField()
}

function clearDraftStorage(message = '') {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(getDraftKey())
  }
  draftSavedAt.value = ''
  draftMessage.value = message
}

async function submitDiscussion() {
  if (!canSubmit.value) return

  submitting.value = true
  draftMessage.value = ''

  try {
    const data = await api.post('/discussions/', {
      title: form.value.title,
      content: form.value.content,
      tag_ids: form.value.tag_id ? [parseInt(form.value.tag_id, 10)] : []
    })

    if (data.approval_status === 'pending') {
      alert('讨论已提交审核，管理员通过后会显示在论坛列表中。')
    }

    resetComposer()
    await router.push(`/d/${data.id}`)
  } catch (error) {
    console.error('创建讨论失败:', error)
    const message =
      error.response?.data?.title?.[0] ||
      error.response?.data?.content?.[0] ||
      error.response?.data?.error ||
      error.response?.data?.detail ||
      error.message ||
      '发布失败，请稍后重试'
    alert(`发布失败: ${message}`)
  } finally {
    submitting.value = false
  }
}

async function applyComposerTool(tool) {
  composerStore.isMinimized = false
  await nextTick()

  const textarea = composerTextarea.value
  if (!textarea) return

  const start = textarea.selectionStart ?? form.value.content.length
  const end = textarea.selectionEnd ?? form.value.content.length
  const selected = form.value.content.slice(start, end)
  const replacement = buildComposerToolReplacement(tool, selected)

  form.value.content = `${form.value.content.slice(0, start)}${replacement}${form.value.content.slice(end)}`

  await nextTick()
  textarea.focus()
  const cursor = selected
    ? start + replacement.length
    : start + defaultToolCursorOffset(tool)
  textarea.setSelectionRange(cursor, cursor)
}

function buildComposerToolReplacement(tool, selected) {
  if (tool.key === 'link') {
    return selected ? `[${selected}](https://)` : '[链接文字](https://)'
  }
  if (tool.key === 'image') {
    return selected ? `![图片描述](${selected})` : '![图片描述](https://)'
  }
  if (tool.key === 'quote') {
    return prefixLines(selected || '引用内容', '> ')
  }
  if (tool.key === 'bullets') {
    return prefixLines(selected || '列表项', '- ')
  }
  if (tool.key === 'ordered') {
    return prefixOrderedLines(selected || '列表项')
  }

  const before = tool.before || ''
  const after = tool.after || ''
  return `${before}${selected || defaultToolText(tool)}${after}`
}

function defaultToolCursorOffset(tool) {
  const replacement = buildComposerToolReplacement(tool, '')
  if (tool.key === 'image') return replacement.indexOf('https://')
  if (tool.key === 'link') return replacement.indexOf('https://')
  return replacement.length
}

function prefixLines(content, prefix) {
  return content
    .split('\n')
    .map(line => `${prefix}${line || '内容'}`)
    .join('\n')
}

function prefixOrderedLines(content) {
  return content
    .split('\n')
    .map((line, index) => `${index + 1}. ${line || '内容'}`)
    .join('\n')
}

function defaultToolText(tool) {
  if (tool.key === 'code') return 'code'
  if (tool.key === 'heading') return '标题'
  return '文本'
}

function resetComposer() {
  clearDraftStorage()
  form.value = {
    title: '',
    content: '',
    tag_id: ''
  }
  composerStore.closeComposer()
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

function loadComposerHeight() {
  if (typeof window === 'undefined') return 520
  const value = Number(window.localStorage.getItem('pyflarum:composer-height:discussion') || 520)
  return clampComposerHeight(value)
}

function persistComposerHeight(value) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('pyflarum:composer-height:discussion', String(clampComposerHeight(value)))
}

function clampComposerHeight(value) {
  const min = 360
  const max = typeof window === 'undefined' ? 760 : Math.max(420, window.innerHeight - 72)
  return Math.max(min, Math.min(value, max))
}
</script>

<style scoped>
.floating-composer {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(760px, calc(100vw - 32px));
  background: #f7f9fb;
  border: 1px solid #dbe2ea;
  border-radius: 10px 10px 0 0;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.18);
  z-index: 900;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.floating-composer.is-minimized {
  width: min(540px, calc(100vw - 32px));
}

.floating-composer.is-expanded {
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  transform: none;
  width: auto;
  border-radius: 0;
  box-shadow: none;
}

.composer-handle {
  height: 14px;
}

.composer-handle::before {
  content: '';
  display: block;
  width: 64px;
  height: 4px;
  border-radius: 999px;
  background: #d7dee6;
  margin: 6px auto 0;
}

.composer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px 10px;
  color: #4a5665;
}

.composer-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.composer-title span,
.composer-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-title span {
  font-size: 14px;
  color: #445161;
}

.composer-title small {
  color: #7b8794;
  font-size: 12px;
}

.composer-controls {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.composer-controls button {
  border: 0;
  background: transparent;
  color: #6c7a89;
  border-radius: 4px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.composer-controls button:hover {
  background: #e8edf3;
  color: #3f4b59;
}

.composer-controls button:disabled {
  cursor: default;
  opacity: 0.45;
}

.composer-body {
  padding: 0 20px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.composer-notice {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #edf4fb;
  color: #325b88;
  line-height: 1.6;
}

.composer-notice-warning {
  background: #fff3cd;
  color: #856404;
}

.composer-field {
  width: 100%;
  border: 0;
  background: transparent;
  border-radius: 0;
  box-shadow: none;
}

.composer-field:focus {
  border: 0;
  outline: none;
  box-shadow: none;
}

.composer-title-input {
  padding: 4px 0 8px;
  font-size: 22px;
  font-weight: 300;
  color: #2f3b47;
}

.composer-title-input::placeholder {
  color: #94a0ad;
}

.composer-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #dbe2ea;
}

.composer-tag-select {
  padding: 0;
  font-size: 13px;
  color: #506172;
  max-width: 220px;
}

.composer-counter {
  margin-left: auto;
  font-size: 12px;
  color: #7b8794;
}

.composer-editor {
  width: 100%;
  padding: 14px 0 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.7;
  resize: none;
  min-height: 140px;
  max-height: none;
  flex: 1;
}

.composer-editor:focus {
  outline: none;
  border: 0;
  box-shadow: none;
}

.floating-composer.is-expanded .composer-editor {
  min-height: calc(100vh - 230px);
  max-height: none;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 -20px;
  padding: 10px 20px;
  border-top: 1px solid #dbe2ea;
  flex-wrap: nowrap;
}

.composer-submit,
.composer-secondary {
  border: 0;
  border-radius: 4px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.composer-submit {
  background: var(--forum-primary-color);
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-submit:disabled {
  cursor: default;
  opacity: 0.6;
}

.composer-formatting {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  white-space: nowrap;
}

.composer-formatting button {
  border: 0;
  background: transparent;
  color: #5b6776;
  border-radius: 4px;
  min-width: 28px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.composer-formatting button:hover {
  background: #e8edf3;
  color: #354152;
}

.composer-formatting button:disabled {
  opacity: 0.45;
  cursor: default;
}

.composer-formatting button span {
  font-weight: 700;
  font-size: 14px;
  line-height: 1;
}

.composer-secondary {
  background: transparent;
  color: #6b7786;
}

.composer-secondary:hover {
  background: #e8edf3;
  color: #425062;
}

@media (max-width: 768px) {
  .floating-composer {
    bottom: 0;
    width: 100vw;
    border-radius: 10px 10px 0 0;
  }

  .floating-composer.is-expanded {
    width: 100vw;
  }

  .composer-meta {
    flex-wrap: wrap;
  }

  .composer-tag-select {
    max-width: none;
  }

  .composer-counter {
    width: 100%;
    text-align: right;
  }

  .composer-toolbar {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .composer-submit,
  .composer-secondary {
    justify-content: center;
  }

  .composer-formatting {
    order: 3;
    flex: 0 0 100%;
    padding-bottom: 2px;
  }
}
</style>
