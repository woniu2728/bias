import { useRouteListState } from '@/composables/useRouteListState'

function normalizeDiscussionSort(value) {
  const normalized = String(value || 'latest').trim()
  return normalized || 'latest'
}

function normalizeDiscussionFilter(value) {
  const normalized = String(value || 'all').trim()
  return normalized || 'all'
}

export function useDiscussionListRouteState({ route, router }) {
  return useRouteListState({
    route,
    router,
    resolveTarget: currentRoute => ({
      path: currentRoute.path,
    }),
    schema: {
      searchQuery: {
        queryKey: 'q',
        defaultValue: '',
        normalize: value => String(value || '').trim(),
      },
      sortBy: {
        queryKey: 'sort',
        defaultValue: 'latest',
        normalize: normalizeDiscussionSort,
        omitWhen: value => value === 'latest',
      },
      listFilter: {
        queryKey: 'filter',
        defaultValue: 'all',
        normalize: normalizeDiscussionFilter,
        omitWhen: value => value === 'all',
      },
    },
  })
}
