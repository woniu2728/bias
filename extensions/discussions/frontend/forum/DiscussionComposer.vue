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
        :title="composerHeading"
        :subtitle="composerStatusText"
        :summary-clickable="composerStore.isMinimized"
        :show-save="true"
        :submitting="submitting"
        :minimized="composerStore.isMinimized"
        :expanded="composerStore.isExpanded"
        @title-click="handleHeaderSummaryClick"
        @save="saveDraft()"
        @toggle-minimized="toggleMinimized"
        @toggle-expanded="toggleExpanded"
        @close="closeComposer"
      />

      <div v-show="!composerStore.isMinimized" class="composer-body">
        <ComposerNoticeStack :notices="composerNotices" />
        <ComposerStatusBar :items="composerStatusItems" />

        <input
          ref="titleInput"
          v-model="form.title"
          type="text"
          class="composer-field composer-title-input"
          maxlength="200"
          :placeholder="titlePlaceholderText"
          :disabled="submitting || isSuspended"
          @keydown.enter.prevent="focusEditor"
          @keydown.esc.prevent="closeComposer"
        />

        <div class="composer-meta" :class="{ 'has-extension-fields': composerFields.length }">
          <component
            :is="field.component"
            v-for="field in composerFields"
            :key="field.key"
            v-bind="field.componentProps || {}"
          />
          <span class="composer-counter">{{ form.title.length }}/200</span>
        </div>
        <textarea
          v-show="!showPreview"
          ref="composerTextarea"
          v-model="form.content"
          class="composer-editor"
          rows="8"
          :placeholder="contentPlaceholderText"
          :disabled="submitting || isSuspended || uploading"
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
        <ComposerAutocompleteOutlet
          v-if="showAutocomplete"
          :active="activeAutocomplete"
          @highlight="handleAutocompleteHighlight"
          @select="handleAutocompleteSelect"
        />

        <ComposerActionBar
          :submit-disabled="!canSubmit"
          :submit-text="submitButtonText"
          :secondary-actions="composerSecondaryActions"
          @submit="submitDiscussion"
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
                  :disabled="submitting || isSuspended || uploading"
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
                :disabled="submitting || isSuspended || uploading"
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
import {
  useAuthStore } from '@bias/users'
import {
  api,
  watch,
  computed,
  nextTick,
  ref,
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
  getComposerFields,
  getUiCopy,
  runComposerPayloadContributors,
  runComposerSubmitGuards,
  runComposerSubmitSuccess,
  useComposerRuntime,
  useComposerStore
} from '@bias/forum'
import { normalizeDiscussion } from '@bias/discussions'

const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()

function createEmptyForm(extensions = {}) {
  return {
    title: '',
    content: '',
    extensions: normalizeExtensionState(extensions),
  }
}

const form = ref(createEmptyForm())
const editorContent = computed({
  get: () => form.value.content,
  set: value => {
    form.value.content = value
  },
})
const submitting = ref(false)
const titleInput = ref(null)
const draftSavedAt = ref('')
const draftMessage = ref('')
const draftNoticeTone = ref('info')
const submitNotice = ref('')
const submitNoticeTone = ref('info')
let draftTimer = null

const isEditingDiscussion = computed(() => composerStore.current.type === 'edit-discussion')
const showComposer = computed(() => {
  return (
    composerStore.isOpen
    && ['discussion', 'edit-discussion'].includes(composerStore.current.type)
    && authStore.isAuthenticated
  )
})
const hasDraftContent = computed(() => {
  return Boolean(
    form.value.title.trim()
    || form.value.content.trim()
    || hasExtensionState.value
  )
})
const hasExtensionState = computed(() => Object.values(form.value.extensions || {}).some(value => {
  if (!value || typeof value !== 'object') return Boolean(value)
  return Object.values(value).some(nested => {
    if (Array.isArray(nested)) return nested.length > 0
    return Boolean(nested)
  })
}))
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))

const runtime = useComposerRuntime({
  composerStore,
  showComposer,
  content: editorContent,
  submitting,
  submit: submitDiscussion,
  closeComposer,
  buildBaseContext,
  focusEditor,
  openComposer: () => composerStore.showComposer(),
  saveRequestType: 'discussion',
  onSaveRequest: saveDraft,
  height: {
    storageKey: 'bias:composer-height:discussion',
    defaultValue: 520,
    min: 360,
    maxDefault: 760,
    maxFloor: 420,
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

const canSubmit = computed(() => {
  return Boolean(
    authStore.isAuthenticated &&
    form.value.title.trim() &&
    form.value.content.trim() &&
    !submitting.value &&
    !uploading.value &&
    !isSuspended.value
  )
})
const composerFields = computed(() => getComposerFields(buildExtensionContext()))
const selectedExtensionLabel = computed(() => {
  return composerFields.value
    .map(item => item.statusText || item.label)
    .filter(Boolean)
    .join(' · ')
})
const composerStatusText = computed(() => {
  if (composerStore.isMinimized) return minimizedSummary.value
  if (draftMessage.value) return draftMessage.value
  return getUiCopy({
    surface: 'discussion-composer-status-text',
    hasDraftSavedAt: Boolean(draftSavedAt.value),
    draftSavedAtText: draftSavedAt.value ? formatDraftTime(draftSavedAt.value) : '',
    isEditingDiscussion: isEditingDiscussion.value,
    selectedExtensionLabel: selectedExtensionLabel.value,
  })?.text || (draftSavedAt.value
    ? `草稿保存于 ${formatDraftTime(draftSavedAt.value)}`
    : (isEditingDiscussion.value
        ? '修改后将保存讨论内容。'
        : (selectedExtensionLabel.value
            ? `将发布到 ${selectedExtensionLabel.value}`
            : '支持 Markdown，可最小化继续编辑。')))
})
const minimizedSummary = computed(() => {
  const title = form.value.title.trim()
  if (title) return title
  return getUiCopy({
    surface: 'discussion-composer-minimized-summary',
    isEditingDiscussion: isEditingDiscussion.value,
    selectedExtensionLabel: selectedExtensionLabel.value,
  })?.text || (isEditingDiscussion.value
    ? '编辑讨论'
    : (selectedExtensionLabel.value ? `新讨论 · ${selectedExtensionLabel.value}` : '发起讨论'))
})
const composerHeading = computed(() => getUiCopy({
  surface: 'discussion-composer-heading',
  isEditingDiscussion: isEditingDiscussion.value,
})?.text || (isEditingDiscussion.value ? '编辑讨论' : '发起讨论'))
const titlePlaceholderText = computed(() => getUiCopy({
  surface: 'discussion-composer-title-placeholder',
})?.text || '讨论标题')
const contentPlaceholderText = computed(() => getUiCopy({
  surface: 'discussion-composer-content-placeholder',
})?.text || '输入讨论内容... 支持 Markdown、@用户名 和代码块')
const previewButtonTitleText = computed(() => getUiCopy({
  surface: 'composer-preview-button-title',
})?.text || '预览')
const submitButtonText = computed(() => getUiCopy({
  surface: 'discussion-composer-submit',
  submitting: submitting.value,
  uploading: uploading.value,
  isEditingDiscussion: isEditingDiscussion.value,
})?.text || (submitting.value ? (isEditingDiscussion.value ? '保存中...' : '发布中...') : (uploading.value ? '上传中...' : (isEditingDiscussion.value ? '保存讨论' : '发布讨论'))))
const unsavedExitMessage = computed(() => getUiCopy({
  surface: 'discussion-composer-unsaved-exit-message',
})?.text || '你有未发布的讨论内容。确定要离开当前页面吗？')
const previewStatusText = computed(() => {
  return getUiCopy({
    surface: 'discussion-composer-preview-status',
    previewLoading: previewLoading.value,
    hasContent: Boolean(form.value.content.trim()),
  })?.text || '按论坛最终渲染效果预览'
})
const composerNotices = computed(() => {
  return [
    {
      key: 'draft',
      label: getUiCopy({
        surface: 'composer-notice-draft-label',
      })?.text || '草稿',
      tone: draftNoticeTone.value,
      message: draftMessage.value,
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
        isEditingDiscussion: isEditingDiscussion.value,
        type: 'discussion',
      })?.text || (isEditingDiscussion.value ? '保存' : '发布'),
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
  [hasDraftContent, unsavedExitMessage],
  ([value, message]) => {
    composerStore.setUnsavedState(value, message)
  },
  { immediate: true }
)

watch(
  () => authStore.isAuthenticated,
  value => {
    if (!value) {
      composerStore.closeComposer()
    }
  }
)

async function prepareComposer() {
  if (!authStore.isAuthenticated) {
    composerStore.closeComposer()
    await router.push({
      name: 'login',
      query: {
        redirect: router.currentRoute.value.fullPath,
      },
    })
    return
  }

  clearRuntimeState()
  submitNotice.value = ''
  submitNoticeTone.value = 'info'

  if (isEditingDiscussion.value) {
    form.value = {
      title: composerStore.current.initialTitle || '',
      content: composerStore.current.initialContent || '',
      extensions: normalizeExtensionState(composerStore.current.extensions),
    }
    draftSavedAt.value = ''
    draftMessage.value = ''
    draftNoticeTone.value = 'info'
  } else {
    const restored = restoreDraft()
    if (!restored) {
      form.value = createEmptyForm(composerStore.current.extensions)
      draftSavedAt.value = ''
      draftMessage.value = ''
      draftNoticeTone.value = 'info'
    }
  }

  await focusPreferredField()
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
  syncInlineSuggestions()
}

function toggleMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    focusPreferredField()
    syncInlineSuggestions()
  }
}

function toggleExpanded() {
  composerStore.toggleExpanded()
  focusPreferredField()
}

function handleHeaderSummaryClick() {
  if (!composerStore.isMinimized) return
  composerStore.showComposer()
  focusPreferredField()
  syncInlineSuggestions()
}

async function closeComposer() {
  if (hasDraftContent.value) {
    const confirmed = await modalStore.confirm({
      title: getUiCopy({
        surface: 'discussion-composer-close-title',
      })?.text || '关闭发帖编辑器',
      message: getUiCopy({
        surface: 'discussion-composer-close-message',
      })?.text || '确定要关闭发帖编辑器吗？当前内容会保留在本地草稿中。',
      confirmText: getUiCopy({
        surface: 'discussion-composer-close-confirm',
      })?.text || '关闭',
      cancelText: getUiCopy({
        surface: 'discussion-composer-close-cancel',
      })?.text || '继续编辑',
    })
    if (!confirmed) return
  }

  clearRuntimeState()
  submitNotice.value = ''
  saveDraft(false)
  composerStore.closeComposer()
}

function getDraftKey() {
  const userId = authStore.user?.id || 'guest'
  if (isEditingDiscussion.value && composerStore.current.discussionId) {
    return `bias:edit-discussion-draft:${userId}:${composerStore.current.discussionId}`
  }
  return `bias:create-discussion-draft:${userId}`
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
      extensions: draft.extensions && typeof draft.extensions === 'object' ? draft.extensions : {},
    }
    draftSavedAt.value = draft.updatedAt || ''
    draftNoticeTone.value = 'success'
    draftMessage.value = getUiCopy({
      surface: 'discussion-composer-draft-restored',
      hasDraftSavedAt: Boolean(draftSavedAt.value),
      draftSavedAtText: draftSavedAt.value ? formatDraftTime(draftSavedAt.value) : '',
    })?.text || (draftSavedAt.value
      ? `已恢复你在 ${formatDraftTime(draftSavedAt.value)} 保存的讨论草稿。`
      : '已恢复本地讨论草稿。')
    return true
  } catch (error) {
    console.error('恢复讨论草稿失败:', error)
    draftNoticeTone.value = 'error'
    draftMessage.value = getUiCopy({
      surface: 'discussion-composer-draft-restore-error',
    })?.text || '讨论草稿恢复失败，已保留当前编辑内容。'
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
    clearDraftStorage(showMessage
      ? (getUiCopy({
          surface: 'discussion-composer-draft-emptied',
        })?.text || '草稿已清空')
      : '')
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    getDraftKey(),
    JSON.stringify({
      title: form.value.title,
      content: form.value.content,
      extensions: form.value.extensions,
      updatedAt,
    })
  )
  draftSavedAt.value = updatedAt
  draftNoticeTone.value = 'success'
  draftMessage.value = showMessage
    ? (getUiCopy({
        surface: 'discussion-composer-draft-saved',
      })?.text || '讨论草稿已保存。')
    : ''
}

async function clearDraft(options = {}) {
  if (hasDraftContent.value && !options.skipConfirm) {
    const confirmed = await modalStore.confirm({
      title: getUiCopy({
        surface: 'discussion-composer-clear-draft-title',
      })?.text || '清除讨论草稿',
      message: getUiCopy({
        surface: 'discussion-composer-clear-draft-message',
      })?.text || '确定要清除当前讨论草稿吗？',
      confirmText: getUiCopy({
        surface: 'discussion-composer-clear-draft-confirm',
      })?.text || '清除',
      cancelText: getUiCopy({
        surface: 'discussion-composer-clear-draft-cancel',
      })?.text || '取消',
      tone: 'danger',
    })
    if (!confirmed) return
  }

  form.value = createEmptyForm()
  clearRuntimeState()
  clearDraftStorage(getUiCopy({
    surface: 'discussion-composer-draft-cleared-local',
  })?.text || '已清除本地草稿。')
  focusPreferredField()
}

function clearDraftStorage(message = '') {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(getDraftKey())
  }
  draftSavedAt.value = ''
  draftNoticeTone.value = message ? 'success' : 'info'
  draftMessage.value = message
}

function resetComposer() {
  clearDraftStorage()
  clearRuntimeState()
  form.value = createEmptyForm()
  submitNotice.value = ''
  submitNoticeTone.value = 'info'
  composerStore.closeComposer()
}

async function submitDiscussion() {
  if (!canSubmit.value) return

  submitting.value = true
  draftMessage.value = ''
  submitNotice.value = ''
  submitNoticeTone.value = 'info'

  try {
    const blocked = await runComposerSubmitGuards({
      ...buildExtensionContext(),
      modalStore,
      submitKind: isEditingDiscussion.value ? 'edit-discussion' : 'discussion',
    })
    if (blocked) {
      submitNoticeTone.value = blocked.tone || 'error'
      submitNotice.value = blocked.message || (getUiCopy({
        surface: 'composer-submit-blocked',
      })?.text || '当前内容未通过校验。')
      return
    }

    let data
    if (isEditingDiscussion.value) {
      data = await api.patch(
        `/discussions/${composerStore.current.discussionId}`,
        await buildDiscussionResourcePayload(),
      )

      window.dispatchEvent(new CustomEvent('bias:discussion-updated', {
        detail: {
          discussionId: data.id,
          discussion: normalizeDiscussion(data),
        },
      }))
    } else {
      data = await api.post('/discussions/', await buildDiscussionResourcePayload())
    }

    const submitSuccessHandled = await runComposerSubmitSuccess({
      ...buildExtensionContext(),
      data,
      mode: isEditingDiscussion.value ? 'edit' : 'create',
      submitKind: isEditingDiscussion.value ? 'edit-discussion' : 'discussion',
      type: 'discussion',
    })

    if (isEditingDiscussion.value && !submitSuccessHandled) {
      await modalStore.alert({
        title: getUiCopy({
          surface: 'discussion-composer-updated-title',
        })?.text || '讨论已更新',
        message: getUiCopy({
          surface: 'discussion-composer-updated-message',
        })?.text || '新的讨论内容已经保存。',
      })
    }

    resetComposer()
    await router.push(`/d/${data.id}`)
  } catch (error) {
    console.error(isEditingDiscussion.value ? '更新讨论失败:' : '创建讨论失败:', error)
    submitNoticeTone.value = 'error'
    submitNotice.value =
      error.response?.data?.title?.[0]
      || error.response?.data?.content?.[0]
      || error.response?.data?.error
      || error.response?.data?.detail
      || error.message
      || (getUiCopy({
          surface: 'composer-submit-failed',
        })?.text || '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

async function buildDiscussionResourcePayload() {
  const payload = {
    data: {
      type: 'discussion',
      attributes: {
        title: form.value.title,
        content: form.value.content,
      },
      relationships: {},
    },
  }
  return runComposerPayloadContributors(payload, {
    ...buildExtensionContext(),
    submitKind: isEditingDiscussion.value ? 'edit-discussion' : 'discussion',
  })
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return getUiCopy({
    surface: 'composer-draft-time-fallback',
  })?.text || '刚刚'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function buildBaseContext() {
  return {
    authStore,
    canSubmit: canSubmit.value,
    draftSavedAt: draftSavedAt.value,
    discussionId: Number(composerStore.current.discussionId || 0),
    discussionTitle: form.value.title.trim() || composerStore.current.discussionTitle || '',
    formatDraftTime,
    hasDraftContent: hasDraftContent.value,
    isEditing: isEditingDiscussion.value,
    mode: isEditingDiscussion.value ? 'edit' : 'create',
    modalStore,
    extensionState: form.value.extensions,
    updateExtensionState,
    route: null,
    router,
    secondaryActionHandlers: {
      'clear-draft': () => clearDraft({ skipConfirm: true }),
    },
    current: composerStore.current,
    isSuspended: isSuspended.value,
    closeComposer,
    source: composerStore.current.source || '',
    title: form.value.title,
    type: 'discussion',
  }
}

function updateExtensionState(key, value) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) return
  form.value.extensions = {
    ...(form.value.extensions || {}),
    [normalizedKey]: {
      ...(form.value.extensions?.[normalizedKey] || {}),
      ...(value && typeof value === 'object' ? value : {}),
    },
  }
}

function normalizeExtensionState(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => String(key || '').trim())
      .map(([key, state]) => [
        String(key).trim(),
        state && typeof state === 'object' && !Array.isArray(state) ? { ...state } : state,
      ])
  )
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

.composer-body {
  padding: 0 20px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
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

.composer-meta :deep(.composer-field) {
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

  .composer-meta :deep(.composer-field) {
    max-width: none;
  }

  .composer-counter {
    width: 100%;
    text-align: right;
  }

}
</style>
