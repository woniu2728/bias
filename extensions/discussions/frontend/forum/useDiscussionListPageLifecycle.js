import { nextTick, onBeforeUnmount, onMounted, watch } from '@bias/core'

export function createDiscussionListPageLifecycle({
  addDiscussionReadStateListener,
  addForumEventListener,
  cleanupTrackedDiscussionIds,
  clearPendingReturnRestore,
  getPendingReturnRestore,
  removeDiscussionReadStateListener,
  removeForumEventListener,
  syncTrackedDiscussionIds,
}) {
  function handleCurrentDiscussionIdsChange(nextDiscussionIds, previousDiscussionIds = []) {
    syncTrackedDiscussionIds(nextDiscussionIds, previousDiscussionIds)
  }

  async function handleMounted() {
    addDiscussionReadStateListener()
    addForumEventListener()
    await restoreListPosition()
  }

  function handleBeforeUnmount() {
    cleanupTrackedDiscussionIds()
    removeDiscussionReadStateListener()
    removeForumEventListener()
  }

  async function handleDiscussionsChange() {
    await restoreListPosition()
  }

  async function restoreListPosition() {
    const restoreId = getPendingReturnRestore?.()
    if (!restoreId) return

    await nextTick()

    if (typeof document === 'undefined') return

    const target = document.querySelector(`[data-discussion-id="${restoreId}"]`)
    if (!(target instanceof HTMLElement)) return

    clearPendingReturnRestore?.()
    target.scrollIntoView({
      behavior: 'auto',
      block: 'center',
    })
  }

  return {
    handleBeforeUnmount,
    handleCurrentDiscussionIdsChange,
    handleDiscussionsChange,
    handleMounted,
  }
}

export function useDiscussionListPageLifecycle({
  addDiscussionReadStateListener,
  addForumEventListener,
  clearPendingReturnRestore,
  cleanupTrackedDiscussionIds,
  currentDiscussionIds,
  discussions,
  getPendingReturnRestore,
  removeDiscussionReadStateListener,
  removeForumEventListener,
  syncTrackedDiscussionIds,
}) {
  const lifecycle = createDiscussionListPageLifecycle({
    addDiscussionReadStateListener,
    addForumEventListener,
    clearPendingReturnRestore,
    cleanupTrackedDiscussionIds,
    getPendingReturnRestore,
    removeDiscussionReadStateListener,
    removeForumEventListener,
    syncTrackedDiscussionIds,
  })

  watch(
    () => currentDiscussionIds.value,
    lifecycle.handleCurrentDiscussionIdsChange,
    { immediate: true }
  )

  watch(
    () => discussions.value,
    lifecycle.handleDiscussionsChange,
  )

  onMounted(lifecycle.handleMounted)
  onBeforeUnmount(lifecycle.handleBeforeUnmount)

  return lifecycle
}
