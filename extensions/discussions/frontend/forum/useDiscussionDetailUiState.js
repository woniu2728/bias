import { computed, nextTick, ref } from '@bias/core'

export function useDiscussionDetailUiState({
  authStore,
  composerStore,
  currentVisiblePostProgress,
  discussion,
  isSuspended,
  maxPostNumber,
}) {
  const discussionSidebarRef = ref(null)
  const discussionMobileNavRef = ref(null)
  const showDiscussionMenu = ref(false)
  const activePostMenuId = ref(null)

  const hasActiveComposer = computed(() => {
    if (!discussion.value) return false
    if (!['reply', 'edit'].includes(composerStore.current.type)) return false

    return Number(composerStore.current.discussionId) === Number(discussion.value.id)
  })

  const hasMobileDiscussionMenuActions = computed(() => Boolean(
    !discussion.value
      ? false
      : (!authStore.isAuthenticated)
          || Boolean(
            authStore.isAuthenticated
            && discussion.value?.can_reply
            && !discussion.value?.is_locked
            && !isSuspended.value
          )
          || (authStore.isAuthenticated && !isSuspended.value)
          || Boolean(
            authStore.isAuthenticated
            && discussion.value?.can_edit
            && !isSuspended.value
          )
          || Boolean(authStore.user?.is_staff)
  ))

  function handleDocumentMouseDown(event) {
    if (showDiscussionMenu.value && !(event.target instanceof Element && event.target.closest('.discussion-actions-scope'))) {
      showDiscussionMenu.value = false
    }

    if (activePostMenuId.value && !(event.target instanceof Element && event.target.closest('.post-controls'))) {
      activePostMenuId.value = null
    }
  }

  function handleMobileHeaderAction(event) {
    if (event.detail?.action !== 'discussion-menu') return

    showDiscussionMenu.value = !showDiscussionMenu.value

    if (!showDiscussionMenu.value) return

    nextTick(() => {
      getDiscussionMobileNavEl()?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  function syncMobileHeader() {
    if (typeof window === 'undefined' || !discussion.value) return

    window.dispatchEvent(new CustomEvent('bias:mobile-header-update', {
      detail: {
        route: 'discussion-detail',
        title: `${sanitizePostNumber(currentVisiblePostProgress.value)} / ${maxPostNumber.value}`,
        leftAction: 'back',
        rightAction: hasMobileDiscussionMenuActions.value ? 'discussion-menu' : 'none'
      }
    }))
  }

  function resetMobileHeader() {
    if (typeof window === 'undefined') return

    window.dispatchEvent(new CustomEvent('bias:mobile-header-reset', {
      detail: {
        route: 'discussion-detail'
      }
    }))
  }

  function attachGlobalListeners() {
    if (typeof window !== 'undefined') {
      window.addEventListener('bias:mobile-header-action', handleMobileHeaderAction)
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('mousedown', handleDocumentMouseDown)
    }
  }

  function detachGlobalListeners() {
    if (typeof window !== 'undefined') {
      window.removeEventListener('bias:mobile-header-action', handleMobileHeaderAction)
    }
    if (typeof document !== 'undefined') {
      document.removeEventListener('mousedown', handleDocumentMouseDown)
    }
    resetMobileHeader()
  }

  function resetTransientUiState() {
    showDiscussionMenu.value = false
    activePostMenuId.value = null
  }

  function toggleDiscussionMenu() {
    showDiscussionMenu.value = !showDiscussionMenu.value
  }

  function togglePostMenu(postId) {
    activePostMenuId.value = activePostMenuId.value === postId ? null : postId
  }

  function closePostMenu() {
    activePostMenuId.value = null
  }

  function sanitizePostNumber(value) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) return 1
    return Math.floor(Math.min(maxPostNumber.value, Math.max(1, parsed)))
  }

  function getDiscussionMobileNavEl() {
    return discussionMobileNavRef.value?.getRootEl?.() || null
  }

  return {
    activePostMenuId,
    attachGlobalListeners,
    closePostMenu,
    detachGlobalListeners,
    discussionMobileNavRef,
    discussionSidebarRef,
    hasActiveComposer,
    hasMobileDiscussionMenuActions,
    resetMobileHeader,
    resetTransientUiState,
    showDiscussionMenu,
    syncMobileHeader,
    toggleDiscussionMenu,
    togglePostMenu,
  }
}
