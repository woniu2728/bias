import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { normalizeDiscussion, normalizeTag, unwrapList } from '@/utils/forum'

export function useDiscussionListData({
  authStore,
  modalStore,
  route
}) {
  const discussions = ref([])
  const tags = ref([])
  const currentTag = ref(null)
  const loading = ref(true)
  const refreshing = ref(false)
  const loadingMore = ref(false)
  const sortBy = ref('latest')
  const currentPage = ref(1)
  const total = ref(0)
  const markingAllRead = ref(false)
  const pageSize = 20

  const currentTagSlug = computed(() => route.params.slug || null)
  const searchQuery = computed(() => route.query.search?.toString().trim() || '')
  const hasMore = computed(() => currentPage.value * pageSize < total.value)
  const isFollowingPage = computed(() => route.name === 'following')

  onMounted(async () => {
    await refreshPageData()
    window.addEventListener('bias:discussion-read-state-updated', handleDiscussionReadStateUpdated)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('bias:discussion-read-state-updated', handleDiscussionReadStateUpdated)
  })

  watch(
    () => [route.name, route.params.slug, route.query.search],
    async () => {
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
      discussions.value = []
      currentTag.value = null
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
    tags.value = unwrapList(response).map(normalizeTag)
  }

  async function loadCurrentTag() {
    if (!currentTagSlug.value || isFollowingPage.value) {
      currentTag.value = null
      return
    }

    try {
      const response = await api.get(`/tags/slug/${currentTagSlug.value}`)
      currentTag.value = normalizeTag(response)
    } catch (error) {
      currentTag.value = null
      console.error('加载标签详情失败:', error)
    }
  }

  async function loadDiscussions(append) {
    const response = await api.get('/discussions/', {
      params: {
        page: currentPage.value,
        limit: pageSize,
        sort: sortBy.value,
        q: searchQuery.value || undefined,
        tag: currentTagSlug.value || undefined,
        subscription: isFollowingPage.value ? 'following' : undefined
      }
    })

    const items = unwrapList(response).map(normalizeDiscussion)

    if (append) {
      discussions.value.push(...items)
    } else {
      discussions.value = items
    }

    total.value = response.total || items.length
  }

  async function changeSortBy(sort) {
    if (sortBy.value === sort) return
    sortBy.value = sort
    currentPage.value = 1
    loading.value = true

    try {
      await loadDiscussions(false)
    } finally {
      loading.value = false
    }
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
      discussions.value = discussions.value.map(discussion => ({
        ...discussion,
        is_unread: false,
        unread_count: 0,
        last_read_post_number: discussion.last_post_number || discussion.last_read_post_number || 0,
        last_read_at: response.marked_all_as_read_at || discussion.last_read_at
      }))
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

    discussions.value = discussions.value.map(discussion => {
      if (Number(discussion.id) !== discussionId) return discussion

      const lastReadPostNumber = Math.max(
        Number(discussion.last_read_post_number || 0),
        Number(detail.lastReadPostNumber || 0)
      )
      const unreadCount = Math.max(Number(detail.unreadCount || 0), 0)

      return {
        ...discussion,
        last_read_post_number: lastReadPostNumber,
        last_read_at: detail.lastReadAt || discussion.last_read_at,
        unread_count: unreadCount,
        is_unread: unreadCount > 0
      }
    })
  }

  return {
    changeSortBy,
    currentTag,
    currentTagSlug,
    discussions,
    hasMore,
    isFollowingPage,
    loadMore,
    loading,
    loadingMore,
    markAllAsRead,
    markingAllRead,
    refreshPageData,
    refreshDiscussionList,
    refreshing,
    sortBy,
    tags
  }
}
