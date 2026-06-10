import test from 'node:test'
import assert from 'node:assert/strict'
import { createSearchResultsResourceState } from './useSearchResultsResourceState.js'

function createResourceStore() {
  const buckets = {
    discussions: {},
    posts: {},
    users: {},
  }

  return {
    list(type, ids = []) {
      return ids.map(id => buckets[type]?.[String(id)]).filter(Boolean)
    },
    upsertMany(type, items = []) {
      return items.map(item => {
        const normalized = { ...item, id: Number(item.id) }
        buckets[type][String(normalized.id)] = normalized
        return normalized
      })
    },
  }
}

test('search results resource state stores totals and resolves tracked discussion ids from results', () => {
  const state = createSearchResultsResourceState({
    resourceStore: createResourceStore(),
    searchSources: [],
  })

  state.applySearchResponse({
    total: 22,
    discussions: [{ id: 12, title: 'Discussion A' }],
    posts: [{ id: 88, discussion_id: 12, content_html: '<p>Reply</p>' }],
    users: [{ id: 5, username: 'alice' }],
  })

  assert.equal(state.total.value, 22)
  assert.equal(state.discussionTotal.value, 1)
  assert.equal(state.postTotal.value, 1)
  assert.equal(state.userTotal.value, 1)
  assert.equal(state.totalPages.value, 2)
  assert.deepEqual(state.trackedDiscussionIds.value, [12, 12])
  assert.equal(state.isEmpty.value, false)
})

test('search results resource state builds visible grouped sections from registered search sources', () => {
  const state = createSearchResultsResourceState({
    resourceStore: createResourceStore(),
    searchSources: [
      {
        type: 'discussions',
        label: '讨论',
        buildResultItems(items, { query }) {
          return items.map(item => ({
            key: `discussion-${item.id}`,
            titleHtml: `${query}:${item.title}`,
          }))
        },
      },
      {
        routeType: 'users',
        type: 'users',
        label: '用户',
        buildResultItems(items) {
          return items.map(item => ({
            key: `user-${item.id}`,
            titleHtml: item.username,
          }))
        },
      },
    ],
  })

  state.applySearchResponse({
    discussion_total: 3,
    discussions: [{ id: 12, title: 'Discussion A' }],
    users: [{ id: 5, username: 'alice' }],
  })

  assert.deepEqual(state.buildSearchSourceSections({
    normalizedQuery: 'bias',
    searchType: 'all',
  }), [
    {
      type: 'discussions',
      label: '讨论',
      buildResultItems: state.buildSearchSourceSections({
        normalizedQuery: 'bias',
        searchType: 'all',
      })[0].buildResultItems,
      key: 'discussions',
      resultItems: [{ key: 'discussion-12', titleHtml: 'bias:Discussion A' }],
      showMore: true,
      visible: true,
    },
    {
      routeType: 'users',
      type: 'users',
      label: '用户',
      buildResultItems: state.buildSearchSourceSections({
        normalizedQuery: 'bias',
        searchType: 'all',
      })[1].buildResultItems,
      key: 'users',
      resultItems: [{ key: 'user-5', titleHtml: 'alice' }],
      showMore: false,
      visible: true,
    },
  ])
})

test('search results resource state resets totals and ids', () => {
  const state = createSearchResultsResourceState({
    resourceStore: createResourceStore(),
    searchSources: [],
  })

  state.applySearchResponse({
    total: 8,
    discussions: [{ id: 3, title: 'Discussion B' }],
  })
  state.resetResults()

  assert.equal(state.total.value, 0)
  assert.equal(state.discussionTotal.value, 0)
  assert.equal(state.postTotal.value, 0)
  assert.equal(state.userTotal.value, 0)
  assert.deepEqual(state.discussionIds.value, [])
  assert.deepEqual(state.postIds.value, [])
  assert.deepEqual(state.userIds.value, [])
  assert.equal(state.isEmpty.value, true)
})
