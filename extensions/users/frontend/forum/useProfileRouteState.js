import { useRouteListState } from '@bias/core'

function normalizeProfileTab(value) {
  const normalized = String(value || 'discussions').trim()
  return normalized || 'discussions'
}

export function useProfileRouteState({ route, router }) {
  return useRouteListState({
    route,
    router,
    resolveTarget: currentRoute => ({
      path: currentRoute.path,
    }),
    schema: {
      activeTab: {
        queryKey: 'tab',
        defaultValue: 'discussions',
        normalize: normalizeProfileTab,
        omitWhen: value => value === 'discussions',
      },
    },
  })
}
