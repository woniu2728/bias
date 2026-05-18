import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { createDiscussionListViewBindings } from './useDiscussionListViewBindings.js'

test('discussion list view bindings expose sidebar and content bindings', () => {
  const bindings = createDiscussionListViewBindings({
    authStore: { isAuthenticated: true },
    buildDiscussionPath: value => `/d/${value.id || value}`,
    buildTrackedDiscussionPath: value => ({ path: `/d/${value.id || value}`, query: { returnDiscussion: value.id || value } }),
    buildTagPath: value => `/t/${value.slug || value}`,
    buildUserPath: value => `/u/${value.id || value}`,
    changeSortBy() {},
    currentTag: ref({ name: '公告' }),
    discussions: ref([{ id: 1 }]),
    emptyStateText: ref('empty'),
    formatRelativeTime: value => value,
    getSidebarTagStyle: () => ({}),
    getUserAvatarColor: () => '#000',
    getUserDisplayName: () => 'alice',
    getUserInitial: () => 'A',
    handleStartDiscussion() {},
    hasMore: ref(true),
    hasSidebarTagNavigation: ref(true),
    isFollowingPage: ref(false),
    isOwnProfilePage: ref(false),
    isSidebarTagActive: () => false,
    isTagsPage: ref(false),
    loading: ref(false),
    loadingMore: ref(false),
    loadingStateText: ref('loading'),
    loadMore() {},
    markingAllRead: ref(false),
    markAllAsRead() {},
    refreshDiscussionList() {},
    refreshing: ref(false),
    showMoreTagsLink: ref(true),
    sidebarFilterItems: ref([{ key: 'all' }]),
    sidebarPrimaryTagItems: ref([{ key: '公告' }]),
    sidebarSecondaryTagItems: ref([]),
    sortBy: ref('latest'),
    sortOptions: ref([{ code: 'latest' }]),
    startDiscussionButtonStyle: ref({ tone: 'primary' }),
  })

  assert.equal(bindings.sidebarBindings.value.currentTag.name, '公告')
  assert.deepEqual(bindings.contentBindings.value.discussions, [{ id: 1 }])
  assert.equal(bindings.contentBindings.value.sortBy, 'latest')
  assert.deepEqual(bindings.contentBindings.value.buildDiscussionPath({ id: 1 }), {
    path: '/d/1',
    query: { returnDiscussion: 1 },
  })
  assert.equal('searchQuery' in bindings.contentBindings.value, false)
  assert.equal('filterOptions' in bindings.contentBindings.value, false)
  assert.equal(typeof bindings.sidebarEvents.startDiscussion, 'function')
  assert.equal(typeof bindings.contentEvents.refresh, 'function')
  assert.equal('changeFilter' in bindings.contentEvents, false)
  assert.equal('changeSearch' in bindings.contentEvents, false)
})
