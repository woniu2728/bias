import test from 'node:test'
import assert from 'node:assert/strict'
import { createTagsRealtimeState } from './useTagsRealtimeState.js'

function createHarness() {
  const calls = []
  const state = createTagsRealtimeState({
    async loadTags() {
      calls.push('load-tags')
    },
    mergePayload(payload) {
      calls.push(['merge-payload', payload])
    },
    trackedDiscussionIds() {
      return [7, 9]
    },
  })

  return {
    calls,
    state,
  }
}

test('tags realtime state refreshes tags for refresh-class events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 7,
      event_type: 'discussion.hidden',
      payload: {},
    },
  })

  assert.deepEqual(harness.calls, ['load-tags'])
})

test('tags realtime state merges payload for tracked updates', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 9,
      event_type: 'post.created',
      payload: {
        tags: [{ id: 2 }],
      },
    },
  })

  assert.deepEqual(harness.calls, [[
    'merge-payload',
    { tags: [{ id: 2 }] },
  ]])
})

test('tags realtime state ignores untracked events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 99,
      event_type: 'post.created',
      payload: {
        tags: [{ id: 3 }],
      },
    },
  })

  assert.deepEqual(harness.calls, [])
})
