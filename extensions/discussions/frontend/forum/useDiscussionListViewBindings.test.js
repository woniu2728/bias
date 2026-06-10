import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListViewBindings } from './useDiscussionListViewBindings.js'

test('discussion list view bindings expose sidebar and content bindings', () => {
  const bindings = createDiscussionListViewBindings({
    authStore: { isAuthenticated: true },
    buildDiscussionPath: value => `/d/${value.id || value}`,
    buildTrackedDiscussionPath: value => ({ path: `/d/${value.id || value}`, query: { returnDiscussion: value.id || value } }),
    buildUserPath: value => `/u/${value.id || value}`,
    changeSortBy() {},
    contextSubject: ref({ name: '公告' }),
    discussionListContexts: ref([{ key: 'tag-filter' }]),
    discussions: ref([{ id: 1 }]),
    emptyStateText: ref('empty'),
    formatRelativeTime: value => value,
    getUserAvatarColor: () => '#000',
    getUserDisplayName: () => 'alice',
    getUserInitial: () => 'A',
    handleStartDiscussion() {},
    hasMore: ref(true),
    isFollowingPage: ref(false),
    isOwnProfilePage: ref(false),
    isTagsPage: ref(false),
    listFilter: ref('all'),
    loading: ref(false),
    loadingMore: ref(false),
    loadingStateText: ref('loading'),
    loadMore() {},
    markingAllRead: ref(false),
    markAllAsRead() {},
    refreshDiscussionList() {},
    refreshing: ref(false),
    sidebarExtensionSections: ref([{ key: 'tags', component: 'TagsSection' }]),
    sidebarFilterItems: ref([{ key: 'all' }]),
    sortBy: ref('latest'),
    sortOptions: ref([{ code: 'latest' }]),
    startDiscussionButtonStyle: ref({ tone: 'primary' }),
  })

  assert.equal(bindings.sidebarBindings.value.contextSubject.name, '公告')
  assert.deepEqual(bindings.contentBindings.value.discussionListContexts, [{ key: 'tag-filter' }])
  assert.deepEqual(bindings.contentBindings.value.discussions, [{ id: 1 }])
  assert.deepEqual(bindings.sidebarBindings.value.sidebarExtensionSections, [{ key: 'tags', component: 'TagsSection' }])
  assert.equal(bindings.contentBindings.value.sortBy, 'latest')
  assert.equal(bindings.contentBindings.value.listFilter, 'all')
  assert.equal(bindings.contentBindings.value.emptyStateText, 'empty')
  assert.equal(bindings.contentBindings.value.loadingStateText, 'loading')
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
