import { defineStore } from 'pinia'
import { ref } from 'vue'

const EMPTY_STATE = {
  type: null,
  tagId: '',
  source: '',
  discussionId: null,
  discussionTitle: '',
  approvalStatus: '',
  approvalNote: '',
  initialTitle: '',
  postId: null,
  postNumber: null,
  username: '',
  initialContent: '',
  initialPrimaryTagId: '',
  initialSecondaryTagId: '',
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
    current.value = {
      ...EMPTY_STATE,
      ...nextState,
      requestId: current.value.requestId + 1
    }
    isOpen.value = true
    isMinimized.value = false
    isExpanded.value = Boolean(options.expanded)
  }

  function openDiscussionComposer(options = {}) {
    openComposerState({
      type: 'discussion',
      tagId: options.tagId ? String(options.tagId) : '',
      source: options.source || ''
    }, options)
  }

  function openEditDiscussionComposer(options = {}) {
    openComposerState({
      type: 'edit-discussion',
      source: options.source || '',
      discussionId: options.discussionId ?? null,
      discussionTitle: options.discussionTitle || '',
      approvalStatus: options.approvalStatus || '',
      approvalNote: options.approvalNote || '',
      initialTitle: options.initialTitle || '',
      initialContent: options.initialContent || '',
      initialPrimaryTagId: options.initialPrimaryTagId ? String(options.initialPrimaryTagId) : '',
      initialSecondaryTagId: options.initialSecondaryTagId ? String(options.initialSecondaryTagId) : ''
    }, options)
  }

  function openReplyComposer(options = {}) {
    openComposerState({
      type: 'reply',
      source: options.source || '',
      discussionId: options.discussionId ?? null,
      discussionTitle: options.discussionTitle || '',
      postId: options.postId ?? null,
      postNumber: options.postNumber ?? null,
      username: options.username || '',
      approvalStatus: options.approvalStatus || '',
      approvalNote: options.approvalNote || '',
      initialContent: options.initialContent || ''
    }, options)
  }

  function openEditPostComposer(options = {}) {
    openComposerState({
      type: 'edit',
      source: options.source || '',
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
