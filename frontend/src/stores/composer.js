import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useComposerStore = defineStore('composer', () => {
  const isOpen = ref(false)
  const isMinimized = ref(false)
  const isExpanded = ref(false)
  const current = ref({
    type: null,
    tagId: '',
    source: '',
    requestId: 0
  })

  function openDiscussionComposer(options = {}) {
    current.value = {
      type: 'discussion',
      tagId: options.tagId ? String(options.tagId) : '',
      source: options.source || '',
      requestId: current.value.requestId + 1
    }
    isOpen.value = true
    isMinimized.value = false
    isExpanded.value = Boolean(options.expanded)
  }

  function closeComposer() {
    isOpen.value = false
    isMinimized.value = false
    isExpanded.value = false
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
    closeComposer,
    toggleMinimized,
    toggleExpanded
  }
})
