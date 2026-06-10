import {
  api,
  setActivePinia,
  createPinia,
  ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'
import { registerDiscussionListRequest } from '@bias/discussions'
import { useDiscussionListResourceState } from './useDiscussionListResourceState.js'

function uniqueKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

test('discussion list resource state loads extension resources and applies request params', async () => {
  setActivePinia(createPinia())
  const requests = []
  const originalGet = api.get
  const requestKey = uniqueKey('resource-request')

  api.get = async (url, config = {}) => {
    requests.push({ url, params: config.params || {} })
    if (url === '/discussions/') {
      return {
        data: [{ id: 10, title: 'Tagged discussion', tags: [] }],
        total: 1,
        available_sorts: [{ code: 'latest' }],
        available_filters: [{ code: 'all' }],
      }
    }
    return {}
  }

  registerDiscussionListRequest({
    key: requestKey,
    order: 10,
    surfaces: ['discussion-list-request'],
    resolve: () => ({
      apply({ params }) {
        return {
          ...params,
          tag: 'announcements',
        }
      },
    }),
  })

  try {
    const state = useDiscussionListResourceState({
      discussionListContexts: ref([{
        key: 'tag-filter',
        currentTagSlug: 'announcements',
        async loadResources({ resourceStore }) {
          resourceStore.upsertMany('tags', [
            { id: 1, slug: 'announcements', name: 'Announcements', children: [] },
            { id: 2, slug: 'general', name: 'General', children: [] },
          ])
          const subject = resourceStore.upsert('tags', { id: 1, slug: 'announcements', name: 'Announcements' })
          return {
            contextData: {
              currentTagSlug: 'announcements',
              flatTags: [
                { id: 1, slug: 'announcements' },
                { id: 2, slug: 'general' },
              ],
            },
            subject,
            subjectKey: 'announcements',
          }
        },
      }]),
      isFollowingPage: ref(false),
      listFilter: ref('all'),
      primaryDiscussionListContext: ref({ subjectKey: 'announcements' }),
      route: { name: 'tag-detail', params: { slug: 'announcements' }, fullPath: '/t/announcements' },
      searchQuery: ref(''),
      sortBy: ref('latest'),
    })

    await state.loadInitialResources()

    assert.equal(state.contextSubject.value.slug, 'announcements')
    assert.deepEqual(state.discussionListContextData.value['tag-filter'].flatTags.map(tag => tag.slug), ['announcements', 'general'])
    assert.deepEqual(state.discussions.value.map(discussion => discussion.id), [10])
    assert.equal(requests[0].url, '/discussions/')
    assert.equal(requests[0].params.tag, 'announcements')
    assert.equal(requests[0].params.sort, 'latest')
  } finally {
    api.get = originalGet
  }
})
