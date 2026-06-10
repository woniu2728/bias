import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { useDiscussionSidebarScrubber } from './useDiscussionSidebarScrubber.js'

test('discussion sidebar scrubber derives visible range text and unread indicator', () => {
  const state = useDiscussionSidebarScrubber({
    currentVisiblePostNumber: ref(12),
    currentVisiblePostProgress: ref(12.4),
    jumpToPost: () => {},
    maxPostNumber: ref(40),
    posts: ref([
      { id: 1, number: 10, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, number: 12, created_at: '2026-01-02T00:00:00Z' },
      { id: 3, number: 15, created_at: '2026-01-03T00:00:00Z' },
    ]),
    unreadCount: ref(5),
    unreadStartPostNumber: ref(20),
  })

  assert.equal(state.scrubberPositionText.value, '12 / 40')
  assert.equal(typeof state.scrubberDescription.value, 'string')
  assert.equal(state.unreadTopPercent.value > 0, true)
  assert.equal(state.unreadHeightPercent.value > 0, true)
})
