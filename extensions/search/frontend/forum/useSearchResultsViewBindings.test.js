import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createSearchResultsViewBindings } from './useSearchResultsViewBindings.js'

test('search results view bindings expose sidebar, hero and content props', () => {
  const bindings = createSearchResultsViewBindings({
    applySyntax() {},
    authStore: { isAuthenticated: true, canStartDiscussion: true },
    changePage() {},
    changeType() {},
    emptyStateText: ref('暂无结果'),
    filterCatalogLoadError: ref(''),
    filterItems: ref([{ value: 'all', label: '全部' }]),
    handleStartDiscussion() {},
    heroPillText: ref('全局搜索'),
    heroText: ref('支持在讨论、帖子和用户之间进行全局搜索。'),
    heroTitleText: ref('“关键词”'),
    idleStateText: ref('请输入关键词后再搜索。'),
    isEmpty: ref(false),
    loading: ref(false),
    loadingStateText: ref('搜索中...'),
    normalizedQuery: ref('关键词'),
    openSearchResult() {},
    page: ref(2),
    searchStatsItems: ref([{ key: 'discussions', count: 3 }]),
    searchType: ref('all'),
    syntaxItems: ref([{ key: 'tag', syntax: 'tag:公告', label: '限定标签' }]),
    totalPages: ref(4),
    visibleSearchSections: ref([{ key: 'discussions', label: '讨论', resultItems: [{ key: 'd-1' }] }]),
  })

  assert.deepEqual(bindings.sidebarBindings.value, {
    authStore: { isAuthenticated: true, canStartDiscussion: true },
    showStartDiscussionButton: true,
    filterItems: [{ value: 'all', label: '全部' }],
    searchType: 'all',
  })
  assert.equal(bindings.heroBindings.value.title, '“关键词”')
  assert.equal(bindings.heroBindings.value.variant, 'primary')
  assert.equal(bindings.contentBindings.value.page, 2)
  assert.deepEqual(bindings.contentBindings.value.visibleSearchSections, [
    { key: 'discussions', label: '讨论', resultItems: [{ key: 'd-1' }] }
  ])
})

test('search results view bindings expose stable events', () => {
  const calls = []
  const bindings = createSearchResultsViewBindings({
    applySyntax(syntax) {
      calls.push(['syntax', syntax])
    },
    authStore: { isAuthenticated: false, canStartDiscussion: false },
    changePage(page) {
      calls.push(['page', page])
    },
    changeType(type) {
      calls.push(['type', type])
    },
    emptyStateText: ref('暂无结果'),
    filterCatalogLoadError: ref('加载失败'),
    filterItems: ref([]),
    handleStartDiscussion() {
      calls.push('start')
    },
    heroPillText: ref('全局搜索'),
    heroText: ref('hero'),
    heroTitleText: ref('title'),
    idleStateText: ref('idle'),
    isEmpty: ref(true),
    loading: ref(false),
    loadingStateText: ref('loading'),
    normalizedQuery: ref(''),
    openSearchResult(path) {
      calls.push(['open', path])
    },
    page: ref(1),
    searchStatsItems: ref([]),
    searchType: ref('users'),
    syntaxItems: ref([]),
    totalPages: ref(1),
    visibleSearchSections: ref([]),
  })

  bindings.sidebarEvents.startDiscussion()
  bindings.sidebarEvents.changeType('posts')
  bindings.heroEvents.applySyntax('tag:公告')
  bindings.contentEvents.changePage(3)
  bindings.contentEvents.changeType('discussions')
  bindings.contentEvents.openSearchResult('/d/1')

  assert.deepEqual(calls, [
    'start',
    ['type', 'posts'],
    ['syntax', 'tag:公告'],
    ['page', 3],
    ['type', 'discussions'],
    ['open', '/d/1'],
  ])
})
