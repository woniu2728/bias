import { nextTick, ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfileMetaState } from './useProfileMetaState.js'

test('profile meta state resolves badges and page state copy', () => {
  const state = createProfileMetaState({
    authStore: { user: { id: 7 } },
    forumStore: { setPageMeta() {} },
    getBadges: () => [{ key: 'founder' }],
    getPageStateBlock: ({ surface }) => ({ text: `${surface}-copy` }),
    loading: ref(true),
    user: ref({ id: 7, username: 'alice' }),
  })

  assert.deepEqual(state.userBadges.value, [{ key: 'founder' }])
  assert.equal(state.loadingStateText.value, 'profile-loading-copy')
  assert.equal(state.missingStateText.value, 'profile-not-found-copy')
})

test('profile meta state syncs resolved page meta when user changes', async () => {
  const calls = []
  const user = ref({
    id: 7,
    username: 'alice',
    display_name: 'Alice',
    bio: '',
    discussion_count: 3,
    comment_count: 5,
  })

  createProfileMetaState({
    authStore: { user: { id: 7 } },
    forumStore: {
      setPageMeta(payload) {
        calls.push(payload)
      },
    },
    loading: ref(false),
    user,
  })

  user.value = {
    id: 8,
    username: 'bob',
    display_name: 'Bob',
    bio: ' Hello  world ',
    discussion_count: 1,
    comment_count: 2,
  }

  await nextTick()

  assert.deepEqual(calls, [
    {
      title: 'Alice 的主页',
      description: 'Alice 在论坛发布了 3 个讨论和 5 条回复。',
      canonicalUrl: '/u/alice',
    },
    {
      title: 'Bob 的主页',
      description: 'Hello world',
      canonicalUrl: '/u/bob',
    },
  ])
})
