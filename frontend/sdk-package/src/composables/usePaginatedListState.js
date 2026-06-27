import { computed, ref, watch } from 'vue'

export function usePaginatedListState(options = {}) {
  const {
    watchSources = () => [],
    page = null,
    initialLoading = true,
    load,
    reset = null,
    onBeforeLoad = null,
    onAfterLoad = null,
  } = options

  const loading = ref(Boolean(initialLoading))
  const refreshing = ref(false)
  const loadingMore = ref(false)
  const loadError = ref('')

  const isBusy = computed(() => loading.value || refreshing.value || loadingMore.value)

  watch(
    watchSources,
    async () => {
      if (page?.value && page.value !== 1) {
        page.value = 1
      }
      if (typeof reset === 'function') {
        reset()
      }
      await refresh({ mode: 'initial', forceLoading: true })
    },
    { immediate: true }
  )

  async function refresh(options = {}) {
    const mode = options.mode || 'refresh'
    const forceLoading = Boolean(options.forceLoading)

    if (mode === 'refresh' && isBusy.value) {
      return null
    }

    if (mode === 'append' && (loadingMore.value || loading.value)) {
      return null
    }

    if (forceLoading || mode === 'initial') {
      loading.value = true
      refreshing.value = false
    } else if (mode === 'append') {
      loadingMore.value = true
    } else {
      refreshing.value = true
    }

    loadError.value = ''

    try {
      onBeforeLoad?.({ mode })
      const result = await load?.({ mode })
      await onAfterLoad?.({ mode, result })
      return result
    } catch (error) {
      loadError.value = error?.response?.data?.error || error?.response?.data?.detail || error?.message || ''
      throw error
    } finally {
      loading.value = false
      refreshing.value = false
      loadingMore.value = false
    }
  }

  return {
    isBusy,
    loadError,
    loading,
    loadingMore,
    refresh,
    refreshing,
  }
}
