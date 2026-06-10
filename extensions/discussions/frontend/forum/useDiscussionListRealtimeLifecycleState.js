import { getDiscussionListTrackingDiff } from './discussionListRealtime.js'

export function createDiscussionListRealtimeLifecycleState({
  addWindowEventListener,
  forumEventHandler,
  forumRealtimeStore,
  getCurrentDiscussionIds,
  readStateHandler,
  removeWindowEventListener,
}) {
  function addDiscussionReadStateListener() {
    addWindowEventListener('bias:discussion-read-state-updated', readStateHandler)
  }

  function removeDiscussionReadStateListener() {
    removeWindowEventListener('bias:discussion-read-state-updated', readStateHandler)
  }

  function addForumEventListener() {
    addWindowEventListener('bias:forum-event', forumEventHandler)
  }

  function removeForumEventListener() {
    removeWindowEventListener('bias:forum-event', forumEventHandler)
  }

  function cleanupTrackedDiscussionIds() {
    forumRealtimeStore.untrackDiscussionIds(getCurrentDiscussionIds())
  }

  function handleMounted() {
    addDiscussionReadStateListener()
    addForumEventListener()
  }

  function handleBeforeUnmount() {
    cleanupTrackedDiscussionIds()
    removeDiscussionReadStateListener()
    removeForumEventListener()
  }

  function syncTrackedDiscussionIds(nextDiscussionIds, previousDiscussionIds = []) {
    const { trackIds, untrackIds } = getDiscussionListTrackingDiff(nextDiscussionIds, previousDiscussionIds)
    if (untrackIds.length) {
      forumRealtimeStore.untrackDiscussionIds(untrackIds)
    }
    if (trackIds.length) {
      forumRealtimeStore.trackDiscussionIds(trackIds)
    }
  }

  return {
    addDiscussionReadStateListener,
    addForumEventListener,
    cleanupTrackedDiscussionIds,
    handleBeforeUnmount,
    handleMounted,
    removeDiscussionReadStateListener,
    removeForumEventListener,
    syncTrackedDiscussionIds,
  }
}

export function useDiscussionListRealtimeLifecycleState({
  forumEventHandler,
  forumRealtimeStore,
  readStateHandler,
  discussionIds,
}) {
  return createDiscussionListRealtimeLifecycleState({
    addWindowEventListener(type, handler) {
      if (typeof window === 'undefined') return
      window.addEventListener(type, handler)
    },
    forumEventHandler,
    forumRealtimeStore,
    getCurrentDiscussionIds() {
      return discussionIds.value
    },
    readStateHandler,
    removeWindowEventListener(type, handler) {
      if (typeof window === 'undefined') return
      window.removeEventListener(type, handler)
    },
  })
}
