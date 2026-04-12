import { defineStore } from 'pinia'
import { ref } from 'vue'

const EMPTY_STATE = {
  type: null,
  tagId: '',
  source: '',
  discussionId: null,
  discussionTitle: '',
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

  function openReplyComposer(options = {}) {
    openComposerState({
      type: 'reply',
      source: options.source || '',
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

  return {
    isOpen,
    isMinimized,
    isExpanded,
    current,
    openDiscussionComposer,
    openReplyComposer,
    openEditPostComposer,
    showComposer,
    closeComposer,
    toggleMinimized,
    toggleExpanded
  }
})
