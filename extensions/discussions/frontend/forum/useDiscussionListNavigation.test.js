import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListNavigation } from './useDiscussionListNavigation.js'

test('discussion list navigation resolves sidebar filters and page state copy', () => {
  const state = createDiscussionListNavigation({
    authStore: { user: { id: 7 } },
    contextSubject: ref({ key: 'announcements', color: '#112233' }),
    contextSubjectKey: ref('announcements'),
    filterOptions: ref([
      { code: 'all', sidebar_visible: true },
      { code: 'following', sidebar_visible: true, requires_authenticated_user: true },
    ]),
    getDefaultFilterLabelText: (code) => `${code}-fallback`,
    getDiscussionEmptyState: () => ({ text: 'empty-copy' }),
    getDiscussionForumNavItems: () => [
      { key: 'home', label: '全部讨论', icon: 'far fa-comments' },
      { key: 'following', label: '关注中', icon: 'fas fa-bell' },
    ],
    discussionListContextData: ref({
      tags: {
        currentTagSlug: 'announcements',
        flatTags: [
          { id: 1, slug: 'announcements', color: '#112233', children: [] },
          { id: 2, slug: 'general', color: '#334455', children: [] },
        ],
      },
    }),
    getDiscussionSidebarSections: ({ discussionListContextData }) => [
      {
        key: 'tags',
        component: 'TagsSection',
        componentProps: {
          currentTagSlug: discussionListContextData.tags.currentTagSlug,
          count: discussionListContextData.tags.flatTags.length,
        },
      },
    ],
    getDiscussionLoadingState: () => ({ text: 'loading-copy' }),
    isFollowingPage: ref(false),
    listFilter: ref('all'),
    route: { name: 'home', params: {} },
  })

  assert.equal(state.isTagsPage.value, false)
  assert.equal(state.isAllDiscussionsPage.value, false)
  assert.equal(state.emptyStateText.value, 'empty-copy')
  assert.equal(state.loadingStateText.value, 'loading-copy')
  assert.deepEqual(state.startDiscussionButtonStyle.value, {
    '--tag-button-bg': '#112233',
    '--tag-button-text': '#ffffff',
  })
  assert.equal(state.sidebarFilterItems.value[0].label, '全部讨论')
  assert.equal(state.sidebarFilterItems.value[1].label, '关注中')
  assert.deepEqual(state.sidebarExtensionSections.value, [
    {
      key: 'tags',
      component: 'TagsSection',
      componentProps: {
        currentTagSlug: 'announcements',
        count: 2,
      },
    },
  ])
})

test('discussion list navigation hides auth-only filters and falls back to default copy', () => {
  const state = createDiscussionListNavigation({
    authStore: { user: null },
    contextSubject: ref(null),
    contextSubjectKey: ref(''),
    discussionListContextData: ref({}),
    filterOptions: ref([{ code: 'unread', sidebar_visible: true, requires_authenticated_user: true }]),
    getDefaultFilterLabelText: (code) => `${code}-fallback`,
    getDiscussionEmptyState: () => null,
    getDiscussionForumNavItems: () => [],
    getDiscussionLoadingState: () => null,
    isFollowingPage: ref(false),
    listFilter: ref('all'),
    route: { name: 'tags', params: {} },
  })

  assert.equal(state.isTagsPage.value, true)
  assert.equal(state.isAllDiscussionsPage.value, false)
  assert.equal(state.emptyStateText.value, '暂无讨论。')
  assert.equal(state.loadingStateText.value, '正在加载讨论...')
  assert.deepEqual(state.sidebarFilterItems.value, [])
  assert.deepEqual(state.sidebarExtensionSections.value, [])
})
