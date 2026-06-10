import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getDiscussionListTrackingDiff,
  resolveDiscussionMarkAllReadPatch,
  resolveDiscussionReadStatePatch,
} from './discussionListRealtime.js'

test('discussion list realtime helper computes track and untrack diffs', () => {
  const result = getDiscussionListTrackingDiff([1, 2, 3], [2, 4])

  assert.deepEqual(result, {
    trackIds: [1, 3],
    untrackIds: [4],
  })
})

test('discussion list realtime helper applies read state updates monotonically', () => {
  const patch = resolveDiscussionReadStatePatch({
    id: 7,
    last_read_post_number: 8,
    last_read_at: '2026-05-10T00:00:00Z',
    unread_count: 5,
    is_unread: true,
  }, {
    lastReadPostNumber: 6,
    lastReadAt: '2026-05-12T00:00:00Z',
    unreadCount: 2,
  })

  assert.equal(patch.last_read_post_number, 8)
  assert.equal(patch.last_read_at, '2026-05-12T00:00:00Z')
  assert.equal(patch.unread_count, 2)
  assert.equal(patch.is_unread, true)
})

test('discussion list realtime helper clears unread state for mark-all-read', () => {
  const patch = resolveDiscussionMarkAllReadPatch({
    id: 9,
    last_post_number: 18,
    last_read_post_number: 12,
    last_read_at: '2026-05-10T00:00:00Z',
    unread_count: 4,
    is_unread: true,
  }, '2026-05-16T00:00:00Z')

  assert.equal(patch.last_read_post_number, 18)
  assert.equal(patch.last_read_at, '2026-05-16T00:00:00Z')
  assert.equal(patch.unread_count, 0)
  assert.equal(patch.is_unread, false)
})
