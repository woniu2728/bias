import { api, ref } from '@bias/core'

export function createTagsLoadState({
  fetchTags,
  getErrorMessage,
  listStateFactory,
  onTagsLoaded,
  resetTags,
}) {
  async function loadTags() {
    const response = await fetchTags()
    onTagsLoaded(response)
    return response
  }

  const listState = listStateFactory({
    load: loadTags,
    reset: resetTags,
  })

  async function refreshTags() {
    try {
      await listState.refresh({ mode: 'refresh' })
    } catch (error) {
      console.error('加载标签失败:', error)
    }
  }

  async function loadInitialTags() {
    try {
      await listState.refresh({ mode: 'initial', forceLoading: true })
    } catch (error) {
      console.error('加载标签失败:', error)
      resetTags()
    }
  }

  return {
    getErrorMessage,
    listState,
    loadInitialTags,
    loadTags,
    refreshTags,
  }
}

export function useTagsLoadState({
  resourceState,
}) {
  return createTagsLoadState({
    async fetchTags() {
      return api.get('/tags', {
        params: {
          include_children: true,
        },
      })
    },
    getErrorMessage(error) {
      return error?.response?.data?.error
        || error?.response?.data?.detail
        || error?.message
        || '加载标签失败，请稍后重试'
    },
    listStateFactory({ load }) {
      const loading = ref(false)
      const refreshing = ref(false)
      const loadingMore = ref(false)

      return {
        loading,
        loadingMore,
        refreshing,
        async refresh(options = {}) {
          const mode = options.mode || 'refresh'
          if (mode === 'initial') {
            loading.value = true
          } else {
            refreshing.value = true
          }

          try {
            return await load()
          } finally {
            loading.value = false
            refreshing.value = false
            loadingMore.value = false
          }
        },
      }
    },
    onTagsLoaded(response) {
      resourceState.applyTagsResponse(response)
    },
    resetTags: resourceState.resetTags,
  })
}
