import test from 'node:test'
import assert from 'node:assert/strict'
import { createDiscussionListPageLifecycle } from './useDiscussionListPageLifecycle.js'

function createLifecycleHarness() {
  const calls = []
  const lifecycle = createDiscussionListPageLifecycle({
    addDiscussionReadStateListener() {
      calls.push('add-discussion-read-state-listener')
    },
    addForumEventListener() {
      calls.push('add-forum-event-listener')
    },
    cleanupTrackedDiscussionIds() {
      calls.push('cleanup-tracked-discussion-ids')
    },
    clearPendingReturnRestore() {
      calls.push('clear-pending-return-restore')
    },
    getPendingReturnRestore() {
      calls.push('get-pending-return-restore')
      return null
    },
    removeDiscussionReadStateListener() {
      calls.push('remove-discussion-read-state-listener')
    },
    removeForumEventListener() {
      calls.push('remove-forum-event-listener')
    },
    syncTrackedDiscussionIds(nextDiscussionIds, previousDiscussionIds) {
      calls.push(['sync-tracked-discussion-ids', nextDiscussionIds, previousDiscussionIds])
    },
  })

  return {
    calls,
    lifecycle,
  }
}

test('discussion list page lifecycle registers browser listeners on mount', () => {
  const harness = createLifecycleHarness()

  return harness.lifecycle.handleMounted().then(() => {
    assert.deepEqual(harness.calls, [
      'add-discussion-read-state-listener',
      'add-forum-event-listener',
      'get-pending-return-restore',
    ])
  })
})

test('discussion list page lifecycle restores pending discussion item into view', async () => {
  const scrollCalls = []
  const originalDocument = globalThis.document
  const originalHTMLElement = globalThis.HTMLElement

  class MockElement {
    scrollIntoView(options) {
      scrollCalls.push(options)
    }
  }

  globalThis.HTMLElement = MockElement
  globalThis.document = {
    querySelector(selector) {
      assert.equal(selector, '[data-discussion-id="42"]')
      return new MockElement()
    },
  }

  const lifecycle = createDiscussionListPageLifecycle({
    addDiscussionReadStateListener() {},
    addForumEventListener() {},
    clearPendingReturnRestore() {
      scrollCalls.push('cleared')
    },
    cleanupTrackedDiscussionIds() {},
    getPendingReturnRestore() {
      return 42
    },
    removeDiscussionReadStateListener() {},
    removeForumEventListener() {},
    syncTrackedDiscussionIds() {},
  })

  try {
    await lifecycle.handleDiscussionsChange()
  } finally {
    globalThis.document = originalDocument
    globalThis.HTMLElement = originalHTMLElement
  }

  assert.deepEqual(scrollCalls, [
    'cleared',
    { behavior: 'auto', block: 'center' },
  ])
})

test('discussion list page lifecycle clears tracked ids and listeners on unmount', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleBeforeUnmount()

  assert.deepEqual(harness.calls, [
    'cleanup-tracked-discussion-ids',
    'remove-discussion-read-state-listener',
    'remove-forum-event-listener',
  ])
})

test('discussion list page lifecycle delegates tracked discussion synchronization', () => {
  const harness = createLifecycleHarness()

  harness.lifecycle.handleCurrentDiscussionIdsChange([1, 2], [2, 3])

  assert.deepEqual(harness.calls, [
    ['sync-tracked-discussion-ids', [1, 2], [2, 3]],
  ])
})
