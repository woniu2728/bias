<template>
  <Teleport to="body">
    <div v-if="showBackdrop" class="composer-backdrop" aria-hidden="true"></div>
    <div
      v-if="showComposer"
      class="floating-composer"
      :class="{
        'is-minimized': composerStore.isMinimized,
        'is-expanded': composerStore.isExpanded,
        'is-phone-overlay': isPhoneOverlay
      }"
      :style="composerInlineStyle"
    >
      <div class="composer-handle" aria-hidden="true" @mousedown.prevent="startResize"></div>
      <div class="composer-header">
        <div
          class="composer-title"
          :class="{ 'composer-title--clickable': composerStore.isMinimized }"
          @click="handleHeaderSummaryClick"
        >
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
        <div
          v-if="uploadNotice"
          class="composer-notice"
          :class="{
            'composer-notice-success': uploadNoticeTone === 'success',
            'composer-notice-error': uploadNoticeTone === 'error'
          }"
        >
          {{ uploadNotice }}
        </div>
        <div v-if="previewError" class="composer-notice composer-notice-error">
          {{ previewError }}
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
          v-show="!showPreview"
          ref="composerTextarea"
          v-model="form.content"
          class="composer-editor"
          rows="8"
          placeholder="输入讨论内容... 支持 Markdown、@用户名 和代码块"
          :disabled="submitting || isSuspended || uploading"
          @input="handleEditorInteraction"
          @click="handleEditorInteraction"
          @keyup="handleEditorInteraction"
          @scroll="handleEditorInteraction"
          @keydown="handleEditorKeydown"
        ></textarea>
        <div v-if="showPreview" class="composer-preview">
          <div class="composer-preview-header">
            <span>预览</span>
            <small>{{ previewStatusText }}</small>
          </div>
          <div v-if="previewLoading" class="composer-preview-loading">正在生成预览...</div>
          <div
            v-else
            class="composer-preview-body post-body"
            v-html="previewHtml || '<p class=&quot;composer-preview-empty&quot;>输入内容后即可查看预览</p>'"
          ></div>
        </div>
        <ComposerMentionPicker
          v-if="showMentionPicker"
          :items="mentionUsers"
          :active-index="mentionActiveIndex"
          :loading="mentionLoading"
          :style-object="mentionPickerStyle"
          @highlight="mentionActiveIndex = $event"
          @select="handleMentionSelect"
        />

        <div class="composer-toolbar">
          <button
            type="button"
            class="composer-submit"
            :disabled="!canSubmit"
            @click="submitDiscussion"
          >
            <i class="fas fa-paper-plane"></i>
            {{ submitting ? '发布中...' : (uploading ? '上传中...' : '发布讨论') }}
          </button>

          <div class="composer-formatting" aria-label="格式化工具栏">
            <button
              type="button"
              title="预览"
              :disabled="submitting || uploading"
              :class="{ 'is-active': showPreview }"
              @click="togglePreview"
            >
              <i class="far fa-eye"></i>
            </button>
            <template v-for="tool in composerTools" :key="tool.key">
              <div v-if="tool.key === 'emoji'" :ref="setEmojiToolRef" class="composer-tool">
                <button
                  type="button"
                  :title="tool.title"
                  :disabled="submitting || isSuspended || uploading"
                  :class="{ 'is-active': showEmojiPicker }"
                  @click="applyComposerTool(tool)"
                >
                  <i v-if="tool.icon" :class="tool.icon"></i>
                  <span v-else>{{ tool.label }}</span>
                </button>
                <ComposerEmojiPicker
                  v-if="showEmojiPicker"
                  :groups="emojiGroups"
                  :style-object="emojiPickerStyle"
                  @select="handleEmojiSelect"
                />
              </div>
              <button
                v-else
                type="button"
                :title="tool.title"
                :disabled="submitting || isSuspended || uploading"
                @click="applyComposerTool(tool)"
              >
                <i v-if="tool.icon" :class="tool.icon"></i>
                <span v-else>{{ tool.label }}</span>
              </button>
            </template>
          </div>

          <button type="button" class="composer-secondary" :disabled="submitting" @click="clearDraft">
            清除草稿
          </button>
        </div>

        <input
          ref="attachmentInput"
          type="file"
          class="composer-file-input"
          :disabled="submitting || isSuspended || uploading"
          @change="handleAttachmentSelected"
        />
        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          class="composer-file-input"
          :disabled="submitting || isSuspended || uploading"
          @change="handleImageSelected"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ComposerEmojiPicker from '@/components/ComposerEmojiPicker.vue'
import ComposerMentionPicker from '@/components/ComposerMentionPicker.vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import api from '@/api'
import {
  EMOJI_GROUPS,
  buildMentionTrigger,
  buildMentionReplacement,
  buildComposerToolReplacement,
  buildUploadedFileMarkdown,
  detectMentionQuery,
  defaultToolCursorOffset,
  fetchComposerPreview,
  getComposerErrorMessage,
  getTextareaCaretCoordinates,
  replaceSelection,
  uploadComposerFile
} from '@/utils/composer'
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
const uploading = ref(false)
const titleInput = ref(null)
const composerTextarea = ref(null)
const attachmentInput = ref(null)
const imageInput = ref(null)
const emojiToolRef = ref(null)
const draftSavedAt = ref('')
const draftMessage = ref('')
const uploadNotice = ref('')
const uploadNoticeTone = ref('info')
const showEmojiPicker = ref(false)
const mentionUsers = ref([])
const mentionState = ref(null)
const mentionCaret = ref(null)
const mentionLoading = ref(false)
const mentionActiveIndex = ref(0)
const showPreview = ref(false)
const previewHtml = ref('')
const previewLoading = ref(false)
const previewError = ref('')
let draftTimer = null
let previewTimer = null
let mentionTimer = null
let mentionRequestId = 0
const composerHeight = ref(loadComposerHeight())
const resizing = ref(false)
const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
let resizeStartY = 0
let resizeStartHeight = composerHeight.value

const composerTools = [
  { key: 'upload', title: '上传附件', icon: 'fas fa-file-upload' },
  { key: 'heading', title: '标题', label: 'H', before: '## ', after: '' },
  { key: 'bold', title: '加粗', label: 'B', before: '**', after: '**' },
  { key: 'italic', title: '斜体', label: 'I', before: '*', after: '*' },
  { key: 'strike', title: '删除线', label: 'S', before: '~~', after: '~~' },
  { key: 'quote', title: '引用', icon: 'fas fa-quote-left' },
  { key: 'spoiler', title: '提示/警告', icon: 'fas fa-exclamation-triangle', before: '> **提示：** ', after: '' },
  { key: 'code', title: '代码', icon: 'fas fa-code', before: '`', after: '`' },
  { key: 'link', title: '链接', icon: 'fas fa-link' },
  { key: 'image', title: '图片', icon: 'fas fa-image' },
  { key: 'bullets', title: '无序列表', icon: 'fas fa-list-ul' },
  { key: 'ordered', title: '有序列表', icon: 'fas fa-list-ol' },
  { key: 'mention', title: '@ 提及', icon: 'fas fa-at', before: '@', after: '' },
  { key: 'emoji', title: '表情', icon: 'far fa-smile' }
]
const emojiGroups = EMOJI_GROUPS

const availableTags = computed(() => flattenTags(tags.value))
const showComposer = computed(() => {
  return composerStore.isOpen && composerStore.current.type === 'discussion' && authStore.isAuthenticated
})
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
    !uploading.value &&
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
  if (composerStore.isMinimized) return minimizedSummary.value
  if (draftMessage.value) return draftMessage.value
  if (draftSavedAt.value) return `草稿保存于 ${formatDraftTime(draftSavedAt.value)}`
  if (selectedTagName.value) return `将发布到 ${selectedTagName.value}`
  return '支持 Markdown，可最小化继续编辑。'
})
const minimizedSummary = computed(() => {
  if (form.value.title.trim()) return form.value.title.trim()
  if (selectedTagName.value) return `新讨论 · ${selectedTagName.value}`
  return '发起讨论'
})
const unsavedExitMessage = '你有未发布的讨论内容。确定要离开当前页面吗？'
const isPhoneViewport = computed(() => viewportWidth.value <= 768)
const isPhoneOverlay = computed(() => isPhoneViewport.value && showComposer.value && !composerStore.isMinimized)
const showBackdrop = computed(() => isPhoneOverlay.value)
const showMentionPicker = computed(() => {
  return Boolean(mentionState.value) && (mentionLoading.value || mentionUsers.value.length > 0)
})
const composerInlineStyle = computed(() => {
  if (composerStore.isMinimized || composerStore.isExpanded || isPhoneOverlay.value) return {}
  return { height: `${composerHeight.value}px` }
})
const previewStatusText = computed(() => {
  if (previewLoading.value) return '同步中'
  if (!form.value.content.trim()) return '暂无内容'
  return '按论坛最终渲染效果预览'
})
const emojiPickerStyle = computed(() => {
  const anchor = emojiToolRef.value
  if (!anchor) return {}

  const rect = anchor.getBoundingClientRect()
  const pickerWidth = Math.min(320, Math.max(220, window.innerWidth - 32))
  const left = Math.max(16, Math.min(rect.right - pickerWidth, window.innerWidth - pickerWidth - 16))
  const top = Math.max(16, rect.top - 12)

  return {
    left: `${left}px`,
    top: `${top}px`,
    transform: 'translateY(-100%)'
  }
})
const mentionPickerStyle = computed(() => {
  const anchor = mentionCaret.value
  if (!anchor) return {}

  const pickerWidth = Math.min(320, Math.max(240, window.innerWidth - 32))
  const pickerHeight = Math.min(280, Math.max(180, window.innerHeight - 32))
  const left = Math.max(16, Math.min(anchor.left, window.innerWidth - pickerWidth - 16))
  const belowTop = anchor.top + anchor.lineHeight + 8
  const openAbove = belowTop + pickerHeight > window.innerHeight - 16 && anchor.top > pickerHeight + 24

  return {
    left: `${left}px`,
    top: openAbove ? `${anchor.top - 8}px` : `${belowTop}px`,
    transform: openAbove ? 'translateY(-100%)' : 'none'
  }
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
    if (!showComposer.value) return
    await prepareComposer()
  }
)

watch(
  form,
  () => {
    if (!composerStore.isOpen) return
    scheduleDraftSave()
    schedulePreview()
  },
  { deep: true }
)

watch(
  hasDraftContent,
  value => {
    composerStore.setUnsavedState(value, unsavedExitMessage)
  },
  { immediate: true }
)

watch(
  () => authStore.isAuthenticated,
  isAuthenticated => {
    if (!isAuthenticated) {
      composerStore.closeComposer()
    }
  }
)

watch(
  [
    () => composerStore.isOpen,
    () => composerStore.isMinimized,
    () => composerStore.isExpanded,
    composerHeight,
    isPhoneViewport
  ],
  () => {
    syncComposerViewportEffects()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (draftTimer) {
    clearTimeout(draftTimer)
  }
  if (previewTimer) {
    clearTimeout(previewTimer)
  }
  if (mentionTimer) {
    clearTimeout(mentionTimer)
  }
  window.removeEventListener('resize', handleViewportResize)
  window.removeEventListener('mousemove', handleResizeMove)
  window.removeEventListener('mouseup', stopResize)
  document.removeEventListener('mousedown', handleDocumentMouseDown)
  clearComposerViewportEffects()
})

onMounted(() => {
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener('mousemove', handleResizeMove)
  window.addEventListener('mouseup', stopResize)
  document.addEventListener('mousedown', handleDocumentMouseDown)
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
  showPreview.value = false
  composerTextarea.value?.focus()
  handleEditorInteraction()
}

function toggleMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    focusPreferredField()
    handleEditorInteraction()
  }
}

function toggleExpanded() {
  composerStore.toggleExpanded()
  focusPreferredField()
}

function togglePreview() {
  showPreview.value = !showPreview.value
  previewError.value = ''
  showEmojiPicker.value = false
  clearMentionSuggestions()

  if (showPreview.value) {
    requestPreview()
    return
  }

  nextTick(() => composerTextarea.value?.focus())
}

function handleHeaderSummaryClick() {
  if (!composerStore.isMinimized) return
  composerStore.showComposer()
  focusPreferredField()
  handleEditorInteraction()
}

function handleViewportResize() {
  viewportWidth.value = window.innerWidth
  if (mentionState.value) {
    nextTick(() => {
      syncMentionSuggestions()
    })
  }
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
  if (hasDraftContent.value && !confirm('确定要关闭发帖编辑器吗？当前内容会保留在本地草稿中。')) {
    return
  }
  showEmojiPicker.value = false
  showPreview.value = false
  clearMentionSuggestions()
  uploadNotice.value = ''
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

  showEmojiPicker.value = false
  submitting.value = true
  draftMessage.value = ''

  try {
    const data = await api.post('/discussions', {
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

  if (tool.key === 'upload') {
    showEmojiPicker.value = false
    clearMentionSuggestions()
    attachmentInput.value?.click()
    return
  }
  if (tool.key === 'image') {
    showEmojiPicker.value = false
    clearMentionSuggestions()
    imageInput.value?.click()
    return
  }
  if (tool.key === 'emoji') {
    clearMentionSuggestions()
    if (showPreview.value) {
      showPreview.value = false
      await nextTick()
    }
    showEmojiPicker.value = !showEmojiPicker.value
    if (showEmojiPicker.value) {
      composerTextarea.value?.focus()
    }
    return
  }

  const textarea = composerTextarea.value
  if (!textarea) return

  const start = textarea.selectionStart ?? form.value.content.length
  const end = textarea.selectionEnd ?? form.value.content.length
  if (tool.key === 'mention') {
    const replacement = buildMentionTrigger(form.value.content, start)
    await insertComposerText(replacement, {
      start,
      end,
      cursor: start + replacement.length
    })
    return
  }
  const selected = form.value.content.slice(start, end)
  const replacement = buildComposerToolReplacement(tool, selected)
  const cursor = selected ? start + replacement.length : start + defaultToolCursorOffset(tool)

  await insertComposerText(replacement, { start, end, cursor })
}

function handleEditorInteraction(event) {
  if (
    event?.type === 'keyup' &&
    ['ArrowUp', 'ArrowDown', 'Enter', 'Escape', 'Tab'].includes(event.key)
  ) {
    return
  }
  syncMentionSuggestions()
}

function handleEditorKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    submitDiscussion()
    return
  }

  if (event.key === 'Escape') {
    if (showMentionPicker.value) {
      event.preventDefault()
      clearMentionSuggestions()
      return
    }
    if (showEmojiPicker.value) {
      event.preventDefault()
      showEmojiPicker.value = false
      return
    }
    if (showPreview.value) {
      event.preventDefault()
      showPreview.value = false
      nextTick(() => composerTextarea.value?.focus())
      return
    }
    event.preventDefault()
    closeComposer()
    return
  }

  if (!showMentionPicker.value) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    mentionActiveIndex.value = (mentionActiveIndex.value + 1) % Math.max(mentionUsers.value.length, 1)
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    mentionActiveIndex.value =
      (mentionActiveIndex.value - 1 + Math.max(mentionUsers.value.length, 1)) % Math.max(mentionUsers.value.length, 1)
    return
  }

  if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey) {
    const activeUser = mentionUsers.value[mentionActiveIndex.value]
    if (!activeUser) return
    event.preventDefault()
    handleMentionSelect(activeUser)
    return
  }

  if (event.key === 'Escape') {
    clearMentionSuggestions()
  }
}

async function handleAttachmentSelected(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  await uploadAndInsertFile(file, false)
}

async function handleImageSelected(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  await uploadAndInsertFile(file, true)
}

async function uploadAndInsertFile(file, asImage) {
  uploading.value = true
  uploadNoticeTone.value = 'info'
  uploadNotice.value = `正在上传${asImage ? '图片' : '附件'}：${file.name}`
  showEmojiPicker.value = false

  try {
    const uploaded = await uploadComposerFile(file)
    if (!showComposer.value) return

    const markdown = buildUploadedFileMarkdown(uploaded.original_name || file.name, uploaded.url, {
      image: asImage
    })
    await insertComposerText(markdown)
    uploadNoticeTone.value = 'success'
    uploadNotice.value = `${asImage ? '图片' : '附件'}已插入编辑器`
  } catch (error) {
    const message = getComposerErrorMessage(error, asImage ? '图片上传失败' : '附件上传失败')
    uploadNoticeTone.value = 'error'
    uploadNotice.value = message
    alert(message)
  } finally {
    uploading.value = false
  }
}

async function handleEmojiSelect(emoji) {
  showEmojiPicker.value = false
  await insertComposerText(emoji)
}

function syncMentionSuggestions() {
  if (showPreview.value) {
    clearMentionSuggestions()
    return
  }

  const textarea = composerTextarea.value
  if (!textarea || textarea.selectionStart !== textarea.selectionEnd) {
    clearMentionSuggestions()
    return
  }

  const detected = detectMentionQuery(form.value.content, textarea.selectionStart)
  if (!detected) {
    clearMentionSuggestions()
    return
  }

  mentionState.value = detected
  mentionCaret.value = getTextareaCaretCoordinates(textarea, detected.start)
  scheduleMentionSearch(detected.query)
}

function scheduleMentionSearch(query) {
  if (mentionTimer) {
    clearTimeout(mentionTimer)
  }

  mentionLoading.value = true
  const requestId = ++mentionRequestId
  mentionTimer = setTimeout(async () => {
    try {
      const users = await api.get('/users', {
        params: {
          q: query,
          limit: 5
        }
      })
      if (requestId !== mentionRequestId || !mentionState.value) return
      mentionUsers.value = Array.isArray(users) ? users.slice(0, 5) : []
      mentionActiveIndex.value = 0
    } catch (error) {
      if (requestId !== mentionRequestId) return
      mentionUsers.value = []
    } finally {
      if (requestId === mentionRequestId) {
        mentionLoading.value = false
      }
    }
  }, 150)
}

async function handleMentionSelect(user) {
  if (!mentionState.value || !user?.username) return

  const replacement = buildMentionReplacement(user.username)
  await insertComposerText(replacement, {
    start: mentionState.value.start,
    end: mentionState.value.end,
    cursor: mentionState.value.start + replacement.length
  })
  clearMentionSuggestions()
}

function schedulePreview() {
  if (!showPreview.value) return

  if (previewTimer) {
    clearTimeout(previewTimer)
  }

  previewTimer = setTimeout(() => {
    requestPreview()
  }, 220)
}

async function requestPreview() {
  if (!showPreview.value) return

  const content = form.value.content.trim()
  previewError.value = ''
  if (!content) {
    previewHtml.value = ''
    previewLoading.value = false
    return
  }

  previewLoading.value = true
  try {
    const data = await fetchComposerPreview(form.value.content)
    if (!showPreview.value) return
    previewHtml.value = data.html || ''
  } catch (error) {
    previewError.value = getComposerErrorMessage(error, '预览加载失败')
  } finally {
    previewLoading.value = false
  }
}

async function insertComposerText(replacement, options = {}) {
  await nextTick()

  const textarea = composerTextarea.value
  const content = form.value.content
  const start = options.start ?? textarea?.selectionStart ?? content.length
  const end = options.end ?? textarea?.selectionEnd ?? content.length
  const cursor = options.cursor ?? start + replacement.length

  form.value.content = replaceSelection(content, start, end, replacement)

  await nextTick()
  composerTextarea.value?.focus()
  composerTextarea.value?.setSelectionRange(cursor, cursor)
  syncMentionSuggestions()
}

function handleDocumentMouseDown(event) {
  if (showEmojiPicker.value && !emojiToolRef.value?.contains(event.target)) {
    showEmojiPicker.value = false
  }
  if (event.target !== composerTextarea.value) {
    clearMentionSuggestions()
  }
}

function setEmojiToolRef(element) {
  emojiToolRef.value = element
}

function clearMentionSuggestions() {
  if (mentionTimer) {
    clearTimeout(mentionTimer)
  }
  mentionLoading.value = false
  mentionUsers.value = []
  mentionState.value = null
  mentionCaret.value = null
  mentionActiveIndex.value = 0
}

function resetComposer() {
  clearDraftStorage()
  form.value = {
    title: '',
    content: '',
    tag_id: ''
  }
  uploadNotice.value = ''
  showEmojiPicker.value = false
  showPreview.value = false
  previewHtml.value = ''
  previewError.value = ''
  clearMentionSuggestions()
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

function syncComposerViewportEffects() {
  if (typeof document === 'undefined') return
  if (composerStore.isOpen && !showComposer.value) return

  const activeDesktopComposer =
    showComposer.value &&
    !composerStore.isMinimized &&
    !composerStore.isExpanded &&
    !isPhoneViewport.value

  document.documentElement.style.setProperty('--composer-offset', activeDesktopComposer ? `${composerHeight.value + 24}px` : '0px')
  document.body.style.overflow = showBackdrop.value ? 'hidden' : ''
}

function clearComposerViewportEffects() {
  if (typeof document === 'undefined') return
  document.documentElement.style.setProperty('--composer-offset', '0px')
  document.body.style.overflow = ''
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

.floating-composer.is-phone-overlay {
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

.composer-title--clickable {
  cursor: pointer;
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

.composer-notice-success {
  background: #edf9f1;
  color: #256b3c;
}

.composer-notice-error {
  background: #fdf0f0;
  color: #b33a3a;
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

.composer-preview {
  display: flex;
  flex: 1;
  min-height: 140px;
  flex-direction: column;
  padding: 14px 0 12px;
}

.composer-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #5c6d7d;
  font-size: 13px;
}

.composer-preview-loading,
.composer-preview-empty {
  color: #7a8794;
  font-size: 14px;
}

.composer-preview-body {
  flex: 1;
  overflow-y: auto;
  line-height: 1.7;
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

.composer-tool {
  position: relative;
  flex-shrink: 0;
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

.composer-formatting button.is-active {
  background: #e3ecf5;
  color: #325b88;
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

.composer-file-input {
  display: none;
}

.composer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(23, 30, 38, 0.4);
  z-index: 899;
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
