import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionHeroState } from './useDiscussionHeroState.js'

test('discussion hero state resolves meta items and review banner', () => {
  const state = createDiscussionHeroState({
    authStore: { user: { id: 1, is_staff: false } },
    canEditDiscussion: ref(true),
    discussion: ref({ id: 12, title: '讨论' }),
    getHeroMeta: () => [{ key: 'author', text: 'alice' }],
    getReviewBanner: () => ({ title: '待审核', message: '请处理' }),
  })

  assert.deepEqual(state.heroMetaItems.value, [{ key: 'author', text: 'alice' }])
  assert.deepEqual(state.discussionReviewBanner.value, { title: '待审核', message: '请处理' })
})
