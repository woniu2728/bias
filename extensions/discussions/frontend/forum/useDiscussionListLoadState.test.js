import test from 'node:test'
import assert from 'node:assert/strict'
import { createDiscussionListLoadState } from './discussionListLoadState.shared.js'

function createHarness(overrides = {}) {
  const calls = []
  const refreshCalls = []
  const state = createDiscussionListLoadState({
    getErrorMessage(error) {
      return error.message || 'fallback'
    },
    getText({ surface, actionType }) {
      if (surface === 'discussion-list-action-failed-title') {
        return { text: `失败:${actionType}` }
      }
      if (surface === 'discussion-list-action-retry-message') {
        return { text: '请稍后再试' }
      }
      return null
    },
    listStateFactory({ load, reset: _reset }) {
      return {
        refresh: async options => {
          refreshCalls.push(options)
          if (options.mode === 'initial' && overrides.initialError) {
            throw overrides.initialError
          }
          if (options.mode === 'refresh' && overrides.refreshError) {
            throw overrides.refreshError
          }
          if (options.mode === 'append' && overrides.appendError) {
            throw overrides.appendError
          }
          return load({ mode: options.mode })
        },
        loading: { value: false },
        loadingMore: { value: false },
        refreshing: { value: false },
      }
    },
    async loadInitialResources() {
      calls.push('load-initial')
    },
    async loadMoreDiscussions() {
      calls.push('load-more')
    },
    modalStore: {
      async alert(payload) {
        calls.push(['alert', payload])
      },
    },
    async refreshDiscussions() {
      calls.push('refresh-discussions')
    },
    resetResources() {
      calls.push('reset')
    },
    ...overrides,
  })

  return {
    calls,
    refreshCalls,
    state,
  }
}

test('discussion list load state routes initial/refresh/append modes to resource loaders', async () => {
  const harness = createHarness()

  await harness.state.listState.refresh({ mode: 'initial', forceLoading: true })
  await harness.state.listState.refresh({ mode: 'refresh' })
  await harness.state.listState.refresh({ mode: 'append' })

  assert.deepEqual(harness.calls, [
    'load-initial',
    'refresh-discussions',
    'load-more',
  ])
})

test('discussion list load state resets resources when initial refresh wrapper fails', async () => {
  const harness = createHarness({
    initialError: new Error('bootstrap failed'),
  })

  await harness.state.refreshPageData()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'initial',
    forceLoading: true,
  }])
  assert.deepEqual(harness.calls, ['reset'])
})

test('discussion list load state shows alert when refresh wrapper fails', async () => {
  const harness = createHarness({
    refreshError: new Error('network down'),
  })

  await harness.state.refreshDiscussionList()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'refresh',
  }])
  assert.deepEqual(harness.calls, [[
    'alert',
    {
      title: '失败:refresh',
      message: 'network down',
      tone: 'danger',
    },
  ]])
})

test('discussion list load state shows alert when append wrapper fails', async () => {
  const harness = createHarness({
    appendError: new Error('append failed'),
  })

  await harness.state.loadMore()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'append',
  }])
  assert.deepEqual(harness.calls, [[
    'alert',
    {
      title: '失败:load-more',
      message: 'append failed',
      tone: 'danger',
    },
  ]])
})
