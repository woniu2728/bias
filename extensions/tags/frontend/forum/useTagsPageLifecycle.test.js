import test from 'node:test'
import assert from 'node:assert/strict'
import { createTagsPageLifecycle } from './useTagsPageLifecycle.js'

function createLifecycleHarness() {
  const calls = []
  const lifecycle = createTagsPageLifecycle({
    addForumEventListener() {
      calls.push('add-forum-event-listener')
    },
    cleanupTrackedDiscussionIds() {
      calls.push('cleanup-tracked-discussion-ids')
    },
    forumEventHandler() {},
    async loadInitialTags() {
      calls.push('load-initial-tags')
    },
    removeForumEventListener() {
      calls.push('remove-forum-event-listener')
    },
    syncTrackedDiscussionIds(nextTrackedIds, previousTrackedIds) {
      calls.push(['sync-tracked-discussion-ids', nextTrackedIds, previousTrackedIds])
    },
  })

  return {
    calls,
    lifecycle,
  }
}

test('tags page lifecycle loads initial tags and registers forum event listener on mount', async () => {
  const harness = createLifecycleHarness()

  await harness.lifecycle.handleMounted()

  assert.deepEqual(harness.calls, [
    'load-initial-tags',
    'add-forum-event-listener',
  ])
})

test('tags page lifecycle clears tracked ids and listeners on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.deepEqual(harness.calls, [
    'cleanup-tracked-discussion-ids',
    'remove-forum-event-listener',
  ])
})

test('tags page lifecycle delegates tracked discussion id synchronization', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleTrackedDiscussionIdsChange([1, 2], [3])

  assert.deepEqual(harness.calls, [
    ['sync-tracked-discussion-ids', [1, 2], [3]],
  ])
})
