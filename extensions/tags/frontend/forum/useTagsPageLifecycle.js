import { onBeforeUnmount, onMounted, watch } from '@bias/forum'

export function createTagsPageLifecycle({
  addForumEventListener,
  cleanupTrackedDiscussionIds,
  forumEventHandler,
  loadInitialTags,
  removeForumEventListener,
  syncTrackedDiscussionIds,
}) {
  function handleTrackedDiscussionIdsChange(nextTrackedIds, previousTrackedIds = []) {
    syncTrackedDiscussionIds(nextTrackedIds, previousTrackedIds)
  }

  async function handleMounted() {
    await loadInitialTags()
    addForumEventListener(forumEventHandler)
  }

  function handleBeforeUnmount() {
    cleanupTrackedDiscussionIds()
    removeForumEventListener(forumEventHandler)
  }

  return {
    handleBeforeUnmount,
    handleMounted,
    handleTrackedDiscussionIdsChange,
  }
}

export function useTagsPageLifecycle({
  addForumEventListener,
  cleanupTrackedDiscussionIds,
  forumEventHandler,
  loadInitialTags,
  removeForumEventListener,
  syncTrackedDiscussionIds,
  trackedDiscussionIds,
}) {
  const lifecycle = createTagsPageLifecycle({
    addForumEventListener,
    cleanupTrackedDiscussionIds,
    forumEventHandler,
    loadInitialTags,
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
