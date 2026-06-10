import {
  mergeForumEventPayload,
  shouldRefreshForumEvent,
} from '@bias/realtime'

export function createProfileRealtimeState({
  getActiveTab,
  getCurrentUserId,
  getDiscussionIds,
  getPosts,
  getRequestedPostUserId,
  loadDiscussions,
  loadPosts,
  mergePostIds,
  resourceStore,
}) {
  async function handleForumEvent(event) {
    const detail = event.detail || {}
    const discussionId = Number(detail.discussion_id)
    const visibleDiscussionIds = new Set(getDiscussionIds().map(id => String(id)))

    if (!discussionId || !visibleDiscussionIds.has(String(discussionId))) {
      return
    }

    if (shouldRefreshForumEvent(detail.event_type)) {
      await loadDiscussions()
      if (getActiveTab() === 'posts' && Number(getRequestedPostUserId() || 0) === Number(getCurrentUserId() || 0)) {
        await loadPosts({ force: true, forceLoading: false })
      }
      return
    }

    mergeForumEventPayload(resourceStore, detail)
    if (detail.payload?.post && getPosts().some(post => Number(post?.discussion_id) === discussionId)) {
      const postId = Number(detail.payload.post.id || 0)
      if (postId > 0) {
        mergePostIds([postId])
      }
    }
  }

  return {
    handleForumEvent,
  }
}

export function useProfileRealtimeState({
  activeTab,
  contentState,
  resourceStore,
  userId,
}) {
  return createProfileRealtimeState({
    getActiveTab() {
      return activeTab.value
    },
    getCurrentUserId() {
      return userId.value
    },
    getDiscussionIds() {
      return contentState.discussionIds.value
    },
    getPosts() {
      return contentState.posts.value
    },
    getRequestedPostUserId() {
      return contentState.requestedPostUserId.value
    },
    loadDiscussions: contentState.loadDiscussions,
    loadPosts: contentState.loadPosts,
    mergePostIds: contentState.mergePostIds,
    resourceStore,
  })
}
