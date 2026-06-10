import test from 'node:test'
import assert from 'node:assert/strict'
import { createSearchResultsLoadState } from './useSearchResultsLoadState.js'

function createHarness(overrides = {}) {
  const calls = []
  const refreshCalls = []
  const state = createSearchResultsLoadState({
    async fetchSearch({ page, query, searchType, sourceType, signal }) {
      calls.push(['fetch', { page, query, searchType, sourceType, aborted: signal.aborted }])
      return { total: 1, discussions: [{ id: 1, title: 'Loaded' }] }
    },
    getActiveSourceType() {
      return 'posts'
    },
    getErrorMessage(error) {
      return error.message || 'fallback'
    },
    getNormalizedQuery() {
      return 'bias'
    },
    getPage() {
      return 3
    },
    getSearchType() {
      return 'all'
    },
    listStateFactory({ load, reset }) {
      return {
        refresh: async options => {
          refreshCalls.push(options)
          if (options.mode === 'initial' && overrides.refreshError) {
            throw overrides.refreshError
          }
          return load()
        },
        loading: { value: false },
      }
    },
    onResponseLoaded(data) {
      calls.push(['loaded', data])
    },
    resetResults() {
      calls.push('reset')
    },
    setLoadError(message) {
      calls.push(['set-load-error', message])
    },
    ...overrides,
  })

  return {
    calls,
    refreshCalls,
    state,
  }
}

test('search results load state resets immediately when query is empty', async () => {
  const harness = createHarness({
    getNormalizedQuery() {
      return ''
    },
  })

  const result = await harness.state.loadSearchResults()

  assert.equal(result, null)
  assert.deepEqual(harness.calls, ['reset'])
})

test('search results load state forwards search params and clears load error after success', async () => {
  const harness = createHarness()

  const result = await harness.state.loadSearchResults()

  assert.deepEqual(result, { total: 1, discussions: [{ id: 1, title: 'Loaded' }] })
  assert.deepEqual(harness.calls, [
    ['fetch', { page: 3, query: 'bias', searchType: 'all', sourceType: 'posts', aborted: false }],
    ['loaded', { total: 1, discussions: [{ id: 1, title: 'Loaded' }] }],
    ['set-load-error', ''],
  ])
})

test('search results load state refresh wrapper resets data and stores error message on failure', async () => {
  const harness = createHarness({
    async fetchSearch() {
      throw new Error('network down')
    },
  })

  await harness.state.refreshResults()

  assert.deepEqual(harness.refreshCalls, [{
    mode: 'initial',
    forceLoading: true,
  }])
  assert.deepEqual(harness.calls, [
    ['set-load-error', 'network down'],
    'reset',
  ])
})
