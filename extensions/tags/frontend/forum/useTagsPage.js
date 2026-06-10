import { useResourceStore } from '@bias/core'

import { useForumRealtimeStore } from '@bias/realtime'
import { useTagsLoadState } from './useTagsLoadState.js'
import { useTagsPageLifecycle } from './useTagsPageLifecycle.js'
import { useTagsRealtimeState } from './useTagsRealtimeState.js'
import { useTagsResourceState } from './useTagsResourceState.js'

export function useTagsPage() {
  const forumRealtimeStore = useForumRealtimeStore()
  const resourceStore = useResourceStore()
  const resourceState = useTagsResourceState({
    resourceStore,
  })
  const loadState = useTagsLoadState({
    resourceState,
  })
  const realtimeState = useTagsRealtimeState({
    loadTags: loadState.loadTags,
    resourceStore,
    trackedDiscussionIds: resourceState.trackedDiscussionIds,
  })

  function addForumEventListener(handler) {
    if (typeof window === 'undefined') return
    window.addEventListener('bias:forum-event', handler)
  }

  function removeForumEventListener(handler) {
    if (typeof window === 'undefined') return
    window.removeEventListener('bias:forum-event', handler)
  }

  function cleanupTrackedDiscussionIds() {
    forumRealtimeStore.untrackDiscussionIds(resourceState.trackedDiscussionIds.value)
  }

  function syncTrackedDiscussionIds(nextTrackedIds, previousTrackedIds = []) {
    forumRealtimeStore.untrackDiscussionIds(previousTrackedIds)
    forumRealtimeStore.trackDiscussionIds(nextTrackedIds)
  }

  useTagsPageLifecycle({
    addForumEventListener,
    cleanupTrackedDiscussionIds,
    forumEventHandler: realtimeState.handleForumEvent,
    loadInitialTags: loadState.loadInitialTags,
    removeForumEventListener,
    syncTrackedDiscussionIds,
    trackedDiscussionIds: resourceState.trackedDiscussionIds,
  })

  return {
    cloudTags: resourceState.cloudTags,
    loading: loadState.listState.loading,
    tags: resourceState.tags,
  }
}
