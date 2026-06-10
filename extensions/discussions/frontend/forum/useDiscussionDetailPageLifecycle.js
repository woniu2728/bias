import { onBeforeUnmount, onMounted, watch } from '@bias/core'

export function createDiscussionDetailPageLifecycle({
  attachGlobalListeners,
  detachGlobalListeners,
  loading,
  refreshDiscussion,
  resetMobileHeader,
  resetPostStream,
  resetScrubberPreview,
  resetTransientUiState,
  syncNearPostWindow,
  syncMobileHeader,
  updateVisiblePostFromScroll,
}) {
  async function handleDiscussionScopeChange() {
    resetMobileHeader()
    resetPostStream()
    resetTransientUiState()
    resetScrubberPreview()
    loading.value = true
    await refreshDiscussion()
  }

  async function handleNearRouteChange() {
    await syncNearPostWindow()
  }

  function handleHeaderSync() {
    syncMobileHeader()
  }

  async function handleMounted() {
    await refreshDiscussion()
    attachGlobalListeners()
    updateVisiblePostFromScroll()
    syncMobileHeader()
  }

  function handleBeforeUnmount() {
    detachGlobalListeners()
  }

  return {
    handleBeforeUnmount,
    handleDiscussionScopeChange,
    handleHeaderSync,
    handleMounted,
    handleNearRouteChange,
  }
}

export function useDiscussionDetailPageLifecycle({
  attachGlobalListeners,
  currentVisiblePostProgress,
  detachGlobalListeners,
  discussionTitle,
  hasMobileDiscussionMenuActions,
  loading,
  maxPostNumber,
  refreshDiscussion,
  resetMobileHeader,
  resetPostStream,
  resetScrubberPreview,
  resetTransientUiState,
  route,
  syncNearPostWindow,
  syncMobileHeader,
  updateVisiblePostFromScroll,
}) {
  const lifecycle = createDiscussionDetailPageLifecycle({
    attachGlobalListeners,
    detachGlobalListeners,
    loading,
    refreshDiscussion,
    resetMobileHeader,
    resetPostStream,
    resetScrubberPreview,
    resetTransientUiState,
    syncNearPostWindow,
    syncMobileHeader,
    updateVisiblePostFromScroll,
  })

  watch(
    () => route.params.id,
    lifecycle.handleDiscussionScopeChange
  )

  watch(
    () => route.query.near,
    lifecycle.handleNearRouteChange
  )

  watch(
    () => [
      currentVisiblePostProgress.value,
      maxPostNumber.value,
      discussionTitle.value,
      hasMobileDiscussionMenuActions.value,
    ],
    lifecycle.handleHeaderSync
  )

  onMounted(lifecycle.handleMounted)
  onBeforeUnmount(lifecycle.handleBeforeUnmount)

  return lifecycle
}
