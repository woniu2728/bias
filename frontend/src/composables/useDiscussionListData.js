import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { useDiscussionListRouteState } from '@/composables/useDiscussionListRouteState'
import { useResourceStore } from '@/stores/resource'
import { normalizeDiscussion, normalizeTag, unwrapList } from '@/utils/forum'

export function useDiscussionListData({
  authStore,
  modalStore,
  route,
  router,
}) {
  const resourceStore = useResourceStore()
  const routeState = useDiscussionListRouteState({ route, router })
  const discussionIds = ref([])
  const tagIds = ref([])
  const currentTagId = ref(null)
  const discussions = computed(() => resourceStore.list('discussions', discussionIds.value))
  const tags = computed(() => resourceStore.list('tags', tagIds.value))
  const currentTag = computed(() => (currentTagId.value ? resourceStore.get('tags', currentTagId.value) : null))
  const loading = ref(true)
  const refreshing = ref(false)
  const loadingMore = ref(false)
  const sortOptions = ref([])
  const filterOptions = ref([])
  const currentPage = ref(1)
  const total = ref(0)
  const markingAllRead = ref(false)
  const pageSize = 20

  const currentTagSlug = computed(() => route.params.slug || null)
  const searchQuery = routeState.searchQuery
  const sortBy = routeState.sortBy
  const listFilter = routeState.listFilter
  const hasMore = computed(() => currentPage.value * pageSize < total.value)
  const isFollowingPage = computed(() => route.name === 'following' || listFilter.value === 'following')

  onMounted(async () => {
    await refreshPageData()
    window.addEventListener('bias:discussion-read-state-updated', handleDiscussionReadStateUpdated)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('bias:discussion-read-state-updated', handleDiscussionReadStateUpdated)
  })

  watch(
    () => [route.name, route.params.slug, route.query.q, route.query.sort, route.query.filter],
    async () => {
      discussionIds.value = []
      currentTagId.value = null
      currentPage.value = 1
      await refreshPageData()
    }
  )

  async function refreshPageData() {
    loading.value = true
    refreshing.value = false
    try {
      await Promise.all([loadTags(), loadCurrentTag(), loadDiscussions(false)])
    } catch (error) {
      discussionIds.value = []
      currentTagId.value = null
      console.error('加载首页列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  async function refreshDiscussionList() {
    if (loading.value || refreshing.value) return

    refreshing.value = true
    try {
      await loadDiscussions(false)
    } catch (error) {
      console.error('刷新讨论列表失败:', error)
      await modalStore.alert({
        title: '刷新失败',
        message: '请稍后重试',
        tone: 'danger'
      })
    } finally {
      refreshing.value = false
    }
  }

  async function loadTags() {
    const response = await api.get('/tags', {
      params: {
        include_children: true
      }
    })
    tagIds.value = unwrapList(response)
      .map(normalizeTag)
      .map(item => resourceStore.upsert('tags', item).id)
  }

  async function loadCurrentTag() {
    if (!currentTagSlug.value || isFollowingPage.value) {
      currentTagId.value = null
      return
    }

    try {
      const response = await api.get(`/tags/slug/${currentTagSlug.value}`)
      const tag = resourceStore.upsert('tags', normalizeTag(response))
      currentTagId.value = tag.id
    } catch (error) {
      currentTagId.value = null
      console.error('加载标签详情失败:', error)
    }
  }

  async function loadDiscussions(append) {
    const response = await api.get('/discussions/', {
      params: {
        page: currentPage.value,
        limit: pageSize,
        sort: sortBy.value,
        filter: listFilter.value,
        q: searchQuery.value || undefined,
        tag: currentTagSlug.value || undefined,
      }
    })

    const items = unwrapList(response).map(normalizeDiscussion)
    const ids = items.map(item => resourceStore.upsert('discussions', item).id)

    if (append) {
      discussionIds.value = [...discussionIds.value, ...ids]
    } else {
      discussionIds.value = ids
    }

    total.value = response.total || items.length
    sortOptions.value = Array.isArray(response.available_sorts) ? response.available_sorts : []
    filterOptions.value = Array.isArray(response.available_filters) ? response.available_filters : []
  }

  async function changeSortBy(sort) {
    if (sortBy.value === sort) return
    await routeState.push({
      sortBy: sort,
      listFilter: listFilter.value,
      searchQuery: searchQuery.value,
    })
  }

  async function changeListFilter(filterCode) {
    if (listFilter.value === filterCode) return
    await routeState.push({
      listFilter: filterCode,
      sortBy: sortBy.value,
      searchQuery: searchQuery.value,
    })
  }

  async function changeSearchQuery(nextQuery) {
    if (searchQuery.value === nextQuery) return
    await routeState.push({
      searchQuery: nextQuery,
      sortBy: sortBy.value,
      listFilter: listFilter.value,
    })
  }

  async function loadMore() {
    loadingMore.value = true
    currentPage.value += 1
    try {
      await loadDiscussions(true)
    } finally {
      loadingMore.value = false
    }
  }

  async function markAllAsRead() {
    if (!authStore.isAuthenticated || markingAllRead.value) return

    markingAllRead.value = true
    try {
      const response = await api.post('/discussions/read-all')
      discussionIds.value.forEach(id => {
        const discussion = resourceStore.get('discussions', id)
        if (!discussion) return
        resourceStore.upsert('discussions', {
          ...discussion,
          is_unread: false,
          unread_count: 0,
          last_read_post_number: discussion.last_post_number || discussion.last_read_post_number || 0,
          last_read_at: response.marked_all_as_read_at || discussion.last_read_at
        })
      })
    } catch (error) {
      console.error('标记已读失败:', error)
      await modalStore.alert({
        title: '标记已读失败',
        message: '请稍后重试',
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
    if (!discussion) return

    const lastReadPostNumber = Math.max(
      Number(discussion.last_read_post_number || 0),
      Number(detail.lastReadPostNumber || 0)
    )
    const unreadCount = Math.max(Number(detail.unreadCount || 0), 0)

    resourceStore.upsert('discussions', {
      ...discussion,
      last_read_post_number: lastReadPostNumber,
      last_read_at: detail.lastReadAt || discussion.last_read_at,
      unread_count: unreadCount,
      is_unread: unreadCount > 0
    })
  }

  return {
    changeSortBy,
    currentTag,
    currentTagSlug,
    discussions,
    filterOptions,
    hasMore,
    isFollowingPage,
    listFilter,
    loadMore,
    loading,
    loadingMore,
    markAllAsRead,
    changeListFilter,
    changeSearchQuery,
    markingAllRead,
    refreshPageData,
    refreshDiscussionList,
    refreshing,
    sortBy,
    sortOptions,
    tags
  }
}
