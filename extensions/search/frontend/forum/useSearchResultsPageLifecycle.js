import { onBeforeUnmount, onMounted, watch } from '@bias/core'

export function createSearchResultsPageLifecycle({
  abortActiveRequest,
  addForumEventListener,
  cleanupTrackedDiscussionIds,
  forumEventHandler,
  removeForumEventListener,
  syncTrackedDiscussionIds,
}) {
  function handleTrackedDiscussionIdsChange(nextTrackedIds, previousTrackedIds = []) {
    syncTrackedDiscussionIds(nextTrackedIds, previousTrackedIds)
  }

  function handleMounted() {
    addForumEventListener(forumEventHandler)
  }

  function handleBeforeUnmount() {
    abortActiveRequest()
    cleanupTrackedDiscussionIds()
    removeForumEventListener(forumEventHandler)
  }

  return {
    handleBeforeUnmount,
    handleMounted,
    handleTrackedDiscussionIdsChange,
  }
}

export function useSearchResultsPageLifecycle({
  abortActiveRequest,
  addForumEventListener,
  cleanupTrackedDiscussionIds,
  forumEventHandler,
  removeForumEventListener,
  syncTrackedDiscussionIds,
  trackedDiscussionIds,
}) {
  const lifecycle = createSearchResultsPageLifecycle({
    abortActiveRequest,
    addForumEventListener,
    cleanupTrackedDiscussionIds,
    forumEventHandler,
    removeForumEventListener,
    syncTrackedDiscussionIds,
  })

  watch(
    () => trackedDiscussionIds.value,
    lifecycle.handleTrackedDiscussionIdsChange
  )

  onMounted(lifecycle.handleMounted)
  onBeforeUnmount(lifecycle.handleBeforeUnmount)

  return lifecycle
}
