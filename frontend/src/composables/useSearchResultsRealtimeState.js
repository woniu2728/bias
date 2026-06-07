import {
  hasTrackedDiscussionId as resolveTrackedDiscussionId,
  shouldRefreshForumEvent,
} from '../utils/forumRealtime.js'

export function createSearchResultsRealtimeState({
  hasTrackedDiscussionId = resolveTrackedDiscussionId,
  loadResults,
  mergePayload,
  shouldRefreshEvent = shouldRefreshForumEvent,
  trackedDiscussionIds,
}) {
  async function handleForumEvent(event) {
    const detail = event.detail || {}
    const discussionId = Number(detail.discussion_id)
    if (!hasTrackedDiscussionId(trackedDiscussionIds(), discussionId)) {
      return
    }

    if (shouldRefreshEvent(detail.event_type)) {
      await loadResults()
      return
    }

    mergePayload(detail.payload || {})
  }

  return {
    handleForumEvent,
  }
}

export function useSearchResultsRealtimeState({
  loadResults,
  resourceStore,
  trackedDiscussionIds,
}) {
  return createSearchResultsRealtimeState({
    hasTrackedDiscussionId: resolveTrackedDiscussionId,
    loadResults,
    mergePayload(payload) {
      resourceStore.mergePayload(payload)
    },
    shouldRefreshEvent: shouldRefreshForumEvent,
    trackedDiscussionIds: () => trackedDiscussionIds.value,
  })
}
