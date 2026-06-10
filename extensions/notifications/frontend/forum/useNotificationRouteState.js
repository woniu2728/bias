import { useRouteListState } from '@bias/core'

function normalizePage(value) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}

function normalizeType(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeViewMode(value) {
  return String(value || '').trim() === 'grouped' ? 'grouped' : 'timeline'
}

export function useNotificationRouteState({ route, router }) {
  return useRouteListState({
    route,
    router,
    resolveTarget: () => ({
      name: 'notifications',
    }),
    schema: {
      activeType: {
        queryKey: 'type',
        defaultValue: '',
        normalize: normalizeType,
      },
      currentPage: {
        queryKey: 'page',
        defaultValue: 1,
        normalize: normalizePage,
        serialize: value => String(value),
        omitWhen: value => value <= 1,
      },
      unreadOnly: {
        queryKey: 'state',
        defaultValue: false,
        normalize: value => String(value || '').trim() === 'unread',
        serialize: value => (value ? 'unread' : ''),
        omitWhen: value => !value,
      },
      viewMode: {
        queryKey: 'view',
        defaultValue: 'timeline',
        normalize: normalizeViewMode,
        omitWhen: value => value === 'timeline',
      },
    },
  })
}
