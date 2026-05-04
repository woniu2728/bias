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
      <ComposerHeaderBar
        :title="composerTitle"
        :summary-clickable="composerStore.isMinimized"
        :show-save="!isEditing"
        :submitting="submitting"
        :minimized="composerStore.isMinimized"
        :expanded="composerStore.isExpanded"
        minimize-icon="fas fa-minus minimize"
        @title-click="handleHeaderSummaryClick"
        @save="saveComposerDraft()"
        @toggle-minimized="toggleComposerMinimized"
        @toggle-expanded="toggleComposerExpanded"
        @close="closeComposer"
      >
        <template #subtitle>
          <router-link :to="discussionLink" class="composer-link" @click="handleHeaderLinkClick">
            {{ composerSubtitle }}
          </router-link>
        </template>
      </ComposerHeaderBar>

      <div v-show="!composerStore.isMinimized" class="composer-body">
        <ComposerNoticeStack :notices="composerNotices" />
        <textarea
          v-show="!showPreview"
          ref="composerTextarea"
          v-model="replyContent"
          placeholder="输入你的回复... 支持 Markdown、@用户名 和代码块"
          rows="7"
          :disabled="submitting || uploading || isSuspended"
          @input="handleEditorInteraction"
          @click="handleEditorInteraction"
          @keyup="handleEditorInteraction"
          @scroll="handleEditorInteraction"
          @keydown="handleEditorKeydown"
        ></textarea>
        <ComposerPreviewPanel
          v-if="showPreview"
          :loading="previewLoading"
          :status-text="previewStatusText"
          :html="previewHtml"
        />
        <ComposerMentionPicker
          v-if="showMentionPicker"
          :items="mentionUsers"
          :active-index="mentionActiveIndex"
          :loading="mentionLoading"
          :style-object="mentionPickerStyle"
          @highlight="mentionActiveIndex = $event"
          @select="handleMentionSelect"
        />
        <ComposerEmojiAutocomplete
          v-if="showEmojiAutocomplete"
          :items="emojiSuggestions"
          :active-index="emojiAutocompleteActiveIndex"
          :style-object="emojiAutocompleteStyle"
          @highlight="emojiAutocompleteActiveIndex = $event"
          @select="handleEmojiAutocompleteSelect"
        />

        <ComposerActionBar
          :submit-disabled="submitting || uploading || !replyContent.trim() || isSuspended"
          :submit-text="submitting ? '提交中...' : (uploading ? '上传中...' : (isEditing ? '更新回复' : '发布回复'))"
          @submit="submitReply"
        >
          <template #formatting>
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
                  :disabled="submitting || uploading || isSuspended"
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
                :disabled="submitting || uploading || isSuspended"
                @click="applyComposerTool(tool)"
              >
                <i v-if="tool.icon" :class="tool.icon"></i>
                <span v-else>{{ tool.label }}</span>
              </button>
            </template>
          </template>

          <template #secondary>
            <button
              v-if="composerDraftSavedAt && !isEditing"
              type="button"
              class="composer-secondary"
              @click="clearComposerDraft"
            >
              清除草稿
            </button>
            <button v-if="isEditing" type="button" class="composer-secondary" @click="cancelEdit">取消编辑</button>
          </template>
        </ComposerActionBar>

        <input
          ref="attachmentInput"
          type="file"
          class="composer-file-input"
          :disabled="submitting || uploading || isSuspended"
          @change="handleAttachmentSelected"
        />
        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          class="composer-file-input"
          :disabled="submitting || uploading || isSuspended"
          @change="handleImageSelected"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ComposerEmojiAutocomplete from '@/components/ComposerEmojiAutocomplete.vue'
import ComposerEmojiPicker from '@/components/ComposerEmojiPicker.vue'
import ComposerActionBar from '@/components/composer/ComposerActionBar.vue'
import ComposerHeaderBar from '@/components/composer/ComposerHeaderBar.vue'
import ComposerNoticeStack from '@/components/composer/ComposerNoticeStack.vue'
import ComposerPreviewPanel from '@/components/composer/ComposerPreviewPanel.vue'
import ComposerMentionPicker from '@/components/ComposerMentionPicker.vue'
import { getComposerNotices, getComposerTools, runComposerSubmitGuards } from '@/forum/registry'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useModalStore } from '@/stores/modal'
import api from '@/api'
import {
  BASE_COMPOSER_TOOLS,
  COMPOSER_EMOJI_PICKER_WIDTH,
  EMOJI_GROUPS,
  buildEmojiReplacement,
  buildMentionTrigger,
  buildMentionReplacement,
  buildComposerToolReplacement,
  buildUploadedFileMarkdown,
  detectEmojiQuery,
  detectMentionQuery,
  defaultToolCursorOffset,
  fetchComposerPreview,
  getComposerErrorMessage,
  getTextareaCaretCoordinates,
  replaceSelection,
  searchEmojiItems,
  uploadComposerFile
} from '@/utils/composer'
import { normalizePost } from '@/utils/forum'
import { renderTwemojiHtml } from '@/utils/twemoji'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()

const replyContent = ref('')
const submitting = ref(false)
const uploading = ref(false)
const composerTextarea = ref(null)
const attachmentInput = ref(null)
const imageInput = ref(null)
const emojiToolRef = ref(null)
const composerDraftSavedAt = ref('')
const draftNotice = ref('')
const draftNoticeTone = ref('info')
const uploadNotice = ref('')
const uploadNoticeTone = ref('info')
const submitNotice = ref('')
const submitNoticeTone = ref('info')
const showEmojiPicker = ref(false)
const emojiSuggestions = ref([])
const emojiAutocompleteState = ref(null)
const emojiAutocompleteCaret = ref(null)
const emojiAutocompleteActiveIndex = ref(0)
const mentionUsers = ref([])
const mentionState = ref(null)
const mentionCaret = ref(null)
const mentionLoading = ref(false)
const mentionActiveIndex = ref(0)
const showPreview = ref(false)
const previewHtml = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const composerHeight = ref(loadComposerHeight())
const resizing = ref(false)
const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
let resizeStartY = 0
let resizeStartHeight = composerHeight.value
let previewTimer = null
let mentionTimer = null
let mentionRequestId = 0

const emojiGroups = EMOJI_GROUPS

const showComposer = computed(() => {
  return composerStore.isOpen && ['reply', 'edit'].includes(composerStore.current.type) && authStore.isAuthenticated
})
const isEditing = computed(() => composerStore.current.type === 'edit')
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
const dirtyState = computed(() => {
  if (!showComposer.value) return false
  if (isEditing.value) {
    return replyContent.value.trim() !== String(composerStore.current.initialContent || '').trim()
  }
  return Boolean(replyContent.value.trim())
})
const discussionId = computed(() => Number(composerStore.current.discussionId || 0))
const discussionLink = computed(() => {
  if (!discussionId.value) return '/'
  if (composerStore.current.postNumber) {
    return `/d/${discussionId.value}?near=${composerStore.current.postNumber}`
  }
  return `/d/${discussionId.value}`
})
const composerTitle = computed(() => {
  if (isEditing.value) return `编辑 #${composerStore.current.postNumber || ''}`.trim()
  if (composerStore.current.postNumber) return `回复 #${composerStore.current.postNumber}`
  return `回复：${composerStore.current.discussionTitle || '讨论'}`
})
const composerSubtitle = computed(() => {
  if (composerStore.isMinimized) return minimizedSummary.value
  if (isEditing.value) {
    return `${composerStore.current.discussionTitle || '讨论'} · 编辑后会直接更新原帖`
  }
  if (composerDraftSavedAt.value) return `草稿已保存于 ${formatDraftTime(composerDraftSavedAt.value)}`
  if (composerStore.current.username) {
    return `${composerStore.current.discussionTitle || '讨论'} · @${composerStore.current.username}`
  }
  return composerStore.current.discussionTitle || '讨论'
})
const minimizedSummary = computed(() => {
  const content = replyContent.value.trim()
  if (content) {
    return content.length > 36 ? `${content.slice(0, 36)}...` : content
  }
  if (isEditing.value) return `编辑 #${composerStore.current.postNumber || ''}`.trim()
  if (composerStore.current.postNumber) return `回复 #${composerStore.current.postNumber}`
  return composerStore.current.discussionTitle || '回复讨论'
})
const isPhoneViewport = computed(() => viewportWidth.value <= 768)
const isPhoneOverlay = computed(() => isPhoneViewport.value && showComposer.value && !composerStore.isMinimized)
const showBackdrop = computed(() => isPhoneOverlay.value)
const showMentionPicker = computed(() => {
  return Boolean(mentionState.value) && (mentionLoading.value || mentionUsers.value.length > 0)
})
const showEmojiAutocomplete = computed(() => {
  return Boolean(emojiAutocompleteState.value) && emojiSuggestions.value.length > 0
})
const composerInlineStyle = computed(() => {
  if (composerStore.isMinimized || composerStore.isExpanded || isPhoneOverlay.value) return {}
  return { height: `${composerHeight.value}px` }
})
const previewStatusText = computed(() => {
  if (previewLoading.value) return '同步中'
  if (!replyContent.value.trim()) return '暂无内容'
  return '按论坛最终渲染效果预览'
})
const composerTools = computed(() => {
  return [...BASE_COMPOSER_TOOLS, ...getComposerTools(buildComposerExtensionContext())]
    .sort((left, right) => (left.order || 100) - (right.order || 100))
})
const composerNotices = computed(() => {
  return [
    {
      key: 'draft',
      label: '草稿',
      tone: draftNoticeTone.value,
      message: draftNotice.value
    },
    {
      key: 'upload',
      label: '上传',
      tone: uploadNoticeTone.value,
      message: uploadNotice.value
    },
    {
      key: 'preview',
      label: '预览',
      tone: 'error',
      message: previewError.value
    },
    {
      key: 'submit',
      label: isEditing.value ? '保存' : '发布',
      tone: submitNoticeTone.value,
      message: submitNotice.value
    },
    ...getComposerNotices(buildComposerExtensionContext())
  ]
    .filter(item => item?.message)
})
const emojiPickerStyle = computed(() => {
  const anchor = emojiToolRef.value
  if (!anchor) return {}

  const rect = anchor.getBoundingClientRect()
  const pickerWidth = Math.min(COMPOSER_EMOJI_PICKER_WIDTH, Math.max(280, window.innerWidth - 32))
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
const emojiAutocompleteStyle = computed(() => {
  const anchor = emojiAutocompleteCaret.value
  if (!anchor) return {}

  const pickerWidth = Math.min(320, Math.max(240, window.innerWidth - 32))
  const pickerHeight = Math.min(320, Math.max(180, window.innerHeight - 32))
  const left = Math.max(16, Math.min(anchor.left, window.innerWidth - pickerWidth - 16))
  const belowTop = anchor.top + anchor.lineHeight + 8
  const openAbove = belowTop + pickerHeight > window.innerHeight - 16 && anchor.top > pickerHeight + 24

  return {
    left: `${left}px`,
    top: openAbove ? `${anchor.top - 8}px` : `${belowTop}px`,
    transform: openAbove ? 'translateY(-100%)' : 'none'
  }
})
const unsavedExitMessage = computed(() => {
  return isEditing.value
    ? '你有未保存的帖子编辑内容。确定要离开当前页面吗？'
    : '你有未发布的回复内容。确定要离开当前页面吗？'
})
const suspensionNotice = computed(() => {
  if (!isSuspended.value) return ''

  const user = authStore.user || {}
  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}，暂时无法回复、编辑或上传附件。`
    : '账号当前已被封禁，暂时无法回复、编辑或上传附件。'
})

watch(
  () => composerStore.current.requestId,
  async () => {
    if (!showComposer.value) return

    if (isEditing.value) {
      composerDraftSavedAt.value = ''
      draftNotice.value = ''
      submitNotice.value = ''
      replyContent.value = composerStore.current.initialContent || ''
    } else if (composerStore.current.initialContent?.trim()) {
      composerDraftSavedAt.value = ''
      draftNotice.value = ''
      submitNotice.value = ''
      replyContent.value = composerStore.current.initialContent
    } else {
      restoreComposerDraft()
    }

    await nextTick()
    if (!composerStore.isMinimized) {
      composerTextarea.value?.focus()
    }
  }
)

watch(
  () => authStore.isAuthenticated,
  value => {
    if (!value) {
      resetComposerState()
    }
  }
)

watch(
  replyContent,
  () => {
    schedulePreview()
  }
)

watch(
  [dirtyState, unsavedExitMessage],
  ([value, message]) => {
    composerStore.setUnsavedState(value, message)
  },
  { immediate: true }
)

watch(
  [
    showComposer,
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

onMounted(() => {
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener('mousemove', handleResizeMove)
  window.addEventListener('mouseup', stopResize)
  document.addEventListener('mousedown', handleDocumentMouseDown)
})

onBeforeUnmount(() => {
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

function handleHeaderLinkClick(event) {
  if (composerStore.isMinimized) {
    event.preventDefault()
    composerStore.showComposer()
    nextTick(() => composerTextarea.value?.focus())
    return
  }

  if (composerStore.isExpanded) {
    composerStore.toggleExpanded()
    composerStore.showComposer()
  }
}

function handleHeaderSummaryClick() {
  if (!composerStore.isMinimized) return
  composerStore.showComposer()
  nextTick(() => composerTextarea.value?.focus())
  handleEditorInteraction()
}

function handleViewportResize() {
  viewportWidth.value = window.innerWidth
  if (mentionState.value || emojiAutocompleteState.value) {
    nextTick(() => {
      syncInlineSuggestions()
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

function toggleComposerMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    nextTick(() => composerTextarea.value?.focus())
    handleEditorInteraction()
  }
}

function toggleComposerExpanded() {
  composerStore.toggleExpanded()
  nextTick(() => composerTextarea.value?.focus())
}

function togglePreview() {
  showPreview.value = !showPreview.value
  previewError.value = ''
  submitNotice.value = ''
  showEmojiPicker.value = false
  clearMentionSuggestions()
  clearEmojiAutocomplete()

  if (showPreview.value) {
    requestPreview()
    return
  }

  nextTick(() => composerTextarea.value?.focus())
}

async function closeComposer(force = false) {
  if (!force && dirtyState.value) {
    const confirmed = await modalStore.confirm({
      title: isEditing.value ? '关闭编辑器' : '关闭回复框',
      message: isEditing.value
        ? '确定要关闭编辑器吗？未保存修改将丢失。'
        : '确定要关闭回复框吗？当前内容会保留在本地草稿中。',
      confirmText: '关闭',
      cancelText: '继续编辑'
    })
    if (!confirmed) return
  }

  showEmojiPicker.value = false
  showPreview.value = false
  clearMentionSuggestions()
  clearEmojiAutocomplete()
  if (!isEditing.value) {
    saveComposerDraft(false)
  }
  resetComposerState()
}

function cancelEdit() {
  closeComposer(true)
}

function resetComposerState() {
  composerStore.closeComposer()
  composerDraftSavedAt.value = ''
  draftNotice.value = ''
  uploadNotice.value = ''
  submitNotice.value = ''
  showEmojiPicker.value = false
  showPreview.value = false
  previewHtml.value = ''
  previewError.value = ''
  clearMentionSuggestions()
  clearEmojiAutocomplete()
  replyContent.value = ''
}

function hasUnsavedChanges() {
  return dirtyState.value
}

function getComposerDraftKey() {
  if (!discussionId.value || isEditing.value) return null
  return `bias:discussion:${discussionId.value}:draft:${authStore.user?.id || 'guest'}`
}

function restoreComposerDraft() {
  if (typeof window === 'undefined') return false

  composerDraftSavedAt.value = ''
  draftNotice.value = ''
  const key = getComposerDraftKey()
  if (!key) return false

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      replyContent.value = ''
      return false
    }

    const draft = JSON.parse(raw)
    if (!draft?.content?.trim()) {
      replyContent.value = ''
      return false
    }

    replyContent.value = draft.content
    composerDraftSavedAt.value = draft.updatedAt || ''
    draftNoticeTone.value = 'success'
    draftNotice.value = composerDraftSavedAt.value
      ? `已恢复你在 ${formatDraftTime(composerDraftSavedAt.value)} 保存的回复草稿。`
      : '已恢复本地回复草稿。'
    return true
  } catch (error) {
    console.error('恢复草稿失败:', error)
    replyContent.value = ''
    draftNoticeTone.value = 'error'
    draftNotice.value = '回复草稿恢复失败。'
    return false
  }
}

function saveComposerDraft(showMessage = true) {
  if (typeof window === 'undefined' || isEditing.value) return

  const key = getComposerDraftKey()
  if (!key) return

  const content = replyContent.value.trim()
  if (!content) {
    window.localStorage.removeItem(key)
    composerDraftSavedAt.value = ''
    if (showMessage) {
      draftNoticeTone.value = 'success'
      draftNotice.value = '回复草稿已清空。'
    }
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    key,
    JSON.stringify({
      content: replyContent.value,
      updatedAt
    })
  )
  composerDraftSavedAt.value = updatedAt
  if (showMessage) {
    draftNoticeTone.value = 'success'
    draftNotice.value = '回复草稿已保存。'
  }
}

function clearComposerDraft() {
  if (typeof window === 'undefined') return

  const key = getComposerDraftKey()
  if (!key) return

  window.localStorage.removeItem(key)
  composerDraftSavedAt.value = ''
  draftNoticeTone.value = 'success'
  draftNotice.value = '已清除本地回复草稿。'
  replyContent.value = ''
  uploadNotice.value = ''
  submitNotice.value = ''
  showEmojiPicker.value = false
  showPreview.value = false
  previewHtml.value = ''
  previewError.value = ''
  clearMentionSuggestions()
  nextTick(() => composerTextarea.value?.focus())
}

async function applyComposerTool(tool) {
  composerStore.showComposer()
  await nextTick()

  if (typeof tool.run === 'function') {
    await tool.run(buildComposerToolContext(tool))
    return
  }

  if (tool.key === 'upload') {
    showEmojiPicker.value = false
    clearMentionSuggestions()
    clearEmojiAutocomplete()
    attachmentInput.value?.click()
    return
  }
  if (tool.key === 'image') {
    showEmojiPicker.value = false
    clearMentionSuggestions()
    clearEmojiAutocomplete()
    imageInput.value?.click()
    return
  }
  if (tool.key === 'emoji') {
    clearMentionSuggestions()
    clearEmojiAutocomplete()
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

  const start = textarea.selectionStart ?? replyContent.value.length
  const end = textarea.selectionEnd ?? replyContent.value.length
  if (tool.key === 'mention') {
    const replacement = buildMentionTrigger(replyContent.value, start)
    await insertComposerText(replacement, {
      start,
      end,
      cursor: start + replacement.length
    })
    return
  }
  const selected = replyContent.value.slice(start, end)
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
  syncInlineSuggestions()
}

function handleEditorKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    submitReply()
    return
  }

  if (event.key === 'Escape') {
    if (showMentionPicker.value) {
      event.preventDefault()
      clearMentionSuggestions()
      return
    }
    if (showEmojiAutocomplete.value) {
      event.preventDefault()
      clearEmojiAutocomplete()
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

  if (showEmojiAutocomplete.value) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      emojiAutocompleteActiveIndex.value =
        (emojiAutocompleteActiveIndex.value + 1) % Math.max(emojiSuggestions.value.length, 1)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      emojiAutocompleteActiveIndex.value =
        (emojiAutocompleteActiveIndex.value - 1 + Math.max(emojiSuggestions.value.length, 1)) % Math.max(emojiSuggestions.value.length, 1)
      return
    }

    if (
      (event.key === 'Enter' || event.key === 'Tab') &&
      !event.shiftKey &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    ) {
      const activeEmoji = emojiSuggestions.value[emojiAutocompleteActiveIndex.value]
      if (!activeEmoji) return
      event.preventDefault()
      handleEmojiAutocompleteSelect(activeEmoji)
      return
    }
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
  submitNotice.value = ''
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
  } finally {
    uploading.value = false
  }
}

async function handleEmojiSelect(emoji) {
  showEmojiPicker.value = false
  await insertComposerText(emoji)
}

async function handleEmojiAutocompleteSelect(item) {
  if (!emojiAutocompleteState.value || !item?.emoji) return

  const replacement = buildEmojiReplacement(item.emoji)
  await insertComposerText(replacement, {
    start: emojiAutocompleteState.value.start,
    end: emojiAutocompleteState.value.end,
    cursor: emojiAutocompleteState.value.start + replacement.length
  })
  clearEmojiAutocomplete()
}

function syncInlineSuggestions() {
  if (showPreview.value) {
    clearMentionSuggestions()
    clearEmojiAutocomplete()
    return
  }

  const textarea = composerTextarea.value
  if (!textarea || textarea.selectionStart !== textarea.selectionEnd) {
    clearMentionSuggestions()
    clearEmojiAutocomplete()
    return
  }

  const detected = detectMentionQuery(replyContent.value, textarea.selectionStart)
  if (detected) {
    clearEmojiAutocomplete()
    mentionState.value = detected
    mentionCaret.value = getTextareaCaretCoordinates(textarea, detected.start)
    scheduleMentionSearch(detected.query)
    return
  }

  clearMentionSuggestions()

  const detectedEmoji = detectEmojiQuery(replyContent.value, textarea.selectionStart)
  if (!detectedEmoji) {
    clearEmojiAutocomplete()
    return
  }

  emojiAutocompleteState.value = detectedEmoji
  emojiAutocompleteCaret.value = getTextareaCaretCoordinates(textarea, detectedEmoji.start)
  emojiSuggestions.value = searchEmojiItems(detectedEmoji.query, {
    limit: 8,
    includeCommonWhenEmpty: true
  })
  emojiAutocompleteActiveIndex.value = 0
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

  const content = replyContent.value.trim()
  previewError.value = ''
  if (!content) {
    previewHtml.value = ''
    previewLoading.value = false
    return
  }

  previewLoading.value = true
  try {
    const data = await fetchComposerPreview(replyContent.value)
    if (!showPreview.value) return
    previewHtml.value = renderTwemojiHtml(data.html || '')
  } catch (error) {
    previewError.value = getComposerErrorMessage(error, '预览加载失败')
  } finally {
    previewLoading.value = false
  }
}

async function insertComposerText(replacement, options = {}) {
  await nextTick()

  const textarea = composerTextarea.value
  const content = replyContent.value
  const start = options.start ?? textarea?.selectionStart ?? content.length
  const end = options.end ?? textarea?.selectionEnd ?? content.length
  const cursor = options.cursor ?? start + replacement.length

  replyContent.value = replaceSelection(content, start, end, replacement)

  await nextTick()
  composerTextarea.value?.focus()
  composerTextarea.value?.setSelectionRange(cursor, cursor)
  syncInlineSuggestions()
}

function handleDocumentMouseDown(event) {
  if (showEmojiPicker.value && !emojiToolRef.value?.contains(event.target)) {
    showEmojiPicker.value = false
  }
  if (event.target !== composerTextarea.value) {
    clearMentionSuggestions()
    clearEmojiAutocomplete()
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

function clearEmojiAutocomplete() {
  emojiSuggestions.value = []
  emojiAutocompleteState.value = null
  emojiAutocompleteCaret.value = null
  emojiAutocompleteActiveIndex.value = 0
}

async function submitReply() {
  if (!replyContent.value.trim() || !discussionId.value) return

  showEmojiPicker.value = false
  showPreview.value = false
  clearMentionSuggestions()
  clearEmojiAutocomplete()
  submitting.value = true
  submitNotice.value = ''
  submitNoticeTone.value = 'info'
  try {
    const blocked = await runComposerSubmitGuards({
      ...buildComposerExtensionContext(),
      modalStore,
      submitKind: isEditing.value ? 'edit-post' : 'reply',
    })
    if (blocked) {
      submitNoticeTone.value = blocked.tone || 'error'
      submitNotice.value = blocked.message || '当前内容未通过校验。'
      return
    }

    if (isEditing.value) {
      const data = await api.patch(`/posts/${composerStore.current.postId}`, {
        content: replyContent.value
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('bias:post-updated', {
        detail: {
          discussionId: discussionId.value,
          post
        }
      }))

      if (post.approval_status === 'pending') {
        await modalStore.alert({
          title: '回复已重新提交审核',
          message: '管理员通过后，这条回复才会重新显示给其他用户。'
        })
      }

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || composerStore.current.postNumber || 1}`)
      }
    } else {
      const data = await api.post(`/discussions/${discussionId.value}/posts`, {
        content: replyContent.value,
        reply_to_post_id: composerStore.current.postId || null
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('bias:reply-created', {
        detail: {
          discussionId: discussionId.value,
          post
        }
      }))

      if (post.approval_status === 'pending') {
        await modalStore.alert({
          title: '回复已进入审核队列',
          message: '管理员通过后，这条回复才会显示给其他用户。'
        })
      }

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || 1}`)
      }

      clearComposerDraft()
    }

    resetComposerState()
  } catch (error) {
    console.error('提交失败:', error)
    submitNoticeTone.value = 'error'
    submitNotice.value = error.response?.data?.error || error.message || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function isViewingCurrentDiscussion() {
  return route.name === 'discussion-detail' && Number(route.params.id) === discussionId.value
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}

function loadComposerHeight() {
  if (typeof window === 'undefined') return 420
  const value = Number(window.localStorage.getItem('bias:composer-height:post') || 420)
  return clampComposerHeight(value)
}

function persistComposerHeight(value) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('bias:composer-height:post', String(clampComposerHeight(value)))
}

function clampComposerHeight(value) {
  const min = 280
  const max = typeof window === 'undefined' ? 680 : Math.max(320, window.innerHeight - 72)
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

function formatAbsoluteDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

function buildComposerExtensionContext() {
  return {
    approvalNote: composerStore.current.approvalNote || '',
    approvalStatus: composerStore.current.approvalStatus || '',
    authStore,
    composerStore,
    content: replyContent.value,
    discussionId: discussionId.value,
    discussionTitle: composerStore.current.discussionTitle || '',
    isEditing: isEditing.value,
    mode: isEditing.value ? 'edit' : 'reply',
    postNumber: composerStore.current.postNumber ?? null,
    route,
    router,
    source: composerStore.current.source || '',
    suspensionNotice: suspensionNotice.value,
    type: 'post',
    username: composerStore.current.username || '',
  }
}

function buildComposerToolContext(tool) {
  const textarea = composerTextarea.value
  return {
    ...buildComposerExtensionContext(),
    tool,
    insertText: insertComposerText,
    focusEditor: () => composerTextarea.value?.focus(),
    openAttachmentPicker: () => attachmentInput.value?.click(),
    openImagePicker: () => imageInput.value?.click(),
    selectionEnd: textarea?.selectionEnd ?? replyContent.value.length,
    selectionStart: textarea?.selectionStart ?? replyContent.value.length,
    setEmojiPickerVisible(value) {
      showEmojiPicker.value = Boolean(value)
    },
    setPreviewVisible(value) {
      showPreview.value = Boolean(value)
    },
  }
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
  cursor: row-resize;
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

.composer-link {
  color: inherit;
}

.composer-link:hover {
  text-decoration: none;
}

.composer-body {
  padding: 0 20px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.composer-body textarea {
  width: 100%;
  padding: 4px 0 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.7;
  resize: none;
  min-height: 120px;
  max-height: none;
  flex: 1;
}

.floating-composer.is-expanded .composer-body textarea {
  min-height: calc(100vh - 170px);
  max-height: none;
}

.composer-body textarea:focus {
  outline: none;
  border: 0;
  box-shadow: none;
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

}
</style>
