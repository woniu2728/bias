import test from 'node:test'
import assert from 'node:assert/strict'
import { useDiscussionNearRouteState } from './useDiscussionNearRouteState.js'

test('discussion near route state normalizes invalid values to null', () => {
  const routeState = useDiscussionNearRouteState({
    route: {
      path: '/d/12',
      query: {
        near: '0',
      },
    },
    router: {
      replace: async () => {},
    },
  })

  assert.equal(routeState.near.value, null)
  assert.equal(routeState.normalizeNear('18.8'), 18)
  assert.equal(routeState.normalizeNear(''), null)
})

test('discussion near route state preserves existing query when replacing route near', async () => {
  const replaces = []
  const routeState = useDiscussionNearRouteState({
    route: {
      path: '/d/12',
      query: {
        foo: 'bar',
        near: '3',
      },
    },
    router: {
      replace: async location => {
        replaces.push(location)
      },
    },
  })

  const changed = await routeState.replaceRouteNear(8)

  assert.equal(changed, true)
  assert.deepEqual(replaces, [{
    path: '/d/12',
    query: {
      foo: 'bar',
      near: '8',
    },
  }])
})

test('discussion near route state updates address bar near without router navigation', () => {
  const previousWindow = globalThis.window
  const replaceCalls = []
  globalThis.window = {
    location: {
      href: 'https://example.com/d/12?foo=bar&near=3#reply',
    },
    history: {
      state: { from: 'test' },
      replaceState: (...args) => {
        replaceCalls.push(args)
      },
    },
  }

  try {
    const routeState = useDiscussionNearRouteState({
      route: {
        path: '/d/12',
        query: {
          foo: 'bar',
          near: '3',
        },
      },
      router: {
        replace: async () => {},
      },
    })

    const changed = routeState.replaceAddressBarNear(9)

    assert.equal(changed, true)
    assert.deepEqual(replaceCalls, [[
      { from: 'test' },
      '',
      '/d/12?foo=bar&near=9#reply',
    ]])
  } finally {
    globalThis.window = previousWindow
  }
})
