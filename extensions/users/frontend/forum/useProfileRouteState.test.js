import test from 'node:test'
import assert from 'node:assert/strict'
import { useProfileRouteState } from './useProfileRouteState.js'

test('profile route state defaults to discussions tab and omits default query', () => {
  const routeState = useProfileRouteState({
    route: {
      path: '/u/7',
      query: {},
    },
    router: {
      push: async () => {},
      replace: async () => {},
    },
  })

  assert.equal(routeState.activeTab.value, 'discussions')
  assert.deepEqual(routeState.buildQuery(), {})
})

test('profile route state preserves explicit tab and current profile path', async () => {
  const pushes = []
  const routeState = useProfileRouteState({
    route: {
      path: '/profile',
      query: {},
    },
    router: {
      push: async location => {
        pushes.push(location)
      },
      replace: async () => {},
    },
  })

  await routeState.push({
    activeTab: 'security',
  })

  assert.deepEqual(pushes, [{
    path: '/profile',
    query: {
      tab: 'security',
    },
  }])
})
