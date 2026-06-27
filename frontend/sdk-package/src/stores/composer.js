import { defineStore } from 'pinia'
import { ref } from 'vue'

const EMPTY_STATE = {
  type: null,
  source: '',
  extensions: {},
  discussionId: null,
  discussionTitle: '',
  initialTitle: '',
  postId: null,
  postNumber: null,
  username: '',
  initialContent: '',
  requestId: 0
}

export const useComposerStore = defineStore('composer', () => {
  const isOpen = ref(false)
  const isMinimized = ref(false)
  const isExpanded = ref(false)
  const current = ref({ ...EMPTY_STATE })
  const hasUnsavedChanges = ref(false)
  const unsavedMessage = ref('')

  function openComposerState(nextState = {}, options = {}) {
    const extensions = normalizeExtensions(nextState.extensions || nextState.extensionState)
    current.value = {
      ...EMPTY_STATE,
      ...nextState,
      extensions,
      requestId: current.value.requestId + 1
    }
    isOpen.value = true
    isMinimized.value = false
    isExpanded.value = Boolean(options.expanded)
  }

  function openDiscussionComposer(options = {}) {
    openComposerState({
      type: 'discussion',
      extensions: options.extensions || options.extensionState || {},
      source: options.source || ''
    }, options)
  }

  function openEditDiscussionComposer(options = {}) {
    openComposerState({
      type: 'edit-discussion',
      source: options.source || '',
      extensions: options.extensions || options.extensionState || {},
      discussionId: options.discussionId ?? null,
      discussionTitle: options.discussionTitle || '',
      initialTitle: options.initialTitle || '',
      initialContent: options.initialContent || ''
    }, options)
  }

  function openReplyComposer(options = {}) {
    openComposerState({
      type: 'reply',
      source: options.source || '',
      extensions: options.extensions || options.extensionState || {},
      discussionId: options.discussionId ?? null,
      discussionTitle: options.discussionTitle || '',
      postId: options.postId ?? null,
      postNumber: options.postNumber ?? null,
      username: options.username || '',
      initialContent: options.initialContent || ''
    }, options)
  }

  function openEditPostComposer(options = {}) {
    openComposerState({
      type: 'edit',
      source: options.source || '',
      extensions: options.extensions || options.extensionState || {},
      discussionId: options.discussionId ?? null,
      discussionTitle: options.discussionTitle || '',
      postId: options.postId ?? null,
      postNumber: options.postNumber ?? null,
      username: options.username || '',
      initialContent: options.initialContent || ''
    }, options)
  }

  function closeComposer() {
    isOpen.value = false
    isMinimized.value = false
    isExpanded.value = false
    hasUnsavedChanges.value = false
    unsavedMessage.value = ''
    current.value = {
      ...EMPTY_STATE,
      extensions: {},
      requestId: current.value.requestId
    }
  }

  function showComposer() {
    if (!current.value.type) return
    isOpen.value = true
    isMinimized.value = false
  }

  function toggleMinimized() {
    isMinimized.value = !isMinimized.value
    if (isMinimized.value) {
      isExpanded.value = false
    }
  }

  function toggleExpanded() {
    isExpanded.value = !isExpanded.value
    if (isExpanded.value) {
      isMinimized.value = false
    }
  }

  function setUnsavedState(value, message = '') {
    hasUnsavedChanges.value = Boolean(value)
    unsavedMessage.value = value ? message : ''
  }

  return {
    isOpen,
    isMinimized,
    isExpanded,
    current,
    hasUnsavedChanges,
    unsavedMessage,
    openDiscussionComposer,
    openEditDiscussionComposer,
    openReplyComposer,
    openEditPostComposer,
    showComposer,
    closeComposer,
    toggleMinimized,
    toggleExpanded,
    setUnsavedState
  }
})

function normalizeExtensions(value) {
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
