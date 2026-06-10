import { usePaginatedListState } from '@bias/core'
import { getUiCopy } from '@bias/forum'
import { createDiscussionListLoadState } from './discussionListLoadState.shared.js'

export function useDiscussionListLoadState({
  modalStore,
  resourceState,
  route,
  searchQuery,
  sortBy,
  listFilter,
}) {
  return createDiscussionListLoadState({
    getErrorMessage(error, fallback = getUiCopy({
      surface: 'discussion-list-action-retry-message',
    })?.text || '请稍后重试') {
      return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
    },
    getText: getUiCopy,
    listStateFactory({ load, reset }) {
      return usePaginatedListState({
        watchSources: () => [route.name, route.fullPath, searchQuery.value, sortBy.value, listFilter.value],
        initialLoading: true,
        load,
        reset,
      })
    },
    loadInitialResources: resourceState.loadInitialResources,
    loadMoreDiscussions: resourceState.loadMoreDiscussions,
    modalStore,
    refreshDiscussions: resourceState.refreshDiscussions,
    resetResources: resourceState.reset,
  })
}
