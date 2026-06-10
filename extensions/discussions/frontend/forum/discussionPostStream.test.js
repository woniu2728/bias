import test from 'node:test'
import assert from 'node:assert/strict'
import { shouldAppendRealtimePostImmediately } from './discussionPostStream.js'

test('realtime post appends immediately when reader is near the loaded bottom', () => {
  const result = shouldAppendRealtimePostImmediately({
    currentVisiblePostNumber: 19,
    lastLoadedPostNumber: 20,
    postNumber: 21,
  })

  assert.equal(result, true)
})

test('realtime post stays pending when reader is away from the loaded bottom', () => {
  const result = shouldAppendRealtimePostImmediately({
    currentVisiblePostNumber: 8,
    lastLoadedPostNumber: 20,
    postNumber: 21,
  })

  assert.equal(result, false)
})

test('realtime post still merges immediately when the post is already present in the window', () => {
  const result = shouldAppendRealtimePostImmediately({
    currentVisiblePostNumber: 8,
    lastLoadedPostNumber: 20,
    postIds: [101, 102, 103],
    postId: 102,
    postNumber: 14,
  })

  assert.equal(result, true)
})
