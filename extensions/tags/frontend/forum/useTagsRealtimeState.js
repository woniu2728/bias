import {
  FORUM_REALTIME_REFRESH_EVENT_TYPES,
  hasTrackedDiscussionId as resolveTrackedDiscussionId,
} from '@bias/forum'

export function createTagsRealtimeState({
  hasTrackedDiscussionId = resolveTrackedDiscussionId,
  loadTags,
  mergePayload,
  trackedDiscussionIds,
}) {
  async function handleForumEvent(event) {
    const detail = event.detail || {}
    const discussionId = Number(detail.discussion_id)
    if (!hasTrackedDiscussionId(trackedDiscussionIds(), discussionId)) {
      return
    }

    if (FORUM_REALTIME_REFRESH_EVENT_TYPES.has(String(detail.event_type || ''))) {
      await loadTags()
      return
    }

    mergePayload(detail.payload || {})
  }

  return {
    handleForumEvent,
  }
}

export function useTagsRealtimeState({
  loadTags,
  resourceStore,
  trackedDiscussionIds,
}) {
  return createTagsRealtimeState({
    hasTrackedDiscussionId: resolveTrackedDiscussionId,
    loadTags,
    mergePayload(payload) {
      resourceStore.mergePayload(payload)
    },
    trackedDiscussionIds() {
      return trackedDiscussionIds.value
    },
  })
}
