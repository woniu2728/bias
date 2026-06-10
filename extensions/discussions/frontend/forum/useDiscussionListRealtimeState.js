import {
  mergeForumEventPayload as defaultMergeForumEventPayload,
  shouldRefreshForumEvent as defaultShouldRefreshForumEvent,
} from '@bias/realtime'
import {
  resolveDiscussionMarkAllReadPatch,
  resolveDiscussionReadStatePatch,
} from './discussionListRealtime.js'
import { resolveDiscussionNewReplyPatch } from './discussionListRealtimeUi.js'

export function createDiscussionListRealtimeState({
  api,
  authStore,
  currentDiscussionIds,
  markingAllRead,
  modalStore,
  mergeEventPayload = defaultMergeForumEventPayload,
  refreshDiscussionList,
  resourceStore,
  shouldRefreshEvent = defaultShouldRefreshForumEvent,
  uiText,
}) {
  async function markAllAsRead() {
    if (!authStore.isAuthenticated || markingAllRead.value) return

    markingAllRead.value = true
    try {
      const response = await api.post('/discussions/read-all')
      currentDiscussionIds.value.forEach(id => {
        const discussion = resourceStore.get('discussions', id)
        const patch = resolveDiscussionMarkAllReadPatch(discussion, response.marked_all_as_read_at)
        if (!patch) return
        resourceStore.upsert('discussions', {
          ...patch,
          has_new_replies: false,
          new_reply_count: 0,
        })
      })
    } catch (error) {
      console.error('标记已读失败:', error)
      await modalStore.alert({
        title: uiText('discussion-list-action-failed-title', '操作失败', { actionType: 'mark-all-read' }),
        message: error.response?.data?.error
          || error.response?.data?.detail
          || error.message
          || uiText('discussion-list-action-retry-message', '请稍后重试'),
        tone: 'danger'
      })
    } finally {
      markingAllRead.value = false
    }
  }

  function handleDiscussionReadStateUpdated(event) {
    const detail = event.detail || {}
    const discussionId = Number(detail.discussionId)
    if (!discussionId) return

    const discussion = resourceStore.get('discussions', discussionId)
    const patch = resolveDiscussionReadStatePatch(discussion, detail)
    if (!patch) return

    resourceStore.upsert('discussions', {
      ...patch,
      has_new_replies: false,
      new_reply_count: 0,
    })
  }

  async function handleForumEvent(event) {
    const detail = event.detail || {}
    const discussionId = Number(detail.discussion_id)
    const visibleDiscussionIds = new Set(currentDiscussionIds.value.map(id => String(id)))
    if (!discussionId || !visibleDiscussionIds.has(String(discussionId))) {
      return
    }

    if (shouldRefreshEvent(detail.event_type)) {
      await refreshDiscussionList()
      return
    }

    const discussion = resourceStore.get('discussions', discussionId)
    const newReplyPatch = resolveDiscussionNewReplyPatch(discussion, detail)
    if (newReplyPatch) {
      resourceStore.upsert('discussions', newReplyPatch)
    }

    mergeEventPayload(resourceStore, detail)
  }

  return {
    handleDiscussionReadStateUpdated,
    handleForumEvent,
    markAllAsRead,
  }
}

export function useDiscussionListRealtimeState(options) {
  return createDiscussionListRealtimeState(options)
}
