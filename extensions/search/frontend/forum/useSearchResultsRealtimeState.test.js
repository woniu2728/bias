import test from 'node:test'
import assert from 'node:assert/strict'
import { createSearchResultsRealtimeState } from './useSearchResultsRealtimeState.js'

function createHarness() {
  const calls = []
  const state = createSearchResultsRealtimeState({
    async loadResults() {
      calls.push('loadResults')
    },
    mergePayload(payload) {
      calls.push(['mergePayload', payload])
    },
    trackedDiscussionIds() {
      return [12, 18]
    },
  })

  return {
    calls,
    state,
  }
}

test('search results realtime state refreshes page for refresh-class forum events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 12,
      event_type: 'discussion.hidden',
      payload: {},
    },
  })

  assert.deepEqual(harness.calls, ['loadResults'])
})

test('search results realtime state merges payload for tracked discussion updates', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 18,
      event_type: 'post.created',
      payload: {
        posts: [{ id: 88 }],
      },
    },
  })

  assert.deepEqual(harness.calls, [[
    'mergePayload',
    { posts: [{ id: 88 }] },
  ]])
})

test('search results realtime state ignores untracked discussion events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 99,
      event_type: 'post.created',
      payload: {
        posts: [{ id: 99 }],
      },
    },
  })

  assert.deepEqual(harness.calls, [])
})
