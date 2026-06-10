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
        <ComposerStatusBar :items="composerStatusItems" />
        <textarea
          v-show="!showPreview"
          ref="composerTextarea"
          v-model="replyContent"
          :placeholder="contentPlaceholderText"
          rows="7"
          :disabled="submitting || uploading || isSuspended"
          @input="handleEditorActivity"
          @click="handleEditorActivity"
          @keyup="handleEditorActivity"
          @scroll="handleEditorActivity"
          @keydown="handleEditorKeydown"
        ></textarea>
        <ComposerPreviewPanel
          v-if="showPreview"
          :loading="previewLoading"
          :status-text="previewStatusText"
          :html="previewHtml"
        />
        <ComposerAutocompleteOutlet
          v-if="showAutocomplete"
          :active="activeAutocomplete"
          @highlight="handleAutocompleteHighlight"
          @select="handleAutocompleteSelect"
        />

        <ComposerActionBar
          :submit-disabled="submitting || uploading || !replyContent.trim() || isSuspended"
          :submit-text="submitButtonText"
          :secondary-actions="composerSecondaryActions"
          @submit="submitReply"
        >
          <template #formatting>
            <button
              type="button"
              :title="previewButtonTitleText"
              :disabled="submitting || uploading"
              :class="{ 'is-active': showPreview }"
              @click="togglePreview"
            >
              <i class="far fa-eye"></i>
            </button>
            <template v-for="tool in composerTools" :key="tool.key">
              <div v-if="tool.popoverComponent || tool.popover_component" class="composer-tool">
                <button
                  type="button"
                  :title="tool.title"
                  :disabled="submitting || uploading || isSuspended"
                  :class="{ 'is-active': activeToolPopover?.key === tool.key }"
                  @click="applyComposerTool(tool, $event)"
                >
                  <i v-if="tool.icon" :class="tool.icon"></i>
                  <span v-else>{{ tool.label }}</span>
                </button>
                <component
                  :is="activeToolPopover.component"
                  v-if="activeToolPopover?.key === tool.key"
                  v-bind="activeToolPopover.componentProps"
                  :style-object="activeToolPopover.styleObject"
                  @select="handleToolPopoverSelect"
                />
              </div>
              <button
                v-else
                type="button"
                :title="tool.title"
                :disabled="submitting || uploading || isSuspended"
                @click="applyComposerTool(tool, $event)"
              >
                <i v-if="tool.icon" :class="tool.icon"></i>
                <span v-else>{{ tool.label }}</span>
              </button>
            </template>
          </template>

          <template #secondary="{ items }">
            <button
              v-for="item in items"
              :key="item.key"
              type="button"
              class="composer-secondary"
              :disabled="submitting || item.disabled"
              @click="handleComposerSecondaryAction(item)"
            >
              {{ item.label }}
            </button>
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
import {
  useAuthStore } from '@bias/users'
import {
  api,
  watch,
  computed,
  nextTick,
  onBeforeUnmount,
  ref,
  useRoute,
  useRouter,
  useModalStore
} from '@bias/core'
import {
  ComposerActionBar,
  ComposerAutocompleteOutlet,
  ComposerHeaderBar,
  ComposerNoticeStack,
  ComposerPreviewPanel,
  ComposerStatusBar,
  getUiCopy,
  runComposerSubmitGuards,
  runComposerSubmitSuccess,
  useComposerRuntime,
  useComposerStore,
  useForumStore
} from '@bias/forum'
import { normalizePost } from '@bias/posts'
import { useForumRealtimeStore } from '@bias/realtime'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const forumRealtimeStore = useForumRealtimeStore()
const modalStore = useModalStore()

const replyContent = ref('')
const submitting = ref(false)
const composerDraftSavedAt = ref('')
const draftNotice = ref('')
const draftNoticeTone = ref('info')
const submitNotice = ref('')
const submitNoticeTone = ref('info')
const canSendTypingIndicator = computed(() => (
  showComposer.value
  && !isEditing.value
  && forumStore.settings.realtime_typing_enabled !== false
  && authStore.hasPermission('discussion.typing')
))

let typingActive = false
let typingIdleTimer = null

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

const runtime = useComposerRuntime({
  composerStore,
  showComposer,
  content: replyContent,
  submitting,
  submit: submitReply,
  closeComposer,
  buildBaseContext,
  focusEditor,
  openComposer: () => composerStore.showComposer(),
  saveRequestType: 'post',
  onSaveRequest: saveComposerDraft,
  height: {
    storageKey: 'bias:composer-height:post',
    defaultValue: 420,
    min: 280,
    maxDefault: 680,
    maxFloor: 320,
    windowOffset: 72,
  },
})

const {
  attachmentInput,
  activeAutocomplete,
  activeToolPopover,
  applyComposerTool,
  buildExtensionContext,
  clearRuntimeState,
  composerExtensionNotices,
  composerInlineStyle,
  composerSecondaryActions,
  composerStatusItems,
  composerTextarea,
  composerTools,
  handleAttachmentSelected,
  handleComposerSecondaryAction,
  handleEditorInteraction,
  handleEditorKeydown,
  handleAutocompleteHighlight,
  handleAutocompleteSelect,
  handleImageSelected,
  handleToolPopoverSelect,
  imageInput,
  isPhoneOverlay,
  previewError,
  previewHtml,
  previewLoading,
  showBackdrop,
  showAutocomplete,
  showPreview,
  startResize,
  syncInlineSuggestions,
  togglePreview,
  uploadNotice,
  uploadNoticeTone,
  uploading,
} = runtime

const composerTitle = computed(() => {
  return getUiCopy({
    surface: 'post-composer-title',
    isEditing: isEditing.value,
    postNumber: composerStore.current.postNumber || '',
    discussionTitle: composerStore.current.discussionTitle || '',
  })?.text || (isEditing.value
    ? `编辑 #${composerStore.current.postNumber || ''}`.trim()
    : (composerStore.current.postNumber
        ? `回复 #${composerStore.current.postNumber}`
        : `回复：${composerStore.current.discussionTitle || '讨论'}`))
})
const composerSubtitle = computed(() => {
  if (composerStore.isMinimized) return minimizedSummary.value
  return getUiCopy({
    surface: 'post-composer-subtitle',
    isEditing: isEditing.value,
    discussionTitle: composerStore.current.discussionTitle || '',
    hasDraftSavedAt: Boolean(composerDraftSavedAt.value),
    draftSavedAtText: composerDraftSavedAt.value ? formatDraftTime(composerDraftSavedAt.value) : '',
    username: composerStore.current.username || '',
  })?.text || (isEditing.value
    ? `${composerStore.current.discussionTitle || '讨论'} · 编辑后会直接更新原帖`
    : (composerDraftSavedAt.value
        ? `草稿已保存于 ${formatDraftTime(composerDraftSavedAt.value)}`
        : (composerStore.current.username
            ? `${composerStore.current.discussionTitle || '讨论'} · @${composerStore.current.username}`
            : (composerStore.current.discussionTitle || '讨论'))))
})
const minimizedSummary = computed(() => {
  const content = replyContent.value.trim()
  if (content) {
    return content.length > 36 ? `${content.slice(0, 36)}...` : content
  }
  return getUiCopy({
    surface: 'post-composer-minimized-summary',
    isEditing: isEditing.value,
    postNumber: composerStore.current.postNumber || '',
    discussionTitle: composerStore.current.discussionTitle || '',
  })?.text || (isEditing.value
    ? `编辑 #${composerStore.current.postNumber || ''}`.trim()
    : (composerStore.current.postNumber
        ? `回复 #${composerStore.current.postNumber}`
        : (composerStore.current.discussionTitle || '回复讨论')))
})
const previewStatusText = computed(() => {
  return getUiCopy({
    surface: 'post-composer-preview-status',
    previewLoading: previewLoading.value,
    hasContent: Boolean(replyContent.value.trim()),
  })?.text || '按论坛最终渲染效果预览'
})
const contentPlaceholderText = computed(() => getUiCopy({
  surface: 'post-composer-content-placeholder',
})?.text || '输入你的回复... 支持 Markdown、@用户名 和代码块')
const previewButtonTitleText = computed(() => getUiCopy({
  surface: 'composer-preview-button-title',
})?.text || '预览')
const submitButtonText = computed(() => getUiCopy({
  surface: 'post-composer-submit',
  submitting: submitting.value,
  uploading: uploading.value,
  isEditing: isEditing.value,
})?.text || (submitting.value ? '提交中...' : (uploading.value ? '上传中...' : (isEditing.value ? '更新回复' : '发布回复'))))
const unsavedExitMessage = computed(() => {
  return getUiCopy({
    surface: 'post-composer-unsaved-exit-message',
    isEditing: isEditing.value,
  })?.text || (isEditing.value
    ? '你有未保存的帖子编辑内容。确定要离开当前页面吗？'
    : '你有未发布的回复内容。确定要离开当前页面吗？')
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
const composerNotices = computed(() => {
  return [
    {
      key: 'draft',
      label: getUiCopy({
        surface: 'composer-notice-draft-label',
      })?.text || '草稿',
      tone: draftNoticeTone.value,
      message: draftNotice.value,
    },
    {
      key: 'upload',
      label: getUiCopy({
        surface: 'composer-notice-upload-label',
      })?.text || '上传',
      tone: uploadNoticeTone.value,
      message: uploadNotice.value,
    },
    {
      key: 'preview',
      label: getUiCopy({
        surface: 'composer-notice-preview-label',
      })?.text || '预览',
      tone: 'error',
      message: previewError.value,
    },
    {
      key: 'submit',
      label: getUiCopy({
        surface: 'composer-notice-submit-label',
        isEditing: isEditing.value,
        type: 'post',
      })?.text || (isEditing.value ? '保存' : '发布'),
      tone: submitNoticeTone.value,
      message: submitNotice.value,
    },
    ...composerExtensionNotices.value,
  ].filter(item => item?.message)
})

watch(
  () => composerStore.current.requestId,
  async () => {
    if (!showComposer.value) return

    clearRuntimeState()
    submitNotice.value = ''
    submitNoticeTone.value = 'info'

    if (isEditing.value) {
      composerDraftSavedAt.value = ''
      draftNotice.value = ''
      draftNoticeTone.value = 'info'
      replyContent.value = composerStore.current.initialContent || ''
    } else if (composerStore.current.initialContent?.trim()) {
      composerDraftSavedAt.value = ''
      draftNotice.value = ''
      draftNoticeTone.value = 'info'
      replyContent.value = composerStore.current.initialContent
    } else {
      restoreComposerDraft()
    }

    await nextTick()
    if (!composerStore.isMinimized) {
      focusEditor()
    }
  }
)

watch(
  () => authStore.isAuthenticated,
  value => {
    if (!value) {
      stopTypingIndicator()
      resetComposerState()
    }
  }
)

watch(
  [dirtyState, unsavedExitMessage],
  ([value, message]) => {
    composerStore.setUnsavedState(value, message)
  },
  { immediate: true }
)

function handleHeaderLinkClick(event) {
  if (composerStore.isMinimized) {
    event.preventDefault()
    composerStore.showComposer()
    nextTick(() => focusEditor())
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
  nextTick(() => focusEditor())
  syncInlineSuggestions()
}

function toggleComposerMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    nextTick(() => focusEditor())
    syncInlineSuggestions()
  }
}

function toggleComposerExpanded() {
  composerStore.toggleExpanded()
  nextTick(() => focusEditor())
}

function focusEditor() {
  showPreview.value = false
  composerTextarea.value?.focus()
}

const runtimeHandleEditorInteraction = handleEditorInteraction

function handleEditorActivity(event) {
  runtimeHandleEditorInteraction(event)
  handleTypingActivity()
}

async function closeComposer(force = false) {
  if (!force && dirtyState.value) {
    const confirmed = await modalStore.confirm({
      title: getUiCopy({
        surface: 'post-composer-close-title',
        isEditing: isEditing.value,
      })?.text || (isEditing.value ? '关闭编辑器' : '关闭回复框'),
      message: getUiCopy({
        surface: 'post-composer-close-message',
        isEditing: isEditing.value,
      })?.text || (isEditing.value
        ? '确定要关闭编辑器吗？未保存修改将丢失。'
        : '确定要关闭回复框吗？当前内容会保留在本地草稿中。'),
      confirmText: getUiCopy({
        surface: 'post-composer-close-confirm',
      })?.text || '关闭',
      cancelText: getUiCopy({
        surface: 'post-composer-close-cancel',
      })?.text || '继续编辑',
    })
    if (!confirmed) return
  }

  if (!isEditing.value) {
    saveComposerDraft(false)
  }
  resetComposerState()
}

function cancelEdit() {
  closeComposer(true)
}

function resetComposerState() {
  stopTypingIndicator()
  composerStore.closeComposer()
  composerDraftSavedAt.value = ''
  draftNotice.value = ''
  draftNoticeTone.value = 'info'
  submitNotice.value = ''
  submitNoticeTone.value = 'info'
  clearRuntimeState()
  replyContent.value = ''
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
    draftNotice.value = getUiCopy({
      surface: 'post-composer-draft-restored',
      hasDraftSavedAt: Boolean(composerDraftSavedAt.value),
      draftSavedAtText: composerDraftSavedAt.value ? formatDraftTime(composerDraftSavedAt.value) : '',
    })?.text || (composerDraftSavedAt.value
      ? `已恢复你在 ${formatDraftTime(composerDraftSavedAt.value)} 保存的回复草稿。`
      : '已恢复本地回复草稿。')
    return true
  } catch (error) {
    console.error('恢复草稿失败:', error)
    replyContent.value = ''
    draftNoticeTone.value = 'error'
    draftNotice.value = getUiCopy({
      surface: 'post-composer-draft-restore-error',
    })?.text || '回复草稿恢复失败。'
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
      draftNotice.value = getUiCopy({
        surface: 'post-composer-draft-emptied',
      })?.text || '回复草稿已清空。'
    }
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    key,
    JSON.stringify({
      content: replyContent.value,
      updatedAt,
    })
  )
  composerDraftSavedAt.value = updatedAt
  if (showMessage) {
    draftNoticeTone.value = 'success'
    draftNotice.value = getUiCopy({
      surface: 'post-composer-draft-saved',
    })?.text || '回复草稿已保存。'
  }
}

function clearComposerDraft() {
  if (typeof window === 'undefined') return

  const key = getComposerDraftKey()
  if (!key) return

  window.localStorage.removeItem(key)
  composerDraftSavedAt.value = ''
  draftNoticeTone.value = 'success'
  draftNotice.value = getUiCopy({
    surface: 'post-composer-draft-cleared-local',
  })?.text || '已清除本地回复草稿。'
  replyContent.value = ''
  clearRuntimeState()
  nextTick(() => focusEditor())
}

async function submitReply() {
  if (!replyContent.value.trim() || !discussionId.value) return

  submitting.value = true
  stopTypingIndicator()
  submitNotice.value = ''
  submitNoticeTone.value = 'info'
  try {
    const blocked = await runComposerSubmitGuards({
      ...buildExtensionContext(),
      modalStore,
      submitKind: isEditing.value ? 'edit-post' : 'reply',
    })
    if (blocked) {
      submitNoticeTone.value = blocked.tone || 'error'
      submitNotice.value = blocked.message || (getUiCopy({
        surface: 'composer-submit-blocked',
      })?.text || '当前内容未通过校验。')
      return
    }

    if (isEditing.value) {
      const data = await api.patch(`/posts/${composerStore.current.postId}`, {
        content: replyContent.value,
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('bias:post-updated', {
        detail: {
          discussionId: discussionId.value,
          post,
        },
      }))

      await runComposerSubmitSuccess({
        ...buildExtensionContext(),
        data,
        post,
        mode: 'edit',
        submitKind: 'edit-post',
        type: 'post',
      })

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || composerStore.current.postNumber || 1}`)
      }
    } else {
      const data = await api.post(`/discussions/${discussionId.value}/posts`, {
        content: replyContent.value,
        reply_to_post_id: composerStore.current.postId || null,
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('bias:reply-created', {
        detail: {
          discussionId: discussionId.value,
          post,
        },
      }))

      await runComposerSubmitSuccess({
        ...buildExtensionContext(),
        data,
        post,
        mode: 'reply',
        submitKind: 'reply',
        type: 'post',
      })

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || 1}`)
      }

      clearComposerDraft()
    }

    resetComposerState()
  } catch (error) {
    console.error('提交失败:', error)
    submitNoticeTone.value = 'error'
    submitNotice.value = error.response?.data?.error || error.message || (getUiCopy({
      surface: 'composer-submit-failed',
    })?.text || '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

function isViewingCurrentDiscussion() {
  return route.name === 'discussion-detail' && Number(route.params.id) === discussionId.value
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return getUiCopy({
    surface: 'composer-draft-time-fallback',
  })?.text || '刚刚'

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatAbsoluteDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return getUiCopy({
    surface: 'composer-date-fallback',
  })?.text || '未知时间'
  return date.toLocaleString('zh-CN')
}

function buildBaseContext() {
  return {
    authStore,
    canSubmit: Boolean(replyContent.value.trim()) && !submitting.value && !uploading.value && !isSuspended.value,
    draftSavedAt: composerDraftSavedAt.value,
    discussionId: discussionId.value,
    discussionTitle: composerStore.current.discussionTitle || '',
    formatDraftTime,
    hasDraftContent: Boolean(replyContent.value.trim()),
    isEditing: isEditing.value,
    mode: isEditing.value ? 'edit' : 'reply',
    modalStore,
    extensionState: composerStore.current.extensions || {},
    postNumber: composerStore.current.postNumber ?? null,
    route,
    router,
    secondaryActionHandlers: {
      'cancel-edit': () => cancelEdit(),
      'clear-draft': () => clearComposerDraft(),
    },
    source: composerStore.current.source || '',
    suspensionNotice: suspensionNotice.value,
    type: 'post',
    username: composerStore.current.username || '',
  }
}

function handleTypingActivity() {
  if (!canSendTypingIndicator.value || !discussionId.value || submitting.value || !replyContent.value.trim()) return

  if (!typingActive) {
    typingActive = forumRealtimeStore.sendTypingIndicator({
      discussionId: discussionId.value,
      isTyping: true,
    })
  }

  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer)
  }

  typingIdleTimer = setTimeout(() => {
    stopTypingIndicator()
  }, 2500)
}

function stopTypingIndicator() {
  if (typingIdleTimer) {
    clearTimeout(typingIdleTimer)
    typingIdleTimer = null
  }

  if (!typingActive || !discussionId.value) {
    typingActive = false
    return
  }

  forumRealtimeStore.sendTypingIndicator({
    discussionId: discussionId.value,
    isTyping: false,
  })
  typingActive = false
}

watch(showComposer, value => {
  if (!value) {
    stopTypingIndicator()
  }
})

watch(() => composerStore.isMinimized, value => {
  if (value) {
    stopTypingIndicator()
  }
})

watch(replyContent, value => {
  if (!value.trim()) {
    stopTypingIndicator()
  }
})

onBeforeUnmount(() => {
  stopTypingIndicator()
})
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
