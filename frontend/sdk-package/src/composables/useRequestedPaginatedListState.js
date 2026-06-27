import { computed } from 'vue'
import { usePaginatedListState } from './usePaginatedListState.js'

export function useRequestedPaginatedListState(options = {}) {
  const {
    watchSources = () => [],
    isRequested = () => true,
    initialLoading = false,
    load,
    reset = null,
    onBeforeLoad = null,
    onAfterLoad = null,
  } = options

  const requested = computed(() => Boolean(isRequested()))

  return usePaginatedListState({
    watchSources: () => [...watchSources(), requested.value],
    initialLoading,
    reset,
    onBeforeLoad,
    onAfterLoad,
    async load(context) {
      if (!requested.value) {
        return null
      }

      return load?.(context)
    },
  })
}
