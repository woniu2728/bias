import test from 'node:test'
import assert from 'node:assert/strict'
import { createTagsLoadState } from './useTagsLoadState.js'

function createHarness(overrides = {}) {
  const calls = []
  const refreshCalls = []
  const state = createTagsLoadState({
    async fetchTags() {
      calls.push('fetch-tags')
      return [{ id: 1 }]
    },
    getErrorMessage(error) {
      return error.message || 'fallback'
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
          return load()
        },
        loading: { value: false },
        loadingMore: { value: false },
        refreshing: { value: false },
      }
    },
    onTagsLoaded(response) {
      calls.push(['loaded', response])
    },
    resetTags() {
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

test('tags load state loads tags through initial wrapper', async () => {
  const harness = createHarness()

  await harness.state.loadInitialTags()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'initial',
    forceLoading: true,
  }])
  assert.deepEqual(harness.calls, [
    'fetch-tags',
    ['loaded', [{ id: 1 }]],
  ])
})

test('tags load state resets resources when initial load fails', async () => {
  const harness = createHarness({
    initialError: new Error('bootstrap failed'),
  })

  await harness.state.loadInitialTags()

  assert.deepEqual(harness.calls, ['reset'])
})

test('tags load state uses refresh wrapper for follow-up refresh', async () => {
  const harness = createHarness()

  await harness.state.refreshTags()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'refresh',
  }])
  assert.deepEqual(harness.calls, [
    'fetch-tags',
    ['loaded', [{ id: 1 }]],
  ])
})
