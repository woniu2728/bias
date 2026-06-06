import test from 'node:test'
import assert from 'node:assert/strict'
import { createNotificationLoadState } from './useNotificationLoadState.js'

function createHarness(overrides = {}) {
  const calls = []
  const state = createNotificationLoadState({
    async fetchNotifications(params) {
      calls.push(['fetchNotifications', params])
      return overrides.response || {
        total: 42,
        limit: 20,
      }
    },
    getActiveType() {
      return overrides.activeType ?? 'mention'
    },
    getCurrentPage() {
      return overrides.currentPage ?? 3
    },
    getNotifications() {
      return overrides.notifications ?? [{ id: 1 }, { id: 2 }]
    },
    getUnreadOnly() {
      return overrides.unreadOnly ?? true
    },
    listStateFactory({ load }) {
      return {
        load,
        loadError: { value: '' },
        loading: { value: false },
        refresh: async payload => {
          calls.push(['refresh', payload])
          return load()
        },
      }
    },
  })

  return {
    calls,
    state,
  }
}

test('notification load state forwards current route filters to fetchNotifications', async () => {
  const harness = createHarness()

  const result = await harness.state.loadNotifications()

  assert.deepEqual(result, {
    total: 42,
    limit: 20,
  })
  assert.deepEqual(harness.calls, [[
    'fetchNotifications',
    { page: 3, type: 'mention', is_read: false },
  ]])
  assert.equal(harness.state.totalCount.value, 42)
  assert.equal(harness.state.totalPages.value, 3)
})

test('notification load state omits optional filters when inactive', async () => {
  const harness = createHarness({
    activeType: '',
    unreadOnly: false,
    response: {
      total: 2,
      limit: 20,
    },
  })

  await harness.state.loadNotifications()

  assert.deepEqual(harness.calls, [[
    'fetchNotifications',
    { page: 3 },
  ]])
  assert.equal(harness.state.totalCount.value, 2)
  assert.equal(harness.state.totalPages.value, 1)
})
