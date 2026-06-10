import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileRealtimeState } from './useProfileRealtimeState.js'

function createHarness(overrides = {}) {
  const calls = []
  const state = createProfileRealtimeState({
    getActiveTab() {
      return overrides.activeTab ?? 'posts'
    },
    getCurrentUserId() {
      return overrides.currentUserId ?? 7
    },
    getDiscussionIds() {
      return overrides.discussionIds ?? [12, 18]
    },
    getPosts() {
      return overrides.posts ?? [{ id: 88, discussion_id: 12 }]
    },
    getRequestedPostUserId() {
      return overrides.requestedPostUserId ?? 7
    },
    async loadDiscussions() {
      calls.push('loadDiscussions')
    },
    async loadPosts(payload) {
      calls.push(['loadPosts', payload])
    },
    mergePostIds(ids) {
      calls.push(['mergePostIds', ids])
    },
    resourceStore: {
      mergePayload(payload) {
        calls.push(['mergePayload', payload])
      },
    },
  })

  return {
    calls,
    state,
  }
}

test('profile realtime state refreshes discussions and posts for tracked refresh-class events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 12,
      event_type: 'post.hidden',
      payload: {},
    },
  })

  assert.deepEqual(harness.calls, [
    'loadDiscussions',
    ['loadPosts', { force: true, forceLoading: false }],
  ])
})

test('profile realtime state merges payload and appends visible post ids for tracked updates', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 12,
      event_type: 'post.created',
      payload: {
        post: { id: 99, discussion_id: 12 },
      },
    },
  })

  assert.deepEqual(harness.calls, [
    ['mergePayload', {
      post: { id: 99, discussion_id: 12 },
    }],
    ['mergePostIds', [99]],
  ])
})

test('profile realtime state ignores untracked discussion events', async () => {
  const harness = createHarness()

  await harness.state.handleForumEvent({
    detail: {
      discussion_id: 99,
      event_type: 'post.created',
      payload: {
        post: { id: 77, discussion_id: 99 },
      },
    },
  })

  assert.deepEqual(harness.calls, [])
})
