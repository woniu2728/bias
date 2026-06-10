import {
  api,
  ref,
  computed,
  useRequestedPaginatedListState } from '@bias/core'

function unwrapList(payload) {
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload)) return payload
  return []
}

function normalizeDiscussion(discussion = {}) {
  const unreadCount = Number(discussion.unread_count || 0)
  return {
    ...discussion,
    is_sticky: Boolean(discussion.is_sticky ?? discussion.is_pinned),
    is_unread: Boolean(discussion.is_unread || unreadCount > 0),
    unread_count: unreadCount,
    last_read_post_number: Number(discussion.last_read_post_number || 0),
    user: discussion.user || null,
    last_post: discussion.last_post || null,
  }
}

function normalizePost(post = {}) {
  return {
    ...post,
    user: post.user || null,
    discussion: post.discussion || (post.discussion_id ? {
      id: post.discussion_id,
      title: post.discussion_title || '讨论',
    } : null),
  }
}

export function createProfileContentState({
  activeTab,
  forumRealtimeStore,
  getErrorMessage,
  getLoadDiscussionsErrorText,
  getLoadPostsErrorText,
  getUser,
  requestedListStateFactory,
  resourceStore,
  setSettingsError,
  userId,
}) {
  const discussionIds = ref([])
  const postIds = ref([])
  const requestedPostUserId = ref(null)

  const discussions = computed(() => resourceStore.list('discussions', discussionIds.value))
  const posts = computed(() => resourceStore.list('posts', postIds.value))

  const discussionListState = requestedListStateFactory({
    watchSources: () => [userId.value || 0],
    isRequested: () => Boolean(getUser()),
    initialLoading: false,
    reset() {
      forumRealtimeStore.untrackDiscussionIds(discussionIds.value)
      discussionIds.value = []
    },
    async load() {
      const data = await api.get('/discussions/', {
        params: {
          author: getUser().username,
          sort: 'newest',
          limit: 20,
        },
      })
      const nextDiscussionIds = unwrapList(data)
        .map(normalizeDiscussion)
        .map(item => resourceStore.upsert('discussions', item).id)

      forumRealtimeStore.untrackDiscussionIds(discussionIds.value)
      discussionIds.value = nextDiscussionIds
      forumRealtimeStore.trackDiscussionIds(nextDiscussionIds)
      return data
    },
  })

  const postListState = requestedListStateFactory({
    watchSources: () => [userId.value || 0],
    isRequested: () => Boolean(getUser()) && (
      activeTab.value === 'posts'
      || Number(requestedPostUserId.value || 0) === Number(userId.value || 0)
    ),
    initialLoading: false,
    reset() {
      postIds.value = []
    },
    async load() {
      const data = await api.get('/posts', {
        params: {
          author: getUser().username,
          limit: 20,
        },
      })
      postIds.value = unwrapList(data)
        .map(normalizePost)
        .map(item => resourceStore.upsert('posts', item).id)
      return data
    },
  })

  async function loadDiscussions() {
    if (!getUser()) return

    try {
      await discussionListState.refresh({
        mode: 'initial',
        forceLoading: discussionIds.value.length === 0,
      })
    } catch (error) {
      console.error('加载讨论失败:', error)
      setSettingsError(getErrorMessage(
        error,
        getLoadDiscussionsErrorText()
      ))
    }
  }

  async function loadPosts(options = {}) {
    if (!getUser()) return
    if (Number(requestedPostUserId.value || 0) !== Number(userId.value || 0)) {
      requestedPostUserId.value = userId.value
      if (!options.force) {
        return
      }
    }

    if (!options.force && posts.value.length > 0) return

    try {
      await postListState.refresh({
        mode: 'initial',
        forceLoading: options.forceLoading ?? posts.value.length === 0,
      })
    } catch (error) {
      console.error('加载回复失败:', error)
      setSettingsError(getErrorMessage(
        error,
        getLoadPostsErrorText()
      ))
    }
  }

  function mergePostIds(ids = []) {
    const seen = new Set()
    postIds.value = [...postIds.value, ...ids].filter(id => {
      const key = String(id)
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })
  }

  function cleanupTrackedDiscussions() {
    forumRealtimeStore.untrackDiscussionIds(discussionIds.value)
  }

  function resetProfileScope() {
    discussionIds.value = []
    postIds.value = []
    requestedPostUserId.value = null
  }

  function markPostsRequestedForCurrentUser() {
    if (userId.value) {
      requestedPostUserId.value = userId.value
    }
  }

  return {
    cleanupTrackedDiscussions,
    discussionIds,
    discussionListState,
    discussions,
    loadDiscussions,
    loadPosts,
    loadingDiscussions: discussionListState.loading,
    loadingPosts: postListState.loading,
    markPostsRequestedForCurrentUser,
    mergePostIds,
    postIds,
    postListState,
    posts,
    requestedPostUserId,
    resetProfileScope,
  }
}

export function useProfileContentState({
  activeTab,
  forumRealtimeStore,
  getErrorMessage,
  getLoadDiscussionsErrorText,
  getLoadPostsErrorText,
  getUser,
  resourceStore,
  setSettingsError,
  userId,
}) {
  return createProfileContentState({
    activeTab,
    forumRealtimeStore,
    getErrorMessage,
    getLoadDiscussionsErrorText,
    getLoadPostsErrorText,
    getUser,
    requestedListStateFactory(options) {
      return useRequestedPaginatedListState(options)
    },
    resourceStore,
    setSettingsError,
    userId,
  })
}
