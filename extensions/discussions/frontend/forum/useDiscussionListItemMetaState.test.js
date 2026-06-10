import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListItemMetaState } from './useDiscussionListItemMetaState.js'

test('discussion list item meta state resolves badges, feedback note, and copy', () => {
  const discussion = ref({
    created_at: '2026-05-17T00:00:00Z',
    last_posted_at: '2026-05-18T00:00:00Z',
  })

  const state = createDiscussionListItemMetaState({
    discussion,
    formatRelativeTime: (value) => `relative:${value}`,
    getDiscussionFeedbackNote: () => ({ text: 'feedback-note-copy' }),
    getDiscussionBadges: () => [{ key: 'locked', label: '已锁定' }],
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
  })

  assert.deepEqual(state.discussionStateBadges.value, [{ key: 'locked', label: '已锁定' }])
  assert.deepEqual(state.feedbackNote.value, { text: 'feedback-note-copy' })
  assert.equal(state.createdAtText.value, 'discussion-list-item-created-at-copy')
  assert.equal(state.lastPostedAtText.value, 'discussion-list-item-last-posted-at-copy')
})

test('discussion list item meta state falls back to default relative time copy', () => {
  const discussion = ref({
    created_at: '2026-05-17T00:00:00Z',
    last_posted_at: '2026-05-18T00:00:00Z',
  })

  const state = createDiscussionListItemMetaState({
    discussion,
    formatRelativeTime: (value) => `relative:${value}`,
    getDiscussionFeedbackNote: () => null,
    getDiscussionBadges: () => [],
    getText: () => null,
  })

  assert.deepEqual(state.discussionStateBadges.value, [])
  assert.equal(state.feedbackNote.value, null)
  assert.equal(state.createdAtText.value, '发起于 relative:2026-05-17T00:00:00Z')
  assert.equal(state.lastPostedAtText.value, '最后回复 relative:2026-05-18T00:00:00Z')
})
