
import { ref, computed } from '@bias/core'
import { getTrackedDiscussionIdsFromDiscussionItems,
  getTrackedDiscussionIdsFromPostItems
} from '@bias/realtime'

function unwrapList(payload) {
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload)) return payload
  return []
}

export function createSearchResultsResourceState({
  resourceStore,
  searchSources,
}) {
  const total = ref(0)
  const discussionTotal = ref(0)
  const postTotal = ref(0)
  const userTotal = ref(0)
  const discussionIds = ref([])
  const postIds = ref([])
  const userIds = ref([])

  const discussions = computed(() => resourceStore.list('discussions', discussionIds.value))
  const posts = computed(() => resourceStore.list('posts', postIds.value))
  const users = computed(() => resourceStore.list('users', userIds.value))
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / 20)))
  const isEmpty = computed(() => !discussions.value.length && !posts.value.length && !users.value.length)
  const trackedDiscussionIds = computed(() => [
    ...getTrackedDiscussionIdsFromDiscussionItems(discussions.value),
    ...getTrackedDiscussionIdsFromPostItems(posts.value),
  ])

  function applySearchResponse(data = {}) {
    total.value = data.total || 0
    discussionTotal.value = data.discussion_total ?? unwrapList(data.discussions || []).length
    postTotal.value = data.post_total ?? unwrapList(data.posts || []).length
    userTotal.value = data.user_total ?? unwrapList(data.users || []).length
    discussionIds.value = resourceStore.upsertMany('discussions', unwrapList(data.discussions || []))
      .map(item => item.id)
    postIds.value = resourceStore.upsertMany('posts', unwrapList(data.posts || []))
      .map(item => item.id)
    userIds.value = resourceStore.upsertMany('users', unwrapList(data.users || []))
      .map(item => item.id)
  }

  function resetResults() {
    total.value = 0
    discussionTotal.value = 0
    postTotal.value = 0
    userTotal.value = 0
    discussionIds.value = []
    postIds.value = []
    userIds.value = []
  }

  function buildSearchSourceSections({ normalizedQuery, searchType }) {
    const sourceItems = {
      discussions: discussions.value,
      posts: posts.value,
      users: users.value,
    }
    const sourceTotals = {
      discussions: discussionTotal.value,
      posts: postTotal.value,
      users: userTotal.value,
    }

    return searchSources.map(source => {
      const sourceKey = source.routeType || source.type
      const items = sourceItems[sourceKey] || []
      const totalForSource = Number(sourceTotals[sourceKey] || 0)
      const resultItems = typeof source.buildResultItems === 'function'
        ? source.buildResultItems(items, { query: normalizedQuery })
        : []

      return {
        ...source,
        key: sourceKey,
        resultItems,
        showMore: searchType === 'all' && totalForSource > items.length,
        visible: searchType === 'all' || searchType === sourceKey,
      }
    })
  }

  return {
    applySearchResponse,
    buildSearchSourceSections,
    discussionIds,
    discussionTotal,
    discussions,
    isEmpty,
    postIds,
    postTotal,
    posts,
    resetResults,
    total,
    totalPages,
    trackedDiscussionIds,
    userIds,
    userTotal,
    users,
  }
}

export function useSearchResultsResourceState({
  resourceStore,
  searchSources,
}) {
  return createSearchResultsResourceState({
    resourceStore,
    searchSources,
  })
}
