import { computed } from '@bias/core'

function normalizeNear(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return null
  return Math.floor(parsed)
}

export function useDiscussionNearRouteState({ route, router }) {
  const near = computed(() => normalizeNear(route.query.near))

  async function replaceRouteNear(number) {
    const normalized = normalizeNear(number)
    if (!normalized || near.value === normalized) {
      return false
    }

    await router.replace({
      path: route.path,
      query: {
        ...route.query,
        near: String(normalized),
      },
    })

    return true
  }

  function replaceAddressBarNear(number) {
    if (typeof window === 'undefined') return false

    const normalized = normalizeNear(number)
    if (!normalized) return false

    const url = new URL(window.location.href)
    if (url.searchParams.get('near') === String(normalized)) {
      return false
    }

    url.searchParams.set('near', String(normalized))
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
    return true
  }

  return {
    near,
    normalizeNear,
    replaceAddressBarNear,
    replaceRouteNear,
  }
}
