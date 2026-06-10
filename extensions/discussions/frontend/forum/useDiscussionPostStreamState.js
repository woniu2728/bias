
import {
  api,
  watch,
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  unwrapList,
  useResourceStore
} from '@bias/core'

import {
  normalizePost } from '@bias/posts'
import {
  getForumRealtimeEventPolicy,
  useForumRealtimeStore,
  mergeForumEventPayload,
  } from '@bias/realtime'
import { runForumRuntimeHook
} from '@bias/forum'
import { shouldAppendRealtimePostImmediately } from './discussionPostStream.js'
import { useDiscussionNearRouteState } from './useDiscussionNearRouteState'

export function useDiscussionPostStreamState({
  authStore,
  discussion,
  discussionId,
  forumStore,
  route,
  router,
  patchDiscussion,
  refreshDiscussion,
}) {
  const resourceStore = useResourceStore()
  const forumRealtimeStore = useForumRealtimeStore()
  const nearRouteState = useDiscussionNearRouteState({ route, router })
  const postIds = ref([])
  const posts = computed(() => resourceStore.list('posts', postIds.value))
  const loading = ref(true)
  const loadingMore = ref(false)
  const loadingPrevious = ref(false)
  const firstLoadedPostNumber = ref(0)
  const lastLoadedPostNumber = ref(0)
  const totalPosts = ref(0)
  const highlightedPostNumber = ref(null)
  const currentVisiblePostNumber = ref(1)
  const currentVisiblePostProgress = ref(1)
  const pendingNewReplyCount = ref(0)
  const pageLimit = 20

  let nearUrlTimer = null
  let readStateTimer = null
  let lastReportedReadNumber = 0

  const targetNearPost = nearRouteState.near
  const hasPrevious = computed(() => Boolean(firstLoadedPostNumber.value > 1))
  const hasMore = computed(() => Boolean(totalPosts.value > 0 && lastLoadedPostNumber.value > 0 && lastLoadedPostNumber.value < totalPosts.value))
  const maxPostNumber = computed(() => {
    return discussion.value?.last_post_number || discussion.value?.comment_count || 1
  })
  const unreadCount = computed(() => {
    return Math.max(Number(discussion.value?.unread_count || 0), 0)
  })
  const unreadStartPostNumber = computed(() => {
    if (!unreadCount.value) return null

    const lastRead = Number(discussion.value?.last_read_post_number || 0)
    return Math.min(maxPostNumber.value, Math.max(1, lastRead + 1))
  })
  const typingDiscussionId = computed(() => Number(discussionId.value || 0))

  onMounted(() => {
    window.addEventListener('bias:reply-created', handleReplyCreated)
    window.addEventListener('bias:post-updated', handlePostUpdated)
    window.addEventListener('bias:discussion-updated', handleDiscussionUpdated)
    window.addEventListener('bias:forum-event', handleForumEvent)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('bias:reply-created', handleReplyCreated)
    window.removeEventListener('bias:post-updated', handlePostUpdated)
    window.removeEventListener('bias:discussion-updated', handleDiscussionUpdated)
    window.removeEventListener('bias:forum-event', handleForumEvent)
    if (discussionId.value) {
      forumRealtimeStore.untrackDiscussionIds([discussionId.value])
    }
    if (nearUrlTimer) {
      clearTimeout(nearUrlTimer)
    }
    if (readStateTimer) {
      clearTimeout(readStateTimer)
    }
  })

  watch(
    discussionId,
    (nextId, previousId) => {
      if (previousId) {
        forumRealtimeStore.untrackDiscussionIds([previousId])
      }
      if (nextId) {
        forumRealtimeStore.trackDiscussionIds([nextId])
      }
    }
  )

  async function refreshPostStream(options = {}) {
    const keepLoading = Boolean(options.keepLoading)
    loading.value = !keepLoading
    try {
      await loadInitialPosts()
    } finally {
      loading.value = false
    }
  }

  async function loadInitialPosts() {
    if (targetNearPost.value) {
      await syncWindowToRouteNear()
      return
    }

    const data = await fetchPosts({ near: 1 })
    replacePosts(data)
  }

  async function fetchPosts(params = {}) {
    const requestParams = {
      limit: pageLimit,
      ...params,
    }

    return api.get(`/discussions/${route.params.id}/posts`, { params: requestParams })
  }

  function replacePosts(data) {
    const items = unwrapList(data).map(normalizePost)
    postIds.value = collectPostIds(items)
    firstLoadedPostNumber.value = Number(data.current_start || items[0]?.number || 0)
    lastLoadedPostNumber.value = Number(data.current_end || items[items.length - 1]?.number || 0)
    totalPosts.value = data.total || items.length
    syncPendingNewReplyCount()
    return items
  }

  function appendPosts(data) {
    const items = unwrapList(data).map(normalizePost)
    mergePostIds(collectPostIds(items))
    lastLoadedPostNumber.value = Number(data.current_end || items[items.length - 1]?.number || lastLoadedPostNumber.value)
    totalPosts.value = data.total || totalPosts.value
    syncPendingNewReplyCount()
  }

  function prependPosts(data) {
    const items = unwrapList(data).map(normalizePost)
    mergePostIds(collectPostIds(items), { prepend: true })
    firstLoadedPostNumber.value = Number(data.current_start || items[0]?.number || firstLoadedPostNumber.value)
    totalPosts.value = data.total || totalPosts.value
    syncPendingNewReplyCount()
  }

  async function loadMorePosts() {
    if (!hasMore.value) return

    loadingMore.value = true
    try {
      const data = await fetchPosts({ after: lastLoadedPostNumber.value })
      appendPosts(data)
    } finally {
      loadingMore.value = false
    }
  }

  async function loadPreviousPosts() {
    if (!hasPrevious.value) return

    loadingPrevious.value = true
    try {
      const data = await fetchPosts({ before: firstLoadedPostNumber.value })
      prependPosts(data)
    } finally {
      loadingPrevious.value = false
    }
  }

  async function jumpToPost(number) {
    const targetNumber = normalizePostNumber(number)
    if (!targetNumber) return

    if (posts.value.some(post => post.number === targetNumber)) {
      await scrollToPost(targetNumber)
      replaceNearInAddressBar(targetNumber)
      return
    }

    await nearRouteState.replaceRouteNear(targetNumber)
  }

  async function scrollToPost(number) {
    await nextTick()
    const target = document.getElementById(`post-${number}`)
    if (!target) return

    highlightedPostNumber.value = number
    currentVisiblePostNumber.value = number
    currentVisiblePostProgress.value = number
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setTimeout(() => {
      if (highlightedPostNumber.value === number) {
        highlightedPostNumber.value = null
      }
    }, 2400)
  }

  async function syncWindowToRouteNear() {
    const targetNumber = normalizePostNumber(targetNearPost.value)
    if (!targetNumber) return null

    if (posts.value.some(post => post.number === targetNumber)) {
      await scrollToPost(targetNumber)
      return targetNumber
    }

    const data = await fetchPosts({ near: targetNumber })
    const items = replacePosts(data)
    const resolvedNumber = items.find(post => post.number === targetNumber)?.number
      || items[0]?.number
      || null

    if (!resolvedNumber) return null

    await scrollToPost(resolvedNumber)
    replaceNearInAddressBar(resolvedNumber)
    scheduleReadStateSync(resolvedNumber)
    return resolvedNumber
  }

  function resetPostStream() {
    postIds.value = []
    firstLoadedPostNumber.value = 0
    lastLoadedPostNumber.value = 0
    totalPosts.value = 0
    highlightedPostNumber.value = null
    pendingNewReplyCount.value = 0
    currentVisiblePostNumber.value = normalizePostNumber(targetNearPost.value) || 1
    currentVisiblePostProgress.value = currentVisiblePostNumber.value
  }

  function syncPendingNewReplyCount() {
    pendingNewReplyCount.value = Math.max(totalPosts.value - lastLoadedPostNumber.value, 0)
  }

  function hasPendingNewReplies() {
    return pendingNewReplyCount.value > 0
  }

  function isNearStreamBottom() {
    return shouldAppendRealtimePostImmediately({
      currentVisiblePostNumber: currentVisiblePostNumber.value,
      lastLoadedPostNumber: lastLoadedPostNumber.value,
    })
  }

  async function loadPendingNewReplies() {
    if (!pendingNewReplyCount.value) return
    await loadMorePosts()
  }

  function collectPostIds(items = []) {
    return items.map(item => resourceStore.upsert('posts', item).id)
  }

  function mergePostIds(ids = [], { prepend = false } = {}) {
    const source = prepend ? [...ids, ...postIds.value] : [...postIds.value, ...ids]
    const seen = new Set()
    postIds.value = source.filter(id => {
      const key = String(id)
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })
  }

  function showUnreadDivider(post) {
    return Boolean(
      authStore.isAuthenticated
      && unreadStartPostNumber.value
      && unreadCount.value > 0
      && Number(post?.number) === Number(unreadStartPostNumber.value)
    )
  }

  function clampPostPosition(value) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) return 1
    return Math.min(maxPostNumber.value, Math.max(1, parsed))
  }

  function sanitizePostNumber(value) {
    return Math.floor(clampPostPosition(value))
  }

  function normalizePostNumber(value) {
    return sanitizePostNumber(value)
  }

  function scheduleNearUrlSync(number) {
    if (nearUrlTimer) {
      clearTimeout(nearUrlTimer)
    }

    nearUrlTimer = setTimeout(() => {
      replaceNearInAddressBar(number)
    }, 300)
  }

  function replaceNearInAddressBar(number) {
    nearRouteState.replaceAddressBarNear(number)
  }

  function scheduleReadStateSync(number) {
    if (!authStore.isAuthenticated || !discussion.value) return

    const targetNumber = normalizePostNumber(number)
    const currentRead = Number(discussion.value.last_read_post_number || 0)
    if (targetNumber <= Math.max(currentRead, lastReportedReadNumber)) return

    if (readStateTimer) {
      clearTimeout(readStateTimer)
    }

    readStateTimer = setTimeout(async () => {
      try {
        const data = await api.post(`/discussions/${discussion.value.id}/read`, {
          last_read_post_number: targetNumber,
        })
        if (!discussion.value) return

        lastReportedReadNumber = Number(data.last_read_post_number || targetNumber)
        const unreadCountValue = Math.max((discussion.value.last_post_number || 0) - lastReportedReadNumber, 0)
        patchDiscussion({
          last_read_post_number: lastReportedReadNumber,
          last_read_at: data.last_read_at || discussion.value.last_read_at,
          unread_count: unreadCountValue,
          is_unread: unreadCountValue > 0,
        })
        window.dispatchEvent(new CustomEvent('bias:discussion-read-state-updated', {
          detail: {
            discussionId: discussion.value.id,
            lastReadPostNumber: lastReportedReadNumber,
            lastReadAt: data.last_read_at || discussion.value.last_read_at,
            unreadCount: unreadCountValue,
          },
        }))
      } catch (error) {
        console.error('更新讨论阅读状态失败:', error)
      }
    }, 400)
  }

  async function handleReplyCreated(event) {
    const detail = event.detail || {}
    if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return
    if (!detail.post) return

    const newPost = normalizePost(detail.post)
    if (posts.value.some(post => post.id === newPost.id)) return

    const mergedPost = resourceStore.upsert('posts', newPost)
    const newPostNumber = Number(newPost.number || 0)
    const shouldAppendImmediately = isNearStreamBottom()

    if (shouldAppendImmediately) {
      mergePostIds([mergedPost.id])
      lastLoadedPostNumber.value = Math.max(lastLoadedPostNumber.value, newPostNumber)
    }

    totalPosts.value = Math.max(totalPosts.value + 1, newPostNumber, posts.value.length)
    syncPendingNewReplyCount()

    const lastPostNumber = Math.max(discussion.value.last_post_number || 0, newPostNumber)
    const extensionDiscussionPatch = await collectReplyCreatedDiscussionPatch(newPost)
    if (!shouldAppendImmediately) {
      const pendingUnreadCount = Math.max(Number(discussion.value.unread_count || 0), pendingNewReplyCount.value)
      patchDiscussion({
        comment_count: Math.max((discussion.value.comment_count || 0) + 1, totalPosts.value),
        last_post_id: newPost.id,
        last_post_number: lastPostNumber,
        last_posted_at: newPost.created_at || discussion.value.last_posted_at,
        unread_count: pendingUnreadCount,
        is_unread: pendingUnreadCount > 0,
        ...extensionDiscussionPatch,
      })
      return
    }

    lastReportedReadNumber = Math.max(lastReportedReadNumber, newPostNumber)
    const lastReadPostNumber = Math.max(Number(discussion.value.last_read_post_number || 0), newPostNumber)
    const unreadCountValue = Math.max(lastPostNumber - lastReadPostNumber, 0)
    patchDiscussion({
      comment_count: Math.max((discussion.value.comment_count || 0) + 1, totalPosts.value),
      last_post_id: newPost.id,
      last_post_number: lastPostNumber,
      last_posted_at: newPost.created_at || discussion.value.last_posted_at,
      last_read_post_number: lastReadPostNumber,
      last_read_at: newPost.created_at || discussion.value.last_read_at,
      unread_count: unreadCountValue,
      is_unread: unreadCountValue > 0,
      ...extensionDiscussionPatch,
    })

    window.dispatchEvent(new CustomEvent('bias:discussion-read-state-updated', {
      detail: {
        discussionId: discussion.value.id,
        lastReadPostNumber,
        lastReadAt: newPost.created_at || discussion.value.last_read_at,
        unreadCount: unreadCountValue,
      },
    }))

    await scrollToPost(newPost.number)
  }

  async function collectReplyCreatedDiscussionPatch(post) {
    const results = await runForumRuntimeHook('onReplyCreated', {
      authStore,
      discussion: discussion.value,
      forumStore,
      post,
    })

    return results.reduce((patch, result) => {
      if (!result || typeof result !== 'object' || result.error) {
        return patch
      }
      if (result.discussionPatch && typeof result.discussionPatch === 'object') {
        return {
          ...patch,
          ...result.discussionPatch,
        }
      }
      if (result.patch && typeof result.patch === 'object') {
        return {
          ...patch,
          ...result.patch,
        }
      }
      return {
        ...patch,
        ...result,
      }
    }, {})
  }

  function applyRealtimeEvent(event) {
    if (!event || Number(event.discussion_id) !== Number(route.params.id)) return

    const realtimePolicy = getForumRealtimeEventPolicy(event.event_type, {
      discussion: discussion.value,
      event,
    })

    if (realtimePolicy.refresh) {
      refreshDiscussion().catch(error => {
        console.error('刷新讨论详情失败:', error)
      })
      return
    }

    const payload = event.payload || {}
    mergeForumEventPayload(resourceStore, event)

    if (payload.post) {
      const postId = Number(payload.post.id || 0)
      const normalizedPost = postId > 0
        ? resourceStore.get('posts', postId) || normalizePost(payload.post)
        : normalizePost(payload.post)
      const normalizedPostNumber = Number(normalizedPost?.number || 0)
      if (realtimePolicy.appendPost) {
        totalPosts.value = Math.max(totalPosts.value, normalizedPostNumber)
        if (shouldAppendRealtimePostImmediately({
          currentVisiblePostNumber: currentVisiblePostNumber.value,
          lastLoadedPostNumber: lastLoadedPostNumber.value,
          postIds: postIds.value,
          postId: normalizedPost.id,
          postNumber: normalizedPostNumber,
        })) {
          upsertPost(normalizedPost)
          sortPostIds()
          lastLoadedPostNumber.value = Math.max(lastLoadedPostNumber.value, normalizedPostNumber)
        }
        syncPendingNewReplyCount()
        return
      }

      if (realtimePolicy.upsertPost) {
        upsertPost(normalizedPost)
        sortPostIds()
        return
      }

      upsertPost(normalizedPost)
    }
  }

  function handleForumEvent(event) {
    applyRealtimeEvent(event.detail)
  }

  function handlePostUpdated(event) {
    const detail = event.detail || {}
    if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return
    if (!detail.post) return

    upsertPost(detail.post)
  }

  async function handleDiscussionUpdated(event) {
    const detail = event.detail || {}
    if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return

    await refreshDiscussion()
  }

  function upsertPost(rawPost) {
    const updatedPost = resourceStore.upsert('posts', normalizePost(rawPost))
    if (!postIds.value.includes(updatedPost.id)) {
      mergePostIds([updatedPost.id])
    }
  }

  function sortPostIds() {
    postIds.value = [...postIds.value].sort((leftId, rightId) => {
      const left = resourceStore.get('posts', leftId)
      const right = resourceStore.get('posts', rightId)
      return Number(left?.number || 0) - Number(right?.number || 0)
    })
  }

  function removePost(postId) {
    postIds.value = postIds.value.filter(id => String(id) !== String(postId))
    resourceStore.remove('posts', postId)
  }

  return {
    currentVisiblePostNumber,
    currentVisiblePostProgress,
    hasMore,
    hasPendingNewReplies,
    hasPrevious,
    highlightedPostNumber,
    lastReportedReadNumber,
    loadInitialPosts,
    loadMorePosts,
    loadPendingNewReplies,
    loadPreviousPosts,
    loading,
    loadingMore,
    loadingPrevious,
    jumpToPost,
    maxPostNumber,
    normalizePostNumber,
    patchDiscussion,
    pendingNewReplyCount,
    postIds,
    posts,
    refreshPostStream,
    removePost,
    replaceNearInAddressBar,
    resetPostStream,
    scheduleNearUrlSync,
    scheduleReadStateSync,
    scrollToPost,
    syncWindowToRouteNear,
    setCurrentVisiblePostNumber(value) {
      currentVisiblePostNumber.value = value
    },
    setCurrentVisiblePostProgress(value) {
      currentVisiblePostProgress.value = value
    },
    showUnreadDivider,
    totalPosts,
    typingDiscussionId,
    unreadCount,
    unreadStartPostNumber,
    upsertPost,
  }
}
