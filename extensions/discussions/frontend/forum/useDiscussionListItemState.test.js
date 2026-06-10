import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListItemState } from './useDiscussionListItemState.js'

test('discussion list item state resolves discussion badges', () => {
  const state = createDiscussionListItemState({
    discussion: ref({ id: 1 }),
    getBadges: ({ discussion, surface }) => [
      { key: `${surface}-${discussion.id}`, label: 'badge-copy' },
    ],
  })

  assert.deepEqual(state.discussionBadges.value, [
    { key: 'discussion-list-item-1', label: 'badge-copy' },
  ])
})

test('discussion list item state falls back to empty badge list', () => {
  const state = createDiscussionListItemState({
    discussion: ref({ id: 2 }),
    getBadges: () => [],
  })

  assert.deepEqual(state.discussionBadges.value, [])
})

test('discussion list item state exposes pending new reply markers', () => {
  const state = createDiscussionListItemState({
    discussion: ref({ id: 3, has_new_replies: true, new_reply_count: 2 }),
    getBadges: () => [],
  })

  assert.equal(state.hasNewReplies.value, true)
  assert.equal(state.newReplyCount.value, 2)
})
