import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileContentState } from './useProfileContentState.js'

function createResourceStore() {
  const buckets = {
    discussions: {},
    posts: {},
  }

  return {
    list(type, ids = []) {
      return ids.map(id => buckets[type]?.[String(id)]).filter(Boolean)
    },
    upsert(type, item) {
      const normalized = { ...item, id: Number(item.id) }
      buckets[type][String(normalized.id)] = normalized
      return normalized
    },
  }
}

function createHarness(overrides = {}) {
  const calls = []
  const activeTab = { value: overrides.activeTab ?? 'discussions' }
  const userId = { value: overrides.userId ?? 7 }
  const user = overrides.user ?? { id: 7, username: 'alice' }

  const forumRealtimeStore = {
    trackDiscussionIds(ids) {
      calls.push(['trackDiscussionIds', ids])
    },
    untrackDiscussionIds(ids) {
      calls.push(['untrackDiscussionIds', ids])
    },
  }

  const state = createProfileContentState({
    activeTab,
    forumRealtimeStore,
    getErrorMessage(error, fallback) {
      return error?.message || fallback
    },
    getLoadDiscussionsErrorText() {
      return '加载讨论失败'
    },
    getLoadPostsErrorText() {
      return '加载回复失败'
    },
    getUser() {
      return user
    },
    requestedListStateFactory(options) {
      return {
        loading: { value: false },
        async refresh(payload) {
          calls.push(['refresh', payload])
          return options.load()
        },
      }
    },
    resourceStore: createResourceStore(),
    setSettingsError(message) {
      calls.push(['setSettingsError', message])
    },
    userId,
  })

  return {
    activeTab,
    calls,
    state,
    userId,
  }
}

test('profile content state merges post ids without duplicates', () => {
  const harness = createHarness()

  harness.state.postIds.value = [1, 2]
  harness.state.mergePostIds([2, 3, 1, 4])

  assert.deepEqual(harness.state.postIds.value, [1, 2, 3, 4])
})

test('profile content state marks current user posts as requested when switching to posts tab', () => {
  const harness = createHarness()

  harness.state.markPostsRequestedForCurrentUser()

  assert.equal(harness.state.requestedPostUserId.value, 7)
})

test('profile content state cleanup delegates tracked discussion cleanup', () => {
  const harness = createHarness()
  harness.state.discussionIds.value = [11, 12]

  harness.state.cleanupTrackedDiscussions()

  assert.deepEqual(harness.calls, [[
    'untrackDiscussionIds',
    [11, 12],
  ]])
})
