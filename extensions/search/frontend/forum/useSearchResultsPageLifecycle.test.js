import test from 'node:test'
import assert from 'node:assert/strict'
import { createSearchResultsPageLifecycle } from './useSearchResultsPageLifecycle.js'

function createLifecycleHarness() {
  const calls = []
  const lifecycle = createSearchResultsPageLifecycle({
    abortActiveRequest() {
      calls.push('abort-active-request')
    },
    addForumEventListener() {
      calls.push('add-forum-event-listener')
    },
    cleanupTrackedDiscussionIds() {
      calls.push('cleanup-tracked-discussion-ids')
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

test('search results page lifecycle registers forum event listener on mount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleMounted()

  assert.deepEqual(harness.calls, ['add-forum-event-listener'])
})

test('search results page lifecycle aborts request and clears subscriptions on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.deepEqual(harness.calls, [
    'abort-active-request',
    'cleanup-tracked-discussion-ids',
    'remove-forum-event-listener',
  ])
})

test('search results page lifecycle delegates tracked discussion id synchronization', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleTrackedDiscussionIdsChange([1, 2], [3])

  assert.deepEqual(harness.calls, [
    ['sync-tracked-discussion-ids', [1, 2], [3]],
  ])
})
