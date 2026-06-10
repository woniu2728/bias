import test from 'node:test'
import assert from 'node:assert/strict'
import { useSearchResultsRouteActions } from './useSearchResultsRouteActions.js'

test('search results route actions skip navigation when search type is unchanged after normalization', async () => {
  const calls = []
  const actions = useSearchResultsRouteActions({
    appendFilter: query => query,
    normalizedQuery: { value: 'bias' },
    routePagination: {
      async changePage(page) {
        calls.push(['changePage', page])
        return true
      },
      async resetPage(payload) {
        calls.push(['resetPage', payload])
      },
    },
    searchSources: [
      { type: 'discussions' },
      { type: 'posts' },
    ],
    searchType: { value: 'all' },
  })

  const changed = await actions.changeType('unknown')

  assert.equal(changed, false)
  assert.deepEqual(calls, [])
})

test('search results route actions reset page for valid type changes and syntax filters', async () => {
  const calls = []
  const actions = useSearchResultsRouteActions({
    appendFilter(query, syntax) {
      return `${query} ${syntax}`.trim()
    },
    normalizedQuery: { value: 'author:alice' },
    routePagination: {
      async changePage(page) {
        calls.push(['changePage', page])
        return page !== 1
      },
      async resetPage(payload) {
        calls.push(['resetPage', payload])
      },
    },
    searchSources: [
      { routeType: 'users', type: 'users' },
      { type: 'posts' },
    ],
    searchType: { value: 'all' },
  })

  const changedType = await actions.changeType('users')
  const changedSyntax = await actions.applySyntax('status:open')
  const changedPage = await actions.changePage(3)

  assert.equal(changedType, true)
  assert.equal(changedSyntax, true)
  assert.equal(changedPage, true)
  assert.deepEqual(calls, [
    ['resetPage', { searchType: 'users' }],
    ['resetPage', { normalizedQuery: 'author:alice status:open' }],
    ['changePage', 3],
  ])
})

test('search results route actions skip syntax navigation when query stays unchanged', async () => {
  const calls = []
  const actions = useSearchResultsRouteActions({
    appendFilter(query) {
      return query
    },
    normalizedQuery: { value: 'tag:news' },
    routePagination: {
      async changePage(page) {
        calls.push(['changePage', page])
        return false
      },
      async resetPage(payload) {
        calls.push(['resetPage', payload])
      },
    },
    searchSources: [],
    searchType: { value: 'posts' },
  })

  const changed = await actions.applySyntax('status:open')

  assert.equal(changed, false)
  assert.deepEqual(calls, [])
})
